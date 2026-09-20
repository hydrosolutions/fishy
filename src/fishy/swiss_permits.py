"""assess_permit_scope : AbstractionContext → PermitScopeAssessment (pure).

assess_limited_abstraction : Flow × AbstractionInventory × Article30ReadingSelection?
    → LimitedAbstractionAssessment.
assess_drinking_abstraction : AnnualDrinkingAbstraction → DrinkingAbstractionAssessment.
assess_permit_process : PermitProcess → PermitProcessAssessment.

GSchG (2025-08-01), Arts. 29–30, 34–35; GSchV (2025-12-01), Arts. 33, 35.
Numerical eligibility is not a permit. FOEN 2000 supports the named instantaneous
Art. 30(b) interpretation; it does not override the amended Act.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    ReferenceKind,
    permitted_use,
)
from fishy.quantities import Flow, Number, Volume, finite_number, mean_discharge
from fishy.spatial import Location
from fishy.time import Interval


class ConcessionRoute(StrEnum):
    NEW_OR_RENEWED = "new_or_renewed"
    EXISTING = "existing_concession_arts_80_ff"
    SUPPLIED_DUTY = "already_prescribed_duty"


class AbstractionSource(StrEnum):
    WATERCOURSE = "watercourse"
    SPRING = "spring"
    GROUNDWATER = "groundwater"
    LAKE = "lake"


class AbstractionPurpose(StrEnum):
    DRINKING_WATER = "drinking_water_supply"
    HYDROPOWER = "hydropower"
    OTHER = "other"


class CommonUse(StrEnum):
    BEYOND = "beyond_common_use"
    WITHIN = "within_common_use"
    UNRESOLVED = "unresolved"


class SignificantEffect(StrEnum):
    SIGNIFICANT = "significant_effect_on_perennial_watercourse"
    NOT_SIGNIFICANT = "no_significant_effect_on_perennial_watercourse"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class PermitScope:
    location: Location
    period: Interval
    scenario: str
    member: str | None
    data_version: str
    configuration_version: str
    reference_kind: ReferenceKind | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.period, Interval):
            raise TypeError("permit scope requires Location and Interval")
        _text(self.scenario)
        _text(self.data_version)
        _text(self.configuration_version)
        if self.reference_kind is not None and not isinstance(self.reference_kind, ReferenceKind):
            raise TypeError("reference kind requires ReferenceKind")
        if self.member is not None:
            _text(self.member)


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("attribution and identifiers require nonempty text")


class PermitEvidencePurpose(StrEnum):
    APPLICABILITY = "Swiss abstraction applicability"
    DOWNSTREAM_PERMANENCE = "Swiss downstream permanence"
    NATURE_FISHERIES_MEASURES = "Swiss nonperennial nature and fisheries measures"
    ABSTRACTION_ENVELOPE = "Swiss simultaneous abstraction envelope"
    ARTICLE_30_READING = "Swiss Art30(b) interpretation selection"
    ANNUAL_DRINKING_ABSTRACTION = "Swiss annual drinking abstraction"
    PROCESS_DOCUMENT = "Swiss permit process document"


def permit_evidence_scope(
    scope: PermitScope,
    purpose: PermitEvidencePurpose,
    subject: PermitSubject,
) -> EvidenceScope:
    """Bind accepted use to the complete physical context and reviewed facts.

    Build the immutable domain record with evidence=None, obtain its review scope,
    then attach the supplied findings with dataclasses.replace. Changing factual
    fields requires a new scoped review; replacing evidence alone does not.
    """
    if not isinstance(scope, PermitScope) or not isinstance(purpose, PermitEvidencePurpose):
        raise TypeError("permit evidence scope requires named scope and purpose")
    return EvidenceScope(
        f"Swiss permit evidence:{scope!r};subject={_subject_content(subject)!r}",
        scope.location.reach.identifier,
        scope.member,
        scope.period,
        purpose.value,
    )


@dataclass(frozen=True)
class PermitEvidence:
    """Exact physical scope and independent numerical/scientific/official findings."""

    scope: PermitScope
    findings: EvidenceFindings

    def __post_init__(self) -> None:
        if not isinstance(self.scope, PermitScope) or not isinstance(self.findings, EvidenceFindings):
            raise TypeError("typed permit scope and evidence findings required")
        f = self.findings
        if (
            f.scope.reach != self.scope.location.reach.identifier
            or not f.scope.product.startswith(f"Swiss permit evidence:{self.scope!r};subject=")
            or f.provenance.data_version != self.scope.data_version
            or f.provenance.configuration_version != self.scope.configuration_version
            or f.scope.period != self.scope.period
            or f.scope.member != self.scope.member
            or f.provenance.scenario != self.scope.scenario
            or f.provenance.reference_member != self.scope.member
            or f.provenance.reference_kind != self.scope.reference_kind
        ):
            raise ValueError("evidence does not describe the declared permit scope")


def _optional_evidence(value: PermitEvidence | None) -> None:
    if value is not None and not isinstance(value, PermitEvidence):
        raise TypeError("evidence requires PermitEvidence or explicit absence")


def _support(
    identifier: str,
    evidence: PermitEvidence | None,
    scope: PermitScope,
    purpose: PermitEvidencePurpose,
    subject: PermitSubject | None,
) -> Check:
    if evidence is None:
        return Check(identifier, CheckFinding.UNKNOWN, ("missing scoped evidence",))
    if evidence.scope != scope:
        return Check(identifier, CheckFinding.UNKNOWN, ("evidence belongs to another physical or scenario scope",))
    if subject is None:
        return Check(identifier, CheckFinding.UNKNOWN, ("missing reviewed content",))
    finding = permitted_use(evidence.findings, permit_evidence_scope(scope, purpose, subject))
    return Check(identifier, finding.finding, finding.reasons)


def _condition(identifier: str, condition: bool, reason: str) -> Check:
    return Check(identifier, CheckFinding.PASS if condition else CheckFinding.FAIL, (reason,))


@dataclass(frozen=True)
class DownstreamPermanence:
    scope: PermitScope
    q347: Flow
    evidence: PermitEvidence | None
    nature_fisheries_measures: PermitEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, PermitScope) or not isinstance(self.q347, Flow):
            raise TypeError("downstream permanence requires scope and Flow Q347")
        _optional_evidence(self.evidence)
        _optional_evidence(self.nature_fisheries_measures)


@dataclass(frozen=True)
class AbstractionContext:
    scope: PermitScope
    concession: ConcessionRoute
    source: AbstractionSource
    common_use: CommonUse
    q347_at_intake: Flow | None
    significant_effect: SignificantEffect
    applicability_evidence: PermitEvidence | None
    downstream: tuple[DownstreamPermanence, ...]
    nature_fisheries_measures: PermitEvidence | None = None

    def __post_init__(self) -> None:
        for value, kind in (
            (self.scope, PermitScope),
            (self.concession, ConcessionRoute),
            (self.source, AbstractionSource),
            (self.common_use, CommonUse),
            (self.significant_effect, SignificantEffect),
        ):
            if not isinstance(value, kind):
                raise TypeError(f"expected {kind.__name__}")
        _optional_evidence(self.applicability_evidence)
        _optional_evidence(self.nature_fisheries_measures)
        if self.q347_at_intake is not None and not isinstance(self.q347_at_intake, Flow):
            raise TypeError("Q347 requires Flow")
        if not isinstance(self.downstream, tuple) or any(
            not isinstance(x, DownstreamPermanence) for x in self.downstream
        ):
            raise TypeError("downstream requires immutable permanence records")
        if len({x.scope.location for x in self.downstream}) != len(self.downstream):
            raise ValueError("duplicate downstream locations")
        if any(
            (x.scope.period, x.scope.scenario, x.scope.member)
            != (self.scope.period, self.scope.scenario, self.scope.member)
            for x in self.downstream
        ):
            raise ValueError("downstream records must retain period, scenario and member")


class PermitRoute(StrEnum):
    ARTICLE_30 = "article_30_conditions"
    ANALOGOUS_PROTECTION = "articles_30_and_34_analogous_protection"
    NATURE_FISHERIES = "nonperennial_intake_nature_and_fisheries_measures"
    OUTSIDE_ARTICLE_29 = "outside_article_29_not_a_permission"
    REMEDIATION = "arts_80_ff_derivation_not_implemented"
    EXISTING_DUTY = "assess_supplied_duty_without_resizing"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class PermitScopeAssessment:
    context: AbstractionContext
    route: PermitRoute
    article_30_sections: tuple[Location, ...]
    summary: CheckSummary


def assess_permit_scope(context: AbstractionContext) -> PermitScopeAssessment:
    """Select applicable obligations, never issue or resize an existing duty."""
    if context.concession is ConcessionRoute.EXISTING:
        return PermitScopeAssessment(
            context,
            PermitRoute.REMEDIATION,
            (),
            CheckSummary(
                (
                    Check(
                        "remediation_derivation",
                        CheckFinding.UNKNOWN,
                        ("Arts. 80 ff. need a separate remediation method",),
                    ),
                )
            ),
        )
    if context.concession is ConcessionRoute.SUPPLIED_DUTY:
        return PermitScopeAssessment(
            context,
            PermitRoute.EXISTING_DUTY,
            (),
            CheckSummary(
                (
                    Check(
                        "supplied_duty_route",
                        CheckFinding.PASS,
                        ("use fishy.duties.assess_duty; no historical sizing required",),
                    ),
                )
            ),
        )
    checks = [
        _support(
            "applicability_evidence",
            context.applicability_evidence,
            context.scope,
            PermitEvidencePurpose.APPLICABILITY,
            context,
        )
    ]
    route = PermitRoute.UNRESOLVED
    if context.common_use is CommonUse.UNRESOLVED:
        checks.append(Check("common_use", CheckFinding.UNKNOWN, ("beyond-common-use classification missing",)))
    elif context.common_use is CommonUse.WITHIN:
        route = PermitRoute.OUTSIDE_ARTICLE_29
    elif context.source in (AbstractionSource.LAKE, AbstractionSource.GROUNDWATER, AbstractionSource.SPRING):
        if context.significant_effect is SignificantEffect.SIGNIFICANT:
            route = PermitRoute.ANALOGOUS_PROTECTION
        elif context.significant_effect is SignificantEffect.NOT_SIGNIFICANT:
            route = PermitRoute.OUTSIDE_ARTICLE_29
        else:
            checks.append(
                Check(
                    "significant_effect", CheckFinding.UNKNOWN, ("significant perennial-watercourse effect unresolved",)
                )
            )
    elif context.q347_at_intake is None:
        checks.append(Check("intake_permanence", CheckFinding.UNKNOWN, ("missing Q347 at intake",)))
    elif context.q347_at_intake.value > 0:
        route = PermitRoute.ARTICLE_30
    else:
        route = PermitRoute.NATURE_FISHERIES
        checks.append(
            _support(
                "nature_fisheries_measures",
                context.nature_fisheries_measures,
                context.scope,
                PermitEvidencePurpose.NATURE_FISHERIES_MEASURES,
                context,
            )
        )
    sections = []
    if route in (PermitRoute.ARTICLE_30, PermitRoute.ANALOGOUS_PROTECTION):
        if not context.downstream:
            checks.append(Check("affected_sections", CheckFinding.UNKNOWN, ("affected downstream inventory missing",)))
        for index, item in enumerate(context.downstream):
            support = _support(
                f"downstream_permanence:{index}",
                item.evidence,
                item.scope,
                PermitEvidencePurpose.DOWNSTREAM_PERMANENCE,
                item,
            )
            checks.append(support)
            if item.q347.value > 0 and support.finding is CheckFinding.PASS:
                sections.append(item.scope.location)
            elif item.q347.value == 0:
                checks.append(
                    _support(
                        f"downstream_nature_fisheries:{index}",
                        item.nature_fisheries_measures,
                        item.scope,
                        PermitEvidencePurpose.NATURE_FISHERIES_MEASURES,
                        item,
                    )
                )
    # A numerically classified route remains unresolved without applicable evidence.
    if checks[0].finding is not CheckFinding.PASS:
        route = PermitRoute.UNRESOLVED
    return PermitScopeAssessment(context, route, tuple(sections), CheckSummary(tuple(checks)))


class AbstractionTimeBasis(StrEnum):
    INSTANTANEOUS_ENVELOPE = "supported_instantaneous_upper_envelope"
    INTERVAL_MEAN = "interval_mean_not_instantaneous"


@dataclass(frozen=True)
class AbstractionRate:
    identifier: str
    upper_rate: Flow

    def __post_init__(self) -> None:
        _text(self.identifier)
        if not isinstance(self.upper_rate, Flow):
            raise TypeError("abstraction rate requires Flow")


@dataclass(frozen=True)
class AbstractionInventory:
    """Declared complete simultaneous envelope, not a resampled daily mean."""

    scope: PermitScope
    abstractions: tuple[AbstractionRate, ...]
    time_basis: AbstractionTimeBasis
    evidence: PermitEvidence | None
    source: AbstractionSource = AbstractionSource.WATERCOURSE

    def __post_init__(self) -> None:
        if not isinstance(self.scope, PermitScope) or not isinstance(self.time_basis, AbstractionTimeBasis):
            raise TypeError("inventory requires typed scope and time basis")
        _optional_evidence(self.evidence)
        if not isinstance(self.source, AbstractionSource):
            raise TypeError("source requires AbstractionSource")
        if not isinstance(self.abstractions, tuple) or any(
            not isinstance(x, AbstractionRate) for x in self.abstractions
        ):
            raise TypeError("abstractions require immutable rate records")
        if len({x.identifier for x in self.abstractions}) != len(self.abstractions):
            raise ValueError("duplicate abstractions would distort the aggregate")


class Article30Reading(StrEnum):
    AGGREGATE_1000 = "act_aggregate_1000_l_s"
    PER_ABSTRACTION_1000 = "foen_2000_per_abstraction_1000_l_s"


class DecisionStatus(StrEnum):
    HYPOTHETICAL = "explicit_hypothetical_scenario"
    SUPPLIED_AUTHORITY = "supplied_authority_interpretation"


@dataclass(frozen=True)
class Article30ReadingSelection:
    reading: Article30Reading
    status: DecisionStatus
    source: str
    evidence: PermitEvidence | None

    def __post_init__(self) -> None:
        if not isinstance(self.reading, Article30Reading) or not isinstance(self.status, DecisionStatus):
            raise TypeError("reading and decision status must be named enums")
        _text(self.source)
        _optional_evidence(self.evidence)


@dataclass(frozen=True)
class LimitedAbstractionAssessment:
    inventory: AbstractionInventory
    q347: Flow
    combined_abstraction: Flow
    combined_limit: Flow
    aggregate_reading: CheckSummary
    per_abstraction_reading: CheckSummary
    selection: Article30ReadingSelection | None
    eligibility: CheckSummary


def assess_limited_abstraction(
    q347: Flow, inventory: AbstractionInventory, selection: Article30ReadingSelection | None
) -> LimitedAbstractionAssessment:
    """Art. 30(b): both named 1000 l/s readings; no automatic interpretation."""
    if not isinstance(q347, Flow):
        raise TypeError("Q347 requires Flow")
    total = Flow(sum((x.upper_rate.value for x in inventory.abstractions), Fraction()))
    limit = Flow(q347.value / 5)
    checks = [
        _condition("watercourse", inventory.source is AbstractionSource.WATERCOURSE, "Art. 30(b) watercourse route"),
        _condition("perennial", q347.value > 0, "Act Art. 4(i): Q347 strictly positive"),
        _support(
            "inventory_evidence",
            inventory.evidence,
            inventory.scope,
            PermitEvidencePurpose.ABSTRACTION_ENVELOPE,
            inventory,
        ),
    ]
    if not inventory.abstractions:
        checks.append(Check("inventory", CheckFinding.UNKNOWN, ("empty abstraction inventory",)))
    instantaneous = inventory.time_basis is AbstractionTimeBasis.INSTANTANEOUS_ENVELOPE
    checks.append(
        Check(
            "time_basis",
            CheckFinding.PASS if instantaneous else CheckFinding.UNKNOWN,
            ("FOEN 2000 p. 23: at all times, not a daily or seasonal mean",),
        )
    )
    # A failed mean bound proves failure; a passing mean cannot prove an instantaneous pass.
    checks.append(_condition("combined_20_percent", total.value <= limit.value, "combined abstraction <= 20% Q347"))
    aggregate = CheckSummary(tuple(checks) + (_condition("aggregate_1000", total.value <= 1, "aggregate <= 1000 l/s"),))
    per_intake = CheckSummary(
        tuple(checks)
        + tuple(
            _condition(f"intake_1000:{x.identifier}", x.upper_rate.value <= 1, "per abstraction <= 1000 l/s")
            for x in inventory.abstractions
        )
    )
    if selection is None:
        # If every named reading fails, lack of selection cannot erase failure.
        if aggregate.finding is CheckFinding.FAIL and per_intake.finding is CheckFinding.FAIL:
            checks.append(Check("all_readings_fail", CheckFinding.FAIL, ("both named Art. 30(b) readings fail",)))
        eligibility = CheckSummary(
            tuple(checks)
            + (
                Check(
                    "interpretation",
                    CheckFinding.UNKNOWN,
                    ("explicit Art. 30(b) reading required; neither branch selected",),
                ),
            )
        )
    else:
        chosen = aggregate if selection.reading is Article30Reading.AGGREGATE_1000 else per_intake
        eligibility = CheckSummary(
            chosen.checks
            + (
                _support(
                    "interpretation_evidence",
                    selection.evidence,
                    inventory.scope,
                    PermitEvidencePurpose.ARTICLE_30_READING,
                    selection,
                ),
            )
        )
    return LimitedAbstractionAssessment(inventory, q347, total, limit, aggregate, per_intake, selection, eligibility)


@dataclass(frozen=True)
class AnnualDrinkingAbstraction:
    scope: PermitScope
    source: AbstractionSource
    purpose: AbstractionPurpose
    annual_volume: Volume
    evidence: PermitEvidence | None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, PermitScope) or not isinstance(self.annual_volume, Volume):
            raise TypeError("annual abstraction requires scope and Volume")
        if not isinstance(self.source, AbstractionSource) or not isinstance(self.purpose, AbstractionPurpose):
            raise TypeError("source and purpose require named enums")
        _optional_evidence(self.evidence)
        period = self.scope.period
        if period.start != datetime(period.start.year, 1, 1, tzinfo=UTC) or period.end != datetime(
            period.start.year + 1, 1, 1, tzinfo=UTC
        ):
            raise ValueError("annual mean requires one complete declared UTC calendar year")


@dataclass(frozen=True)
class DrinkingAbstractionAssessment:
    abstraction: AnnualDrinkingAbstraction
    annual_mean: Flow
    annual_mean_limit: Flow | None
    eligibility: CheckSummary


def assess_drinking_abstraction(abstraction: AnnualDrinkingAbstraction) -> DrinkingAbstractionAssessment:
    """Art. 30(c): annual volume / actual year seconds, distinct spring/groundwater limits."""
    mean = mean_discharge(abstraction.annual_volume, abstraction.scope.period)
    limit = {AbstractionSource.SPRING: Flow(80, "l/s"), AbstractionSource.GROUNDWATER: Flow(100, "l/s")}.get(
        abstraction.source
    )
    checks = [
        _condition(
            "drinking_purpose", abstraction.purpose is AbstractionPurpose.DRINKING_WATER, "drinking-water supply only"
        ),
        _condition("eligible_source", limit is not None, "spring or groundwater only; no lake route"),
        _support(
            "annual_abstraction_evidence",
            abstraction.evidence,
            abstraction.scope,
            PermitEvidencePurpose.ANNUAL_DRINKING_ABSTRACTION,
            abstraction,
        ),
    ]
    if limit is not None:
        checks.append(_condition("annual_mean_limit", mean.value <= limit.value, "source-specific annual mean limit"))
    return DrinkingAbstractionAssessment(abstraction, mean, limit, CheckSummary(tuple(checks)))


@dataclass(frozen=True, init=False)
class GrossHydropower:
    kilowatts: Fraction

    def __init__(self, value: Number, unit: str = "kW") -> None:
        if unit not in ("kW", "MW"):
            raise ValueError("gross hydropower requires kW or MW")
        power = finite_number(value) * (1000 if unit == "MW" else 1)
        if power < 0:
            raise ValueError("gross hydropower cannot be negative")
        object.__setattr__(self, "kilowatts", power)


class EnvironmentalReview(StrEnum):
    EIA = "subject_to_environmental_impact_assessment"
    NON_EIA = "not_subject_to_environmental_impact_assessment"
    UNRESOLVED = "eia_applicability_unresolved"


class PermitDocumentKind(StrEnum):
    SPECIALIST_CONSULTATION = "interested_specialist_consultation"
    FEDERAL_HEARING = "federal_hearing"
    EIA_RESIDUAL_REPORT = "residual_report_in_environmental_impact_report"
    FOEN_CANTONAL_OPINION = "cantonal_residual_report_opinion_available_to_foen"
    FOEN_CANTONAL_DRAFT = "revised_cantonal_opinion_draft_available_to_foen"


@dataclass(frozen=True)
class PermitDocument:
    kind: PermitDocumentKind
    evidence: PermitEvidence | None
    issuer: str
    reference: str
    consulted_specialists: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PermitDocumentKind):
            raise TypeError("permit document requires named kind")
        _optional_evidence(self.evidence)
        _text(self.issuer)
        _text(self.reference)
        if not isinstance(self.consulted_specialists, tuple):
            raise TypeError("consulted specialists require immutable names")
        for specialist in self.consulted_specialists:
            _text(specialist)
        if len(set(self.consulted_specialists)) != len(self.consulted_specialists):
            raise ValueError("duplicate consulted specialists")


@dataclass(frozen=True)
class PermitProcess:
    scope: PermitScope
    purpose: AbstractionPurpose
    gross_power: GrossHydropower | None
    environmental_review: EnvironmentalReview
    required_specialists: tuple[str, ...]
    documents: tuple[PermitDocument, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scope, PermitScope) or not isinstance(self.purpose, AbstractionPurpose):
            raise TypeError("permit process requires typed scope and purpose")
        if not isinstance(self.environmental_review, EnvironmentalReview):
            raise TypeError("environmental review requires named state")
        if self.gross_power is not None and not isinstance(self.gross_power, GrossHydropower):
            raise TypeError("gross power requires GrossHydropower")
        if self.purpose is not AbstractionPurpose.HYDROPOWER and self.gross_power is not None:
            raise ValueError("gross hydropower cannot describe another purpose")
        if not isinstance(self.required_specialists, tuple) or not isinstance(self.documents, tuple):
            raise TypeError("process inventories require immutable tuples")
        for name in self.required_specialists:
            _text(name)
        if len(set(self.required_specialists)) != len(self.required_specialists):
            raise ValueError("duplicate required specialists")
        if any(not isinstance(x, PermitDocument) for x in self.documents):
            raise TypeError("documents require PermitDocument")
        if len({x.kind for x in self.documents}) != len(self.documents):
            raise ValueError("duplicate document kinds")


@dataclass(frozen=True)
class PermitProcessAssessment:
    process: PermitProcess
    required_documents: tuple[PermitDocumentKind, ...]
    summary: CheckSummary


def assess_permit_process(process: PermitProcess) -> PermitProcessAssessment:
    """Arts. 35/Ordinance 35 process coverage, separate from an authority decision."""
    required = [PermitDocumentKind.SPECIALIST_CONSULTATION]
    checks = []
    hearing = (
        process.purpose is AbstractionPurpose.HYDROPOWER
        and process.gross_power is not None
        and process.gross_power.kilowatts > 300
    )
    if process.purpose is AbstractionPurpose.HYDROPOWER and process.gross_power is None:
        checks.append(
            Check("gross_power", CheckFinding.UNKNOWN, ("missing gross power; federal hearing requirement unresolved",))
        )
    if hearing:
        required.append(PermitDocumentKind.FEDERAL_HEARING)
    if process.environmental_review is EnvironmentalReview.EIA:
        required.append(PermitDocumentKind.EIA_RESIDUAL_REPORT)
    elif process.environmental_review is EnvironmentalReview.UNRESOLVED:
        checks.append(Check("eia_applicability", CheckFinding.UNKNOWN, ("EIA document route unresolved",)))
    elif hearing:
        alternatives = tuple(
            x
            for x in process.documents
            if x.kind
            in (
                PermitDocumentKind.FOEN_CANTONAL_OPINION,
                PermitDocumentKind.FOEN_CANTONAL_DRAFT,
            )
        )
        # Either supported document satisfies Ordinance 35(2). Retain both inputs.
        supported = tuple(
            x
            for x in alternatives
            if _support(
                x.kind.value,
                x.evidence,
                process.scope,
                PermitEvidencePurpose.PROCESS_DOCUMENT,
                x,
            ).finding
            is CheckFinding.PASS
        )
        required.append(
            supported[0].kind
            if supported
            else (alternatives[0].kind if alternatives else PermitDocumentKind.FOEN_CANTONAL_DRAFT)
        )
    by_kind = {x.kind: x for x in process.documents}
    for kind in required:
        document = by_kind.get(kind)
        checks.append(
            _support(
                kind.value,
                None if document is None else document.evidence,
                process.scope,
                PermitEvidencePurpose.PROCESS_DOCUMENT,
                document,
            )
        )
    consultation = by_kind.get(PermitDocumentKind.SPECIALIST_CONSULTATION)
    if not process.required_specialists:
        checks.append(Check("specialist_inventory", CheckFinding.UNKNOWN, ("interested specialist inventory missing",)))
    elif consultation is not None:
        for specialist in process.required_specialists:
            checks.append(
                _condition(
                    f"consulted:{specialist}",
                    specialist in consultation.consulted_specialists,
                    "each identified interested specialist must be consulted",
                )
            )
    return PermitProcessAssessment(process, tuple(required), CheckSummary(tuple(checks)))


type PermitSubject = (
    AbstractionContext
    | DownstreamPermanence
    | AbstractionInventory
    | Article30ReadingSelection
    | AnnualDrinkingAbstraction
    | PermitDocument
)


def _subject_content(subject: PermitSubject) -> tuple[object, ...]:
    """Project exactly the reviewed facts, excluding attached evidence records."""
    if isinstance(subject, AbstractionContext):
        return (
            "abstraction applicability",
            subject.concession,
            subject.source,
            subject.common_use,
            subject.q347_at_intake,
            subject.significant_effect,
            tuple((item.scope, item.q347) for item in subject.downstream),
        )
    if isinstance(subject, DownstreamPermanence):
        return ("downstream permanence", subject.q347)
    if isinstance(subject, AbstractionInventory):
        return ("abstraction envelope", subject.abstractions, subject.time_basis, subject.source)
    if isinstance(subject, Article30ReadingSelection):
        return ("Art30 interpretation", subject.reading, subject.status, subject.source)
    if isinstance(subject, AnnualDrinkingAbstraction):
        return ("annual drinking abstraction", subject.source, subject.purpose, subject.annual_volume)
    if isinstance(subject, PermitDocument):
        return ("permit document", subject.kind, subject.issuer, subject.reference, subject.consulted_specialists)
    raise TypeError("permit evidence requires a typed reviewed domain record")
