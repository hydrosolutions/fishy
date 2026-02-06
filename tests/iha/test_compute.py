"""Tests for the IHA computation orchestrator."""

import numpy as np
import pytest

from fishy.iha.compute import compute_iha, pulse_thresholds_from_record
from fishy.iha.errors import (
    DateFlowLengthMismatchError,
    InsufficientDataError,
    NegativeFlowError,
    NonDailyTimestepError,
)
from fishy.iha.types import Col, PulseThresholds


def _make_data(start: str, end: str, value: float = 10.0) -> tuple[np.ndarray, np.ndarray]:
    """Create constant-flow test data between two dates.

    Args:
        start: Start date (inclusive), e.g. "2023-01-01".
        end: End date (exclusive), e.g. "2024-01-01".
        value: Constant flow value.

    Returns:
        Tuple of (q, dates).
    """
    dates = np.arange(start, end, dtype="datetime64[D]")
    q = np.full(len(dates), value)
    return q, dates


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_length_mismatch_raises(self) -> None:
        q = np.arange(10, dtype=np.float64)
        dates = np.arange("2023-01-01", "2023-01-06", dtype="datetime64[D]")
        with pytest.raises(DateFlowLengthMismatchError, match="10.*5|5.*10"):
            compute_iha(q, dates)

    def test_negative_flow_raises(self) -> None:
        dates = np.arange("2023-01-01", "2023-01-05", dtype="datetime64[D]")
        q = np.array([1.0, -1.0, 2.0, -3.0])
        with pytest.raises(NegativeFlowError, match="2 negative") as exc_info:
            compute_iha(q, dates)
        assert exc_info.value.n_negative == 2
        assert exc_info.value.min_value == -3.0

    def test_non_daily_gap_raises(self) -> None:
        dates = np.array(
            ["2023-01-01", "2023-01-02", "2023-01-04", "2023-01-05"],
            dtype="datetime64[D]",
        )
        q = np.ones(4)
        with pytest.raises(NonDailyTimestepError, match="position 1.*2 day"):
            compute_iha(q, dates)

    def test_insufficient_years_raises(self) -> None:
        # 200 days starting mid-year: no complete calendar year
        q, dates = _make_data("2023-06-01", "2023-12-18")
        with pytest.raises(InsufficientDataError, match="0 complete"):
            compute_iha(q, dates, min_years=1)

    def test_empty_arrays_raises(self) -> None:
        q = np.array([], dtype=np.float64)
        dates = np.array([], dtype="datetime64[D]")
        with pytest.raises(InsufficientDataError, match="0 complete"):
            compute_iha(q, dates, min_years=1)


# ---------------------------------------------------------------------------
# Pulse Thresholds from Record
# ---------------------------------------------------------------------------


class TestPulseThresholdsFromRecord:
    def test_derived_from_percentiles(self) -> None:
        q = np.arange(100, dtype=np.float64)
        thresholds = pulse_thresholds_from_record(q)
        np.testing.assert_allclose(thresholds.low, np.percentile(q, 25))
        np.testing.assert_allclose(thresholds.high, np.percentile(q, 75))

    def test_constant_flow_raises(self) -> None:
        q = np.full(100, 5.0)
        with pytest.raises(ValueError, match="low.*high|less than"):
            pulse_thresholds_from_record(q)


# ---------------------------------------------------------------------------
# Single Year
# ---------------------------------------------------------------------------


class TestSingleYear:
    def test_constant_flow_shape(self, constant_flow: dict) -> None:
        result = compute_iha(
            constant_flow["q"],
            constant_flow["dates"],
            pulse_thresholds=PulseThresholds(low=5.0, high=15.0),
        )
        assert result.values.shape == (1, 33)

    def test_constant_flow_year(self, constant_flow: dict) -> None:
        result = compute_iha(
            constant_flow["q"],
            constant_flow["dates"],
            pulse_thresholds=PulseThresholds(low=5.0, high=15.0),
        )
        np.testing.assert_array_equal(result.years, [2023])

    def test_constant_flow_monthly_means(self, constant_flow: dict) -> None:
        result = compute_iha(
            constant_flow["q"],
            constant_flow["dates"],
            pulse_thresholds=PulseThresholds(low=5.0, high=15.0),
        )
        group1 = result.group(1)
        np.testing.assert_allclose(group1, 10.0)

    def test_constant_flow_bfi(self, constant_flow: dict) -> None:
        result = compute_iha(
            constant_flow["q"],
            constant_flow["dates"],
            pulse_thresholds=PulseThresholds(low=5.0, high=15.0),
        )
        bfi = result.param(Col.BASE_FLOW_INDEX)
        np.testing.assert_allclose(bfi, 1.0)

    def test_ramp_flow_rise_rate(self, ramp_flow: dict) -> None:
        result = compute_iha(ramp_flow["q"], ramp_flow["dates"])
        rise_rate = result.param(Col.RISE_RATE)
        # Monotonic ramp: every diff is 99/364, so median is 99/364
        np.testing.assert_allclose(rise_rate, 99.0 / 364.0, rtol=1e-4)

    def test_step_flow_extremes(self, step_flow: dict) -> None:
        result = compute_iha(step_flow["q"], step_flow["dates"])
        np.testing.assert_allclose(result.param(Col.MIN_1DAY), 5.0)
        np.testing.assert_allclose(result.param(Col.MAX_1DAY), 20.0)


# ---------------------------------------------------------------------------
# Multi-Year
# ---------------------------------------------------------------------------


class TestMultiYear:
    def test_three_complete_years(self) -> None:
        # 2022-01-01 through 2024-12-31 = 3 full calendar years
        q, dates = _make_data("2022-01-01", "2025-01-01")
        result = compute_iha(q, dates, pulse_thresholds=PulseThresholds(low=5.0, high=15.0))
        assert result.values.shape[0] == 3
        np.testing.assert_array_equal(result.years, [2022, 2023, 2024])

    def test_partial_years_excluded(self) -> None:
        # 2023-06-01 through 2025-06-01: only 2024 is complete
        q, dates = _make_data("2023-06-01", "2025-06-02")
        result = compute_iha(q, dates, pulse_thresholds=PulseThresholds(low=5.0, high=15.0))
        assert result.values.shape[0] == 1
        np.testing.assert_array_equal(result.years, [2024])

    def test_multi_year_values_independent(self) -> None:
        dates = np.arange("2022-01-01", "2024-01-01", dtype="datetime64[D]")
        # Year 2022: constant 10.0 (365 days), year 2023: constant 20.0 (365 days)
        q = np.concatenate([np.full(365, 10.0), np.full(365, 20.0)])
        result = compute_iha(q, dates, pulse_thresholds=PulseThresholds(low=5.0, high=25.0))
        # Group 1 (monthly means) should differ between years
        row_2022 = result.year_row(2022)
        row_2023 = result.year_row(2023)
        np.testing.assert_allclose(row_2022[Col.JAN], 10.0)
        np.testing.assert_allclose(row_2023[Col.JAN], 20.0)


# ---------------------------------------------------------------------------
# External Thresholds
# ---------------------------------------------------------------------------


class TestExternalThresholds:
    def test_custom_thresholds_used(self) -> None:
        q, dates = _make_data("2023-01-01", "2024-01-01")
        custom = PulseThresholds(low=3.0, high=17.0)
        result = compute_iha(q, dates, pulse_thresholds=custom)
        assert result.pulse_thresholds == custom

    def test_derived_thresholds_stored(self) -> None:
        # Use ramp data so Q25 != Q75 and auto-derivation works
        dates = np.arange("2023-01-01", "2024-01-01", dtype="datetime64[D]")
        q = np.linspace(1, 100, len(dates))
        result = compute_iha(q, dates)
        assert result.pulse_thresholds is not None
        assert isinstance(result.pulse_thresholds, PulseThresholds)


# ---------------------------------------------------------------------------
# Zero-Flow Threshold
# ---------------------------------------------------------------------------


class TestZeroFlowThreshold:
    def test_default_threshold(self) -> None:
        q, dates = _make_data("2023-01-01", "2024-01-01")
        result = compute_iha(q, dates, pulse_thresholds=PulseThresholds(low=5.0, high=15.0))
        assert result.zero_flow_threshold == 0.001

    def test_custom_threshold(self) -> None:
        q, dates = _make_data("2023-01-01", "2024-01-01")
        result = compute_iha(
            q,
            dates,
            zero_flow_threshold=0.01,
            pulse_thresholds=PulseThresholds(low=5.0, high=15.0),
        )
        assert result.zero_flow_threshold == 0.01

    def test_threshold_affects_count(self) -> None:
        dates = np.arange("2023-01-01", "2024-01-01", dtype="datetime64[D]")
        q = np.full(365, 0.005)

        # Default threshold (0.001): 0.005 > 0.001 => 0 zero-flow days
        result_default = compute_iha(q, dates, pulse_thresholds=PulseThresholds(low=0.001, high=0.01))
        np.testing.assert_allclose(result_default.param(Col.ZERO_FLOW_DAYS), 0.0)

        # Custom threshold (0.01): 0.005 < 0.01 => 365 zero-flow days
        result_custom = compute_iha(
            q,
            dates,
            zero_flow_threshold=0.01,
            pulse_thresholds=PulseThresholds(low=0.001, high=0.01),
        )
        np.testing.assert_allclose(result_custom.param(Col.ZERO_FLOW_DAYS), 365.0)


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_single_day_diffs(self) -> None:
        """Group 5 reversal counting works with diff of length n-1."""
        dates = np.arange("2023-01-01", "2024-01-01", dtype="datetime64[D]")
        # Alternating up/down: many reversals
        q = np.where(np.arange(365) % 2 == 0, 10.0, 20.0)
        result = compute_iha(q, dates)
        reversals = result.param(Col.REVERSALS)[0]
        # With 365 values and alternating pattern, diff has 364 elements
        # whose signs alternate => 363 sign changes
        assert reversals == 363.0

    def test_leap_year(self) -> None:
        """Leap year (366 days) is processed correctly."""
        q, dates = _make_data("2024-01-01", "2025-01-01")
        assert len(dates) == 366  # sanity check: 2024 is a leap year
        result = compute_iha(q, dates, pulse_thresholds=PulseThresholds(low=5.0, high=15.0))
        assert result.values.shape == (1, 33)
        np.testing.assert_array_equal(result.years, [2024])

    def test_min_years_zero(self) -> None:
        """min_years=0 returns empty result when no complete years exist."""
        # 100 days mid-year: no complete calendar year
        q, dates = _make_data("2023-06-01", "2023-09-08")
        result = compute_iha(
            q,
            dates,
            pulse_thresholds=PulseThresholds(low=5.0, high=15.0),
            min_years=0,
        )
        assert result.values.shape == (0, 33)
        assert len(result.years) == 0
