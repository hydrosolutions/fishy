"""assess_exception : Flow × Flow × ExceptionScope × ExceptionConditions × ExceptionDecision? → ExceptionAssessment.

Literal GSchG (2025-08-01) Art. 32 and GSchV (2025-12-01) Arts. 33a–34.
Supplied site findings and decisions are assessed, never inferred from arithmetic.
"""

from dataclasses import dataclass, fields, replace
from enum import StrEnum
from fractions import Fraction
from typing import get_type_hints

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    OfficialAdmissibility,
    permitted_use,
)
from fishy.quantities import Elevation as Elevation
from fishy.quantities import Flow, Number, finite_number
from fishy.spatial import Location
from fishy.time import Interval


class ExceptionClause(StrEnum):
    HIGH_ALTITUDE = "32(a)"
    NON_FISH = "32(b)"
    LOW_POTENTIAL = "32(bbis)"
    PROTECTION_PLAN = "32(c)"
    EMERGENCY = "32(d)"


class DecisionBasis(StrEnum):
    AUTHORISED = "authorised"
    HYPOTHETICAL = "hypothetical"


class FishStatus(StrEnum):
    NON_FISH = "non_fish"
    FISH = "fish"


class Significance(StrEnum):
    LOW = "low"
    NOT_LOW = "not_low"


class FunctionalImpact(StrEnum):
    NOT_SUBSTANTIAL = "not_substantial"
    SUBSTANTIAL = "substantial"


class AreaConnection(StrEnum):
    LIMITED_CONNECTED = "limited_topographically_connected"
    NOT_LIMITED_CONNECTED = "not_limited_topographically_connected"


class CompensationPurpose(StrEnum):
    WATER_OR_DEPENDENT_HABITAT = "water_or_dependent_habitat"
    OTHER = "other"


class LegalRequirement(StrEnum):
    ADDITIONAL = "additional"
    ALREADY_REQUIRED = "already_required"


class CompensationAdequacy(StrEnum):
    ADEQUATE = "adequate"
    INADEQUATE = "inadequate"


class PlanApproval(StrEnum):
    FEDERAL_COUNCIL = "federal_council"
    NOT_APPROVED = "not_approved"


class EmergencyBasis(StrEnum):
    EMERGENCY = "identified_emergency"
    ORDINARY_SCARCITY = "ordinary_scarcity"


class AltitudeEndpoints(StrEnum):
    INCLUSIVE_SCENARIO = "explicit_hypothetical_inclusive_1500_1700"
    AUTHORITY_INCLUSIVE = "supplied_authority_inclusive_1500_1700"
    EXCLUSIVE = "explicit_exclusive_endpoints"


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("attribution and identifiers must be nonempty")


@dataclass(frozen=True, init=False)
class DownstreamExtent:
    """Nonnegative ordered distances in metres downstream from the named intake."""

    start_metres: Fraction
    end_metres: Fraction

    def __init__(self, start_metres: Number, end_metres: Number) -> None:
        start, end = finite_number(start_metres), finite_number(end_metres)
        if not 0 <= start < end:
            raise ValueError("downstream extent must be nonnegative and increasing")
        object.__setattr__(self, "start_metres", start)
        object.__setattr__(self, "end_metres", end)


@dataclass(frozen=True)
class ExceptionScope:
    location: Location
    intake: str
    scenario: str
    member: str | None
    period: Interval
    extent: DownstreamExtent
    configuration_version: str
    data_version: str

    def __post_init__(self) -> None:
        for value in (self.intake, self.scenario, self.configuration_version, self.data_version):
            _text(value)
        if self.member is not None:
            _text(self.member)
        for value, kind in ((self.location, Location), (self.period, Interval), (self.extent, DownstreamExtent)):
            if not isinstance(value, kind):
                raise TypeError("exception scope requires typed location, interval and extent")

    def evidence_scope(self, clause: ExceptionClause) -> EvidenceScope:
        identity = (
            clause.value,
            self.location,
            self.intake,
            self.extent,
            self.scenario,
            self.configuration_version,
            self.data_version,
        )
        return EvidenceScope(
            repr(identity),
            f"{self.location.reach.identifier}@{self.location.reach.version}",
            self.member,
            self.period,
            "residual-flow exception",
        )


class _ConditionRecord:
    def __post_init__(self) -> None:
        for name, kind in get_type_hints(type(self)).items():
            value = getattr(self, name)
            if not isinstance(value, kind):
                raise TypeError(f"{name} requires its declared domain type")
            if isinstance(value, str):
                _text(value)


@dataclass(frozen=True)
class HighAltitudeWater(_ConditionRecord):
    evidence: EvidenceFindings | None
    elevation: Elevation | None
    fish_status: FishStatus | None
    endpoints: AltitudeEndpoints | None = None
    endpoint_source: str | None = None


@dataclass(frozen=True)
class NonFishWater(_ConditionRecord):
    evidence: EvidenceFindings | None
    fish_status: FishStatus | None


@dataclass(frozen=True)
class LowEcologicalPotential(_ConditionRecord):
    evidence: EvidenceFindings | None
    present_significance: Significance | None
    restored_significance: Significance | None
    proportionate_restoration_study: str | None
    natural_functions: FunctionalImpact | None


@dataclass(frozen=True)
class ProtectionUsePlan(_ConditionRecord):
    evidence: EvidenceFindings | None
    plan: str | None
    area: str | None
    connection: AreaConnection | None
    compensation_area: str | None
    compensation_purpose: CompensationPurpose | None
    legal_requirement: LegalRequirement | None
    adequacy: CompensationAdequacy | None
    adequacy_explanation: str | None
    binding_arrangement: str | None
    binding_period: Interval | None
    concession_period: Interval | None
    approval: PlanApproval | None
    approval_reference: str | None
    application_to_foen: str | None


@dataclass(frozen=True)
class EmergencyAbstraction(_ConditionRecord):
    evidence: EvidenceFindings | None
    basis: EmergencyBasis | None
    emergency_reference: str | None
    temporary_period: Interval | None


type ExceptionConditions = (
    HighAltitudeWater | NonFishWater | LowEcologicalPotential | ProtectionUsePlan | EmergencyAbstraction
)


@dataclass(frozen=True)
class ExceptionDecision:
    scope: ExceptionScope
    clause: ExceptionClause
    minimum: Flow
    basis: DecisionBasis
    issuer: str
    reference: str
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        for value in (self.issuer, self.reference):
            _text(value)
        for value, kind in (
            (self.scope, ExceptionScope),
            (self.clause, ExceptionClause),
            (self.minimum, Flow),
            (self.basis, DecisionBasis),
            (self.evidence, EvidenceFindings),
        ):
            if not isinstance(value, kind):
                raise TypeError("exception decision requires domain records")


def condition_evidence_scope(
    scope: ExceptionScope, clause: ExceptionClause, conditions: ExceptionConditions
) -> EvidenceScope:
    """Identify the reviewed condition values, excluding the evidence wrapper itself."""
    subject = tuple(
        (field.name, getattr(conditions, field.name)) for field in fields(conditions) if field.name != "evidence"
    )
    base = scope.evidence_scope(clause)
    return replace(base, product=repr((base.product, type(conditions).__name__, subject)))


def decision_evidence_scope(
    scope: ExceptionScope,
    clause: ExceptionClause,
    minimum: Flow,
    basis: DecisionBasis,
    issuer: str,
    reference: str,
) -> EvidenceScope:
    """Identify the exact reviewed lower amount, decision basis and attribution."""
    base = scope.evidence_scope(clause)
    return replace(base, product=repr((base.product, minimum, basis, issuer, reference)))


@dataclass(frozen=True)
class ExceptionAssessment:
    scope: ExceptionScope
    clause: ExceptionClause
    q347: Flow
    ordinary_minimum: Flow
    conditions: ExceptionConditions
    decision: ExceptionDecision | None
    summary: CheckSummary
    applied_minimum: Flow | None
    sources: tuple[str, ...] = ("GSchG 2025-08-01 Art. 32", "GSchV 2025-12-01 Arts. 33a–34", "FOEN 2000 §§4.5–4.6")
    restrictions: tuple[str, ...] = (
        "Normal Arts. 31 and 33 protection remains outside the exception extent and period.",
        "Separate Art. 33 interest balancing remains required, including after an exception.",
        "Passing eligibility neither issues a permit nor authenticates supplied evidence.",
    )


def assess_exception(
    q347: Flow,
    ordinary_minimum: Flow,
    scope: ExceptionScope,
    conditions: ExceptionConditions,
    decision: ExceptionDecision | None,
) -> ExceptionAssessment:
    """Return a lower value only when conditions and the scoped decision are supported.

    Missing inputs and unsupported uses remain separate UNKNOWN reasons. Known failed
    conditions survive either. The ordinary value is retained, not silently applied as
    a substitute for an unresolved exception decision.
    """
    if not isinstance(q347, Flow) or not isinstance(ordinary_minimum, Flow) or not isinstance(scope, ExceptionScope):
        raise TypeError("Flow quantities and ExceptionScope required")
    clauses: dict[type, ExceptionClause] = {
        HighAltitudeWater: ExceptionClause.HIGH_ALTITUDE,
        NonFishWater: ExceptionClause.NON_FISH,
        LowEcologicalPotential: ExceptionClause.LOW_POTENTIAL,
        ProtectionUsePlan: ExceptionClause.PROTECTION_PLAN,
        EmergencyAbstraction: ExceptionClause.EMERGENCY,
    }
    if type(conditions) not in clauses:
        raise TypeError("unsupported exception conditions")
    clause = clauses[type(conditions)]
    checks: list[Check] = []

    def test(name: str, result: bool | None, reason: str) -> None:
        finding = CheckFinding.UNKNOWN if result is None else CheckFinding.PASS if result else CheckFinding.FAIL
        checks.append(Check(name, finding, (reason,)))

    def field(name: str, value: object, expected: object) -> None:
        if value is not None and not isinstance(value, type(expected)):
            raise TypeError(f"{name} requires {type(expected).__name__}")
        test(name, None if value is None else value == expected, f"{name}: {value}; required {expected}")

    def text(name: str, value: str | None) -> None:
        if value is not None:
            _text(value)
        test(name, None if value is None else True, f"{name}: {value or 'missing'}")

    def evidence(name: str, findings: EvidenceFindings | None, expected_scope: EvidenceScope) -> None:
        if findings is None:
            test(name, None, "missing attributed evidence")
            return
        test(
            name + "/versions",
            findings.provenance.configuration_version == scope.configuration_version
            and findings.provenance.data_version == scope.data_version,
            "evidence must match declared configuration and data versions",
        )
        check = permitted_use(findings, expected_scope)
        checks.append(Check(name, check.finding, check.reasons))
        test(
            name + "/scenario",
            findings.provenance.scenario == scope.scenario and findings.provenance.reference_member == scope.member,
            "evidence scenario and member must match",
        )

    evidence("conditions/evidence", conditions.evidence, condition_evidence_scope(scope, clause, conditions))
    if isinstance(conditions, HighAltitudeWater):
        test("q347<50l/s", q347.value < Flow(50, "l/s").value, "strict Q347 <50 l/s")
        test("reach<=1000m", scope.extent.end_metres <= 1000, "within 1000 metres below intake")
        if conditions.elevation is None:
            test("altitude", None, "missing elevation")
        else:
            if not isinstance(conditions.elevation, Elevation):
                raise TypeError("elevation requires Elevation")
            z = conditions.elevation.metres
            if z > 1700:
                test("altitude", True, "strictly above 1700 m")
            elif z < 1500:
                test("altitude", False, "below non-fish band")
            else:
                field("non_fish", conditions.fish_status, FishStatus.NON_FISH)
                if z in (1500, 1700):
                    selection = conditions.endpoints
                    if selection is not None and not isinstance(selection, AltitudeEndpoints):
                        raise TypeError("typed altitude interpretation required")
                    test(
                        "altitude_endpoints",
                        None if selection is None else selection is not AltitudeEndpoints.EXCLUSIVE,
                        f"exact endpoint selection: {selection}",
                    )
                    text("endpoint_source", conditions.endpoint_source)
                    if selection is AltitudeEndpoints.INCLUSIVE_SCENARIO:
                        test(
                            "endpoint_scenario",
                            None if decision is None else decision.basis is DecisionBasis.HYPOTHETICAL,
                            "inclusive scenario must remain hypothetical",
                        )
                    elif selection is AltitudeEndpoints.AUTHORITY_INCLUSIVE:
                        test(
                            "endpoint_authority",
                            None
                            if conditions.evidence is None
                            else conditions.evidence.official_admissibility is OfficialAdmissibility.ADMISSIBLE,
                            "endpoint reading requires supplied admissible authority evidence",
                        )
                else:
                    test("altitude", True, "strictly inside 1500–1700 m band")
    elif isinstance(conditions, NonFishWater):
        field("non_fish", conditions.fish_status, FishStatus.NON_FISH)
        test(
            "residual>=35%q347",
            None if decision is None else decision.minimum.value >= q347.value * Fraction(35, 100),
            "reduced residual must be at least 35% of Q347",
        )
    elif isinstance(conditions, LowEcologicalPotential):
        test("reach<=1000m", scope.extent.end_metres <= 1000, "within 1000 metres below intake")
        field("present_significance", conditions.present_significance, Significance.LOW)
        field("restored_significance", conditions.restored_significance, Significance.LOW)
        text("proportionate_restoration_study", conditions.proportionate_restoration_study)
        field("natural_functions", conditions.natural_functions, FunctionalImpact.NOT_SUBSTANTIAL)
    elif isinstance(conditions, ProtectionUsePlan):
        for name in (
            "plan",
            "area",
            "compensation_area",
            "adequacy_explanation",
            "binding_arrangement",
            "approval_reference",
            "application_to_foen",
        ):
            text(name, getattr(conditions, name))
        field("area_connection", conditions.connection, AreaConnection.LIMITED_CONNECTED)
        test(
            "same_area",
            None
            if conditions.area is None or conditions.compensation_area is None
            else conditions.area == conditions.compensation_area,
            "compensation in the same limited area",
        )
        field("compensation_purpose", conditions.compensation_purpose, CompensationPurpose.WATER_OR_DEPENDENT_HABITAT)
        field("additional_compensation", conditions.legal_requirement, LegalRequirement.ADDITIONAL)
        field("compensation_adequacy", conditions.adequacy, CompensationAdequacy.ADEQUATE)
        field("plan_approval", conditions.approval, PlanApproval.FEDERAL_COUNCIL)
        binding, concession = conditions.binding_period, conditions.concession_period
        test(
            "binding_concession_duration",
            None
            if binding is None or concession is None
            else binding.start <= concession.start and binding.end >= concession.end,
            "arrangements bind everyone for the entire concession",
        )
        test(
            "concession_scope",
            None
            if concession is None
            else concession.start <= scope.period.start and concession.end >= scope.period.end,
            "exception within concession",
        )
    else:
        field("emergency_basis", conditions.basis, EmergencyBasis.EMERGENCY)
        text("emergency_reference", conditions.emergency_reference)
        period = conditions.temporary_period
        test(
            "temporary_scope",
            None if period is None else period.start <= scope.period.start and period.end >= scope.period.end,
            "identified temporary emergency period",
        )
    if decision is None:
        test("decision", None, "missing authorised or explicitly hypothetical decision")
    else:
        if not isinstance(decision, ExceptionDecision):
            raise TypeError("ExceptionDecision required")
        test(
            "decision_scope",
            decision.scope == scope and decision.clause is clause,
            "exact decision reach, period, scenario and clause",
        )
        test(
            "lower_minimum",
            decision.minimum.value < ordinary_minimum.value,
            "decision specifies a lower numerical minimum",
        )
        evidence(
            "decision/evidence",
            decision.evidence,
            decision_evidence_scope(
                scope,
                clause,
                decision.minimum,
                decision.basis,
                decision.issuer,
                decision.reference,
            ),
        )
        test(
            "reference_kind",
            None
            if conditions.evidence is None
            else decision.evidence.provenance.reference_kind == conditions.evidence.provenance.reference_kind,
            "condition evidence and decision must use the same reference kind",
        )
        if decision.basis is DecisionBasis.AUTHORISED:
            test(
                "official_decision",
                decision.evidence.official_admissibility is OfficialAdmissibility.ADMISSIBLE,
                "authorised decision needs supplied official admissibility",
            )
            test(
                "official_conditions",
                None
                if conditions.evidence is None
                else conditions.evidence.official_admissibility is OfficialAdmissibility.ADMISSIBLE,
                "official use requires admissible condition evidence",
            )
    summary = CheckSummary(tuple(checks))
    return ExceptionAssessment(
        scope,
        clause,
        q347,
        ordinary_minimum,
        conditions,
        decision,
        summary,
        decision.minimum if decision is not None and summary.finding is CheckFinding.PASS else None,
    )


def effective_minimum_for(scope: ExceptionScope, assessment: ExceptionAssessment) -> Flow | None:
    """Select the supported exception or retained ordinary minimum for a segment.

    Disjoint spatial or temporal segments retain normal protection. Contained
    segments receive a reduction only from a passing assessment. Straddling segments
    require caller subdivision; unrelated physical/scenario identities are unsupported.
    This selects residual minima, not an intake schedule or Art. 33 final decision.
    """
    if not isinstance(scope, ExceptionScope) or not isinstance(assessment, ExceptionAssessment):
        raise TypeError("typed requested scope and exception assessment required")
    assessment = assess_exception(
        assessment.q347,
        assessment.ordinary_minimum,
        assessment.scope,
        assessment.conditions,
        assessment.decision,
    )
    granted = assessment.scope
    if (
        scope.location,
        scope.intake,
        scope.scenario,
        scope.member,
        scope.configuration_version,
        scope.data_version,
    ) != (
        granted.location,
        granted.intake,
        granted.scenario,
        granted.member,
        granted.configuration_version,
        granted.data_version,
    ):
        return None
    spatially_disjoint = (
        scope.extent.end_metres <= granted.extent.start_metres or scope.extent.start_metres >= granted.extent.end_metres
    )
    temporally_disjoint = scope.period.end <= granted.period.start or scope.period.start >= granted.period.end
    if spatially_disjoint or temporally_disjoint:
        return assessment.ordinary_minimum
    contained = (
        granted.extent.start_metres <= scope.extent.start_metres
        and scope.extent.end_metres <= granted.extent.end_metres
        and granted.period.start <= scope.period.start
        and scope.period.end <= granted.period.end
    )
    if contained:
        return assessment.applied_minimum
    return None
