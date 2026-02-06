"""Property-based invariant tests for IHA computation."""

import numpy as np
import pytest

from fishy.iha.compute import compute_iha
from fishy.iha.types import Col, PulseThresholds

ALL_FIXTURES = [
    "constant_flow",
    "step_flow",
    "seasonal_sine",
    "triangle_wave",
    "pulse_flow",
    "zero_flow",
    "ramp_flow",
]


@pytest.fixture(params=ALL_FIXTURES)
def flow_data(request):
    return request.getfixturevalue(request.param)


def _compute(data: dict):
    """Compute IHA for a fixture dict with safe external thresholds."""
    return compute_iha(
        data["q"],
        data["dates"],
        pulse_thresholds=PulseThresholds(low=1.0, high=50.0),
    )


class TestInvariants:
    def test_output_shape(self, flow_data):
        result = _compute(flow_data)
        assert result.values.shape == (1, 33)

    def test_years_match(self, flow_data):
        result = _compute(flow_data)
        assert result.years.tolist() == [2023]

    def test_bfi_in_valid_range(self, flow_data):
        result = _compute(flow_data)
        bfi = result.values[0, Col.BASE_FLOW_INDEX]
        assert np.isnan(bfi) or (0.0 <= bfi <= 1.0)

    def test_min_less_than_or_equal_max(self, flow_data):
        result = _compute(flow_data)
        row = result.values[0]
        for i in range(5):
            min_val = row[Col.MIN_1DAY + i]
            max_val = row[Col.MAX_1DAY + i]
            assert min_val <= max_val or (np.isnan(min_val) and np.isnan(max_val))

    def test_date_of_min_in_range(self, flow_data):
        result = _compute(flow_data)
        date_of_min = result.values[0, Col.DATE_OF_MIN]
        assert 1 <= date_of_min <= 366

    def test_date_of_max_in_range(self, flow_data):
        result = _compute(flow_data)
        date_of_max = result.values[0, Col.DATE_OF_MAX]
        assert 1 <= date_of_max <= 366

    def test_zero_flow_days_non_negative(self, flow_data):
        result = _compute(flow_data)
        assert result.values[0, Col.ZERO_FLOW_DAYS] >= 0

    def test_zero_flow_days_at_most_365(self, flow_data):
        result = _compute(flow_data)
        assert result.values[0, Col.ZERO_FLOW_DAYS] <= 365

    def test_pulse_counts_non_negative(self, flow_data):
        result = _compute(flow_data)
        row = result.values[0]
        assert row[Col.LOW_PULSE_COUNT] >= 0
        assert row[Col.HIGH_PULSE_COUNT] >= 0

    def test_pulse_durations_non_negative(self, flow_data):
        result = _compute(flow_data)
        row = result.values[0]
        assert row[Col.LOW_PULSE_DURATION] >= 0
        assert row[Col.HIGH_PULSE_DURATION] >= 0

    def test_rise_rate_non_negative(self, flow_data):
        result = _compute(flow_data)
        assert result.values[0, Col.RISE_RATE] >= 0

    def test_fall_rate_non_positive(self, flow_data):
        result = _compute(flow_data)
        assert result.values[0, Col.FALL_RATE] <= 0

    def test_reversals_non_negative(self, flow_data):
        result = _compute(flow_data)
        assert result.values[0, Col.REVERSALS] >= 0
