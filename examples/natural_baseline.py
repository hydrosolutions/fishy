"""SyntheticNaturalEvidence → PreQualityBaseline demonstration.

Run with ``uv run python examples/natural_baseline.py``. All evidence below is
explicit hypothetical support. None certifies an actual river or adopts policy.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

from fishy.annual_statistics import (
    AnnualEstimator,
    AnnualReference,
    ExceedanceProbability,
    ImportedDerivation,
    TrendTreatment,
    import_annual_estimate,
)
from fishy.daily_patterns import (
    DailyReferenceYear,
    annual_magnitude_product,
    import_pattern,
    pattern_product,
)
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Computability,
    CorrectionState,
    Disclosure,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
)
from fishy.flows import FlowSample, Presence
from fishy.natural_baseline import RecordedMinimum, baseline_family, recorded_minimum_product
from fishy.pattern_calendar import AccountingYear
from fishy.quantities import Flow
from fishy.scientific_acceptance import (
    AcceptanceRecord,
    Aggregation,
    ClimateTreatment,
    Comparison,
    CriterionRole,
    DailyDerivation,
    DiagnosticObservation,
    ErrorMeasure,
    EvidenceItem,
    EvidenceRequirement,
    HydrologicalProductKind,
    RatingSupport,
    ScientificCriterion,
    ScientificEvidence,
    UsePurpose,
    ValidationEvidence,
    ValidationMethod,
    assess_scientific_use,
    minimum_evidence,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

PROVENANCE = Provenance(
    "synthetic-record",
    "present",
    "natural-v1",
    "test-v1",
    "test-v1",
    "test-v1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
    ReferenceKind.PRESENT_CLIMATE_NATURAL,
)


def synthetic_acceptance(subject):
    """Hypothetical external study; declared 1-unit maxima pass at equality.

    The frozen record precedes the supplied withheld diagnostics. This exercises
    permission plumbing, not scientific certification of these synthetic rivers.
    """
    contracts = ((EvidenceRequirement.DISTRIBUTION, "m3/s", "annual-mean-error"),)
    if subject.kind is HydrologicalProductKind.RECORDED_MINIMUM:
        contracts = ((EvidenceRequirement.UNCERTAINTY, "m3/s", "supported-record-minimum-uncertainty-width"),)
    if subject.kind is HydrologicalProductKind.DAILY_PATTERN:
        contracts = (
            (EvidenceRequirement.SEASONAL_SHARES, "percent", "season-volume/annual-volume*100"),
            (EvidenceRequirement.TIMING, "days", "first-half-volume-time-nonwrapping"),
            (EvidenceRequirement.MINIMA, "m3/s", "minimum-complete-seven-day-mean"),
            (EvidenceRequirement.SPELLS, "days", "longest-strict-below-fixed-threshold"),
        )
    cases = ("heldout-climate-2010", "heldout-climate-2011")
    criteria = tuple(
        ScientificCriterion(
            requirement.value,
            CriterionRole.MANDATORY,
            formula,
            "synthetic withheld year",
            units,
            ErrorMeasure.ABSOLUTE,
            Aggregation.EACH_CASE,
            Comparison.AT_MOST,
            1.0,
            cases,
            "hypothetical test distinction of one unit, not a policy threshold",
            requirement,
        )
        for requirement, units, formula in contracts
    )
    record = AcceptanceRecord(
        subject,
        "synthetic-acceptance-v1",
        "preparer",
        "independent-reviewer",
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 4, tzinfo=UTC),
        criteria,
        "synthetic sampling and rating uncertainty with declared coverage",
        ("structural alternatives",),
        "synthetic screening only",
        (subject.scope.intended_use,),
        (),
        "new independent evidence required",
    )
    observations = tuple(
        DiagnosticObservation(
            c.criterion_id,
            case,
            1.0,
            0.0,
            c.units,
            c.formula,
            c.domain,
            "hypothetical withheld independent diagnostics",
        )
        for c in record.criteria
        for case in cases
    )
    validation = ValidationEvidence(
        ValidationMethod.WITHHELD,
        ("training-climate-2000",),
        cases,
        (),
        (),
        ("training-case",),
        cases,
        ("training-climate-2000",),
        cases,
        ("heldout-donor",),
        ("shared-rating-error",),
        datetime(2026, 9, 3, tzinfo=UTC),
        "caller-owned whole climate-year holdouts",
    )
    items = tuple(
        EvidenceItem(
            requirement,
            CheckFinding.PASS,
            "synthetic external study",
            "explicit hypothetical supported finding; not empirical site certification",
        )
        for requirement in minimum_evidence(subject, DailyDerivation.NATIVE)
    )
    evidence = ScientificEvidence(
        subject,
        record.profile_version,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        OfficialAdmissibility.PENDING,
        items,
        observations,
        validation,
        RatingSupport.WITHIN_RANGE,
        ClimateTreatment.COMMON_BASIS,
        DailyDerivation.NATIVE,
        frozen_record=record,
    )
    assessment = assess_scientific_use(record, evidence)
    assert assessment.findings.scientific_adequacy is ScientificAdequacy.ACCEPTED
    assert assessment.acceptance_for(subject).finding is CheckFinding.PASS
    assert all(c.actual == c.criterion.limit == 1.0 for c in assessment.comparisons)
    return assessment


DEFAULT_CALENDAR = AccountingYear(2024, 1, 0)


def accepted_family(
    calendar=DEFAULT_CALENDAR, *, minimum=1, magnitudes=(10, 8, 6, 4, 2), shapes=None, purpose=UsePurpose.SIZING
):
    """Complete supported hypothetical products, each accepted at its exact identity."""
    source_calendar = AccountingYear(2019, 1, 0)
    loc = Location(Reach("receiver", "v1", WaterBody("water", "v1")), CalculationSection("receiver", "v1"), "v1")
    samples = tuple(
        FlowSample(
            loc,
            Interval(
                source_calendar.interval.start + timedelta(days=i),
                source_calendar.interval.start + timedelta(days=i + 1),
            ),
            Flow(minimum),
            Presence.PRESENT,
            PROVENANCE,
        )
        for i in range(source_calendar.days)
    )
    source = DailyReferenceYear(
        source_calendar, samples, "synthetic-source-2019", CheckSummary((Check("source", CheckFinding.PASS),))
    )
    reference = AnnualReference(
        (FlowSample(loc, source_calendar.interval, source.annual_mean, Presence.PRESENT, PROVENANCE),),
        source_calendar.interval,
        "synthetic-present-climate",
        1,
        0,
        (),
        TrendTreatment.COMMON_CLIMATE,
        "stipulated scenario basis",
    )
    derivation = ImportedDerivation(
        "Q(P)=supplied scenario",
        "fixed fixture",
        "complete synthetic record",
        ("explicit independent hypothetical support",),
        "rare-year transfer assumed",
        "fixed hypothetical values",
        "U4",
    )
    patterns = []
    for percent, magnitude in zip((50, 75, 90, 97, 99), magnitudes, strict=True):
        annual = import_annual_estimate(
            reference,
            ExceedanceProbability(Fraction(percent, 100)),
            Flow(magnitude),
            estimator=AnnualEstimator.IMPORTED_STATIONARY,
            profile_version="U4-v1",
            provenance=PROVENANCE,
            derivation=derivation,
        )
        assessment = synthetic_acceptance(annual_magnitude_product(annual, intended_use=purpose.value, purpose=purpose))
        shape = (Fraction(1),) * calendar.days if shapes is None else shapes[percent]
        samples = tuple(
            FlowSample(
                reference.location,
                Interval(calendar.interval.start + timedelta(days=i), calendar.interval.start + timedelta(days=i + 1)),
                Flow(magnitude * factor),
                Presence.PRESENT,
                PROVENANCE,
            )
            for i, factor in enumerate(shape)
        )
        candidate = import_pattern(
            annual,
            calendar,
            samples,
            derivation,
            intended_use=purpose.value,
            purpose=purpose,
            magnitude_assessment=assessment,
        )
        shape_assessment = synthetic_acceptance(pattern_product(candidate, intended_use=purpose.value, purpose=purpose))
        patterns.append(
            import_pattern(
                annual,
                calendar,
                samples,
                derivation,
                intended_use=purpose.value,
                purpose=purpose,
                magnitude_assessment=assessment,
                shape_assessment=shape_assessment,
            )
        )
    record = RecordedMinimum(
        reference,
        (source,),
        "complete supported synthetic daily record; no missing values",
        "fixed hypothetical values",
    )
    record = replace(
        record,
        assessment=synthetic_acceptance(recorded_minimum_product(record, intended_use=purpose.value, purpose=purpose)),
    )
    return tuple(patterns), record


def main():
    patterns, record = accepted_family()
    result = baseline_family(patterns, record, provenance=PROVENANCE, profile_version="synthetic-U4-v1")
    assert result.candidate is not None
    print(
        {
            c.design.value: float(c.samples[0].value.value)
            for c in result.candidate.classes
            if c.samples[0].value is not None
        }
    )
    missing = baseline_family(patterns, None, provenance=PROVENANCE, profile_version="synthetic-U4-v1")
    print("Missing minimum:", missing.checks.finding.value)
    print("Final quality, receptor, duration and issuance gates remain separate.")


if __name__ == "__main__":
    main()
