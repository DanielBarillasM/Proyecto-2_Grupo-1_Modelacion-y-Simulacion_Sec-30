"""Behavioral tests for reproducibility and internal model consistency."""

from ed_simulation import default_config, simulate
from ed_simulation.simulation import _QueueTracker


def test_same_seed_produces_same_result() -> None:
    config = default_config(seed=31415)

    first = simulate(config)
    second = simulate(config)

    assert first.metrics == second.metrics
    assert first.hourly_arrivals == second.hourly_arrivals
    assert [patient.to_dict() for patient in first.patients] == [
        patient.to_dict() for patient in second.patients
    ]


def test_patient_conservation_and_nonnegative_waits() -> None:
    result = simulate(default_config(seed=7))
    metrics = result.metrics

    assert metrics["arrived"] == metrics["completed"] + metrics["in_system_at_end"]
    assert metrics["started_service"] <= metrics["arrived"]
    assert metrics["started_service"] == metrics["arrived"]
    assert metrics["not_started_at_end"] == 0
    assert metrics["drain_complete"] == 1
    assert all(
        patient.wait_minutes is None or patient.wait_minutes >= 0
        for patient in result.patients
    )


def test_zero_arrivals_produce_empty_system() -> None:
    result = simulate(
        default_config(
            arrival_rates=(0.0,) * 24,
            simulation_days=1,
            warmup_days=0,
        )
    )

    assert result.metrics["arrived"] == 0
    assert result.metrics["mean_wait_minutes"] == 0.0
    assert result.metrics["maximum_queue"] == 0
    assert result.metrics["resource_utilization"] == 0.0


def test_more_capacity_does_not_change_generated_arrivals() -> None:
    low = simulate(default_config(seed=99, capacity_schedule=(2, 2, 2, 2, 2, 2)))
    high = simulate(default_config(seed=99, capacity_schedule=(8, 8, 8, 8, 8, 8)))

    # Random attributes are sampled at arrival, so common seeds create the same
    # exogenous demand independently of resource decisions.
    assert low.hourly_arrivals == high.hourly_arrivals


def test_distinct_seeds_change_exogenous_demand() -> None:
    first = simulate(default_config(seed=1))
    second = simulate(default_config(seed=2))

    assert first.hourly_arrivals != second.hourly_arrivals


def test_warmup_backlog_is_carried_into_queue_statistics() -> None:
    tracker = _QueueTracker(window_start=10.0, window_end=20.0)
    tracker.change(1.0, 1)
    tracker.change(3.0, 1)
    tracker.change(12.0, -1)
    tracker.finish()

    assert tracker.count_at_window_start == 2
    assert tracker.maximum == 2
    assert tracker.area == 12.0


def test_terminal_drain_completes_every_measured_wait() -> None:
    result = simulate(
        default_config(
            seed=44,
            arrival_rates=(4.0,) * 24,
            capacity_schedule=(1,) * 6,
            service_medians_minutes=(60.0,) * 5,
            service_sigma=0.0,
            min_service_minutes=60.0,
            max_service_minutes=60.0,
            simulation_days=1,
            warmup_days=0,
        )
    )

    assert result.metrics["not_started_at_measurement_end"] > 0
    assert result.metrics["drain_minutes"] > 0
    assert result.metrics["not_started_at_end"] == 0
    assert all(patient.wait_minutes is not None for patient in result.patients)


def test_effective_capacity_keeps_utilization_bounded_on_descending_schedule() -> None:
    result = simulate(
        default_config(
            seed=11,
            arrival_rates=(5.0,) * 24,
            capacity_schedule=(4, 1, 1, 1, 1, 1),
            service_medians_minutes=(120.0,) * 5,
            service_sigma=0.0,
            min_service_minutes=120.0,
            max_service_minutes=120.0,
            simulation_days=1,
            warmup_days=0,
        )
    )

    metrics = result.metrics
    assert metrics["resource_utilization"] <= 1.0
    assert metrics["effective_capacity_team_minutes"] >= metrics["busy_team_minutes"]
