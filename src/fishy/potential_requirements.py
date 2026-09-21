"""size_potential_floor : PotentialInputs → OrderedRouteFindings × SeasonalFloor (pure).

Floor candidates do not issue requirements or delivery obligations. Existing duties
and additional process conditions pass unchanged to the assembly boundary.
"""

from dataclasses import dataclass
from enum import StrEnum

from fishy.duties import SuppliedDuty
from fishy.evidence import Check, CheckFinding, CheckSummary, EvidenceFindings, OfficialAdmissibility
from fishy.quantities import Flow
from fishy.service_conveyance import (
    ConveyanceStatus,
    ServiceConveyanceRequest,
    ServiceConveyanceResult,
    solve_service_conveyance,
)
from fishy.spatial import PreparedClassification, Track, assessment_track
from fishy.study_requirements import (
    FlowResponseRelation,
    StudyAssessment,
    StudyCondition,
    StudyNeed,
    StudyScope,
    StudySelection,
    StudyVariable,
    _evidence,
    _supported,
    _text,
    assess_study,
)


class PotentialRoute(StrEnum):
    HABITAT = "habitat"
    HYDRAULIC = "joint_velocity_depth"
    CONVEYANCE = "authenticated_service_conveyance"
    WINTER = "winter_share_suspended"
    ZERO = "supported_service_zero"


class Applicability(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class PotentialStudy:
    applicability: Applicability
    applicability_source: str
    selection: StudySelection | None
    relations: tuple[FlowResponseRelation, ...]

    def __post_init__(self) -> None:
        _text(self.applicability_source)
        if not isinstance(self.applicability, Applicability):
            raise TypeError("Applicability required")


class ZeroInterpretation(StrEnum):
    SERVICE_DETERMINATION = "service_determination"
    DESIGNED_DRY = "proposed_designed_dry_interpretation"


class AuthorityBasis(StrEnum):
    ADOPTED = "supplied_adopted_authority"
    HYPOTHETICAL = "explicit_hypothetical_treatment"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class ServiceZeroDetermination:
    scope: StudyScope
    interpretation: ZeroInterpretation
    basis: AuthorityBasis
    evidence: EvidenceFindings
    determination: str | None
    committee_signoff: str | None
    audit_right: str | None
    dispute_route: str | None
    service_impact_criterion: str | None
    review: StudyNeed
    drying_adoption: str | None = None

    def __post_init__(self) -> None:
        _evidence(self.scope, self.evidence)
        if not isinstance(self.interpretation, ZeroInterpretation) or not isinstance(self.basis, AuthorityBasis):
            raise TypeError("typed zero interpretation and authority basis required")
        for value in (
            self.determination,
            self.committee_signoff,
            self.audit_right,
            self.dispute_route,
            self.service_impact_criterion,
            self.drying_adoption,
        ):
            if value is not None:
                _text(value)


@dataclass(frozen=True)
class PotentialRouteFinding:
    route: PotentialRoute
    applicability: Applicability
    checks: CheckSummary
    flow: Flow | None
    next_route: PotentialRoute | None
    study: StudyAssessment | None = None
    conveyance: ServiceConveyanceResult | None = None


@dataclass(frozen=True)
class PotentialFloorResult:
    scope: StudyScope
    classification: PreparedClassification
    floor: Flow | None
    selected_route: PotentialRoute | None
    routes: tuple[PotentialRouteFinding, ...]
    additional_conditions: tuple[StudyCondition, ...]
    existing_duties: tuple[SuppliedDuty, ...]
    active_quality: tuple[StudyCondition, ...]
    review: StudyNeed
    zero_determination: ServiceZeroDetermination | None
    uncertainty: str
    requirement_state: str = "pending_full_requirement"
    obligation_state: str = "pending_new_delivery_obligation"
    output_kind: str = "seasonal_floor_only"


def _study_route(route: PotentialRoute, inputs: PotentialStudy, scope: StudyScope) -> PotentialRouteFinding:
    next_route = PotentialRoute.HYDRAULIC if route is PotentialRoute.HABITAT else PotentialRoute.CONVEYANCE
    checks = []
    result = None
    if inputs.applicability is not Applicability.APPLICABLE:
        checks.append(
            Check("applicability", CheckFinding.UNKNOWN, (inputs.applicability_source, inputs.applicability.value))
        )
    if inputs.selection is None:
        checks.append(
            Check("study", CheckFinding.UNKNOWN, ("required objective, selected criterion or relation missing",))
        )
    else:
        if inputs.selection.scope != scope:
            raise ValueError("potential study candidate scope mismatch")
        result = assess_study(inputs.selection, inputs.relations)
        checks.extend(result.checks.checks)
        required = (
            {StudyVariable.HABITAT}
            if route is PotentialRoute.HABITAT
            else {StudyVariable.DEPTH, StudyVariable.VELOCITY}
        )
        present = {c.variable.variable for c in inputs.selection.criteria}
        for variable in sorted(required - present):
            checks.append(Check(f"required_{variable.value}", CheckFinding.UNKNOWN, ("required route target missing",)))
        if "ramping" not in inputs.selection.required_conditions:
            checks.append(Check("route_ramping", CheckFinding.UNKNOWN, ("seasonal ramping condition missing",)))
    summary = CheckSummary(tuple(checks))
    flow = result.supported_flow if result and summary.finding is CheckFinding.PASS else None
    return PotentialRouteFinding(
        route, inputs.applicability, summary, flow, None if flow is not None else next_route, result
    )


def _zero_checks(zero: ServiceZeroDetermination) -> CheckSummary:
    checks = [
        Check(
            "zero_evidence",
            CheckFinding.PASS if _supported(zero.evidence) else CheckFinding.UNKNOWN,
            (zero.interpretation.value, zero.basis.value),
        )
    ]
    for field in ("determination", "committee_signoff", "audit_right", "dispute_route", "service_impact_criterion"):
        value = getattr(zero, field)
        checks.append(
            Check(
                field,
                CheckFinding.PASS if value is not None else CheckFinding.UNKNOWN,
                (value,) if value is not None else ("required service determination evidence missing",),
            )
        )
    if zero.basis is AuthorityBasis.UNRESOLVED:
        checks.append(Check("authority", CheckFinding.UNKNOWN, ("adopted or explicitly hypothetical basis required",)))
    if zero.interpretation is ZeroInterpretation.DESIGNED_DRY and zero.drying_adoption is None:
        checks.append(
            Check(
                "drying_adoption",
                CheckFinding.UNKNOWN,
                ("characteristic-drying reading not adopted or explicitly assumed",),
            )
        )
    if zero.review.owner is None or zero.review.deadline is None:
        checks.append(Check("zero_review", CheckFinding.UNKNOWN, ("responsible review owner and date required",)))
    return CheckSummary(tuple(checks))


def size_potential_floor(
    scope: StudyScope,
    classification: PreparedClassification,
    habitat: PotentialStudy,
    hydraulics: PotentialStudy,
    conveyance: ServiceConveyanceRequest | None,
    review: StudyNeed,
    *,
    existing_duties: tuple[SuppliedDuty, ...] = (),
    additional_conditions: tuple[StudyCondition, ...] = (),
    active_quality: tuple[StudyCondition, ...] = (),
    zero: ServiceZeroDetermination | None = None,
) -> PotentialFloorResult:
    """Try habitat, joint hydraulics then service; never erase earlier unresolved ecology.

    Quality and receptor integration belongs to final assembly. Conditions supplied
    here retain their exact candidate and period and are not silently summed.
    """
    if assessment_track(classification).track is not Track.POTENTIAL:
        raise ValueError("potential sizing requires supported origin or valid designation")
    if review.owner is None or review.deadline is None:
        raise ValueError("pending routes require responsibility and revisit date")
    if any(c.scope != scope for c in (*additional_conditions, *active_quality)):
        raise ValueError("additional conditions must retain exact candidate scope")
    if zero is not None and zero.scope != scope:
        raise ValueError("zero determination scope mismatch")
    evidence = [c.evidence for c in (*additional_conditions, *active_quality)]
    for inputs in (habitat, hydraulics):
        if inputs.selection is not None:
            evidence.append(inputs.selection.evidence)
    if conveyance is not None:
        evidence.extend(d.evidence for d in conveyance.duties)
        if conveyance.relation is not None:
            evidence.append(conveyance.relation.evidence)
    if zero is not None:
        evidence.append(zero.evidence)
    if len({e.provenance.configuration_version for e in evidence}) > 1:
        raise ValueError("incompatible potential configuration versions")
    routes = []
    calculated = None
    flow = None
    selected = None
    for route, inputs in ((PotentialRoute.HABITAT, habitat), (PotentialRoute.HYDRAULIC, hydraulics)):
        record = _study_route(route, inputs, scope)
        routes.append(record)
        if record.flow is not None:
            flow, selected = record.flow, route
            break
    if flow is None:
        calculated = None
        if conveyance is None:
            summary = CheckSummary(
                (Check("conveyance", CheckFinding.UNKNOWN, ("authenticated service duty or relation missing",)),)
            )
        else:
            if conveyance.location != scope.location or conveyance.interval != scope.period:
                raise ValueError("conveyance location/interval mismatch")
            evidence = [item.evidence for item in (*conveyance.duties, *conveyance.other_inflows)]
            if conveyance.relation is not None:
                evidence.append(conveyance.relation.evidence)
            if any(
                (e.provenance.scenario, e.provenance.reference_member) != (scope.scenario, scope.reference_member)
                for e in evidence
            ):
                raise ValueError("conveyance scenario/reference mismatch")
            calculated = solve_service_conveyance(conveyance)
            flow = calculated.flow
            summary = CheckSummary(
                (
                    Check(
                        "conveyance",
                        CheckFinding.PASS
                        if flow is not None
                        else CheckFinding.FAIL
                        if calculated.status is ConveyanceStatus.INFEASIBLE
                        else CheckFinding.UNKNOWN,
                        calculated.reasons or ("service balance only; no ecological adequacy claim",),
                    ),
                )
            )
        routes.append(
            PotentialRouteFinding(
                PotentialRoute.CONVEYANCE,
                Applicability.APPLICABLE,
                summary,
                flow,
                None if flow is not None else PotentialRoute.WINTER,
                conveyance=calculated,
            )
        )
        if flow is not None:
            selected = PotentialRoute.CONVEYANCE
    if flow is None:
        routes.append(
            PotentialRouteFinding(
                PotentialRoute.WINTER,
                Applicability.NOT_APPLICABLE,
                CheckSummary(
                    (Check("winter_share", CheckFinding.UNKNOWN, ("suspended; cannot size or rescue a route",)),)
                ),
                None,
                None,
            )
        )
    # Any zero candidate, including a numerical hydraulic/service zero, needs the
    # evidence-backed service determination. Missing data is never permission.
    if flow is None or flow.value == 0:
        if zero is not None:
            checks = _zero_checks(zero)
        else:
            checks = CheckSummary(
                (Check("zero", CheckFinding.UNKNOWN, ("supported zero determination not supplied",)),)
            )
        if zero is not None or flow is not None:
            if conveyance is not None and (calculated is None or calculated.zero_candidate is None):
                finding = (
                    CheckFinding.FAIL
                    if calculated is not None and calculated.status is ConveyanceStatus.INFEASIBLE
                    else CheckFinding.UNKNOWN
                )
                checks = CheckSummary(
                    (
                        *checks.checks,
                        Check(
                            "zero_service_balance",
                            finding,
                            (
                                "a supplied service account must support zero; a determination cannot erase duties or physical failure",
                            ),
                        ),
                    )
                )
            accepted = checks.finding is CheckFinding.PASS
            flow = Flow(0) if accepted else None
            selected = PotentialRoute.ZERO if accepted else None
            routes.append(PotentialRouteFinding(PotentialRoute.ZERO, Applicability.APPLICABLE, checks, flow, None))
    return PotentialFloorResult(
        scope,
        classification,
        flow,
        selected,
        tuple(routes),
        additional_conditions,
        existing_duties,
        active_quality,
        review,
        zero,
        "high" if flow is None else "as_supplied_in_evidence",
    )


@dataclass(frozen=True)
class IssuedRequirementVersion:
    identifier: str
    track: Track
    duties: tuple[SuppliedDuty, ...]
    authority: str

    def __post_init__(self) -> None:
        _text(self.identifier)
        _text(self.authority)
        if not isinstance(self.track, Track) or self.track is Track.UNDETERMINED:
            raise ValueError("issued requirement needs a supported track")
        if not isinstance(self.duties, tuple) or any(not isinstance(d, SuppliedDuty) for d in self.duties):
            raise TypeError("issued version needs immutable duties")


@dataclass(frozen=True)
class ReplacementDecision:
    previous_version: str
    replacement_version: IssuedRequirementVersion
    competent_revision: str
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        _text(self.previous_version)
        _text(self.competent_revision)


@dataclass(frozen=True)
class RequirementHistory:
    classification: PreparedClassification
    issued: tuple[IssuedRequirementVersion, ...]
    in_force: IssuedRequirementVersion | None
    proposal: PotentialFloorResult
    replacement: ReplacementDecision | None


def retain_requirement_history(
    proposal: PotentialFloorResult,
    issued: tuple[IssuedRequirementVersion, ...],
    replacement: ReplacementDecision | None = None,
) -> RequirementHistory:
    """Retain prior issuance until an attributable competent supported replacement.

    No prior version is fabricated for a reach designated before first calculation.
    This operation records a supplied decision; it does not issue a new duty.
    """
    if len({item.identifier for item in issued}) != len(issued):
        raise ValueError("duplicate issued versions")
    current = issued[-1] if issued else None
    if replacement is not None:
        _evidence(proposal.scope, replacement.evidence)
        if current is None or replacement.previous_version != current.identifier:
            raise ValueError("replacement must name the actual previous issued version")
        if replacement.replacement_version.identifier in {item.identifier for item in issued}:
            raise ValueError("replacement must have a new version")
        if replacement.replacement_version.track is not Track.POTENTIAL:
            raise ValueError("valid designation cannot issue a new natural result")
        if (
            proposal.floor is not None
            and _supported(replacement.evidence)
            and replacement.evidence.official_admissibility is OfficialAdmissibility.ADMISSIBLE
        ):
            current = replacement.replacement_version
            issued += (current,)
    return RequirementHistory(proposal.classification, issued, current, proposal, replacement)
