"""Unit tests for visible model assumptions and validation rules."""

import pytest

from ed_simulation.config import SimulationConfig, default_config


def test_default_configuration_has_expected_resource_budget() -> None:
    config = default_config()

    assert config.capacity_schedule == (3, 3, 4, 4, 5, 4)
    assert config.total_capacity_units == 23
    assert config.capacity_hours_per_day == 92
    assert config.measurement_minutes == 1_440


def test_triage_probabilities_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sumar 1"):
        SimulationConfig(triage_probabilities=(0.1, 0.1, 0.1, 0.1, 0.1))


def test_capacity_length_matches_block_size() -> None:
    with pytest.raises(ValueError, match="seis bloques|6 bloques"):
        SimulationConfig(capacity_schedule=(3, 3, 4))


def test_zero_block_size_fails_with_clear_message() -> None:
    with pytest.raises(ValueError, match="divisor positivo"):
        SimulationConfig(block_hours=0)
