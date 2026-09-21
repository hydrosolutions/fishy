"""baseline_family : AcceptedNaturalPatterns × RecordedMinimum → EcologicalMemberCandidate.

Appendix A step 7 of the proposed Uzbek method. Candidates are pre-quality,
uncapped ecological requirements, not issued duties or scientific certification.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from fractions import Fraction
from hashlib import sha256

from fishy.annual_statistics import AnnualReference
from fishy.daily_patterns import AnalogueReference, DailyPattern, DailyReferenceYear
from fishy.design_conditions import DesignClass
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    Provenance,
    ReferenceKind,
    permitted_use,
)
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, interval_use
from fishy.pattern_calendar import AccountingYear
from fishy.quantities import Flow, finite_number
from fishy.scientific_acceptance import (
    HydrologicalProduct,
    HydrologicalProductKind,
    ScientificAssessment,
    TemporalResolution,
    UsePurpose,
)
from fishy.spatial import Location
from fishy.time import Interval


class EcologicalRegimeMethod(StrEnum):
    BASELINE = "uzbek_baseline"
    TRANSFER = "qualified_ecological_transfer"
    STUDY = "natural_study"


@dataclass(frozen=True)
class ClassEcologicalRegime:
    design: DesignClass
    samples: tuple[FlowSample, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.design, DesignClass):
            raise TypeError("design requires DesignClass")
        if not isinstance(self.samples, tuple) or any(not isinstance(s, FlowSample) for s in self.samples):
            raise TypeError("immutable flow samples required")


def _identity(left: Provenance, right: Provenance) -> None:
    if any(getattr(left, key) != getattr(right, key) for key in ("scenario", "reference_member", "reference_kind")):
        raise ValueError("incompatible member/scenario/reference identity")


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty evidence attribution required")


@dataclass(frozen=True)
class EcologicalMemberCandidate:
    """Complete pre-quality family; never includes spawning or delivery capping."""

    location: Location
    calendar: AccountingYear
    provenance: Provenance
    method: EcologicalRegimeMethod
    profile_version: str
    classes: tuple[ClassEcologicalRegime, ...]
    evidence: tuple[Provenance | ScientificAssessment, ...]

    def __post_init__(self) -> None:
        _text(self.profile_version)
        if not isinstance(self.method, EcologicalRegimeMethod):
            raise TypeError("ecological method required")
        if (
            not isinstance(self.classes, tuple)
            or len(self.classes) != 4
            or {c.design for c in self.classes} != set(DesignClass)
        ):
            raise ValueError("one complete family of four classes required")
        if not isinstance(self.evidence, tuple) or any(
            not isinstance(item, (Provenance, ScientificAssessment)) for item in self.evidence
        ):
            raise TypeError("immutable evidence required")
        if self.provenance.reference_member is None:
            raise ValueError("member identity required")
        for regime in self.classes:
            if len(regime.samples) != self.calendar.days:
                raise ValueError("complete receiving calendar required")
            for i, sample in enumerate(regime.samples):
                start = self.calendar.interval.start + timedelta(days=i)
                if sample.location != self.location or sample.interval != Interval(start, start + timedelta(days=1)):
                    raise ValueError("candidate location/calendar mismatch")
                _identity(sample.provenance, self.provenance)
                if (
                    sample.value is None
                    or sample.presence is not Presence.PRESENT
                    or sample.coverage is not Coverage.COMPLETE
                    or interval_use(sample) is not IntervalUse.ELIGIBLE
                ):
                    raise ValueError("complete supported daily candidate required")


@dataclass(frozen=True)
class RecordedMinimum:
    """Exact scalar derived from the complete accepted naturalised record."""

    reference: AnnualReference
    years: tuple[DailyReferenceYear, ...]
    missing_data_treatment: str
    uncertainty: str
    assessment: ScientificAssessment | None = None

    def __post_init__(self) -> None:
        _text(self.missing_data_treatment)
        _text(self.uncertainty)
        object.__setattr__(self, "years", tuple(sorted(self.years, key=lambda y: y.calendar.interval.start)))
        AnalogueReference(self.reference, self.years)
        if {y.calendar.interval for y in self.years} != set(self.reference.accepted_years):
            raise ValueError("minimum needs all accepted daily reference years")
        if any(y.quality_checks.finding is not CheckFinding.PASS for y in self.years):
            raise ValueError("minimum source quality is unsupported")

    @property
    def value(self) -> Flow:
        return min((s.value for y in self.years for s in y.samples if s.value is not None), key=lambda v: v.value)

    @property
    def days(self) -> tuple[Interval, ...]:
        minimum = self.value
        return tuple(s.interval for y in self.years for s in y.samples if s.value == minimum)


def recorded_minimum_product(record: RecordedMinimum, *, intended_use: str, purpose: UsePurpose) -> HydrologicalProduct:
    identity = (
        "recorded-minimum-v1:"
        + sha256(
            repr((record.reference, record.years, record.missing_data_treatment, record.uncertainty)).encode()
        ).hexdigest()
    )
    reference = record.reference
    return HydrologicalProduct(
        EvidenceScope(
            identity,
            reference.location.reach.identifier,
            reference.provenance.reference_member,
            reference.reference_period,
            intended_use,
        ),
        reference.provenance,
        HydrologicalProductKind.RECORDED_MINIMUM,
        "scalar_recorded_daily_minimum",
        "m3/s",
        f"fixed-day:{reference.accounting_start_month}:{reference.utc_offset_minutes}",
        TemporalResolution.DAILY,
        purpose,
        None,
        1,
        reference.location,
        reference.climate_basis,
        "lowest daily value over declared accepted record",
        identity,
        identity,
        record.value,
        tuple(s.interval for y in record.years for s in y.samples),
    )


@dataclass(frozen=True)
class ReachCoefficients:
    values: tuple[tuple[DesignClass, Fraction], ...]
    qualification: str
    derivation: str
    findings: EvidenceFindings | None = None

    def __post_init__(self) -> None:
        _text(self.qualification)
        _text(self.derivation)
        if (
            not isinstance(self.values, tuple)
            or len(self.values) != 4
            or {c for c, _ in self.values} != set(DesignClass)
        ):
            raise ValueError("qualified coefficients require all four classes")
        values = tuple((c, finite_number(v)) for c, v in self.values)
        if any(not isinstance(c, DesignClass) or v < 0 for c, v in values):
            raise ValueError("nonnegative typed class coefficients required")
        object.__setattr__(self, "values", values)


class RiverRegulation(StrEnum):
    REGULATED_NATURAL = "regulated_natural"
    UNREGULATED_NATURAL = "unregulated_natural"


@dataclass(frozen=True)
class WinterProvision:
    regulation: RiverRegulation
    reference: Flow
    share: Fraction
    adoption_basis: str
    reference_evidence: str
    findings: EvidenceFindings | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.regulation, RiverRegulation) or not isinstance(self.reference, Flow):
            raise TypeError("natural regulation and Flow reference required")
        share = finite_number(self.share)
        if not 0 <= share <= 1:
            raise ValueError("winter share must lie in [0,1]")
        object.__setattr__(self, "share", share)
        _text(self.adoption_basis)
        _text(self.reference_evidence)


def coefficient_scope(
    alpha: ReachCoefficients, location: Location, calendar: AccountingYear, provenance: Provenance, intended_use: str
) -> EvidenceScope:
    identity = (
        "reach-alpha-v1:"
        + sha256(
            repr((alpha.values, alpha.qualification, alpha.derivation, location, calendar, provenance)).encode()
        ).hexdigest()
    )
    return EvidenceScope(
        identity, location.reach.identifier, provenance.reference_member, calendar.interval, intended_use
    )


def winter_scope(
    winter: WinterProvision, location: Location, calendar: AccountingYear, provenance: Provenance, intended_use: str
) -> EvidenceScope:
    identity = (
        "winter-provision-v1:"
        + sha256(
            repr(
                (
                    winter.regulation,
                    winter.reference,
                    winter.share,
                    winter.adoption_basis,
                    winter.reference_evidence,
                    location,
                    calendar,
                    provenance,
                )
            ).encode()
        ).hexdigest()
    )
    return EvidenceScope(
        identity, location.reach.identifier, provenance.reference_member, calendar.interval, intended_use
    )


def _optional_permission(
    findings: EvidenceFindings | None, scope: EvidenceScope, provenance: Provenance, name: str
) -> Check:
    if findings is None:
        return Check(name, CheckFinding.UNKNOWN, ("exact supported evidence missing; component inactive",))
    if findings.provenance != provenance:
        return Check(name, CheckFinding.FAIL, ("evidence provenance mismatch",))
    return replace(permitted_use(findings, scope), check_id=name)


@dataclass(frozen=True)
class AdvisorySpawning:
    coefficients: tuple[Fraction, ...]
    calendar: AccountingYear
    biological_timing: str
    coefficient_provenance: str
    findings: EvidenceFindings | None = None

    def __post_init__(self) -> None:
        _text(self.biological_timing)
        _text(self.coefficient_provenance)
        if not isinstance(self.coefficients, tuple) or len(self.coefficients) != self.calendar.days:
            raise ValueError("complete spawning calendar required")
        values = tuple(finite_number(v) for v in self.coefficients)
        if any(v < 1 for v in values):
            raise ValueError("spawning advisory cannot reduce baseline")
        object.__setattr__(self, "coefficients", values)


def spawning_scope(
    spawning: AdvisorySpawning, location: Location, provenance: Provenance, intended_use: str
) -> EvidenceScope:
    identity = (
        "advisory-spawning-v1:"
        + sha256(
            repr(
                (
                    spawning.coefficients,
                    spawning.calendar,
                    spawning.biological_timing,
                    spawning.coefficient_provenance,
                    location,
                    provenance,
                )
            ).encode()
        ).hexdigest()
    )
    return EvidenceScope(
        identity, location.reach.identifier, provenance.reference_member, spawning.calendar.interval, intended_use
    )


@dataclass(frozen=True)
class BaselineDay:
    design: DesignClass
    interval: Interval
    class_flow: Flow
    natural99: Flow
    natural50: Flow
    recorded_minimum: Flow
    winter: Flow | None
    lower: Flow
    crossing: CheckFinding


@dataclass(frozen=True)
class BaselineInputs:
    patterns: tuple[DailyPattern, ...]
    recorded: RecordedMinimum | None
    alpha: ReachCoefficients | None
    winter: WinterProvision | None
    spawning: AdvisorySpawning | None


@dataclass(frozen=True)
class BaselineResult:
    candidate: EcologicalMemberCandidate | None
    diagnostics: tuple[BaselineDay, ...]
    checks: CheckSummary
    advisory_spawning: tuple[ClassEcologicalRegime, ...]
    inputs: BaselineInputs
    optional_evidence: CheckSummary = field(default_factory=lambda: CheckSummary(()))
    limitations: tuple[str, ...] = (
        "Pre-quality candidate: final duration, quality, receptor and selected-family gates still required.",
    )


def baseline_family(
    patterns: tuple[DailyPattern, ...],
    recorded: RecordedMinimum | None,
    *,
    provenance: Provenance,
    profile_version: str,
    alpha: ReachCoefficients | None = None,
    winter: WinterProvision | None = None,
    spawning: AdvisorySpawning | None = None,
) -> BaselineResult:
    """Assemble all four classes; one strict pre-cap crossing declines the family."""
    _text(profile_version)
    required = tuple(Fraction(p, 100) for p in (50, 75, 90, 97, 99))
    by_probability = {p.magnitude.target.value: p for p in patterns}
    if len(by_probability) != len(patterns) or set(by_probability) - set(required):
        raise ValueError("duplicate or unexpected natural probability")
    inputs = BaselineInputs(patterns, recorded, alpha, winter, spawning)
    checks = []
    for p in required:
        pattern = by_probability.get(p)
        checks.append(
            Check(f"pattern:{p}", CheckFinding.UNKNOWN, ("required pattern missing",))
            if pattern is None
            else Check(
                f"pattern:{p}",
                pattern.use_checks.finding,
                tuple(r for c in pattern.use_checks.checks for r in c.reasons),
            )
        )
    if not patterns:
        return BaselineResult(None, (), CheckSummary(tuple(checks)), (), inputs)
    first = patterns[0]
    for pattern in patterns:
        _identity(pattern.magnitude.provenance, provenance)
        if pattern.magnitude.provenance.reference_kind is not ReferenceKind.PRESENT_CLIMATE_NATURAL:
            raise ValueError("baseline requires accepted present-climate natural reference")
        if (
            pattern.calendar,
            pattern.location,
            pattern.magnitude.reference_identity,
            pattern.requested_use,
            pattern.purpose,
        ) != (first.calendar, first.location, first.magnitude.reference_identity, first.requested_use, first.purpose):
            raise ValueError("patterns must share exact reference/location/calendar/use")
    optional_checks = []
    selected_alpha = alpha
    selected_winter = winter
    if alpha is not None:
        permission = _optional_permission(
            alpha.findings,
            coefficient_scope(alpha, first.location, first.calendar, provenance, first.requested_use),
            provenance,
            "reach_coefficient",
        )
        optional_checks.append(permission)
        if permission.finding is not CheckFinding.PASS:
            selected_alpha = None
    if winter is not None:
        permission = _optional_permission(
            winter.findings,
            winter_scope(winter, first.location, first.calendar, provenance, first.requested_use),
            provenance,
            "winter_provision",
        )
        optional_checks.append(permission)
        if permission.finding is not CheckFinding.PASS:
            selected_winter = None
    selected_spawning = spawning
    if spawning is not None:
        if spawning.calendar != first.calendar:
            raise ValueError("spawning calendar differs")
        permission = _optional_permission(
            spawning.findings,
            spawning_scope(spawning, first.location, provenance, first.requested_use),
            provenance,
            "advisory_spawning",
        )
        optional_checks.append(permission)
        if permission.finding is not CheckFinding.PASS:
            selected_spawning = None
    optional_evidence = CheckSummary(tuple(optional_checks))
    checks.append(
        Check(
            "sizing_purpose",
            CheckFinding.PASS if first.purpose is UsePurpose.SIZING else CheckFinding.UNKNOWN,
            () if first.purpose is UsePurpose.SIZING else ("screening-only hydrology cannot size a requirement",),
        )
    )
    minimum_check = Check("recorded_minimum", CheckFinding.UNKNOWN, ("accepted recorded minimum missing",))
    if recorded is not None:
        if recorded.reference != first.magnitude.reference:
            raise ValueError("recorded minimum and patterns require same accepted reference")
        if recorded.assessment is not None:
            product = recorded_minimum_product(recorded, intended_use=first.requested_use, purpose=first.purpose)
            minimum_check = replace(recorded.assessment.acceptance_for(product), check_id="recorded_minimum")
    checks.append(minimum_check)
    if recorded is None or set(by_probability) != set(required) or any(not p.samples for p in patterns):
        return BaselineResult(None, (), CheckSummary(tuple(checks)), (), inputs, optional_evidence)
    assert recorded is not None
    minimum_value = recorded.value
    spawning = selected_spawning
    alpha = selected_alpha
    winter = selected_winter
    median = by_probability[Fraction(1, 2)]
    low = by_probability[Fraction(99, 100)]
    diagnostics = []
    regimes = []
    for design, probability in zip(DesignClass, required[:4], strict=True):
        pattern = by_probability[probability]
        if alpha is None:
            values = tuple(s.value.value for s in pattern.samples if s.value is not None)
        else:
            assert median.magnitude.value is not None
            magnitude = dict(alpha.values)[design] * median.magnitude.value.value
            if pattern.shape is None and magnitude != 0:
                checks.append(
                    Check(
                        f"alpha_shape:{design.value}",
                        CheckFinding.FAIL,
                        ("zero target has no supported positive shape",),
                    )
                )
                continue
            values = (
                tuple(magnitude * s for s in pattern.shape)
                if pattern.shape is not None
                else (Fraction(),) * first.calendar.days
            )
        samples = []
        for i, value in enumerate(values):
            n99, n50 = low.samples[i].value, median.samples[i].value
            assert n99 is not None and n50 is not None
            winter_flow = None
            if (
                winter is not None
                and winter.regulation is RiverRegulation.REGULATED_NATURAL
                and first.calendar.dates[i].month in (11, 12)
            ):
                winter_flow = Flow(winter.reference.value * winter.share)
            floors = (n99.value, minimum_value.value) + (() if winter_flow is None else (winter_flow.value,))
            lower = Flow(max(value, *floors))
            crossing = CheckFinding.FAIL if lower.value > n50.value else CheckFinding.PASS
            interval = pattern.samples[i].interval
            diagnostics.append(
                BaselineDay(design, interval, Flow(value), n99, n50, minimum_value, winter_flow, lower, crossing)
            )
            samples.append(
                FlowSample(
                    first.location, interval, Flow(max(min(value, n50.value), *floors)), Presence.PRESENT, provenance
                )
            )
        regimes.append(ClassEcologicalRegime(design, tuple(samples)))
    crossings = tuple(d for d in diagnostics if d.crossing is CheckFinding.FAIL)
    checks.append(
        Check(
            "pre_cap_natural_bounds",
            CheckFinding.FAIL if crossings else CheckFinding.PASS,
            (f"{len(crossings)} strict crossings; complete family declined",) if crossings else (),
        )
    )
    summary = CheckSummary(tuple(checks))
    if summary.finding is not CheckFinding.PASS:
        return BaselineResult(None, tuple(diagnostics), summary, (), inputs, optional_evidence)
    candidate = EcologicalMemberCandidate(
        first.location,
        first.calendar,
        provenance,
        EcologicalRegimeMethod.BASELINE,
        profile_version,
        tuple(regimes),
        tuple(a for p in patterns for a in (p.magnitude_assessment, p.shape_assessment) if a is not None)
        + (() if recorded.assessment is None else (recorded.assessment,)),
    )
    advisory = ()
    if spawning is not None:
        if spawning.calendar != first.calendar:
            raise ValueError("spawning calendar differs")
        advisory = tuple(
            ClassEcologicalRegime(
                r.design,
                tuple(
                    replace(s, value=Flow(s.value.value * k))
                    for s, k in zip(r.samples, spawning.coefficients, strict=True)
                    if s.value is not None
                ),
            )
            for r in regimes
            if r.design.value >= 75
        )
    return BaselineResult(candidate, tuple(diagnostics), summary, advisory, inputs, optional_evidence)


class EndpointRule(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class ClassInterval:
    design: DesignClass
    lower: Fraction
    upper: Fraction
    lower_rule: EndpointRule
    upper_rule: EndpointRule

    def __post_init__(self) -> None:
        if (
            not isinstance(self.design, DesignClass)
            or not isinstance(self.lower_rule, EndpointRule)
            or not isinstance(self.upper_rule, EndpointRule)
        ):
            raise TypeError("typed class and endpoint rules required")
        object.__setattr__(self, "lower", finite_number(self.lower))
        object.__setattr__(self, "upper", finite_number(self.upper))
        if not 0 <= self.lower < self.upper <= 1:
            raise ValueError("interval must lie in [0,1]")


@dataclass(frozen=True)
class ActualYearConvention:
    version: str
    calendar: AccountingYear
    reference_identity: str
    intervals: tuple[ClassInterval, ...]
    tie_basis: str

    def __post_init__(self) -> None:
        for value in (self.version, self.reference_identity, self.tie_basis):
            _text(value)
        if (
            not isinstance(self.intervals, tuple)
            or len(self.intervals) != 4
            or {i.design for i in self.intervals} != set(DesignClass)
        ):
            raise ValueError("four complete class intervals required")
        ordered = sorted(self.intervals, key=lambda i: i.lower)
        if (
            ordered[0].lower != 0
            or ordered[-1].upper != 1
            or ordered[0].lower_rule is not EndpointRule.INCLUDED
            or ordered[-1].upper_rule is not EndpointRule.INCLUDED
        ):
            raise ValueError("convention must cover full [0,1]")
        for a, b in zip(ordered, ordered[1:], strict=False):
            if a.upper != b.lower or a.upper_rule == b.lower_rule:
                raise ValueError("interval gap/overlap or ambiguous tie")


class ClassificationBasis(StrEnum):
    FORECAST = "forecast"
    OBSERVED = "observed_completed_year"


@dataclass(frozen=True)
class ActualYearSelection:
    design: DesignClass | None
    convention: ActualYearConvention | None
    probability: Fraction
    basis: ClassificationBasis
    issue_date: datetime
    assumptions: str
    reasons: tuple[str, ...]
    accepted_reference: DailyPattern | None = None


def select_actual_year(
    probability: Fraction,
    convention: ActualYearConvention | None,
    *,
    calendar: AccountingYear,
    reference_identity: str,
    basis: ClassificationBasis,
    issue_date: datetime,
    assumptions: str,
    reference: DailyPattern | None = None,
) -> ActualYearSelection:
    """Classify a supplied accepted-reference exceedance; never alter issued duties."""
    p = finite_number(probability)
    if not 0 <= p <= 1 or not isinstance(basis, ClassificationBasis) or issue_date.utcoffset() is None:
        raise ValueError("valid probability, classification basis and aware issue date required")
    _text(assumptions)
    _text(reference_identity)
    if basis is ClassificationBasis.OBSERVED and issue_date < calendar.interval.end:
        raise ValueError("observed classification requires completed year")
    if convention is None:
        return ActualYearSelection(
            None, None, p, basis, issue_date, assumptions, ("versioned interval convention missing",)
        )
    if reference is None or reference.use_checks.finding is not CheckFinding.PASS:
        return ActualYearSelection(
            None,
            convention,
            p,
            basis,
            issue_date,
            assumptions,
            ("accepted exact natural reference missing",),
            reference,
        )
    if (
        reference.magnitude.provenance.reference_kind is not ReferenceKind.PRESENT_CLIMATE_NATURAL
        or reference.magnitude.reference_identity != reference_identity
    ):
        raise ValueError("classification requires same accepted present-climate reference")
    if convention.calendar != calendar or convention.reference_identity != reference_identity:
        raise ValueError("classification calendar/reference mismatch")
    matches = tuple(
        i.design
        for i in convention.intervals
        if (p > i.lower or p == i.lower and i.lower_rule is EndpointRule.INCLUDED)
        and (p < i.upper or p == i.upper and i.upper_rule is EndpointRule.INCLUDED)
    )
    if len(matches) != 1:
        raise ValueError("classification requires unique interval")
    return ActualYearSelection(matches[0], convention, p, basis, issue_date, assumptions, (), reference)
