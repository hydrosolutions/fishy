"""assess_quality : QualityProfile × QualityObservations × ReferenceObservations → QualityAssessment.

Exact interval tests assess supplied evidence, not process predictions or official compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    ProductionMethod,
    Provenance,
    _text,
    _texts,
    aggregate_checks,
    warmup_restrictions,
)
from fishy.flows import Presence
from fishy.physical import ConstituentSample
from fishy.quantities import Number, finite_number
from fishy.spatial import Location
from fishy.time import Interval


class ChemicalBehavior(StrEnum):
    CONSERVATIVE = "conservative"
    PROCESS = "process"
    TOTAL_DISSOLVED_SOLIDS = "total_dissolved_solids"


@dataclass(frozen=True)
class ChemicalIdentity:
    identifier: str
    chemical_form: str
    reporting_basis: str
    fraction: str
    behavior: ChemicalBehavior
    components: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("identifier", "chemical_form", "reporting_basis", "fraction"):
            _text(getattr(self, name), name)
        if not isinstance(self.behavior, ChemicalBehavior):
            raise TypeError("chemical behavior must be explicit")
        _texts(self.components, "components")
        if len(set(self.components)) != len(self.components):
            raise ValueError("duplicate chemical components")


@dataclass(frozen=True, init=False)
class QualityValue:
    """Concentration, signed process state, or dimensionless ratio in canonical units."""

    value: Fraction
    unit: str

    def __init__(self, value: Number, unit: str) -> None:
        units = {
            "kg/m3": ("kg/m3", 1),
            "mg/l": ("kg/m3", 1000),
            "mg/L": ("kg/m3", 1000),
            "ug/l": ("kg/m3", 1000000),
            "degC": ("degC", 1),
            "pH": ("pH", 1),
            "1": ("1", 1),
        }
        if unit not in units:
            raise ValueError(f"unsupported quality unit {unit!r}")
        canonical, divisor = units[unit]
        amount = finite_number(value) / divisor
        if canonical == "kg/m3" and amount < 0:
            raise ValueError("concentration cannot be negative")
        object.__setattr__(self, "value", amount)
        object.__setattr__(self, "unit", canonical)


class Comparison(StrEnum):
    LE = "le"
    LT = "lt"
    GE = "ge"
    GT = "gt"
    UNRESOLVED_UPPER = "unresolved_upper"


@dataclass(frozen=True)
class QualityTarget:
    identifier: str
    chemical: ChemicalIdentity
    operator: Comparison
    limit: QualityValue
    basis: str
    source: str

    def __post_init__(self) -> None:
        for name in ("identifier", "basis", "source"):
            _text(getattr(self, name), name)
        if not isinstance(self.chemical, ChemicalIdentity) or not isinstance(self.limit, QualityValue):
            raise TypeError("target requires chemical identity and typed limit")
        if not isinstance(self.operator, Comparison):
            raise TypeError("target requires explicit Comparison")


@dataclass(frozen=True)
class RelativeTarget(QualityTarget):
    reference_id: str
    reference_basis: str
    reference_interval: Interval

    def __post_init__(self) -> None:
        super().__post_init__()
        _text(self.reference_id, "reference_id")
        _text(self.reference_basis, "reference_basis")
        if not isinstance(self.reference_interval, Interval):
            raise TypeError("relative target requires an explicit reference interval")


@dataclass(frozen=True)
class GroupMember:
    chemical: ChemicalIdentity
    denominator: QualityValue

    def __post_init__(self) -> None:
        if not isinstance(self.chemical, ChemicalIdentity) or not isinstance(self.denominator, QualityValue):
            raise TypeError("group member requires typed chemical and denominator")
        if self.denominator.unit != "kg/m3" or self.denominator.value <= 0:
            raise ValueError("group denominator must be a positive concentration")


@dataclass(frozen=True)
class GroupTarget:
    identifier: str
    members: tuple[GroupMember, ...]
    operator: Comparison
    basis: str
    source: str
    authority: str
    limit: Fraction = Fraction(1)

    def __post_init__(self) -> None:
        for name in ("identifier", "basis", "source", "authority"):
            _text(getattr(self, name), name)
        if not isinstance(self.operator, Comparison):
            raise TypeError("group requires explicit Comparison")
        if not isinstance(self.limit, Fraction):
            raise TypeError("group limit requires exact Fraction")
        if self.limit < 0:
            raise ValueError("group limit cannot be negative")
        if (
            not isinstance(self.members, tuple)
            or not self.members
            or any(not isinstance(member, GroupMember) for member in self.members)
        ):
            raise ValueError("group requires a nonempty immutable membership")
        identifiers = {member.chemical.identifier for member in self.members}
        if len(identifiers) != len(self.members):
            raise ValueError("duplicate group members")
        for member in self.members:
            chemical = member.chemical
            if chemical.behavior is ChemicalBehavior.TOTAL_DISSOLVED_SOLIDS and len(self.members) > 1:
                raise ValueError("TDS stays outside ionic groups")
            if identifiers.intersection(chemical.components):
                raise ValueError("group double counts a chemical and its components")


@dataclass(frozen=True)
class UnresolvedTarget:
    identifier: str
    reason: str
    source: str

    def __post_init__(self) -> None:
        for name in ("identifier", "reason", "source"):
            _text(getattr(self, name), name)


type Target = QualityTarget | GroupTarget | UnresolvedTarget


def quality_range(
    identifier: str,
    chemical: ChemicalIdentity,
    lower: QualityValue,
    upper: QualityValue,
    basis: str,
    source: str,
    *,
    lower_operator: Comparison = Comparison.GE,
    upper_operator: Comparison = Comparison.LE,
) -> tuple[QualityTarget, QualityTarget]:
    if lower.unit != upper.unit or lower.value > upper.value:
        raise ValueError("range requires compatible ordered bounds")
    if lower_operator not in (Comparison.GE, Comparison.GT) or upper_operator not in (Comparison.LE, Comparison.LT):
        raise ValueError("range requires lower and upper comparisons")
    return (
        QualityTarget(identifier + ":lower", chemical, lower_operator, lower, basis, source),
        QualityTarget(identifier + ":upper", chemical, upper_operator, upper, basis, source),
    )


class ProfileStatus(StrEnum):
    SCENARIO = "scenario"
    ADOPTED = "adopted"


@dataclass(frozen=True)
class QualityProfile:
    identifier: str
    version: str
    jurisdiction: str
    instrument: str
    instrument_version: str
    category: str
    purpose: str
    location: Location
    interval: Interval
    scenario: str
    status: ProfileStatus
    required: tuple[str, ...]
    targets: tuple[Target, ...]
    applicability: str
    uncertainty_policy: str
    interpretation: str
    exclusions: tuple[str, ...] = ()
    parent_profile: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "identifier",
            "version",
            "jurisdiction",
            "instrument",
            "instrument_version",
            "category",
            "purpose",
            "scenario",
            "applicability",
            "uncertainty_policy",
            "interpretation",
        ):
            _text(getattr(self, name), name)
        if not isinstance(self.location, Location) or not isinstance(self.interval, Interval):
            raise TypeError("profile requires exact location and interval")
        if not isinstance(self.status, ProfileStatus):
            raise TypeError("profile requires explicit status")
        _texts(self.required, "required")
        _texts(self.exclusions, "exclusions")
        if not self.required or len(set(self.required)) != len(self.required):
            raise ValueError("profile requires nonempty unique required checks")
        if not isinstance(self.targets, tuple) or any(
            not isinstance(t, (QualityTarget, GroupTarget, UnresolvedTarget)) for t in self.targets
        ):
            raise TypeError("targets require immutable domain records")
        ids = [target.identifier for target in self.targets]
        if len(ids) != len(set(ids)) or set(ids) - set(self.required):
            raise ValueError("duplicate or undeclared target")
        if self.parent_profile is not None:
            _text(self.parent_profile, "parent_profile")

    def override(
        self, *, identifier: str, version: str, scenario: str, targets: tuple[Target, ...], interpretation: str
    ) -> QualityProfile:
        if (identifier, version) == (self.identifier, self.version):
            raise ValueError("override requires a new profile identity/version")
        return replace(
            self,
            identifier=identifier,
            version=version,
            scenario=scenario,
            targets=targets,
            status=ProfileStatus.SCENARIO,
            interpretation=interpretation,
            parent_profile=f"{self.identifier}@{self.version}",
        )


class ObservationKind(StrEnum):
    MEASUREMENT = "measurement"
    AGGREGATE = "aggregate"
    MODEL = "model"
    SYNTHETIC = "synthetic"


@dataclass(frozen=True)
class ObservationAdmission:
    publisher: str | None = None
    original_url: str | None = None
    retrieved: date | None = None
    observed: date | None = None
    station: str | None = None
    depth: str | None = None
    determinand: str | None = None
    chemical_form: str | None = None
    unit: str | None = None
    sampling_basis: str | None = None
    analytical_method: str | None = None
    reporting_limit: QualityValue | None = None
    quality_flags: tuple[str, ...] | None = None
    licence: str | None = None
    transformations: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        for name in (
            "publisher",
            "original_url",
            "station",
            "depth",
            "determinand",
            "chemical_form",
            "unit",
            "sampling_basis",
            "analytical_method",
            "licence",
        ):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
        for name in ("retrieved", "observed"):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), date):
                raise TypeError("admission dates must be dates")
        for name in ("quality_flags", "transformations"):
            if getattr(self, name) is not None:
                _texts(getattr(self, name), name)
        if self.reporting_limit is not None and not isinstance(self.reporting_limit, QualityValue):
            raise TypeError("reporting limit must be QualityValue")

    @property
    def limitations(self) -> tuple[str, ...]:
        return tuple(
            f"admission field missing: {name}" for name in self.__dataclass_fields__ if getattr(self, name) is None
        )


class Censoring(StrEnum):
    NONE = "none"
    INTERVAL = "interval"
    NON_DETECT = "non_detect"


@dataclass(frozen=True)
class QualityBounds:
    lower: QualityValue
    upper: QualityValue
    meaning: str
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.lower, QualityValue) or not isinstance(self.upper, QualityValue):
            raise TypeError("quality bounds require QualityValue")
        if self.lower.unit != self.upper.unit or self.lower.value > self.upper.value:
            raise ValueError("quality bounds must be ordered and unit-compatible")
        _text(self.meaning, "meaning")
        _text(self.source, "source")


@dataclass(frozen=True)
class QualityObservation:
    identifier: str
    chemical: ChemicalIdentity
    bounds: QualityBounds | None
    location: Location
    interval: Interval
    basis: str
    presence: Presence
    provenance: Provenance
    kind: ObservationKind
    support: str
    domain: str
    censoring: Censoring = Censoring.NONE
    admission: ObservationAdmission | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("identifier", "basis", "support", "domain"):
            _text(getattr(self, name), name)
        for name, kind in (
            ("chemical", ChemicalIdentity),
            ("location", Location),
            ("interval", Interval),
            ("presence", Presence),
            ("provenance", Provenance),
            ("kind", ObservationKind),
            ("censoring", Censoring),
        ):
            if not isinstance(getattr(self, name), kind):
                raise TypeError(f"{name} requires {kind.__name__}")
        _texts(self.reasons, "reasons")
        if self.bounds is not None and not isinstance(self.bounds, QualityBounds):
            raise TypeError("bounds require QualityBounds")
        if self.presence is Presence.PRESENT and self.bounds is None:
            raise ValueError("present quality requires supported bounds")
        if self.presence is not Presence.PRESENT and not self.reasons:
            raise ValueError("unavailable quality requires reasons")
        if self.admission is not None and not isinstance(self.admission, ObservationAdmission):
            raise TypeError("admission requires ObservationAdmission")
        if self.kind in (ObservationKind.MEASUREMENT, ObservationKind.AGGREGATE) and self.admission is None:
            raise ValueError("public observations require an admission record, including missing fields")
        supported_methods = {
            ObservationKind.MEASUREMENT: (ProductionMethod.OBSERVED, ProductionMethod.IMPORTED),
            ObservationKind.AGGREGATE: (ProductionMethod.OBSERVED, ProductionMethod.IMPORTED),
            ObservationKind.MODEL: (
                ProductionMethod.SIMULATED,
                ProductionMethod.RECONSTRUCTED,
                ProductionMethod.IMPORTED,
                ProductionMethod.ILLUSTRATIVE,
            ),
            ObservationKind.SYNTHETIC: (ProductionMethod.ILLUSTRATIVE, ProductionMethod.IMPORTED),
        }
        if self.provenance.production_method not in supported_methods[self.kind]:
            raise ValueError("observation kind conflicts with provenance production method")
        if (
            self.censoring is Censoring.NON_DETECT
            and self.bounds is not None
            and (self.bounds.lower.unit != "kg/m3" or self.bounds.lower.value != 0)
        ):
            raise ValueError("non-detect requires nonnegative reporting-limit bounds")

    @property
    def limitations(self) -> tuple[str, ...]:
        return self.reasons + (() if self.admission is None else self.admission.limitations)


def from_constituent_sample(sample: ConstituentSample, *, chemical: ChemicalIdentity, basis: str) -> QualityObservation:
    """Retain physical identity, support and exact summed mass/water concentration."""
    if not isinstance(sample, ConstituentSample):
        raise TypeError("sample must be ConstituentSample")
    if (sample.constituent, sample.chemical_form, sample.reporting_basis) != (
        chemical.identifier,
        chemical.chemical_form,
        chemical.reporting_basis,
    ):
        raise ValueError("physical chemical identity/reporting basis mismatch")
    presence = sample.presence
    reasons = sample.reasons
    if chemical.behavior is ChemicalBehavior.PROCESS:
        presence = Presence.UNSUPPORTED
        reasons += ("conservative transport does not establish process state",)
    bounds = None
    if presence is Presence.PRESENT:
        assert sample.concentration_kg_m3 is not None
        value = QualityValue(sample.concentration_kg_m3, "kg/m3")
        bounds = QualityBounds(
            value, value, "exact physical accounting; not measurement uncertainty", sample.provenance.source
        )
    return QualityObservation(
        chemical.identifier,
        chemical,
        bounds,
        sample.location,
        sample.interval,
        basis,
        presence,
        sample.provenance,
        ObservationKind.MODEL,
        "supplied physical transport projection",
        "aggregate transfer concentration",
        reasons=reasons,
    )


def compare_bounds(lower: Fraction, upper: Fraction, limit: Fraction, operator: Comparison) -> CheckFinding:
    """Whole-interval comparisons preserve strict endpoints and unresolved source equality."""
    if lower > upper:
        raise ValueError("unordered bounds")
    if operator is Comparison.LE:
        return CheckFinding.PASS if upper <= limit else CheckFinding.FAIL if lower > limit else CheckFinding.UNKNOWN
    if operator is Comparison.LT:
        return CheckFinding.PASS if upper < limit else CheckFinding.FAIL if lower >= limit else CheckFinding.UNKNOWN
    if operator is Comparison.GE:
        return CheckFinding.PASS if lower >= limit else CheckFinding.FAIL if upper < limit else CheckFinding.UNKNOWN
    if operator is Comparison.GT:
        return CheckFinding.PASS if lower > limit else CheckFinding.FAIL if upper <= limit else CheckFinding.UNKNOWN
    if operator is Comparison.UNRESOLVED_UPPER:
        return CheckFinding.PASS if upper < limit else CheckFinding.FAIL if lower > limit else CheckFinding.UNKNOWN
    raise TypeError("explicit Comparison required")


@dataclass(frozen=True)
class QualityTestResult:
    check: Check
    lower: Fraction | None
    upper: Fraction | None
    unit: str | None
    target: Target
    observations: tuple[QualityObservation, ...]


@dataclass(frozen=True)
class QualityAssessment:
    profile: QualityProfile
    results: tuple[QualityTestResult, ...]
    summary: CheckSummary
    limitations: tuple[str, ...]


def _match(
    observation: QualityObservation | None,
    chemical: ChemicalIdentity,
    basis: str,
    profile: QualityProfile,
    *,
    reference: str | None = None,
) -> tuple[str, ...]:
    if observation is None:
        return ("required chemical/reference observation missing",)
    reasons = list(warmup_restrictions(observation.provenance, observation.interval))
    if observation.chemical != chemical:
        reasons.append("chemical form, fraction or reporting basis mismatch; no supported conversion")
    if observation.location != profile.location or observation.provenance.scenario != profile.scenario:
        reasons.append("observation location or scenario mismatch")
    if reference is None and observation.interval != profile.interval:
        reasons.append("observation interval mismatch; no temporal disaggregation")
    if observation.basis != basis:
        reasons.append("sampling/averaging basis mismatch")
    if observation.presence is not Presence.PRESENT:
        reasons.extend(observation.reasons)
    return tuple(reasons)


def assess_quality(
    profile: QualityProfile,
    observations: tuple[QualityObservation, ...],
    *,
    references: tuple[QualityObservation, ...] = (),
) -> QualityAssessment:
    """Assess one selected profile; missing membership cannot erase supported failures."""
    if not isinstance(profile, QualityProfile):
        raise TypeError("assessment requires QualityProfile")
    for samples in (observations, references):
        if not isinstance(samples, tuple) or any(not isinstance(o, QualityObservation) for o in samples):
            raise TypeError("observations require immutable QualityObservation tuples")
        if len({o.identifier for o in samples}) != len(samples):
            raise ValueError("duplicate observation IDs")
    by_chemical = {o.chemical.identifier: o for o in observations}
    if len(by_chemical) != len(observations):
        raise ValueError("duplicate chemical observations")
    by_reference = {o.identifier: o for o in references}
    results = []
    for target in profile.targets:
        used: tuple[QualityObservation, ...] = ()
        reasons: tuple[str, ...] = ()
        lower = upper = None
        unit = None
        if isinstance(target, UnresolvedTarget):
            reasons = (target.reason,)
        elif isinstance(target, GroupTarget):
            lo = hi = Fraction(0)
            for member in target.members:
                observation = by_chemical.get(member.chemical.identifier)
                mismatch = _match(observation, member.chemical, target.basis, profile)
                reasons += mismatch
                if observation is not None:
                    used += (observation,)
                if not mismatch:
                    assert observation is not None and observation.bounds is not None
                    bounds = observation.bounds
                    if bounds.lower.unit != member.denominator.unit:
                        reasons += ("group member unit mismatch",)
                    else:
                        lo += bounds.lower.value / member.denominator.value
                        hi += bounds.upper.value / member.denominator.value
            if not reasons:
                lower, upper, unit = lo, hi, "1"
        else:
            observation = by_chemical.get(target.chemical.identifier)
            reasons = _match(observation, target.chemical, target.basis, profile)
            if observation is not None:
                used = (observation,)
            if not reasons:
                assert observation is not None and observation.bounds is not None
                bounds = observation.bounds
                if bounds.lower.unit != target.limit.unit:
                    reasons = ("quality unit mismatch",)
                else:
                    lower, upper, unit = bounds.lower.value, bounds.upper.value, bounds.lower.unit
            if isinstance(target, RelativeTarget):
                reference = by_reference.get(target.reference_id)
                reasons += _match(
                    reference, target.chemical, target.reference_basis, profile, reference=target.reference_id
                )
                if reference is not None:
                    used += (reference,)
                    if reference.interval != target.reference_interval:
                        reasons += ("reference interval mismatch",)
                if not reasons:
                    assert reference is not None and reference.bounds is not None
                    if reference.bounds.lower.unit != unit:
                        reasons += ("relative reference unit mismatch",)
                    else:
                        assert lower is not None and upper is not None
                        lower -= reference.bounds.upper.value
                        upper -= reference.bounds.lower.value
        if reasons or lower is None or upper is None or isinstance(target, UnresolvedTarget):
            finding = CheckFinding.UNKNOWN
        else:
            limit = target.limit if isinstance(target, GroupTarget) else target.limit.value
            finding = compare_bounds(lower, upper, limit, target.operator)
            if finding is CheckFinding.UNKNOWN:
                reasons = ("interval overlaps threshold or source equality remains unresolved",)
        results.append(QualityTestResult(Check(target.identifier, finding, reasons), lower, upper, unit, target, used))
    summary = aggregate_checks(profile.required, tuple(result.check for result in results))
    limitations = tuple(
        dict.fromkeys(reason for observation in observations + references for reason in observation.limitations)
    )
    return QualityAssessment(profile, tuple(results), summary, limitations)


@dataclass(frozen=True)
class QualityConversion:
    """A caller-supplied positive linear conversion; never an inferred chemistry repair."""

    source_chemical: ChemicalIdentity
    target_chemical: ChemicalIdentity
    factor: Fraction
    source: str
    domain: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_chemical, ChemicalIdentity) or not isinstance(
            self.target_chemical, ChemicalIdentity
        ):
            raise TypeError("conversion requires explicit source and target chemical identities")
        if not isinstance(self.factor, Fraction) or self.factor <= 0:
            raise ValueError("conversion requires a positive exact factor")
        _text(self.source, "source")
        _text(self.domain, "domain")


def convert_quality(observation: QualityObservation, conversion: QualityConversion) -> QualityObservation:
    """Apply only the supplied supported concentration conversion, retaining original provenance."""
    if observation.chemical != conversion.source_chemical:
        raise ValueError("conversion source chemical identity mismatch")
    if observation.domain != conversion.domain:
        raise ValueError("conversion domain mismatch")
    bounds = observation.bounds
    converted = None
    if bounds is not None:
        if bounds.lower.unit != "kg/m3":
            raise ValueError("chemical conversion only supports supplied concentration bases")
        converted = QualityBounds(
            QualityValue(bounds.lower.value * conversion.factor, "kg/m3"),
            QualityValue(bounds.upper.value * conversion.factor, "kg/m3"),
            bounds.meaning,
            bounds.source,
        )
    description = (
        f"supplied conversion {conversion.source_chemical!r} -> {conversion.target_chemical!r}; "
        f"factor={conversion.factor}; source={conversion.source}; domain={conversion.domain}"
    )
    admission = observation.admission
    if admission is not None:
        prior = () if admission.transformations is None else admission.transformations
        admission = replace(admission, transformations=(*prior, description))
    return replace(
        observation,
        chemical=conversion.target_chemical,
        bounds=converted,
        admission=admission,
        provenance=replace(observation.provenance, dependencies=(*observation.provenance.dependencies, description)),
        reasons=(*observation.reasons, description),
    )
