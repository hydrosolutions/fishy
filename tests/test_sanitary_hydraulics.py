"""Synthetic sanitary D.9 boundary witnesses, not authenticated legal criteria."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.evidence import (
    CheckFinding,
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
from fishy.sanitary_hydraulics import (
    BoundState,
    Comparison,
    CriterionApplicability,
    CriterionStatus,
    HydraulicRelationEvidence,
    HydraulicScope,
    HydraulicTransition,
    HydraulicVariable,
    ImportedHydraulicFinding,
    RateBound,
    RateCriterion,
    RelationDomain,
    StateBounds,
    TemporalSupport,
    TransitionCoverage,
    assess_imported_hydraulics,
    assess_sanitary_rate,
    rate_check,
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
    ("previous", "current", "rate", "finding"),
    [
        ("1", "1.12", ".24", CheckFinding.FAIL),
        ("1.12", "1", "-.24", CheckFinding.PASS),
        ("1", "1.10", ".20", CheckFinding.PASS),
    ],
)
def test_s4_half_hour_stage_witness(previous, current, rate, finding):
    c, t = inputs(previous, current)
    result = assess_sanitary_rate(c, t)
    assert result.rate_bounds == bounds(rate)
    assert result.elapsed_hours == Fraction(1, 2)
    assert result.check.finding is finding
    assert result.criterion.status is CriterionStatus.HYPOTHETICAL
    assert result.transition.evidence.official_admissibility is OfficialAdmissibility.PENDING
    assert rate_check(c.scope, result) == result.check


@pytest.mark.parametrize(("previous", "current", "direction"), [("1", "1.10", "rise"), ("1.15", "1", "fall")])
def test_strict_equality_fails(previous, current, direction):
    c, t = inputs(previous, current)
    c = replace(c, **{direction: replace(getattr(c, direction), comparison=Comparison.STRICT)})
    assert assess_sanitary_rate(c, t).check.finding is CheckFinding.FAIL


@pytest.mark.parametrize(
    ("current", "expected", "finding"),
    [
        (("1.07", "1.09"), (".10", ".18"), CheckFinding.UNKNOWN),
        (("1.13", "1.15"), (".22", ".30"), CheckFinding.FAIL),
        (("1.04", "1.05"), (".04", ".10"), CheckFinding.PASS),
    ],
)
def test_conservative_uncertainty(current, expected, finding):
    c, t = inputs()
    c = replace(c, rise=RateBound(BoundState.SUPPLIED, Fraction(".15")))
    t = replace(t, previous=bounds("1", "1.02"), current=bounds(*current))
    result = assess_sanitary_rate(c, t)
    assert result.rate_bounds == bounds(*expected)
    assert result.check.finding is finding


def test_irregular_elapsed_and_tighter_supported_joint_evidence():
    c, t = inputs("1", "1.09")
    s = replace(c.scope, period=Interval(c.scope.period.start, c.scope.period.start + timedelta(minutes=45)))
    result = assess_sanitary_rate(replace(c, scope=s), replace(t, scope=s, evidence=evidence(s)))
    assert result.rate_bounds == bounds(".12")
    t = replace(
        t,
        previous=bounds("1", "1.02"),
        current=bounds("1.07", "1.09"),
        joint_rate_bounds=bounds(".12"),
        joint_evidence="shared datum error cancels; study J v1",
    )
    assert assess_sanitary_rate(c, t).rate_bounds == bounds(".12")
    with pytest.raises(ValueError, match="tighten"):
        assess_sanitary_rate(c, replace(t, joint_rate_bounds=bounds(".5")))


@pytest.mark.parametrize("coverage", [TransitionCoverage.GAP, TransitionCoverage.MISSING_PREDECESSOR])
def test_expected_gaps_never_bridged(coverage):
    c, t = inputs()
    result = assess_sanitary_rate(c, replace(t, coverage=coverage))
    assert result.check.finding is CheckFinding.UNKNOWN
    assert result.rate_bounds is None


def test_missing_state_season_boundary_and_required_bound():
    c, t = inputs()
    assert assess_sanitary_rate(c, replace(t, previous=None)).check.finding is CheckFinding.UNKNOWN
    assert (
        assess_sanitary_rate(replace(c, applicability=CriterionApplicability.UNRESOLVED), t).check.finding
        is CheckFinding.UNKNOWN
    )
    absent = RateBound(BoundState.INTENTIONALLY_ABSENT, None)
    assert assess_sanitary_rate(replace(c, rise=absent), t).check.finding is CheckFinding.PASS
    assert (
        assess_sanitary_rate(replace(c, rise=RateBound(BoundState.MISSING, None)), t).check.finding
        is CheckFinding.UNKNOWN
    )


def test_daily_means_cannot_certify_within_day_or_endpoints_peak():
    c, t = inputs("1", "1")
    daily = replace(t.scope, temporal_support=TemporalSupport.DAILY_MEANS)
    t = replace(t, scope=daily, evidence=evidence(daily))
    required = replace(c.scope, temporal_support=TemporalSupport.WITHIN_DAY)
    assert assess_sanitary_rate(replace(c, scope=required), t).check.finding is CheckFinding.UNKNOWN
    assert assess_sanitary_rate(replace(c, scope=daily), t).check.finding is CheckFinding.PASS
    assert (
        assess_sanitary_rate(replace(c, scope=required), replace(t, scope=required)).check.finding
        is CheckFinding.UNKNOWN
    )


@pytest.mark.parametrize("finding", [CheckFinding.PASS, CheckFinding.FAIL])
@pytest.mark.parametrize(
    "component,variable",
    [
        ("pre_impoundment_velocity", HydraulicVariable.DIRECTIONAL_VELOCITY),
        ("cascade_current_continuity", HydraulicVariable.DIRECTIONAL_VELOCITY),
        ("release_uniformity", HydraulicVariable.RELEASE_DISCHARGE),
        ("within_day_stage", HydraulicVariable.STAGE),
        ("within_day_velocity", HydraulicVariable.SPEED),
    ],
)
def test_s4_attributable_imported_success_failure(component, variable, finding):
    s = replace(scope(), component=component, variable=variable, temporal_support=TemporalSupport.WITHIN_DAY)
    imported = ImportedHydraulicFinding(
        s,
        "specialist-study-v3",
        "supplied §4.3/§4.4 interpretation",
        evidence(s),
        finding,
        ("supported assessment on specified domain",),
    )
    result = assess_imported_hydraulics(s, imported)
    assert result.finding is finding
    assert "imported study" in result.reasons[0]
    for changed in (
        replace(s, domain="other domain"),
        replace(s, candidate="other candidate"),
        replace(s, scenario="other scenario"),
        replace(s, reference="other datum"),
        replace(s, variable=HydraulicVariable.DEPTH),
        replace(s, temporal_support=TemporalSupport.DAILY_MEANS),
    ):
        assert assess_imported_hydraulics(changed, imported).finding is CheckFinding.UNKNOWN


def test_unsupported_states_and_imports_do_not_gain_validity():
    c, t = inputs()
    unsupported = replace(
        t.evidence,
        numerical_validity=NumericalValidity.INVALID,
        reasons=("outside supported geometry or boundary-condition domain",),
    )
    assert assess_sanitary_rate(c, replace(t, evidence=unsupported)).check.finding is CheckFinding.UNKNOWN
    imported = ImportedHydraulicFinding(c.scope, "study", "criterion", unsupported, CheckFinding.PASS, ("exploratory",))
    assert assess_imported_hydraulics(c.scope, imported).finding is CheckFinding.UNKNOWN


def test_invalid_domains_and_unattributed_findings():
    c, t = inputs()
    with pytest.raises(ValueError):
        RateBound(BoundState.SUPPLIED, Fraction(-1))
    with pytest.raises(ValueError):
        RateBound(BoundState.MISSING, Fraction(0))
    with pytest.raises(TypeError):
        StateBounds(float("nan"), Fraction(0))  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError):
        Interval(c.scope.period.start, c.scope.period.start)
    with pytest.raises(ValueError):
        ImportedHydraulicFinding(c.scope, "", "criterion", t.evidence, CheckFinding.PASS, ("reason",))
    with pytest.raises(ValueError):
        replace(t, evidence=replace(t.evidence, scope=replace(t.evidence.scope, product="another candidate")))
    with pytest.raises(ValueError):
        replace(t, scope=replace(t.scope, variable=HydraulicVariable.SPEED), previous=bounds("-1"))


def test_empty_strict_zero_range_is_disjoint_even_with_uncertainty():
    c, t = inputs()
    zero = RateBound(BoundState.SUPPLIED, Fraction(0), Comparison.STRICT)
    result = assess_sanitary_rate(
        replace(c, rise=zero, fall=zero), replace(t, previous=bounds("0", "1"), current=bounds("0", "1"))
    )
    assert result.check.finding is CheckFinding.FAIL


def test_numeric_finding_does_not_promote_or_depend_on_scientific_acceptance():
    c, t = inputs()
    rejected = replace(t.evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    result = assess_sanitary_rate(c, replace(t, evidence=rejected))
    assert result.check.finding is CheckFinding.FAIL
    assert result.permission.finding is CheckFinding.FAIL


def test_warmup_states_cannot_certify():
    c, t = inputs("1", "1")
    excluded = replace(t.evidence, provenance=replace(t.evidence.provenance, excluded_warmup=(t.scope.period,)))
    assert assess_sanitary_rate(c, replace(t, evidence=excluded)).check.finding is CheckFinding.UNKNOWN


def test_imported_permission_and_warmup_remain_distinct():
    s = scope()
    rejected = replace(evidence(s), scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    imported = ImportedHydraulicFinding(s, "study", "criterion", rejected, CheckFinding.FAIL, ("observed failure",))
    assert assess_imported_hydraulics(s, imported).finding is CheckFinding.FAIL
    assert imported.permission.finding is CheckFinding.FAIL
    excluded = replace(rejected, provenance=replace(rejected.provenance, excluded_warmup=(s.period,)))
    assert assess_imported_hydraulics(s, replace(imported, evidence=excluded)).finding is CheckFinding.UNKNOWN


def test_rate_cannot_transfer_to_other_location_variable_or_period():
    c, t = inputs()
    assessment = assess_sanitary_rate(c, t)
    for requested in (
        replace(c.scope, variable=HydraulicVariable.RELEASE_DISCHARGE),
        replace(c.scope, location=replace(c.scope.location, mapping_version="v2")),
        replace(c.scope, period=Interval(c.scope.period.start, c.scope.period.end + timedelta(hours=1))),
    ):
        assert rate_check(requested, assessment).finding is CheckFinding.UNKNOWN


def test_relation_metadata_retained_and_no_extrapolation():
    c, t = inputs("1", "1")
    relation = HydraulicRelationEvidence(
        "hydraulic-study-r2",
        "survey-geometry-v3",
        "downstream stage 12m; steady boundary",
        "discharge 0 to 5 m3/s",
        "linear within supported domain only",
        "closed bounds from survey; correlated datum error",
        "indicative scenario only",
        RelationDomain.SUPPORTED,
    )
    result = assess_sanitary_rate(c, replace(t, relation=relation))
    assert result.check.finding is CheckFinding.PASS
    assert result.transition.relation == relation
    unsupported = replace(relation, domain_state=RelationDomain.UNSUPPORTED)
    assert assess_sanitary_rate(c, replace(t, relation=unsupported)).check.finding is CheckFinding.UNKNOWN
    imported = ImportedHydraulicFinding(
        c.scope, "study", "criterion", t.evidence, CheckFinding.PASS, ("local stage evaluated",), relation=unsupported
    )
    assert imported.relation == unsupported
    assert assess_imported_hydraulics(c.scope, imported).finding is CheckFinding.UNKNOWN
    with pytest.raises(ValueError):
        replace(relation, boundary_conditions="")


def test_no_directional_criteria_cannot_manufacture_satisfaction():
    c, t = inputs()
    absent = RateBound(BoundState.INTENTIONALLY_ABSENT, None)
    result = assess_sanitary_rate(replace(c, rise=absent, fall=absent), t)
    assert result.check.finding is CheckFinding.UNKNOWN
    assert result.rate_bounds is None


@pytest.mark.parametrize(
    ("previous", "current", "missing", "rate"),
    [("1", "1.12", "fall", ".24"), ("1.20", "1", "rise", "-.4")],
)
def test_supported_direction_failure_survives_missing_other_bound(previous, current, missing, rate):
    from fishy.evidence import Completeness

    criterion, transition = inputs(previous, current)
    criterion = replace(criterion, **{missing: RateBound(BoundState.MISSING, None)})
    result = assess_sanitary_rate(criterion, transition)
    assert result.check.finding is CheckFinding.FAIL
    assert result.completeness is Completeness.INCOMPLETE
    assert result.directional_checks.finding is CheckFinding.FAIL
    assert any(check.finding is CheckFinding.UNKNOWN for check in result.directional_checks.checks)
    assert result.rate_bounds == bounds(rate)
    assert result.elapsed_hours == Fraction(1, 2)
    assert result.change_bounds == bounds(Fraction(current) - Fraction(previous))
    assert result.criterion == criterion and result.transition == transition


def test_passed_direction_cannot_hide_missing_other_bound():
    from fishy.evidence import Completeness

    criterion, transition = inputs("1", "1.05")
    criterion = replace(criterion, fall=RateBound(BoundState.MISSING, None))
    result = assess_sanitary_rate(criterion, transition)
    assert result.check.finding is CheckFinding.UNKNOWN
    assert result.completeness is Completeness.INCOMPLETE
    assert result.rate_bounds == bounds(".1")


def test_incomplete_scalar_rate_transfer_is_rejected_instead_of_claiming_complete_duty():
    from fishy.duties import DutyApplicability, SuppliedDuty, assess_duty
    from fishy.evidence import Completeness

    criterion, transition = inputs("1", "1.12")
    criterion = replace(criterion, fall=RateBound(BoundState.MISSING, None))
    rate = assess_sanitary_rate(criterion, transition)
    duty = SuppliedDuty(
        "instrument",
        "v1",
        "supplied criterion",
        DutyApplicability.HYPOTHETICAL,
        (),
        "documented search",
        required_components=(criterion.scope.component,),
    )
    assert rate.completeness is Completeness.INCOMPLETE
    with pytest.raises(ValueError, match="lossless"):
        assess_duty(duty, (), component_checks=(rate_check(criterion.scope, rate),))
