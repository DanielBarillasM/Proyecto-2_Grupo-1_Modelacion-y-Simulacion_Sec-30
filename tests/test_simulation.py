"""Behavioral tests for reproducibility and internal model consistency."""

from ed_simulation import default_config, simulate


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
