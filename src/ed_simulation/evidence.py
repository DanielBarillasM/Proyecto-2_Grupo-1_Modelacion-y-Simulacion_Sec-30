"""Freeze the optimized schedule and write auditable experimental evidence."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
from math import ceil
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .calibration import DEFAULT_REFERENCE_VOLUME, OUTPUT_FILES, load_calibrated_config
from .experiments import (
    EXPERIMENT_ID,
    ExperimentCondition,
    factorial_conditions,
    paired_differences,
    run_experiment,
    summarize_paired_differences,
    summarize_runs,
)
from .optimization import (
    GAConfig,
    OptimizationConstraints,
    is_feasible,
    optimize_staffing,
)
from .validation import (
    load_overall_reference,
    validation_comparison,
    validation_diagnostics,
)


DEFAULT_OPTIMIZATION_SEED_START = 10_000
DEFAULT_EVALUATION_SEED_START = 30_000
DEFAULT_ALGORITHM_SEED = 9_101


def freeze_candidate(
    processed_dir: Path | str,
    *,
    population_size: int = 24,
    generations: int = 20,
    optimization_replicates: int = 10,
    algorithm_seed: int = DEFAULT_ALGORITHM_SEED,
    optimization_seed_start: int = DEFAULT_OPTIMIZATION_SEED_START,
    evaluation_seed_start: int = DEFAULT_EVALUATION_SEED_START,
) -> dict[str, Any]:
    """Optimize calibrated nominal demand using no final-evaluation seeds."""

    base_config = load_calibrated_config(
        processed_dir,
        reference_volume=DEFAULT_REFERENCE_VOLUME,
        demand_multiplier=1.0,
        seed=optimization_seed_start,
    )
    constraints = OptimizationConstraints(
        blocks=len(base_config.capacity_schedule),
        total_capacity_units=sum(base_config.capacity_schedule),
        min_capacity=1,
        max_capacity=8,
        max_step_change=3,
    )
    ga_config = GAConfig(
        population_size=population_size,
        generations=generations,
        patience=min(8, generations),
        evaluation_replicates=optimization_replicates,
        evaluation_seed_start=optimization_seed_start,
        algorithm_seed=algorithm_seed,
    )
    result = optimize_staffing(base_config, constraints, ga_config)
    candidate = tuple(result.best.schedule)
    if not is_feasible(candidate, constraints):
        raise RuntimeError("la candidata congelada no satisface las restricciones")
    optimization_seeds = set(ga_config.evaluation_seeds)
    if evaluation_seed_start in optimization_seeds:
        raise ValueError("las semillas de optimización y evaluación se traslapan")
    optimization_payload = result.to_dict()
    optimization_payload["evidence_status"] = "candidate_selected_with_calibrated_inputs"
    optimization_payload["claim_scope"] = (
        "candidate selection only; final evaluation uses independent seeds"
    )
    return {
        "schema_version": 1,
        "candidate_status": "frozen_before_final_evaluation",
        "claim_scope": "simulated improvement only; not observed real-world improvement",
        "calibration": {
            "dataset": "NHAMCS 2022",
            "reference_volume": DEFAULT_REFERENCE_VOLUME,
            "demand_multiplier": 1.0,
        },
        "baseline_schedule": list(base_config.capacity_schedule),
        "candidate_schedule": list(candidate),
        "constraints": asdict(constraints),
        "optimization_seed_role": "candidate selection only",
        "optimization_seeds": list(ga_config.evaluation_seeds),
        "reserved_evaluation_seed_start": evaluation_seed_start,
        "optimization": optimization_payload,
    }


def load_frozen_candidate(path: Path | str) -> dict[str, Any]:
    """Load and validate the minimal frozen-candidate contract."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "candidate_status",
        "baseline_schedule",
        "candidate_schedule",
        "constraints",
        "optimization_seeds",
        "reserved_evaluation_seed_start",
    }
    missing = required - set(payload)
    if missing:
        raise ValueError(f"faltan campos en frozen_candidate: {sorted(missing)}")
    if payload["candidate_status"] != "frozen_before_final_evaluation":
        raise ValueError("la candidata no está marcada como congelada")
    constraints = OptimizationConstraints(**payload["constraints"])
    if not is_feasible(payload["candidate_schedule"], constraints):
        raise ValueError("la candidata guardada no es factible")
    return payload


def write_json(path: Path | str, payload: object) -> Path:
    """Write stable UTF-8 JSON with a trailing newline."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path


def generate_evidence_bundle(
    processed_dir: Path | str,
    output_dir: Path | str,
    frozen_candidate: dict[str, Any],
    *,
    replicates: int = 30,
    evaluation_seed_start: int = DEFAULT_EVALUATION_SEED_START,
    git_commit: str = "unknown",
) -> dict[str, Path]:
    """Run, summarize, validate, visualize and manifest the final design."""

    if replicates < 1:
        raise ValueError("replicates debe ser al menos 1")
    optimization_seeds = set(int(seed) for seed in frozen_candidate["optimization_seeds"])
    evaluation_seeds = tuple(
        evaluation_seed_start + index for index in range(replicates)
    )
    overlap = optimization_seeds & set(evaluation_seeds)
    if overlap:
        raise ValueError(f"semillas de optimización reutilizadas: {sorted(overlap)}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    conditions = factorial_conditions(
        frozen_candidate["baseline_schedule"],
        frozen_candidate["candidate_schedule"],
    )
    runs = run_experiment(processed_dir, conditions, evaluation_seeds)
    summary = summarize_runs(runs)
    paired = paired_differences(runs)
    paired_summary = summarize_paired_differences(paired)
    reference = load_overall_reference(processed_dir)
    comparison = validation_comparison(runs, reference)

    paths = {
        "frozen_candidate": output_dir / "frozen_candidate.json",
        "runs": output_dir / "runs.csv",
        "summary": output_dir / "summary.csv",
        "paired_differences": output_dir / "paired_differences.csv",
        "paired_summary": output_dir / "paired_summary.csv",
        "validation_comparison": output_dir / "validation_comparison.csv",
    }
    write_json(paths["frozen_candidate"], frozen_candidate)
    for name, frame in (
        ("runs", runs),
        ("summary", summary),
        ("paired_differences", paired),
        ("paired_summary", paired_summary),
        ("validation_comparison", comparison),
    ):
        frame.to_csv(paths[name], index=False, lineterminator="\n")

    figure_paths = write_svg_figures(summary, paired, comparison, output_dir / "figures")
    paths.update({f"figure_{path.stem}": path for path in figure_paths})
    manifest = build_manifest(
        processed_dir=processed_dir,
        output_dir=output_dir,
        conditions=conditions,
        frozen_candidate=frozen_candidate,
        evaluation_seeds=evaluation_seeds,
        validation=comparison,
        git_commit=git_commit,
        generated_files=[*paths.values()],
    )
    paths["manifest"] = write_json(output_dir / "manifest.json", manifest)
    return paths


def build_manifest(
    *,
    processed_dir: Path | str,
    output_dir: Path | str,
    conditions: Sequence[ExperimentCondition],
    frozen_candidate: dict[str, Any],
    evaluation_seeds: Sequence[int],
    validation: pd.DataFrame,
    git_commit: str,
    generated_files: Sequence[Path],
) -> dict[str, Any]:
    """Create the audit manifest required by the experimental contract."""

    processed_dir = Path(processed_dir)
    output_dir = Path(output_dir)
    data_files = [processed_dir / filename for filename in OUTPUT_FILES.values()]
    constraints = frozen_candidate["constraints"]
    diagnostics = validation_diagnostics(validation)
    packages = {}
    for package in ("numpy", "pandas", "simpy", "streamlit", "plotly", "pytest"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_of_generator": git_commit,
        "python": platform.python_version(),
        "dependencies": packages,
        "data": {
            "dataset": "NHAMCS 2022 Emergency Department Public Use File",
            "processed_sha256": {
                path.name: _sha256(path) for path in data_files if path.exists()
            },
            "reference_volume": DEFAULT_REFERENCE_VOLUME,
            "source_category": "derived_from_public",
        },
        "model": {
            "warmup_days": 1,
            "measurement_days": 1,
            "terminal_policy": "stop arrivals and drain measured cohort until every patient starts service",
            "utilization_denominator": "effective patient-usable capacity exposure during the measurement window",
        },
        "conditions": [condition.to_dict() for condition in conditions],
        "schedules": {
            "base": frozen_candidate["baseline_schedule"],
            "candidate": frozen_candidate["candidate_schedule"],
        },
        "constraints": constraints,
        "genetic_algorithm": frozen_candidate["optimization"]["ga_config"],
        "seeds": {
            "algorithm": frozen_candidate["optimization"]["ga_config"][
                "algorithm_seed"
            ],
            "optimization": frozen_candidate["optimization_seeds"],
            "evaluation": list(evaluation_seeds),
            "pairing": "base and candidate share each evaluation seed within demand level",
        },
        "validation_diagnostics": diagnostics,
        "claim_scope": "candidate results are synthetic simulations; NHAMCS is a US public reference, not an observed intervention",
        "commands": [
            "python scripts/generate_evidence.py",
            "python scripts/run_experiments.py --candidate evidence/final/frozen_candidate.json",
        ],
        "files": sorted(
            {
                "manifest.json",
                *(
                    str(path.relative_to(output_dir)).replace("\\", "/")
                    for path in generated_files
                ),
            }
        ),
    }


def write_svg_figures(
    summary: pd.DataFrame,
    paired: pd.DataFrame,
    comparison: pd.DataFrame,
    output_dir: Path | str,
) -> list[Path]:
    """Generate three dependency-free, reproducible SVG evidence charts."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        output_dir / "mean_wait_by_condition.svg",
        output_dir / "paired_wait_improvement.svg",
        output_dir / "validation_comparison.svg",
    ]
    paths[0].write_text(_condition_figure(summary), encoding="utf-8")
    paths[1].write_text(_paired_figure(paired), encoding="utf-8")
    paths[2].write_text(_validation_figure(comparison), encoding="utf-8")
    return paths


def _condition_figure(summary: pd.DataFrame) -> str:
    data = summary[summary["metric"] == "mean_wait_minutes"].sort_values(
        ["demand_multiplier", "schedule_id"], kind="stable"
    )
    maximum = max(float(data["ci95_high"].max()), 1.0)
    width, height = 960, 560
    left, top, chart_w, chart_h = 90, 100, 810, 350
    elements = _svg_header(
        width,
        height,
        "Espera media por condición",
        "Media e intervalo de confianza del 95 %; 30 réplicas por condición",
    )
    elements += _axes(left, top, chart_w, chart_h, maximum, "Espera media (min)")
    bar_w = chart_w / max(len(data), 1) * 0.62
    for index, row in enumerate(data.itertuples()):
        center = left + (index + 0.5) * chart_w / len(data)
        value = float(row.mean)
        bar_h = chart_h * value / maximum
        color = "#176B87" if row.schedule_id == "base" else "#2A9D8F"
        elements.append(
            f'<rect x="{center-bar_w/2:.1f}" y="{top+chart_h-bar_h:.1f}" '
            f'width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" rx="4"/>'
        )
        low_y = top + chart_h * (1 - float(row.ci95_low) / maximum)
        high_y = top + chart_h * (1 - float(row.ci95_high) / maximum)
        elements.append(
            f'<line x1="{center:.1f}" y1="{high_y:.1f}" x2="{center:.1f}" y2="{low_y:.1f}" stroke="#20262E" stroke-width="2"/>'
        )
        label = f"{int(round(row.demand_multiplier*100))}% {'Base' if row.schedule_id == 'base' else 'Mejora'}"
        elements.append(
            f'<text x="{center:.1f}" y="{top+chart_h+28}" text-anchor="middle" class="axis">{escape(label)}</text>'
        )
        elements.append(
            f'<text x="{center:.1f}" y="{top+chart_h-bar_h-8:.1f}" text-anchor="middle" class="value">{value:.1f}</text>'
        )
    elements += _legend(width - 260, 62)
    return "".join(elements) + "</svg>\n"


def _paired_figure(paired: pd.DataFrame) -> str:
    data = paired[paired["metric"] == "mean_wait_minutes"].copy()
    values = data["improvement_base_minus_candidate"].astype(float)
    bound = max(abs(float(values.min())), abs(float(values.max())), 1.0)
    bound = float(ceil((bound * 1.1) / 25.0) * 25.0)
    lower, upper = -bound, bound
    width, height = 960, 560
    left, top, chart_w, chart_h = 90, 100, 810, 350
    elements = _svg_header(
        width,
        height,
        "Diferencias pareadas de espera media",
        "Cada punto comparte semilla entre base y candidata; positivo favorece la candidata",
    )
    for tick in np.linspace(lower, upper, 5):
        tick_y = top + chart_h * (upper - float(tick)) / (upper - lower)
        elements.append(
            f'<line x1="{left}" y1="{tick_y:.1f}" x2="{left+chart_w}" y2="{tick_y:.1f}" stroke="#E4E7EC"/>'
        )
        elements.append(
            f'<text x="{left-12}" y="{tick_y+4:.1f}" text-anchor="end" class="axis">{tick:.0f}</text>'
        )
    zero_y = top + chart_h * upper / (upper - lower)
    elements.append(
        f'<line x1="{left}" y1="{zero_y:.1f}" x2="{left+chart_w}" y2="{zero_y:.1f}" stroke="#667085" stroke-dasharray="6 5"/>'
    )
    demands = sorted(data["demand_multiplier"].unique())
    for demand_index, demand in enumerate(demands):
        group = data[np.isclose(data["demand_multiplier"], demand)].sort_values("seed")
        center = left + (demand_index + 0.5) * chart_w / len(demands)
        for point_index, value in enumerate(group["improvement_base_minus_candidate"]):
            jitter = ((point_index % 7) - 3) * 5
            y = top + chart_h * (upper - float(value)) / (upper - lower)
            elements.append(
                f'<circle cx="{center+jitter:.1f}" cy="{y:.1f}" r="4" fill="#2A9D8F" fill-opacity="0.58"/>'
            )
        mean = float(group["improvement_base_minus_candidate"].mean())
        mean_y = top + chart_h * (upper - mean) / (upper - lower)
        elements.append(
            f'<rect x="{center-9:.1f}" y="{mean_y-9:.1f}" width="18" height="18" fill="#D97706" transform="rotate(45 {center:.1f} {mean_y:.1f})"/>'
        )
        elements.append(
            f'<text x="{center:.1f}" y="{top+chart_h+28}" text-anchor="middle" class="axis">Demanda {int(round(demand*100))}%</text>'
        )
        elements.append(
            f'<text x="{center:.1f}" y="{mean_y-16:.1f}" text-anchor="middle" class="value">media {mean:.1f} min</text>'
        )
    elements.append(
        f'<text x="24" y="{top+chart_h/2:.1f}" transform="rotate(-90 24 {top+chart_h/2:.1f})" text-anchor="middle" class="axis">Reducción base - candidata (min)</text>'
    )
    return "".join(elements) + "</svg>\n"


def _validation_figure(comparison: pd.DataFrame) -> str:
    width, height = 960, 650
    elements = _svg_header(
        width,
        height,
        "Referencia real, simulación base y candidata",
        "Demanda nominal; WAITTIME de NHAMCS y métricas simuladas en las mismas unidades",
    )
    labels = {
        "mean_wait_minutes": "Espera media (min)",
        "median_wait_minutes": "Mediana (min)",
        "p90_wait_minutes": "Percentil 90 (min)",
        "share_wait_over_60": "Proporción > 60 min",
    }
    colors = ["#6B7280", "#176B87", "#2A9D8F"]
    names = ["Referencia NHAMCS", "Simulación base", "Simulación candidata"]
    y = 110
    for row in comparison.itertuples():
        values = [
            float(row.reference_value),
            float(row.base_simulation_mean),
            float(row.candidate_simulation_mean),
        ]
        maximum = max(values) or 1.0
        elements.append(f'<text x="70" y="{y}" class="panel">{escape(labels[row.metric])}</text>')
        for index, value in enumerate(values):
            bar_y = y + 16 + index * 28
            bar_w = 620 * value / maximum
            display = f"{value:.3f}" if row.unit == "proportion" else f"{value:.1f}"
            elements.append(
                f'<rect x="230" y="{bar_y}" width="{bar_w:.1f}" height="18" fill="{colors[index]}" rx="3"/>'
            )
            elements.append(f'<text x="70" y="{bar_y+14}" class="axis">{names[index]}</text>')
            elements.append(f'<text x="{240+bar_w:.1f}" y="{bar_y+14}" class="value">{display}</text>')
        y += 132
    elements.append(
        '<text x="70" y="620" class="note">La candidata es una predicción simulada; no representa una mejora observada en un hospital real.</text>'
    )
    return "".join(elements) + "</svg>\n"


def _svg_header(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{escape(title)}</title>",
        f"<desc id=\"desc\">{escape(subtitle)}</desc>",
        "<style>text{font-family:Arial,sans-serif;fill:#20262E}.title{font-size:26px;font-weight:700}.subtitle{font-size:14px;fill:#596273}.axis{font-size:12px}.value{font-size:12px;font-weight:700}.panel{font-size:16px;font-weight:700}.note{font-size:13px;fill:#596273}</style>",
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        f'<text x="48" y="42" class="title">{escape(title)}</text>',
        f'<text x="48" y="68" class="subtitle">{escape(subtitle)}</text>',
    ]


def _axes(
    left: float,
    top: float,
    width: float,
    height: float,
    maximum: float,
    y_label: str,
) -> list[str]:
    elements = []
    for index in range(6):
        value = maximum * index / 5
        y = top + height * (1 - index / 5)
        elements.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left+width}" y2="{y:.1f}" stroke="#E4E7EC"/>'
        )
        elements.append(
            f'<text x="{left-12}" y="{y+4:.1f}" text-anchor="end" class="axis">{value:.0f}</text>'
        )
    elements.append(
        f'<text x="24" y="{top+height/2:.1f}" transform="rotate(-90 24 {top+height/2:.1f})" text-anchor="middle" class="axis">{escape(y_label)}</text>'
    )
    return elements


def _legend(x: float, y: float) -> list[str]:
    return [
        f'<rect x="{x}" y="{y}" width="14" height="14" fill="#176B87"/><text x="{x+20}" y="{y+12}" class="axis">Base</text>',
        f'<rect x="{x+82}" y="{y}" width="14" height="14" fill="#2A9D8F"/><text x="{x+102}" y="{y+12}" class="axis">Candidata</text>',
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
