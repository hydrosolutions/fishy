"""assess_selected_family : RequirementMember* × RequirementCandidate? × SelectionSpecification → FamilySelection.

D.10 of the proposed Uzbek method (author report, 2026-09-19).
Selection verifies an external decision; it does not run members or cap requirements.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from hashlib import sha256

from fishy.design_conditions import DesignClass
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    ReferenceKind,
    permitted_use,
)
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, check_flow_intervals, interval_use
from fishy.quantities import Flow, finite_number
from fishy.spatial import Location
from fishy.time import Interval


@dataclass(frozen=True)
class FamilyBasis:
    location: Location
    period: Interval
    scenario: str
    method: str
    parameter_version: str
    activation_version: str
    reference_kind: ReferenceKind

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.period, Interval):
            raise TypeError("family requires location and period")
        if not isinstance(self.reference_kind, ReferenceKind):
            raise TypeError("family requires reference kind")
        for value in (self.scenario, self.method, self.parameter_version, self.activation_version):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("family basis requires identified scenario, method, parameters and activation")


@dataclass(frozen=True)
class ClassRequirement:
    design: DesignClass
    samples: tuple[FlowSample, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.design, DesignClass):
            raise TypeError("requirement class requires DesignClass")
        if not isinstance(self.samples, tuple) or any(not isinstance(s, FlowSample) for s in self.samples):
            raise TypeError("requirement samples must be immutable FlowSample records")


def _daily_coverage(samples: tuple[FlowSample, ...], basis: FamilyBasis) -> None:
    check_flow_intervals(samples)
    if (
        len(
            {(s.provenance.reference_member, s.provenance.data_version, s.provenance.software_version) for s in samples}
        )
        != 1
    ):
        raise ValueError("reference/data/software identity cannot change within a series")
    if samples[0].interval.start != basis.period.start or samples[-1].interval.end != basis.period.end:
        raise ValueError("complete declared period required")
    for sample in samples:
        if sample.location != basis.location or sample.interval.seconds != 86400:
            raise ValueError("family requires matching location and fixed 86400-second days")
        if sample.interval.start.time() != basis.period.start.time():
            raise ValueError("incompatible daily boundaries")
        if sample.provenance.scenario != basis.scenario or sample.provenance.reference_kind != basis.reference_kind:
            raise ValueError("family scenario/reference basis mismatch")
        if sample.provenance.configuration_version != basis.parameter_version:
            raise ValueError("family parameter version mismatch")
        if (
            sample.presence is not Presence.PRESENT
            or sample.coverage is not Coverage.COMPLETE
            or interval_use(sample) is not IntervalUse.ELIGIBLE
        ):
            raise ValueError("selectable family needs supported complete daily values")
    if any(a.interval.end != b.interval.start for a, b in zip(samples, samples[1:], strict=False)):
        raise ValueError("family calendar has gaps, duplicates or disorder")


@dataclass(frozen=True)
class RequirementFamily:
    """One complete uncapped four-class annual requirement, not natural hydrology."""

    basis: FamilyBasis
    classes: tuple[ClassRequirement, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.basis, FamilyBasis):
            raise TypeError("family needs FamilyBasis")
        if not isinstance(self.classes, tuple) or any(not isinstance(c, ClassRequirement) for c in self.classes):
            raise TypeError("classes require immutable ClassRequirement records")
        if len(self.classes) != 4 or {c.design for c in self.classes} != set(DesignClass):
            raise ValueError("complete four-class family required")
        start, end = self.basis.period.start, self.basis.period.end
        # A complete accounting year may start on any supplied fixed calendar date.
        if end != start.replace(year=start.year + 1):
            raise ValueError("regime family requires one complete accounting year")
        for item in self.classes:
            _daily_coverage(item.samples, self.basis)
        first = self.classes[0].samples
        for item in self.classes[1:]:
            if tuple(s.interval for s in item.samples) != tuple(s.interval for s in first):
                raise ValueError("classes require identical complete calendars")
        identities = {
            (s.provenance.reference_member, s.provenance.data_version, s.provenance.software_version)
            for c in self.classes
            for s in c.samples
        }
        if len(identities) != 1:
            raise ValueError("member/reference/software identity cannot change by day or class")

    def samples(self, design: DesignClass) -> tuple[FlowSample, ...]:
        return next(c.samples for c in self.classes if c.design is design)


@dataclass(frozen=True)
class FloorSeries:
    """Complete final direct floors over a declared period, with no regime classes."""

    basis: FamilyBasis
    samples: tuple[FlowSample, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.basis, FamilyBasis) or not isinstance(self.samples, tuple):
            raise TypeError("floor series requires typed basis and immutable samples")
        _daily_coverage(self.samples, self.basis)


type RequirementCandidate = RequirementFamily | FloorSeries


def candidate_scope(candidate: RequirementCandidate) -> EvidenceScope:
    """Acceptance is bound to values, provenance, calendar and configuration."""
    digest = sha256(repr(candidate).encode()).hexdigest()
    first = _slots(candidate)[0][2]
    return EvidenceScope(
        f"uncapped-requirement:{digest}",
        candidate.basis.location.reach.identifier,
        first.provenance.reference_member,
        candidate.basis.period,
        "requirement_selection",
    )


def _slots(candidate: RequirementCandidate) -> tuple[tuple[DesignClass | None, int, FlowSample], ...]:
    if isinstance(candidate, FloorSeries):
        return tuple((None, i, s) for i, s in enumerate(candidate.samples))
    return tuple((design, i, s) for design in DesignClass for i, s in enumerate(candidate.samples(design)))


@dataclass(frozen=True)
class RequirementMember:
    identifier: str
    structure: str
    candidate: RequirementCandidate
    evidence: EvidenceFindings | None
    dependence: str

    def __post_init__(self) -> None:
        for value in (self.identifier, self.structure, self.dependence):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("member identity, structural basis and dependence are required")
        if not isinstance(self.candidate, (RequirementFamily, FloorSeries)):
            raise TypeError("member requires complete uncapped requirement or floor series")
        if any(s.provenance.reference_member != self.identifier for _, _, s in _slots(self.candidate)):
            raise ValueError("member identifier differs from sample reference member")
        if self.evidence is not None and self.evidence.provenance != _slots(self.candidate)[0][2].provenance:
            raise ValueError("member acceptance provenance differs from candidate")


@dataclass(frozen=True)
class MemberExclusion:
    identifier: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not self.identifier
            or not isinstance(self.reasons, tuple)
            or not self.reasons
            or any(not r for r in self.reasons)
        ):
            raise ValueError("excluded member needs attributable reasons")


class ReconstructionNeed(StrEnum):
    REQUIRED = "structurally_distinct_reconstructions_required"
    NOT_REQUIRED = "route_does_not_require_reconstruction"


@dataclass(frozen=True)
class SelectionSpecification:
    retained: tuple[str, ...]
    exclusions: tuple[MemberExclusion, ...]
    threshold: Fraction
    reconstruction: ReconstructionNeed
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.retained, tuple) or len(set(self.retained)) != len(self.retained):
            raise ValueError("one immutable retained member set required")
        if not isinstance(self.exclusions, tuple) or any(not isinstance(e, MemberExclusion) for e in self.exclusions):
            raise TypeError("exclusions require immutable attributable records")
        excluded = tuple(e.identifier for e in self.exclusions)
        if len(set(excluded)) != len(excluded) or set(excluded) & set(self.retained):
            raise ValueError("retained and excluded member identities must be disjoint and unique")
        threshold = finite_number(self.threshold)
        if threshold < 0:
            raise ValueError("spread threshold must be finite and nonnegative")
        object.__setattr__(self, "threshold", threshold)
        if not isinstance(self.reconstruction, ReconstructionNeed) or not self.source.strip():
            raise ValueError("explicit reconstruction applicability and selection source required")


class SelectionBranch(StrEnum):
    MEDIAN = "median"
    UPPER = "upper_envelope"


@dataclass(frozen=True)
class SelectionSlot:
    design: DesignClass | None
    interval: Interval
    median: Flow
    lower: Flow
    upper: Flow
    spread: Fraction | float
    lower_members: tuple[str, ...]
    upper_members: tuple[str, ...]
    median_members: tuple[str, ...]


@dataclass(frozen=True)
class FamilySelection:
    specification: SelectionSpecification
    members: tuple[RequirementMember, ...]
    supplied: RequirementCandidate | None
    slots: tuple[SelectionSlot, ...]
    maximum_spread: Fraction | float | None
    branch: SelectionBranch | None
    checks: CheckSummary

    @property
    def accepted(self) -> RequirementCandidate | None:
        return self.supplied if self.checks.finding is CheckFinding.PASS else None


def assess_selected_family(
    members: tuple[RequirementMember, ...],
    supplied: RequirementCandidate | None,
    specification: SelectionSpecification,
) -> FamilySelection:
    """Verify the caller's fixed-family selection, retaining a single-member screening candidate.

    This validates arithmetic and scoped member support only. Final physical and
    safeguard checks must run on the selected values before deriving/issuing a floor.
    No tolerance, delivery cap, reconstructed natural mosaic or policy default enters.
    """
    if not isinstance(members, tuple) or any(not isinstance(m, RequirementMember) for m in members):
        raise TypeError("members require immutable RequirementMember records")
    if len({m.identifier for m in members}) != len(members):
        raise ValueError("duplicate member identity")
    if {m.identifier for m in members} != set(specification.retained):
        raise ValueError("supplied members must match the fixed retained set exactly")
    checks = []
    slots = []
    if not members:
        return FamilySelection(
            specification,
            members,
            supplied,
            (),
            None,
            None,
            CheckSummary((Check("retained_members", CheckFinding.UNKNOWN, ("no selectable member",)),)),
        )
    first = members[0].candidate
    for member in members:
        if type(member.candidate) is not type(first) or member.candidate.basis != first.basis:
            raise ValueError(
                "different locations/calendars/methods/parameters/activation scenarios are separate studies"
            )
        check = (
            permitted_use(member.evidence, candidate_scope(member.candidate))
            if member.evidence
            else Check("support", CheckFinding.UNKNOWN, ("member acceptance missing",))
        )
        checks.append(Check(f"member:{member.identifier}", check.finding, check.reasons))
    if isinstance(first, RequirementFamily) or specification.reconstruction is ReconstructionNeed.REQUIRED:
        checks.append(
            Check(
                "structural_diversity",
                CheckFinding.PASS if len({m.structure for m in members}) >= 2 else CheckFinding.UNKNOWN,
                ("at least two structurally different accepted reconstructions required; one remains screening",),
            )
        )
    member_slots = [_slots(m.candidate) for m in members]
    for index, (design, _, sample) in enumerate(member_slots[0]):
        values = [
            (m.identifier, value.value)
            for m, ss in zip(members, member_slots, strict=True)
            if (value := ss[index][2].value) is not None
        ]
        ordered = sorted(v for _, v in values)
        n = len(ordered)
        lo, hi = ordered[0], ordered[-1]
        middle = (ordered[(n - 1) // 2] + ordered[n // 2]) / 2
        spread = (hi - lo) / middle if middle else 0 if hi == 0 else float("inf")
        slots.append(
            SelectionSlot(
                design,
                sample.interval,
                Flow(middle),
                Flow(lo),
                Flow(hi),
                spread,
                tuple(k for k, v in values if v == lo),
                tuple(k for k, v in values if v == hi),
                tuple(k for k, v in values if v in (ordered[(n - 1) // 2], ordered[n // 2])),
            )
        )
    maximum = max(s.spread for s in slots)
    branch = SelectionBranch.MEDIAN if maximum <= specification.threshold else SelectionBranch.UPPER
    if supplied is None:
        checks.append(Check("external_selection", CheckFinding.UNKNOWN, ("selected candidate not supplied",)))
    else:
        if type(supplied) is not type(first) or supplied.basis != first.basis:
            raise ValueError("selected candidate must retain the identical calculation basis")
        matched = all(
            sample.value == (slot.median if branch is SelectionBranch.MEDIAN else slot.upper)
            for (_, _, sample), slot in zip(_slots(supplied), slots, strict=True)
        )
        checks.append(
            Check(
                "external_selection",
                CheckFinding.PASS if matched else CheckFinding.FAIL,
                ("verify uncapped selected median/envelope over every day and class",),
            )
        )
    return FamilySelection(specification, members, supplied, tuple(slots), maximum, branch, CheckSummary(tuple(checks)))
