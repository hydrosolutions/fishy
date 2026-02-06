"""Tests for DHRAM and IHA bridge error types."""

import pytest

from fishy.dhram.errors import (
    DHRAMError,
    EdgeEvaluationError,
    IncompatibleIHAResultsError,
    InsufficientYearsError,
    NoCommonEdgesError,
)
from fishy.iha.errors import (
    EdgeNotFoundError,
    EmptyTraceError,
    IHAError,
    MissingStartDateError,
    NonDailyFrequencyError,
)

# ---------------------------------------------------------------------------
# DHRAM errors
# ---------------------------------------------------------------------------


class TestDHRAMErrorHierarchy:
    def test_base_class(self) -> None:
        assert issubclass(IncompatibleIHAResultsError, DHRAMError)
        assert issubclass(InsufficientYearsError, DHRAMError)
        assert issubclass(NoCommonEdgesError, DHRAMError)
        assert issubclass(EdgeEvaluationError, DHRAMError)

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


class TestNoCommonEdgesError:
    def test_fields(self) -> None:
        err = NoCommonEdgesError(
            natural_edge_ids=frozenset({"a", "b"}),
            impacted_edge_ids=frozenset({"c", "d"}),
        )
        assert err.natural_edge_ids == frozenset({"a", "b"})
        assert err.impacted_edge_ids == frozenset({"c", "d"})

    def test_str_contains_edges(self) -> None:
        err = NoCommonEdgesError(
            natural_edge_ids=frozenset({"edge1"}),
            impacted_edge_ids=frozenset({"edge2"}),
        )
        msg = str(err)
        assert "edge1" in msg
        assert "edge2" in msg


class TestEdgeEvaluationError:
    def test_fields(self) -> None:
        errors = {"e1": ValueError("bad"), "e2": RuntimeError("worse")}
        err = EdgeEvaluationError(edge_errors=errors)
        assert len(err.edge_errors) == 2

    def test_str_contains_count_and_details(self) -> None:
        errors = {"e1": ValueError("bad data")}
        err = EdgeEvaluationError(edge_errors=errors)
        msg = str(err)
        assert "1" in msg
        assert "e1" in msg
        assert "bad data" in msg


# ---------------------------------------------------------------------------
# IHA bridge errors
# ---------------------------------------------------------------------------


class TestIHABridgeErrorHierarchy:
    def test_all_inherit_from_iha_error(self) -> None:
        assert issubclass(MissingStartDateError, IHAError)
        assert issubclass(NonDailyFrequencyError, IHAError)
        assert issubclass(EdgeNotFoundError, IHAError)
        assert issubclass(EmptyTraceError, IHAError)


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


class TestEdgeNotFoundError:
    def test_fields(self) -> None:
        err = EdgeNotFoundError(edge_id="bad_edge", available_edge_ids=frozenset({"e1", "e2"}))
        assert err.edge_id == "bad_edge"
        assert err.available_edge_ids == frozenset({"e1", "e2"})

    def test_str_mentions_edge_and_available(self) -> None:
        err = EdgeNotFoundError(edge_id="bad_edge", available_edge_ids=frozenset({"e1"}))
        msg = str(err)
        assert "bad_edge" in msg
        assert "e1" in msg


class TestEmptyTraceError:
    def test_field(self) -> None:
        err = EmptyTraceError(edge_id="e1")
        assert err.edge_id == "e1"

    def test_str_mentions_edge(self) -> None:
        err = EmptyTraceError(edge_id="e1")
        assert "e1" in str(err)
