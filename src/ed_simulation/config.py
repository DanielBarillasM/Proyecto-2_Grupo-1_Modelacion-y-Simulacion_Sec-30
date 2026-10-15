"""Validated configuration objects for the emergency-department model.

The module keeps all model assumptions in one place. This avoids hidden constants
inside the simulation and makes CLI, tests, Streamlit, and future experiments use
the same definitions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isclose
from typing import Any


# Estimated profile used only while the NHAMCS preparation pipeline is completed.
# Values represent expected arrivals per hour and are deliberately visible here so
# that the source category cannot be confused with observed data.
DEFAULT_ARRIVAL_RATES: tuple[float, ...] = (
    1.2,
    1.0,
    0.9,
    0.8,
    0.9,
    1.4,
    2.2,
    3.0,
    3.8,
    4.2,
    4.0,
    4.1,
    4.3,
    4.2,
    4.0,
    4.2,
    4.8,
    5.4,
    5.8,
    5.2,
    4.1,
    3.1,
    2.3,
    1.6,
)


@dataclass(frozen=True)
class SimulationConfig:
    """Parameters required for one stochastic simulation.

    One warm-up day is recommended so that the measured day does not start from an
    artificially empty queue. Capacity and arrivals repeat every 24 hours.
    """

    arrival_rates: tuple[float, ...] = field(
        default_factory=lambda: DEFAULT_ARRIVAL_RATES
    )
    triage_probabilities: tuple[float, ...] = (
        0.02,
        0.08,
        0.35,
        0.42,
        0.13,
    )
    service_medians_minutes: tuple[float, ...] = (
        120.0,
        90.0,
        70.0,
        50.0,
        35.0,
    )
    service_sigma: float = 0.45
    capacity_schedule: tuple[int, ...] = (3, 3, 4, 4, 5, 4)
    block_hours: int = 4
    simulation_days: int = 2
    warmup_days: int = 1
    min_service_minutes: float = 5.0
    max_service_minutes: float = 480.0
    seed: int = 2026

    def __post_init__(self) -> None:
        """Fail fast when a configuration would invalidate the model."""

        if len(self.arrival_rates) != 24:
            raise ValueError("arrival_rates debe contener exactamente 24 tasas")
        if any(rate < 0 for rate in self.arrival_rates):
            raise ValueError("las tasas de llegada no pueden ser negativas")
        if len(self.triage_probabilities) != 5:
            raise ValueError("se requieren cinco probabilidades de triaje")
        if any(probability < 0 for probability in self.triage_probabilities):
            raise ValueError("las probabilidades no pueden ser negativas")
        if not isclose(sum(self.triage_probabilities), 1.0, abs_tol=1e-9):
            raise ValueError("las probabilidades de triaje deben sumar 1")
        if len(self.service_medians_minutes) != 5:
            raise ValueError("se requieren cinco medianas de servicio")
        if any(value <= 0 for value in self.service_medians_minutes):
            raise ValueError("las medianas de servicio deben ser positivas")
        if self.service_sigma < 0:
            raise ValueError("service_sigma no puede ser negativo")
        if self.block_hours <= 0 or 24 % self.block_hours != 0:
            raise ValueError("block_hours debe ser un divisor positivo de 24")
        expected_blocks = 24 // self.block_hours
        if len(self.capacity_schedule) != expected_blocks:
            raise ValueError(
                f"capacity_schedule debe contener {expected_blocks} bloques"
            )
        if any(capacity < 1 for capacity in self.capacity_schedule):
            raise ValueError("cada bloque debe tener al menos un equipo")
        if self.simulation_days < 1:
            raise ValueError("simulation_days debe ser al menos 1")
        if not 0 <= self.warmup_days < self.simulation_days:
            raise ValueError("warmup_days debe ser menor que simulation_days")
        if self.min_service_minutes <= 0:
            raise ValueError("min_service_minutes debe ser positivo")
        if self.max_service_minutes < self.min_service_minutes:
            raise ValueError("max_service_minutes debe ser mayor que el mínimo")
        if self.seed < 0:
            raise ValueError("la semilla debe ser un entero no negativo")

    @property
    def horizon_minutes(self) -> float:
        """Total simulated time, including warm-up."""

        return float(self.simulation_days * 24 * 60)

    @property
    def warmup_minutes(self) -> float:
        """Time discarded before recording patient-level metrics."""

        return float(self.warmup_days * 24 * 60)

    @property
    def measurement_minutes(self) -> float:
        """Length of the observation window."""

        return self.horizon_minutes - self.warmup_minutes

    @property
    def total_capacity_units(self) -> int:
        """Resource units allocated across one daily schedule."""

        return sum(self.capacity_schedule)

    @property
    def capacity_hours_per_day(self) -> int:
        """Daily team-hours; used to enforce fair optimization comparisons."""

        return self.total_capacity_units * self.block_hours

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        payload = asdict(self)
        for key, value in payload.items():
            if isinstance(value, tuple):
                payload[key] = list(value)
        return payload


def default_config(**overrides: Any) -> SimulationConfig:
    """Create a default configuration with explicit, validated overrides."""

    base = SimulationConfig().to_dict()
    base.update(overrides)
    for key in (
        "arrival_rates",
        "triage_probabilities",
        "service_medians_minutes",
        "capacity_schedule",
    ):
        if key in base:
            base[key] = tuple(base[key])
    return SimulationConfig(**base)
