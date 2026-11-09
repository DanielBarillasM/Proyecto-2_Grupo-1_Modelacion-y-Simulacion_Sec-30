"""Tests for the paired factorial experiment and aggregation contract."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ed_simulation.experiments import (
    factorial_conditions,
    paired_differences,
    run_experiment,
    summarize_runs,
    validate_runs,
)


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
BASE = (3, 3, 4, 4, 5, 4)
CANDIDATE = (1, 2, 5, 5, 6, 4)


@pytest.fixture(scope="module")
def small_runs() -> pd.DataFrame:
    return run_experiment(
        PROCESSED,
        factorial_conditions(BASE, CANDIDATE),
        seeds=(700, 701),
    )


def test_factorial_design_has_six_conditions() -> None:
    conditions = factorial_conditions(BASE, CANDIDATE)

    assert len(conditions) == 6
    assert {condition.demand_multiplier for condition in conditions} == {
        0.8,
        1.0,
        1.2,
    }
    assert {condition.schedule_id for condition in conditions} == {
        "base",
        "candidate",
    }


def test_runs_use_common_seeds_and_complete_the_drained_cohort(
    small_runs: pd.DataFrame,
) -> None:
    validate_runs(small_runs, expected_replicates=2)

    assert len(small_runs) == 12
    assert small_runs["not_started_at_end"].eq(0).all()
    assert small_runs["started_service"].eq(small_runs["arrived"]).all()
    for _, demand in small_runs.groupby("demand_multiplier"):
        base = set(demand[demand["schedule_id"] == "base"]["seed"])
        candidate = set(demand[demand["schedule_id"] == "candidate"]["seed"])
        assert base == candidate == {700, 701}


def test_summary_is_recomputed_from_replica_rows(small_runs: pd.DataFrame) -> None:
    summary = summarize_runs(small_runs)
    selected = small_runs[
        (small_runs["condition_id"] == "base_demand_100")
    ]["mean_wait_minutes"]
    row = summary[
        (summary["condition_id"] == "base_demand_100")
        & (summary["metric"] == "mean_wait_minutes")
    ].iloc[0]

    assert row["n"] == 2
    assert row["mean"] == pytest.approx(selected.mean())
    assert row["std"] == pytest.approx(selected.std(ddof=1))


def test_paired_differences_match_source_runs(small_runs: pd.DataFrame) -> None:
    paired = paired_differences(small_runs)
    row = paired[
        (paired["demand_multiplier"] == 1.0)
        & (paired["seed"] == 700)
        & (paired["metric"] == "mean_wait_minutes")
    ].iloc[0]
    source = small_runs[
        (small_runs["demand_multiplier"] == 1.0) & (small_runs["seed"] == 700)
    ].set_index("schedule_id")

    expected = (
        source.loc["base", "mean_wait_minutes"]
        - source.loc["candidate", "mean_wait_minutes"]
    )
    assert row["improvement_base_minus_candidate"] == pytest.approx(expected)


def test_validation_rejects_unpaired_seed() -> None:
    bad = pd.DataFrame(
        {
            "experiment_id": ["x"] * 6,
            "condition_id": ["a", "a", "b", "b", "c", "c"],
            "schedule_id": ["base", "base", "candidate", "candidate", "base", "candidate"],
            "demand_multiplier": [0.8, 0.8, 0.8, 0.8, 1.0, 1.0],
            "replicate": [1, 2, 1, 2, 1, 1],
            "seed": [1, 2, 1, 3, 1, 1],
            "arrived": [1] * 6,
            "started_service": [1] * 6,
            "completed": [1] * 6,
            "not_started_at_end": [0] * 6,
            "mean_wait_minutes": [1.0] * 6,
            "median_wait_minutes": [1.0] * 6,
            "p90_wait_minutes": [1.0] * 6,
            "share_wait_over_60": [0.0] * 6,
            "mean_queue": [0.0] * 6,
            "maximum_queue": [0] * 6,
            "resource_utilization": [0.5] * 6,
            "runtime_seconds": [0.1] * 6,
        }
    )

    with pytest.raises(ValueError):
        validate_runs(bad)


def test_no_negative_wait_or_queue_in_runs(small_runs: pd.DataFrame) -> None:
    assert (small_runs["mean_wait_minutes"] >= 0).all()
    assert (small_runs["mean_queue"] >= 0).all()
    assert np.isfinite(small_runs["runtime_seconds"]).all()
