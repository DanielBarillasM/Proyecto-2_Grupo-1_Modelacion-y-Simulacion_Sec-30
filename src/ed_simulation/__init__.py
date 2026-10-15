"""Emergency-department simulation and resource optimization package."""

from .config import SimulationConfig, default_config
from .simulation import PatientRecord, SimulationResult, simulate

__all__ = [
    "PatientRecord",
    "SimulationConfig",
    "SimulationResult",
    "default_config",
    "simulate",
]
