"""construct_pattern : AnnualEstimate × AnalogueReferences × PatternProfile → DailyPattern.

Conditional analogues preserve complete calendars, equal source-year weights and
separate scientific permission. This is a proposed Uzbek study method, not a
Kazakh statutory algorithm. No numerical setting is a national default.
"""

from dataclasses import dataclass, replace
from datetime import timedelta
from enum import StrEnum
from fractions import Fraction
from hashlib import sha256
from statistics import median

from fishy.annual_statistics import (
    AnnualEstimate,
    AnnualReference,
    ExceedanceProbability,
    ImportedDerivation,
    TrendTreatment,
    YearProbability,
    annual_use_checks,
    empirical_membership,
    fit_zero_mixture,
    fitted_membership,
)
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
)
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, check_flow_intervals, interval_use
from fishy.pattern_calendar import (
    AccountingYear,
    half_volume_marker,
    map_calendar,
    normalize_shares,
    shift_year,
)
from fishy.quantities import Flow, Volume, finite_number
from fishy.scientific_acceptance import (
    DESIGN_PATTERN_DEVELOPMENT_LIMITATION,
    HydrologicalProduct,
    HydrologicalProductKind,
    ScientificAssessment,
    TemporalResolution,
    UsePurpose,
)
from fishy.spatial import Location
from fishy.time import Interval


class MembershipEstimator(StrEnum):
    EMPIRICAL = "weibull_midrank"
    FITTED = "zero_mixture_lognormal"
    IMPORTED = "supported_import"


class AlignmentChoice(StrEnum):
    CALENDAR = "calendar_average"
    MELT = "half_volume_alignment"


class PatternMethod(StrEnum):
    ZERO = "accepted_zero"
    CALENDAR = "calendar_average"
    ALIGNED = "half_volume_alignment"
    FALLBACK = "calendar_fallback"
    IMPORTED = "imported_pattern"
    UNAVAILABLE = "unavailable"


class Extrapolation(StrEnum):
    WITHIN_SUPPORT = "within_selected_range"
    OUTSIDE_SUPPORT = "outside_selected_range"
    UNDEFINED = "undefined"


@dataclass(frozen=True)
class DailyReferenceYear:
    """Complete fixed-day natural-reference record; no inferred daily detail."""

    calendar: AccountingYear
    samples: tuple[FlowSample, ...]
    climate_cluster: str
    quality_checks: CheckSummary

    def __post_init__(self) -> None:
        if not isinstance(self.calendar, AccountingYear) or not isinstance(self.quality_checks, CheckSummary):
            raise TypeError("typed accounting calendar and quality checks required")
        if not isinstance(self.climate_cluster, str) or not self.climate_cluster.strip():
            raise ValueError("climate/accounting-year cluster required")
        if not isinstance(self.samples, tuple) or len(self.samples) != self.calendar.days:
            raise ValueError("daily reference requires one complete accounting year")
        check_flow_intervals(self.samples)
        ordered = tuple(sorted(self.samples, key=lambda x: x.interval.start))
        for index, sample in enumerate(ordered):
            start = self.calendar.interval.start + timedelta(days=index)
            if sample.interval != Interval(start, start + timedelta(days=1)):
                raise ValueError("daily reference must cover every fixed-offset day exactly")
            if (
                sample.value is None
                or sample.presence is not Presence.PRESENT
                or sample.coverage is not Coverage.COMPLETE
            ):
                raise ValueError("missing daily coverage cannot be substituted by zero")
            if interval_use(sample) is IntervalUse.EXCLUDED_WARMUP:
                raise ValueError("excluded warmup cannot supply a daily reference")
            if sample.provenance.reference_kind not in (
                ReferenceKind.PRESENT_CLIMATE_NATURAL,
                ReferenceKind.NATURALISED_HISTORICAL,
            ):
                raise ValueError("pattern sources require explicit natural-reference basis")
        object.__setattr__(self, "samples", ordered)

    @property
    def location(self) -> Location:
        return self.samples[0].location

    @property
    def provenance(self) -> Provenance:
        return self.samples[0].provenance

    @property
    def volumes(self) -> tuple[Fraction, ...]:
        return tuple(s.value.value * 86400 for s in self.samples if s.value is not None)

    @property
    def annual_mean(self) -> Flow:
        return Flow(sum(self.volumes, Fraction()) / self.calendar.interval.seconds)


@dataclass(frozen=True)
class ImportedMembership:
    """Full-reference probabilities from a reproducible specialist operator."""

    probabilities: tuple[YearProbability, ...]
    equation: str
    calibration: str
    diagnostics: str
    uncertainty: str
    provenance: Provenance

    def __post_init__(self) -> None:
        for name in ("equation", "calibration", "diagnostics", "uncertainty"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError("imported probabilities require reproducible derivation, not a model label")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("imported probabilities require provenance")
        if not isinstance(self.probabilities, tuple) or not self.probabilities:
            raise ValueError("full-reference probabilities required")


@dataclass(frozen=True)
class AnalogueReference:
    reference: AnnualReference
    years: tuple[DailyReferenceYear, ...]
    imported_membership: ImportedMembership | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reference, AnnualReference):
            raise TypeError("analogue requires the full accepted annual reference")
        if not isinstance(self.years, tuple):
            raise TypeError("daily years must be immutable")
        periods = [y.calendar.interval for y in self.years]
        if len(set(periods)) != len(periods):
            raise ValueError("a source year contributes at most once")
        observations = {s.interval: s for s in self.reference.observations}
        for year in self.years:
            if year.calendar.interval not in observations:
                raise ValueError("daily year is outside the full accepted reference")
            annual = observations[year.calendar.interval]
            if year.annual_mean != annual.value or year.location != annual.location:
                raise ValueError("daily annual mean/location differs from full-reference statistic")
            _same_identity(year.provenance, annual.provenance)
        if self.imported_membership is not None:
            probabilities = self.imported_membership.probabilities
            if len({p.interval for p in probabilities}) != len(probabilities):
                raise ValueError("duplicate imported membership years")
            if {p.interval for p in probabilities} != set(observations):
                raise ValueError("imported probabilities must cover the FULL annual reference, including zeros")
            _same_identity(self.imported_membership.provenance, self.reference.observations[0].provenance)


@dataclass(frozen=True)
class DonorEligibility:
    location: Location
    descriptors: tuple[str, ...]
    checks: CheckSummary
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.checks, CheckSummary):
            raise TypeError("donor requires location and supported eligibility checks")
        if not self.descriptors or any(not s.strip() for s in self.descriptors):
            raise ValueError("hydrological similarity descriptors required; proximity alone is insufficient")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("donor eligibility requires provenance")


@dataclass(frozen=True)
class AlignmentSettings:
    choice: AlignmentChoice
    season_start_day: int
    season_end_day: int
    maximum_shift_seconds: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.choice, AlignmentChoice):
            raise TypeError("explicit alignment choice required")
        for value in (self.season_start_day, self.season_end_day):
            if type(value) is not int or not 0 <= value <= 366:
                raise ValueError("season boundaries must be integer elapsed calendar days")
        shift = finite_number(self.maximum_shift_seconds)
        if shift < 0:
            raise ValueError("maximum shift must be nonnegative seconds")
        object.__setattr__(self, "maximum_shift_seconds", shift)


@dataclass(frozen=True)
class PatternProfile:
    version: str
    target: ExceedanceProbability
    band: Fraction
    reference_member: str
    scenario: str
    climate_basis: str
    estimator: MembershipEstimator
    donors: tuple[DonorEligibility, ...]
    minimum_source_years: int
    minimum_climate_clusters: int
    alignment: AlignmentSettings
    acceptance_profile: str
    reference_period: Interval

    def __post_init__(self) -> None:
        for name in ("version", "reference_member", "scenario", "climate_basis", "acceptance_profile"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError("complete versioned profile required before construction")
        if not isinstance(self.reference_period, Interval):
            raise TypeError("declared source-reference period required")
        if not isinstance(self.target, ExceedanceProbability) or not isinstance(self.estimator, MembershipEstimator):
            raise TypeError("target and probability estimator required")
        if not isinstance(self.alignment, AlignmentSettings):
            raise TypeError("alignment settings required")
        band = finite_number(self.band)
        if not 0 <= band <= 1:
            raise ValueError("probability band must be in [0,1]")
        object.__setattr__(self, "band", band)
        for count in (self.minimum_source_years, self.minimum_climate_clusters):
            if type(count) is not int or count < 1:
                raise ValueError("positive study-defined source/cluster support required")
        if not isinstance(self.donors, tuple) or len({d.location for d in self.donors}) != len(self.donors):
            raise ValueError("donor eligibility must be an immutable unique set")


@dataclass(frozen=True)
class SourceContribution:
    source: DailyReferenceYear
    probability: ExceedanceProbability
    mapped_shares: tuple[Fraction, ...]
    retained_shares: tuple[Fraction, ...]
    marker_seconds: Fraction | None
    shift_seconds: Fraction
    introduced_share: Fraction
    displaced_share: Fraction


@dataclass(frozen=True)
class SourceExclusion:
    location: Location
    year: Interval
    iteration: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AlignmentIteration:
    iteration: int
    median_seconds: Fraction
    shifts: tuple[tuple[Location, Interval, Fraction], ...]
    exclusions: tuple[SourceExclusion, ...]


@dataclass(frozen=True)
class MembershipSummary:
    source_count: int
    climate_cluster_count: int
    donor_counts: tuple[tuple[Location, int], ...]
    probability_range: tuple[Fraction, Fraction] | None
    probability_centre: Fraction | None
    nearest_distance: Fraction | None
    shape_extrapolation: Extrapolation


@dataclass(frozen=True)
class DailyPattern:
    """Numerical candidate and permission are independently inspectable."""

    location: Location
    calendar: AccountingYear
    magnitude: AnnualEstimate
    profile: PatternProfile | None
    method: PatternMethod
    samples: tuple[FlowSample, ...]
    shape: tuple[Fraction, ...] | None
    selected: tuple[SourceContribution, ...]
    retained: tuple[SourceContribution, ...]
    exclusions: tuple[SourceExclusion, ...]
    membership: MembershipSummary
    support: CheckSummary
    magnitude_evidence: EvidenceFindings | None
    shape_evidence: EvidenceFindings | None
    requested_use: str
    purpose: UsePurpose
    magnitude_assessment: ScientificAssessment | None
    shape_assessment: ScientificAssessment | None
    reasons: tuple[str, ...]
    references: tuple[AnalogueReference, ...] = ()
    imported_derivation: ImportedDerivation | None = None
    alignment_iterations: tuple[AlignmentIteration, ...] = ()

    def __post_init__(self) -> None:
        _receiving_calendar(self.magnitude, self.calendar)
        for values, kind in (
            (self.samples, FlowSample),
            (self.selected, SourceContribution),
            (self.retained, SourceContribution),
            (self.exclusions, SourceExclusion),
            (self.references, AnalogueReference),
            (self.alignment_iterations, AlignmentIteration),
            (self.reasons, str),
        ):
            if not isinstance(values, tuple) or any(not isinstance(value, kind) for value in values):
                raise TypeError("daily pattern carriers must be immutable typed tuples")
        if self.shape is not None and (
            not isinstance(self.shape, tuple) or any(not isinstance(value, Fraction) for value in self.shape)
        ):
            raise TypeError("shape must be an immutable exact tuple")
        for contributions in (self.selected, self.retained):
            keys = [(c.source.location, c.source.calendar.interval) for c in contributions]
            if len(set(keys)) != len(keys):
                raise ValueError("duplicate donor/source-year contribution cannot manufacture support")
        selected = {(c.source.location, c.source.calendar.interval): c for c in self.selected}
        for contribution in self.retained:
            key = (contribution.source.location, contribution.source.calendar.interval)
            if key not in selected:
                raise ValueError("retained contribution must belong to original selected set")
            original = selected[key]
            if (
                contribution.source != original.source
                or contribution.probability != original.probability
                or contribution.mapped_shares != original.mapped_shares
            ):
                raise ValueError("retained contribution changed its original source/membership/mapping")
        if self.membership != _summary(self.retained, self.magnitude.target.value):
            raise ValueError("membership diagnostics must match actual retained sources")
        if self.profile is not None and self.method in (
            PatternMethod.CALENDAR,
            PatternMethod.ALIGNED,
            PatternMethod.FALLBACK,
        ):
            if self.support != _support(self.retained, self.profile):
                raise ValueError("support diagnostics must match actual retained sources")
            for contribution in self.selected:
                if not isinstance(contribution.mapped_shares, tuple) or contribution.mapped_shares != normalize_shares(
                    map_calendar(contribution.source.calendar, contribution.source.volumes, self.calendar)
                ):
                    raise ValueError("selected calendar mapping differs from complete original source")
        if not isinstance(self.purpose, UsePurpose) or not self.requested_use.strip():
            raise ValueError("pattern requires explicit scoped intended use")
        if self.magnitude_evidence != (
            None if self.magnitude_assessment is None else self.magnitude_assessment.findings
        ):
            raise ValueError("annual findings must retain their evaluated acceptance record")
        if self.shape_evidence != (None if self.shape_assessment is None else self.shape_assessment.findings):
            raise ValueError("shape findings must retain their evaluated acceptance record")
        if self.method in (PatternMethod.CALENDAR, PatternMethod.ALIGNED, PatternMethod.FALLBACK) and not self.retained:
            raise ValueError("native positive pattern cannot discard its fixed contributors")
        if self.method is PatternMethod.IMPORTED and not isinstance(self.imported_derivation, ImportedDerivation):
            raise TypeError("imported pattern must retain its complete reproducible derivation")
        if not self.samples:
            if self.shape is not None or self.method is not PatternMethod.UNAVAILABLE:
                raise ValueError("unavailable pattern cannot assert a shape or successful method")
            return
        if len(self.samples) != self.calendar.days or self.magnitude.value is None:
            raise ValueError("pattern requires complete receiving calendar and annual magnitude")
        check_flow_intervals(self.samples)
        for i, sample in enumerate(self.samples):
            start = self.calendar.interval.start + timedelta(days=i)
            if (
                sample.location != self.location
                or sample.interval != Interval(start, start + timedelta(days=1))
                or sample.value is None
                or sample.presence is not Presence.PRESENT
                or sample.coverage is not Coverage.COMPLETE
            ):
                raise ValueError("pattern schedule must cover complete supported fixed days")
            _same_identity(sample.provenance, self.magnitude.provenance)
        total = sum((sample.value.value for sample in self.samples if sample.value is not None), Fraction())
        if total != self.magnitude.value.value * self.calendar.days:
            raise ValueError("pattern schedule fails receiving annual mean/volume closure")
        if self.magnitude.value.value == 0:
            if self.shape is not None:
                raise ValueError("zero-target mean-one shape is undefined")
        elif (
            self.shape is None
            or tuple(
                sample.value.value / self.magnitude.value.value for sample in self.samples if sample.value is not None
            )
            != self.shape
        ):
            raise ValueError("pattern shape differs from its once-scaled schedule")
        if self.retained:
            for contribution in self.retained:
                if (
                    not isinstance(contribution.retained_shares, tuple)
                    or len(contribution.retained_shares) != self.calendar.days
                    or sum(contribution.retained_shares, Fraction()) != 1
                    or any(value < 0 for value in contribution.retained_shares)
                ):
                    raise ValueError("retained contributions require complete nonnegative unit shares")
            expected = tuple(
                self.calendar.days * sum((c.retained_shares[i] for c in self.retained), Fraction()) / len(self.retained)
                for i in range(self.calendar.days)
            )
            if self.shape != expected:
                raise ValueError("daily shape must use one fixed equal-year contributor set")
        if self.shape_assessment is not None and self.magnitude.value.value > 0:
            expected_product = pattern_product(self, intended_use=self.requested_use, purpose=self.purpose)
            if self.shape_assessment.record.product != expected_product:
                raise ValueError("shape acceptance record does not bind this exact daily candidate")

    @property
    def use_checks(self) -> CheckSummary:
        """Re-evaluate permission against current content; replacement cannot carry a pass."""
        annual = _permission(
            self.magnitude_assessment,
            annual_magnitude_product(self.magnitude, intended_use=self.requested_use, purpose=self.purpose),
            "annual_magnitude",
        )
        if self.magnitude_evidence is not None:
            checks = annual_use_checks(self.magnitude, self.magnitude_evidence, self.requested_use)
            combined = CheckSummary((annual, *checks.checks))
            annual = Check("annual_magnitude", combined.finding, tuple(r for c in combined.checks for r in c.reasons))
        if not self.samples:
            return CheckSummary((annual, Check("daily_pattern", CheckFinding.FAIL, self.reasons)))
        if self.magnitude.value is not None and self.magnitude.value.value == 0:
            zero = Check(
                "accepted_zero",
                CheckFinding.PASS
                if self.magnitude_evidence is not None
                and self.magnitude_evidence.scientific_adequacy is ScientificAdequacy.ACCEPTED
                else CheckFinding.FAIL,
                ("zero target requires accepted annual and intermittency evidence",),
            )
            return CheckSummary((annual, zero))
        shape = _permission(
            self.shape_assessment,
            pattern_product(self, intended_use=self.requested_use, purpose=self.purpose),
            "daily_shape",
        )
        if (
            self.shape_assessment is not None
            and self.profile is not None
            and self.shape_assessment.record.profile_version != self.profile.acceptance_profile
        ):
            shape = Check("daily_shape", CheckFinding.UNKNOWN, ("configured acceptance profile differs",))
        source_separation = Check(
            "source_validation_separation", CheckFinding.UNKNOWN, ("source/validation independence not supplied",)
        )
        if self.shape_assessment is not None and self.shape_assessment.evidence.validation is not None:
            validation = self.shape_assessment.evidence.validation
            clusters = {year.climate_cluster for reference in self.references for year in reference.years}
            overlap = clusters.intersection(validation.validation_clusters)
            source_separation = Check(
                "source_validation_separation",
                CheckFinding.FAIL if overlap else CheckFinding.PASS,
                tuple(f"actual source climate cluster also withheld: {cluster}" for cluster in sorted(overlap)),
            )
        retained_locations = {c.source.location for c in self.retained}
        source_climate = []
        for index, reference in enumerate(self.references):
            if reference.reference.location not in retained_locations:
                continue
            if reference.reference.provenance.reference_kind is not ReferenceKind.PRESENT_CLIMATE_NATURAL:
                continue
            trend = reference.reference.trend
            finding = (
                CheckFinding.FAIL
                if trend is TrendTreatment.UNTREATED
                else CheckFinding.UNKNOWN
                if trend is TrendTreatment.UNASSESSED
                else CheckFinding.PASS
            )
            source_climate.append(
                Check(f"source_climate_{index}", finding, (f"actual donor climate treatment: {trend.value}",))
            )
        support = _support(self.retained, self.profile).checks if self.profile is not None else ()
        return CheckSummary((annual, shape, source_separation, *source_climate, *support))

    @property
    def volume(self) -> Volume | None:
        if not self.samples:
            return None
        return Volume(
            sum((s.value.value * s.interval.seconds for s in self.samples if s.value is not None), Fraction())
        )


def _receiving_calendar(magnitude: AnnualEstimate, calendar: AccountingYear) -> None:
    if (
        magnitude.reference.accounting_start_month != calendar.start_month
        or magnitude.reference.utc_offset_minutes != calendar.utc_offset_minutes
    ):
        raise ValueError(
            "receiving annual magnitude and daily accounting calendar differ; explicit conversion required"
        )


def _same_identity(first: Provenance, second: Provenance) -> None:
    if any(getattr(first, key) != getattr(second, key) for key in ("scenario", "reference_member", "reference_kind")):
        raise ValueError("incompatible scenario/reference member/basis")


def _summary(contributions: tuple[SourceContribution, ...], target: Fraction) -> MembershipSummary:
    probabilities = tuple(c.probability.value for c in contributions)
    donors = sorted(
        {c.source.location for c in contributions}, key=lambda d: (d.reach.identifier, d.section.identifier)
    )
    bounds = (min(probabilities), max(probabilities)) if probabilities else None
    return MembershipSummary(
        len(contributions),
        len({c.source.climate_cluster for c in contributions}),
        tuple((donor, sum(c.source.location == donor for c in contributions)) for donor in donors),
        bounds,
        sum(probabilities, Fraction()) / len(probabilities) if probabilities else None,
        min(abs(p - target) for p in probabilities) if probabilities else None,
        Extrapolation.UNDEFINED
        if bounds is None
        else (Extrapolation.WITHIN_SUPPORT if bounds[0] <= target <= bounds[1] else Extrapolation.OUTSIDE_SUPPORT),
    )


def _support(contributions: tuple[SourceContribution, ...], profile: PatternProfile) -> CheckSummary:
    summary = _summary(contributions, profile.target.value)
    return CheckSummary(
        (
            Check(
                "source_years",
                CheckFinding.PASS if summary.source_count >= profile.minimum_source_years else CheckFinding.FAIL,
                (f"actual={summary.source_count}; required={profile.minimum_source_years}",),
            ),
            Check(
                "climate_clusters",
                CheckFinding.PASS
                if summary.climate_cluster_count >= profile.minimum_climate_clusters
                else CheckFinding.FAIL,
                (f"actual={summary.climate_cluster_count}; required={profile.minimum_climate_clusters}",),
            ),
        )
    )


def pattern_scope(
    magnitude: AnnualEstimate, calendar: AccountingYear, profile: PatternProfile | None, intended_use: str
) -> EvidenceScope:
    """Identify one probability/profile/calendar product, not a generic daily shape."""
    version = "imported" if profile is None else profile.version
    product = f"daily_pattern:{version}:P={magnitude.target.value}:annual={magnitude.scope(intended_use).product}"
    return EvidenceScope(
        product,
        magnitude.reference.location.reach.identifier,
        magnitude.provenance.reference_member,
        calendar.interval,
        intended_use,
    )


def _permission(assessment: ScientificAssessment | None, product: HydrologicalProduct, identifier: str) -> Check:
    if assessment is None:
        return Check(identifier, CheckFinding.UNKNOWN, ("scientific acceptance basis missing",))
    if not isinstance(assessment, ScientificAssessment):
        raise TypeError("use permission requires an evaluated ScientificAssessment")
    return replace(assessment.acceptance_for(product), check_id=identifier)


def _schedule(
    location: Location, calendar: AccountingYear, values: tuple[Fraction, ...], provenance: Provenance
) -> tuple[FlowSample, ...]:
    return tuple(
        FlowSample(
            location,
            Interval(calendar.interval.start + timedelta(days=i), calendar.interval.start + timedelta(days=i + 1)),
            Flow(value),
            Presence.PRESENT,
            provenance,
        )
        for i, value in enumerate(values)
    )


def _probabilities(pool: AnalogueReference, estimator: MembershipEstimator) -> tuple[YearProbability, ...]:
    if estimator is MembershipEstimator.EMPIRICAL:
        return empirical_membership(pool.reference)
    if estimator is MembershipEstimator.FITTED:
        return fitted_membership(pool.reference, fit_zero_mixture(pool.reference))
    if pool.imported_membership is None:
        raise ValueError("selected imported probability estimator is missing")
    return pool.imported_membership.probabilities


def construct_pattern(
    magnitude: AnnualEstimate,
    calendar: AccountingYear,
    references: tuple[AnalogueReference, ...],
    profile: PatternProfile | None,
    *,
    intended_use: str,
    purpose: UsePurpose,
    magnitude_assessment: ScientificAssessment | None = None,
    shape_assessment: ScientificAssessment | None = None,
) -> DailyPattern:
    """Compute one selected conditional-analogue candidate, never an issued duty.

    A failed support check retains exploratory numbers. Scientific evidence must
    match the exact annual and daily scopes; annual permission cannot clear a
    shape failure. Missing profile or unsupported zero returns no schedule.
    """
    if not isinstance(magnitude, AnnualEstimate) or not isinstance(calendar, AccountingYear):
        raise TypeError("annual estimate and valid accounting calendar required")
    _receiving_calendar(magnitude, calendar)
    if not isinstance(purpose, UsePurpose):
        raise TypeError("explicit intended-use purpose required")
    location, provenance = magnitude.reference.location, magnitude.provenance
    magnitude_evidence = None if magnitude_assessment is None else magnitude_assessment.findings
    shape_evidence = None if shape_assessment is None else shape_assessment.findings
    magnitude_check = _permission(
        magnitude_assessment,
        annual_magnitude_product(magnitude, intended_use=intended_use, purpose=purpose),
        "annual_magnitude",
    )
    if magnitude_evidence is not None:
        annual_checks = annual_use_checks(magnitude, magnitude_evidence, intended_use)
        combined = CheckSummary((magnitude_check, *annual_checks.checks))
        magnitude_check = Check(
            "annual_magnitude", combined.finding, tuple(r for check in combined.checks for r in check.reasons)
        )
    empty = _summary((), magnitude.target.value)

    def unavailable(reason: str) -> DailyPattern:
        return DailyPattern(
            location,
            calendar,
            magnitude,
            profile,
            PatternMethod.UNAVAILABLE,
            (),
            None,
            (),
            (),
            (),
            empty,
            CheckSummary(()),
            magnitude_evidence,
            shape_evidence,
            intended_use,
            purpose,
            magnitude_assessment,
            shape_assessment,
            (reason,),
            references,
        )

    if profile is not None:
        if (
            profile.target != magnitude.target
            or profile.reference_member != provenance.reference_member
            or profile.scenario != provenance.scenario
        ):
            raise ValueError("pattern profile differs from receiving target/scenario/member")
        if profile.climate_basis != magnitude.reference.climate_basis:
            raise ValueError("receiving magnitude differs from declared climate basis")
    if magnitude.provenance.reference_kind not in (
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
        ReferenceKind.NATURALISED_HISTORICAL,
    ):
        raise ValueError("daily natural design pattern requires nonnegative natural-reference magnitude")
    if magnitude.value is None:
        return unavailable("annual magnitude unavailable")
    if magnitude.value.value == 0:
        if (
            magnitude_check.finding is not CheckFinding.PASS
            or magnitude_evidence is None
            or magnitude_evidence.scientific_adequacy is not ScientificAdequacy.ACCEPTED
        ):
            return unavailable("zero target is not accepted; positive-shape exception unavailable")
        samples = _schedule(location, calendar, (Fraction(),) * calendar.days, provenance)
        return DailyPattern(
            location,
            calendar,
            magnitude,
            profile,
            PatternMethod.ZERO,
            samples,
            None,
            (),
            (),
            (),
            empty,
            CheckSummary(()),
            magnitude_evidence,
            shape_evidence,
            intended_use,
            purpose,
            magnitude_assessment,
            shape_assessment,
            ("accepted zero magnitude; mean-one shape undefined and unnecessary",),
        )
    if profile is None:
        return unavailable("pattern profile missing")
    if profile.target != magnitude.target:
        raise ValueError("pattern target differs from receiving magnitude; no second probability shift")
    if profile.reference_member != provenance.reference_member or profile.scenario != provenance.scenario:
        raise ValueError("pattern profile differs from receiving scenario/member")
    if magnitude.reference.climate_basis != profile.climate_basis:
        raise ValueError("receiving magnitude differs from declared climate basis")
    donors = {d.location: d for d in profile.donors}
    exclusions: list[SourceExclusion] = []
    selected: list[SourceContribution] = []
    source_pools: dict[tuple[Location, Interval], AnalogueReference] = {}
    lower, upper = (
        max(Fraction(), profile.target.value - profile.band),
        min(Fraction(1), profile.target.value + profile.band),
    )
    for pool in references:
        source = pool.reference.observations[0]
        if (
            pool.reference.reference_period.start < profile.reference_period.start
            or pool.reference.reference_period.end > profile.reference_period.end
        ):
            raise ValueError("source reference outside frozen profile reference period")
        _same_identity(provenance, source.provenance)
        if pool.reference.climate_basis != profile.climate_basis:
            raise ValueError("donor climate basis mismatch")
        probabilities = {p.interval: p.exceedance for p in _probabilities(pool, profile.estimator)}
        supplied_daily = {year.calendar.interval for year in pool.years}
        for observation in pool.reference.observations:
            if observation.interval not in supplied_daily:
                exclusions.append(
                    SourceExclusion(
                        observation.location, observation.interval, 0, ("complete daily source year unavailable",)
                    )
                )
        for year in pool.years:
            key = (year.location, year.calendar.interval)
            if key in source_pools:
                raise ValueError("duplicate donor-year contribution")
            source_pools[key] = pool
            if year.calendar.start_month != calendar.start_month:
                raise ValueError("accounting years must start in the same calendar month")
            probability = probabilities[year.calendar.interval]
            reasons: list[str] = []
            if year.location not in donors:
                reasons.append("donor eligibility missing")
            else:
                _same_identity(donors[year.location].provenance, year.provenance)
                if donors[year.location].checks.finding is not CheckFinding.PASS:
                    reasons.append("donor eligibility not supported")
            if year.quality_checks.finding is not CheckFinding.PASS:
                reasons.append("daily quality/reconstruction not supported")
            if year.annual_mean.value == 0:
                reasons.append("zero source retained in annual statistics, not positive shape")
            if not lower <= probability.value <= upper:
                reasons.append("outside closed probability band")
            if reasons:
                exclusions.append(SourceExclusion(year.location, year.calendar.interval, 0, tuple(reasons)))
                continue
            shares = normalize_shares(map_calendar(year.calendar, year.volumes, calendar))
            selected.append(
                SourceContribution(year, probability, shares, shares, None, Fraction(), Fraction(), Fraction())
            )
    selected.sort(
        key=lambda c: (c.source.location.reach.identifier, c.source.location.section.identifier, c.source.calendar.year)
    )
    original = tuple(selected)
    if not original:
        result = unavailable("no eligible positive-volume source years")
        return replace(result, exclusions=tuple(exclusions), support=_support((), profile))
    retained = original
    method = PatternMethod.CALENDAR
    reasons_out: list[str] = []
    iterations: list[AlignmentIteration] = []
    settings = profile.alignment
    if settings.choice is AlignmentChoice.MELT:
        if settings.season_start_day >= settings.season_end_day:
            method = PatternMethod.FALLBACK
            reasons_out.append("melt season crosses design-year boundary; calendar fallback")
        else:
            if settings.season_end_day > calendar.days:
                raise ValueError("melt season exceeds receiving calendar")
            retained_list: list[SourceContribution] = []
            for contribution in original:
                marker = half_volume_marker(
                    contribution.mapped_shares, settings.season_start_day, settings.season_end_day
                )
                if marker is None:
                    exclusions.append(
                        SourceExclusion(
                            contribution.source.location,
                            contribution.source.calendar.interval,
                            1,
                            ("no identifiable positive seasonal volume",),
                        )
                    )
                else:
                    retained_list.append(replace(contribution, marker_seconds=marker))
            retained = tuple(retained_list)
            iteration = 1
            while retained:
                centre = Fraction(median(c.marker_seconds for c in retained if c.marker_seconds is not None))
                candidates: list[SourceContribution] = []
                removed: list[SourceExclusion] = []
                for contribution in retained:
                    assert contribution.marker_seconds is not None
                    shift = centre - contribution.marker_seconds
                    year = contribution.source
                    failure: str | None = None
                    if abs(shift) > settings.maximum_shift_seconds:
                        failure = "maximum absolute shift exceeded"
                    else:
                        pool = source_pools[(year.location, year.calendar.interval)]
                        context = {
                            y.calendar.year: y for y in pool.years if y.quality_checks.finding is CheckFinding.PASS
                        }
                        left = context.get(year.calendar.year - 1)
                        right = context.get(year.calendar.year + 1)
                        shifted = shift_year(
                            year.calendar,
                            year.volumes,
                            calendar,
                            shift,
                            left_volumes=None if left is None else left.volumes,
                            right_volumes=None if right is None else right.volumes,
                        )
                        if shifted.shares is None:
                            failure = shifted.reason or "alignment unsupported"
                        elif sum(shifted.shares, Fraction()) <= 0:
                            failure = "zero retained design-interval volume"
                        else:
                            candidates.append(
                                replace(
                                    contribution,
                                    retained_shares=normalize_shares(shifted.shares),
                                    shift_seconds=shift,
                                    introduced_share=shifted.introduced or Fraction(),
                                    displaced_share=shifted.displaced or Fraction(),
                                )
                            )
                    if failure is not None:
                        removed.append(SourceExclusion(year.location, year.calendar.interval, iteration, (failure,)))
                iterations.append(
                    AlignmentIteration(
                        iteration,
                        centre,
                        tuple(
                            (c.source.location, c.source.calendar.interval, centre - c.marker_seconds)
                            for c in retained
                            if c.marker_seconds is not None
                        ),
                        tuple(removed),
                    )
                )
                exclusions.extend(removed)
                retained = tuple(candidates)
                if not removed:
                    break
                iteration += 1
            if _support(retained, profile).finding is CheckFinding.PASS:
                method = PatternMethod.ALIGNED
            else:
                method, retained = PatternMethod.FALLBACK, original
                reasons_out.append("aligned support failed; calendar fallback uses original eligible set")
    support = _support(retained, profile)
    shares = tuple(
        sum((c.retained_shares[i] for c in retained), Fraction()) / len(retained) for i in range(calendar.days)
    )
    shares = normalize_shares(shares)
    shape = tuple(calendar.days * value for value in shares)
    values = tuple(magnitude.value.value * value for value in shape)
    if sum(shape, Fraction()) != calendar.days or any(value < 0 for value in values):
        raise ArithmeticError("daily shape closure violated")
    output_provenance = replace(
        provenance,
        production_method=ProductionMethod.IMPORTED,
        configuration_version=profile.version,
        dependencies=(*provenance.dependencies, *(c.source.provenance.source for c in retained)),
        limitations=(
            *provenance.limitations,
            "calendar mapping/alignment is not newly observed daily detail",
            "annual closure does not establish daily or rare-tail adequacy",
            DESIGN_PATTERN_DEVELOPMENT_LIMITATION,
        ),
    )
    samples = _schedule(location, calendar, values, output_provenance)
    result = DailyPattern(
        location,
        calendar,
        magnitude,
        profile,
        method,
        samples,
        shape,
        original,
        retained,
        tuple(exclusions),
        _summary(retained, profile.target.value),
        support,
        magnitude_evidence,
        shape_evidence,
        intended_use,
        purpose,
        magnitude_assessment,
        shape_assessment,
        tuple(reasons_out),
        references,
        alignment_iterations=tuple(iterations),
    )

    return result


def crossed_bounds(lower: DailyPattern, upper: DailyPattern) -> tuple[Interval, ...]:
    """Return strict daily crossings without sorting, clipping or mixing members."""
    if lower.location != upper.location or lower.calendar != upper.calendar:
        raise ValueError("bounds require identical receiving location/calendar")
    if not lower.samples or not upper.samples:
        raise ValueError("both complete design patterns are required")
    _same_identity(lower.samples[0].provenance, upper.samples[0].provenance)
    return tuple(
        a.interval
        for a, b in zip(lower.samples, upper.samples, strict=True)
        if a.value is not None and b.value is not None and a.value.value > b.value.value
    )


def annual_magnitude_product(
    magnitude: AnnualEstimate, *, intended_use: str, purpose: UsePurpose
) -> HydrologicalProduct:
    """Build the exact annual subject for a caller-owned scientific assessment."""
    reference = magnitude.reference
    return HydrologicalProduct(
        scope=magnitude.scope(intended_use),
        provenance=magnitude.provenance,
        kind=HydrologicalProductKind.ANNUAL_MAGNITUDE,
        statistic_name="annual mean discharge",
        units="m3/s",
        calendar=f"gregorian:start_month={reference.accounting_start_month}:utc_offset_minutes={reference.utc_offset_minutes}",
        resolution=TemporalResolution.ANNUAL,
        purpose=purpose,
        target_probability=float(magnitude.target.value),
        duration_days=None,
        location=reference.location,
        climate_basis=reference.climate_basis,
        population="annual mean discharge",
        reference_identity=magnitude.reference_identity,
        result_identity=magnitude.identity,
        result_value=magnitude.value,
    )


def pattern_product(pattern: DailyPattern, *, intended_use: str, purpose: UsePurpose) -> HydrologicalProduct:
    """Identify exact candidate content, without claiming scientific acceptance."""
    if not pattern.samples:
        raise ValueError("unavailable pattern has no numerical daily product")
    calendar = pattern.calendar
    source_records = tuple(sorted(repr(reference) for reference in pattern.references))
    reference_identity = sha256(repr((pattern.magnitude.reference_identity, source_records)).encode()).hexdigest()
    result_identity = sha256(
        repr(
            (
                pattern.samples,
                pattern.profile,
                pattern.method,
                pattern.reasons,
                pattern.imported_derivation,
                pattern.selected,
                pattern.retained,
                pattern.exclusions,
                pattern.membership,
                pattern.support,
                pattern.alignment_iterations,
            )
        ).encode()
    ).hexdigest()
    return HydrologicalProduct(
        scope=pattern_scope(pattern.magnitude, calendar, pattern.profile, intended_use),
        provenance=pattern.samples[0].provenance,
        kind=HydrologicalProductKind.DAILY_PATTERN,
        statistic_name="conditional daily design discharge"
        if pattern.method is not PatternMethod.IMPORTED
        else "imported daily design discharge",
        units="m3/s",
        calendar=f"gregorian:start_month={calendar.start_month}:utc_offset_minutes={calendar.utc_offset_minutes}",
        resolution=TemporalResolution.DAILY,
        purpose=purpose,
        target_probability=float(pattern.magnitude.target.value),
        duration_days=None,
        location=pattern.location,
        climate_basis=pattern.magnitude.reference.climate_basis,
        population="daily design pattern conditional on annual mean exceedance",
        reference_identity=reference_identity,
        result_identity=result_identity,
        result_value=None,
        intervals=tuple(sample.interval for sample in pattern.samples),
    )


def import_pattern(
    magnitude: AnnualEstimate,
    calendar: AccountingYear,
    samples: tuple[FlowSample, ...],
    derivation: ImportedDerivation,
    *,
    intended_use: str,
    purpose: UsePurpose,
    magnitude_assessment: ScientificAssessment | None = None,
    shape_assessment: ScientificAssessment | None = None,
) -> DailyPattern:
    """Check a supported external daily pattern without re-scaling its discharge.

    Complete fixed-day coverage, member identity and annual mean must agree.
    Derivation and all original per-day provenance remain visible. An import
    is not relabelled as the native conditional-analogue construction.
    """
    _receiving_calendar(magnitude, calendar)
    if not isinstance(derivation, ImportedDerivation):
        raise TypeError("pattern import requires reproducible specialist derivation")
    if magnitude.value is None:
        raise ValueError("import requires receiving annual magnitude")
    if not isinstance(samples, tuple) or len(samples) != calendar.days:
        raise ValueError("import requires a complete daily accounting year")
    check_flow_intervals(samples)
    ordered = tuple(sorted(samples, key=lambda sample: sample.interval.start))
    for i, sample in enumerate(ordered):
        expected = Interval(
            calendar.interval.start + timedelta(days=i), calendar.interval.start + timedelta(days=i + 1)
        )
        if sample.interval != expected or sample.location != magnitude.reference.location:
            raise ValueError("imported daily interval/location differs from receiving calendar")
        if (
            sample.value is None
            or sample.presence is not Presence.PRESENT
            or sample.coverage is not Coverage.COMPLETE
            or interval_use(sample) is not IntervalUse.ELIGIBLE
        ):
            raise ValueError("imported pattern contains missing or unsupported daily coverage")
        _same_identity(sample.provenance, magnitude.provenance)
    total = sum((sample.value.value for sample in ordered if sample.value is not None), Fraction())
    if total != magnitude.value.value * calendar.days:
        raise ValueError("imported pattern mean/volume differs from annual magnitude; no silent scaling")
    magnitude_evidence = None if magnitude_assessment is None else magnitude_assessment.findings
    shape_evidence = None if shape_assessment is None else shape_assessment.findings
    annual_check = _permission(
        magnitude_assessment,
        annual_magnitude_product(magnitude, intended_use=intended_use, purpose=purpose),
        "annual_magnitude",
    )
    if magnitude_evidence is not None:
        annual_checks = annual_use_checks(magnitude, magnitude_evidence, intended_use)
        summary = CheckSummary((annual_check, *annual_checks.checks))
        annual_check = Check(
            "annual_magnitude", summary.finding, tuple(r for check in summary.checks for r in check.reasons)
        )
    if magnitude.value.value == 0 and (
        annual_check.finding is not CheckFinding.PASS
        or magnitude_evidence is None
        or magnitude_evidence.scientific_adequacy is not ScientificAdequacy.ACCEPTED
    ):
        raise ValueError("imported zero target requires accepted annual/intermittency evidence")
    shape = (
        None
        if magnitude.value.value == 0
        else tuple(sample.value.value / magnitude.value.value for sample in ordered if sample.value is not None)
    )
    result = DailyPattern(
        magnitude.reference.location,
        calendar,
        magnitude,
        None,
        PatternMethod.IMPORTED,
        ordered,
        shape,
        (),
        (),
        (),
        _summary((), magnitude.target.value),
        CheckSummary(()),
        magnitude_evidence,
        shape_evidence,
        intended_use,
        purpose,
        magnitude_assessment,
        shape_assessment,
        (
            f"import equation: {derivation.equation}",
            f"import calibration: {derivation.calibration_data}",
            f"import diagnostics: {derivation.diagnostics}",
            f"import uncertainty: {derivation.uncertainty_method}",
            f"import reproduction: {derivation.reproducibility_reference}",
            "supported import; unseen external model not independently validated",
        ),
        imported_derivation=derivation,
    )

    return result
