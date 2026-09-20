"""assess_balancing : tuple[FlowSample] × CheckSummary × BalancingDecision → BalancingAssessment.

GSchG Art. 33 (2025-08-01), FOEN Guide 2000 §§4.5–4.6.
Supplied attributed judgement selects a total, never an arithmetic increment.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from hashlib import sha256

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    OfficialAdmissibility,
    ProductionMethod,
    ScientificAdequacy,
    permitted_use,
    warmup_restrictions,
)
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, check_flow_intervals, interval_use
from fishy.swiss_exceptions import DecisionBasis, ExceptionAssessment, assess_exception
from fishy.swiss_safeguards import SafeguardAssessment, SafeguardUse, assess_safeguard_candidate
from fishy.time import Interval


class BalancingBasis(StrEnum):
    HYPOTHETICAL = "hypothetical"
    AUTHORIZED = "supplied_authorized_decision"


class AbstractionInterest(StrEnum):
    PUBLIC = "33(2)(a): public interests"
    SOURCE_REGION_ECONOMY = "33(2)(b): source-region economy"
    APPLICANT_ECONOMY = "33(2)(c): applicant economy"
    ENERGY = "33(2)(d): energy supply"
    LANDSCAPE = "33(3)(a): landscape"
    HABITATS = "33(3)(b): habitats, biodiversity, fish yield and natural reproduction"
    WATER_QUALITY = "33(3)(c): long-term water quality"
    GROUNDWATER = "33(3)(d): future drinking water, land use and site vegetation"
    IRRIGATION = "33(3)(e): agricultural irrigation"


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("attribution and reasoning require nonempty text")


@dataclass(frozen=True)
class InterestConsideration:
    interest: AbstractionInterest
    assessment: str
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        if not isinstance(self.interest, AbstractionInterest) or not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("interest requires AbstractionInterest and EvidenceFindings")
        _text(self.assessment)


@dataclass(frozen=True)
class ApplicantAlternatives:
    """Art. 33(4) report content; findings qualify its use, not its conclusions."""

    applicant: str
    alternative_abstraction_effects: str
    energy_production_and_costs: str
    anticipated_protection_impairments: str
    prevention_measures: str
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        for value in (
            self.applicant,
            self.alternative_abstraction_effects,
            self.energy_production_and_costs,
            self.anticipated_protection_impairments,
            self.prevention_measures,
        ):
            _text(value)
        if not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("applicant report requires EvidenceFindings")


@dataclass(frozen=True)
class BalancingDecision:
    identifier: str
    decision_maker: str
    rationale: str
    basis: BalancingBasis
    final_total: tuple[FlowSample, ...]
    interests: tuple[InterestConsideration, ...]
    applicant_report: ApplicantAlternatives | None
    evidence: EvidenceFindings | None = None

    def __post_init__(self) -> None:
        for value in (self.identifier, self.decision_maker, self.rationale):
            _text(value)
        if not isinstance(self.basis, BalancingBasis):
            raise TypeError("decision requires BalancingBasis")
        if self.evidence is not None and not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("decision evidence requires EvidenceFindings")
        if not isinstance(self.final_total, tuple) or any(not isinstance(s, FlowSample) for s in self.final_total):
            raise TypeError("final totals require immutable FlowSample schedule")
        if self.final_total:
            check_flow_intervals(self.final_total)
        if any(s.provenance.production_method is ProductionMethod.OBSERVED for s in self.final_total):
            raise ValueError("a prescribed final total is not an observation")
        if not isinstance(self.interests, tuple) or any(
            not isinstance(i, InterestConsideration) for i in self.interests
        ):
            raise TypeError("interests require immutable InterestConsideration records")
        if len({i.interest for i in self.interests}) != len(self.interests):
            raise ValueError("duplicate interest consideration")
        if self.applicant_report is not None and not isinstance(self.applicant_report, ApplicantAlternatives):
            raise TypeError("report requires ApplicantAlternatives")


@dataclass(frozen=True)
class BalancingAssessment:
    preceding_minimum: tuple[FlowSample, ...]
    preceding_summary: CheckSummary
    decision: BalancingDecision | None
    balancing_summary: CheckSummary
    summary: CheckSummary
    supported_final_total: tuple[FlowSample, ...]
    official: Check
    safeguards: SafeguardAssessment | None
    exception: ExceptionAssessment | None


def balancing_scope(samples: tuple[FlowSample, ...], final_total: tuple[FlowSample, ...]) -> EvidenceScope:
    """Exact one-location schedule scope for supplied Art. 33 evidence.

    The product binds the complete physical and versioned input identity, not
    only a reach name. Each protection location requires its own assessment.
    """
    check_flow_intervals(samples)
    if not isinstance(final_total, tuple) or any(not isinstance(sample, FlowSample) for sample in final_total):
        raise TypeError("reviewed final total requires an immutable FlowSample schedule")
    if final_total:
        check_flow_intervals(final_total)
    subject = (
        tuple(sorted(samples, key=lambda sample: sample.interval.start)),
        tuple(sorted(final_total, key=lambda sample: sample.interval.start)),
    )
    return EvidenceScope(
        f"Swiss Art. 33 balancing: {subject!r}",
        samples[0].location.reach.identifier,
        samples[0].provenance.reference_member,
        Interval(min(s.interval.start for s in samples), max(s.interval.end for s in samples)),
        "determine residual-flow total",
    )


def balancing_decision_scope(samples: tuple[FlowSample, ...], decision: BalancingDecision) -> EvidenceScope:
    """Bind the reviewed authority/scenario decision, not only its numerical schedules.

    Construct a decision with evidence=None, then attach findings with this scope.
    Only the decision's own evidence wrapper is excluded to avoid recursion.
    Scientific interest/report findings remain part of the reviewed decision.
    """
    if not isinstance(decision, BalancingDecision):
        raise TypeError("reviewed decision requires BalancingDecision")
    base = balancing_scope(samples, decision.final_total)
    subject = (
        base.product,
        decision.identifier,
        decision.decision_maker,
        decision.rationale,
        decision.basis,
        decision.interests,
        decision.applicant_report,
    )
    digest = sha256(repr(subject).encode("utf-8")).hexdigest()
    return replace(base, product=f"Swiss Art. 33 reviewed decision:{digest}")


def _evidence(check_id: str, evidence: EvidenceFindings | None, scope: EvidenceScope, sample: FlowSample) -> Check:
    if evidence is None:
        return Check(check_id, CheckFinding.UNKNOWN, ("reviewed decision evidence not supplied",))
    if any(
        getattr(evidence.provenance, key) != getattr(sample.provenance, key)
        for key in ("scenario", "reference_member", "reference_kind")
    ):
        return Check(check_id, CheckFinding.UNKNOWN, ("evidence scenario/member/reference mismatch",))
    check = permitted_use(evidence, scope)
    if check.finding is not CheckFinding.FAIL and warmup_restrictions(evidence.provenance, scope.period):
        return Check(check_id, CheckFinding.UNKNOWN, ("evidence period overlaps excluded warm-up",))
    if check.finding is CheckFinding.PASS and evidence.scientific_adequacy is not ScientificAdequacy.ACCEPTED:
        return Check(check_id, CheckFinding.UNKNOWN, ("indicative evidence cannot establish final sizing",))
    return Check(check_id, check.finding, check.reasons)


def _supported(sample: FlowSample) -> bool:
    return (
        sample.presence is Presence.PRESENT
        and sample.coverage is Coverage.COMPLETE
        and interval_use(sample) is IntervalUse.ELIGIBLE
        and sample.value is not None
    )


def assess_balancing(
    preceding_minimum: tuple[FlowSample, ...],
    preceding_summary: CheckSummary,
    decision: BalancingDecision | None,
    *,
    safeguards: SafeguardAssessment | None = None,
    exception: ExceptionAssessment | None = None,
) -> BalancingAssessment:
    """Compare a supplied seasonal total to each preceding supported minimum.

    This operation remains required after an Art. 32 exception. No exception,
    economics or successful arithmetic erases a preceding failed safeguard.
    Missing decisions, reports and enumerated interests remain unresolved.
    """
    if not isinstance(preceding_minimum, tuple) or any(not isinstance(s, FlowSample) for s in preceding_minimum):
        raise TypeError("preceding minima require immutable FlowSample schedule")
    if not isinstance(preceding_summary, CheckSummary):
        raise TypeError("preceding_summary requires CheckSummary")
    if decision is not None and not isinstance(decision, BalancingDecision):
        raise TypeError("decision requires BalancingDecision")
    if safeguards is not None and not isinstance(safeguards, SafeguardAssessment):
        raise TypeError("final safeguard checks require the actual SafeguardAssessment")
    if exception is not None and not isinstance(exception, ExceptionAssessment):
        raise TypeError("exception requires the actual ExceptionAssessment")
    if safeguards is not None and exception is not None:
        raise ValueError("normal safeguards and exceptions require separate scoped assessments")
    scope = balancing_scope(preceding_minimum, decision.final_total if decision is not None else ())
    first = preceding_minimum[0]
    checks: list[Check] = []
    official = Check("official", CheckFinding.UNKNOWN, ("no authorized decision established",))
    if decision is None:
        checks.append(
            Check("decision", CheckFinding.UNKNOWN, ("Art. 33 decision required, including after exception",))
        )
    else:
        decision_scope = balancing_decision_scope(preceding_minimum, decision)
        checks.append(_evidence("decision", decision.evidence, decision_scope, first))
        interests = {i.interest: i for i in decision.interests}
        for interest in AbstractionInterest:
            item = interests.get(interest)
            checks.append(
                _evidence(interest.value, item.evidence, scope, first)
                if item
                else Check(interest.value, CheckFinding.UNKNOWN, ("required interest not considered",))
            )
        report = decision.applicant_report
        checks.append(
            _evidence("applicant_report", report.evidence, scope, first)
            if report
            else Check(
                "applicant_report", CheckFinding.UNKNOWN, ("alternative abstractions and mitigation report missing",)
            )
        )
        targets = {s.interval: s for s in decision.final_total}
        if set(targets) - {s.interval for s in preceding_minimum}:
            raise ValueError("final schedule intervals have no exact preceding minimum; no resampling")
        for index, minimum in enumerate(preceding_minimum):
            target = targets.get(minimum.interval)
            finding, reasons = CheckFinding.UNKNOWN, ("missing or unsupported final/minimum interval",)
            if target is not None:
                if target.location != minimum.location or any(
                    getattr(target.provenance, key) != getattr(minimum.provenance, key)
                    for key in ("scenario", "reference_member", "reference_kind")
                ):
                    raise ValueError("final total must match exact location/scenario/member/reference")
                if _supported(target) and _supported(minimum):
                    assert target.value is not None and minimum.value is not None
                    finding = CheckFinding.PASS if target.value.value >= minimum.value.value else CheckFinding.FAIL
                    reasons = ("final total compared directly to preceding minimum; no addition",)
            checks.append(Check(f"minimum:{index}", finding, reasons))
        if decision.basis is BalancingBasis.AUTHORIZED:
            evidence = decision.evidence
            status = evidence.official_admissibility if evidence is not None else OfficialAdmissibility.PENDING
            if (
                evidence is None
                or evidence.scope != decision_scope
                or any(
                    getattr(evidence.provenance, key) != getattr(first.provenance, key)
                    for key in ("scenario", "reference_member", "reference_kind")
                )
            ):
                status = OfficialAdmissibility.PENDING
            official = Check(
                "official",
                CheckFinding.PASS
                if status is OfficialAdmissibility.ADMISSIBLE
                else CheckFinding.FAIL
                if status is OfficialAdmissibility.NOT_ADMISSIBLE
                else CheckFinding.UNKNOWN,
                ("supplied decision status; not authenticated by this calculation",),
            )
            checks.append(official)
        else:
            official = Check("official", CheckFinding.UNKNOWN, ("explicit hypothetical decision is not authorization",))
    if exception is not None:
        exception = assess_exception(
            exception.q347, exception.ordinary_minimum, exception.scope, exception.conditions, exception.decision
        )
        checks.extend(Check("exception:" + c.check_id, c.finding, c.reasons) for c in exception.summary.checks)
        granted = exception.scope
        exact_subject = (
            len(preceding_minimum) == 1
            and first.location == granted.location
            and first.interval == granted.period
            and first.provenance.scenario == granted.scenario
            and first.provenance.reference_member == granted.member
            and first.provenance.configuration_version == granted.configuration_version
            and first.provenance.data_version == granted.data_version
            and exception.decision is not None
            and first.provenance.reference_kind == exception.decision.evidence.provenance.reference_kind
            and exception.applied_minimum is not None
            and first.value == exception.applied_minimum
        )
        checks.append(
            Check(
                "exception_subject",
                CheckFinding.PASS if exact_subject else CheckFinding.UNKNOWN,
                ("exception must match one exact preceding minimum and its versioned physical scope",),
            )
        )
        if (
            decision is not None
            and decision.basis is BalancingBasis.AUTHORIZED
            and (exception.decision is None or exception.decision.basis is not DecisionBasis.AUTHORISED)
        ):
            checks.append(
                Check(
                    "exception_basis",
                    CheckFinding.UNKNOWN,
                    ("hypothetical exception cannot support an authorized final total",),
                )
            )
    elif safeguards is None or decision is None:
        checks.append(
            Check(
                "final_safeguards",
                CheckFinding.UNKNOWN,
                ("actual final-candidate safeguard studies or scoped exception required",),
            )
        )
    else:
        candidate = assess_safeguard_candidate(safeguards, decision.final_total)
        checks.extend(Check("final_safeguards:" + c.check_id, c.finding, c.reasons) for c in candidate.checks)
        if decision.basis is BalancingBasis.AUTHORIZED and safeguards.use is not SafeguardUse.FINAL_SIZING:
            checks.append(
                Check(
                    "safeguard_use", CheckFinding.UNKNOWN, ("authorized total needs final-sizing safeguard evidence",)
                )
            )
    balancing = CheckSummary(tuple(checks))
    preceding_checks = preceding_summary.checks or (
        Check("coverage", CheckFinding.UNKNOWN, ("preceding checks absent",)),
    )
    combined = CheckSummary(
        tuple(Check("preceding:" + c.check_id, c.finding, c.reasons) for c in preceding_checks)
        + tuple(Check("balancing:" + c.check_id, c.finding, c.reasons) for c in checks)
    )
    supported = decision.final_total if decision is not None and combined.finding is CheckFinding.PASS else ()
    return BalancingAssessment(
        preceding_minimum, preceding_summary, decision, balancing, combined, supported, official, safeguards, exception
    )
