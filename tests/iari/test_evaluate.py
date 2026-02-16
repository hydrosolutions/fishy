"""Tests for IARI evaluation orchestrator."""

import pytest
from fishy.iari.evaluate import evaluate_iari

from fishy.iari.errors import NoCommonReachesError
from fishy.iari.types import IARIResult
from fishy.iha.errors import MissingStartDateError, NonDailyFrequencyError


class TestInputValidation:
    def test_non_daily_natural_raises(self, monthly_system, simple_daily_system) -> None:
        with pytest.raises(NonDailyFrequencyError, match="365"):
            evaluate_iari(monthly_system, simple_daily_system)

    def test_non_daily_impacted_raises(self, simple_daily_system, monthly_system) -> None:
        with pytest.raises(NonDailyFrequencyError, match="365"):
            evaluate_iari(simple_daily_system, monthly_system)

    def test_missing_start_date_raises(self, no_start_date_system, simple_daily_system) -> None:
        with pytest.raises(MissingStartDateError, match="start_date"):
            evaluate_iari(no_start_date_system, simple_daily_system)

    def test_no_common_reaches_raises(self, no_natural_reaches_system, simple_daily_system) -> None:
        with pytest.raises(NoCommonReachesError, match="No common"):
            evaluate_iari(simple_daily_system, no_natural_reaches_system)


class TestReachSelection:
    def test_default_selects_natural_reaches(self, simple_daily_system) -> None:
        results = evaluate_iari(simple_daily_system, simple_daily_system)
        assert "reach" in results

    def test_subset_filtering(self, multi_reach_system) -> None:
        results = evaluate_iari(multi_reach_system, multi_reach_system, reach_ids=["reach2"])
        assert "reach2" in results
        assert "reach3" not in results


class TestIntegration:
    def test_natural_vs_itself_zero(self, simple_daily_system) -> None:
        results = evaluate_iari(simple_daily_system, simple_daily_system)
        for result in results.values():
            assert result.overall == pytest.approx(0.0, abs=1e-10)

    def test_natural_vs_itself_excellent(self, simple_daily_system) -> None:
        results = evaluate_iari(simple_daily_system, simple_daily_system)
        for result in results.values():
            assert result.classification == "Excellent"

    def test_returns_dict_keyed_by_reach(self, multi_reach_system) -> None:
        results = evaluate_iari(multi_reach_system, multi_reach_system)
        assert isinstance(results, dict)
        assert len(results) >= 2

    def test_each_result_is_iari_result(self, multi_reach_system) -> None:
        results = evaluate_iari(multi_reach_system, multi_reach_system)
        for result in results.values():
            assert isinstance(result, IARIResult)
