"""assess_sanitary_duty : SanitaryDuty × DeliveredFlows × HydraulicFindings → SanitaryAssessment.

Keeps instrument authority, flow comparisons and scoped specialist evidence separate.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from fishy.duties import Delivery, DutyApplicability, DutyAssessment, Requirement, SuppliedDuty, assess_duty
from fishy.evidence import CheckSummary, _text
from fishy.sanitary_hydraulics import HydraulicScope, ImportedHydraulicFinding, assess_imported_hydraulics


class Authenticity(StrEnum):
    AUTHENTICATED = "authenticated"
    SECONDARY_COPY = "secondary reproduction"
    UNRESOLVED = "unresolved"


class Currency(StrEnum):
    IN_FORCE = "in force"
    NOT_IN_FORCE = "not in force"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class InstrumentEvidence:
    source: str
    authority: str
    authenticity: Authenticity
    currency: Currency
    searched_on: date
    search_record: str
    follow_up: str

    def __post_init__(self) -> None:
        for name in ("source", "authority", "search_record", "follow_up"):
            _text(getattr(self, name), name)
        if not isinstance(self.authenticity, Authenticity) or not isinstance(self.currency, Currency):
            raise TypeError("instrument requires independent authenticity and currency enums")
        if type(self.searched_on) is not date:
            raise TypeError("instrument search requires a date")


@dataclass(frozen=True)
class SanitaryDuty:
    duty: SuppliedDuty
    instrument: InstrumentEvidence
    hydraulic_components: tuple[HydraulicScope, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.duty, SuppliedDuty) or not isinstance(self.instrument, InstrumentEvidence):
            raise TypeError("sanitary duty requires a supplied instrument and evidence")
        if self.duty.search_record != self.instrument.search_record:
            raise ValueError("instrument and duty search records must match")
        if self.duty.applicability is DutyApplicability.APPLICABLE and (
            self.instrument.authenticity is not Authenticity.AUTHENTICATED
            or self.instrument.currency is not Currency.IN_FORCE
        ):
            raise ValueError(
                "binding applicability requires separately authenticated, current evidence; use hypothetical or unresolved"
            )
        if not isinstance(self.hydraulic_components, tuple) or any(
            not isinstance(scope, HydraulicScope) for scope in self.hydraulic_components
        ):
            raise TypeError("hydraulic components require immutable HydraulicScope records")
        names = tuple(scope.component for scope in self.hydraulic_components)
        if len(set(names)) != len(names):
            raise ValueError("duplicate hydraulic components")
        if set(names) != set(self.duty.required_components) - {"discharge"}:
            raise ValueError("each non-discharge component requires its declared hydraulic scope")


@dataclass(frozen=True)
class SanitaryAssessment:
    supplied: SanitaryDuty
    candidate: str
    scenario: str
    flow_and_components: DutyAssessment
    hydraulic_findings: tuple[ImportedHydraulicFinding, ...]

    @property
    def summary(self) -> CheckSummary:
        return self.flow_and_components.summary


def assess_sanitary_duty(
    supplied: SanitaryDuty,
    deliveries: tuple[Delivery, ...],
    *,
    candidate: str,
    scenario: str,
    hydraulic_findings: tuple[ImportedHydraulicFinding, ...] = (),
) -> SanitaryAssessment:
    """Assess one candidate without estimating, capping or authenticating a duty.

    Generic pass flags cannot enter this boundary. Every specialist finding must
    match the declared component, domain, candidate, scenario and temporal scope.
    """
    _text(candidate, "candidate")
    _text(scenario, "scenario")
    if any(item.sample.provenance.scenario != scenario for item in deliveries):
        raise ValueError("delivery scenario differs from the assessed candidate scenario")
    if any(scope.candidate != candidate or scope.scenario != scenario for scope in supplied.hydraulic_components):
        raise ValueError("required hydraulic scope differs from candidate/scenario")
    if not isinstance(hydraulic_findings, tuple) or any(
        not isinstance(item, ImportedHydraulicFinding) for item in hydraulic_findings
    ):
        raise TypeError("sanitary components require attributable imported hydraulic findings")
    by_name = {item.scope.component: item for item in hydraulic_findings}
    if len(by_name) != len(hydraulic_findings):
        raise ValueError("duplicate hydraulic findings")
    if set(by_name) - {scope.component for scope in supplied.hydraulic_components}:
        raise ValueError("undeclared hydraulic finding")
    checks = tuple(
        assess_imported_hydraulics(scope, by_name[scope.component])
        for scope in supplied.hydraulic_components
        if scope.component in by_name
    )
    assessment = assess_duty(supplied.duty, deliveries, component_checks=checks)
    return SanitaryAssessment(supplied, candidate, scenario, assessment, hydraulic_findings)


@dataclass(frozen=True)
class EcologicalRequirementAssessment:
    """An externally assessed ecological requirement, never a merged sanitary duty."""

    identifier: str
    source: str
    candidate: str
    scenario: str
    requirements: tuple[Requirement, ...]
    findings: CheckSummary

    def __post_init__(self) -> None:
        for name in ("identifier", "source", "candidate", "scenario"):
            _text(getattr(self, name), name)
        if (
            not isinstance(self.requirements, tuple)
            or not self.requirements
            or any(not isinstance(item, Requirement) for item in self.requirements)
        ):
            raise TypeError("ecological requirements need attributable Requirement records")
        if any(item.sample.provenance.scenario != self.scenario for item in self.requirements):
            raise ValueError("ecological requirement scenario differs from its assessment")
        if not isinstance(self.findings, CheckSummary):
            raise TypeError("ecological component findings require CheckSummary")


@dataclass(frozen=True)
class RequirementConflict:
    first: str
    second: str
    source: str
    reason: str

    def __post_init__(self) -> None:
        for name in ("first", "second", "source", "reason"):
            _text(getattr(self, name), name)
        if self.first == self.second:
            raise ValueError("conflict must name two independently identified requirements")


@dataclass(frozen=True)
class CombinedAssessment:
    """Side-by-side findings, with no maximum, sum, precedence or demand conversion.

    Keys in conflicts use sanitary instrument identifier@version or ecological
    assessment identifier. Conflicts are supplied determinations, not inferred law.
    """

    sanitary: tuple[SanitaryAssessment, ...]
    ecological: tuple[EcologicalRequirementAssessment, ...] = ()
    conflicts: tuple[RequirementConflict, ...] = ()

    def __post_init__(self) -> None:
        for name, kind in (
            ("sanitary", SanitaryAssessment),
            ("ecological", EcologicalRequirementAssessment),
            ("conflicts", RequirementConflict),
        ):
            values = getattr(self, name)
            if not isinstance(values, tuple) or any(not isinstance(item, kind) for item in values):
                raise TypeError(f"{name} requires immutable attributable records")
        keys = tuple(f"{item.supplied.duty.identifier}@{item.supplied.duty.version}" for item in self.sanitary) + tuple(
            item.identifier for item in self.ecological
        )
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate requirement/version identity")
        if any(conflict.first not in keys or conflict.second not in keys for conflict in self.conflicts):
            raise ValueError("conflict references an absent requirement")
        identities = {(item.candidate, item.scenario) for item in (*self.sanitary, *self.ecological)}
        if len(identities) > 1:
            raise ValueError("combined findings must concern the same candidate and scenario")
