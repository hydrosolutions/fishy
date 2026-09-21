"""Source §6.1 spatial partitions, missing-area branches and reach boundaries."""

from dataclasses import replace
from fractions import Fraction

import pytest
from test_hydrological_condition import context, result

from fishy.catchment_conditions import (
    BoundaryAction,
    CatchmentNode,
    DrainageNetwork,
    IntermediateCondition,
    InterventionInfluence,
    ReachBoundaryInputs,
    ReachFeature,
    delimit_reach,
    propagate_indicator,
)
from fishy.evidence import Completeness
from fishy.hydrological_condition import AssessmentState, Indicator
from fishy.quantities import Area, Flow, Volume

MEAN_FLOW = Indicator.MEAN_FLOW


def node(name, area, upstream=(), cls=None, *, affected=(), local=IntermediateCondition.UNAFFECTED):
    ctx = context(name)
    results = () if cls is None else (result(MEAN_FLOW, cls, ctx),)
    return CatchmentNode(
        name, ctx, Area(area, "km2"), upstream, affected, results, local, "prepared synthetic topology"
    )


@pytest.mark.parametrize(
    "missing,expected",
    [("14.9", 2), ("15", None), ("15.1", None), ("14.999999999999999999", 2), ("15.000000000000000001", None)],
)
def test_unrounded_missing_area_threshold(missing, expected):
    absent = node("unknown", missing, affected=(MEAN_FLOW,))
    known = node("known", 50, cls=3, affected=(MEAN_FLOW,))
    outlet = node("outlet", 100, ("unknown", "known"))
    network = DrainageNetwork((absent, known, outlet), "v1", "survey")
    output = propagate_indicator(network, "outlet", MEAN_FLOW)
    assert output.result.classification == expected
    assert output.result.coverage is Completeness.INCOMPLETE
    assert output.unassessed_area == Area(missing, "km2")
    if expected:
        assert output.weighted_class == (Fraction(150) + 50 - Fraction(missing)) / (100 - Fraction(missing))
    elif missing == "15":
        assert "equality unresolved" in output.result.reasons[0]


def test_nearest_upstream_per_indicator_and_no_nested_double_count():
    far = node("far", 10, cls=5, affected=(MEAN_FLOW,))
    near = node("near", 20, ("far",), cls=2, affected=(MEAN_FLOW,))
    tributary = node("tributary", 20, cls=4, affected=(MEAN_FLOW,))
    outlet = node("outlet", 50, ("near", "tributary"))
    network = DrainageNetwork((far, near, tributary, outlet), "v1", "disjoint tributaries")
    output = propagate_indicator(network, "outlet", MEAN_FLOW)
    assert output.weighted_class == Fraction(13, 5)
    assert output.result.classification == 3
    assert {p.node.identifier for p in output.contributions} == {"near", "tributary", "outlet"}
    # The near intervention does not mask another indicator assessed farther upstream.
    far2 = replace(
        far,
        affected_indicators=(MEAN_FLOW, Indicator.FLOOD_FREQUENCY),
        results=(*far.results, result(Indicator.FLOOD_FREQUENCY, 5, far.context)),
    )
    network = replace(network, nodes=(far2, near, tributary, outlet))
    flood = propagate_indicator(network, "outlet", Indicator.FLOOD_FREQUENCY)
    assert flood.weighted_class == Fraction(9, 5)


def test_half_up_rounding_not_bankers_rounding_and_lake_not_classified():
    a = node("a", 10, cls=4, affected=(MEAN_FLOW,))
    b = node("b", 20, ("a",))
    network = DrainageNetwork((a, b), "v1", "survey")
    output = propagate_indicator(network, "b", MEAN_FLOW)
    assert output.weighted_class == Fraction(5, 2)
    assert output.result.classification == 3
    lake = replace(b, feature=ReachFeature.LAKE)
    output = propagate_indicator(replace(network, nodes=(a, lake)), "b", MEAN_FLOW)
    assert output.result.state is AssessmentState.NOT_APPLICABLE
    assert output.result.classification is None


def test_topology_and_area_refusals():
    a = node("a", 10)
    with pytest.raises(ValueError, match="exceed"):
        DrainageNetwork((a, node("b", 9, ("a",))), "v1", "survey")
    with pytest.raises(ValueError, match="cyclic"):
        DrainageNetwork((replace(a, upstream=("b",)), node("b", 10, ("a",))), "v1", "survey")
    with pytest.raises(ValueError, match="overlapping"):
        DrainageNetwork((a, node("b", 20, ("a",)), node("c", 30, ("a", "b"))), "v1", "survey")
    with pytest.raises(ValueError, match="undeclared"):
        DrainageNetwork((replace(a, upstream=("missing",)),), "v1", "survey")
    with pytest.raises(ValueError, match="positive"):
        node("bad", 0)


def boundary(**changes):
    base = ReachBoundaryInputs(
        context(),
        Area(100, "km2"),
        Area(115, "km2"),
        Flow(1),
        Flow(0),
        InterventionInfluence.NONE,
        InterventionInfluence.NONE,
        None,
        (),
        "prepared site evidence",
    )
    return replace(base, **changes)


def test_all_reach_delimitation_thresholds():
    assert delimit_reach(boundary()).action is BoundaryAction.CONTINUE
    assert delimit_reach(boundary(current_area=Area("115.0000001", "km2"))).action is BoundaryAction.NEW_REACH
    assert delimit_reach(boundary(groundwater_gain=Flow(1))).action is BoundaryAction.NEW_REACH
    assert delimit_reach(boundary(intervention=InterventionInfluence.SIGNIFICANT)).action is BoundaryAction.NEW_REACH
    assert delimit_reach(boundary(tributary=InterventionInfluence.SIGNIFICANT)).action is BoundaryAction.NEW_REACH
    assert delimit_reach(boundary(lake_volume=Volume(3600))).action is BoundaryAction.LAKE_EXCLUDED
    assert delimit_reach(boundary(lake_volume=Volume(3601))).action is BoundaryAction.NEW_REACH
    assert delimit_reach(boundary(lake_volume=Volume(10800))).action is BoundaryAction.NEW_REACH
    assert delimit_reach(boundary(lake_volume=Volume(10801))).action is BoundaryAction.END_INFLUENCE
    all_high = tuple(result(i, 1) for i in Indicator)
    assert delimit_reach(boundary(upstream_classes=all_high)).action is BoundaryAction.END_INFLUENCE
    assert delimit_reach(boundary(upstream_classes=all_high[:-1])).action is BoundaryAction.CONTINUE
    assert (
        delimit_reach(boundary(upstream_classes=all_high, intervention=InterventionInfluence.SIGNIFICANT)).action
        is BoundaryAction.NEW_REACH
    )


def test_boundary_refuses_foreign_scenario_results():
    foreign = replace(context(), provenance=replace(context().provenance, scenario="other"))
    wrong = tuple(result(i, 1, foreign) for i in Indicator)
    with pytest.raises(ValueError, match="scenario"):
        boundary(upstream_classes=wrong)


def test_source_lake_end_can_feed_downstream_river_without_classifying_lake():
    from fishy.catchment_conditions import screen_ended_influence

    ended = delimit_reach(boundary(lake_volume=Volume(10801)))
    ctx = context("downstream")
    rs = screen_ended_influence(ended, ctx)
    assert all(r.classification == 1 and r.state is AssessmentState.SCREENED for r in rs)
    with pytest.raises(ValueError, match="end of influence"):
        screen_ended_influence(delimit_reach(boundary(lake_volume=Volume(10800))), ctx)
    downstream = CatchmentNode(
        "downstream",
        ctx,
        Area(200, "km2"),
        (),
        tuple(Indicator),
        rs,
        IntermediateCondition.UNAFFECTED,
        "source lake reset",
    )
    output = propagate_indicator(DrainageNetwork((downstream,), "v1", "survey"), "downstream", MEAN_FLOW)
    assert output.result.classification == 1
    assert output.contributions[0].point_result is not None
    assert output.contributions[0].point_result.inputs == (ended,)


@pytest.mark.parametrize("partial_indicators", [tuple(Indicator), (Indicator.MEAN_FLOW,)])
def test_class_based_end_preserves_each_upstream_indicator_coverage(partial_indicators):
    from fishy.catchment_conditions import screen_ended_influence
    from fishy.hydrological_condition import assess_hydrology

    upstream = tuple(
        replace(result(i, 1), coverage=Completeness.INCOMPLETE) if i in partial_indicators else result(i, 1)
        for i in Indicator
    )
    ended = delimit_reach(boundary(upstream_classes=upstream))
    downstream = context("downstream")
    screened = screen_ended_influence(ended, downstream)
    assert tuple(r.coverage for r in screened) == tuple(r.coverage for r in upstream)
    assert assess_hydrology(downstream, screened).completeness is Completeness.INCOMPLETE


def test_lake_end_uses_independent_volume_criterion_not_upstream_class_coverage():
    from fishy.catchment_conditions import screen_ended_influence
    from fishy.hydrological_condition import assess_hydrology

    upstream = tuple(replace(result(i, 1), coverage=Completeness.INCOMPLETE) for i in Indicator)
    ended = delimit_reach(boundary(lake_volume=Volume(10801), upstream_classes=upstream))
    downstream = context("downstream")
    screened = screen_ended_influence(ended, downstream)
    assert assess_hydrology(downstream, screened).completeness is Completeness.COMPLETE
    assert all(r.inputs == (ended,) for r in screened)
