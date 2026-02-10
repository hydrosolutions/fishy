"""Tests for DHRAM evaluation orchestrator."""

from datetime import date

import numpy as np
import pytest
from taqsim.node import TimeSeries
from taqsim.testing import (
    EvenSplit,
    make_edge,
    make_reach,
    make_sink,
    make_source,
    make_splitter,
    make_system,
)
from taqsim.time import Frequency

from fishy.dhram.errors import NoCommonReachesError
from fishy.dhram.evaluate import evaluate_dhram
from fishy.dhram.types import ThresholdVariant
from fishy.iha.errors import MissingStartDateError, NonDailyFrequencyError

NATURAL_TAG = "natural"
N_STEPS = 730  # ~2 years of daily data


def _variable_inflow(n: int, seed: int = 42) -> TimeSeries:
    """Create a sinusoidal + noise inflow pattern with distinct percentiles."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 4 * np.pi, n)
    values = 50.0 + 40.0 * np.sin(t) + rng.normal(0, 5, n)
    values = np.maximum(values, 0.1)
    return TimeSeries(values=values.tolist())


@pytest.fixture
def simple_daily_system():
    """Source -> Reach -> Sink with natural tags, daily, 2 years."""
    system = make_system(
        make_source("source", n_steps=N_STEPS, inflow=_variable_inflow(N_STEPS)),
        make_reach("reach"),
        make_sink("sink"),
        make_edge("e_in", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("e_out", "reach", "sink", tags=frozenset({NATURAL_TAG})),
        frequency=Frequency.DAILY,
        start_date=date(2020, 1, 1),
        validate=False,
    )
    system.simulate(N_STEPS)
    return system


@pytest.fixture
def multi_reach_system():
    """Source -> Reach1 -> Splitter -> Reach2 -> Sink1, Splitter -> Reach3 -> Sink2."""
    system = make_system(
        make_source("source", n_steps=N_STEPS, inflow=_variable_inflow(N_STEPS)),
        make_reach("reach1"),
        make_splitter("splitter", split_policy=EvenSplit()),
        make_reach("reach2"),
        make_reach("reach3"),
        make_sink("sink1"),
        make_sink("sink2"),
        make_edge("e_src_r1", "source", "reach1", tags=frozenset({NATURAL_TAG})),
        make_edge("e_r1_sp", "reach1", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("e_sp_r2", "splitter", "reach2", tags=frozenset({NATURAL_TAG})),
        make_edge("e_sp_r3", "splitter", "reach3", tags=frozenset({NATURAL_TAG})),
        make_edge("e_r2_s1", "reach2", "sink1", tags=frozenset({NATURAL_TAG})),
        make_edge("e_r3_s2", "reach3", "sink2", tags=frozenset({NATURAL_TAG})),
        frequency=Frequency.DAILY,
        start_date=date(2020, 1, 1),
        validate=False,
    )
    system.simulate(N_STEPS)
    return system


@pytest.fixture
def monthly_system():
    """Monthly system — should fail validation."""
    system = make_system(
        make_source("source", n_steps=24),
        make_reach("reach"),
        make_sink("sink"),
        make_edge("e_in", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("e_out", "reach", "sink", tags=frozenset({NATURAL_TAG})),
        frequency=Frequency.MONTHLY,
        start_date=date(2020, 1, 1),
        validate=False,
    )
    system.simulate(24)
    return system


@pytest.fixture
def no_start_date_system():
    """Daily system without start_date."""
    system = make_system(
        make_source("source", n_steps=N_STEPS),
        make_reach("reach"),
        make_sink("sink"),
        make_edge("e_in", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("e_out", "reach", "sink", tags=frozenset({NATURAL_TAG})),
        frequency=Frequency.DAILY,
        validate=False,
    )
    system.simulate(N_STEPS)
    return system


@pytest.fixture
def no_natural_reaches_system():
    """Daily system with natural-tagged edges but no Reach node on natural path."""
    system = make_system(
        make_source("source", n_steps=N_STEPS, inflow=_variable_inflow(N_STEPS)),
        make_sink("sink"),
        make_edge("e1", "source", "sink", tags=frozenset({NATURAL_TAG})),
        frequency=Frequency.DAILY,
        start_date=date(2020, 1, 1),
        validate=False,
    )
    system.simulate(N_STEPS)
    return system


class TestInputValidation:
    def test_non_daily_natural_raises(self, monthly_system, simple_daily_system) -> None:
        with pytest.raises(NonDailyFrequencyError, match="365"):
            evaluate_dhram(monthly_system, simple_daily_system)

    def test_non_daily_impacted_raises(self, simple_daily_system, monthly_system) -> None:
        with pytest.raises(NonDailyFrequencyError, match="365"):
            evaluate_dhram(simple_daily_system, monthly_system)

    def test_missing_start_date_raises(self, no_start_date_system, simple_daily_system) -> None:
        with pytest.raises(MissingStartDateError, match="start_date"):
            evaluate_dhram(no_start_date_system, simple_daily_system)

    def test_no_common_reaches_raises(self, no_natural_reaches_system, simple_daily_system) -> None:
        with pytest.raises(NoCommonReachesError, match="No common"):
            evaluate_dhram(simple_daily_system, no_natural_reaches_system)


class TestReachSelection:
    def test_default_selects_natural_reaches(self, simple_daily_system) -> None:
        results = evaluate_dhram(simple_daily_system, simple_daily_system)
        assert "reach" in results

    def test_subset_filtering(self, multi_reach_system) -> None:
        results = evaluate_dhram(multi_reach_system, multi_reach_system, reach_ids=["reach2"])
        assert "reach2" in results
        assert "reach3" not in results


class TestMultiReach:
    def test_returns_dict_keyed_by_reach(self, multi_reach_system) -> None:
        results = evaluate_dhram(multi_reach_system, multi_reach_system)
        assert isinstance(results, dict)
        # Should have multiple natural reaches
        assert len(results) >= 2

    def test_each_result_is_dhram_result(self, multi_reach_system) -> None:
        from fishy.dhram.types import DHRAMResult

        results = evaluate_dhram(multi_reach_system, multi_reach_system)
        for result in results.values():
            assert isinstance(result, DHRAMResult)


class TestIntegration:
    def test_natural_vs_itself_class_1(self, simple_daily_system) -> None:
        results = evaluate_dhram(simple_daily_system, simple_daily_system)
        for result in results.values():
            assert result.total_points == 0
            assert result.final_class == 1
            assert result.wfd_status == "High"

    def test_threshold_variant_passed_through(self, simple_daily_system) -> None:
        results = evaluate_dhram(
            simple_daily_system,
            simple_daily_system,
            threshold_variant=ThresholdVariant.SIMPLIFIED,
        )
        for result in results.values():
            assert result.threshold_variant == ThresholdVariant.SIMPLIFIED
