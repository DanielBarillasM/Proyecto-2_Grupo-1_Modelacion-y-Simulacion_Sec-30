"""Reproducible paired experiments for the calibrated ED simulation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import NormalDist
from time import perf_counter
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from .calibration import DEFAULT_REFERENCE_VOLUME, load_calibrated_config
from .simulation import simulate


EXPERIMENT_ID = "nhamcs_2022_staffing_v1"
DEFAULT_DEMAND_LEVELS = (0.80, 1.00, 1.20)
SUMMARY_METRICS: dict[str, str] = {
    "arrived": "patients",
    "mean_wait_minutes": "minutes",
    "median_wait_minutes": "minutes",
    "p90_wait_minutes": "minutes",
    "share_wait_over_60": "proportion",
    "mean_queue": "patients",
    "maximum_queue": "patients",
    "resource_utilization": "proportion",
    "drain_minutes": "minutes",
}
PAIRED_METRICS: dict[str, str] = {
    "mean_wait_minutes": "minutes",
    "median_wait_minutes": "minutes",
    "p90_wait_minutes": "minutes",
    "share_wait_over_60": "proportion",
    "mean_queue": "patients",
    "maximum_queue": "patients",
}


@dataclass(frozen=True)
class ExperimentCondition:
    """One schedule-demand combination in the final factorial design."""

    condition_id: str
    schedule_id: str
    capacity_schedule: tuple[int, ...]
    demand_multiplier: float

    def __post_init__(self) -> None:
        if not self.condition_id:
            raise ValueError("condition_id no puede estar vacío")
        if self.schedule_id not in {"base", "candidate"}:
            raise ValueError("schedule_id debe ser base o candidate")
        if len(self.capacity_schedule) != 6:
            raise ValueError("capacity_schedule debe tener seis bloques")
        if self.demand_multiplier <= 0:
            raise ValueError("demand_multiplier debe ser positivo")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["capacity_schedule"] = list(self.capacity_schedule)
        return payload


def factorial_conditions(
    baseline_schedule: Sequence[int],
    candidate_schedule: Sequence[int],
    demand_levels: Iterable[float] = DEFAULT_DEMAND_LEVELS,
) -> tuple[ExperimentCondition, ...]:
    """Build two schedules by three demand levels (six conditions)."""

    schedules = {
        "base": tuple(int(value) for value in baseline_schedule),
        "candidate": tuple(int(value) for value in candidate_schedule),
    }
    conditions = []
    for demand in demand_levels:
        demand = float(demand)
        suffix = f"{round(demand * 100):03d}"
        for schedule_id, schedule in schedules.items():
            conditions.append(
                ExperimentCondition(
                    condition_id=f"{schedule_id}_demand_{suffix}",
                    schedule_id=schedule_id,
                    capacity_schedule=schedule,
                    demand_multiplier=demand,
                )
            )
    return tuple(conditions)


def run_experiment(
    processed_dir: Path | str,
    conditions: Sequence[ExperimentCondition],
    seeds: Sequence[int],
    *,
    experiment_id: str = EXPERIMENT_ID,
    reference_volume: str = DEFAULT_REFERENCE_VOLUME,
    config_overrides: dict[str, object] | None = None,
) -> pd.DataFrame:
    """Run every condition with common seeds across schedule pairs."""

    if len(conditions) < 3:
        raise ValueError("se requieren al menos tres condiciones")
    seeds = tuple(int(seed) for seed in seeds)
    if not seeds or len(set(seeds)) != len(seeds) or min(seeds) < 0:
        raise ValueError("las semillas deben ser únicas y no negativas")
    if len({condition.condition_id for condition in conditions}) != len(conditions):
        raise ValueError("condition_id debe ser único")
    overrides = dict(config_overrides or {})

    rows: list[dict[str, object]] = []
    for condition in conditions:
        for replicate, seed in enumerate(seeds, start=1):
            config = load_calibrated_config(
                processed_dir,
                reference_volume=reference_volume,
                demand_multiplier=condition.demand_multiplier,
                capacity_schedule=condition.capacity_schedule,
                seed=seed,
                **overrides,
            )
            started = perf_counter()
            result = simulate(config)
            runtime_seconds = perf_counter() - started
            rows.append(
                {
                    "experiment_id": experiment_id,
                    "condition_id": condition.condition_id,
                    "schedule_id": condition.schedule_id,
                    "demand_multiplier": condition.demand_multiplier,
                    "replicate": replicate,
                    "seed": seed,
                    **result.metrics,
                    "runtime_seconds": round(runtime_seconds, 6),
                }
            )
    runs = pd.DataFrame(rows)
    validate_runs(runs, expected_replicates=len(seeds))
    return runs.sort_values(
        ["demand_multiplier", "schedule_id", "replicate"],
        kind="stable",
    ).reset_index(drop=True)


def validate_runs(
    runs: pd.DataFrame,
    *,
    expected_replicates: int | None = None,
    minimum_conditions: int = 3,
) -> None:
    """Fail when a run table cannot support the required comparison."""

    required = {
        "experiment_id",
        "condition_id",
        "schedule_id",
        "demand_multiplier",
        "replicate",
        "seed",
        "arrived",
        "started_service",
        "completed",
        "not_started_at_end",
        "mean_wait_minutes",
        "median_wait_minutes",
        "p90_wait_minutes",
        "share_wait_over_60",
        "mean_queue",
        "maximum_queue",
        "resource_utilization",
        "runtime_seconds",
    }
    missing = required - set(runs.columns)
    if missing:
        raise ValueError(f"faltan columnas de resultados: {sorted(missing)}")
    if runs["condition_id"].nunique() < minimum_conditions:
        raise ValueError("no se alcanzó el mínimo de condiciones")
    duplicates = runs.duplicated(["condition_id", "seed"])
    if duplicates.any():
        raise ValueError("condition_id y seed deben identificar una ejecución")
    if (runs["not_started_at_end"] != 0).any():
        raise ValueError("el experimento contiene esperas censuradas tras el drenaje")
    if (runs["resource_utilization"] > 1.0 + 1e-9).any():
        raise ValueError("la utilización efectiva supera 1")
    counts = runs.groupby("condition_id")["seed"].nunique()
    if expected_replicates is not None and not counts.eq(expected_replicates).all():
        raise ValueError("cada condición debe tener el mismo número de réplicas")

    for demand, group in runs.groupby("demand_multiplier"):
        schedule_ids = set(group["schedule_id"])
        if schedule_ids != {"base", "candidate"}:
            raise ValueError(f"demanda {demand} no contiene base y candidate")
        seed_sets = {
            schedule_id: set(part["seed"])
            for schedule_id, part in group.groupby("schedule_id")
        }
        if seed_sets["base"] != seed_sets["candidate"]:
            raise ValueError("base y candidate deben usar semillas comunes")


def summarize_runs(runs: pd.DataFrame) -> pd.DataFrame:
    """Compute descriptive statistics and normal 95 % mean intervals."""

    validate_runs(runs)
    rows: list[dict[str, object]] = []
    z95 = NormalDist().inv_cdf(0.975)
    group_columns = [
        "experiment_id",
        "condition_id",
        "schedule_id",
        "demand_multiplier",
    ]
    for keys, group in runs.groupby(group_columns, sort=True):
        metadata = dict(zip(group_columns, keys))
        for metric, unit in SUMMARY_METRICS.items():
            values = group[metric].astype(float)
            n = int(len(values))
            mean = float(values.mean())
            std = float(values.std(ddof=1)) if n > 1 else 0.0
            half_width = z95 * std / np.sqrt(n) if n > 1 else 0.0
            rows.append(
                {
                    **metadata,
                    "metric": metric,
                    "unit": unit,
                    "n": n,
                    "mean": mean,
                    "std": std,
                    "ci95_low": mean - half_width,
                    "ci95_high": mean + half_width,
                    "median": float(values.median()),
                    "p10": float(values.quantile(0.10)),
                    "p90": float(values.quantile(0.90)),
                    "minimum": float(values.min()),
                    "maximum": float(values.max()),
                    "source_category": "synthetic_simulation",
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["metric", "demand_multiplier", "schedule_id"], kind="stable"
    ).reset_index(drop=True)


def paired_differences(runs: pd.DataFrame) -> pd.DataFrame:
    """Return seed-level base minus candidate effects for every demand level."""

    validate_runs(runs)
    rows: list[dict[str, object]] = []
    for demand, demand_runs in runs.groupby("demand_multiplier", sort=True):
        base = demand_runs[demand_runs["schedule_id"] == "base"].set_index("seed")
        candidate = demand_runs[
            demand_runs["schedule_id"] == "candidate"
        ].set_index("seed")
        common = sorted(set(base.index) & set(candidate.index))
        for seed in common:
            for metric, unit in PAIRED_METRICS.items():
                base_value = float(base.loc[seed, metric])
                candidate_value = float(candidate.loc[seed, metric])
                improvement = base_value - candidate_value
                rows.append(
                    {
                        "experiment_id": str(base.loc[seed, "experiment_id"]),
                        "demand_multiplier": float(demand),
                        "seed": int(seed),
                        "metric": metric,
                        "unit": unit,
                        "base_value": base_value,
                        "candidate_value": candidate_value,
                        "candidate_minus_base": candidate_value - base_value,
                        "improvement_base_minus_candidate": improvement,
                        "improvement_percent": (
                            100.0 * improvement / base_value
                            if base_value != 0
                            else np.nan
                        ),
                        "source_category": "synthetic_simulation",
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["metric", "demand_multiplier", "seed"], kind="stable"
    ).reset_index(drop=True)
