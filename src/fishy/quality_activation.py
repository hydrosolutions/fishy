"""apply_quality_component : BaseFlow × FixedBoundary × ActivationEvidence → QualityComponent.

Report residual dilution is gated by source control and exact accounts before sizing.
This operation combines one matched interval, not a seasonal regime or issued duty.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from fractions import Fraction

from fishy.load_accounts import AccountAssessment, SourceControlEvidence
from fishy.mixing import (
    CheckOutcome,
    Feasibility,
    FixedBoundary,
    FlowConstraints,
    MixingRecheck,
    MixingResult,
    MixingTarget,
    recheck_mixing,
    solve_mixing,
)
from fishy.quantities import Flow
from fishy.spatial import Location


class EvidenceState(StrEnum):
    HELD = "held"
    MISSING = "missing"


@dataclass(frozen=True)
class ActivationCondition:
    state: EvidenceState
    evidence: str

    def __post_init__(self) -> None:
        if not isinstance(self.state, EvidenceState):
            raise TypeError("condition requires EvidenceState")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("condition requires evidence or missing-evidence reason")


@dataclass(frozen=True)
class ActivationConditions:
    reach_season_screen: ActivationCondition
    fisheries_targets: ActivationCondition
    approved_harmfulness_grouping: ActivationCondition
    basin_salt_budget: ActivationCondition
    ncecc_approved_transport_model: ActivationCondition

    def __post_init__(self) -> None:
        if any(not isinstance(value, ActivationCondition) for value in self.values):
            raise TypeError("all five activation conditions must be explicit")

    @property
    def values(self) -> tuple[ActivationCondition, ...]:
        return (
            self.reach_season_screen,
            self.fisheries_targets,
            self.approved_harmfulness_grouping,
            self.basin_salt_budget,
            self.ncecc_approved_transport_model,
        )

    @property
    def missing(self) -> tuple[str, ...]:
        names = (
            "reach_season_screen",
            "fisheries_targets",
            "approved_harmfulness_grouping",
            "basin_salt_budget",
            "ncecc_approved_transport_model",
        )
        return tuple(
            name for name, condition in zip(names, self.values, strict=True) if condition.state is EvidenceState.MISSING
        )


class ActivationMode(StrEnum):
    ADVISORY = "advisory"
    REPORT = "report"
    HYPOTHETICAL = "hypothetical"


class QualityRoute(StrEnum):
    REGIME = "regime"
    FLOOR_ONLY = "floor_only"


class ComponentStatus(StrEnum):
    ADVISORY = "advisory"
    ACTIVE = "active"
    HYPOTHETICAL = "hypothetical"
    INFEASIBLE = "infeasible"
    UNSIZED = "unsized"


@dataclass(frozen=True)
class QualityActivation:
    scenario: str
    route: QualityRoute
    mode: ActivationMode
    conditions: ActivationConditions
    decision_basis: str

    def __post_init__(self) -> None:
        for value in (self.scenario, self.decision_basis):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("activation requires scenario identity and applicable decision basis")
        if not isinstance(self.route, QualityRoute) or not isinstance(self.mode, ActivationMode):
            raise TypeError("activation requires route and mode enums")
        if not isinstance(self.conditions, ActivationConditions):
            raise TypeError("activation requires five explicit conditions")


@dataclass(frozen=True)
class BackgroundAccountMapping:
    """Identified incoming background carriers and separate loads, excluding arrival q.

    Every constituent ledger must retain these same physical transfers, including
    explicit zero constituent mass where supported. An empty mapping denotes a
    dry, load-free background, not missing accounting evidence.
    """

    transfer_ids: tuple[str, ...]
    basis: str
    location: Location
    arrival_transfer_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.basis, str) or not self.basis.strip():
            raise ValueError("background account mapping requires an attributable basis")
        if not isinstance(self.location, Location):
            raise TypeError("background account mapping requires a prepared Location")
        if not isinstance(self.transfer_ids, tuple) or any(
            not isinstance(value, str) or not value.strip() for value in self.transfer_ids
        ):
            raise TypeError("background transfer IDs require an immutable tuple of nonempty text")
        if not isinstance(self.arrival_transfer_ids, tuple) or any(
            not isinstance(value, str) or not value.strip() for value in self.arrival_transfer_ids
        ):
            raise TypeError("arrival transfer IDs require an immutable tuple of nonempty text")
        identifiers = self.transfer_ids + self.arrival_transfer_ids
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("duplicate or overlapping background/arrival transfer IDs")

    def require_matches(self, boundary: FixedBoundary, accounts: tuple[AccountAssessment, ...]) -> None:
        if self.location != boundary.location:
            raise ValueError("account mapping prepared location does not match fixed-boundary location")
        carriers = {}
        for constituent in boundary.constituents:
            ledgers = tuple(a for a in accounts if a.accounts[0].constituent == constituent.chemical)
            if len(ledgers) != 1:
                raise ValueError("background requires exactly one ledger per boundary chemical identity")
            ledger = ledgers[0]
            transfers = {transfer.identifier: transfer for transfer in ledger.transfers}
            for transfer in ledger.transfers:
                if transfer.destination == boundary.location.section.identifier:
                    carrier = (transfer.origin, transfer.destination, transfer.amount.water)
                    if transfer.identifier in carriers and carriers[transfer.identifier] != carrier:
                        raise ValueError("constituent ledgers disagree on a shared physical water carrier")
                    carriers[transfer.identifier] = carrier
            incoming = {t.identifier for t in ledger.transfers if t.destination == boundary.location.section.identifier}
            if incoming != set(self.transfer_ids + self.arrival_transfer_ids):
                raise ValueError(
                    "every incoming section transfer must be classified as background or arrival exactly once"
                )
            arrival_water = sum((transfers[i].amount.water.value for i in self.arrival_transfer_ids), Fraction())
            arrival_mass = sum((transfers[i].amount.mass.value for i in self.arrival_transfer_ids), Fraction())
            if arrival_mass != arrival_water * constituent.source_concentration.value:
                raise ValueError("excluded arrival mass/water does not match fixed source composition")
            water, mass = Fraction(), Fraction()
            for identifier in self.transfer_ids:
                if identifier not in transfers:
                    raise ValueError(f"background transfer {identifier!r} is absent from constituent ledger")
                transfer = transfers[identifier]
                if transfer.destination != boundary.location.section.identifier:
                    raise ValueError("background transfers must arrive at the assessed section")
                water += transfer.amount.water.value
                mass += transfer.amount.mass.value
            if water != boundary.background.value * boundary.interval.seconds:
                raise ValueError("accounted background water does not match fixed-boundary Qb")
            if mass != constituent.background_load.value * boundary.interval.seconds:
                raise ValueError("accounted background mass does not match fixed-boundary constituent load")


@dataclass(frozen=True)
class QualityComponent:
    activation: QualityActivation
    base: Flow
    quality: MixingResult
    combined: Flow
    final_check: MixingRecheck | None
    status: ComponentStatus
    reasons: tuple[str, ...]
    source_control: SourceControlEvidence
    accounts: tuple[AccountAssessment, ...]
    background_mapping: BackgroundAccountMapping

    @property
    def requirement(self) -> Flow | None:
        """Interval requirement candidate only on an already regime-producing route."""
        return self.combined if self.activation.route is QualityRoute.REGIME else None

    @property
    def floor(self) -> Flow | None:
        """Direct floor only; regime-family floor derivation belongs to its own method."""
        return self.combined if self.activation.route is QualityRoute.FLOOR_ONLY else None


def apply_quality_component(
    base: Flow,
    boundary: FixedBoundary,
    targets: tuple[MixingTarget, ...],
    activation: QualityActivation,
    source_control: SourceControlEvidence,
    accounts: tuple[AccountAssessment, ...],
    background_mapping: BackgroundAccountMapping,
    bounds: FlowConstraints | None = None,
    candidate_arrival: Flow | None = None,
) -> QualityComponent:
    """Combine a report component only after original-test and feasibility rechecks.

    Hypothetical activation bypasses absent approvals, never physical feasibility,
    conservation, source control or matched location/time. No obligation is issued.
    """
    if not isinstance(base, Flow) or not isinstance(boundary, FixedBoundary):
        raise TypeError("quality component requires base Flow and FixedBoundary")
    if not isinstance(activation, QualityActivation) or not isinstance(source_control, SourceControlEvidence):
        raise TypeError("quality component requires activation and source-control evidence")
    if boundary.provenance.scenario != activation.scenario:
        raise ValueError("fixed-boundary provenance must match activation scenario")
    if (
        source_control.scenario != activation.scenario
        or source_control.interval != boundary.interval
        or source_control.location != boundary.location.section.identifier
    ):
        raise ValueError("source controls must match scenario, section and interval")
    source_control.require_residual_dilution()
    if not isinstance(accounts, tuple) or not accounts or any(not isinstance(a, AccountAssessment) for a in accounts):
        raise ValueError("residual dilution requires supported local/basin accounts")
    for assessment in accounts:
        assessment.require_valid()
        if any(a.interval != boundary.interval or a.scenario != activation.scenario for a in assessment.accounts):
            raise ValueError("accounts must match scenario and interval")
        for account in assessment.accounts:
            if any(
                getattr(account.provenance, field) != getattr(boundary.provenance, field)
                for field in ("scenario", "data_version", "configuration_version", "reference_member")
            ):
                raise ValueError("account provenance snapshot does not match fixed-boundary provenance")
        if boundary.location.section.identifier not in {a.location for a in assessment.accounts}:
            raise ValueError("accounts must include the assessed control section")
    chemicals = {a.constituent for assessment in accounts for a in assessment.accounts}
    if any(c.chemical not in chemicals for c in boundary.constituents):
        raise ValueError("accounts must cover every boundary chemical identity, fraction and reporting basis")
    if not isinstance(background_mapping, BackgroundAccountMapping):
        raise TypeError("explicit background-to-account transfer mapping required")
    background_mapping.require_matches(boundary, accounts)
    if bounds is None:
        bounds = FlowConstraints(boundary.location, boundary.interval, ecological_total=base)
    elif bounds.ecological_total is not None and bounds.ecological_total != base:
        raise ValueError("base and supplied ecological total disagree")
    else:
        bounds = replace(bounds, ecological_total=base)
    quality = solve_mixing(boundary, targets, bounds)
    final = (
        quality.candidate if candidate_arrival is None else recheck_mixing(boundary, targets, candidate_arrival, bounds)
    )
    combined = base
    reasons = quality.reasons
    eligible = activation.mode is ActivationMode.HYPOTHETICAL or (
        activation.mode is ActivationMode.REPORT and not activation.conditions.missing
    )
    if not eligible:
        status = ComponentStatus.ADVISORY
        reasons += ("quality is advisory; base retained",) + activation.conditions.missing
    elif quality.status is not Feasibility.FEASIBLE:
        status = ComponentStatus.INFEASIBLE
        reasons += ("only feasible quality can bind; base retained",)
    elif final is None:
        status = ComponentStatus.UNSIZED
        reasons += ("no attained candidate; supply an original-test-compliant arrival",)
    elif final.outcome is not CheckOutcome.PASS:
        status = ComponentStatus.INFEASIBLE
        reasons += ("final candidate fails or lacks original-test support; base retained",)
    else:
        combined = final.total
        status = (
            ComponentStatus.HYPOTHETICAL if activation.mode is ActivationMode.HYPOTHETICAL else ComponentStatus.ACTIVE
        )
    return QualityComponent(
        activation, base, quality, combined, final, status, reasons, source_control, accounts, background_mapping
    )
