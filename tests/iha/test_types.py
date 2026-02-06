"""Tests for IHA type definitions."""

import numpy as np
import pytest

from fishy.iha.types import ZERO_FLOW_THRESHOLD, Col, IHAResult, PulseThresholds


class TestCol:
    def test_n_params_is_33(self) -> None:
        assert Col.N_PARAMS == 33

    def test_names_length_matches_n_params(self) -> None:
        assert len(Col.NAMES) == Col.N_PARAMS

    def test_groups_cover_all_params(self) -> None:
        covered = set()
        for s in Col.GROUPS:
            indices = set(range(s.start, s.stop))
            assert covered.isdisjoint(indices), f"overlap at {covered & indices}"
            covered |= indices
        assert covered == set(range(Col.N_PARAMS))

    def test_jan_through_dec_are_0_to_11(self) -> None:
        months = [
            Col.JAN,
            Col.FEB,
            Col.MAR,
            Col.APR,
            Col.MAY,
            Col.JUN,
            Col.JUL,
            Col.AUG,
            Col.SEP,
            Col.OCT,
            Col.NOV,
            Col.DEC,
        ]
        assert months == list(range(12))


class TestPulseThresholds:
    def test_valid_construction(self) -> None:
        pt = PulseThresholds(low=5.0, high=25.0)
        assert pt.low == 5.0
        assert pt.high == 25.0

    def test_negative_low_raises(self) -> None:
        with pytest.raises(ValueError, match="low threshold"):
            PulseThresholds(low=-1.0, high=10.0)

    def test_low_equals_high_raises(self) -> None:
        with pytest.raises(ValueError, match="less than"):
            PulseThresholds(low=10.0, high=10.0)

    def test_low_greater_than_high_raises(self) -> None:
        with pytest.raises(ValueError, match="less than"):
            PulseThresholds(low=20.0, high=10.0)


def _make_result() -> IHAResult:
    values = np.arange(66, dtype=np.float64).reshape(2, 33)
    years = np.array([2020, 2021], dtype=np.intp)
    return IHAResult(
        values=values,
        years=years,
        zero_flow_threshold=ZERO_FLOW_THRESHOLD,
        pulse_thresholds=None,
    )


class TestIHAResult:
    def test_group_returns_correct_slice(self) -> None:
        result = _make_result()
        g1 = result.group(1)
        np.testing.assert_array_equal(g1, result.values[:, 0:12])

    def test_group_out_of_range_raises(self) -> None:
        result = _make_result()
        with pytest.raises(ValueError, match="between 1 and 5"):
            result.group(0)
        with pytest.raises(ValueError, match="between 1 and 5"):
            result.group(6)

    def test_param_returns_column(self) -> None:
        result = _make_result()
        jan = result.param(Col.JAN)
        np.testing.assert_array_equal(jan, result.values[:, 0])

    def test_param_out_of_range_raises(self) -> None:
        result = _make_result()
        with pytest.raises(ValueError, match="between 0 and 32"):
            result.param(-1)
        with pytest.raises(ValueError, match="between 0 and 32"):
            result.param(33)

    def test_year_row_returns_correct_row(self) -> None:
        result = _make_result()
        row = result.year_row(2020)
        np.testing.assert_array_equal(row, np.arange(33, dtype=np.float64))

    def test_year_row_missing_raises(self) -> None:
        result = _make_result()
        with pytest.raises(ValueError, match="not found"):
            result.year_row(9999)
