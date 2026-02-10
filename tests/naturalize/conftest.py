"""Test fixtures for naturalize module tests."""

import pytest
from taqsim.testing import (
    EvenSplit,
    make_demand,
    make_edge,
    make_passthrough,
    make_reach,
    make_sink,
    make_source,
    make_splitter,
    make_storage,
    make_system,
)

from fishy.naturalize import NATURAL_SPLIT_RATIOS, NATURAL_TAG, NaturalRiverSplitter


@pytest.fixture
def simple_linear_system():
    """Source -> Reach -> Storage -> Sink (all natural)."""
    return make_system(
        make_source("source", n_steps=2),
        make_reach("reach"),
        make_storage("storage"),
        make_sink("sink"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_storage", "reach", "storage", tags=frozenset({NATURAL_TAG})),
        make_edge("storage_to_sink", "storage", "sink", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )


@pytest.fixture
def system_with_side_branch():
    """Source -> Reach -> Storage -> Sink (natural) + Storage -> Demand (canal)."""
    return make_system(
        make_source("source"),
        make_reach("reach"),
        make_storage("storage"),
        make_sink("sink"),
        make_demand("demand"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_storage", "reach", "storage", tags=frozenset({NATURAL_TAG})),
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
    """Source -> Reach -> Demand -> Sink (all natural)."""
    return make_system(
        make_source("source"),
        make_reach("reach"),
        make_demand("demand"),
        make_sink("sink"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_demand", "reach", "demand", tags=frozenset({NATURAL_TAG})),
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
    """Source -> Reach -> PassThrough -> Sink (all natural)."""
    return make_system(
        make_source("source"),
        make_reach("reach"),
        make_passthrough("passthrough", capacity=500.0),
        make_sink("sink"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_pt", "reach", "passthrough", tags=frozenset({NATURAL_TAG})),
        make_edge("pt_to_sink", "passthrough", "sink", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )


@pytest.fixture
def system_with_splitter_single_natural():
    """Splitter with single natural downstream edge, Reach on path."""
    return make_system(
        make_source("source"),
        make_reach("reach"),
        make_splitter("splitter"),
        make_sink("sink"),
        make_demand("demand"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_splitter", "reach", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_sink", "splitter", "sink", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_demand", "splitter", "demand", tags=frozenset({"canal"})),
        validate=False,
    )


@pytest.fixture
def system_with_natural_splitter():
    """Splitter with NaturalRiverSplitter, Reach on path."""
    return make_system(
        make_source("source"),
        make_reach("reach"),
        make_splitter("splitter", split_policy=NaturalRiverSplitter(ratios={"sink_a": 0.6, "sink_b": 0.4})),
        make_sink("sink_a"),
        make_sink("sink_b"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_splitter", "reach", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_sink_a", "splitter", "sink_a", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_sink_b", "splitter", "sink_b", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )


@pytest.fixture
def system_with_ambiguous_splitter():
    """Splitter with multiple natural downstream but no NaturalRiverSplitter, Reach on path."""
    return make_system(
        make_source("source"),
        make_reach("reach"),
        make_splitter("splitter", split_policy=EvenSplit()),
        make_sink("sink_a"),
        make_sink("sink_b"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_splitter", "reach", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_sink_a", "splitter", "sink_a", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_sink_b", "splitter", "sink_b", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )


@pytest.fixture
def system_with_reach_on_natural_path():
    """Source -> Reach -> Sink (all natural)."""
    return make_system(
        make_source("source", n_steps=2),
        make_reach("reach"),
        make_sink("sink"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_sink", "reach", "sink", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )


@pytest.fixture
def system_with_reach_off_natural_path():
    """Natural path: Source -> Reach -> Sink. Non-natural branch has another Reach as canal."""
    return make_system(
        make_source("source", n_steps=2),
        make_reach("natural_reach"),
        make_reach("canal_reach"),
        make_sink("sink"),
        make_edge("source_to_reach", "source", "natural_reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_sink", "natural_reach", "sink", tags=frozenset({NATURAL_TAG})),
        make_edge("source_to_canal", "source", "canal_reach", tags=frozenset({"canal"})),
        validate=False,
    )


@pytest.fixture
def system_without_reach_on_natural_path():
    """Source -> Storage -> Sink (all natural, no Reach). Should raise NoNaturalReachError."""
    return make_system(
        make_source("source"),
        make_storage("storage"),
        make_sink("sink"),
        make_edge("source_to_storage", "source", "storage", tags=frozenset({NATURAL_TAG})),
        make_edge("storage_to_sink", "storage", "sink", tags=frozenset({NATURAL_TAG})),
        validate=False,
    )


@pytest.fixture
def system_with_mixed_splitter():
    """Splitter with 2 natural + 1 non-natural downstream, NATURAL_SPLIT_RATIOS metadata."""
    return make_system(
        make_source("source"),
        make_reach("reach"),
        make_splitter(
            "splitter",
            split_policy=EvenSplit(),
            metadata={NATURAL_SPLIT_RATIOS: {"reach_a": 0.6, "reach_b": 0.4}},
        ),
        make_reach("reach_a"),
        make_reach("reach_b"),
        make_sink("sink_a"),
        make_sink("sink_b"),
        make_demand("demand"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_splitter", "reach", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_reach_a", "splitter", "reach_a", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_reach_b", "splitter", "reach_b", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_a_to_sink_a", "reach_a", "sink_a", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_b_to_sink_b", "reach_b", "sink_b", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_demand", "splitter", "demand", tags=frozenset({"canal"})),
        validate=False,
    )


@pytest.fixture
def system_with_mixed_splitter_bad_sum():
    """Mixed splitter with ratios that don't sum to 1.0."""
    return make_system(
        make_source("source"),
        make_reach("reach"),
        make_splitter(
            "splitter",
            split_policy=EvenSplit(),
            metadata={NATURAL_SPLIT_RATIOS: {"reach_a": 0.4, "reach_b": 0.3}},
        ),
        make_reach("reach_a"),
        make_reach("reach_b"),
        make_sink("sink_a"),
        make_sink("sink_b"),
        make_demand("demand"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_splitter", "reach", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_reach_a", "splitter", "reach_a", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_reach_b", "splitter", "reach_b", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_a_to_sink_a", "reach_a", "sink_a", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_b_to_sink_b", "reach_b", "sink_b", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_demand", "splitter", "demand", tags=frozenset({"canal"})),
        validate=False,
    )


@pytest.fixture
def system_with_mixed_splitter_wrong_targets():
    """Mixed splitter with ratio keys that don't match downstream targets."""
    return make_system(
        make_source("source"),
        make_reach("reach"),
        make_splitter(
            "splitter",
            split_policy=EvenSplit(),
            metadata={NATURAL_SPLIT_RATIOS: {"wrong_a": 0.6, "wrong_b": 0.4}},
        ),
        make_reach("reach_a"),
        make_reach("reach_b"),
        make_sink("sink_a"),
        make_sink("sink_b"),
        make_demand("demand"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_splitter", "reach", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_reach_a", "splitter", "reach_a", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_reach_b", "splitter", "reach_b", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_a_to_sink_a", "reach_a", "sink_a", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_b_to_sink_b", "reach_b", "sink_b", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_demand", "splitter", "demand", tags=frozenset({"canal"})),
        validate=False,
    )


@pytest.fixture
def system_with_mixed_splitter_no_metadata():
    """Mixed splitter without NATURAL_SPLIT_RATIOS metadata — should raise AmbiguousSplitError."""
    return make_system(
        make_source("source"),
        make_reach("reach"),
        make_splitter("splitter", split_policy=EvenSplit()),
        make_reach("reach_a"),
        make_reach("reach_b"),
        make_sink("sink_a"),
        make_sink("sink_b"),
        make_demand("demand"),
        make_edge("source_to_reach", "source", "reach", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_to_splitter", "reach", "splitter", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_reach_a", "splitter", "reach_a", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_reach_b", "splitter", "reach_b", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_a_to_sink_a", "reach_a", "sink_a", tags=frozenset({NATURAL_TAG})),
        make_edge("reach_b_to_sink_b", "reach_b", "sink_b", tags=frozenset({NATURAL_TAG})),
        make_edge("splitter_to_demand", "splitter", "demand", tags=frozenset({"canal"})),
        validate=False,
    )
