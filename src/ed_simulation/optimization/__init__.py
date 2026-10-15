"""Constrained resource-allocation optimization for the ED simulation."""

from .constraints import (
    OptimizationConstraints,
    constraint_violations,
    is_feasible,
    repair_schedule,
)
from .genetic_algorithm import (
    CandidateEvaluation,
    GAConfig,
    GenerationRecord,
    OptimizationResult,
    optimize_staffing,
)

__all__ = [
    "CandidateEvaluation",
    "GAConfig",
    "GenerationRecord",
    "OptimizationConstraints",
    "OptimizationResult",
    "constraint_violations",
    "is_feasible",
    "optimize_staffing",
    "repair_schedule",
]
