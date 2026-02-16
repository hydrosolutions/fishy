"""Shared fixtures for IARI tests."""

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

from fishy.iari._deviation import bands_from_iha
from fishy.iari.types import NaturalBands
from fishy.iha.bridge import iha_from_reach
from fishy.iha.types import IHAResult, PulseThresholds

NATURAL_TAG = "natural"
N_STEPS = 730  # ~2 years of daily data


def make_iha_result(
    values: np.ndarray,
    years: np.ndarray | None = None,
    zero_flow_threshold: float = 0.001,
    pulse_thresholds: PulseThresholds | None = None,
) -> IHAResult:
    """Helper to construct IHAResult from a values array."""
    if values.ndim == 1:
        values = values.reshape(1, -1)
    n_years = values.shape[0]
    if years is None:
        years = np.arange(2000, 2000 + n_years, dtype=np.intp)
    if pulse_thresholds is None:
        pulse_thresholds = PulseThresholds(low=5.0, high=50.0)
    return IHAResult(
        values=values,
        years=years,
        zero_flow_threshold=zero_flow_threshold,
        pulse_thresholds=pulse_thresholds,
    )


def _variable_inflow(n: int, seed: int = 42) -> TimeSeries:
    """Create a sinusoidal + noise inflow pattern."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 4 * np.pi, n)
    values = 50.0 + 40.0 * np.sin(t) + rng.normal(0, 5, n)
    values = np.maximum(values, 0.1)
    return TimeSeries(values=values.tolist())


@pytest.fixture
def identical_iha_pair() -> tuple[IHAResult, IHAResult]:
    """Identical natural and impacted IHA data (random, 5 years)."""
    rng = np.random.default_rng(42)
    values = rng.uniform(1.0, 100.0, size=(5, 33))
    # Set timing columns to valid DOY range
    values[:, 24] = rng.uniform(1, 365, size=5)
    values[:, 25] = rng.uniform(1, 365, size=5)
    natural = make_iha_result(values.copy())
    impacted = make_iha_result(values.copy())
    return natural, impacted


@pytest.fixture
def controlled_iha_pair() -> tuple[IHAResult, IHAResult]:
    """5 natural years with values [10,20,30,40,50] per param.
    Q25=20, Q75=40, IQR=20. Altered value=50 -> deviation=0.5.
    """
    # Natural: 5 years, each param has values [10, 20, 30, 40, 50]
    natural_values = np.tile(np.array([10.0, 20.0, 30.0, 40.0, 50.0]).reshape(5, 1), (1, 33))
    natural = make_iha_result(natural_values)

    # Impacted: single year with all params = 50
    # deviation = min(|50-20|, |50-40|) / 20 = min(30, 10) / 20 = 10/20 = 0.5
    impacted_values = np.full((1, 33), 50.0)
    impacted = make_iha_result(impacted_values, years=np.array([2010], dtype=np.intp))
    return natural, impacted


@pytest.fixture
def within_band_pair() -> tuple[IHAResult, IHAResult]:
    """Altered values all within Q25-Q75 band — deviation should be 0."""
    # Natural: 5 years, each param has values [10, 20, 30, 40, 50]
    natural_values = np.tile(np.array([10.0, 20.0, 30.0, 40.0, 50.0]).reshape(5, 1), (1, 33))
    natural = make_iha_result(natural_values)

    # Impacted: single year with all params = 30 (within [20, 40])
    impacted_values = np.full((1, 33), 30.0)
    impacted = make_iha_result(impacted_values, years=np.array([2010], dtype=np.intp))
    return natural, impacted


@pytest.fixture
def degenerate_band_pair() -> tuple[IHAResult, IHAResult]:
    """Natural has constant values (IQR=0) for some params."""
    # Natural: 5 years, all params = 25.0 (constant -> IQR=0 for all)
    natural_values = np.full((5, 33), 25.0)
    natural = make_iha_result(natural_values)

    # Impacted: single year, first 16 params = 25.0 (same), last 17 params = 50.0
    impacted_values = np.full((1, 33), 25.0)
    impacted_values[0, 16:] = 50.0
    impacted = make_iha_result(impacted_values, years=np.array([2010], dtype=np.intp))
    return natural, impacted


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
    """Source -> Reach1 -> Splitter -> Reach2, Reach3."""
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
    """Daily system with no Reach on natural path."""
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


@pytest.fixture
def multi_reach_bands(multi_reach_system) -> dict[str, NaturalBands]:
    """Pre-computed NaturalBands for each reach in multi_reach_system."""
    return {rid: bands_from_iha(iha_from_reach(multi_reach_system, rid)) for rid in ["reach1", "reach2", "reach3"]}
