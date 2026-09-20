"""Synthetic Art.32 and Ordinance33a/34 witnesses; no private source fixtures."""

from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

import pytest

from fishy.evidence import (
    CheckFinding,
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.swiss_exceptions import (
    AltitudeEndpoints,
    AreaConnection,
    CompensationAdequacy,
    CompensationPurpose,
    DecisionBasis,
    DownstreamExtent,
    Elevation,
    EmergencyAbstraction,
    EmergencyBasis,
    ExceptionClause,
    ExceptionDecision,
    ExceptionScope,
    FishStatus,
    FunctionalImpact,
    HighAltitudeWater,
    LegalRequirement,
    LowEcologicalPotential,
    NonFishWater,
    PlanApproval,
    ProtectionUsePlan,
    Significance,
    assess_exception,
    condition_evidence_scope,
    decision_evidence_scope,
)
from fishy.time import Interval

PERIOD = Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 2, 1, tzinfo=UTC))
SCOPE = ExceptionScope(
    Location(Reach("reach", "v1", WaterBody("river", "v1")), CalculationSection("intake", "v1"), "v1"),
    "intake",
    "synthetic",
    "member",
    PERIOD,
    DownstreamExtent(0, 1000),
    "v1",
    "v1",
)


def evidence(clause, scope=SCOPE):
    return EvidenceFindings(
        scope.evidence_scope(clause),
        Provenance(
            "synthetic study",
            scope.scenario,
            scope.member,
            "v1",
            "v1",
            "v1",
            ProductionMethod.ILLUSTRATIVE,
            CorrectionState.ORIGINAL,
        ),
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic, not a permit",),
    )


def decision(clause, minimum=10, scope=SCOPE):
    return ExceptionDecision(
        scope,
        clause,
        Flow(minimum, "l/s"),
        DecisionBasis.HYPOTHETICAL,
        "scenario author",
        "synthetic decision",
        replace(
            evidence(clause, scope),
            scope=decision_evidence_scope(
                scope, clause, Flow(minimum, "l/s"), DecisionBasis.HYPOTHETICAL, "scenario author", "synthetic decision"
            ),
        ),
    )


def high(z=1800, fish=FishStatus.NON_FISH, scope=SCOPE):
    c = HighAltitudeWater(evidence(ExceptionClause.HIGH_ALTITUDE, scope), Elevation(z), fish)
    assert c.evidence is not None
    return replace(
        c, evidence=replace(c.evidence, scope=condition_evidence_scope(scope, ExceptionClause.HIGH_ALTITUDE, c))
    )


def plan():
    return ProtectionUsePlan(
        evidence(ExceptionClause.PROTECTION_PLAN),
        "adopted plan",
        "area-A",
        AreaConnection.LIMITED_CONNECTED,
        "area-A",
        CompensationPurpose.WATER_OR_DEPENDENT_HABITAT,
        LegalRequirement.ADDITIONAL,
        CompensationAdequacy.ADEQUATE,
        "study of compensating protection",
        "binding on everyone",
        PERIOD,
        PERIOD,
        PlanApproval.FEDERAL_COUNCIL,
        "hypothetical approval",
        "FOEN filing",
    )


def run(conditions, clause, q=40, minimum=10, scope=SCOPE):
    # Synthetic reviewer attributes each intended variant before assessing it.
    if conditions.evidence is not None and conditions.evidence.scope == scope.evidence_scope(clause):
        conditions = replace(
            conditions, evidence=replace(conditions.evidence, scope=condition_evidence_scope(scope, clause, conditions))
        )
    return assess_exception(Flow(q, "l/s"), Flow(50, "l/s"), scope, conditions, decision(clause, minimum, scope))


@pytest.mark.parametrize(
    "q,expected", [(Fraction(49999, 1000), CheckFinding.PASS), (50, CheckFinding.FAIL), (51, CheckFinding.FAIL)]
)
def test_high_altitude_q_strict(q, expected):
    assert run(high(), ExceptionClause.HIGH_ALTITUDE, q).summary.finding is expected


@pytest.mark.parametrize(
    "length,expected", [(999, CheckFinding.PASS), (1000, CheckFinding.PASS), (1001, CheckFinding.FAIL)]
)
def test_limited_reach_boundaries(length, expected):
    scope = replace(SCOPE, extent=DownstreamExtent(0, length))
    assert run(high(scope=scope), ExceptionClause.HIGH_ALTITUDE, scope=scope).summary.finding is expected
    c = LowEcologicalPotential(
        evidence(ExceptionClause.LOW_POTENTIAL, scope),
        Significance.LOW,
        Significance.LOW,
        "restoration",
        FunctionalImpact.NOT_SUBSTANTIAL,
    )
    assert run(c, ExceptionClause.LOW_POTENTIAL, scope=scope).summary.finding is expected


@pytest.mark.parametrize(
    "z,fish,expected",
    [
        (1701, FishStatus.FISH, CheckFinding.PASS),
        (1700, FishStatus.FISH, CheckFinding.FAIL),
        (1499, FishStatus.NON_FISH, CheckFinding.FAIL),
        (1600, FishStatus.NON_FISH, CheckFinding.PASS),
        (1600, FishStatus.FISH, CheckFinding.FAIL),
    ],
)
def test_altitude_and_nonfish(z, fish, expected):
    assert run(high(z, fish), ExceptionClause.HIGH_ALTITUDE).summary.finding is expected


@pytest.mark.parametrize("z", [1500, 1700])
def test_exact_altitude_endpoints_require_explicit_selection(z):
    c = high(z)
    assert run(c, ExceptionClause.HIGH_ALTITUDE).summary.finding is CheckFinding.UNKNOWN
    c = replace(c, endpoints=AltitudeEndpoints.INCLUSIVE_SCENARIO, endpoint_source="declared inclusive scenario")
    c = replace(
        c, evidence=replace(c.evidence, scope=condition_evidence_scope(SCOPE, ExceptionClause.HIGH_ALTITUDE, c))
    )
    r = run(c, ExceptionClause.HIGH_ALTITUDE)
    assert r.applied_minimum == Flow(10, "l/s")
    assert r.decision.basis is DecisionBasis.HYPOTHETICAL
    assert (
        run(replace(c, endpoints=AltitudeEndpoints.EXCLUSIVE), ExceptionClause.HIGH_ALTITUDE).summary.finding
        is CheckFinding.FAIL
    )


@pytest.mark.parametrize(
    "minimum,expected", [("13.999", CheckFinding.FAIL), (14, CheckFinding.PASS), ("14.001", CheckFinding.PASS)]
)
def test_nonfish_35_percent_exact(minimum, expected):
    c = NonFishWater(evidence(ExceptionClause.NON_FISH), FishStatus.NON_FISH)
    assert run(c, ExceptionClause.NON_FISH, minimum=minimum).summary.finding is expected


def test_nonfish_required():
    assert (
        run(
            NonFishWater(evidence(ExceptionClause.NON_FISH), FishStatus.FISH), ExceptionClause.NON_FISH, minimum=14
        ).summary.finding
        is CheckFinding.FAIL
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("present_significance", Significance.NOT_LOW),
        ("restored_significance", Significance.NOT_LOW),
        ("natural_functions", FunctionalImpact.SUBSTANTIAL),
    ],
)
def test_low_potential_requires_present_and_restored_significance(field, value):
    c = LowEcologicalPotential(
        evidence(ExceptionClause.LOW_POTENTIAL),
        Significance.LOW,
        Significance.LOW,
        "proportionate restoration",
        FunctionalImpact.NOT_SUBSTANTIAL,
    )
    assert run(c, ExceptionClause.LOW_POTENTIAL).summary.finding is CheckFinding.PASS
    assert run(replace(c, **{field: value}), ExceptionClause.LOW_POTENTIAL).summary.finding is CheckFinding.FAIL


def test_present_degradation_alone_insufficient():
    c = LowEcologicalPotential(
        evidence(ExceptionClause.LOW_POTENTIAL), Significance.LOW, None, None, FunctionalImpact.NOT_SUBSTANTIAL
    )
    assert run(c, ExceptionClause.LOW_POTENTIAL).summary.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "field,value",
    [
        ("connection", AreaConnection.NOT_LIMITED_CONNECTED),
        ("compensation_area", "area-B"),
        ("compensation_purpose", CompensationPurpose.OTHER),
        ("legal_requirement", LegalRequirement.ALREADY_REQUIRED),
        ("adequacy", CompensationAdequacy.INADEQUATE),
        ("approval", PlanApproval.NOT_APPROVED),
        ("binding_period", Interval(datetime(2024, 1, 2, tzinfo=UTC), PERIOD.end)),
    ],
)
def test_protection_plan_real_conditions(field, value):
    c = plan()
    assert run(c, ExceptionClause.PROTECTION_PLAN).summary.finding is CheckFinding.PASS
    assert run(replace(c, **{field: value}), ExceptionClause.PROTECTION_PLAN).summary.finding is CheckFinding.FAIL


@pytest.mark.parametrize(
    "field",
    [
        "plan",
        "area",
        "compensation_area",
        "adequacy_explanation",
        "binding_arrangement",
        "binding_period",
        "concession_period",
        "approval_reference",
        "application_to_foen",
    ],
)
def test_missing_plan_inputs_do_not_pass(field):
    assert (
        run(replace(plan(), **{field: None}), ExceptionClause.PROTECTION_PLAN).summary.finding is CheckFinding.UNKNOWN
    )


def test_emergency_temporary_not_ordinary_scarcity():
    c = EmergencyAbstraction(evidence(ExceptionClause.EMERGENCY), EmergencyBasis.EMERGENCY, "fire emergency", PERIOD)
    assert run(c, ExceptionClause.EMERGENCY).applied_minimum == Flow(10, "l/s")
    assert (
        run(replace(c, basis=EmergencyBasis.ORDINARY_SCARCITY), ExceptionClause.EMERGENCY).summary.finding
        is CheckFinding.FAIL
    )
    assert run(replace(c, temporary_period=None), ExceptionClause.EMERGENCY).summary.finding is CheckFinding.UNKNOWN
    shorter = Interval(datetime(2024, 1, 2, tzinfo=UTC), PERIOD.end)
    assert run(replace(c, temporary_period=shorter), ExceptionClause.EMERGENCY).summary.finding is CheckFinding.FAIL


@pytest.mark.parametrize("clause", list(ExceptionClause))
def test_every_exception_needs_decision(clause):
    cases = {
        ExceptionClause.HIGH_ALTITUDE: high(),
        ExceptionClause.NON_FISH: NonFishWater(evidence(clause), FishStatus.NON_FISH),
        ExceptionClause.LOW_POTENTIAL: LowEcologicalPotential(
            evidence(clause), Significance.LOW, Significance.LOW, "study", FunctionalImpact.NOT_SUBSTANTIAL
        ),
        ExceptionClause.PROTECTION_PLAN: plan(),
        ExceptionClause.EMERGENCY: EmergencyAbstraction(evidence(clause), EmergencyBasis.EMERGENCY, "basis", PERIOD),
    }
    r = assess_exception(Flow(40, "l/s"), Flow(50, "l/s"), SCOPE, cases[clause], None)
    assert r.applied_minimum is None
    assert r.summary.finding is CheckFinding.UNKNOWN


def test_failure_survives_missing_and_unsupported_evidence():
    c = replace(high(), evidence=None)
    r = run(c, ExceptionClause.HIGH_ALTITUDE, q=50)
    assert r.summary.finding is CheckFinding.FAIL
    assert r.summary.completeness is Completeness.INCOMPLETE
    c = replace(
        high(),
        evidence=replace(high().evidence, computability=Computability.UNKNOWN, reasons=("unsupported measurement",)),
    )
    r = run(c, ExceptionClause.HIGH_ALTITUDE)
    assert r.applied_minimum is None
    assert r.summary.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenario", "other"),
        ("member", "other"),
        ("intake", "other"),
        ("extent", DownstreamExtent(0, 500)),
        ("period", Interval(datetime(2024, 1, 2, tzinfo=UTC), PERIOD.end)),
        ("location", replace(SCOPE.location, reach=Reach("other", "v1", SCOPE.location.reach.water_body))),
    ],
)
def test_out_of_scope_decision_cannot_lower(field, value):
    d = decision(ExceptionClause.HIGH_ALTITUDE, scope=replace(SCOPE, **{field: value}))
    r = assess_exception(Flow(40, "l/s"), Flow(50, "l/s"), SCOPE, high(), d)
    assert r.summary.finding is CheckFinding.FAIL
    assert r.applied_minimum is None


def test_numeric_result_keeps_ordinary_protection_and_balancing():
    r = run(high(), ExceptionClause.HIGH_ALTITUDE)
    assert r.ordinary_minimum == Flow(50, "l/s") and r.applied_minimum == Flow(10, "l/s")
    assert "outside the exception" in r.restrictions[0]
    assert "Art. 33" in r.restrictions[1]
    assert run(high(), ExceptionClause.HIGH_ALTITUDE, minimum=50).summary.finding is CheckFinding.FAIL


def test_authorised_requires_admissible_decision_and_conditions():
    clause = ExceptionClause.HIGH_ALTITUDE
    d = replace(decision(clause), basis=DecisionBasis.AUTHORISED)
    assert assess_exception(Flow(40, "l/s"), Flow(50, "l/s"), SCOPE, high(), d).applied_minimum is None
    e = replace(evidence(clause), official_admissibility=OfficialAdmissibility.ADMISSIBLE)
    d = replace(
        d, evidence=replace(e, scope=decision_evidence_scope(SCOPE, clause, d.minimum, d.basis, d.issuer, d.reference))
    )
    c = replace(high(), evidence=replace(e, scope=condition_evidence_scope(SCOPE, clause, high())))
    r = assess_exception(Flow(40, "l/s"), Flow(50, "l/s"), SCOPE, c, d)
    assert r.applied_minimum == Flow(10, "l/s")


@pytest.mark.parametrize("value", ["nan", "inf", True])
def test_invalid_elevation(value):
    with pytest.raises((TypeError, ValueError)):
        Elevation(value)


def test_runtime_domain_validation():
    with pytest.raises(TypeError):
        NonFishWater(None, True)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError):
        replace(plan(), binding_period="2024")
    with pytest.raises(ValueError):
        DownstreamExtent(-1, 1000)


def test_section_version_evidence_cannot_transfer():
    other = replace(SCOPE, location=replace(SCOPE.location, section=CalculationSection("intake", "v2")))
    c = replace(high(), evidence=evidence(ExceptionClause.HIGH_ALTITUDE, other))
    assert run(c, ExceptionClause.HIGH_ALTITUDE).applied_minimum is None


def test_mixed_reference_kinds_cannot_lower():
    from fishy.evidence import ReferenceKind

    c = high()
    e = c.evidence
    c = replace(c, evidence=replace(e, provenance=replace(e.provenance, reference_kind=ReferenceKind.OBSERVED)))
    d = decision(ExceptionClause.HIGH_ALTITUDE)
    d = replace(
        d,
        evidence=replace(
            d.evidence, provenance=replace(d.evidence.provenance, reference_kind=ReferenceKind.FUTURE_CLIMATE_STRESS)
        ),
    )
    r = assess_exception(Flow(40, "l/s"), Flow(50, "l/s"), SCOPE, c, d)
    assert r.applied_minimum is None


def test_effective_minimum_retains_normal_protection_outside_exception():
    from fishy.swiss_exceptions import effective_minimum_for

    r = run(high(), ExceptionClause.HIGH_ALTITUDE)
    assert effective_minimum_for(SCOPE, r) == Flow(10, "l/s")
    inside = replace(SCOPE, extent=DownstreamExtent(500, 900))
    assert effective_minimum_for(inside, r) == Flow(10, "l/s")
    beyond = replace(SCOPE, extent=DownstreamExtent(1000, 2000))
    assert effective_minimum_for(beyond, r) == Flow(50, "l/s")
    after = replace(SCOPE, period=Interval(PERIOD.end, datetime(2024, 3, 1, tzinfo=UTC)))
    assert effective_minimum_for(after, r) == Flow(50, "l/s")
    across = replace(SCOPE, extent=DownstreamExtent(500, 1500))
    assert effective_minimum_for(across, r) is None
    across_time = replace(SCOPE, period=Interval(PERIOD.start, datetime(2024, 3, 1, tzinfo=UTC)))
    assert effective_minimum_for(across_time, r) is None
    assert effective_minimum_for(replace(SCOPE, scenario="other"), r) is None


def test_effective_minimum_cannot_lower_on_unresolved_assessment():
    from fishy.swiss_exceptions import effective_minimum_for

    r = run(replace(high(), evidence=None), ExceptionClause.HIGH_ALTITUDE)
    assert effective_minimum_for(SCOPE, r) is None
    beyond = replace(SCOPE, extent=DownstreamExtent(1000, 2000))
    assert effective_minimum_for(beyond, r) == Flow(50, "l/s")


def test_evidence_configuration_and_data_cannot_transfer():
    c = high()
    for field in ("configuration_version", "data_version"):
        changed = replace(c.evidence, provenance=replace(c.evidence.provenance, **{field: "other"}))
        assert run(replace(c, evidence=changed), ExceptionClause.HIGH_ALTITUDE).applied_minimum is None


def test_reviewed_decision_amount_cannot_be_replaced():
    d = decision(ExceptionClause.HIGH_ALTITUDE)
    c = high()
    d = replace(d, minimum=Flow(1, "l/s"))
    assert assess_exception(Flow(40, "l/s"), Flow(50, "l/s"), SCOPE, c, d).applied_minimum is None


def test_reviewed_condition_content_cannot_be_replaced():
    c = high(1600, FishStatus.FISH)
    c = replace(c, fish_status=FishStatus.NON_FISH)
    assert (
        assess_exception(
            Flow(40, "l/s"), Flow(50, "l/s"), SCOPE, c, decision(ExceptionClause.HIGH_ALTITUDE)
        ).applied_minimum
        is None
    )


def test_effective_minimum_recomputes_replaced_derived_value():
    from fishy.swiss_exceptions import effective_minimum_for

    assessed = run(high(), ExceptionClause.HIGH_ALTITUDE)
    altered = replace(assessed, applied_minimum=Flow(0, "l/s"))
    assert effective_minimum_for(SCOPE, altered) == Flow(10, "l/s")
