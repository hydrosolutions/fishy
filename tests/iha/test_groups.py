"""Tests for per-group IHA computation functions."""

import numpy as np

from fishy.iha._groups import (
    compute_group1,
    compute_group2,
    compute_group3,
    compute_group4,
    compute_group5,
)
from fishy.iha._util import dates_to_components


# ---------------------------------------------------------------------------
# Group 1: monthly means
# ---------------------------------------------------------------------------
class TestGroup1:
    def test_constant_flow_all_months_equal(self, constant_flow: dict) -> None:
        _, months, _ = dates_to_components(constant_flow["dates"])
        result = compute_group1(constant_flow["q"], months)
        np.testing.assert_array_equal(result, np.full(12, 10.0))

    def test_zero_flow_all_months_zero(self, zero_flow: dict) -> None:
        _, months, _ = dates_to_components(zero_flow["dates"])
        result = compute_group1(zero_flow["q"], months)
        np.testing.assert_array_equal(result, np.zeros(12))

    def test_step_flow_jan_mean(self, step_flow: dict) -> None:
        _, months, _ = dates_to_components(step_flow["dates"])
        result = compute_group1(step_flow["q"], months)
        assert result[0] == 5.0

    def test_step_flow_may_mean(self, step_flow: dict) -> None:
        _, months, _ = dates_to_components(step_flow["dates"])
        result = compute_group1(step_flow["q"], months)
        assert result[4] == 20.0

    def test_output_shape(self, constant_flow: dict) -> None:
        _, months, _ = dates_to_components(constant_flow["dates"])
        result = compute_group1(constant_flow["q"], months)
        assert result.shape == (12,)


# ---------------------------------------------------------------------------
# Group 2: min/max rolling means, zero-flow days, BFI
# ---------------------------------------------------------------------------
class TestGroup2:
    def test_constant_flow_all_mins_equal(self, constant_flow: dict) -> None:
        result = compute_group2(constant_flow["q"], zero_flow_threshold=0.001)
        np.testing.assert_allclose(result[:5], np.full(5, 10.0), atol=1e-12)

    def test_constant_flow_all_maxs_equal(self, constant_flow: dict) -> None:
        result = compute_group2(constant_flow["q"], zero_flow_threshold=0.001)
        np.testing.assert_allclose(result[5:10], np.full(5, 10.0), atol=1e-12)

    def test_constant_flow_bfi_is_one(self, constant_flow: dict) -> None:
        result = compute_group2(constant_flow["q"], zero_flow_threshold=0.001)
        assert result[11] == 1.0

    def test_constant_flow_zero_flow_days(self, constant_flow: dict) -> None:
        result = compute_group2(constant_flow["q"], zero_flow_threshold=0.001)
        assert result[10] == 0.0

    def test_zero_flow_bfi_is_nan(self, zero_flow: dict) -> None:
        result = compute_group2(zero_flow["q"], zero_flow_threshold=0.001)
        assert np.isnan(result[11])

    def test_zero_flow_days_is_365(self, zero_flow: dict) -> None:
        result = compute_group2(zero_flow["q"], zero_flow_threshold=0.001)
        assert result[10] == 365.0

    def test_step_flow_min_1day(self, step_flow: dict) -> None:
        result = compute_group2(step_flow["q"], zero_flow_threshold=0.001)
        assert result[0] == 5.0

    def test_step_flow_max_1day(self, step_flow: dict) -> None:
        result = compute_group2(step_flow["q"], zero_flow_threshold=0.001)
        assert result[5] == 20.0

    def test_ramp_flow_min_less_than_max(self, ramp_flow: dict) -> None:
        result = compute_group2(ramp_flow["q"], zero_flow_threshold=0.001)
        for i in range(5):
            assert result[i] < result[i + 5]

    def test_output_shape(self, constant_flow: dict) -> None:
        result = compute_group2(constant_flow["q"], zero_flow_threshold=0.001)
        assert result.shape == (12,)


# ---------------------------------------------------------------------------
# Group 3: timing of annual extremes
# ---------------------------------------------------------------------------
class TestGroup3:
    def test_step_flow_date_of_min(self, step_flow: dict) -> None:
        _, _, doy = dates_to_components(step_flow["dates"])
        result = compute_group3(step_flow["q"], doy)
        assert result[0] == 1

    def test_step_flow_date_of_max(self, step_flow: dict) -> None:
        _, _, doy = dates_to_components(step_flow["dates"])
        result = compute_group3(step_flow["q"], doy)
        assert result[1] == 101

    def test_seasonal_sine_date_of_max(self, seasonal_sine: dict) -> None:
        _, _, doy = dates_to_components(seasonal_sine["dates"])
        result = compute_group3(seasonal_sine["q"], doy)
        np.testing.assert_allclose(result[1], 183, atol=2)

    def test_output_shape(self, constant_flow: dict) -> None:
        _, _, doy = dates_to_components(constant_flow["dates"])
        result = compute_group3(constant_flow["q"], doy)
        assert result.shape == (2,)


# ---------------------------------------------------------------------------
# Group 4: low/high pulse count and mean duration
# ---------------------------------------------------------------------------
class TestGroup4:
    def test_pulse_flow_low_count(self, pulse_flow: dict) -> None:
        result = compute_group4(pulse_flow["q"], low_thresh=10.0, high_thresh=40.0)
        assert result[0] == 19

    def test_pulse_flow_high_count(self, pulse_flow: dict) -> None:
        result = compute_group4(pulse_flow["q"], low_thresh=10.0, high_thresh=40.0)
        assert result[2] == 18

    def test_pulse_flow_high_duration(self, pulse_flow: dict) -> None:
        result = compute_group4(pulse_flow["q"], low_thresh=10.0, high_thresh=40.0)
        assert result[3] == 10.0

    def test_constant_flow_no_pulses(self, constant_flow: dict) -> None:
        result = compute_group4(constant_flow["q"], low_thresh=5.0, high_thresh=15.0)
        np.testing.assert_array_equal(result, np.zeros(4))

    def test_output_shape(self, constant_flow: dict) -> None:
        result = compute_group4(constant_flow["q"], low_thresh=5.0, high_thresh=15.0)
        assert result.shape == (4,)


# ---------------------------------------------------------------------------
# Group 5: rise rate, fall rate, reversals
# ---------------------------------------------------------------------------
class TestGroup5:
    def test_constant_flow_zero_rates(self, constant_flow: dict) -> None:
        result = compute_group5(constant_flow["q"])
        np.testing.assert_array_equal(result, np.zeros(3))

    def test_ramp_flow_positive_rise(self, ramp_flow: dict) -> None:
        result = compute_group5(ramp_flow["q"])
        np.testing.assert_allclose(result[0], 99.0 / 364.0, rtol=1e-4)

    def test_ramp_flow_zero_fall(self, ramp_flow: dict) -> None:
        result = compute_group5(ramp_flow["q"])
        assert result[1] == 0.0

    def test_ramp_flow_zero_reversals(self, ramp_flow: dict) -> None:
        result = compute_group5(ramp_flow["q"])
        assert result[2] == 0.0

    def test_triangle_wave_one_reversal(self, triangle_wave: dict) -> None:
        result = compute_group5(triangle_wave["q"])
        assert result[2] == 1.0

    def test_triangle_wave_rise_rate(self, triangle_wave: dict) -> None:
        result = compute_group5(triangle_wave["q"])
        np.testing.assert_allclose(result[0], 90.0 / 99.0, rtol=1e-4)

    def test_triangle_wave_fall_rate_negative(self, triangle_wave: dict) -> None:
        result = compute_group5(triangle_wave["q"])
        np.testing.assert_allclose(result[1], -90.0 / 264.0, rtol=1e-4)

    def test_output_shape(self, constant_flow: dict) -> None:
        result = compute_group5(constant_flow["q"])
        assert result.shape == (3,)

    def test_zero_flow_no_rates(self, zero_flow: dict) -> None:
        result = compute_group5(zero_flow["q"])
        assert result[0] == 0.0
        assert result[1] == 0.0
        assert result[2] == 0.0
