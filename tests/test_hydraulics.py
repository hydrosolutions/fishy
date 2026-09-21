"""Synthetic sanitary D.9 boundary witnesses, not authenticated legal criteria."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.evidence import (
    CheckFinding,
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.hydraulics import (
    BoundState,
    Comparison,
    CriterionApplicability,
    CriterionStatus,
    HydraulicRelationEvidence,
    HydraulicScope,
    HydraulicState,
    HydraulicTransition,
    HydraulicVariable,
    ImportedHydraulicFinding,
    RateBound,
    RateCriterion,
    RelationDomain,
    StateBounds,
    StateCriterion,
    StateLimit,
    StatePresence,
    TemporalSupport,
    TransitionCoverage,
    assess_discrete_rate,
    assess_hydraulics,
    assess_imported_hydraulics,
    assess_state_range,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def scope():
    return HydraulicScope(
        "within_day_stage",
        Location(Reach("reach", "v1", WaterBody("river", "v1")), CalculationSection("point", "v1"), "v1"),
        "downstream reach",
        "candidate-A",
        "scenario-A",
        HydraulicVariable.STAGE,
        Interval(datetime(2020, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, 0, 30, tzinfo=UTC)),
        "local datum v1",
        TemporalSupport.ENDPOINTS,
    )


def evidence(s):
    return EvidenceFindings(
        EvidenceScope(s.candidate, s.location.reach.identifier, None, s.period, s.component),
        Provenance(
            "synthetic states",
            s.scenario,
            None,
            "v1",
            "v1",
            "v1",
            ProductionMethod.ILLUSTRATIVE,
            CorrectionState.ORIGINAL,
        ),
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("synthetic acceptance witness only",),
    )


def bounds(lo, hi=None):
    return StateBounds(Fraction(lo), Fraction(lo if hi is None else hi))


def inputs(previous="1", current="1.12"):
    s = scope()
    criterion = RateCriterion(
        s,
        "hypothetical supplied limits, not SanPiN defaults",
        CriterionStatus.HYPOTHETICAL,
        RateBound(BoundState.SUPPLIED, Fraction(".20")),
        RateBound(BoundState.SUPPLIED, Fraction(".30")),
        CriterionApplicability.APPLICABLE,
    )
    transition = HydraulicTransition(s, bounds(previous), bounds(current), TransitionCoverage.ADJACENT, evidence(s))
    return criterion, transition


@pytest.mark.parametrize(
    "case,previous,current,minutes,limit,strict,expected,finding",
    [
        ("rise_exceeds_limit", ("1",), ("1.12",), 30, ".20", False, (".24",), CheckFinding.FAIL),
        ("fall_uses_distinct_limit", ("1.12",), ("1",), 30, ".20", False, ("-.24",), CheckFinding.PASS),
        ("inclusive_equality_pass", ("1",), ("1.10",), 30, ".20", False, (".20",), CheckFinding.PASS),
        ("strict_equality_fail", ("1",), ("1.10",), 30, ".20", True, (".20",), CheckFinding.FAIL),
        ("irregular_supported_elapsed_time", ("1",), ("1.09",), 45, ".20", False, (".12",), CheckFinding.PASS),
        (
            "uncertainty_overlap",
            ("1", "1.02"),
            ("1.07", "1.09"),
            30,
            ".15",
            False,
            (".10", ".18"),
            CheckFinding.UNKNOWN,
        ),
        ("uncertainty_disjoint", ("1", "1.02"), ("1.13", "1.15"), 30, ".15", False, (".22", ".30"), CheckFinding.FAIL),
        ("uncertainty_contained", ("1", "1.02"), ("1.04", "1.05"), 30, ".15", False, (".04", ".10"), CheckFinding.PASS),
    ],
    ids=lambda value: value if isinstance(value, str) and "_" in value else None,
)
def test_held_rate(case, previous, current, minutes, limit, strict, expected, finding):
    c, t = inputs()
    s = replace(c.scope, period=Interval(c.scope.period.start, c.scope.period.start + timedelta(minutes=minutes)))
    c = replace(
        c,
        scope=s,
        rise=RateBound(BoundState.SUPPLIED, Fraction(limit), Comparison.STRICT if strict else Comparison.INCLUSIVE),
    )
    t = replace(t, scope=s, evidence=evidence(s), previous=bounds(*previous), current=bounds(*current))
    result = assess_discrete_rate(c, t)
    assert result.rate_bounds == bounds(*expected), case
    assert result.check.finding is finding
    assert result.change_bounds == bounds(t.current.lower - t.previous.upper, t.current.upper - t.previous.lower)
    assert result.elapsed_hours == Fraction(minutes, 60)


def test_known_missing_interval_not_bridged():
    c, t = inputs("1", "1.1")
    s = replace(c.scope, period=Interval(c.scope.period.start, c.scope.period.start + timedelta(hours=2)))
    r = assess_discrete_rate(
        replace(c, scope=s), replace(t, scope=s, evidence=evidence(s), coverage=TransitionCoverage.GAP)
    )
    assert r.check.finding is CheckFinding.UNKNOWN and r.rate_bounds is None
    assert r.completeness is Completeness.INCOMPLETE


def test_missing_predecessor():
    c, t = inputs()
    r = assess_discrete_rate(c, replace(t, previous=None, coverage=TransitionCoverage.MISSING_PREDECESSOR))
    assert r.check.finding is CheckFinding.UNKNOWN and r.rate_bounds is None
    assert r.completeness is Completeness.INCOMPLETE


def test_daily_means_do_not_test_hourly_peak():
    c, t = inputs("1", "1")
    daily = replace(t.scope, temporal_support=TemporalSupport.DAILY_MEANS)
    t = replace(t, scope=daily, evidence=evidence(daily))
    assert assess_discrete_rate(replace(c, scope=daily), t).rate_bounds == bounds("0")
    peak = replace(c.scope, temporal_support=TemporalSupport.WITHIN_DAY)
    assert assess_discrete_rate(replace(c, scope=peak), t).check.finding is CheckFinding.UNKNOWN


def test_discharge_not_downstream_stage():
    s = scope()
    q = replace(s, variable=HydraulicVariable.RELEASE_DISCHARGE, reference="section mean discharge")
    supplied = ImportedHydraulicFinding(q, "study-v1", "Q ramp", evidence(q), CheckFinding.PASS, ("Q only",))
    assert assess_imported_hydraulics(s, supplied).finding is CheckFinding.UNKNOWN
    joint = assess_hydraulics((s,), ())
    assert joint.finding is CheckFinding.UNKNOWN and joint.completeness is Completeness.INCOMPLETE


def state_input(component, variable, value, lower=None, upper=None):
    s = replace(
        scope(),
        component=component,
        variable=variable,
        reference="survey bed v1" if variable is HydraulicVariable.DEPTH else "speed magnitude",
    )
    c = StateCriterion(
        s,
        "synthetic selected target v1",
        CriterionStatus.HYPOTHETICAL,
        StateLimit(BoundState.INTENTIONALLY_ABSENT, None)
        if lower is None
        else StateLimit(BoundState.SUPPLIED, Fraction(lower)),
        StateLimit(BoundState.INTENTIONALLY_ABSENT, None)
        if upper is None
        else StateLimit(BoundState.SUPPLIED, Fraction(upper)),
    )
    return c, HydraulicState(s, bounds(*value), evidence(s))


def test_known_velocity_failure_with_uncertain_depth():
    dc, d = state_input("depth", HydraulicVariable.DEPTH, (".25", ".35"), lower=".30")
    vc, v = state_input("velocity", HydraulicVariable.SPEED, (".80",), upper=".60")
    depth, velocity = assess_state_range(dc, d), assess_state_range(vc, v)
    assert depth.check.finding is CheckFinding.UNKNOWN
    assert velocity.check.finding is CheckFinding.FAIL
    joint = assess_hydraulics((dc.scope, vc.scope), (depth, velocity))
    assert joint.finding is CheckFinding.FAIL and joint.completeness is Completeness.INCOMPLETE
    assert joint.components == (depth, velocity)


def test_qualitative_duty_has_no_numeric_limit():
    c, t = inputs()
    absent = RateBound(BoundState.MISSING, None)
    r = assess_discrete_rate(replace(c, rise=absent, fall=absent), t)
    assert r.check.finding is CheckFinding.UNKNOWN
    assert all(check.finding is CheckFinding.UNKNOWN for check in r.directional_checks.checks)


def test_relation_outside_supported_domain():
    c, state = state_input("depth", HydraulicVariable.DEPTH, (".5",), lower=".3")
    relation = HydraulicRelationEvidence(
        "relation-v1",
        "geometry-v1",
        "candidate discharge 6 m3/s",
        "discharge 0..5 m3/s",
        "linear inside domain only",
        "closed bounds",
        "indicative",
        RelationDomain.UNSUPPORTED,
    )
    r = assess_state_range(c, replace(state, relation=relation))
    assert r.exploratory_checks.finding is CheckFinding.PASS
    assert r.check.finding is CheckFinding.UNKNOWN
    assert r.state.relation == relation


def test_season_boundary_criterion_missing():
    c, t = inputs()
    r = assess_discrete_rate(replace(c, applicability=CriterionApplicability.UNRESOLVED), t)
    assert r.check.finding is CheckFinding.UNKNOWN and r.rate_bounds is None


def test_invalid_zero_elapsed_time():
    with pytest.raises(ValueError, match="positive elapsed"):
        Interval(scope().period.start, scope().period.start)


def test_invalid_negative_rate_magnitude():
    with pytest.raises(ValueError, match="nonnegative"):
        RateBound(BoundState.SUPPLIED, Fraction("-.1"))


@pytest.mark.parametrize("variable", [HydraulicVariable.STAGE, HydraulicVariable.DIRECTIONAL_VELOCITY])
def test_signed_state_and_range_strictness(variable):
    c, state = state_input("signed", variable, ("-1",), lower="-1", upper="0")
    assert assess_state_range(c, state).check.finding is CheckFinding.PASS
    strict = replace(c, lower=replace(c.lower, comparison=Comparison.STRICT))
    assert assess_state_range(strict, state).check.finding is CheckFinding.FAIL
    assert assess_state_range(c, replace(state, value=bounds("-2", "-.5"))).check.finding is CheckFinding.UNKNOWN


def test_joint_preserves_missing_rate_direction_and_permission():
    c, t = inputs()
    r = assess_discrete_rate(replace(c, fall=RateBound(BoundState.MISSING, None)), t)
    joint = assess_hydraulics((c.scope,), (r,))
    assert joint.finding is CheckFinding.FAIL and joint.completeness is Completeness.INCOMPLETE
    rejected = replace(t, evidence=replace(t.evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED))
    r = assess_discrete_rate(c, rejected)
    assert r.check.finding is CheckFinding.FAIL
    joint = assess_hydraulics((c.scope,), (r,))
    assert joint.finding is CheckFinding.UNKNOWN and joint.completeness is Completeness.INCOMPLETE


def test_joint_success_missing_empty_and_identity_refusals():
    c, state = state_input("depth", HydraulicVariable.DEPTH, (".4",), lower=".3")
    result = assess_state_range(c, state)
    assert assess_hydraulics((c.scope,), (result,)).finding is CheckFinding.PASS
    assert assess_hydraulics((), ()).finding is CheckFinding.UNKNOWN
    assert assess_hydraulics((c.scope,), ()).finding is CheckFinding.UNKNOWN
    with pytest.raises(ValueError, match="duplicate"):
        assess_hydraulics((c.scope,), (result, result))
    with pytest.raises(ValueError, match="same candidate"):
        assess_hydraulics((c.scope, replace(c.scope, component="other", candidate="another")), ())
    with pytest.raises(ValueError, match="required hydraulic scope"):
        assess_hydraulics((replace(c.scope, reference="other bed"),), (result,))
    assert (
        assess_state_range(c, replace(state, value=None, presence=StatePresence.MISSING)).check.finding
        is CheckFinding.UNKNOWN
    )


def test_state_missing_bound_cannot_hide_supported_failure():
    c, state = state_input("depth", HydraulicVariable.DEPTH, (".2",), lower=".3")
    c = replace(c, upper=StateLimit(BoundState.MISSING, None))
    r = assess_state_range(c, state)
    assert r.check.finding is CheckFinding.FAIL and r.completeness is Completeness.INCOMPLETE
    assert assess_hydraulics((c.scope,), (r,)).completeness is Completeness.INCOMPLETE


def test_state_invalid_domains_and_empty_range():
    c, state = state_input("depth", HydraulicVariable.DEPTH, ("0", "1"), lower=".5", upper=".5")
    c = replace(c, lower=replace(c.lower, comparison=Comparison.STRICT))
    assert assess_state_range(c, state).check.finding is CheckFinding.FAIL
    with pytest.raises(ValueError, match="negative"):
        replace(state, value=bounds("-1"))
    with pytest.raises(ValueError, match="reversed"):
        replace(c, upper=StateLimit(BoundState.SUPPLIED, Fraction(".1")))
    with pytest.raises(TypeError, match="Fraction"):
        StateLimit(BoundState.SUPPLIED, float("nan"))  # ty: ignore[invalid-argument-type]


def test_component_names_cannot_collide_with_internal_coverage_findings():
    c, t = inputs()
    rate = assess_discrete_rate(replace(c, fall=RateBound(BoundState.MISSING, None)), t)
    dc, d = state_input(c.scope.component + ":coverage", HydraulicVariable.DEPTH, (".4",), lower=".3")
    result = assess_hydraulics((c.scope, dc.scope), (rate, assess_state_range(dc, d)))
    assert result.finding is CheckFinding.FAIL
    assert result.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize("presence", [StatePresence.MISSING, StatePresence.OUTSIDE_HORIZON, StatePresence.UNSUPPORTED])
def test_state_presence_does_not_become_zero(presence):
    c, state = state_input("depth", HydraulicVariable.DEPTH, ("0",), lower="0")
    assert assess_state_range(c, state).check.finding is CheckFinding.PASS
    missing = replace(state, value=None, presence=presence)
    result = assess_state_range(c, missing)
    assert result.check.finding is CheckFinding.UNKNOWN
    assert result.state.presence is presence
    assert presence.value in result.check.reasons


def test_local_velocity_cannot_substitute_section_mean():
    c, state = state_input("velocity", HydraulicVariable.DIRECTIONAL_VELOCITY, ("-.2",), lower="-.3")
    mean = replace(c, scope=replace(c.scope, variable=HydraulicVariable.SECTION_MEAN_VELOCITY))
    result = assess_state_range(mean, state)
    assert result.exploratory_checks.finding is CheckFinding.PASS
    assert result.check.finding is CheckFinding.UNKNOWN


def test_public_example():
    from examples.hydraulic_assessment import example

    result = example()
    assert result.finding is CheckFinding.PASS
    assert result.completeness is Completeness.COMPLETE


def test_mismatched_reference_member_evidence_is_rejected():
    c, transition = inputs()
    contradictory = replace(
        transition.evidence,
        scope=replace(transition.evidence.scope, member="member-A"),
        provenance=replace(transition.evidence.provenance, reference_member="member-B"),
    )
    with pytest.raises(ValueError, match="member"):
        replace(transition, evidence=contradictory)


def test_joint_cannot_mix_reference_members():
    dc, depth = state_input("depth", HydraulicVariable.DEPTH, (".4",), lower=".3")
    vc, velocity = state_input("velocity", HydraulicVariable.SPEED, (".4",), upper=".6")
    results = []
    for criterion, state, member in ((dc, depth, "A"), (vc, velocity, "B")):
        member_evidence = replace(
            state.evidence,
            scope=replace(state.evidence.scope, member=member),
            provenance=replace(state.evidence.provenance, reference_member=member),
        )
        results.append(assess_state_range(criterion, replace(state, evidence=member_evidence)))
    with pytest.raises(ValueError, match="reference member"):
        assess_hydraulics((dc.scope, vc.scope), tuple(results))


def test_joint_cannot_mix_candidate_configuration_versions():
    dc, depth = state_input("depth", HydraulicVariable.DEPTH, (".4",), lower=".3")
    vc, velocity = state_input("velocity", HydraulicVariable.SPEED, (".4",), upper=".6")
    changed = replace(velocity.evidence, provenance=replace(velocity.evidence.provenance, configuration_version="v2"))
    with pytest.raises(ValueError, match="configuration"):
        assess_hydraulics(
            (dc.scope, vc.scope),
            (assess_state_range(dc, depth), assess_state_range(vc, replace(velocity, evidence=changed))),
        )


def test_joint_retains_distinct_specialist_study_revisions():
    dc, depth = state_input("depth", HydraulicVariable.DEPTH, (".4",), lower=".3")
    vc, velocity = state_input("velocity", HydraulicVariable.SPEED, (".4",), upper=".6")
    changed = replace(
        velocity.evidence,
        provenance=replace(
            velocity.evidence.provenance,
            source="independent velocity study",
            data_version="survey-v2",
            software_version="specialist-v3",
        ),
    )
    results = (assess_state_range(dc, depth), assess_state_range(vc, replace(velocity, evidence=changed)))
    joint = assess_hydraulics((dc.scope, vc.scope), results)
    assert joint.finding is CheckFinding.PASS
    assert joint.components == results
