"""Tests for DHRAM and IHA bridge error types."""

import pytest

from fishy.dhram.errors import (
    DHRAMError,
    IncompatibleIHAResultsError,
    InsufficientYearsError,
    NoCommonReachesError,
    ReachEvaluationError,
)
from fishy.iha.errors import (
    EmptyReachTraceError,
    IHAError,
    MissingStartDateError,
    NonDailyFrequencyError,
    NotAReachError,
    ReachNotFoundError,
)

# ---------------------------------------------------------------------------
# DHRAM errors
# ---------------------------------------------------------------------------


class TestDHRAMErrorHierarchy:
    def test_base_class(self) -> None:
        assert issubclass(IncompatibleIHAResultsError, DHRAMError)
        assert issubclass(InsufficientYearsError, DHRAMError)
        assert issubclass(NoCommonReachesError, DHRAMError)
        assert issubclass(ReachEvaluationError, DHRAMError)

    def test_dhram_error_is_exception(self) -> None:
        assert issubclass(DHRAMError, Exception)


class TestIncompatibleIHAResultsError:
    def test_fields(self) -> None:
        err = IncompatibleIHAResultsError(natural_n_params=33, impacted_n_params=10)
        assert err.natural_n_params == 33
        assert err.impacted_n_params == 10

    def test_str_contains_counts(self) -> None:
        err = IncompatibleIHAResultsError(natural_n_params=33, impacted_n_params=10)
        msg = str(err)
        assert "33" in msg
        assert "10" in msg
        assert "parameters" in msg.lower()

    def test_is_catchable_as_dhram_error(self) -> None:
        with pytest.raises(DHRAMError):
            raise IncompatibleIHAResultsError(natural_n_params=33, impacted_n_params=10)


class TestInsufficientYearsError:
    def test_fields(self) -> None:
        err = InsufficientYearsError(series_label="natural", n_years=2, min_years=5)
        assert err.series_label == "natural"
        assert err.n_years == 2
        assert err.min_years == 5

    def test_str_contains_info(self) -> None:
        err = InsufficientYearsError(series_label="natural", n_years=2, min_years=5)
        msg = str(err)
        assert "natural" in msg
        assert "2" in msg
        assert "5" in msg


class TestNoCommonReachesError:
    def test_fields(self) -> None:
        err = NoCommonReachesError(
            natural_reach_ids=frozenset({"a", "b"}),
            impacted_reach_ids=frozenset({"c", "d"}),
        )
        assert err.natural_reach_ids == frozenset({"a", "b"})
        assert err.impacted_reach_ids == frozenset({"c", "d"})

    def test_str_contains_reaches(self) -> None:
        err = NoCommonReachesError(
            natural_reach_ids=frozenset({"reach1"}),
            impacted_reach_ids=frozenset({"reach2"}),
        )
        msg = str(err)
        assert "reach1" in msg
        assert "reach2" in msg


class TestReachEvaluationError:
    def test_fields(self) -> None:
        errors = {"r1": ValueError("bad"), "r2": RuntimeError("worse")}
        err = ReachEvaluationError(reach_errors=errors)
        assert len(err.reach_errors) == 2

    def test_str_contains_count_and_details(self) -> None:
        errors = {"r1": ValueError("bad data")}
        err = ReachEvaluationError(reach_errors=errors)
        msg = str(err)
        assert "1" in msg
        assert "r1" in msg
        assert "bad data" in msg


# ---------------------------------------------------------------------------
# IHA bridge errors
# ---------------------------------------------------------------------------


class TestIHABridgeErrorHierarchy:
    def test_all_inherit_from_iha_error(self) -> None:
        assert issubclass(MissingStartDateError, IHAError)
        assert issubclass(NonDailyFrequencyError, IHAError)
        assert issubclass(ReachNotFoundError, IHAError)
        assert issubclass(NotAReachError, IHAError)
        assert issubclass(EmptyReachTraceError, IHAError)


class TestMissingStartDateError:
    def test_str_mentions_start_date(self) -> None:
        err = MissingStartDateError()
        assert "start_date" in str(err)

    def test_catchable_as_iha_error(self) -> None:
        with pytest.raises(IHAError):
            raise MissingStartDateError()


class TestNonDailyFrequencyError:
    def test_field(self) -> None:
        err = NonDailyFrequencyError(frequency=12)
        assert err.frequency == 12

    def test_str_mentions_frequency(self) -> None:
        err = NonDailyFrequencyError(frequency=12)
        assert "12" in str(err)
        assert "365" in str(err)


class TestReachNotFoundError:
    def test_fields(self) -> None:
        err = ReachNotFoundError(reach_id="bad_reach", available_reach_ids=frozenset({"r1", "r2"}))
        assert err.reach_id == "bad_reach"
        assert err.available_reach_ids == frozenset({"r1", "r2"})

    def test_str_mentions_reach_and_available(self) -> None:
        err = ReachNotFoundError(reach_id="bad_reach", available_reach_ids=frozenset({"r1"}))
        msg = str(err)
        assert "bad_reach" in msg
        assert "r1" in msg


class TestNotAReachError:
    def test_fields(self) -> None:
        err = NotAReachError(node_id="sink1", actual_type="Sink")
        assert err.node_id == "sink1"
        assert err.actual_type == "Sink"

    def test_str_mentions_node_and_type(self) -> None:
        err = NotAReachError(node_id="sink1", actual_type="Sink")
        msg = str(err)
        assert "sink1" in msg
        assert "Sink" in msg
        assert "Reach" in msg


class TestEmptyReachTraceError:
    def test_field(self) -> None:
        err = EmptyReachTraceError(reach_id="r1")
        assert err.reach_id == "r1"

    def test_str_mentions_reach(self) -> None:
        err = EmptyReachTraceError(reach_id="r1")
        assert "r1" in str(err)
