"""Reference, inventory and computed evidence remain separate through composition."""

from dataclasses import replace

import pytest
from test_hydrological_condition import context, result

from fishy.evidence import Completeness
from fishy.flow_interventions import (
    LandscapeBasis,
    ReferenceConditions,
    ReferenceProfile,
    ReferenceSuitability,
    WaterBodyKind,
)
from fishy.hydrological_assessment import InventorySurvey, assess_river_hydrology
from fishy.hydrological_condition import Indicator


def reference(kind=WaterBodyKind.RIVER):
    return ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        kind,
        ReferenceSuitability.SUPPORTED,
        context().provenance,
        "supplied current-landscape reference study",
    )


def test_known_empty_inventory_distinct_unknown_inventory():
    known = InventorySurvey((), (), Completeness.COMPLETE, "complete field inventory", "v1")
    output = assess_river_hydrology(context(), reference(), known, ())
    assert output.condition.classification == 1
    assert output.condition.completeness is Completeness.COMPLETE
    unknown = replace(known, coverage=Completeness.INCOMPLETE)
    output = assess_river_hydrology(context(), reference(), unknown, ())
    assert output.condition.classification is None
    assert output.condition.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize("kind", [WaterBodyKind.CANAL, WaterBodyKind.DRAIN, WaterBodyKind.LAKE])
def test_artificial_and_lake_references_cannot_acquire_river_class(kind):
    calculations = tuple(result(i, 1) for i in Indicator)
    inventory = InventorySurvey((), (), Completeness.COMPLETE, "survey", "v1")
    output = assess_river_hydrology(context(), reference(kind), inventory, calculations)
    assert output.condition.classification is None
    assert output.calculations == calculations


def test_incomplete_inventory_not_hidden_by_nine_computations():
    calculations = tuple(result(i, 1) for i in Indicator)
    inventory = InventorySurvey((), (), Completeness.INCOMPLETE, "partial survey", "v1")
    output = assess_river_hydrology(context(), reference(), inventory, calculations)
    assert output.condition.classification == 1
    assert output.condition.completeness is Completeness.INCOMPLETE
    naturalised = replace(reference(), landscape=LandscapeBasis.STRUCTURAL_NATURALISATION)
    assert assess_river_hydrology(context(), naturalised, inventory, calculations).condition.classification is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenario", "foreign"),
        ("reference_member", "foreign"),
        ("data_version", "stale"),
        ("configuration_version", "stale"),
    ],
)
def test_unrelated_reference_cannot_authorise_composed_river_class(field, value):
    inventory = InventorySurvey((), (), Completeness.COMPLETE, "survey", "v1")
    unrelated = replace(reference(), provenance=replace(reference().provenance, **{field: value}))
    output = assess_river_hydrology(context(), unrelated, inventory, tuple(result(i, 1) for i in Indicator))
    assert output.condition.classification is None
    assert len(output.calculations) == 9


@pytest.mark.parametrize("other_local", [(), ("intake",)])
def test_local_impoundment_cannot_acquire_river_class_from_calculations(other_local):
    from fishy.flow_interventions import (
        Intervention,
        InterventionType,
        ReferenceDischarges,
        SelectionAction,
        SiteSelection,
        screen_intervention,
    )
    from fishy.quantities import Area, Flow

    ctx = context()
    impounded = Intervention("impounded reach", InterventionType.IMPOUNDMENT, ctx, "river", Area(10, "km2"))
    discharges = ReferenceDischarges(Flow(1), None, ctx.provenance)
    screens = (screen_intervention(impounded, discharges),)
    if other_local:
        intake = Intervention("intake", InterventionType.A1, ctx, "river", Area(10, "km2"))
        screens += (screen_intervention(intake, discharges),)
    inventory = InventorySurvey(screens, (), Completeness.COMPLETE, "survey", "1")
    calculations = tuple(result(i, 1, ctx) for i in Indicator)
    site = tuple(
        SiteSelection(i, SelectionAction.INCLUDE, "supplied additional calculation", ctx.provenance) for i in Indicator
    )
    output = assess_river_hydrology(ctx, reference(), inventory, calculations, site)
    assert output.condition.classification is None
    assert output.calculations == calculations
    assert all(r.classification is None for r in output.condition.indicators)


def test_upstream_impoundment_does_not_exclude_receiving_river_computation():
    from fishy.flow_interventions import Intervention, InterventionType, ReferenceDischarges, screen_intervention
    from fishy.quantities import Area, Flow

    upstream = context("upstream reservoir")
    impounded = Intervention("reservoir", InterventionType.IMPOUNDMENT, upstream, "river", Area(10, "km2"))
    screen = screen_intervention(impounded, ReferenceDischarges(Flow(1), None, upstream.provenance))
    inventory = InventorySurvey((), (screen,), Completeness.COMPLETE, "survey", "1")
    calculations = tuple(result(i, 1) for i in Indicator)
    output = assess_river_hydrology(context(), reference(), inventory, calculations)
    assert output.condition.classification == 1
