"""PreparedTopology → MouthToSourceSections; TributaryAccounts → AttributedVolume (pure).

Prepared identities and connectivity do not infer hydrology or route releases.
Order 179 paragraphs 4–6, 8–14 and 22 supply the basin and evidence context.
"""

from dataclasses import dataclass
from enum import StrEnum

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    Provenance,
    permitted_use,
    warmup_restrictions,
)
from fishy.quantities import Volume
from fishy.spatial import Location
from fishy.time import Interval


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Identity, version and attribution must be nonempty text")


def _records(values: tuple, kind: type) -> None:
    if not isinstance(values, tuple) or any(not isinstance(value, kind) for value in values):
        raise TypeError(f"Expected immutable tuple of {kind.__name__}")


def _support(findings: EvidenceFindings, scope: EvidenceScope) -> Check:
    permitted = permitted_use(findings, scope)
    reasons = warmup_restrictions(findings.provenance, scope.period)
    if findings.provenance.reference_member != scope.member:
        reasons += ("Evidence provenance and requested reference member differ",)
    if reasons:
        return Check("support", CheckFinding.FAIL, permitted.reasons + reasons)
    return permitted


@dataclass(frozen=True)
class Basin:
    identifier: str
    version: str

    def __post_init__(self) -> None:
        _text(self.identifier)
        _text(self.version)


@dataclass(frozen=True)
class River:
    identifier: str
    version: str
    order: int

    def __post_init__(self) -> None:
        _text(self.identifier)
        _text(self.version)
        if type(self.order) is not int or self.order < 0:
            raise ValueError("Source river order must be a nonnegative integer")


class RiverType(StrEnum):
    MOUNTAIN = "mountain"
    PLAIN = "plain"
    UNRESOLVED = "unresolved"


class ContextKind(StrEnum):
    CHANNEL = "channel"
    FLOODPLAIN = "floodplain"
    DELTA = "delta"
    TERMINAL_WATER = "terminal_water"
    HYDROLOGICAL_PHASES = "hydrological_phases"
    CLIMATE = "climate"
    BIOLOGY = "biology"
    WATER_USE = "water_use"
    OPERATIONS = "operations"
    TRANSBOUNDARY = "transboundary"
    RIVER_TYPE = "river_type"


@dataclass(frozen=True)
class ContextEvidence:
    kind: ContextKind
    findings: EvidenceFindings

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ContextKind) or not isinstance(self.findings, EvidenceFindings):
            raise TypeError("Context requires a named kind and EvidenceFindings")


@dataclass(frozen=True)
class SectionContext:
    river: River
    location: Location
    downstream: Location | None
    river_type: RiverType = RiverType.UNRESOLVED
    evidence: tuple[ContextEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.river, River) or not isinstance(self.location, Location):
            raise TypeError("Section requires River and Location")
        if self.downstream is not None and not isinstance(self.downstream, Location):
            raise TypeError("Downstream section requires Location")
        if not isinstance(self.river_type, RiverType):
            raise TypeError("River type requires RiverType")
        _records(self.evidence, ContextEvidence)
        if any(item.findings.scope.reach != self.location.reach.identifier for item in self.evidence):
            raise ValueError("Context evidence belongs to a different reach")


@dataclass(frozen=True)
class RiverConnection:
    tributary: River
    receiving: River

    def __post_init__(self) -> None:
        if not isinstance(self.tributary, River) or not isinstance(self.receiving, River):
            raise TypeError("Connectivity requires river identities")
        if self.tributary == self.receiving:
            raise ValueError("A river cannot receive itself")


@dataclass(frozen=True)
class PreparedTopology:
    """A complete, rooted section tree with separately supplied river connections.

    Order labels remain source metadata. Neither order nor revision predecessors
    create a connection. Unsupported or absent topology is represented by None at
    operations, not guessed from geography or labels.
    """

    basin: Basin
    version: str
    rivers: tuple[River, ...]
    connections: tuple[RiverConnection, ...]
    sections: tuple[SectionContext, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.basin, Basin):
            raise TypeError("Topology requires Basin")
        _text(self.version)
        _records(self.rivers, River)
        _records(self.connections, RiverConnection)
        _records(self.sections, SectionContext)
        if not self.rivers or not self.sections:
            raise ValueError("Topology requires rivers and sections")
        if len({r.identifier for r in self.rivers}) != len(self.rivers):
            raise ValueError("Duplicate river identity or mixed river revisions")
        if len({s.location.section.identifier for s in self.sections}) != len(self.sections):
            raise ValueError("Duplicate section identity or mixed section revisions")
        if len({s.location.mapping_version for s in self.sections}) != 1:
            raise ValueError("Mixed location mapping versions")
        if {s.river for s in self.sections} != set(self.rivers):
            raise ValueError("Every river requires its declared sections")
        parents = {}
        for edge in self.connections:
            if edge.tributary not in self.rivers or edge.receiving not in self.rivers:
                raise ValueError("Connection references an undeclared river revision")
            if edge.tributary in parents:
                raise ValueError("Duplicate or multiple receiving parents")
            parents[edge.tributary] = edge.receiving
        roots = set(self.rivers) - set(parents)
        if len(roots) != 1 or next(iter(roots)).order != 0:
            raise ValueError("Topology requires one main-river-zero outlet")
        if any(r.order == 0 for r in parents):
            raise ValueError("Only the main river has source order zero")
        for river in self.rivers:
            visited = set()
            current = river
            while current in parents:
                if current in visited:
                    raise ValueError("Cyclic river connectivity")
                visited.add(current)
                current = parents[current]
        locations = {s.location: s for s in self.sections}
        outlets = [s for s in self.sections if s.downstream is None]
        if len(outlets) != 1 or outlets[0].river not in roots:
            raise ValueError("Section tree requires one main-river outlet")
        transitions = []
        for section in self.sections:
            if section.downstream is not None:
                if section.downstream not in locations:
                    raise ValueError("Downstream location is undeclared or a different revision")
                downstream = locations[section.downstream]
                if section.river != downstream.river:
                    transitions.append(RiverConnection(section.river, downstream.river))
            visited_locations = set()
            current_location = section.location
            while current_location is not None:
                if current_location in visited_locations:
                    raise ValueError("Cyclic section connectivity")
                visited_locations.add(current_location)
                current_location = locations[current_location].downstream
        if set(transitions) != set(self.connections) or len(transitions) != len(self.connections):
            raise ValueError("Section transitions must match each river connection exactly once")


def receiving_parent(topology: PreparedTopology, river: River) -> River | None:
    """Follow an explicit connection, never a numerical-order or nearest-gauge rule."""
    if river not in topology.rivers:
        raise ValueError("River revision is absent from topology")
    return next((edge.receiving for edge in topology.connections if edge.tributary == river), None)


def mouth_to_source(topology: PreparedTopology) -> tuple[SectionContext, ...]:
    """Topological ordering: each section follows its downstream receiving section.

    Whole receiving rivers precede their tributaries. Input order only resolves
    independent sibling ties, never physical precedence.
    """
    pending = list(topology.sections)
    result = []
    completed = set()
    while pending:
        for section in pending:
            parent = receiving_parent(topology, section.river)
            if (section.downstream is None or section.downstream in completed) and not any(
                other.river == parent for other in pending
            ):
                result.append(section)
                completed.add(section.location)
                pending.remove(section)
                break
        else:
            raise ValueError("No mouth-to-source ordering exists")
    return tuple(result)


@dataclass(frozen=True)
class DonorReference:
    """The explicit donor reference accepted for transfer to the recipient scope."""

    provenance: Provenance
    period: Interval

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance) or not isinstance(self.period, Interval):
            raise TypeError("donor reference requires provenance and historical period")


@dataclass(frozen=True)
class DonorRelation:
    recipient: River
    donor: River
    evidence: EvidenceFindings
    donor_reference: DonorReference | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.recipient, River) or not isinstance(self.donor, River):
            raise TypeError("Donor relation requires River identities")
        if not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("Donor relation requires scoped EvidenceFindings")
        if self.donor_reference is not None and not isinstance(self.donor_reference, DonorReference):
            raise TypeError("declared donor reference requires DonorReference")


def verify_donor_relation(
    topology: PreparedTopology | None,
    recipient: River,
    relation: DonorRelation | None,
    scope: EvidenceScope,
) -> Check:
    """Verify the explicitly selected receiving-parent interpretation.

    Coefficient evidence and an explicit interpretation choice are separate caller
    operands. Calling this named operation does not estimate a coefficient.
    """
    if topology is None or relation is None:
        return Check("donor_relation", CheckFinding.UNKNOWN, ("Further study: missing topology or donor relation",))
    parent = receiving_parent(topology, recipient)
    if relation.recipient != recipient or parent != relation.donor:
        return Check("donor_relation", CheckFinding.FAIL, ("Donor is not the connected receiving parent",))
    if not any(s.river == recipient and s.location.reach.identifier == scope.reach for s in topology.sections):
        return Check("donor_relation", CheckFinding.UNKNOWN, ("Donor evidence scope is not a recipient reach",))
    finding = _support(relation.evidence, scope)
    return Check("donor_relation", finding.finding, finding.reasons)


@dataclass(frozen=True)
class TributaryAccount:
    """One attributed river contribution, not every section's repeated requirement.

    water_accounts identify the prepared disjoint water-accounting parcels. They
    require accounting evidence; topology alone cannot prove physical independence.
    """

    river: River
    location: Location
    volume: Volume | None
    water_accounts: tuple[str, ...]
    evidence: EvidenceFindings | None

    def __post_init__(self) -> None:
        if not isinstance(self.river, River) or not isinstance(self.location, Location):
            raise TypeError("Contribution requires River and Location")
        if self.volume is not None and not isinstance(self.volume, Volume):
            raise TypeError("Contribution quantity requires Volume")
        _records(self.water_accounts, str)
        for account in self.water_accounts:
            _text(account)
        if len(set(self.water_accounts)) != len(self.water_accounts):
            raise ValueError("Duplicate water-accounting parcels")
        if self.evidence is not None and not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("Accounting requires EvidenceFindings")


@dataclass(frozen=True)
class TributarySum:
    topology: PreparedTopology | None
    receiving: River
    location: Location
    scope: EvidenceScope
    accounts: tuple[TributaryAccount, ...]
    evidence: EvidenceFindings | None
    volume: Volume | None
    checks: CheckSummary
    source: str = "Order 179-НҚ (2025), methodology paragraph 5"


def tributary_sum(
    topology: PreparedTopology | None,
    receiving: River,
    location: Location,
    scope: EvidenceScope,
    accounts: tuple[TributaryAccount, ...],
    evidence: EvidenceFindings | None,
) -> TributarySum:
    """Attributed paragraph-5 main-river sum, not a routed release or consumptive duty.

    Require every direct tributary once, disjoint prepared accounts, a common
    product/member/period/use and scenario, and supported accounting evidence.
    Missing support retains the supplied accounts without a guessed sum or maximum.
    """
    _records(accounts, TributaryAccount)
    if len({item.river for item in accounts}) != len(accounts):
        raise ValueError("Repeated sections of the same river cannot be added")
    parcels = [parcel for item in accounts for parcel in item.water_accounts]
    if len(parcels) != len(set(parcels)):
        raise ValueError("Overlapping water accounts would double count the same water")
    if scope.reach != location.reach.identifier:
        raise ValueError("Accounting scope differs from receiving location")
    checks = []
    if topology is None:
        checks.append(Check("topology", CheckFinding.UNKNOWN, ("Prepared topology is missing",)))
    else:
        if receiving not in topology.rivers or receiving_parent(topology, receiving) is not None:
            raise ValueError("Paragraph-5 sum is attributed to the basin main river")
        if not any(s.river == receiving and s.location == location for s in topology.sections):
            raise ValueError("Receiving location is absent from topology")
        expected = {edge.tributary for edge in topology.connections if edge.receiving == receiving}
        supplied = {item.river for item in accounts}
        if supplied - expected:
            raise ValueError("Only direct tributaries enter the attributed sum, not nested or main-river sections")
        for item in accounts:
            if not any(s.river == item.river and s.location == item.location for s in topology.sections):
                raise ValueError("Contribution location does not belong to its river revision")
        checks.append(Check("topology", CheckFinding.PASS))
        checks.append(
            Check(
                "tributary_coverage",
                CheckFinding.PASS if expected and expected == supplied else CheckFinding.UNKNOWN,
                () if expected and expected == supplied else ("Tributary coverage is missing or empty",),
            )
        )
    if evidence is None:
        checks.append(Check("accounting_evidence", CheckFinding.UNKNOWN, ("Accounting relation lacks evidence",)))
    else:
        permitted = _support(evidence, scope)
        checks.append(Check("accounting_evidence", permitted.finding, permitted.reasons))
    for item in accounts:
        reasons = []
        if item.volume is None:
            reasons.append("Tributary volume is missing")
        if not item.water_accounts:
            reasons.append("Disjoint water accounts are not established")
        checks.append(
            Check(
                f"quantity:{item.river.identifier}",
                CheckFinding.UNKNOWN if reasons else CheckFinding.PASS,
                tuple(reasons),
            )
        )
        requested = EvidenceScope(
            scope.product, item.location.reach.identifier, scope.member, scope.period, scope.intended_use
        )
        if item.evidence is None:
            check = Check("support", CheckFinding.UNKNOWN, ("Tributary evidence is missing",))
        else:
            check = _support(item.evidence, requested)
            if evidence is not None and (
                item.evidence.provenance.scenario != evidence.provenance.scenario
                or item.evidence.provenance.reference_member != evidence.provenance.reference_member
                or item.evidence.provenance.configuration_version != evidence.provenance.configuration_version
            ):
                raise ValueError("Mixed accounting scenarios, reference members or configurations")
        checks.append(Check(f"support:{item.river.identifier}", check.finding, check.reasons))
    summary = CheckSummary(tuple(checks))
    volume = (
        Volume(sum(item.volume.value for item in accounts if item.volume is not None))
        if summary.finding is CheckFinding.PASS
        else None
    )
    return TributarySum(topology, receiving, location, scope, accounts, evidence, volume, summary)
