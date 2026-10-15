"""Feasibility rules and repair operators for staffing schedules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class OptimizationConstraints:
    """Operational limits shared by the optimizer and its tests."""

    blocks: int
    total_capacity_units: int
    min_capacity: int = 1
    max_capacity: int = 8
    max_step_change: int = 3

    def __post_init__(self) -> None:
        if self.blocks < 2:
            raise ValueError("blocks debe ser al menos 2")
        if self.min_capacity < 1:
            raise ValueError("min_capacity debe ser al menos 1")
        if self.max_capacity < self.min_capacity:
            raise ValueError("max_capacity debe ser mayor o igual al mínimo")
        minimum_budget = self.blocks * self.min_capacity
        maximum_budget = self.blocks * self.max_capacity
        if not minimum_budget <= self.total_capacity_units <= maximum_budget:
            raise ValueError("el presupuesto no cabe dentro de los límites por bloque")
        if self.max_step_change < 0:
            raise ValueError("max_step_change no puede ser negativo")


def constraint_violations(
    schedule: Sequence[int],
    constraints: OptimizationConstraints,
) -> dict[str, int]:
    """Quantify each violation; zero in every field means feasible."""

    values = tuple(int(value) for value in schedule)
    length_violation = abs(len(values) - constraints.blocks)
    if length_violation:
        return {
            "length": length_violation,
            "bounds": length_violation,
            "budget": constraints.total_capacity_units,
            "smoothness": length_violation,
        }

    bounds_violation = sum(
        max(0, constraints.min_capacity - value)
        + max(0, value - constraints.max_capacity)
        for value in values
    )
    budget_violation = abs(sum(values) - constraints.total_capacity_units)
    # The schedule repeats every day, so the last-to-first transition is also an
    # operational boundary and must satisfy the same limit.
    smoothness_violation = sum(
        max(
            0,
            abs(values[(index + 1) % len(values)] - values[index])
            - constraints.max_step_change,
        )
        for index in range(len(values))
    )
    return {
        "length": length_violation,
        "bounds": bounds_violation,
        "budget": budget_violation,
        "smoothness": smoothness_violation,
    }


def total_violation(
    schedule: Sequence[int],
    constraints: OptimizationConstraints,
) -> int:
    """Return a scalar used only to rank infeasible schedules."""

    return sum(constraint_violations(schedule, constraints).values())


def is_feasible(
    schedule: Sequence[int],
    constraints: OptimizationConstraints,
) -> bool:
    """Return whether every declared operational restriction is satisfied."""

    return total_violation(schedule, constraints) == 0


def feasible_transfer_neighbors(
    schedule: Sequence[int],
    constraints: OptimizationConstraints,
) -> list[tuple[int, ...]]:
    """Enumerate one-unit transfers that preserve every constraint."""

    values = tuple(int(value) for value in schedule)
    neighbors: list[tuple[int, ...]] = []
    for donor in range(len(values)):
        if values[donor] <= constraints.min_capacity:
            continue
        for receiver in range(len(values)):
            if donor == receiver or values[receiver] >= constraints.max_capacity:
                continue
            candidate = list(values)
            candidate[donor] -= 1
            candidate[receiver] += 1
            candidate_tuple = tuple(candidate)
            if is_feasible(candidate_tuple, constraints):
                neighbors.append(candidate_tuple)
    return neighbors


def repair_schedule(
    schedule: Sequence[int],
    constraints: OptimizationConstraints,
    fallback: Sequence[int],
    rng: np.random.Generator,
) -> tuple[int, ...]:
    """Repair bounds, budget, and smoothness or return a known feasible fallback.

    The repair is deliberately explicit. It first clips values, then restores the
    total budget, and finally searches budget-preserving one-unit transfers that
    reduce remaining violations. It never returns an unchecked candidate.
    """

    fallback_tuple = tuple(int(value) for value in fallback)
    if not is_feasible(fallback_tuple, constraints):
        raise ValueError("fallback debe ser factible")
    if len(schedule) != constraints.blocks:
        return fallback_tuple

    candidate = [
        int(np.clip(int(round(value)), constraints.min_capacity, constraints.max_capacity))
        for value in schedule
    ]

    # Restore the fixed budget. Among allowed indices, prefer a random order so
    # crossover does not systematically favor early blocks.
    for _ in range(constraints.blocks * constraints.max_capacity * 2):
        difference = constraints.total_capacity_units - sum(candidate)
        if difference == 0:
            break
        if difference > 0:
            options = [
                index
                for index, value in enumerate(candidate)
                if value < constraints.max_capacity
            ]
            delta = 1
        else:
            options = [
                index
                for index, value in enumerate(candidate)
                if value > constraints.min_capacity
            ]
            delta = -1
        if not options:
            return fallback_tuple
        chosen = int(rng.choice(options))
        candidate[chosen] += delta

    current = tuple(candidate)
    if is_feasible(current, constraints):
        return current

    # Improve smoothness while preserving the now-correct budget. A move is
    # accepted only if total violation decreases, preventing repair cycles.
    for _ in range(200):
        current_violation = total_violation(current, constraints)
        improving: list[tuple[int, ...]] = []
        for donor in range(constraints.blocks):
            for receiver in range(constraints.blocks):
                if donor == receiver:
                    continue
                trial = list(current)
                trial[donor] -= 1
                trial[receiver] += 1
                if total_violation(trial, constraints) < current_violation:
                    improving.append(tuple(trial))
        if not improving:
            break
        current = improving[int(rng.integers(0, len(improving)))]
        if is_feasible(current, constraints):
            return current

    return fallback_tuple
