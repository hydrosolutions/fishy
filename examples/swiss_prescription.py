"""A complete synthetic Swiss supplied-study scenario, without Taqsim or HYDMOD.

scenario : ImportedQ347 × SiteStudies × HypotheticalDecisions → ReleaseAssessment.
No example input is a site calibration, permit or national policy default.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from fractions import Fraction

from fishy.duties import Delivery, DutyApplicability, Obligation, SuppliedDuty
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
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
from fishy.flows import FlowSample, Presence
from fishy.low_flow import (
    EstimateStatus,
    Q347Review,
    Q347Use,
    VerificationRoute,
    assess_q347,
    imported_q347,
)
from fishy.quantities import Elevation, Flow, FlowBounds, Volume
from fishy.residual_flow import StartingMinimum, attributed_starting_minimum
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.swiss_balancing import (
    AbstractionInterest,
    ApplicantAlternatives,
    BalancingAssessment,
    BalancingBasis,
    BalancingDecision,
    InterestConsideration,
    assess_balancing,
    balancing_decision_scope,
    balancing_scope,
)
from fishy.swiss_delivery import (
    FlowProof,
    IntakePrescription,
    IntakeRelationship,
    ProofMethod,
    SwissDeliveryAssessment,
    WaterBalance,
    assess_swiss_delivery,
    derive_intake_schedule,
    proof_scope,
    relationship_scope,
)
from fishy.swiss_permits import (
    AbstractionContext,
    AbstractionPurpose,
    AbstractionSource,
    CommonUse,
    ConcessionRoute,
    DownstreamPermanence,
    EnvironmentalReview,
    GrossHydropower,
    PermitDocument,
    PermitDocumentKind,
    PermitEvidence,
    PermitEvidencePurpose,
    PermitProcess,
    PermitProcessAssessment,
    PermitScope,
    PermitScopeAssessment,
    SignificantEffect,
    assess_permit_process,
    assess_permit_scope,
    permit_evidence_scope,
)
from fishy.swiss_safeguards import (
    FishFunction,
    FlowNeed,
    Safeguard,
    SafeguardAssessment,
    SafeguardSite,
    SafeguardStudy,
    SafeguardTreatment,
    SafeguardUse,
    assess_safeguards,
    safeguard_study_scope,
)
from fishy.time import Interval


def accepted(scope: EvidenceScope, provenance: Provenance) -> EvidenceFindings:
    """Explicit synthetic scientific acceptance, never official admission."""
    return EvidenceFindings(
        scope,
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic accepted scenario input, not site certification",),
    )


@dataclass(frozen=True)
class SwissScenario:
    starting: StartingMinimum
    hydrology: CheckSummary
    permit: PermitScopeAssessment
    process: PermitProcessAssessment
    safeguards: SafeguardAssessment
    balancing: BalancingAssessment
    intake: IntakePrescription
    delivery: SwissDeliveryAssessment


def scenario() -> SwissScenario:
    provenance = Provenance(
        "own synthetic Swiss scenario",
        "illustration",
        "member-1",
        "example-v1",
        "synthetic-v1",
        "scenario-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    reach = Reach("synthetic reach", "1", WaterBody("synthetic river", "1"))
    intake = Location(reach, CalculationSection("intake", "1"), "1")
    downstream = Location(reach, CalculationSection("protection point", "1"), "1")
    reference = Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2010, 1, 1, tzinfo=UTC))
    interval = Interval(datetime(2025, 7, 1, tzinfo=UTC), datetime(2025, 7, 2, tzinfo=UTC))
    q347 = imported_q347(
        Flow(160, "l/s"),
        downstream,
        reference,
        provenance,
        "synthetic Art.59 supplied model estimate",
        EstimateStatus.PRELIMINARY,
    )
    q_scope = EvidenceScope("Q347", reach.identifier, provenance.reference_member, reference, "scenario sizing")
    passed = Check("supplied", CheckFinding.PASS, ("own synthetic reviewed condition",))
    review = Q347Review(
        q347,
        Q347Use.INDICATIVE_SCENARIO,
        accepted(q_scope, provenance),
        passed,
        passed,
        passed,
        VerificationRoute.NOT_APPLICABLE,
        passed,
        None,
        "preliminary labelled scenario; no final verification claim",
    )
    hydrology = assess_q347(q347, review, q_scope)
    starting = attributed_starting_minimum(q347)

    def permit_scope(location: Location) -> PermitScope:
        return PermitScope(
            location,
            interval,
            provenance.scenario,
            provenance.reference_member,
            provenance.data_version,
            provenance.configuration_version,
        )

    def permit_evidence(
        location: Location,
        purpose: PermitEvidencePurpose,
        subject: AbstractionContext | DownstreamPermanence | PermitDocument,
    ) -> PermitEvidence:
        scope = permit_scope(location)
        return PermitEvidence(scope, accepted(permit_evidence_scope(scope, purpose, subject), provenance))

    permanence = DownstreamPermanence(permit_scope(downstream), q347.value, None)
    permanence = replace(
        permanence, evidence=permit_evidence(downstream, PermitEvidencePurpose.DOWNSTREAM_PERMANENCE, permanence)
    )
    context = AbstractionContext(
        permit_scope(intake),
        ConcessionRoute.NEW_OR_RENEWED,
        AbstractionSource.WATERCOURSE,
        CommonUse.BEYOND,
        q347.value,
        SignificantEffect.NOT_SIGNIFICANT,
        None,
        (permanence,),
    )
    context = replace(
        context, applicability_evidence=permit_evidence(intake, PermitEvidencePurpose.APPLICABILITY, context)
    )
    permit = assess_permit_scope(context)
    consultation = PermitDocument(
        PermitDocumentKind.SPECIALIST_CONSULTATION,
        None,
        "synthetic specialists",
        "synthetic consultation record",
        ("fisheries", "water quality"),
    )
    consultation = replace(
        consultation, evidence=permit_evidence(intake, PermitEvidencePurpose.PROCESS_DOCUMENT, consultation)
    )
    process = assess_permit_process(
        PermitProcess(
            permit_scope(intake),
            AbstractionPurpose.HYDROPOWER,
            GrossHydropower(300),
            EnvironmentalReview.NON_EIA,
            ("fisheries", "water quality"),
            (consultation,),
        )
    )

    base = FlowSample(downstream, interval, starting.value, Presence.PRESENT, provenance)
    site = SafeguardSite(
        "protection point in July",
        base,
        q347.value,
        Elevation(700),
        FishFunction.SPAWNING_OR_REARING,
        "synthetic complete affected-point inventory",
    )
    studies = []
    for safeguard in Safeguard:
        total = Flow(180 if safeguard is Safeguard.FISH_PASSAGE else 130, "l/s")
        need = FlowNeed(
            total,
            Flow(0),
            Flow(1),
            "synthetic supplied site relationship",
            "specialist-selected hypothetical criterion",
        )
        treatment = SafeguardTreatment.FLOW_REQUIREMENT
        evidence = accepted(safeguard_study_scope(site, safeguard, treatment, need), provenance)
        studies.append(
            SafeguardStudy(
                site.identifier,
                safeguard,
                downstream,
                evidence,
                treatment,
                "synthetic supported total, not an additive uplift",
                need,
            )
        )
    safeguards = assess_safeguards((site,), tuple(studies), use=SafeguardUse.SCENARIO)
    preceding = (safeguards.sites[0].minimum,)
    final = (replace(preceding[0], value=Flow(220, "l/s")),)
    balance_evidence = accepted(balancing_scope(preceding, final), provenance)
    decision = BalancingDecision(
        "synthetic decision",
        "scenario modeller",
        "separate supplied interest judgement selects final total220",
        BalancingBasis.HYPOTHETICAL,
        final,
        tuple(
            InterestConsideration(interest, "synthetic study consideration", balance_evidence)
            for interest in AbstractionInterest
        ),
        ApplicantAlternatives(
            "synthetic applicant",
            "different abstractions compared",
            "energy and cost effects reviewed",
            "landscape and ecosystem effects reviewed",
            "mitigations reviewed",
            balance_evidence,
        ),
        None,
    )
    decision = replace(decision, evidence=accepted(balancing_decision_scope(preceding, decision), provenance))
    balancing = assess_balancing(preceding, safeguards.summary, decision, safeguards=safeguards)
    need = balancing.supported_final_total[0]
    intake_base = replace(base, location=intake)
    domain = FlowBounds(Flow(0), Flow(1), "valid intake domain", "synthetic study", "not uncertainty")
    volume = Volume(Flow(220, "l/s").value * interval.seconds)
    accounts = WaterBalance(Volume(0), volume, volume, Volume(0), Volume(0), "synthetic zero-loss account")
    relation_source = "synthetic same-day unit transmission; explicit no exchange or storage"
    relation_evidence = accepted(
        relationship_scope(intake, need, Fraction(1), domain, (), accounts, relation_source), provenance
    )
    relation = IntakeRelationship(intake, need, Fraction(1), domain, (), relation_evidence, accounts, relation_source)
    preceding_checks = CheckSummary(
        tuple(
            Check(f"{group}:{c.check_id}", c.finding, c.reasons)
            for group, summary in (
                ("q347", hydrology),
                ("route", permit.summary),
                ("process", process.summary),
                ("balancing", balancing.summary),
            )
            for c in summary.checks
        )
    )
    prescription = derive_intake_schedule(
        (intake_base,),
        (need,),
        (relation,),
        provenance=provenance,
        upstream_checks=preceding_checks,
        downstream_assessments=(balancing,),
    )
    if prescription.summary.finding is not CheckFinding.PASS:
        raise ValueError("synthetic prescription is not fully supported")
    nominal = prescription.schedule[0]
    duty = SuppliedDuty(
        "hypothetical Swiss intake duty",
        "v1",
        "GSchG Arts35–36 labelled scenario",
        DutyApplicability.HYPOTHETICAL,
        (Obligation(nominal, "v1"),),
        "own synthetic duty, no legal approval",
    )
    inflow = replace(nominal, value=Flow(150, "l/s"), components=())
    actual = replace(nominal, value=Flow(120, "l/s"), components=())
    inflow_proof = FlowProof(
        inflow,
        ProofMethod.MEASUREMENT,
        accepted(proof_scope(inflow, ProofMethod.MEASUREMENT, "inflow_proof"), provenance),
    )
    delivery_proof = FlowProof(
        actual,
        ProofMethod.MEASUREMENT,
        accepted(proof_scope(actual, ProofMethod.MEASUREMENT, "delivery_proof"), provenance),
    )
    delivery = assess_swiss_delivery(
        duty, (Delivery(actual, "observation-v1"),), inflow_proofs=(inflow_proof,), delivery_proofs=(delivery_proof,)
    )
    return SwissScenario(starting, hydrology, permit, process, safeguards, balancing, prescription, delivery)


if __name__ == "__main__":
    result = scenario()
    adjustment = result.delivery.adjustments[0]
    row = result.delivery.delivery.intervals[0]
    print("Synthetic scenario, not a permit or observed compliance")
    print(f"Q347={result.starting.q347.value.value * 1000}; table={result.starting.value.value * 1000} l/s")
    safeguarded = result.safeguards.sites[0].minimum.value
    final = result.balancing.supported_final_total[0].value
    nominal = adjustment.nominal.sample.value
    justified = adjustment.justified.sample.value
    shortfall = row.shortfall
    assert safeguarded is not None and final is not None
    assert nominal is not None and justified is not None and shortfall is not None
    print(f"safeguards={safeguarded.value * 1000}; final={final.value * 1000} l/s")
    print(f"nominal={nominal.value * 1000}; justified={justified.value * 1000}; shortfall={shortfall.value * 1000} l/s")
