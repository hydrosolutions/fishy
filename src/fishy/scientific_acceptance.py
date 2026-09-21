"""assess_scientific_use : AcceptanceRecord × ScientificEvidence → ScientificAssessment (pure).

Purpose-specific study gates for hydrological products. External reviewers supply
scientific evidence; this module checks identity, separation, completeness and
predeclared comparisons. It neither conducts validation nor grants official approval.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from statistics import fmean

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Computability,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    Provenance,
    ScientificAdequacy,
    UseRestriction,
    permitted_use,
)
from fishy.quantities import Flow
from fishy.spatial import Location
from fishy.time import Interval

DESIGN_PATTERN_DEVELOPMENT_LIMITATION = (
    "All 21 dry held-out cases in the two-US-record, 50-year-training comparison "
    "overestimated the seven-day minimum. Mean shape error improved against the "
    "calendar benchmark in four station-period groups; longer training improved "
    "three, not all four. Correlated development cases are not naturalised Uzbek "
    "evidence or untouched independent rare-tail validation; no correction factor "
    "or universal tolerance follows."
)


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty text required")


def _tuple(values: tuple, kind: type) -> None:
    if not isinstance(values, tuple) or any(not isinstance(v, kind) for v in values):
        raise TypeError(f"immutable tuple of {kind.__name__} required")


def _enum(value: object, kind: type) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"{kind.__name__} required")


def _time(value: datetime) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("timezone-aware date required")


class HydrologicalProductKind(StrEnum):
    ANNUAL_MAGNITUDE = "annual_magnitude"
    DAILY_PATTERN = "daily_pattern"
    DURATION_MINIMUM = "duration_minimum"
    RARE_TAIL = "rare_tail"
    COARSE_STATISTIC = "coarse_statistic"


class TemporalResolution(StrEnum):
    ANNUAL = "annual"
    DAILY = "daily"
    DEKADAL = "dekadal"


class UsePurpose(StrEnum):
    SCREENING = "screening"
    SIZING = "obligation sizing"


@dataclass(frozen=True)
class HydrologicalProduct:
    """Exact scientific subject, including target and production identity."""

    scope: EvidenceScope
    provenance: Provenance
    kind: HydrologicalProductKind
    statistic_name: str
    units: str
    calendar: str
    resolution: TemporalResolution
    purpose: UsePurpose
    target_probability: float | None
    duration_days: int | None
    location: Location
    climate_basis: str
    population: str
    reference_identity: str
    result_identity: str
    result_value: Flow | None
    intervals: tuple[Interval, ...] = ()

    def __post_init__(self) -> None:
        for value, kind in (
            (self.scope, EvidenceScope),
            (self.provenance, Provenance),
            (self.kind, HydrologicalProductKind),
            (self.resolution, TemporalResolution),
            (self.purpose, UsePurpose),
        ):
            _enum(value, kind)
        _enum(self.location, Location)
        if self.scope.reach != self.location.reach.identifier:
            raise ValueError("scope and physical location reach differ")
        if self.result_value is not None:
            _enum(self.result_value, Flow)
        for value in (
            self.statistic_name,
            self.units,
            self.calendar,
            self.climate_basis,
            self.population,
            self.reference_identity,
            self.result_identity,
        ):
            _text(value)
        if self.units != "m3/s":
            raise ValueError("hydrological discharge products require m3/s")
        if self.scope.member != self.provenance.reference_member:
            raise ValueError("product and provenance members differ")
        if self.target_probability is not None and (
            isinstance(self.target_probability, bool)
            or not isfinite(self.target_probability)
            or not 0 < self.target_probability < 1
        ):
            raise ValueError("target exceedance must be in (0, 1)")
        if self.duration_days is not None and (type(self.duration_days) is not int or self.duration_days < 1):
            raise ValueError("duration must be positive integer days")
        if self.kind is HydrologicalProductKind.DURATION_MINIMUM and self.duration_days is None:
            raise ValueError("minimum population needs duration")
        if (
            self.kind in (HydrologicalProductKind.DAILY_PATTERN, HydrologicalProductKind.RARE_TAIL)
            and self.target_probability is None
        ):
            raise ValueError("target probability required")
        _tuple(self.intervals, Interval)
        if any(a.end > z.start for a, z in zip(self.intervals, self.intervals[1:], strict=False)):
            raise ValueError("intervals must be ordered and nonoverlapping")
        if any(i.start < self.scope.period.start or i.end > self.scope.period.end for i in self.intervals):
            raise ValueError("interval outside product period")
        if self.resolution is TemporalResolution.DEKADAL:
            if self.kind not in (HydrologicalProductKind.COARSE_STATISTIC, HydrologicalProductKind.ANNUAL_MAGNITUDE):
                raise ValueError("dekadal support cannot be a daily or duration extreme")
            name = self.statistic_name.lower().replace(" ", "")
            if "q347" in name or "daily" in name or "q95" in name:
                raise ValueError("dekadal statistic must not be labelled Q347 or daily Q95")
            if not self.intervals:
                raise ValueError("dekadal product must retain actual intervals")
            if self.kind is HydrologicalProductKind.COARSE_STATISTIC and "dekadal" not in name:
                raise ValueError("coarse statistic must retain its dekadal name")
        if self.kind is HydrologicalProductKind.DAILY_PATTERN and self.resolution is not TemporalResolution.DAILY:
            raise ValueError("daily pattern needs daily resolution")


class EvidenceRequirement(StrEnum):
    SOURCE = "source_requirements"
    POPULATION = "population_and_accepted_years"
    ZEROS = "zeros_and_intermittency"
    RATING = "rating_history_and_range"
    PERSISTENCE = "persistence_and_shared_errors"
    ARTEFACTS = "artefact_checks"
    CLIMATE = "climate_treatment"
    DISTRIBUTION = "empirical_fitted_behaviour"
    TAIL_SENSITIVITY = "target_tail_sensitivity"
    TARGET_DISTANCE = "target_distance_from_support"
    UNCERTAINTY = "uncertainty_and_coverage"
    APPLICABILITY = "applicability"
    PREDICTIVE = "predictive_or_regional_evidence"
    ANNUAL_SEPARATION = "annual_magnitude_separate_from_shape"
    SEASONAL_SHARES = "seasonal_share_errors"
    TIMING = "nonwrapping_timing_errors"
    MINIMA = "signed_and_absolute_duration_minimum_errors"
    SPELLS = "strict_below_spell_errors"
    CALENDAR = "calendar_alignment_effects"
    BENCHMARK = "same_case_calendar_benchmark"
    DONOR_SENSITIVITY = "donor_reference_sensitivity"
    TARGET_TRANSFER = "requested_target_transfer_and_uncertainty"
    RARE_TAIL = "independent_rare_tail_applicability"
    COLOCATED_DAILY = "withheld_colocated_daily_validation"
    DAILY_LOW_TAIL = "daily_disaggregation_low_tail"
    DAILY_SPELLS = "daily_disaggregation_spells"
    PROPAGATED_UNCERTAINTY = "disaggregation_propagated_uncertainty"


_COMMON = (
    EvidenceRequirement.SOURCE,
    EvidenceRequirement.POPULATION,
    EvidenceRequirement.ZEROS,
    EvidenceRequirement.RATING,
    EvidenceRequirement.PERSISTENCE,
    EvidenceRequirement.ARTEFACTS,
    EvidenceRequirement.CLIMATE,
    EvidenceRequirement.UNCERTAINTY,
    EvidenceRequirement.APPLICABILITY,
)
_ANNUAL = (
    EvidenceRequirement.DISTRIBUTION,
    EvidenceRequirement.TAIL_SENSITIVITY,
    EvidenceRequirement.TARGET_DISTANCE,
    EvidenceRequirement.PREDICTIVE,
)
_DAILY = (
    EvidenceRequirement.ANNUAL_SEPARATION,
    EvidenceRequirement.SEASONAL_SHARES,
    EvidenceRequirement.TIMING,
    EvidenceRequirement.MINIMA,
    EvidenceRequirement.SPELLS,
    EvidenceRequirement.CALENDAR,
    EvidenceRequirement.BENCHMARK,
    EvidenceRequirement.DONOR_SENSITIVITY,
    EvidenceRequirement.TARGET_TRANSFER,
)


class RatingSupport(StrEnum):
    WITHIN_RANGE = "within_calibrated_range"
    OUTSIDE_RANGE = "outside_calibrated_range"
    UNKNOWN = "unknown"


class ClimateTreatment(StrEnum):
    COMMON_BASIS = "supported_common_basis"
    TREATED = "supported_treatment"
    UNTREATED_TREND = "untreated_genuine_trend"
    UNKNOWN = "unknown"


class DailyDerivation(StrEnum):
    NATIVE = "native_daily_or_not_daily"
    DISAGGREGATED = "disaggregated"


class ValidationMethod(StrEnum):
    WITHHELD = "withheld_complete_years"
    NESTED = "nested_withheld_complete_years"
    REGIONAL = "supported_regional_evidence"


@dataclass(frozen=True)
class ValidationEvidence:
    method: ValidationMethod
    training_clusters: tuple[str, ...]
    validation_clusters: tuple[str, ...]
    excluded_clusters: tuple[str, ...]
    previously_exposed_clusters: tuple[str, ...]
    training_cases: tuple[str, ...]
    validation_cases: tuple[str, ...]
    benchmark_training_clusters: tuple[str, ...]
    benchmark_cases: tuple[str, ...]
    donor_groups: tuple[str, ...]
    shared_inputs: tuple[str, ...]
    evaluated_at: datetime
    procedure: str

    def __post_init__(self) -> None:
        _enum(self.method, ValidationMethod)
        _time(self.evaluated_at)
        _text(self.procedure)
        for name in (
            "training_clusters",
            "validation_clusters",
            "excluded_clusters",
            "previously_exposed_clusters",
            "training_cases",
            "validation_cases",
            "benchmark_training_clusters",
            "benchmark_cases",
            "donor_groups",
            "shared_inputs",
        ):
            values = getattr(self, name)
            _tuple(values, str)
            for value in values:
                _text(value)
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate {name}")


@dataclass(frozen=True)
class EvidenceItem:
    requirement: EvidenceRequirement
    finding: CheckFinding
    source: str
    explanation: str

    def __post_init__(self) -> None:
        _enum(self.requirement, EvidenceRequirement)
        _enum(self.finding, CheckFinding)
        _text(self.source)
        _text(self.explanation)


class CriterionRole(StrEnum):
    MANDATORY = "mandatory"
    ADVISORY = "advisory"


class ErrorMeasure(StrEnum):
    SIGNED = "candidate_minus_reference"
    ABSOLUTE = "absolute_candidate_minus_reference"
    RELATIVE = "relative_candidate_minus_reference"
    VALUE = "candidate_value"


class Aggregation(StrEnum):
    EACH_CASE = "each_case"
    MAXIMUM = "maximum"
    MEAN = "arithmetic_mean"
    MINIMUM = "minimum"


class Comparison(StrEnum):
    AT_MOST = "<="
    LESS_THAN = "<"
    AT_LEAST = ">="
    GREATER_THAN = ">"


@dataclass(frozen=True)
class ScientificCriterion:
    criterion_id: str
    role: CriterionRole
    formula: str
    domain: str
    units: str
    measure: ErrorMeasure
    aggregation: Aggregation
    comparison: Comparison
    limit: float
    cases: tuple[str, ...]
    justification: str
    requirement: EvidenceRequirement | None = None

    @property
    def comparison_units(self) -> str:
        return "1" if self.measure is ErrorMeasure.RELATIVE else self.units

    def __post_init__(self) -> None:
        if self.requirement is not None:
            _enum(self.requirement, EvidenceRequirement)
        for value in (self.criterion_id, self.formula, self.domain, self.units, self.justification):
            _text(value)
        for value, kind in (
            (self.role, CriterionRole),
            (self.measure, ErrorMeasure),
            (self.aggregation, Aggregation),
            (self.comparison, Comparison),
        ):
            _enum(value, kind)
        if isinstance(self.limit, bool) or not isfinite(self.limit):
            raise ValueError("finite criterion limit required")
        _tuple(self.cases, str)
        if not self.cases or len(set(self.cases)) != len(self.cases):
            raise ValueError("nonempty unique expected cases required")
        for case in self.cases:
            _text(case)


@dataclass(frozen=True)
class DiagnosticObservation:
    criterion_id: str
    case: str
    candidate: float | None
    reference: float | None
    units: str
    formula: str
    domain: str
    source: str

    def __post_init__(self) -> None:
        for value in (self.criterion_id, self.case, self.units, self.formula, self.domain, self.source):
            _text(value)
        for value in (self.candidate, self.reference):
            if value is not None and (isinstance(value, bool) or not isfinite(value)):
                raise ValueError("diagnostic must be finite or explicitly undefined")

    @property
    def signed_error(self) -> float | None:
        return None if self.candidate is None or self.reference is None else self.candidate - self.reference

    @property
    def absolute_error(self) -> float | None:
        return None if self.signed_error is None else abs(self.signed_error)

    @property
    def relative_error(self) -> float | None:
        return None if self.reference in (None, 0) or self.signed_error is None else self.signed_error / self.reference


@dataclass(frozen=True)
class AcceptanceRecord:
    product: HydrologicalProduct
    profile_version: str
    preparer: str
    independent_reviewer: str
    frozen_at: datetime
    reviewed_at: datetime
    criteria: tuple[ScientificCriterion, ...]
    uncertainty_scope: str
    omitted_error_sources: tuple[str, ...]
    applicability: str
    permitted_uses: tuple[str, ...]
    restrictions: tuple[UseRestriction, ...]
    restriction_removal_evidence: str
    indicative_basis: str | None = None
    previous_profile: str | None = None
    revision_reason: str | None = None
    previous_result: str | None = None

    def __post_init__(self) -> None:
        _enum(self.product, HydrologicalProduct)
        for value in (
            self.profile_version,
            self.preparer,
            self.independent_reviewer,
            self.uncertainty_scope,
            self.applicability,
            self.restriction_removal_evidence,
        ):
            _text(value)
        if self.preparer.strip().casefold() == self.independent_reviewer.strip().casefold():
            raise ValueError("preparer and independent reviewer must differ")
        _time(self.frozen_at)
        _time(self.reviewed_at)
        if self.reviewed_at < self.frozen_at:
            raise ValueError("review precedes frozen record")
        _tuple(self.criteria, ScientificCriterion)
        if len({c.criterion_id for c in self.criteria}) != len(self.criteria):
            raise ValueError("duplicate criterion IDs")
        _tuple(self.restrictions, UseRestriction)
        for values in (self.omitted_error_sources, self.permitted_uses):
            _tuple(values, str)
            for value in values:
                _text(value)
        if self.indicative_basis is not None:
            _text(self.indicative_basis)
        revision = (self.previous_profile, self.revision_reason, self.previous_result)
        if any(v is not None for v in revision):
            if not all(v is not None for v in revision):
                raise ValueError("revision needs previous profile, result and reason")
            for value in revision:
                assert value is not None
                _text(value)
            if self.previous_profile == self.profile_version:
                raise ValueError("revision requires new profile version")


@dataclass(frozen=True)
class ScientificEvidence:
    product: HydrologicalProduct
    profile_version: str
    computability: Computability
    numerical_validity: NumericalValidity
    disclosure: Disclosure
    official_admissibility: OfficialAdmissibility
    items: tuple[EvidenceItem, ...]
    observations: tuple[DiagnosticObservation, ...]
    validation: ValidationEvidence | None
    rating: RatingSupport
    climate: ClimateTreatment
    daily_derivation: DailyDerivation
    frozen_record: AcceptanceRecord
    restrictions: tuple[UseRestriction, ...] = ()

    def __post_init__(self) -> None:
        for value, kind in (
            (self.product, HydrologicalProduct),
            (self.computability, Computability),
            (self.numerical_validity, NumericalValidity),
            (self.disclosure, Disclosure),
            (self.official_admissibility, OfficialAdmissibility),
            (self.rating, RatingSupport),
            (self.climate, ClimateTreatment),
            (self.daily_derivation, DailyDerivation),
        ):
            _enum(value, kind)
        _text(self.profile_version)
        _enum(self.frozen_record, AcceptanceRecord)
        _tuple(self.items, EvidenceItem)
        _tuple(self.observations, DiagnosticObservation)
        _tuple(self.restrictions, UseRestriction)
        if self.validation is not None:
            _enum(self.validation, ValidationEvidence)
        if len({i.requirement for i in self.items}) != len(self.items):
            raise ValueError("duplicate evidence requirement")
        if len({(o.criterion_id, o.case) for o in self.observations}) != len(self.observations):
            raise ValueError("duplicate diagnostic observation")


@dataclass(frozen=True)
class CriterionComparison:
    criterion: ScientificCriterion
    case: str | None
    observations: tuple[DiagnosticObservation, ...]
    actual: float | None
    finding: CheckFinding


@dataclass(frozen=True)
class ScientificAssessment:
    record: AcceptanceRecord
    evidence: ScientificEvidence
    findings: EvidenceFindings
    checks: CheckSummary
    comparisons: tuple[CriterionComparison, ...]

    def acceptance_for(self, product: HydrologicalProduct) -> Check:
        """Permission never transfers to another value target, provenance or purpose."""
        if product != self.record.product:
            return Check("scientific_use", CheckFinding.UNKNOWN, ("exact hydrological product differs",))
        # Public frozen dataclasses may be reconstructed with dataclasses.replace.
        # Re-evaluate source inputs, never trust a replaced output label or summary.
        evaluated = assess_scientific_use(self.record, self.evidence)
        return permitted_use(evaluated.findings, product.scope)


def minimum_evidence(product: HydrologicalProduct, derivation: DailyDerivation) -> tuple[EvidenceRequirement, ...]:
    """Return non-waivable requirements; this is not a configurable tolerance table."""
    required = _COMMON
    if product.kind in (
        HydrologicalProductKind.ANNUAL_MAGNITUDE,
        HydrologicalProductKind.DURATION_MINIMUM,
        HydrologicalProductKind.RARE_TAIL,
    ):
        required += _ANNUAL
    if product.kind is HydrologicalProductKind.DAILY_PATTERN:
        required += _DAILY
    if product.kind is HydrologicalProductKind.RARE_TAIL or (
        product.target_probability is not None and product.target_probability >= 0.99
    ):
        required += (EvidenceRequirement.RARE_TAIL,)
    if derivation is DailyDerivation.DISAGGREGATED and (
        product.resolution is TemporalResolution.DAILY
        or product.kind in (HydrologicalProductKind.DURATION_MINIMUM, HydrologicalProductKind.RARE_TAIL)
    ):
        required += (
            EvidenceRequirement.COLOCATED_DAILY,
            EvidenceRequirement.DAILY_LOW_TAIL,
            EvidenceRequirement.DAILY_SPELLS,
            EvidenceRequirement.PROPAGATED_UNCERTAINTY,
        )
    return required


def _compare(value: float | None, criterion: ScientificCriterion) -> CheckFinding:
    if value is None:
        return CheckFinding.UNKNOWN
    match criterion.comparison:
        case Comparison.AT_MOST:
            passes = value <= criterion.limit
        case Comparison.LESS_THAN:
            passes = value < criterion.limit
        case Comparison.AT_LEAST:
            passes = value >= criterion.limit
        case Comparison.GREATER_THAN:
            passes = value > criterion.limit
    return CheckFinding.PASS if passes else CheckFinding.FAIL


def _measure(observation: DiagnosticObservation, measure: ErrorMeasure) -> float | None:
    match measure:
        case ErrorMeasure.VALUE:
            return observation.candidate
        case ErrorMeasure.SIGNED:
            return observation.signed_error
        case ErrorMeasure.ABSOLUTE:
            return observation.absolute_error
        case ErrorMeasure.RELATIVE:
            return observation.relative_error


def compare_criterion(
    criterion: ScientificCriterion, observations: tuple[DiagnosticObservation, ...]
) -> tuple[CriterionComparison, ...]:
    """Compute declared errors and aggregation; undefined/missing cases cannot pass."""
    _tuple(observations, DiagnosticObservation)
    if len({o.case for o in observations}) != len(observations):
        raise ValueError("duplicate cases")
    for o in observations:
        if (
            o.criterion_id != criterion.criterion_id
            or o.case not in criterion.cases
            or (o.units, o.formula, o.domain) != (criterion.units, criterion.formula, criterion.domain)
        ):
            raise ValueError("diagnostic does not match frozen criterion")
    by_case = {o.case: o for o in observations}
    values = tuple(_measure(by_case[c], criterion.measure) if c in by_case else None for c in criterion.cases)
    if criterion.aggregation is Aggregation.EACH_CASE:
        return tuple(
            CriterionComparison(
                criterion, case, (by_case[case],) if case in by_case else (), value, _compare(value, criterion)
            )
            for case, value in zip(criterion.cases, values, strict=True)
        )
    actual = None
    if all(value is not None for value in values):
        complete = tuple(value for value in values if value is not None)
        if criterion.aggregation is Aggregation.MAXIMUM:
            actual = max(complete)
        elif criterion.aggregation is Aggregation.MINIMUM:
            actual = min(complete)
        else:
            actual = fmean(complete)
    finding = _compare(actual, criterion)
    if (
        actual is None
        and (
            (
                criterion.aggregation is Aggregation.MAXIMUM
                and criterion.comparison in (Comparison.AT_MOST, Comparison.LESS_THAN)
            )
            or (
                criterion.aggregation is Aggregation.MINIMUM
                and criterion.comparison in (Comparison.AT_LEAST, Comparison.GREATER_THAN)
            )
        )
        and any(_compare(value, criterion) is CheckFinding.FAIL for value in values if value is not None)
    ):
        finding = CheckFinding.FAIL
    return (CriterionComparison(criterion, None, observations, actual, finding),)


def _validation_checks(record: AcceptanceRecord, evidence: ScientificEvidence) -> tuple[Check, ...]:
    validation = evidence.validation
    if validation is None:
        return (Check("validation", CheckFinding.UNKNOWN, ("independent validation basis missing",)),)
    checks = []

    def add(name: str, passed: bool, reason: str) -> None:
        checks.append(Check(name, CheckFinding.PASS if passed else CheckFinding.FAIL, () if passed else (reason,)))

    add(
        "frozen_before_validation",
        record.frozen_at <= validation.evaluated_at <= record.reviewed_at,
        "validation must follow freeze and precede review",
    )
    withheld = set(validation.validation_clusters)
    contamination = (
        set(validation.training_clusters)
        | set(validation.excluded_clusters)
        | set(validation.previously_exposed_clusters)
    ) & withheld
    add(
        "climate_cluster_separation",
        not contamination,
        "withheld climate clusters overlap training/excluded/exposed evidence",
    )
    add(
        "case_separation",
        not set(validation.training_cases) & set(validation.validation_cases),
        "same case used for preparation and validation",
    )
    if validation.method is not ValidationMethod.REGIONAL:
        add(
            "withheld_coverage",
            bool(withheld and validation.validation_cases),
            "withheld complete-year evidence missing",
        )
    if validation.method is not ValidationMethod.REGIONAL:
        add(
            "diagnostic_validation_cases",
            all(
                set(c.cases) == set(validation.validation_cases)
                for c in record.criteria
                if c.role is CriterionRole.MANDATORY
            ),
            "mandatory diagnostic cases must match declared withheld cases",
        )
    if record.previous_profile is not None:
        add(
            "revision_exposure_disclosed",
            bool(validation.previously_exposed_clusters),
            "revised criteria require exposed clusters and new or nested withheld evidence",
        )
    if record.product.kind is HydrologicalProductKind.DAILY_PATTERN:
        add(
            "daily_withheld_years",
            validation.method is not ValidationMethod.REGIONAL,
            "daily pattern requires held-out complete years",
        )
        add(
            "benchmark_separation",
            not withheld & set(validation.benchmark_training_clusters),
            "benchmark trained on validation climate clusters",
        )
        add(
            "benchmark_same_cases",
            bool(validation.validation_cases) and set(validation.benchmark_cases) == set(validation.validation_cases),
            "benchmark cases differ from validation",
        )
    return tuple(checks)


def assess_scientific_use(record: AcceptanceRecord, evidence: ScientificEvidence) -> ScientificAssessment:
    """Evaluate supplied frozen study evidence without choosing scientific limits."""
    if record.product != evidence.product or record.profile_version != evidence.profile_version:
        raise ValueError("evidence must match exact product and frozen profile")
    criteria = {c.criterion_id: c for c in record.criteria}
    if any(o.criterion_id not in criteria for o in evidence.observations):
        raise ValueError("undeclared diagnostic criterion")
    checks = [
        Check(
            "frozen_record_identity",
            CheckFinding.PASS if evidence.frozen_record == record else CheckFinding.FAIL,
            ()
            if evidence.frozen_record == record
            else ("evidence was evaluated under a different frozen acceptance record",),
        )
    ]
    for name, value, passing, failing in (
        ("computability", evidence.computability, Computability.COMPUTABLE, Computability.NOT_COMPUTABLE),
        ("numerical_validity", evidence.numerical_validity, NumericalValidity.VALID, NumericalValidity.INVALID),
        ("disclosure", evidence.disclosure, Disclosure.COMPLETE, Disclosure.INCOMPLETE),
    ):
        finding = (
            CheckFinding.PASS if value is passing else CheckFinding.FAIL if value is failing else CheckFinding.UNKNOWN
        )
        checks.append(Check(name, finding, () if finding is CheckFinding.PASS else (str(value),)))
    if record.product.kind in (
        HydrologicalProductKind.ANNUAL_MAGNITUDE,
        HydrologicalProductKind.DURATION_MINIMUM,
        HydrologicalProductKind.RARE_TAIL,
    ):
        checks.append(
            Check(
                "scalar_result",
                CheckFinding.PASS if record.product.result_value is not None else CheckFinding.UNKNOWN,
                () if record.product.result_value is not None else ("declared scalar result missing",),
            )
        )
    mandatory = tuple(c for c in record.criteria if c.role is CriterionRole.MANDATORY)
    checks.append(
        Check(
            "acceptance_basis",
            CheckFinding.PASS if mandatory else CheckFinding.UNKNOWN,
            () if mandatory else ("acceptance basis missing",),
        )
    )
    items = {i.requirement: i for i in evidence.items}
    for requirement in minimum_evidence(record.product, evidence.daily_derivation):
        item = items.get(requirement)
        checks.append(
            Check(
                requirement.value,
                item.finding if item else CheckFinding.UNKNOWN,
                (item.explanation, item.source) if item else ("minimum product-specific evidence missing",),
            )
        )
    if record.product.kind is HydrologicalProductKind.DAILY_PATTERN:
        numeric_requirements = {
            EvidenceRequirement.SEASONAL_SHARES,
            EvidenceRequirement.TIMING,
            EvidenceRequirement.MINIMA,
            EvidenceRequirement.SPELLS,
        }
        covered = {criterion.requirement for criterion in mandatory}
        missing = numeric_requirements - covered
        checks.append(
            Check(
                "daily_numeric_criteria",
                CheckFinding.UNKNOWN if missing else CheckFinding.PASS,
                tuple(f"mandatory diagnostic limit missing: {requirement.value}" for requirement in sorted(missing)),
            )
        )
    comparisons = tuple(
        result
        for criterion in record.criteria
        for result in compare_criterion(
            criterion, tuple(o for o in evidence.observations if o.criterion_id == criterion.criterion_id)
        )
    )
    for i, comparison in enumerate(comparisons):
        if comparison.criterion.role is CriterionRole.MANDATORY or comparison.criterion.requirement in minimum_evidence(
            record.product, evidence.daily_derivation
        ):
            if comparison.criterion.aggregation is not Aggregation.EACH_CASE and comparison.actual is None:
                checks.append(
                    Check(
                        f"criterion_coverage:{comparison.criterion.criterion_id}",
                        CheckFinding.UNKNOWN,
                        ("aggregate diagnostic coverage incomplete or undefined",),
                    )
                )
            checks.append(
                Check(
                    f"criterion:{comparison.criterion.criterion_id}:{i}",
                    comparison.finding,
                    (
                        f"actual={comparison.actual}; {comparison.criterion.comparison.value} {comparison.criterion.limit} {comparison.criterion.comparison_units}",
                    ),
                )
            )
    checks.extend(_validation_checks(record, evidence))
    restrictions = record.restrictions + evidence.restrictions
    if evidence.rating is RatingSupport.OUTSIDE_RANGE:
        prohibited = (UsePurpose.SIZING.value,)
        if record.product.purpose is UsePurpose.SIZING:
            prohibited += (record.product.scope.intended_use,)
        restrictions += (UseRestriction("outside calibrated rating range", prohibited),)
    checks.append(
        Check(
            "rating_support",
            CheckFinding.UNKNOWN if evidence.rating is RatingSupport.UNKNOWN else CheckFinding.PASS,
            (evidence.rating.value,),
        )
    )
    climate = (
        CheckFinding.UNKNOWN
        if evidence.climate is ClimateTreatment.UNKNOWN
        else (CheckFinding.FAIL if evidence.climate is ClimateTreatment.UNTREATED_TREND else CheckFinding.PASS)
    )
    checks.append(Check("climate_basis", climate, (evidence.climate.value,)))
    if evidence.climate is ClimateTreatment.UNTREATED_TREND:
        restrictions += (
            UseRestriction(
                "untreated trend cannot support present-climate estimate", (record.product.scope.intended_use,)
            ),
        )
    prohibited_reasons = tuple(r.reason for r in restrictions if record.product.scope.intended_use in r.prohibited_uses)
    checks.append(
        Check(
            "use_permission",
            CheckFinding.FAIL
            if prohibited_reasons
            else CheckFinding.PASS
            if record.product.scope.intended_use in record.permitted_uses
            else CheckFinding.UNKNOWN,
            prohibited_reasons
            or (() if record.product.scope.intended_use in record.permitted_uses else ("use permission missing",)),
        )
    )
    if evidence.rating is RatingSupport.OUTSIDE_RANGE:
        checks.append(
            Check(
                "rating_indicative_basis",
                CheckFinding.PASS if record.indicative_basis else CheckFinding.UNKNOWN,
                () if record.indicative_basis else ("explicit supported indicative use required",),
            )
        )
    summary = CheckSummary(tuple(checks))
    adequacy = ScientificAdequacy.NOT_ACCEPTED
    if summary.finding is CheckFinding.PASS:
        adequacy = ScientificAdequacy.ACCEPTED_AS_INDICATIVE if record.indicative_basis else ScientificAdequacy.ACCEPTED
    reasons = tuple(
        reason for check in summary.checks if check.finding is not CheckFinding.PASS for reason in check.reasons
    )
    if record.indicative_basis:
        reasons += (record.indicative_basis,)
    findings = EvidenceFindings(
        record.product.scope,
        record.product.provenance,
        evidence.computability,
        evidence.numerical_validity,
        evidence.disclosure,
        adequacy,
        evidence.official_admissibility,
        reasons,
        restrictions,
    )
    return ScientificAssessment(record, evidence, findings, summary, comparisons)
