"""Synthetic witnesses for GSchG Arts. 4(k–l), 35–36 and FOEN 2000 §§4.3, 4.9."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.duties import Delivery, DutyApplicability, Obligation, SuppliedDuty
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
)
from fishy.flows import Coverage, FlowSample, Presence
from fishy.quantities import Elevation, Flow, FlowBounds, Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.swiss_balancing import (
    AbstractionInterest,
    ApplicantAlternatives,
    BalancingBasis,
    BalancingDecision,
    InterestConsideration,
    assess_balancing,
    balancing_decision_scope,
    balancing_scope,
)
from fishy.swiss_delivery import (
    ConditionFinding,
    ExchangeRole,
    FlowProof,
    IntakeRelationship,
    ProofMethod,
    ProtectiveMeasure,
    RoutingExchange,
    WaterBalance,
    assess_swiss_delivery,
    delivery_scope,
    derive_intake_schedule,
    proof_scope,
    relationship_scope,
    specialist_scope,
)
from fishy.swiss_safeguards import (
    FishFunction,
    FlowNeed,
    Safeguard,
    SafeguardSite,
    SafeguardStudy,
    SafeguardTreatment,
    SafeguardUse,
    assess_safeguards,
    safeguard_study_scope,
)
from fishy.time import Interval


def location(point="intake", reach="river"):
    return Location(Reach(reach, "v1", WaterBody("body", "v1")), CalculationSection(point, "v1"), "map-v1")


def sample(value, point="intake", day=0):
    start = datetime(2024, 2, 28, tzinfo=UTC) + timedelta(days=day)
    return FlowSample(
        location(point),
        Interval(start, start + timedelta(days=1)),
        Flow(value, "l/s"),
        Presence.PRESENT,
        Provenance(
            "synthetic site study",
            "scenario",
            "member",
            "v1",
            "v1",
            "v1",
            ProductionMethod.ILLUSTRATIVE,
            CorrectionState.ORIGINAL,
            ReferenceKind.MANAGED,
        ),
    )


def findings(s, use):
    return EvidenceFindings(
        delivery_scope(s, use, intake=location() if use == "intake_prescription" else None),
        s.provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("supplied synthetic acceptance, not certification",),
    )


def specialist_findings(s, use, subject):
    return replace(findings(s, use), scope=specialist_scope(s.location, s.interval, s.provenance, use, subject))


def proof_balance(s, error=0):
    volume = s.value.value * s.interval.seconds
    return WaterBalance(Volume(0), Volume(volume), Volume(volume - error), Volume(0), Volume(0), "exact source account")


def balance(error=0):
    return WaterBalance(Volume(0), Volume(100), Volume(100 - error), Volume(0), Volume(0), "synthetic exact account")


def relationship(need, *, exchanges=(), upper=1000):
    domain = FlowBounds(Flow(0), Flow(upper, "l/s"), "supported input domain", "study", "joint scenario")
    account = balance()
    source = "supplied zero-delay affine site relation"
    scope = relationship_scope(location(), need, Fraction(1), domain, exchanges, account, source)
    return IntakeRelationship(
        location(),
        need,
        Fraction(1),
        domain,
        exchanges,
        replace(findings(need, "intake_prescription"), scope=scope),
        account,
        source,
    )


def reviewed_relationship(relation, **changes):
    fields = ("intake", "downstream", "transmission", "intake_domain", "exchanges", "balance", "relation_source")
    values = {key: getattr(relation, key) for key in fields}
    values.update(changes)
    scope = relationship_scope(**values)
    return IntakeRelationship(**values, evidence=replace(relation.evidence, scope=scope))


def balanced_need(need, upper=10000):
    site = SafeguardSite("site", need, Flow(160, "l/s"), Elevation(700), FishFunction.NEITHER, "synthetic inventory")
    studies = []
    for safeguard in Safeguard:
        flow_need = FlowNeed(Flow(0), Flow(0), Flow(upper, "l/s"), "supplied site relation", "supported criterion")
        evidence = replace(
            findings(need, "safeguard"),
            scope=safeguard_study_scope(site, safeguard, SafeguardTreatment.FLOW_REQUIREMENT, flow_need=flow_need),
        )
        studies.append(
            SafeguardStudy(
                site.identifier,
                safeguard,
                need.location,
                evidence,
                SafeguardTreatment.FLOW_REQUIREMENT,
                "supplied supported relationship",
                flow_need,
            )
        )
    safeguards = assess_safeguards((site,), tuple(studies), use=SafeguardUse.SCENARIO)
    evidence = replace(findings(need, "balancing"), scope=balancing_scope((need,), (need,)))
    decision = BalancingDecision(
        "decision",
        "scenario modeller",
        "supplied balancing",
        BalancingBasis.HYPOTHETICAL,
        (need,),
        tuple(InterestConsideration(i, "considered", evidence) for i in AbstractionInterest),
        ApplicantAlternatives("applicant", "alternatives", "energy costs", "effects", "mitigation", evidence),
        None,
    )
    decision = replace(decision, evidence=replace(evidence, scope=balancing_decision_scope((need,), decision)))
    return assess_balancing((need,), safeguards.summary, decision, safeguards=safeguards)


def derive(minima, needs, relations, **kwargs):
    return derive_intake_schedule(
        minima,
        needs,
        relations,
        provenance=minima[0].provenance,
        upstream_checks=kwargs.pop(
            "upstream_checks", CheckSummary((Check("safeguards_and_balancing", CheckFinding.PASS),))
        ),
        downstream_assessments=kwargs.pop("downstream_assessments", tuple(balanced_need(n) for n in needs)),
        **kwargs,
    )


def duty(values=(220,)):
    return SuppliedDuty(
        "existing Swiss duty",
        "v1",
        "GSchG Art. 35 supplied decision",
        DutyApplicability.HYPOTHETICAL,
        tuple(Obligation(sample(q, day=i), "v1") for i, q in enumerate(values)),
        "supplied historical duty; sizing unavailable",
    )


def proof(s, use="inflow_proof", method=ProofMethod.MEASUREMENT, **kwargs):
    evidence = replace(findings(s, use), scope=proof_scope(s, method, use, **kwargs))
    return FlowProof(s, method, evidence, **kwargs)


def test_downstream_gains_losses_abstractions_and_return_points():
    minimum, need = sample(130), sample(220, "fish_passage")
    exchanges = tuple(
        RoutingExchange(name, role, sample(q, name))
        for name, role, q in (
            ("tributary", ExchangeRole.GAIN, 50),
            ("seepage", ExchangeRole.LOSS, 20),
            ("other_intake", ExchangeRole.ABSTRACTION, 10),
        )
    )
    relation = relationship(need, exchanges=exchanges)
    result = derive((minimum,), (need,), (relation,))
    assert result.schedule[0].value == Flow(200, "l/s")  # 200 + 50 - 20 - 10 = 220
    assert result.summary.finding is CheckFinding.PASS
    below_return = sample(260, "below_powerhouse_return")
    changed = derive((minimum,), (need, below_return), (relation, relationship(below_return)))
    assert changed.schedule[0].value == Flow(260, "l/s")
    assert result.schedule[0].value == Flow(200, "l/s")
    assert changed.downstream_needs == (need, below_return)


def test_exact_seasonal_schedule_keeps_intake_minima_and_separate_measures():
    minima = (sample(130), sample(180, day=1))
    needs = (sample(160, "habitat"), sample(220, "habitat", day=1))
    relations = tuple(relationship(n) for n in needs)
    measure = ProtectiveMeasure(
        "fish_access",
        needs[0].location,
        needs[0].interval,
        "supplied barrier removal",
        specialist_findings(needs[0], "protective_measure", ("fish_access", "supplied barrier removal")),
    )
    result = derive(minima, needs, relations, measures=(measure,))
    assert tuple(s.value for s in result.schedule) == (Flow(160, "l/s"), Flow(220, "l/s"))
    assert result.schedule[1].interval.start.day == 29
    assert result.measures == (measure,)
    assert result.intake_minima == minima
    high_gain = RoutingExchange("gain", ExchangeRole.GAIN, sample(500, "gain"))
    retained = derive((minima[0],), (needs[0],), (relationship(needs[0], exchanges=(high_gain,)),))
    assert retained.schedule[0].value == Flow(130, "l/s")


def test_explicit_transmission_not_topology_sum_and_infeasible_domain():
    need = sample(220, "downstream")
    relation = reviewed_relationship(relationship(need), transmission=Fraction(4, 5))
    result = derive((sample(130),), (need,), (relation,))
    assert result.schedule[0].value == Flow(275, "l/s")
    outside = derive(
        (sample(130),),
        (need,),
        (reviewed_relationship(relation, intake_domain=replace(relation.intake_domain, upper=Flow(250, "l/s"))),),
    )
    assert outside.summary.finding is CheckFinding.FAIL
    assert outside.schedule[0].presence is Presence.UNSUPPORTED


def test_missing_relationship_and_failed_balance_survive_incomplete_coverage():
    need, missing = sample(220, "downstream"), sample(300, "farther_downstream")
    failed = reviewed_relationship(relationship(need), balance=balance(1))
    result = derive((sample(130),), (need, missing), (failed,))
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert result.schedule[0].value is None
    assert derive((sample(130),), (need,), ()).summary.finding is CheckFinding.UNKNOWN
    assert derive((sample(130),), (), ()).summary.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "gate",
    [
        CheckSummary(()),
        CheckSummary((Check("missing", CheckFinding.UNKNOWN),)),
        CheckSummary((Check("failed", CheckFinding.FAIL), Check("missing", CheckFinding.UNKNOWN))),
    ],
)
def test_upstream_coverage_cannot_be_laundered_into_complete_prescription(gate):
    need = sample(220, "downstream")
    result = derive((sample(130),), (need,), (relationship(need),), upstream_checks=gate)
    assert result.schedule[0].presence is Presence.UNSUPPORTED
    assert result.summary.finding is gate.finding
    assert result.summary.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize("state", [Presence.MISSING, Presence.ABSENT, Presence.OUTSIDE_HORIZON, Presence.UNSUPPORTED])
def test_physical_support_is_preserved_not_used_as_zero(state):
    need = sample(220, "downstream")
    missing = replace(sample(50, "gain"), value=None, presence=state, reasons=("source output unsupported",))
    relation = relationship(need, exchanges=(RoutingExchange("gain", ExchangeRole.GAIN, missing),))
    result = derive((sample(130),), (need,), (relation,))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.schedule[0].value is None
    assert result.relationships[0].exchanges[0].sample.presence is state


def test_art36_exact_low_inflow_preserves_nominal_and_shortfall():
    issued = duty()
    inflow, actual = sample(150), sample(120)
    result = assess_swiss_delivery(
        issued,
        (Delivery(actual, "v1"),),
        inflow_proofs=(proof(inflow),),
        delivery_proofs=(proof(actual, "delivery_proof"),),
    )
    assert result.nominal_duty == issued
    assert result.nominal_duty.schedule[0].sample.value == Flow(220, "l/s")
    assert result.adjustments[0].justified.sample.value == Flow(150, "l/s")
    assert result.delivery.intervals[0].shortfall == Flow(30, "l/s")
    assert result.delivery.known_shortfall_volume == Volume(2592)
    assert result.control_evidence.finding is CheckFinding.PASS
    assert result.adjustments[0].inflow_proof is not None
    assert result.adjustments[0].inflow_proof.sample is inflow
    assert result.adjustments[0].inflow_proof.evidence.official_admissibility is OfficialAdmissibility.PENDING
    with pytest.raises(FrozenInstanceError):
        issued.version = "changed"


def test_existing_duty_independent_sizing_no_proof_no_relief_no_retroactive_tributary():
    issued, actual = duty(), sample(120)
    result = assess_swiss_delivery(issued, (Delivery(actual, "v1"),))
    assert result.delivery.intervals[0].shortfall == Flow(100, "l/s")
    assert result.adjustments[0].justified == issued.schedule[0]
    assert result.control_evidence.finding is CheckFinding.UNKNOWN
    # Calculating a different future schedule has no link to the issued intake duty.
    need = sample(220, "downstream")
    gain = RoutingExchange("new_gain", ExchangeRole.GAIN, sample(100, "tributary"))
    derive((sample(50),), (need,), (relationship(need, exchanges=(gain,)),))
    assert result.nominal_duty.schedule[0].sample.value == Flow(220, "l/s")


@pytest.mark.parametrize(
    "justification,error,expected",
    [
        (None, 0, 220),
        ("measurement burden unreasonable at this site", 0, 150),
        ("measurement burden unreasonable at this site", 1, 220),
    ],
)
def test_water_balance_relief_requires_unreasonable_measurement_and_closure(justification, error, expected):
    inflow = proof(
        sample(150),
        method=ProofMethod.WATER_BALANCE,
        balance=proof_balance(sample(150), error),
        unreasonable_measurement=justification,
    )
    result = assess_swiss_delivery(duty(), (Delivery(sample(120), "v1"),), inflow_proofs=(inflow,))
    assert result.adjustments[0].justified.sample.value == Flow(expected, "l/s")
    if error:
        assert result.adjustments[0].proof_summary.finding is CheckFinding.FAIL


@pytest.mark.parametrize("value,expected", [(0, 0), (150, 150), (220, 220), (300, 220)])
def test_all_inflow_threshold_and_present_zero(value, expected):
    result = assess_swiss_delivery(duty(), (Delivery(sample(0), "v1"),), inflow_proofs=(proof(sample(value)),))
    assert result.adjustments[0].justified.sample.value == Flow(expected, "l/s")


def test_partial_rejected_and_uncertain_inflow_cannot_manufacture_relief():
    base = sample(150)
    inputs = [
        proof(replace(base, coverage=Coverage.PARTIAL, reasons=("partial gauge interval",))),
        replace(
            proof(base),
            evidence=replace(proof(base).evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED),
        ),
        proof(
            replace(base, uncertainty=FlowBounds(Flow(140, "l/s"), Flow(160, "l/s"), "interval", "gauge", "unknown"))
        ),
    ]
    for inflow in inputs:
        result = assess_swiss_delivery(duty(), (), inflow_proofs=(inflow,))
        assert result.adjustments[0].justified.sample.value == Flow(220, "l/s")
        assert result.adjustments[0].proof_summary.finding is not CheckFinding.PASS


def test_same_release_compliance_different_specialist_conditions():
    supplied = sample(220)
    evidence = specialist_findings(supplied, "specialist_condition", ("HYDMOD hydropeaking", "class 5"))
    hydropeaking = ConditionFinding(supplied.location, supplied.interval, "HYDMOD hydropeaking", "class 5", evidence)
    seasonality = replace(
        hydropeaking,
        indicator="seasonality",
        result="class 1",
        evidence=specialist_findings(supplied, "specialist_condition", ("seasonality", "class 1")),
    )
    a = assess_swiss_delivery(duty(), (Delivery(supplied, "v1"),), conditions=(hydropeaking,))
    b = assess_swiss_delivery(duty(), (Delivery(supplied, "v1"),), conditions=(seasonality,))
    assert a.delivery == b.delivery
    assert a.delivery.summary.finding is CheckFinding.PASS
    assert a.conditions != b.conditions
    assert a.conditions[0].evidence is evidence


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenario", "other"),
        ("reference_member", "other"),
        ("reference_kind", ReferenceKind.OBSERVED),
        ("configuration_version", "v2"),
    ],
)
def test_mixed_scenario_member_reference_configuration_rejected(field, value):
    s = sample(150)
    changed = replace(s, provenance=replace(s.provenance, **{field: value}))
    with pytest.raises(ValueError, match="identity"):
        assess_swiss_delivery(duty(), (), inflow_proofs=(proof(changed),))
    with pytest.raises(ValueError, match="identity"):
        assess_swiss_delivery(duty(), (Delivery(changed, "v1"),))


def test_wrong_proof_scope_point_period_or_condition_rejected():
    for s in (sample(150, "tributary"), sample(150, day=1)):
        with pytest.raises(ValueError, match="exact"):
            assess_swiss_delivery(duty(), (), inflow_proofs=(proof(s),))
    incorrect = proof(sample(150), "wrong_use")
    with pytest.raises(ValueError, match="evidence"):
        assess_swiss_delivery(duty(), (), inflow_proofs=(incorrect,))
    other = replace(sample(220), location=location(reach="another_reach"))
    condition = ConditionFinding(
        other.location,
        other.interval,
        "HYDMOD",
        "class 1",
        specialist_findings(other, "specialist_condition", ("HYDMOD", "class 1")),
    )
    with pytest.raises(ValueError, match="same prescribed reach"):
        assess_swiss_delivery(duty(), (), conditions=(condition,))


def test_delivery_known_failure_plus_unsupported_and_control_balance_failure():
    actual = sample(120)
    unknown = replace(
        sample(300, day=1), value=None, presence=Presence.UNSUPPORTED, reasons=("imported physical account failed",)
    )
    result = assess_swiss_delivery(
        duty((220, 220)),
        (Delivery(actual, "v1"), Delivery(unknown, "v1")),
        delivery_proofs=(
            proof(
                actual,
                "delivery_proof",
                ProofMethod.WATER_BALANCE,
                balance=balance(1),
                unreasonable_measurement="supported site justification",
            ),
        ),
    )
    assert result.delivery.summary.finding is CheckFinding.FAIL
    assert result.delivery.summary.completeness is Completeness.INCOMPLETE
    assert result.control_evidence.finding is CheckFinding.FAIL
    assert result.control_evidence.completeness is Completeness.INCOMPLETE
    assert result.delivery.intervals[1].delivery is not None
    assert result.delivery.intervals[1].delivery.sample is unknown


def test_relation_domain_enums_and_duplicate_accounts_rejected():
    need = sample(220, "downstream")
    for coefficient in (0, 1.0, Fraction(0), Fraction(2)):
        with pytest.raises(ValueError, match="Fraction"):
            replace(relationship(need), transmission=coefficient)
    with pytest.raises(TypeError):
        RoutingExchange("gain", "gain", sample(50))  # ty: ignore[invalid-argument-type]
    exchange = RoutingExchange("shared", ExchangeRole.GAIN, sample(50))
    with pytest.raises(ValueError, match="duplicate"):
        relationship(need, exchanges=(exchange, exchange))
    with pytest.raises(ValueError, match="duplicate"):
        derive((sample(130),), (need, need), ())
    with pytest.raises(ValueError, match="duplicate"):
        assess_swiss_delivery(duty(), (), inflow_proofs=(proof(sample(150)), proof(sample(150))))


def test_required_measure_rejection_or_wrong_use_cannot_pass_prescription():
    need = sample(220, "downstream")
    evidence = replace(
        specialist_findings(need, "protective_measure", ("required_measure", "required habitat measure")),
        scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED,
    )
    measure = ProtectiveMeasure("required_measure", need.location, need.interval, "required habitat measure", evidence)
    result = derive((sample(130),), (need,), (relationship(need),), measures=(measure,))
    assert result.summary.finding is CheckFinding.FAIL
    assert result.schedule[0].presence is Presence.UNSUPPORTED
    with pytest.raises(ValueError, match="intended use"):
        derive(
            (sample(130),),
            (need,),
            (relationship(need),),
            measures=(replace(measure, evidence=findings(need, "wrong_use")),),
        )


def test_unrelated_closed_balance_cannot_prove_low_inflow_or_delivery():
    s = sample(150)
    inflow = proof(s, method=ProofMethod.WATER_BALANCE, balance=balance(), unreasonable_measurement="site study")
    result = assess_swiss_delivery(
        duty(),
        (Delivery(s, "v1"),),
        inflow_proofs=(inflow,),
        delivery_proofs=(
            proof(
                s, "delivery_proof", ProofMethod.WATER_BALANCE, balance=balance(), unreasonable_measurement="site study"
            ),
        ),
    )
    assert result.adjustments[0].justified.sample.value == Flow(220, "l/s")
    assert result.adjustments[0].proof_summary.finding is CheckFinding.FAIL
    assert result.control_evidence.finding is CheckFinding.FAIL


def test_simulated_measurement_cannot_enable_relief():
    s = sample(150)
    simulated = replace(s, provenance=replace(s.provenance, production_method=ProductionMethod.SIMULATED))
    result = assess_swiss_delivery(duty(), (), inflow_proofs=(proof(simulated),))
    assert result.adjustments[0].justified.sample.value == Flow(220, "l/s")
    assert result.adjustments[0].proof_summary.finding is CheckFinding.FAIL


def test_hypothetical_inflow_cannot_lower_authenticated_duty():
    issued = replace(duty(), applicability=DutyApplicability.APPLICABLE)
    result = assess_swiss_delivery(issued, (), inflow_proofs=(proof(sample(150)),))
    assert result.adjustments[0].justified.sample.value == Flow(220, "l/s")


def test_same_reach_other_control_point_or_data_version_cannot_reuse_evidence():
    need = sample(220, "one")
    original = relationship(need)
    with pytest.raises(ValueError, match="evidence"):
        replace(original, downstream=replace(need, location=location("two")))
    with pytest.raises(ValueError, match="evidence"):
        replace(original, downstream=replace(need, provenance=replace(need.provenance, data_version="v2")))


def test_routing_evidence_cannot_move_to_another_intake():
    need = sample(220, "downstream")
    with pytest.raises(ValueError, match="evidence"):
        replace(relationship(need), intake=location("another_intake"))


def test_specialist_evidence_cannot_move_within_reach_or_change_result():
    s = sample(220)
    evidence = specialist_findings(s, "specialist_condition", ("HYDMOD", "class 1"))
    condition = ConditionFinding(s.location, s.interval, "HYDMOD", "class 1", evidence)
    with pytest.raises(ValueError, match="evidence"):
        replace(condition, location=location("other_point"))
    with pytest.raises(ValueError, match="evidence"):
        replace(condition, result="class 5")


def test_observed_delivery_cannot_make_hypothetical_relief_observed_compliance():
    from fishy.duties import ComparisonKind

    actual = sample(120)
    observed = replace(actual, provenance=replace(actual.provenance, production_method=ProductionMethod.OBSERVED))
    result = assess_swiss_delivery(duty(), (Delivery(observed, "v1"),), inflow_proofs=(proof(sample(150)),))
    assert result.delivery.interpretation is ComparisonKind.PREDICTION


def test_authenticated_observed_proof_remains_independently_runnable():
    from fishy.duties import ComparisonKind

    issued = replace(duty(), applicability=DutyApplicability.APPLICABLE)
    inflow = sample(150)
    actual = sample(120)
    inflow = replace(inflow, provenance=replace(inflow.provenance, production_method=ProductionMethod.OBSERVED))
    actual = replace(actual, provenance=replace(actual.provenance, production_method=ProductionMethod.OBSERVED))
    result = assess_swiss_delivery(
        issued,
        (Delivery(actual, "v1"),),
        inflow_proofs=(proof(inflow),),
        delivery_proofs=(proof(actual, "delivery_proof"),),
    )
    assert result.delivery.interpretation is ComparisonKind.OBSERVATION
    assert result.delivery.intervals[0].shortfall == Flow(30, "l/s")
    assert result.control_evidence.finding is CheckFinding.PASS


def test_proof_value_support_or_data_cannot_be_replaced_with_accepted_findings():
    original = proof(
        sample(150),
        method=ProofMethod.WATER_BALANCE,
        balance=proof_balance(sample(150)),
        unreasonable_measurement="site justification",
    )
    changed_samples = (
        replace(original.sample, value=Flow(1, "l/s")),
        replace(original.sample, coverage=Coverage.PARTIAL, reasons=("partial",)),
        replace(original.sample, provenance=replace(original.sample.provenance, data_version="v2")),
    )
    for changed in changed_samples:
        with pytest.raises(ValueError, match="evidence"):
            assess_swiss_delivery(duty(), (), inflow_proofs=(replace(original, sample=changed),))


def test_relationship_parameters_cannot_change_under_existing_acceptance():
    relation = relationship(sample(220, "downstream"))
    alterations = (
        {"transmission": Fraction(1, 10)},
        {"intake_domain": replace(relation.intake_domain, upper=Flow(5000, "l/s"))},
        {"exchanges": (RoutingExchange("gain", ExchangeRole.GAIN, sample(50)),)},
        {"balance": balance(1)},
        {"relation_source": "other relation"},
    )
    for alteration in alterations:
        with pytest.raises(ValueError, match="evidence"):
            replace(relation, **alteration)


def test_proof_balance_tolerance_cannot_change_under_existing_findings():
    s = sample(150)
    original = proof(
        s, method=ProofMethod.WATER_BALANCE, balance=proof_balance(s, 1), unreasonable_measurement="site justification"
    )
    before = assess_swiss_delivery(duty(), (), inflow_proofs=(original,))
    assert before.adjustments[0].proof_summary.finding is CheckFinding.FAIL
    assert original.balance is not None
    with pytest.raises(ValueError, match="evidence"):
        changed = replace(original, balance=replace(original.balance, tolerance=Volume(1)))
        assess_swiss_delivery(duty(), (), inflow_proofs=(changed,))


def test_free_upstream_pass_without_actual_downstream_assessments_cannot_issue():
    need = sample(220, "downstream")
    result = derive_intake_schedule(
        (sample(130),),
        (need,),
        (relationship(need),),
        provenance=need.provenance,
        upstream_checks=CheckSummary((Check("claimed_full_pass", CheckFinding.PASS),)),
    )
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.schedule[0].presence is Presence.UNSUPPORTED


def test_shared_release_rechecks_actual_downstream_safeguard_domain():
    first, second = sample(180, "first"), sample(300, "second")
    a, b = balanced_need(first, upper=200), balanced_need(second)
    assert a.summary.finding is CheckFinding.PASS
    assert b.summary.finding is CheckFinding.PASS
    result = derive(
        (sample(130),), (first, second), (relationship(first), relationship(second)), downstream_assessments=(a, b)
    )
    assert result.summary.finding is CheckFinding.FAIL
    assert result.schedule[0].presence is Presence.UNSUPPORTED
    assert result.numerical_schedule[0].value == Flow(300, "l/s")
    assert tuple(s.value for s in result.projected_downstream) == (Flow(300, "l/s"), Flow(300, "l/s"))


def test_cached_balancing_pass_cannot_replace_actual_studies_or_need():
    need = sample(220, "downstream")
    original = balanced_need(need)
    assert original.safeguards is not None
    missing = replace(original.safeguards, sites=tuple(replace(s, studies=()) for s in original.safeguards.sites))
    result = derive(
        (sample(130),), (need,), (relationship(need),), downstream_assessments=(replace(original, safeguards=missing),)
    )
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.schedule[0].presence is Presence.UNSUPPORTED
    assert result.numerical_schedule[0].value == Flow(220, "l/s")


def test_projected_numeric_result_does_not_become_an_observation():
    need = sample(220, "downstream")
    need = replace(need, provenance=replace(need.provenance, production_method=ProductionMethod.OBSERVED))
    result = derive_intake_schedule(
        (sample(130),),
        (need,),
        (relationship(need),),
        provenance=sample(130).provenance,
        upstream_checks=CheckSummary((Check("claimed", CheckFinding.PASS),)),
    )
    assert result.projected_downstream[0].provenance.production_method is not ProductionMethod.OBSERVED


def test_scoped_exception_and_normal_protection_beyond_reach_remain_separate():
    from fishy.swiss_exceptions import (
        DecisionBasis,
        DownstreamExtent,
        ExceptionClause,
        ExceptionDecision,
        ExceptionScope,
        FishStatus,
        NonFishWater,
        assess_exception,
        condition_evidence_scope,
        decision_evidence_scope,
    )

    need = sample(35, "exception_point")
    scope = ExceptionScope(
        need.location,
        "intake",
        need.provenance.scenario,
        need.provenance.reference_member,
        need.interval,
        DownstreamExtent(0, 1000),
        need.provenance.configuration_version,
        need.provenance.data_version,
    )
    conditions = NonFishWater(None, FishStatus.NON_FISH)
    conditions = replace(
        conditions,
        evidence=replace(
            findings(need, "exception"), scope=condition_evidence_scope(scope, ExceptionClause.NON_FISH, conditions)
        ),
    )
    decision_scope = decision_evidence_scope(
        scope, ExceptionClause.NON_FISH, Flow(35, "l/s"), DecisionBasis.HYPOTHETICAL, "modeller", "explicit scenario"
    )
    decision = ExceptionDecision(
        scope,
        ExceptionClause.NON_FISH,
        Flow(35, "l/s"),
        DecisionBasis.HYPOTHETICAL,
        "modeller",
        "explicit scenario",
        replace(findings(need, "exception"), scope=decision_scope),
    )
    exception = assess_exception(Flow(100, "l/s"), Flow(130, "l/s"), scope, conditions, decision)
    original = balanced_need(need)
    special = assess_balancing((need,), exception.summary, original.decision, exception=exception)
    assert special.summary.finding is CheckFinding.PASS
    farther = sample(130, "beyond_exception")
    result = derive(
        (sample(35),),
        (need, farther),
        (relationship(need), relationship(farther)),
        downstream_assessments=(special, balanced_need(farther)),
    )
    assert result.summary.finding is CheckFinding.PASS
    assert result.schedule[0].value == Flow(130, "l/s")
    missing = derive(
        (sample(35),), (need, farther), (relationship(need), relationship(farther)), downstream_assessments=(special,)
    )
    assert missing.summary.finding is CheckFinding.UNKNOWN
    assert missing.schedule[0].presence is Presence.UNSUPPORTED
    assert missing.numerical_schedule[0].value == Flow(130, "l/s")


def test_missing_third_mapping_preserves_known_shared_lower_bound_contradiction():
    first, second, third = sample(180, "first"), sample(300, "second"), sample(100, "third")
    result = derive(
        (sample(130),),
        (first, second, third),
        (relationship(first), relationship(second)),
        downstream_assessments=(balanced_need(first, upper=200), balanced_need(second), balanced_need(third)),
    )
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert result.schedule[0].presence is Presence.UNSUPPORTED
    assert result.numerical_schedule[0].presence is Presence.UNSUPPORTED
    assert result.numerical_schedule[0].value is None


def test_unmapped_large_need_cannot_invent_a_supported_lower_bound_failure():
    first, second, third = sample(180, "first"), sample(300, "second"), sample(100, "third")
    result = derive(
        (sample(130),),
        (first, second, third),
        (relationship(first),),
        downstream_assessments=(balanced_need(first, upper=200), balanced_need(second), balanced_need(third)),
    )
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert not any(":lower_bound:" in c.check_id and c.finding is CheckFinding.FAIL for c in result.summary.checks)


def test_missing_mapping_cannot_erase_known_intake_minimum_upper_domain_conflict():
    first, missing = sample(180, "first"), sample(100, "missing")
    result = derive(
        (sample(300),),
        (first, missing),
        (relationship(first),),
        downstream_assessments=(balanced_need(first, upper=200), balanced_need(missing)),
    )
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert result.numerical_schedule[0].presence is Presence.UNSUPPORTED
