"""Synthetic Art. 33 witnesses, independent of private source fixtures."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

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
    ScientificAdequacy,
)
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow
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
from fishy.time import Interval


def inputs(values=(180,), final=220):
    provenance = Provenance(
        "synthetic study",
        "hypothesis",
        "member",
        "test",
        "v1",
        "v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    location = Location(Reach("reach", "v1", WaterBody("river", "v1")), CalculationSection("point", "v1"), "v1")
    samples = tuple(
        FlowSample(
            location,
            Interval(datetime(2020, i + 1, 1, tzinfo=UTC), datetime(2020, i + 2, 1, tzinfo=UTC)),
            Flow(v, "l/s"),
            Presence.PRESENT,
            provenance,
        )
        for i, v in enumerate(values)
    )
    final_total = tuple(replace(s, value=Flow(final, "l/s")) for s in samples)
    evidence = EvidenceFindings(
        balancing_scope(samples, final_total),
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic supported scenario",),
    )
    decision = BalancingDecision(
        "synthetic decision",
        "scenario modeller",
        "supplied non-weighted judgement",
        BalancingBasis.HYPOTHETICAL,
        final_total,
        tuple(InterestConsideration(i, "considered in supplied study", evidence) for i in AbstractionInterest),
        ApplicantAlternatives(
            "applicant",
            "alternative rates compared",
            "cost/production effects",
            "protected interests assessed",
            "prevention measures assessed",
            evidence,
        ),
        None,
    )
    decision = replace(decision, evidence=replace(evidence, scope=balancing_decision_scope(samples, decision)))
    summary = CheckSummary((Check("safeguards", CheckFinding.PASS),))
    return samples, summary, decision


def safeguards_for(samples, upper=1000):
    from fishy.quantities import Elevation
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

    sites, studies = [], []
    for index, sample in enumerate(samples):
        site = SafeguardSite(
            str(index),
            sample,
            Flow(160, "l/s"),
            Elevation(700),
            FishFunction.SPAWNING_OR_REARING,
            "synthetic inventory",
        )
        sites.append(site)
        for safeguard in Safeguard:
            need = FlowNeed(Flow(0), Flow(0), Flow(upper, "l/s"), "supported relationship", "site criterion")
            findings = EvidenceFindings(
                safeguard_study_scope(site, safeguard, SafeguardTreatment.FLOW_REQUIREMENT, flow_need=need),
                sample.provenance,
                Computability.COMPUTABLE,
                NumericalValidity.VALID,
                Disclosure.COMPLETE,
                ScientificAdequacy.ACCEPTED,
                OfficialAdmissibility.PENDING,
                ("synthetic relationship",),
            )
            studies.append(
                SafeguardStudy(
                    site.identifier,
                    safeguard,
                    sample.location,
                    findings,
                    SafeguardTreatment.FLOW_REQUIREMENT,
                    "synthetic requirement",
                    need,
                )
            )
    return assess_safeguards(tuple(sites), tuple(studies), use=SafeguardUse.FINAL_SIZING)


def assess_supported(minimum, summary, decision):
    return assess_balancing(minimum, summary, decision, safeguards=safeguards_for(minimum))


def test_supported_final_is_total_not_added_and_hypothetical_stays_hypothetical():
    minimum, summary, decision = inputs()
    result = assess_supported(minimum, summary, decision)
    assert result.supported_final_total[0].value == Flow(220, "l/s")
    assert result.preceding_minimum[0].value == Flow(180, "l/s")
    assert result.summary.finding is CheckFinding.PASS
    assert result.official.finding is CheckFinding.UNKNOWN
    assert result.decision.basis is BalancingBasis.HYPOTHETICAL


@pytest.mark.parametrize("interest", tuple(AbstractionInterest))
def test_every_enumerated_interest_is_required(interest):
    minimum, summary, decision = inputs()
    result = assess_supported(
        minimum,
        summary,
        replace(decision, interests=tuple(i for i in decision.interests if i.interest is not interest)),
    )
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.supported_final_total == ()


def test_report_and_decision_required_even_after_exception():
    minimum, summary, decision = inputs((35,))
    for supplied in (None, replace(decision, applicant_report=None)):
        result = assess_supported(minimum, summary, supplied)
        assert result.summary.finding is CheckFinding.UNKNOWN
        assert not result.supported_final_total


def test_seasonal_minimum_failure_survives_missing_interest():
    minimum, summary, decision = inputs((180, 250))
    result = assess_supported(minimum, summary, replace(decision, interests=()))
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert not result.supported_final_total
    assert decision.final_total[1].value == Flow(220, "l/s")


def test_preceding_failure_is_not_erased_by_economics():
    minimum, _, decision = inputs()
    summary = CheckSummary((Check("habitat", CheckFinding.FAIL), Check("quality", CheckFinding.UNKNOWN)))
    result = assess_supported(minimum, summary, decision)
    assert result.balancing_summary.finding is CheckFinding.PASS
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert result.preceding_summary is summary
    assert not result.supported_final_total


@pytest.mark.parametrize("field", ("scenario", "reference_member", "reference_kind"))
def test_cross_identity_final_cannot_supply_a_decision(field):
    from fishy.evidence import ReferenceKind

    minimum, summary, decision = inputs()
    target = decision.final_total[0]
    value = ReferenceKind.MANAGED if field == "reference_kind" else "other"
    target = replace(target, provenance=replace(target.provenance, **{field: value}))
    with pytest.raises(ValueError, match="exact location"):
        assess_supported(minimum, summary, replace(decision, final_total=(target,)))


def test_wrong_location_or_interval_cannot_transfer():
    minimum, summary, decision = inputs()
    target = decision.final_total[0]
    target = replace(target, location=replace(target.location, mapping_version="other"))
    with pytest.raises(ValueError, match="exact location"):
        assess_supported(minimum, summary, replace(decision, final_total=(target,)))
    other = replace(
        decision.final_total[0], interval=Interval(datetime(2021, 1, 1, tzinfo=UTC), datetime(2021, 2, 1, tzinfo=UTC))
    )
    with pytest.raises(ValueError, match="exact preceding"):
        assess_supported(minimum, summary, replace(decision, final_total=(other,)))


def test_missing_schedule_interval_and_empty_preceding_checks_cannot_pass():
    minimum, summary, decision = inputs((180, 180))
    result = assess_supported(minimum, summary, replace(decision, final_total=decision.final_total[:1]))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert assess_supported(minimum, CheckSummary(()), decision).summary.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("change", ("scope", "scenario", "science", "invalid"))
def test_evidence_changes_affect_outcome(change):
    minimum, summary, decision = inputs()
    evidence = decision.evidence
    if change == "scope":
        evidence = replace(evidence, scope=replace(evidence.scope, intended_use="other use"))
    elif change == "scenario":
        evidence = replace(evidence, provenance=replace(evidence.provenance, scenario="other"))
    elif change == "science":
        evidence = replace(evidence, scientific_adequacy=ScientificAdequacy.ACCEPTED_AS_INDICATIVE)
    else:
        evidence = replace(evidence, numerical_validity=NumericalValidity.INVALID)
    result = assess_supported(minimum, summary, replace(decision, evidence=evidence))
    assert result.summary.finding is (CheckFinding.FAIL if change == "invalid" else CheckFinding.UNKNOWN)
    assert not result.supported_final_total


def test_authorization_is_supplied_not_inferred_from_numbers():
    minimum, summary, decision = inputs()
    authorized = replace(decision, basis=BalancingBasis.AUTHORIZED)
    authorized = replace(
        authorized, evidence=replace(decision.evidence, scope=balancing_decision_scope(minimum, authorized))
    )
    assert not assess_supported(minimum, summary, authorized).supported_final_total
    accepted = replace(
        authorized, evidence=replace(authorized.evidence, official_admissibility=OfficialAdmissibility.ADMISSIBLE)
    )
    result = assess_supported(minimum, summary, accepted)
    assert result.supported_final_total == decision.final_total
    assert result.official.finding is CheckFinding.PASS
    rejected = replace(
        authorized, evidence=replace(authorized.evidence, official_admissibility=OfficialAdmissibility.NOT_ADMISSIBLE)
    )
    assert assess_supported(minimum, summary, rejected).summary.finding is CheckFinding.FAIL


def test_presence_and_unknown_minimum_never_enable_lowering():
    minimum, summary, decision = inputs()
    absent = replace(minimum[0], value=None, presence=Presence.UNSUPPORTED, reasons=("study absent",))
    result = assess_supported((absent,), summary, decision)
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert not result.supported_final_total
    assert result.preceding_minimum[0].presence is Presence.UNSUPPORTED


def test_official_status_does_not_transfer_out_of_scope():
    minimum, summary, decision = inputs()
    evidence = replace(
        decision.evidence,
        scope=replace(decision.evidence.scope, reach="other reach"),
        official_admissibility=OfficialAdmissibility.ADMISSIBLE,
    )
    result = assess_supported(minimum, summary, replace(decision, basis=BalancingBasis.AUTHORIZED, evidence=evidence))
    assert result.official.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("changed", ("section", "mapping", "reach_version", "body_version", "data", "config"))
def test_evidence_cannot_rebind_to_changed_subject_identity(changed):
    minimum, summary, decision = inputs()
    sample = minimum[0]
    location, provenance = sample.location, sample.provenance
    if changed == "section":
        location = replace(location, section=CalculationSection("other-point", "v1"))
    elif changed == "mapping":
        location = replace(location, mapping_version="v2")
    elif changed == "reach_version":
        location = replace(location, reach=replace(location.reach, version="v2"))
    elif changed == "body_version":
        location = replace(
            location, reach=replace(location.reach, water_body=replace(location.reach.water_body, version="v2"))
        )
    elif changed == "data":
        provenance = replace(provenance, data_version="v2")
    else:
        provenance = replace(provenance, configuration_version="v2")
    moved = replace(sample, location=location, provenance=provenance)
    target = replace(decision.final_total[0], location=location, provenance=provenance)
    result = assess_supported((moved,), summary, replace(decision, final_total=(target,)))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.supported_final_total == ()


def test_derived_final_total_cannot_be_labelled_observed():
    _, _, decision = inputs()
    target = decision.final_total[0]
    observed = replace(target, provenance=replace(target.provenance, production_method=ProductionMethod.OBSERVED))
    with pytest.raises(ValueError, match="observation"):
        replace(decision, final_total=(observed,))


def test_decision_evidence_excluded_warmup_cannot_support_total():
    minimum, summary, decision = inputs()
    evidence = replace(
        decision.evidence, provenance=replace(decision.evidence.provenance, excluded_warmup=(minimum[0].interval,))
    )
    result = assess_supported(minimum, summary, replace(decision, evidence=evidence))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.supported_final_total == ()


def test_decision_evidence_cannot_authorize_changed_final_amount():
    minimum, summary, decision = inputs()
    changed = replace(decision, final_total=(replace(decision.final_total[0], value=Flow(999, "l/s")),))
    result = assess_supported(minimum, summary, changed)
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.supported_final_total == ()


def test_minimum_summary_alone_cannot_certify_final_safeguards():
    minimum, summary, decision = inputs()
    result = assess_balancing(minimum, summary, decision)
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.supported_final_total == ()


def test_actual_final_total_rechecks_safeguard_upper_domain():
    minimum, _, decision = inputs()
    safeguards = safeguards_for(minimum, upper=200)
    assert safeguards.summary.finding is CheckFinding.PASS
    result = assess_balancing(minimum, safeguards.summary, decision, safeguards=safeguards)
    assert result.summary.finding is CheckFinding.FAIL
    assert result.supported_final_total == ()


def exception_for(sample):
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

    scope = ExceptionScope(
        sample.location,
        "intake",
        sample.provenance.scenario,
        sample.provenance.reference_member,
        sample.interval,
        DownstreamExtent(0, 1000),
        sample.provenance.configuration_version,
        sample.provenance.data_version,
    )
    conditions = NonFishWater(None, FishStatus.NON_FISH)
    findings = EvidenceFindings(
        condition_evidence_scope(scope, ExceptionClause.NON_FISH, conditions),
        sample.provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic non-fish study",),
    )
    conditions = replace(conditions, evidence=findings)
    evidence = replace(
        findings,
        scope=decision_evidence_scope(
            scope,
            ExceptionClause.NON_FISH,
            Flow(35, "l/s"),
            DecisionBasis.HYPOTHETICAL,
            "modeller",
            "synthetic exception",
        ),
    )
    exception_decision = ExceptionDecision(
        scope,
        ExceptionClause.NON_FISH,
        Flow(35, "l/s"),
        DecisionBasis.HYPOTHETICAL,
        "modeller",
        "synthetic exception",
        evidence,
    )
    return assess_exception(Flow(100, "l/s"), Flow(130, "l/s"), scope, conditions, exception_decision)


def test_separate_balancing_after_supported_exception():
    minimum, summary, decision = inputs((35,), final=40)
    exception = exception_for(minimum[0])
    result = assess_balancing(minimum, summary, decision, exception=exception)
    assert result.summary.finding is CheckFinding.PASS
    assert result.exception is not None
    assert result.exception.applied_minimum == Flow(35, "l/s")
    assert result.supported_final_total == decision.final_total
    missing = assess_balancing(minimum, summary, None, exception=exception)
    assert missing.summary.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("changed", ("scope", "amount", "condition", "period", "config"))
def test_exception_cannot_substitute_mismatched_or_failed_lower_minimum(changed):
    minimum, summary, decision = inputs((35,))
    exception = exception_for(minimum[0])
    if changed == "scope":
        exception = replace(
            exception,
            scope=replace(exception.scope, location=replace(exception.scope.location, mapping_version="other")),
        )
    elif changed == "period":
        exception = replace(
            exception,
            scope=replace(
                exception.scope, period=Interval(datetime(2019, 1, 1, tzinfo=UTC), datetime(2019, 2, 1, tzinfo=UTC))
            ),
        )
    elif changed == "config":
        exception = replace(exception, scope=replace(exception.scope, configuration_version="other"))
    elif changed == "amount":
        # Preserve the old passing summary to prove the boundary recomputes stored inputs.
        exception = replace(exception, decision=replace(exception.decision, minimum=Flow(34, "l/s")))
    else:
        from fishy.swiss_exceptions import FishStatus

        exception = replace(exception, conditions=replace(exception.conditions, fish_status=FishStatus.FISH))
    result = assess_balancing(minimum, summary, decision, exception=exception)
    assert result.summary.finding is not CheckFinding.PASS
    assert result.supported_final_total == ()


def test_exception_and_normal_safeguards_require_separate_scoped_assessments():
    minimum, summary, decision = inputs((35,))
    with pytest.raises(ValueError, match="separate"):
        assess_balancing(
            minimum, summary, decision, safeguards=safeguards_for(minimum), exception=exception_for(minimum[0])
        )


def test_exception_cannot_erase_independent_preceding_failure():
    minimum, _, decision = inputs((35,))
    summary = CheckSummary((Check("independent_condition", CheckFinding.FAIL),))
    result = assess_balancing(minimum, summary, decision, exception=exception_for(minimum[0]))
    assert result.summary.finding is CheckFinding.FAIL
    assert not result.supported_final_total


def test_hypothetical_exception_cannot_authorize_official_final():
    minimum, summary, decision = inputs((35,), final=40)
    official = replace(
        decision,
        basis=BalancingBasis.AUTHORIZED,
        evidence=replace(decision.evidence, official_admissibility=OfficialAdmissibility.ADMISSIBLE),
    )
    official = replace(official, evidence=replace(official.evidence, scope=balancing_decision_scope(minimum, official)))
    result = assess_balancing(minimum, summary, official, exception=exception_for(minimum[0]))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.supported_final_total == ()


def test_one_exception_does_not_cover_additional_periods():
    minimum, summary, decision = inputs((35, 35), final=40)
    result = assess_balancing(minimum, summary, decision, exception=exception_for(minimum[0]))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.supported_final_total == ()


@pytest.mark.parametrize("changed", ("basis", "issuer", "identifier", "rationale", "interest", "report"))
def test_reviewed_decision_cannot_change_authority_or_content(changed):
    minimum, summary, decision = inputs()
    reviewed = replace(
        decision, evidence=replace(decision.evidence, official_admissibility=OfficialAdmissibility.ADMISSIBLE)
    )
    if changed == "basis":
        altered = replace(reviewed, basis=BalancingBasis.AUTHORIZED)
    elif changed == "issuer":
        altered = replace(reviewed, decision_maker="other authority")
    elif changed == "identifier":
        altered = replace(reviewed, identifier="other decision")
    elif changed == "rationale":
        altered = replace(reviewed, rationale="different unreviewed balancing")
    elif changed == "interest":
        altered = replace(
            reviewed,
            interests=(replace(reviewed.interests[0], assessment="different public interest"), *reviewed.interests[1:]),
        )
    else:
        altered = replace(
            reviewed, applicant_report=replace(reviewed.applicant_report, prevention_measures="different mitigation")
        )
    result = assess_supported(minimum, summary, altered)
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.official.finding is CheckFinding.UNKNOWN
    assert result.supported_final_total == ()


@pytest.mark.parametrize("basis", tuple(BalancingBasis))
def test_two_stage_decision_requires_attached_reviewed_evidence(basis):
    minimum, summary, reviewed = inputs()
    draft = replace(reviewed, basis=basis, evidence=None)
    pending = assess_supported(minimum, summary, draft)
    assert pending.summary.finding is CheckFinding.UNKNOWN
    assert pending.official.finding is CheckFinding.UNKNOWN
    assert not pending.supported_final_total
    findings = replace(
        reviewed.evidence,
        scope=balancing_decision_scope(minimum, draft),
        official_admissibility=OfficialAdmissibility.ADMISSIBLE,
    )
    final = replace(draft, evidence=findings)
    assert assess_supported(minimum, summary, final).supported_final_total == final.final_total
