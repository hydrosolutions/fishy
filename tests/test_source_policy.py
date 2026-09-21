"""Actual source policy cannot drift behind common configuration labels."""

from dataclasses import replace
from fractions import Fraction

import pytest
from test_requirement_finalization import inputs

from fishy.design_conditions import DesignClass
from fishy.evidence import CheckFinding
from fishy.natural_baseline import AdvisorySpawning, ReachCoefficients, RiverRegulation, WinterProvision
from fishy.quality_activation import ActivationMode
from fishy.quantities import Flow
from fishy.source_policy import floor_policy_checks, source_policy_checks


@pytest.fixture(scope="module")
def sources():
    return tuple(c.source for c in inputs(ActivationMode.HYPOTHETICAL)[3])


def test_reference_members_and_scientific_data_are_not_policy(sources):
    assert sources[0].provenance != sources[1].provenance
    assert source_policy_checks(sources).finding is CheckFinding.PASS


@pytest.mark.parametrize("field", ("alpha", "winter", "spawning"))
def test_actual_baseline_coefficients_are_policy_even_with_same_version(sources, field):
    source = sources[0]
    calendar = source.result.inputs.patterns[0].calendar
    policy = {
        "alpha": ReachCoefficients(tuple((c, Fraction(1, 2)) for c in DesignClass), "qualified", "different policy"),
        "winter": WinterProvision(
            RiverRegulation.REGULATED_NATURAL, Flow(2), Fraction(1, 4), "different share", "supported reference"
        ),
        "spawning": AdvisorySpawning((Fraction(2),) * calendar.days, calendar, "different timing", "different policy"),
    }[field]
    changed = replace(source, result=replace(source.result, inputs=replace(source.result.inputs, **{field: policy})))
    assert changed.profile_version == source.profile_version
    assert source_policy_checks((source, changed)).finding is CheckFinding.FAIL


def test_actual_scientific_acceptance_threshold_is_not_just_profile_name(sources):
    source = sources[0]
    first, *rest = source.result.inputs.patterns
    assessment = first.magnitude_assessment
    assert assessment is not None
    record = replace(
        assessment.record, criteria=tuple(replace(c, limit=c.limit + 1) for c in assessment.record.criteria)
    )
    changed_pattern = replace(first, magnitude_assessment=replace(assessment, record=record))
    changed = replace(
        source, result=replace(source.result, inputs=replace(source.result.inputs, patterns=(changed_pattern, *rest)))
    )
    assert source_policy_checks((source, changed)).finding is CheckFinding.FAIL


def without_assessment(source):
    first, *rest = source.result.inputs.patterns
    return replace(
        source,
        result=replace(
            source.result,
            inputs=replace(
                source.result.inputs,
                patterns=(replace(first, magnitude_assessment=None, magnitude_evidence=None), *rest),
            ),
        ),
    )


def test_missing_scientific_assessment_is_unknown_not_policy_drift(sources):
    result = source_policy_checks((sources[0], without_assessment(sources[1])))
    assert result.finding is CheckFinding.UNKNOWN
    assert not any(c.finding is CheckFinding.FAIL for c in result.checks)


def test_known_alpha_drift_survives_missing_scientific_assessment(sources):
    missing = without_assessment(sources[1])
    changed = replace(
        missing,
        result=replace(
            missing.result,
            inputs=replace(
                missing.result.inputs,
                alpha=ReachCoefficients(
                    tuple((c, Fraction(1, 2)) for c in DesignClass), "qualified", "different policy"
                ),
            ),
        ),
    )
    result = source_policy_checks((sources[0], changed))
    assert result.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks)
    assert any(c.finding is CheckFinding.FAIL and "alpha" in c.check_id for c in result.checks)


@pytest.fixture(scope="module")
def floor_source():
    from examples.graduated_entry import supplied_entry
    from fishy.floor_construction import EntryFloorSource
    from fishy.graduated_entry import evaluate_graduated_entry

    route = inputs(ActivationMode.HYPOTHETICAL)[3][0].route
    assert route is not None
    return EntryFloorSource(evaluate_graduated_entry(*supplied_entry()), route)


@pytest.mark.parametrize("missing", ("curve", "screen"))
def test_missing_floor_component_is_unknown(floor_source, missing):
    changed = replace(floor_source, result=replace(floor_source.result, **{missing: None}))
    assert floor_policy_checks((floor_source, changed)).finding is CheckFinding.UNKNOWN


def test_changed_known_screen_survives_missing_curve(floor_source):
    screen = floor_source.result.screen
    assert screen is not None
    changed = replace(
        floor_source, result=replace(floor_source.result, curve=None, screen=replace(screen, minimum_input=Flow(200)))
    )
    result = floor_policy_checks((floor_source, changed))
    assert result.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks)
    assert any(c.finding is CheckFinding.FAIL and "screen" in c.check_id for c in result.checks)


def test_missing_presumptive_profile_is_unknown(sources, floor_source):
    from fishy.floor_construction import PresumptiveFloorSource
    from fishy.presumptive_floor import (
        PresumptiveProfile,
        SeasonalFraction,
        presumptive_floor,
        presumptive_reference_identity,
    )

    pattern = sources[0].result.inputs.patterns[0]
    profile = PresumptiveProfile(
        "test",
        "natural pattern",
        presumptive_reference_identity(pattern),
        (SeasonalFraction("year", 0, pattern.calendar.days, Fraction(1, 2)),),
        "hypothetical",
        "fixed",
    )
    source = PresumptiveFloorSource(presumptive_floor(pattern, profile), floor_source.route)
    missing = replace(source, result=replace(source.result, profile=None))
    assert floor_policy_checks((source, missing)).finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("left,right", ((1, 1.0), (0.0, -0.0)))
def test_equal_scientific_numeric_limits_are_same_policy(sources, left, right):
    source = sources[0]
    first, *rest = source.result.inputs.patterns
    assessment = first.magnitude_assessment
    assert assessment is not None

    def with_limit(value):
        record = replace(assessment.record, criteria=tuple(replace(c, limit=value) for c in assessment.record.criteria))
        pattern = replace(first, magnitude_assessment=replace(assessment, record=record))
        return replace(
            source, result=replace(source.result, inputs=replace(source.result.inputs, patterns=(pattern, *rest)))
        )

    assert source_policy_checks((with_limit(left), with_limit(right))).finding is CheckFinding.PASS


def test_unresolved_unused_habitat_does_not_gate_supported_hydraulic_policy():
    from datetime import date

    from examples.requirement_chain import TARGET, potential_study, provenance
    from examples.study_requirements import POTENTIAL
    from fishy.evidence import ReferenceKind
    from fishy.floor_construction import PotentialFloorSource, assess_floor_source
    from fishy.potential_requirements import Applicability, PotentialFloorResult, PotentialRoute, PotentialStudy
    from fishy.study_requirements import StudyNeed

    selected, relations, _, _ = potential_study(
        Flow(3),
        TARGET.interval,
        replace(provenance("potential"), reference_kind=ReferenceKind.MANAGED),
        "policy-hydraulic",
    )
    source = PotentialFloorSource(
        selected.scope,
        POTENTIAL,
        PotentialStudy(Applicability.UNRESOLVED, "habitat study pending", None, ()),
        PotentialStudy(Applicability.APPLICABLE, "supported hydraulic fallback", selected, relations),
        None,
        StudyNeed("remaining habitat study", "review owner", date(2027, 1, 1)),
    )
    result, _ = assess_floor_source(source)
    assert isinstance(result, PotentialFloorResult)
    assert result.selected_route is PotentialRoute.HYDRAULIC
    assert result.routes[0].checks.finding is CheckFinding.UNKNOWN
    assert floor_policy_checks((source,)).finding is CheckFinding.PASS


@pytest.fixture
def conveyance_source():
    from datetime import date

    from test_service_conveyance import request

    from examples.study_requirements import POTENTIAL
    from fishy.floor_construction import PotentialFloorSource
    from fishy.potential_requirements import Applicability, PotentialStudy
    from fishy.study_requirements import StudyNeed, StudyScope

    supplied = request()
    scope = StudyScope(
        "service-floor", supplied.location, supplied.interval, "scenario", "member", "sizing", "service season"
    )
    pending = PotentialStudy(Applicability.UNRESOLVED, "study pending", None, ())
    return PotentialFloorSource(
        scope, POTENTIAL, pending, pending, supplied, StudyNeed("ecological studies", "review owner", date(2027, 1, 1))
    )


@pytest.mark.parametrize("field", ("capacity", "ramp", "stopping", "duty"))
def test_selected_conveyance_policy_changes_fail(conveyance_source, field):
    from fishy.quantities import Volume

    req = conveyance_source.conveyance
    assert req is not None and req.ramp is not None
    change = {
        "capacity": {"capacity": Flow(21)},
        "ramp": {"ramp": replace(req.ramp, rise=Flow(6))},
        "stopping": {"stopping": replace(req.stopping, iteration_limit=31)},
        "duty": {"duties": (replace(req.duties[0], volume=Volume(81)),)},
    }[field]
    changed = replace(conveyance_source, conveyance=replace(req, **change))
    assert floor_policy_checks((conveyance_source,)).finding is CheckFinding.PASS
    assert floor_policy_checks((conveyance_source, changed)).finding is CheckFinding.FAIL


def test_missing_conveyance_request_is_unknown(conveyance_source):
    missing = replace(conveyance_source, conveyance=None)
    assert floor_policy_checks((conveyance_source, missing)).finding is CheckFinding.UNKNOWN


def test_conveyance_previous_flow_is_reference_not_policy(conveyance_source):
    req = conveyance_source.conveyance
    assert req is not None and req.ramp is not None
    changed = replace(conveyance_source, conveyance=replace(req, ramp=replace(req.ramp, previous_flow=Flow(9))))
    assert floor_policy_checks((conveyance_source, changed)).finding is CheckFinding.PASS


@pytest.fixture
def zero_conveyance_source(conveyance_source):
    from test_potential_requirements import zero

    from fishy.evidence import EvidenceScope
    from fishy.quantities import Volume

    req = conveyance_source.conveyance
    assert req is not None and req.ramp is not None
    req = replace(
        req,
        duties=(replace(req.duties[0], volume=Volume(0)),),
        initial_flow=Flow(0),
        ramp=replace(req.ramp, previous_flow=Flow(0)),
    )
    scope = conveyance_source.scope
    evidence = replace(
        req.duties[0].evidence,
        scope=EvidenceScope(
            scope.candidate, scope.location.reach.identifier, scope.reference_member, scope.period, scope.purpose
        ),
    )
    determination = replace(zero(), scope=scope, evidence=evidence)
    return replace(conveyance_source, conveyance=req, zero=determination)


@pytest.mark.parametrize("field", ("capacity", "ramp", "stopping", "duty"))
def test_zero_retains_reconciled_conveyance_policy(zero_conveyance_source, field):
    from fishy.floor_construction import assess_floor_source
    from fishy.potential_requirements import PotentialFloorResult, PotentialRoute

    source = zero_conveyance_source
    req = source.conveyance
    assert req is not None and req.ramp is not None
    change = {
        "capacity": {"capacity": Flow(21)},
        "ramp": {"ramp": replace(req.ramp, rise=Flow(6))},
        "stopping": {"stopping": replace(req.stopping, iteration_limit=31)},
        "duty": {"duties": (replace(req.duties[0], capacity=Flow(21)),)},
    }[field]
    changed = replace(source, conveyance=replace(req, **change))
    for candidate in (source, changed):
        result, _ = assess_floor_source(candidate)
        assert isinstance(result, PotentialFloorResult)
        assert result.selected_route is PotentialRoute.ZERO
    assert floor_policy_checks((source, changed)).finding is CheckFinding.FAIL


def test_zero_retains_underlying_study_policy_without_requiring_unused_service():
    from test_potential_requirements import HABITAT, MISSING, NEED, POTENTIAL, SCOPE, criterion, selection, zero

    from fishy.floor_construction import PotentialFloorSource, assess_floor_source
    from fishy.potential_requirements import PotentialFloorResult, PotentialRoute

    study = replace(HABITAT, selection=selection(0, criteria=(criterion(low=0),)))
    source = PotentialFloorSource(SCOPE, POTENTIAL, study, MISSING, None, NEED, zero=zero())
    assert study.selection is not None
    changed = replace(
        source, habitat=replace(study, selection=replace(study.selection, objective="different zero-study objective"))
    )
    result, _ = assess_floor_source(source)
    assert isinstance(result, PotentialFloorResult)
    assert result.selected_route is PotentialRoute.ZERO
    assert result.routes[0].route is PotentialRoute.HABITAT
    assert floor_policy_checks((source,)).finding is CheckFinding.PASS
    assert floor_policy_checks((source, changed)).finding is CheckFinding.FAIL


def test_zero_service_origins_and_determination_policy(zero_conveyance_source):
    from fishy.floor_construction import assess_floor_source
    from fishy.potential_requirements import PotentialFloorResult, PotentialRoute
    from fishy.source_policy import potential_source_routes

    source = zero_conveyance_source
    result, _ = assess_floor_source(source)
    assert isinstance(result, PotentialFloorResult)
    assert potential_source_routes(result) == (PotentialRoute.CONVEYANCE,)
    assert source.zero is not None
    changed = replace(source, zero=replace(source.zero, service_impact_criterion="different criterion"))
    assert floor_policy_checks((source, changed)).finding is CheckFinding.FAIL


def test_direct_zero_determination_requires_no_unselected_route_policy():
    from test_potential_requirements import MISSING, NEED, POTENTIAL, SCOPE, zero

    from fishy.floor_construction import PotentialFloorSource, assess_floor_source
    from fishy.potential_requirements import PotentialFloorResult
    from fishy.source_policy import potential_source_routes

    source = PotentialFloorSource(SCOPE, POTENTIAL, MISSING, MISSING, None, NEED, zero=zero())
    result, _ = assess_floor_source(source)
    assert isinstance(result, PotentialFloorResult)
    assert potential_source_routes(result) == ()
    assert floor_policy_checks((source,)).finding is CheckFinding.PASS
