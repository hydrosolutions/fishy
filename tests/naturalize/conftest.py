"""Test fixtures for naturalize module tests."""

import pytest
from taqsim.testing import (
    EvenSplit,
    make_demand,
    make_edge,
    make_passthrough,
    make_sink,
    make_source,
    make_splitter,
    make_storage,
    make_system,
)

from fishy.naturalize import NATURAL_TAG, NaturalRiverSplitter


@pytest.fixture
def simple_linear_system():
    """Source -> Storage -> Sink (all natural)."""
    return make_system(
        make_source("source", n_steps=2),
        make_storage("storage"),
        make_sink("sink"),
        make_edge("source_to_storage", "source", "storage", tags=frozenset({NATURAL_TAG})),
        make_edge("storage_to_sink", "storage", "sink", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )


@pytest.fixture
def system_with_side_branch():
    """Source -> Storage -> Sink (natural) + Storage -> Demand (canal)."""
    return make_system(
        make_source("source"),
        make_storage("storage"),
        make_sink("sink"),
        make_demand("demand"),
        make_edge("source_to_storage", "source", "storage", tags=frozenset({NATURAL_TAG})),
        make_edge("storage_to_sink", "storage", "sink", tags=frozenset({NATURAL_TAG})),
        make_edge("storage_to_demand", "storage", "demand", tags=frozenset({"canal"})),
        validate=False,
    )


@pytest.fixture
def system_no_natural_edges():
    """System with no natural edges - should fail naturalization."""
    return make_system(
        make_source("source"),
        make_sink("sink"),
        make_edge("source_to_sink", "source", "sink", tags=frozenset({"canal"})),
        validate=False,
    )


@pytest.fixture
def system_with_demand_on_path():
    """Source -> Demand -> Sink (all natural)."""
    return make_system(
        make_source("source"),
        make_demand("demand"),
        make_sink("sink"),
        make_edge("source_to_demand", "source", "demand", tags=frozenset({NATURAL_TAG})),
        make_edge("demand_to_sink", "demand", "sink", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )


@pytest.fixture
def system_with_terminal_demand():
    """Source -> Demand (terminal on natural path)."""
    return make_system(
        make_source("source"),
        make_demand("demand"),
        make_sink("sink"),
        make_edge("source_to_demand", "source", "demand", tags=frozenset({NATURAL_TAG})),
        make_edge("demand_to_sink", "demand", "sink", tags=frozenset({"canal"})),
        validate=False,
    )


@pytest.fixture
def system_with_passthrough():
    """Source -> PassThrough -> Sink (all natural)."""
    return make_system(
        make_source("source"),
        make_passthrough("passthrough", capacity=500.0),
        make_sink("sink"),
        make_edge("source_to_pt", "source", "passthrough", tags=frozenset({NATURAL_TAG})),
        make_edge("pt_to_sink", "passthrough", "sink", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )


@pytest.fixture
def system_with_splitter_single_natural():
    """Splitter with single natural downstream edge."""
    return make_system(
        make_source("source"),
        make_splitter("splitter"),
        make_sink("sink"),
        make_demand("demand"),
        make_edge("source_to_splitter", "source", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_sink", "splitter", "sink", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_demand", "splitter", "demand", tags=frozenset({"canal"})),
        validate=False,
    )


@pytest.fixture
def system_with_natural_splitter():
    """Splitter with NaturalRiverSplitter and multiple natural downstream edges."""
    return make_system(
        make_source("source"),
        make_splitter("splitter", split_policy=NaturalRiverSplitter(ratios={"sink_a": 0.6, "sink_b": 0.4})),
        make_sink("sink_a"),
        make_sink("sink_b"),
        make_edge("source_to_splitter", "source", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_sink_a", "splitter", "sink_a", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_sink_b", "splitter", "sink_b", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )


@pytest.fixture
def system_with_ambiguous_splitter():
    """Splitter with multiple natural downstream but no NaturalRiverSplitter."""
    return make_system(
        make_source("source"),
        make_splitter("splitter", split_policy=EvenSplit()),
        make_sink("sink_a"),
        make_sink("sink_b"),
        make_edge("source_to_splitter", "source", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_sink_a", "splitter", "sink_a", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_sink_b", "splitter", "sink_b", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )
