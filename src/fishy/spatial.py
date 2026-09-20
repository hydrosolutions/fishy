"""PreparedMapping × Reach → Location; PreparedClassification → TrackDecision (pure).

Consumes prepared spatial records, not geometry or legal designations. Plan assignment
never changes physical identity. Boundary changes create new reaches and preserve history.
"""

from dataclasses import dataclass
from enum import Enum


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Identifiers, versions and evidence must be nonempty text")


@dataclass(frozen=True)
class _Identity:
    identifier: str
    version: str

    def __post_init__(self) -> None:
        _text(self.identifier)
        _text(self.version)


@dataclass(frozen=True)
class WaterBody(_Identity):
    """Physical water body and its boundary version, independent of plan adoption."""


@dataclass(frozen=True)
class PlanUnit(_Identity):
    """Prepared basin-plan unit and boundary version."""


@dataclass(frozen=True)
class Reach(_Identity):
    water_body: WaterBody
    predecessors: tuple["Reach", ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.water_body, WaterBody):
            raise TypeError("Reach requires a physical WaterBody")
        if not isinstance(self.predecessors, tuple) or any(not isinstance(r, Reach) for r in self.predecessors):
            raise TypeError("Predecessors must be an immutable tuple of reaches")
        if len(set(self.predecessors)) != len(self.predecessors):
            raise ValueError("Duplicate predecessors")
        if any(self.identifier == r.identifier for r in self.predecessors):
            raise ValueError("A boundary change must create a new reach identifier")


@dataclass(frozen=True)
class CalculationSection(_Identity):
    """Versioned physical calculation section, not a measuring or compliance point."""


@dataclass(frozen=True)
class Location:
    reach: Reach
    section: CalculationSection
    mapping_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.reach, Reach) or not isinstance(self.section, CalculationSection):
            raise TypeError("Location requires a Reach and CalculationSection")
        _text(self.mapping_version)


class PlanStatus(Enum):
    PENDING = "pending"
    PROVISIONAL = "provisional"
    ADOPTED = "adopted"


@dataclass(frozen=True)
class PlanAssignment:
    reach: Reach
    version: str
    status: PlanStatus
    plan_unit: PlanUnit | None
    evidence: str

    def __post_init__(self) -> None:
        _text(self.version)
        _text(self.evidence)
        if not isinstance(self.reach, Reach) or not isinstance(self.status, PlanStatus):
            raise TypeError("Typed reach and plan status required")
        if self.status is PlanStatus.PENDING:
            if self.plan_unit is not None:
                raise ValueError("Pending assignment cannot assert a plan unit")
        elif not isinstance(self.plan_unit, PlanUnit):
            raise ValueError("An assigned plan unit is required")


@dataclass(frozen=True)
class ObservationPoint(_Identity):
    section: CalculationSection

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.section, CalculationSection):
            raise TypeError("Observation point requires a calculation-section relation")


@dataclass(frozen=True)
class CompliancePoint(_Identity):
    section: CalculationSection
    designation: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.section, CalculationSection):
            raise TypeError("Compliance point requires a calculation-section relation")
        _text(self.designation)


@dataclass(frozen=True)
class ModelLocation:
    location: Location
    model_identifier: str
    model_version: str
    output_identifier: str
    process_owner: str

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location):
            raise TypeError("Model output requires a physical Location")
        for value in (self.model_identifier, self.model_version, self.output_identifier, self.process_owner):
            _text(value)


@dataclass(frozen=True)
class PreparedMapping:
    """Declared complete reach set and many-to-many calculation-section relations.

    Shared sections and multiple sections per reach require explicit declarations.
    No geographic overlap or coverage claim is inferred from these relations.
    """

    version: str
    reaches: tuple[Reach, ...]
    locations: tuple[Location, ...]
    shared_sections: tuple[CalculationSection, ...] = ()
    multiple_section_reaches: tuple[Reach, ...] = ()
    model_locations: tuple[ModelLocation, ...] = ()

    def __post_init__(self) -> None:
        _text(self.version)
        for values, cls in (
            (self.reaches, Reach),
            (self.locations, Location),
            (self.shared_sections, CalculationSection),
            (self.multiple_section_reaches, Reach),
            (self.model_locations, ModelLocation),
        ):
            if not isinstance(values, tuple) or any(not isinstance(v, cls) for v in values):
                raise TypeError("Mapping collections require immutable domain records")
            if len(values) != len(set(values)):
                raise ValueError("Duplicate mapping records")
        if not self.reaches or not self.locations:
            raise ValueError("Mapping requires reaches and locations")
        if any(loc.mapping_version != self.version for loc in self.locations):
            raise ValueError("Incompatible mapping versions")
        if {loc.reach for loc in self.locations} != set(self.reaches):
            raise ValueError("Missing or undeclared reach records")
        sections = {loc.section for loc in self.locations}
        shared = {s for s in sections if sum(loc.section == s for loc in self.locations) > 1}
        multiple = {r for r in self.reaches if sum(loc.reach == r for loc in self.locations) > 1}
        if shared != set(self.shared_sections) or multiple != set(self.multiple_section_reaches):
            raise ValueError("Shared and multiple sections must be declared exactly")
        if any(item.location not in self.locations for item in self.model_locations):
            raise ValueError("Model output references an undeclared physical location")


class Origin(Enum):
    NATURAL = "natural"
    ARTIFICIAL = "artificial"
    UNKNOWN = "unknown"
    NOT_ASSESSED = "not_assessed"


class DesignationState(Enum):
    NONE = "none"
    NOT_SEARCHED = "not_searched"
    PENDING = "pending"
    DESIGNATED = "designated"
    EXPIRED = "expired"
    REJECTED = "rejected"


class Eligibility(Enum):
    ACCEPTED = "accepted"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


class UseCategory(Enum):
    PROTECTED = "А"
    DRINKING_DOMESTIC = "Б"
    CULTURAL_DOMESTIC = "В"
    FISHERIES = "Г"
    AGRICULTURE_IRRIGATION = "Д"
    UNDETERMINED = "undetermined"


class ClassificationBasis(Enum):
    PREPARED_EVIDENCE = "prepared_evidence"
    HYPOTHETICAL = "hypothetical"


class Track(Enum):
    NATURAL = "natural"
    POTENTIAL = "potential"
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class PreparedClassification:
    origin: Origin
    designation: DesignationState
    designation_eligibility: Eligibility
    category: UseCategory
    uses: tuple[str, ...]
    evidence: str
    version: str
    basis: ClassificationBasis = ClassificationBasis.PREPARED_EVIDENCE

    def __post_init__(self) -> None:
        for value, cls in (
            (self.origin, Origin),
            (self.designation, DesignationState),
            (self.designation_eligibility, Eligibility),
            (self.category, UseCategory),
            (self.basis, ClassificationBasis),
        ):
            if not isinstance(value, cls):
                raise TypeError("Classification states require domain enums")
        if not isinstance(self.uses, tuple):
            raise TypeError("Uses require an immutable tuple")
        for value in (*self.uses, self.evidence, self.version):
            _text(value)
        if (
            self.designation is not DesignationState.DESIGNATED
            and self.designation_eligibility is not Eligibility.NOT_APPLICABLE
        ):
            raise ValueError("Designation eligibility belongs only to a designated body")


@dataclass(frozen=True)
class TrackDecision:
    track: Track
    reason: str
    classification: PreparedClassification


def assessment_track(classification: PreparedClassification) -> TrackDecision:
    """Explain the prepared track; do not select a method tier or confer authority."""
    if not isinstance(classification, PreparedClassification):
        raise TypeError("Prepared classification required")
    if classification.origin in (Origin.UNKNOWN, Origin.NOT_ASSESSED):
        track, reason = Track.UNDETERMINED, "Origin is unresolved"
    elif classification.designation in (DesignationState.NOT_SEARCHED, DesignationState.PENDING):
        track, reason = Track.UNDETERMINED, "Designation search or decision is unresolved"
    elif classification.origin is Origin.ARTIFICIAL:
        track, reason = Track.POTENTIAL, "Artificial construction, independent of use category"
    elif classification.designation is DesignationState.DESIGNATED:
        if classification.designation_eligibility is Eligibility.ACCEPTED:
            track, reason = Track.POTENTIAL, "Prepared designation eligibility and anti-downgrade safeguards accepted"
        else:
            track, reason = Track.UNDETERMINED, "Designation eligibility or safeguards are not accepted"
    else:
        track, reason = Track.NATURAL, "Natural origin without a current valid heavily-modified designation"
    return TrackDecision(track, reason, classification)
