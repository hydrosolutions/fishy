"""conveyance_floor : CompletePotentialFloorSources × DailyQualityUplift → FinalFloors.

365-day public-boundary regression: original service5, quality-adjusted floor10.
Supported surplus is not re-sized to5. An accepted domain ending8 cannot certify10.
"""

from dataclasses import replace

import pytest
from test_conveyance_conditions import service_request

from examples.alternative_requirements import family_basis, local_quality, single_selection
from examples.requirement_chain import TARGET, samples
from examples.study_requirements import NEED, POTENTIAL
from fishy.evidence import CheckFinding, ReferenceKind
from fishy.floor_construction import FloorComponent, FloorConstruction, PotentialFloorSource
from fishy.potential_requirements import Applicability, PotentialFloorResult, PotentialRoute, PotentialStudy
from fishy.quality_activation import QualityRoute
from fishy.quantities import Flow
from fishy.requirement_checks import FinalCondition, assess_requirement, sample_subject
from fishy.requirement_composition import compose_requirement
from fishy.requirement_family import FloorSeries, ReconstructionNeed, assess_selected_family
from fishy.requirement_finalization import FloorMemberAssessment, finalize_floors
from fishy.study_requirements import StudyScope


@pytest.mark.parametrize("upper,expected", ((8, CheckFinding.UNKNOWN), (12, CheckFinding.PASS)))
def test_complete_potential_service_floor_rechecks_actual_final_relation_domain(upper, expected):
    rows, physical, finals = [], [], []
    missing = PotentialStudy(
        Applicability.UNRESOLVED, "habitat/hydraulic study not supplied; service route only", None, ()
    )
    for raw in samples(TARGET, 5, "conveyance-final", "R"):
        base = replace(raw, provenance=replace(raw.provenance, reference_kind=ReferenceKind.MANAGED))
        _, request = service_request(base, upper=upper)
        p = base.provenance
        scope = StudyScope(
            sample_subject(base),
            base.location,
            base.interval,
            p.scenario,
            p.reference_member,
            "sizing",
            "whole-year daily service",
        )
        source = PotentialFloorSource(scope, POTENTIAL, missing, missing, request, NEED)
        quality = local_quality(base, route=QualityRoute.FLOOR_ONLY, background_mg_l=10)
        composition = compose_requirement(base, p, quality=quality)
        final = composition.candidate
        assert final is not None and final.value == Flow(10)
        rows.append(FloorComponent(source, composition))
        finals.append(final)
        physical.append(assess_requirement(final, (FinalCondition.QUALITY,), quality=quality))
    series = FloorSeries(family_basis(finals[0], TARGET.interval, "potential_floor"), tuple(finals))
    original = single_selection(series)
    selection = assess_selected_family(
        original.members,
        series,
        replace(
            original.specification,
            reconstruction=ReconstructionNeed.NOT_REQUIRED,
            source="constructed service route; no natural reconstruction prerequisite",
        ),
    )
    member = selection.members[0].identifier
    result = finalize_floors(
        selection,
        (FinalCondition.QUALITY,),
        tuple(physical),
        version="service-final-v1",
        constructions=(FloorConstruction(member, tuple(rows)),),
        member_physical=tuple(FloorMemberAssessment(member, item) for item in physical),
    )
    assert len(finals) == len(physical) == 365
    for source in result.constructions[0].sources:
        assert isinstance(source, PotentialFloorResult)
        assert source.selected_route is PotentialRoute.CONVEYANCE and source.floor == Flow(5)
    assert result.checks.finding is expected
    if expected is CheckFinding.PASS:
        assert tuple(f.sample.value for f in result.floors) == (Flow(10),) * 365
    else:
        assert result.floors == ()
    assert len(result.conveyance_conditions) == 730
    assert all(c.source.flow == Flow(5) and c.local_flow == Flow(10) for c in result.conveyance_conditions)
    assert all(c.checks.finding is expected for c in result.conveyance_conditions)
