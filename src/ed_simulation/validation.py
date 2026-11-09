"""Quantitative validation against the NHAMCS WAITTIME reference."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .calibration import OUTPUT_FILES
from .experiments import validate_runs


VALIDATION_METRICS: dict[str, str] = {
    "mean_wait_minutes": "minutes",
    "median_wait_minutes": "minutes",
    "p90_wait_minutes": "minutes",
    "share_wait_over_60": "proportion",
}


def load_overall_reference(processed_dir: Path | str) -> pd.DataFrame:
    """Load the independent overall NHAMCS WAITTIME validation targets."""

    path = Path(processed_dir) / OUTPUT_FILES["reference_metrics"]
    reference = pd.read_csv(path)
    overall = reference[
        (reference["group_type"] == "overall") & (reference["group"] == "all")
    ].copy()
    overall = overall[overall["metric"].isin(VALIDATION_METRICS)].copy()
    if set(overall["metric"]) != set(VALIDATION_METRICS):
        raise ValueError("la referencia no contiene las cuatro métricas esperadas")
    for row in overall.itertuples():
        if VALIDATION_METRICS[row.metric] != row.unit:
            raise ValueError(f"unidad incompatible para {row.metric}: {row.unit}")
    return overall.sort_values("metric", kind="stable").reset_index(drop=True)


def validation_comparison(
    runs: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    nominal_demand: float = 1.0,
) -> pd.DataFrame:
    """Compare reference, base and candidate using identical metrics and units."""

    validate_runs(runs)
    nominal = runs[np.isclose(runs["demand_multiplier"], nominal_demand)]
    if set(nominal["schedule_id"]) != {"base", "candidate"}:
        raise ValueError("faltan base o candidate bajo demanda nominal")
    ref = reference.set_index("metric")
    rows: list[dict[str, object]] = []
    for metric, expected_unit in VALIDATION_METRICS.items():
        if metric not in ref.index:
            raise ValueError(f"falta la referencia {metric}")
        unit = str(ref.loc[metric, "unit"])
        if unit != expected_unit:
            raise ValueError(f"unidad incompatible para {metric}: {unit}")
        reference_value = float(ref.loc[metric, "value"])
        base_values = nominal[nominal["schedule_id"] == "base"][metric].astype(float)
        candidate_values = nominal[
            nominal["schedule_id"] == "candidate"
        ][metric].astype(float)
        base_value = float(base_values.mean())
        candidate_value = float(candidate_values.mean())
        change = candidate_value - base_value
        rows.append(
            {
                "metric": metric,
                "unit": unit,
                "reference_value": reference_value,
                "reference_se": _optional_number(ref.loc[metric, "se"]),
                "reference_ci95_low": _optional_number(
                    ref.loc[metric, "ci95_low"]
                ),
                "reference_ci95_high": _optional_number(
                    ref.loc[metric, "ci95_high"]
                ),
                "reference_n_unweighted": int(ref.loc[metric, "n_unweighted"]),
                "base_simulation_mean": base_value,
                "candidate_simulation_mean": candidate_value,
                "base_absolute_error": abs(base_value - reference_value),
                "base_relative_error_percent": (
                    100.0 * abs(base_value - reference_value) / reference_value
                    if reference_value != 0
                    else np.nan
                ),
                "candidate_absolute_error": abs(candidate_value - reference_value),
                "candidate_minus_base": change,
                "improvement_base_minus_candidate": -change,
                "improvement_percent": (
                    -100.0 * change / base_value if base_value != 0 else np.nan
                ),
                "reference_source_category": "derived_from_public",
                "simulation_source_category": "synthetic_simulation",
                "claim_scope": "simulated improvement; not observed real-world change",
            }
        )
    return pd.DataFrame(rows)


def validation_diagnostics(comparison: pd.DataFrame) -> dict[str, float]:
    """Aggregate transparent error summaries without mixing proportions/minutes."""

    minute_rows = comparison[comparison["unit"] == "minutes"]
    proportion_rows = comparison[comparison["unit"] == "proportion"]
    return {
        "base_mae_minutes": float(minute_rows["base_absolute_error"].mean()),
        "candidate_mae_minutes": float(
            minute_rows["candidate_absolute_error"].mean()
        ),
        "base_mae_proportion_points": float(
            proportion_rows["base_absolute_error"].mean()
        ),
        "candidate_mae_proportion_points": float(
            proportion_rows["candidate_absolute_error"].mean()
        ),
    }


def _optional_number(value: object) -> float | None:
    """Convert pandas missing values to JSON-friendly ``None``."""

    return None if pd.isna(value) else float(value)
