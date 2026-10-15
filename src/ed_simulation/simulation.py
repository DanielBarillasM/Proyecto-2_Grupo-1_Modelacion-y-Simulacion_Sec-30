"""Discrete-event model for patient flow through an emergency department.

Capacity changes are implemented with *blocker* processes. The SimPy priority
resource is created with the largest scheduled capacity; blocker processes reserve
the slots that are unavailable in each time block. This preserves SimPy's normal
queue semantics and allows an ongoing service to finish when capacity decreases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import floor, log
from statistics import fmean, median
from typing import Any

import numpy as np
import simpy

from .config import SimulationConfig


@dataclass
class PatientRecord:
    """Trace of one patient who arrived inside the measurement window."""

    patient_id: int
    arrival_minute: float
    triage_level: int
    service_minutes: float
    service_start_minute: float | None = None
    departure_minute: float | None = None

    @property
    def wait_minutes(self) -> float | None:
        """Wait until a care team starts service, or ``None`` if censored."""

        if self.service_start_minute is None:
            return None
        return self.service_start_minute - self.arrival_minute

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable patient trace."""

        return {
            "patient_id": self.patient_id,
            "arrival_minute": round(self.arrival_minute, 4),
            "triage_level": self.triage_level,
            "service_minutes": round(self.service_minutes, 4),
            "service_start_minute": _rounded_or_none(self.service_start_minute),
            "departure_minute": _rounded_or_none(self.departure_minute),
            "wait_minutes": _rounded_or_none(self.wait_minutes),
        }


@dataclass
class SimulationResult:
    """Complete output from one model execution."""

    config: SimulationConfig
    metrics: dict[str, float | int]
    patients: list[PatientRecord]
    hourly_arrivals: tuple[int, ...]

    def to_dict(self, *, include_patients: bool = True) -> dict[str, Any]:
        """Return a JSON-compatible result for CLI and evidence files."""

        payload: dict[str, Any] = {
            "config": self.config.to_dict(),
            "metrics": self.metrics,
            "hourly_arrivals": list(self.hourly_arrivals),
        }
        if include_patients:
            payload["patients"] = [patient.to_dict() for patient in self.patients]
        return payload


@dataclass
class _QueueTracker:
    """Time-weighted queue statistics for measured patients only."""

    window_start: float
    window_end: float
    count: int = 0
    maximum: int = 0
    area: float = 0.0
    last_update: float = field(init=False)

    def __post_init__(self) -> None:
        self.last_update = self.window_start

    def change(self, now: float, delta: int) -> None:
        """Accumulate queue area before changing the patient count."""

        bounded_now = min(max(now, self.window_start), self.window_end)
        if bounded_now >= self.last_update:
            self.area += self.count * (bounded_now - self.last_update)
            self.last_update = bounded_now
        self.count += delta
        if self.count < 0:
            raise RuntimeError("el contador de cola no puede ser negativo")
        self.maximum = max(self.maximum, self.count)

    def finish(self) -> None:
        """Close the final interval at the measurement horizon."""

        self.change(self.window_end, 0)


@dataclass
class _RuntimeState:
    """Mutable counters shared by SimPy processes."""

    measured_records: list[PatientRecord]
    queue: _QueueTracker
    busy_minutes: float = 0.0
    next_patient_id: int = 0


def simulate(config: SimulationConfig) -> SimulationResult:
    """Execute one reproducible emergency-department simulation.

    Parameters
    ----------
    config:
        Fully validated assumptions, distributions, schedule, horizon, and seed.

    Returns
    -------
    SimulationResult
        Metrics, hourly arrivals, and patient-level records for the measurement
        window. Arrivals before the warm-up threshold affect congestion but are
        not reported as observations.
    """

    rng = np.random.default_rng(config.seed)
    environment = simpy.Environment()
    max_capacity = max(config.capacity_schedule)
    resource = simpy.PriorityResource(environment, capacity=max_capacity)
    queue_tracker = _QueueTracker(
        window_start=config.warmup_minutes,
        window_end=config.horizon_minutes,
    )
    state = _RuntimeState(measured_records=[], queue=queue_tracker)

    # A controller is created for each possible team slot. When a slot is not in
    # the schedule, its controller reserves one resource unit with higher priority
    # than patients. If it is occupied, the reduction takes effect after service.
    for slot_index in range(max_capacity):
        environment.process(
            _capacity_slot_controller(environment, resource, config, slot_index)
        )

    environment.process(
        _arrival_generator(environment, resource, config, rng, state)
    )
    environment.run(until=config.horizon_minutes)
    queue_tracker.finish()

    return _build_result(config, state)


def _capacity_slot_controller(
    environment: simpy.Environment,
    resource: simpy.PriorityResource,
    config: SimulationConfig,
    slot_index: int,
):
    """Reserve a team slot during blocks where it is not scheduled."""

    block_minutes = config.block_hours * 60
    total_blocks = config.simulation_days * len(config.capacity_schedule)

    for block_number in range(total_blocks):
        block_end = min((block_number + 1) * block_minutes, config.horizon_minutes)
        scheduled_capacity = config.capacity_schedule[
            block_number % len(config.capacity_schedule)
        ]
        slot_is_available = slot_index < scheduled_capacity

        if slot_is_available:
            yield environment.timeout(max(0.0, block_end - environment.now))
            continue

        request = resource.request(priority=-1_000)
        timeout = environment.timeout(max(0.0, block_end - environment.now))
        outcome = yield request | timeout

        if request in outcome:
            # The blocker acquired a slot. Hold it only until this block ends.
            remaining = max(0.0, block_end - environment.now)
            if remaining:
                yield environment.timeout(remaining)
            resource.release(request)
        else:
            # Capacity could not decrease before the next block because active
            # patients occupied all slots. Cancel the queued blocker cleanly.
            request.cancel()


def _arrival_generator(
    environment: simpy.Environment,
    resource: simpy.PriorityResource,
    config: SimulationConfig,
    rng: np.random.Generator,
    state: _RuntimeState,
):
    """Generate a piecewise-homogeneous Poisson arrival process."""

    while environment.now < config.horizon_minutes:
        hour_index = int(floor(environment.now / 60.0)) % 24
        next_hour = min(
            (floor(environment.now / 60.0) + 1) * 60.0,
            config.horizon_minutes,
        )
        rate_per_hour = config.arrival_rates[hour_index]

        if rate_per_hour == 0:
            yield environment.timeout(max(0.0, next_hour - environment.now))
            continue

        interarrival = float(rng.exponential(60.0 / rate_per_hour))
        if environment.now + interarrival >= next_hour:
            yield environment.timeout(max(0.0, next_hour - environment.now))
            continue

        yield environment.timeout(interarrival)
        state.next_patient_id += 1
        triage_level = int(rng.choice(np.arange(1, 6), p=config.triage_probabilities))
        service_minutes = _sample_service_minutes(config, rng, triage_level)
        measured = environment.now >= config.warmup_minutes
        record = PatientRecord(
            patient_id=state.next_patient_id,
            arrival_minute=environment.now,
            triage_level=triage_level,
            service_minutes=service_minutes,
        )
        if measured:
            state.measured_records.append(record)
            state.queue.change(environment.now, 1)
        environment.process(
            _patient_process(
                environment,
                resource,
                config,
                state,
                record,
                measured,
            )
        )


def _patient_process(
    environment: simpy.Environment,
    resource: simpy.PriorityResource,
    config: SimulationConfig,
    state: _RuntimeState,
    record: PatientRecord,
    measured: bool,
):
    """Wait by triage priority, receive service, and release the team."""

    with resource.request(priority=record.triage_level) as request:
        yield request
        record.service_start_minute = environment.now
        if measured:
            state.queue.change(environment.now, -1)

        # Count only the overlap with the observation window. The service may
        # begin during warm-up or continue after the simulation horizon.
        overlap_start = max(environment.now, config.warmup_minutes)
        overlap_end = min(
            environment.now + record.service_minutes,
            config.horizon_minutes,
        )
        state.busy_minutes += max(0.0, overlap_end - overlap_start)

        yield environment.timeout(record.service_minutes)
        record.departure_minute = environment.now


def _sample_service_minutes(
    config: SimulationConfig,
    rng: np.random.Generator,
    triage_level: int,
) -> float:
    """Draw a bounded lognormal duration using the triage-specific median."""

    median_minutes = config.service_medians_minutes[triage_level - 1]
    sampled = float(rng.lognormal(mean=log(median_minutes), sigma=config.service_sigma))
    return float(
        np.clip(sampled, config.min_service_minutes, config.max_service_minutes)
    )


def _build_result(
    config: SimulationConfig,
    state: _RuntimeState,
) -> SimulationResult:
    """Aggregate patient traces without hiding censored observations."""

    records = state.measured_records
    waits = [record.wait_minutes for record in records if record.wait_minutes is not None]
    completed = sum(record.departure_minute is not None for record in records)
    started = len(waits)
    arrived = len(records)
    capacity_minutes = (
        config.capacity_hours_per_day
        * 60
        * (config.simulation_days - config.warmup_days)
    )
    utilization = state.busy_minutes / capacity_minutes if capacity_minutes else 0.0

    hourly_arrivals = [0] * 24
    for record in records:
        hour = int(record.arrival_minute // 60) % 24
        hourly_arrivals[hour] += 1

    wait_array = np.asarray(waits, dtype=float)
    metrics: dict[str, float | int] = {
        "arrived": arrived,
        "started_service": started,
        "completed": completed,
        "in_system_at_end": arrived - completed,
        "not_started_at_end": arrived - started,
        "mean_wait_minutes": round(fmean(waits), 4) if waits else 0.0,
        "median_wait_minutes": round(median(waits), 4) if waits else 0.0,
        "p90_wait_minutes": (
            round(float(np.percentile(wait_array, 90)), 4) if waits else 0.0
        ),
        "share_wait_over_60": (
            round(float(np.mean(wait_array > 60)), 6) if waits else 0.0
        ),
        "maximum_queue": state.queue.maximum,
        "mean_queue": round(state.queue.area / config.measurement_minutes, 4),
        "resource_utilization": round(utilization, 6),
        "capacity_hours_per_day": config.capacity_hours_per_day,
    }

    if arrived != completed + metrics["in_system_at_end"]:
        raise RuntimeError("falló la conservación de pacientes")

    return SimulationResult(
        config=config,
        metrics=metrics,
        patients=records,
        hourly_arrivals=tuple(hourly_arrivals),
    )


def _rounded_or_none(value: float | None) -> float | None:
    """Round optional times consistently for JSON output."""

    return None if value is None else round(value, 4)
