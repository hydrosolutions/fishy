"""Tests for IARI error hierarchy."""

import pytest

from fishy.iari.errors import (
    IARIError,
    IncompatibleIHAResultsError,
    InsufficientYearsError,
    NoCommonReachesError,
    ReachEvaluationError,
)


class TestErrorHierarchy:
    def test_all_errors_inherit_from_iari_error(self) -> None:
        assert issubclass(IncompatibleIHAResultsError, IARIError)
        assert issubclass(InsufficientYearsError, IARIError)
        assert issubclass(NoCommonReachesError, IARIError)
        assert issubclass(ReachEvaluationError, IARIError)

    def test_iari_error_is_exception(self) -> None:
        assert issubclass(IARIError, Exception)


class TestIncompatibleIHAResultsError:
    def test_fields(self) -> None:
        err = IncompatibleIHAResultsError(natural_n_params=33, impacted_n_params=10)
        assert err.natural_n_params == 33
        assert err.impacted_n_params == 10

    def test_str_message(self) -> None:
        err = IncompatibleIHAResultsError(natural_n_params=33, impacted_n_params=10)
        msg = str(err)
        assert "33" in msg
        assert "10" in msg
        assert "Incompatible" in msg

    def test_catchable_as_iari_error(self) -> None:
        with pytest.raises(IARIError):
            raise IncompatibleIHAResultsError(natural_n_params=33, impacted_n_params=10)


class TestInsufficientYearsError:
    def test_fields(self) -> None:
        err = InsufficientYearsError(series_label="natural", n_years=2, min_years=5)
        assert err.series_label == "natural"
        assert err.n_years == 2
        assert err.min_years == 5

    def test_str_message(self) -> None:
        err = InsufficientYearsError(series_label="natural", n_years=2, min_years=5)
        msg = str(err)
        assert "natural" in msg
        assert "2" in msg
        assert "5" in msg
        assert "Insufficient" in msg


class TestNoCommonReachesError:
    def test_fields(self) -> None:
        err = NoCommonReachesError(
            natural_reach_ids=frozenset({"r1", "r2"}),
            impacted_reach_ids=frozenset({"r3", "r4"}),
        )
        assert err.natural_reach_ids == frozenset({"r1", "r2"})
        assert err.impacted_reach_ids == frozenset({"r3", "r4"})

    def test_str_message(self) -> None:
        err = NoCommonReachesError(
            natural_reach_ids=frozenset({"r1", "r2"}),
            impacted_reach_ids=frozenset({"r3"}),
        )
        msg = str(err)
        assert "No common" in msg
        assert "r1" in msg
        assert "r2" in msg
        assert "r3" in msg


class TestReachEvaluationError:
    def test_fields(self) -> None:
        errors = {"reach_a": ValueError("bad"), "reach_b": RuntimeError("fail")}
        err = ReachEvaluationError(reach_errors=errors)
        assert err.reach_errors is errors
        assert len(err.reach_errors) == 2

    def test_str_message(self) -> None:
        errors = {"reach_a": ValueError("bad value"), "reach_b": RuntimeError("fail")}
        err = ReachEvaluationError(reach_errors=errors)
        msg = str(err)
        assert "reach_a" in msg
        assert "reach_b" in msg
        assert "bad value" in msg
        assert "fail" in msg
        assert "2" in msg  # "All 2 reach(es)"
