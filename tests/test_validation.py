"""Tests for real-reference comparison and frozen evidence metadata."""

import json
from pathlib import Path

import pytest

from ed_simulation.evidence import (
    freeze_candidate,
    generate_evidence_bundle,
    load_frozen_candidate,
    write_json,
)
from ed_simulation.experiments import factorial_conditions, run_experiment
from ed_simulation.optimization import OptimizationConstraints, is_feasible
from ed_simulation.validation import (
    load_overall_reference,
    validation_comparison,
    validation_diagnostics,
)


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


def test_reference_and_simulation_use_the_same_metrics_and_units() -> None:
    runs = run_experiment(
        PROCESSED,
        factorial_conditions((3, 3, 4, 4, 5, 4), (1, 2, 5, 5, 6, 4)),
        seeds=(800, 801),
    )
    comparison = validation_comparison(runs, load_overall_reference(PROCESSED))

    assert set(comparison["metric"]) == {
        "mean_wait_minutes",
        "median_wait_minutes",
        "p90_wait_minutes",
        "share_wait_over_60",
    }
    assert set(comparison["unit"]) == {"minutes", "proportion"}
    assert comparison["reference_n_unweighted"].eq(13_272).all()
    assert comparison["claim_scope"].str.contains("not observed").all()
    diagnostics = validation_diagnostics(comparison)
    assert diagnostics["base_mae_minutes"] >= 0


def test_candidate_is_feasible_and_optimization_seeds_are_separate() -> None:
    candidate = freeze_candidate(
        PROCESSED,
        population_size=8,
        generations=2,
        optimization_replicates=1,
        optimization_seed_start=1_000,
        evaluation_seed_start=2_000,
    )
    constraints = OptimizationConstraints(**candidate["constraints"])

    assert candidate["candidate_status"] == "frozen_before_final_evaluation"
    assert is_feasible(candidate["candidate_schedule"], constraints)
    assert set(candidate["optimization_seeds"]).isdisjoint({2_000, 2_001})


def test_smoke_bundle_has_manifest_tables_and_three_figures(tmp_path: Path) -> None:
    candidate = freeze_candidate(
        PROCESSED,
        population_size=8,
        generations=2,
        optimization_replicates=1,
        optimization_seed_start=3_000,
        evaluation_seed_start=4_000,
    )
    output = tmp_path / "evidence"
    paths = generate_evidence_bundle(
        PROCESSED,
        output,
        candidate,
        replicates=2,
        evaluation_seed_start=4_000,
        git_commit="test-commit",
    )

    assert all(path.exists() for path in paths.values())
    assert len(list((output / "figures").glob("*.svg"))) == 3
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["conditions"]) == 6
    assert manifest["seeds"]["evaluation"] == [4_000, 4_001]
    assert manifest["git_commit_of_generator"] == "test-commit"


def test_invalid_frozen_candidate_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    write_json(path, {"candidate_status": "draft"})

    with pytest.raises(ValueError, match="faltan campos"):
        load_frozen_candidate(path)
