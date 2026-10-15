"""A transparent constrained genetic algorithm coupled to the simulation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from statistics import fmean
from typing import Any, Sequence

import numpy as np

from ed_simulation.config import SimulationConfig
from ed_simulation.simulation import simulate

from .constraints import (
    OptimizationConstraints,
    constraint_violations,
    feasible_transfer_neighbors,
    is_feasible,
    repair_schedule,
    total_violation,
)


@dataclass(frozen=True)
class GAConfig:
    """Configurable algorithm parameters with reproducible defaults."""

    population_size: int = 24
    generations: int = 20
    crossover_probability: float = 0.80
    mutation_probability: float = 0.25
    elitism: int = 2
    tournament_size: int = 3
    patience: int = 8
    evaluation_replicates: int = 3
    evaluation_seed_start: int = 20_260
    algorithm_seed: int = 9_101
    mean_wait_weight: float = 0.70
    p90_wait_weight: float = 0.30
    censored_share_penalty_minutes: float = 120.0

    def __post_init__(self) -> None:
        if self.population_size < 4:
            raise ValueError("population_size debe ser al menos 4")
        if self.generations < 1:
            raise ValueError("generations debe ser al menos 1")
        if not 0 <= self.crossover_probability <= 1:
            raise ValueError("crossover_probability debe estar entre 0 y 1")
        if not 0 <= self.mutation_probability <= 1:
            raise ValueError("mutation_probability debe estar entre 0 y 1")
        if not 1 <= self.elitism < self.population_size:
            raise ValueError("elitism debe estar entre 1 y population_size - 1")
        if not 2 <= self.tournament_size <= self.population_size:
            raise ValueError("tournament_size fuera del rango permitido")
        if self.patience < 1:
            raise ValueError("patience debe ser al menos 1")
        if self.evaluation_replicates < 1:
            raise ValueError("evaluation_replicates debe ser al menos 1")
        if self.algorithm_seed < 0 or self.evaluation_seed_start < 0:
            raise ValueError("las semillas deben ser no negativas")
        if self.mean_wait_weight < 0 or self.p90_wait_weight < 0:
            raise ValueError("los pesos del objetivo no pueden ser negativos")
        if not np.isclose(self.mean_wait_weight + self.p90_wait_weight, 1.0):
            raise ValueError("los pesos de espera deben sumar 1")
        if self.censored_share_penalty_minutes < 0:
            raise ValueError("la penalización de censura no puede ser negativa")

    @property
    def evaluation_seeds(self) -> tuple[int, ...]:
        """Common random numbers used for every candidate."""

        return tuple(
            self.evaluation_seed_start + index
            for index in range(self.evaluation_replicates)
        )


@dataclass(frozen=True)
class CandidateEvaluation:
    """Aggregated stochastic performance and feasibility of one schedule."""

    schedule: tuple[int, ...]
    objective: float
    mean_wait_minutes: float
    p90_wait_minutes: float
    censored_share: float
    mean_queue: float
    resource_utilization: float
    feasible: bool
    violations: dict[str, int]
    replicate_seeds: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schedule"] = list(self.schedule)
        payload["replicate_seeds"] = list(self.replicate_seeds)
        return payload


@dataclass(frozen=True)
class GenerationRecord:
    """Convergence evidence captured after each evaluated generation."""

    generation: int
    best_objective: float
    population_mean_objective: float
    unique_schedules: int


@dataclass
class OptimizationResult:
    """Best feasible candidate, baseline, convergence, and audit metadata."""

    baseline: CandidateEvaluation
    best: CandidateEvaluation
    history: list[GenerationRecord]
    constraints: OptimizationConstraints
    ga_config: GAConfig
    evaluated_schedules: int
    stopped_early: bool

    @property
    def absolute_improvement_minutes(self) -> float:
        return self.baseline.objective - self.best.objective

    @property
    def relative_improvement(self) -> float:
        if self.baseline.objective == 0:
            return 0.0
        return self.absolute_improvement_minutes / self.baseline.objective

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_status": "development_candidate_with_estimated_parameters",
            "claim_scope": "simulated improvement only; not observed real-world improvement",
            "baseline": self.baseline.to_dict(),
            "best": self.best.to_dict(),
            "absolute_improvement_minutes": round(
                self.absolute_improvement_minutes, 6
            ),
            "relative_improvement": round(self.relative_improvement, 8),
            "history": [asdict(record) for record in self.history],
            "constraints": asdict(self.constraints),
            "ga_config": asdict(self.ga_config),
            "evaluated_schedules": self.evaluated_schedules,
            "stopped_early": self.stopped_early,
        }


def optimize_staffing(
    base_config: SimulationConfig,
    constraints: OptimizationConstraints,
    ga_config: GAConfig | None = None,
) -> OptimizationResult:
    """Search for a feasible allocation using simulation-based fitness.

    The baseline is inserted into every run and elitism prevents losing it. Thus,
    the returned feasible solution cannot be worse than the evaluated baseline
    under the same common random numbers.
    """

    settings = ga_config or GAConfig()
    baseline_schedule = tuple(base_config.capacity_schedule)
    if constraints.blocks != len(baseline_schedule):
        raise ValueError("constraints.blocks no coincide con capacity_schedule")
    if constraints.total_capacity_units != sum(baseline_schedule):
        raise ValueError("el presupuesto debe coincidir con el escenario base")
    if not is_feasible(baseline_schedule, constraints):
        raise ValueError("el escenario base debe satisfacer las restricciones")

    rng = np.random.default_rng(settings.algorithm_seed)
    cache: dict[tuple[int, ...], CandidateEvaluation] = {}

    def evaluate(schedule: Sequence[int]) -> CandidateEvaluation:
        schedule_tuple = tuple(int(value) for value in schedule)
        if schedule_tuple not in cache:
            cache[schedule_tuple] = _evaluate_candidate(
                base_config,
                schedule_tuple,
                constraints,
                settings,
            )
        return cache[schedule_tuple]

    population = _initial_population(
        baseline_schedule,
        constraints,
        settings.population_size,
        rng,
    )
    baseline_evaluation = evaluate(baseline_schedule)
    history: list[GenerationRecord] = []
    best = baseline_evaluation
    generations_without_improvement = 0
    stopped_early = False

    for generation in range(settings.generations + 1):
        evaluations = [evaluate(individual) for individual in population]
        evaluations.sort(key=lambda item: _rank_key(item, constraints))
        generation_best = evaluations[0]
        feasible_objectives = [
            evaluation.objective for evaluation in evaluations if evaluation.feasible
        ]
        population_mean = (
            fmean(feasible_objectives) if feasible_objectives else float("inf")
        )
        history.append(
            GenerationRecord(
                generation=generation,
                best_objective=round(generation_best.objective, 6),
                population_mean_objective=round(population_mean, 6),
                unique_schedules=len(set(population)),
            )
        )

        if _rank_key(generation_best, constraints) < _rank_key(best, constraints):
            best = generation_best
            generations_without_improvement = 0
        else:
            generations_without_improvement += 1

        if generation == settings.generations:
            break
        if generations_without_improvement >= settings.patience:
            stopped_early = True
            break

        next_population = [
            evaluation.schedule for evaluation in evaluations[: settings.elitism]
        ]
        while len(next_population) < settings.population_size:
            parent_a = _tournament(population, evaluate, constraints, settings, rng)
            parent_b = _tournament(population, evaluate, constraints, settings, rng)
            child_a, child_b = _crossover(
                parent_a,
                parent_b,
                baseline_schedule,
                constraints,
                settings,
                rng,
            )
            child_a = _mutate(child_a, constraints, settings, rng)
            child_b = _mutate(child_b, constraints, settings, rng)
            next_population.extend((child_a, child_b))
        population = next_population[: settings.population_size]

    if not best.feasible:
        raise RuntimeError("el algoritmo terminó sin una solución factible")
    return OptimizationResult(
        baseline=baseline_evaluation,
        best=best,
        history=history,
        constraints=constraints,
        ga_config=settings,
        evaluated_schedules=len(cache),
        stopped_early=stopped_early,
    )


def _evaluate_candidate(
    base_config: SimulationConfig,
    schedule: tuple[int, ...],
    constraints: OptimizationConstraints,
    settings: GAConfig,
) -> CandidateEvaluation:
    """Evaluate one schedule with common seeds and aggregate the metrics."""

    violations = constraint_violations(schedule, constraints)
    feasible = sum(violations.values()) == 0
    if not feasible:
        # Infeasible schedules are never simulated. Their numerical objective is
        # infinite; Deb's ranking uses violation magnitude instead.
        return CandidateEvaluation(
            schedule=schedule,
            objective=float("inf"),
            mean_wait_minutes=float("inf"),
            p90_wait_minutes=float("inf"),
            censored_share=1.0,
            mean_queue=float("inf"),
            resource_utilization=float("inf"),
            feasible=False,
            violations=violations,
            replicate_seeds=settings.evaluation_seeds,
        )

    metrics = []
    for seed in settings.evaluation_seeds:
        result = simulate(
            replace(base_config, capacity_schedule=schedule, seed=seed)
        )
        metrics.append(result.metrics)

    mean_wait = fmean(float(item["mean_wait_minutes"]) for item in metrics)
    p90_wait = fmean(float(item["p90_wait_minutes"]) for item in metrics)
    censored_share = fmean(
        (
            float(item["not_started_at_end"]) / float(item["arrived"])
            if item["arrived"]
            else 0.0
        )
        for item in metrics
    )
    objective = (
        settings.mean_wait_weight * mean_wait
        + settings.p90_wait_weight * p90_wait
        + settings.censored_share_penalty_minutes * censored_share
    )
    return CandidateEvaluation(
        schedule=schedule,
        objective=round(objective, 6),
        mean_wait_minutes=round(mean_wait, 6),
        p90_wait_minutes=round(p90_wait, 6),
        censored_share=round(censored_share, 8),
        mean_queue=round(
            fmean(float(item["mean_queue"]) for item in metrics), 6
        ),
        resource_utilization=round(
            fmean(float(item["resource_utilization"]) for item in metrics), 8
        ),
        feasible=True,
        violations=violations,
        replicate_seeds=settings.evaluation_seeds,
    )


def _initial_population(
    baseline: tuple[int, ...],
    constraints: OptimizationConstraints,
    population_size: int,
    rng: np.random.Generator,
) -> list[tuple[int, ...]]:
    """Create feasible diversity through random walks from the baseline."""

    population = [baseline]
    attempts = 0
    while len(population) < population_size and attempts < population_size * 100:
        attempts += 1
        candidate = baseline
        steps = int(rng.integers(1, 10))
        for _ in range(steps):
            neighbors = feasible_transfer_neighbors(candidate, constraints)
            if not neighbors:
                break
            candidate = neighbors[int(rng.integers(0, len(neighbors)))]
        population.append(candidate)

    while len(population) < population_size:
        population.append(baseline)
    return population


def _tournament(
    population: Sequence[tuple[int, ...]],
    evaluate,
    constraints: OptimizationConstraints,
    settings: GAConfig,
    rng: np.random.Generator,
) -> tuple[int, ...]:
    """Select the best candidate from a random tournament."""

    indices = rng.integers(0, len(population), size=settings.tournament_size)
    contestants = [population[int(index)] for index in indices]
    return min(
        contestants,
        key=lambda schedule: _rank_key(evaluate(schedule), constraints),
    )


def _crossover(
    parent_a: tuple[int, ...],
    parent_b: tuple[int, ...],
    fallback: tuple[int, ...],
    constraints: OptimizationConstraints,
    settings: GAConfig,
    rng: np.random.Generator,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Apply uniform crossover and repair both children."""

    if rng.random() >= settings.crossover_probability:
        return parent_a, parent_b
    mask = rng.random(len(parent_a)) < 0.5
    raw_a = tuple(a if use_a else b for a, b, use_a in zip(parent_a, parent_b, mask))
    raw_b = tuple(b if use_a else a for a, b, use_a in zip(parent_a, parent_b, mask))
    return (
        repair_schedule(raw_a, constraints, fallback, rng),
        repair_schedule(raw_b, constraints, fallback, rng),
    )


def _mutate(
    schedule: tuple[int, ...],
    constraints: OptimizationConstraints,
    settings: GAConfig,
    rng: np.random.Generator,
) -> tuple[int, ...]:
    """Transfer one resource unit while preserving feasibility."""

    if rng.random() >= settings.mutation_probability:
        return schedule
    neighbors = feasible_transfer_neighbors(schedule, constraints)
    if not neighbors:
        return schedule
    return neighbors[int(rng.integers(0, len(neighbors)))]


def _rank_key(
    evaluation: CandidateEvaluation,
    constraints: OptimizationConstraints,
) -> tuple[float, ...]:
    """Implement Deb's feasibility-first comparison rule."""

    if evaluation.feasible:
        return (0.0, evaluation.objective)
    return (
        1.0,
        float(total_violation(evaluation.schedule, constraints)),
        evaluation.objective,
    )
