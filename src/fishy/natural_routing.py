"""select_natural_route : PreparedClassification × TierEvidence × RouteFailures → RouteDecision (pure).

Appendix A steps 5–7. Eligibility, scientific permission and arithmetic route failure
remain separate. This selects one supplied configuration; it runs no member study.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.daily_patterns import DailyPattern
from fishy.ecological_transfer import TransferResult, transfer_ecological_regime
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    ReferenceKind,
    permitted_use,
)
from fishy.natural_baseline import RecordedMinimum, recorded_minimum_product
from fishy.presumptive_floor import PresumptiveFloor, presumptive_floor
from fishy.scientific_acceptance import HydrologicalProduct, HydrologicalProductKind, ScientificAssessment, UsePurpose
from fishy.spatial import Location, PreparedClassification, Track, assessment_track
from fishy.study_requirements import (
    HighFlowTrigger,
    NaturalStudyComponent,
    StudyNeed,
    TopTierEligibility,
    assess_natural_study,
)


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty version, source and reason required")


class NaturalRoute(StrEnum):
    TOP = "top"
    BASELINE = "baseline"
    ENTRY = "entry"
    TRANSFER = "qualified_transfer"
    PRESUMPTIVE = "presumptive_floor"
    PENDING = "pending_no_computable_basis"
    POTENTIAL = "potential_track"


class Availability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScientificRequirement:
    identifier: str
    product: HydrologicalProduct
    assessment: ScientificAssessment | None

    def __post_init__(self) -> None:
        _text(self.identifier)
        if not isinstance(self.product, HydrologicalProduct):
            raise TypeError("exact HydrologicalProduct required")
        if self.assessment is not None and not isinstance(self.assessment, ScientificAssessment):
            raise TypeError("ScientificAssessment required")

    def check(self) -> Check:
        if self.assessment is None:
            return Check(self.identifier, CheckFinding.UNKNOWN, ("scientific assessment missing",))
        result = self.assessment.acceptance_for(self.product)
        return Check(self.identifier, result.finding, result.reasons)


@dataclass(frozen=True)
class ScopedRequirement:
    """Non-hydrological supplied evidence, e.g. reconstruction disclosure contract."""

    identifier: str
    scope: EvidenceScope
    findings: EvidenceFindings | None

    def __post_init__(self) -> None:
        _text(self.identifier)
        if not isinstance(self.scope, EvidenceScope):
            raise TypeError("exact EvidenceScope required")
        if self.findings is not None and not isinstance(self.findings, EvidenceFindings):
            raise TypeError("EvidenceFindings required")

    def check(self) -> Check:
        if self.findings is None:
            return Check(self.identifier, CheckFinding.UNKNOWN, ("required scoped evidence missing",))
        result = permitted_use(self.findings, self.scope)
        return Check(self.identifier, result.finding, result.reasons)


@dataclass(frozen=True)
class TierEvidence:
    route: NaturalRoute
    location: Location
    version: str
    specified: Availability
    resourced: Availability
    priority: Check
    required_ids: tuple[str, ...]
    statistics: tuple[ScientificRequirement, ...]
    prerequisites: tuple[ScopedRequirement, ...]
    studies: tuple[NaturalStudyComponent, ...]
    source: str
    natural_patterns: tuple[DailyPattern, ...] = ()
    recorded_minimum: RecordedMinimum | None = None
    required_study_components: tuple[str, ...] = ()
    study_trigger: HighFlowTrigger = HighFlowTrigger.NONE
    study_need: StudyNeed | None = None

    def __post_init__(self) -> None:
        for value in (self.version, self.source):
            _text(value)
        if self.route not in (NaturalRoute.TOP, NaturalRoute.BASELINE, NaturalRoute.ENTRY):
            raise ValueError("only natural tiers enter the tier ladder")
        if not isinstance(self.route, NaturalRoute) or not isinstance(self.location, Location):
            raise TypeError("typed route and location required")
        if not isinstance(self.specified, Availability) or not isinstance(self.resourced, Availability):
            raise TypeError("availability enums required")
        if not isinstance(self.priority, Check):
            raise TypeError("priority/trigger Check required")
        for values, kind in (
            (self.required_ids, str),
            (self.statistics, ScientificRequirement),
            (self.prerequisites, ScopedRequirement),
            (self.studies, NaturalStudyComponent),
            (self.natural_patterns, DailyPattern),
        ):
            if not isinstance(values, tuple) or any(not isinstance(v, kind) for v in values):
                raise TypeError("immutable typed requirements required")
        if not self.required_ids or len(set(self.required_ids)) != len(self.required_ids):
            raise ValueError("nonempty distinct required product IDs required")
        for identifier in self.required_ids:
            _text(identifier)
        actual = tuple(r.identifier for r in (*self.statistics, *self.prerequisites))
        if len(set(actual)) != len(actual) or set(actual) - set(self.required_ids):
            raise ValueError("duplicate or undeclared requirements")
        if any(r.product.location != self.location for r in self.statistics):
            raise ValueError("statistics refer to another location")
        if any(r.scope.reach != self.location.reach.identifier for r in self.prerequisites):
            raise ValueError("prerequisite evidence refers to another reach")
        if any(s.study.scope.location != self.location for s in self.studies):
            raise ValueError("study refers to another location")

    def data_checks(self, classification: PreparedClassification) -> CheckSummary:
        supplied = {r.identifier: r.check() for r in (*self.statistics, *self.prerequisites)}
        checks = [
            supplied[i] if i in supplied else Check(i, CheckFinding.UNKNOWN, ("required statistic missing",))
            for i in self.required_ids
        ]
        if self.route is NaturalRoute.ENTRY:
            checks.append(
                Check(
                    "entry_statistic",
                    CheckFinding.PASS
                    if any(r.product.kind is HydrologicalProductKind.LOW_FLOW_STATISTIC for r in self.statistics)
                    else CheckFinding.UNKNOWN,
                    ("entry needs a daily low-flow statistic",),
                )
            )
        if self.route is NaturalRoute.BASELINE:
            required_targets = {Fraction(p, 100) for p in (50, 75, 90, 97, 99)}
            targets = {p.magnitude.target.value for p in self.natural_patterns}
            checks.append(
                Check(
                    "natural_probability_family",
                    CheckFinding.PASS
                    if targets == required_targets and len(self.natural_patterns) == 5
                    else CheckFinding.UNKNOWN,
                    ("five own-probability natural patterns required",),
                )
            )
            if self.natural_patterns:
                first = self.natural_patterns[0]
                for index, pattern in enumerate(self.natural_patterns):
                    aligned = (
                        pattern.location == self.location
                        and pattern.calendar == first.calendar
                        and pattern.purpose is UsePurpose.SIZING
                        and pattern.magnitude.provenance.reference_kind is ReferenceKind.PRESENT_CLIMATE_NATURAL
                        and pattern.magnitude.reference_identity == first.magnitude.reference_identity
                        and pattern.magnitude.provenance.reference_member == first.magnitude.provenance.reference_member
                        and pattern.magnitude.provenance.scenario == first.magnitude.provenance.scenario
                    )
                    checks.append(
                        Check(
                            f"natural_pattern:{index}",
                            pattern.use_checks.finding if aligned else CheckFinding.FAIL,
                            tuple(reason for c in pattern.use_checks.checks for reason in c.reasons),
                        )
                    )
            record = self.recorded_minimum
            if record is None or record.assessment is None:
                checks.append(
                    Check("recorded_minimum", CheckFinding.UNKNOWN, ("accepted scalar recorded minimum missing",))
                )
            else:
                product = recorded_minimum_product(
                    record, intended_use=record.assessment.record.product.scope.intended_use, purpose=UsePurpose.SIZING
                )
                check = record.assessment.acceptance_for(product)
                aligned = record.reference.location == self.location and all(
                    (
                        p.magnitude.reference.reference_period == record.reference.reference_period
                        and p.magnitude.provenance.reference_member == record.reference.provenance.reference_member
                        and p.magnitude.provenance.scenario == record.reference.provenance.scenario
                    )
                    for p in self.natural_patterns
                )
                checks.append(Check("recorded_minimum", check.finding if aligned else CheckFinding.FAIL, check.reasons))
            disclosure = next((p for p in self.prerequisites if p.identifier == "reconstruction_disclosure"), None)
            checks.append(
                Check(
                    "reconstruction_contract",
                    disclosure.check().finding if disclosure else CheckFinding.UNKNOWN,
                    ("separate reconstruction disclosure contract required",),
                )
            )
        if self.route is NaturalRoute.TOP:
            if not self.studies or self.study_need is None or not self.required_study_components:
                checks.append(
                    Check(
                        "study_findings", CheckFinding.UNKNOWN, ("required habitat/holistic study inventory missing",)
                    )
                )
            else:
                # Run the supplied real eligibility. Extract only non-eligibility checks
                # for data support; never manufacture a priority decision or candidate.
                eligibility = TopTierEligibility.NOT_SELECTED
                if self.resourced is not Availability.AVAILABLE:
                    eligibility = TopTierEligibility.UNRESOURCED
                elif self.priority.finding is CheckFinding.PASS:
                    eligibility = (
                        TopTierEligibility.TRIGGERED
                        if self.study_trigger is not HighFlowTrigger.NONE
                        else TopTierEligibility.PRIORITY
                    )
                evaluated = assess_natural_study(
                    classification,
                    eligibility,
                    self.required_study_components,
                    self.studies,
                    self.study_trigger,
                    self.study_need,
                    "next_eligible_tier",
                )
                checks.extend(
                    Check(f"study:{c.check_id}", c.finding, c.reasons)
                    for c in evaluated.checks.checks
                    if c.check_id != "eligibility"
                )
        return CheckSummary(tuple(checks))


@dataclass(frozen=True)
class RouteFailure:
    route: NaturalRoute
    finding: CheckFinding
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.route, NaturalRoute) or not isinstance(self.finding, CheckFinding):
            raise TypeError("typed route and finding required")
        if self.finding is CheckFinding.PASS or not isinstance(self.reasons, tuple) or not self.reasons:
            raise ValueError("failed attempts need non-pass finding and reasons")
        for reason in self.reasons:
            _text(reason)


@dataclass(frozen=True)
class TierDecision:
    evidence: TierEvidence
    data: CheckSummary
    eligibility: CheckSummary


@dataclass(frozen=True)
class RouteDecision:
    selected: NaturalRoute
    highest_data_supported: NaturalRoute | None
    tiers: tuple[TierDecision, ...]
    failures: tuple[RouteFailure, ...]
    reasons: tuple[str, ...]


def select_natural_route(
    classification: PreparedClassification,
    tiers: tuple[TierEvidence, ...],
    failures: tuple[RouteFailure, ...] = (),
    *,
    transfer: TransferResult | None = None,
    presumptive: PresumptiveFloor | None = None,
) -> RouteDecision:
    """Inspect eligible tiers, then qualified transfer, presumptive floor, pending.

    Fallback results are re-evaluated from retained inputs, not pass labels.
    No existing duty is consumed or modified by route selection.
    """
    if not isinstance(tiers, tuple) or any(not isinstance(t, TierEvidence) for t in tiers):
        raise TypeError("tuple of TierEvidence required")
    if not isinstance(failures, tuple) or any(not isinstance(f, RouteFailure) for f in failures):
        raise TypeError("tuple of RouteFailure required")
    if len({t.route for t in tiers}) != len(tiers) or len({t.location for t in tiers}) > 1:
        raise ValueError("one evidence record per tier at the same location required")
    track = assessment_track(classification)
    if track.track is not Track.NATURAL:
        return RouteDecision(
            NaturalRoute.POTENTIAL if track.track is Track.POTENTIAL else NaturalRoute.PENDING,
            None,
            (),
            failures,
            (track.reason,),
        )
    by_route = {t.route: t for t in tiers}
    failed = {f.route for f in failures}
    decisions = []
    selected = None
    highest = None
    for route in (NaturalRoute.TOP, NaturalRoute.BASELINE, NaturalRoute.ENTRY):
        if route not in by_route:
            continue
        tier = by_route[route]
        data = tier.data_checks(classification)
        eligibility = [
            Check(
                "specified",
                CheckFinding.PASS if tier.specified is Availability.AVAILABLE else CheckFinding.UNKNOWN,
                (f"method {tier.specified.value}",),
            ),
            Check(
                "resourced",
                CheckFinding.PASS if tier.resourced is Availability.AVAILABLE else CheckFinding.UNKNOWN,
                (f"resources {tier.resourced.value}",),
            ),
        ]
        if route is NaturalRoute.TOP:
            eligibility.append(tier.priority)
        if route in failed:
            eligibility.append(Check("previous_attempt", CheckFinding.FAIL, ("route failed in this attempt",)))
        summary = CheckSummary(tuple(eligibility))
        decisions.append(TierDecision(tier, data, summary))
        if data.finding is CheckFinding.PASS:
            if highest is None:
                highest = route
            if selected is None and summary.finding is CheckFinding.PASS:
                selected = route
    fallback_checks = []
    if transfer is not None:
        if not isinstance(transfer, TransferResult):
            raise TypeError("assessed TransferResult required, not a pass label")
        if tiers and transfer.recipient_natural and transfer.recipient_natural[0].location != tiers[0].location:
            raise ValueError("fallback transfer belongs to another reach/location")
        evaluated = transfer_ecological_regime(
            transfer.donor,
            transfer.donor_natural,
            transfer.recipient_natural,
            transfer.profile,
            transfer.qualification,
            transfer.register,
            evaluated_at=transfer.evaluated_at,
        )
        fallback_checks.append((NaturalRoute.TRANSFER, evaluated.checks.finding))
    if presumptive is not None:
        if not isinstance(presumptive, PresumptiveFloor):
            raise TypeError("assessed PresumptiveFloor required, not a pass label")
        if tiers and presumptive.reference is not None and presumptive.reference.location != tiers[0].location:
            raise ValueError("presumptive reference belongs to another reach/location")
        evaluated_floor = presumptive_floor(presumptive.reference, presumptive.profile)
        fallback_checks.append((NaturalRoute.PRESUMPTIVE, evaluated_floor.checks.finding))
    if selected is None:
        for route, finding in fallback_checks:
            if route not in failed and finding is CheckFinding.PASS:
                selected = route
                break
    reasons = tuple(
        f"{d.evidence.route.value}: {c.check_id}: {reason}"
        for d in decisions
        for c in (*d.data.checks, *d.eligibility.checks)
        if c.finding is not CheckFinding.PASS
        for reason in c.reasons
    )
    if selected is None:
        reasons += ("pending — no computable basis; no zero or positive default; existing duties persist",)
    return RouteDecision(selected or NaturalRoute.PENDING, highest, tuple(decisions), failures, reasons)


class EntryVariant(StrEnum):
    DOMESTIC = "domestic"
    GRADUATED = "graduated"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class DomesticEntryContracts:
    """Five independently evidenced contracts; sanitary scenario sizing supplies none."""

    estimator: Check
    seasonal_windows: Check
    adequacy_rule: Check
    failure_route: Check
    selection_rule: Check
    competent_interpretation: Check

    def __post_init__(self) -> None:
        if any(not isinstance(c, Check) for c in self.checks):
            raise TypeError("independent contract checks required")

    @property
    def checks(self) -> tuple[Check, ...]:
        return (
            self.estimator,
            self.seasonal_windows,
            self.adequacy_rule,
            self.failure_route,
            self.selection_rule,
            self.competent_interpretation,
        )


@dataclass(frozen=True)
class EntryVariantDecision:
    variant: EntryVariant
    checks: tuple[Check, ...]


def select_entry_variant(
    contracts: DomesticEntryContracts | None,
    applicability: Check,
    statistic_adequacy: Check,
) -> EntryVariantDecision:
    """Ordered availability/applicability/adequacy; no result-based estimator shopping.

    Current proposed profile supplies no domestic contracts. None keeps it unavailable.
    Explicit complete future contracts permit assessment, not a sanitary estimator alias.
    """
    if not isinstance(applicability, Check) or not isinstance(statistic_adequacy, Check):
        raise TypeError("applicability and adequacy checks required")
    availability = (
        (
            Check(
                "domestic_contracts", CheckFinding.UNKNOWN, ("current domestic ecological-entry contracts unavailable",)
            ),
        )
        if contracts is None
        else contracts.checks
    )
    if CheckSummary(availability).finding is not CheckFinding.PASS:
        return EntryVariantDecision(EntryVariant.GRADUATED, availability)
    if applicability.finding is not CheckFinding.PASS:
        return EntryVariantDecision(EntryVariant.GRADUATED, (*availability, applicability))
    variant = EntryVariant.DOMESTIC if statistic_adequacy.finding is CheckFinding.PASS else EntryVariant.FALLBACK
    return EntryVariantDecision(variant, (*availability, applicability, statistic_adequacy))
