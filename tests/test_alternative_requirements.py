"""alternative_acceptance : CompleteSupportedAlternatives → ExactFinalizationAssertions.

U11/U6/U7: real source calculations, full calendars and matched physical rechecks.
All numerical witnesses are exact rational synthetic scenarios, not national policy.
"""

from dataclasses import replace

import pytest

from examples.alternative_requirements import (
    finalize_direct_floors,
    supported_presumptive,
    supported_top,
    supported_transfer,
)
from fishy.daily_patterns import PatternMethod
from fishy.design_conditions import DesignClass
from fishy.evidence import CheckFinding
from fishy.natural_routing import NaturalRoute
from fishy.quantities import Flow
from fishy.requirement_construction import StudySource
from fishy.requirement_family import FloorSeries, ReconstructionNeed


@pytest.fixture(scope="module")
def top():
    return supported_top()


@pytest.fixture(scope="module")
def transfer():
    return supported_transfer()


def test_u11_complete_supported_top_preserves_pulse_above_baseline_median(top):
    result = top.finalize()
    assert result.checks.finding is CheckFinding.PASS
    assert result.requirement is not None and result.floor is not None
    assert len(result.physical) == len(result.member_physical) == 4 * 365
    assert result.duration == result.member_duration == ()
    assert result.floor.sample.value == Flow(12)
    assert result.invariant is not None and not result.invariant.crossings
    source = top.construction.source
    assert isinstance(source, StudySource)
    assert source.hydrology.result.candidate is not None
    assert all(s.value == Flow(10) for s in source.hydrology.result.candidate.classes[0].samples)
    for design in DesignClass:
        samples = result.requirement.samples(design)
        assert len(samples) == 365
        assert all(
            s.value == Flow(20 if (s.interval.start.month, s.interval.start.day) == (6, 1) else 12) for s in samples
        )
    assert all(
        p.result.study is not None and p.result.study.supported_flow == p.result.sample.value for p in result.physical
    )
    assert result.route_failure is None


def test_u11_missing_actual_study_relation_declines_complete_regime(top):
    source = top.construction.source
    assert isinstance(source, StudySource)
    first = source.studies[0]
    broken = replace(first, components=(replace(first.components[0], relations=()),))
    changed = replace(source, studies=(broken, *source.studies[1:]))
    result = replace(top, construction=replace(top.construction, source=changed)).finalize()
    assert result.checks.finding is not CheckFinding.PASS
    assert result.requirement is None and result.floor is None
    assert result.route_failure is not None and result.route_failure.route is NaturalRoute.TOP


def test_u6_qualified_transfer_rechecks_local_quality_before_floor_without_baseline_gate(transfer):
    result = transfer.finalize()
    assert result.checks.finding is CheckFinding.PASS
    assert result.requirement is not None and result.floor is not None
    source = transfer.construction.source
    assert source.candidate is not None
    assert [s.value for s in source.candidate.classes[0].samples[:2]] == [Flow(3), Flow(5)]
    assert [s.value for s in source.donor.classes[0].samples[:2]] == [Flow(2), Flow(4)]
    assert all(s.value == Flow(6) for c in result.requirement.classes for s in c.samples)
    assert result.floor.sample.value == Flow(6)
    assert result.duration == result.member_duration == ()
    assert len(result.physical) == len(result.member_physical) == 4 * 365
    assert all(p.result.quality is not None for p in result.physical)
    assert result.invariant is not None and result.invariant.check.finding is CheckFinding.PASS
    assert result.selection.specification.reconstruction is ReconstructionNeed.NOT_REQUIRED
    assert all(p.method is PatternMethod.IMPORTED for p in source.recipient_natural)


def test_u6_missing_one_final_quality_day_is_not_complete_acceptance(transfer):
    result = replace(transfer, physical=transfer.physical[1:]).finalize()
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.requirement is None and result.floor is None
    assert result.route_failure is not None and result.route_failure.route is NaturalRoute.TRANSFER


def test_u6_tampered_transfer_output_does_not_override_recomputed_source(transfer):
    source = transfer.construction.source
    assert source.candidate is not None
    first = source.candidate.classes[0]
    wrong = replace(first, samples=(replace(first.samples[0], value=Flow(4)), *first.samples[1:]))
    changed = replace(source, candidate=replace(source.candidate, classes=(wrong, *source.candidate.classes[1:])))
    result = replace(transfer, construction=replace(transfer.construction, source=changed)).finalize()
    assert result.checks.finding is CheckFinding.FAIL
    assert result.requirement is None and result.floor is None
    assert any(
        c.check_id.endswith("source_result_binding") and c.finding is CheckFinding.FAIL for c in result.checks.checks
    )


def test_u7_presumptive_actual_sizing_keeps_active_quality_in_final_floors_only():
    base, result = supported_presumptive()
    assert base.checks.finding is CheckFinding.PASS
    assert [s.value for s in base.samples[:2]] == [Flow("1.2"), Flow(2)]
    assert result.checks.finding is CheckFinding.PASS
    assert isinstance(result.selection.supplied, FloorSeries)
    assert len(result.floors) == 365
    assert all(f.sample.value == Flow(6) for f in result.floors)
    assert not hasattr(result, "requirement") and not hasattr(result, "obligation")


def entry_final():
    from test_graduated_entry import curve, screen, statistic

    from examples.requirement_chain import TARGET, samples
    from fishy.graduated_entry import EntryStatus, evaluate_graduated_entry

    base = evaluate_graduated_entry(statistic(5), curve(), screen())
    assert base.status is EntryStatus.FLOOR_ONLY and base.floor == Flow(4)
    # The accepted observed daily statistic sizes a scalar floor, explicitly applied
    # to this declared complete period. It does not fabricate ecological classes.
    subject = base.statistic.product
    assert subject.location is not None
    daily = tuple(
        replace(s, value=base.floor, location=subject.location, provenance=subject.provenance)
        for s in samples(TARGET, 4, "entry-direct")
    )
    from examples.study_requirements import NATURAL
    from fishy.evidence import Check
    from fishy.floor_construction import EntryFloorSource
    from fishy.natural_routing import Availability, ScientificRequirement, TierEvidence
    from fishy.requirement_construction import NaturalRouteInputs

    tier = TierEvidence(
        NaturalRoute.ENTRY,
        subject.location,
        "entry-direct-v1",
        Availability.AVAILABLE,
        Availability.AVAILABLE,
        Check("priority_not_required", CheckFinding.PASS),
        ("daily_low_flow",),
        (ScientificRequirement("daily_low_flow", subject, base.statistic.assessment),),
        (),
        (),
        "explicit accepted direct statistic; no reconstruction needed",
    )
    source = EntryFloorSource(base, NaturalRouteInputs(subject.location, NATURAL, (tier,)))
    result = finalize_direct_floors(daily, "graduated_entry", source)
    return result


def test_u7_observed_entry_sizing_keeps_active_quality_in_final_floors_only():
    result = entry_final()
    assert result.checks.finding is CheckFinding.PASS
    assert isinstance(result.selection.supplied, FloorSeries)
    assert len(result.floors) == 365
    assert all(f.sample.value == Flow(6) for f in result.floors)
    assert not hasattr(result, "requirement") and not hasattr(result, "obligation")


def test_u7_top_floor_crossing_declines_without_lowering_floor_or_lifting_other_classes():
    result = supported_top(dry_flow=13).finalize()
    assert result.checks.finding is CheckFinding.FAIL
    assert result.invariant is not None
    assert result.invariant.candidate == Flow(13)
    assert result.invariant.crossings
    assert all(c.requirement == Flow(12) for c in result.invariant.crossings)
    assert result.requirement is None and result.floor is None
    assert all(c.checks.finding is CheckFinding.PASS for c in result.constructions)
    assert all(p.result.checks.finding is CheckFinding.PASS for p in result.physical)
    assert result.route_failure is not None and result.route_failure.route is NaturalRoute.TOP


@pytest.mark.parametrize("name", ["top", "transfer"])
def test_complete_source_cannot_finalize_without_bound_natural_route(name, request):
    inputs = request.getfixturevalue(name)
    result = replace(inputs, construction=replace(inputs.construction, route=None)).finalize()
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.requirement is None and result.floor is None
    assert any(
        c.check_id.endswith("route_selection") and c.finding is CheckFinding.UNKNOWN for c in result.checks.checks
    )


@pytest.fixture(scope="module", params=["entry", "presumptive"])
def direct_floor(request):
    return entry_final() if request.param == "entry" else supported_presumptive()[1]


def repeat_floor_finalization(result, constructions):
    from fishy.requirement_checks import FinalCondition
    from fishy.requirement_finalization import finalize_floors

    return finalize_floors(
        result.selection,
        (FinalCondition.QUALITY,),
        result.physical,
        version="rechecked-direct-final-v1",
        constructions=constructions,
        member_physical=result.member_physical,
    )


def test_direct_floor_missing_actual_source_cannot_publish(direct_floor):
    result = repeat_floor_finalization(direct_floor, ())
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert not result.floors


def test_direct_floor_natural_source_cannot_publish_on_artificial_classification(direct_floor):
    from fishy.spatial import Origin

    original = direct_floor.constructions[0].construction
    source = original.components[0].source
    changed = replace(
        source,
        route=replace(source.route, classification=replace(source.route.classification, origin=Origin.ARTIFICIAL)),
    )
    construction = replace(original, components=tuple(replace(c, source=changed) for c in original.components))
    result = repeat_floor_finalization(direct_floor, (construction,))
    assert result.checks.finding is CheckFinding.FAIL
    assert not result.floors


def test_direct_floor_tampered_sizing_result_cannot_publish(direct_floor):
    from fishy.floor_construction import EntryFloorSource

    original = direct_floor.constructions[0].construction
    source = original.components[0].source
    if isinstance(source, EntryFloorSource):
        changed = replace(source, result=replace(source.result, floor=Flow(5)))
    else:
        samples = source.result.samples
        changed = replace(
            source, result=replace(source.result, samples=(replace(samples[0], value=Flow(5)), *samples[1:]))
        )
    construction = replace(original, components=tuple(replace(c, source=changed) for c in original.components))
    result = repeat_floor_finalization(direct_floor, (construction,))
    assert result.checks.finding is CheckFinding.FAIL
    assert not result.floors


def test_direct_floor_missing_retained_member_physics_cannot_publish(direct_floor):
    from fishy.requirement_checks import FinalCondition
    from fishy.requirement_finalization import finalize_floors

    result = finalize_floors(
        direct_floor.selection,
        (FinalCondition.QUALITY,),
        direct_floor.physical,
        version="missing-member-physics",
        constructions=tuple(c.construction for c in direct_floor.constructions),
        member_physical=direct_floor.member_physical[1:],
    )
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert not result.floors


def test_direct_floor_missing_sizing_input_remains_unknown_not_computed_failure(direct_floor):
    from fishy.floor_construction import EntryFloorSource
    from fishy.graduated_entry import evaluate_graduated_entry
    from fishy.presumptive_floor import presumptive_floor

    original = direct_floor.constructions[0].construction
    source = original.components[0].source
    if isinstance(source, EntryFloorSource):
        incomplete = evaluate_graduated_entry(source.result.statistic, None, source.result.screen)
    else:
        incomplete = presumptive_floor(source.result.reference, None)
    changed = replace(source, result=incomplete)
    construction = replace(original, components=tuple(replace(c, source=changed) for c in original.components))
    result = repeat_floor_finalization(direct_floor, (construction,))
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert not result.floors
