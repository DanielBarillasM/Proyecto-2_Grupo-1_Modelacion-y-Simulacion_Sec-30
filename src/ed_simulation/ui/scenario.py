"""Validated adapters between Streamlit forms and public domain functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from ed_simulation.calibration import load_calibrated_config
from ed_simulation.simulation import SimulationResult, simulate


def parse_capacity_schedule(text: str) -> tuple[int, ...]:
    """Parse six comma-separated positive integer capacities."""

    try:
        values = tuple(int(part.strip()) for part in text.split(","))
    except ValueError as error:
        raise ValueError("la capacidad debe contener únicamente enteros") from error
    if len(values) != 6:
        raise ValueError("la capacidad debe contener exactamente seis bloques")
    if any(value < 1 or value > 10 for value in values):
        raise ValueError("cada capacidad debe estar entre 1 y 10 equipos")
    return values


def run_calibrated_scenario(
    root: Path | str,
    *,
    seed: int,
    demand_multiplier: float,
    capacity_schedule: Sequence[int],
) -> SimulationResult:
    """Build a calibrated configuration and execute one explicit scenario."""

    root = Path(root)
    config = load_calibrated_config(
        root / "data" / "processed",
        demand_multiplier=float(demand_multiplier),
        seed=int(seed),
        capacity_schedule=tuple(int(value) for value in capacity_schedule),
    )
    return simulate(config)


def result_download(result: SimulationResult) -> bytes:
    """Serialize a complete reproducible result for download."""

    return (
        json.dumps(result.to_dict(include_patients=True), ensure_ascii=False, indent=2)
        + "\n"
    ).encode("utf-8")


def config_download(
    *, seed: int, demand_multiplier: float, capacity_schedule: Sequence[int]
) -> bytes:
    """Serialize form values separately from stochastic output."""

    return (
        json.dumps(
            {
                "seed": int(seed),
                "demand_multiplier": float(demand_multiplier),
                "capacity_schedule": [int(value) for value in capacity_schedule],
                "data_source": "NHAMCS 2022 processed aggregates",
                "source_category": "derived_from_public + estimated_assumption",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
