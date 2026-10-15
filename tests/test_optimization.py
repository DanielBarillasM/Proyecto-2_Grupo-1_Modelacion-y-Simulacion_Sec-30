"""Tests for constraints, repair, and simulation-based genetic search."""

import numpy as np

from ed_simulation import default_config
from ed_simulation.optimization import (
    GAConfig,
    OptimizationConstraints,
    constraint_violations,
    is_feasible,
    optimize_staffing,
    repair_schedule,
)


def default_constraints() -> OptimizationConstraints:
    return OptimizationConstraints(
        blocks=6,
        total_capacity_units=23,
        min_capacity=1,
        max_capacity=8,
        max_step_change=3,
    )


def test_default_schedule_is_feasible() -> None:
    schedule = (3, 3, 4, 4, 5, 4)
    constraints = default_constraints()

    assert is_feasible(schedule, constraints)
    assert constraint_violations(schedule, constraints) == {
        "length": 0,
        "bounds": 0,
        "budget": 0,
        "smoothness": 0,
    }


def test_repair_returns_checked_feasible_schedule() -> None:
    constraints = default_constraints()
    fallback = (3, 3, 4, 4, 5, 4)
    repaired = repair_schedule(
        (8, 8, 1, 1, 1, 1),
        constraints,
        fallback,
        np.random.default_rng(10),
    )

    assert is_feasible(repaired, constraints)
    assert sum(repaired) == sum(fallback)


def test_optimizer_is_reproducible_and_never_worse_than_baseline() -> None:
    config = default_config()
    constraints = default_constraints()
    settings = GAConfig(
        population_size=8,
        generations=3,
        elitism=1,
        tournament_size=2,
        patience=3,
        evaluation_replicates=1,
        algorithm_seed=123,
        evaluation_seed_start=456,
    )

    first = optimize_staffing(config, constraints, settings)
    second = optimize_staffing(config, constraints, settings)

    assert first.to_dict() == second.to_dict()
    assert first.best.feasible
    assert is_feasible(first.best.schedule, constraints)
    assert sum(first.best.schedule) == sum(config.capacity_schedule)
    assert first.best.objective <= first.baseline.objective


def test_wraparound_transition_is_enforced() -> None:
    constraints = OptimizationConstraints(
        blocks=6,
        total_capacity_units=27,
        min_capacity=1,
        max_capacity=8,
        max_step_change=2,
    )
    schedule = (2, 4, 5, 5, 5, 6)

    # Internal transitions are at most two, but the repeated-day transition from
    # six teams back to two violates the limit by two units.
    assert constraint_violations(schedule, constraints)["smoothness"] == 2
    assert not is_feasible(schedule, constraints)
