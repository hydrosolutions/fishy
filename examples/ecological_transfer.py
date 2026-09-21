"""Synthetic complete-year donor transfer and presumptive floor, before local assembly.

Run ``uv run python examples/ecological_transfer.py``. Assumed acceptance is
explicit synthetic evidence, not a basin validation or adopted policy.
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
from fishy.daily_patterns import DailyPattern, annual_magnitude_product, import_pattern, pattern_product
from fishy.design_conditions import DesignClass
from fishy.ecological_transfer import (
    QualificationAspect,
    QualificationTest,
    TransferProfile,
    TransferRegister,
    transfer_ecological_regime,
    transfer_scope,
)
from fishy.evidence import (
    CheckFinding,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
)
from fishy.flows import FlowSample, Presence
from fishy.natural_baseline import ClassEcologicalRegime, EcologicalMemberCandidate, EcologicalRegimeMethod
from fishy.pattern_calendar import AccountingYear
from fishy.presumptive_floor import (
    PresumptiveProfile,
    SeasonalFraction,
    presumptive_floor,
    presumptive_reference_identity,
)
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
    HydrologicalProduct,
    HydrologicalProductKind,
    RatingSupport,
    ScientificAssessment,
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


def synthetic_acceptance(subject: HydrologicalProduct) -> ScientificAssessment:
    """Hypothetical external study; declared 1-unit maxima pass at equality.

    The frozen record precedes the supplied withheld diagnostics. This exercises
    permission plumbing, not scientific certification of these synthetic rivers.
    """
    contracts = ((EvidenceRequirement.DISTRIBUTION, "m3/s", "annual-mean-error"),)
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
        "stipulated synthetic sizing scenario, not empirical certification",
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


def synthetic_pattern(
    name: str, calendar: AccountingYear, design: DesignClass, values: tuple[Fraction, ...]
) -> DailyPattern:
    """Full imported calendar with separate content-bound annual and daily review."""
    location = Location(Reach(name, "v1", WaterBody(name, "v1")), CalculationSection(name, "v1"), "v1")
    provenance = Provenance(
        "synthetic transfer evidence",
        "hypothetical-transfer",
        name + "-member",
        "example-v1",
        "data-v1",
        "profile-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    mean = Flow(sum(values, Fraction()) / calendar.days)
    ref_calendar = AccountingYear(2001, calendar.start_month, calendar.utc_offset_minutes)
    reference = AnnualReference(
        (FlowSample(location, ref_calendar.interval, mean, Presence.PRESENT, provenance),),
        ref_calendar.interval,
        "assumed present climate",
        calendar.start_month,
        calendar.utc_offset_minutes,
        (),
        TrendTreatment.COMMON_CLIMATE,
        "stipulated synthetic common climate",
    )
    derivation = ImportedDerivation(
        "supplied complete daily hydrograph; annual mean=sum(Q)/days",
        "fixed scenario",
        "complete synthetic reference",
        ("mean checked exactly",),
        "stipulated shape and tail support",
        "hypothetical singleton flows, donor transfer uncertainty separate",
        "examples/ecological_transfer.py",
    )
    magnitude = import_annual_estimate(
        reference,
        ExceedanceProbability(Fraction(int(design), 100)),
        mean,
        estimator=AnnualEstimator.IMPORTED_STATIONARY,
        profile_version="synthetic-v1",
        provenance=provenance,
        derivation=derivation,
    )
    annual = synthetic_acceptance(
        annual_magnitude_product(magnitude, intended_use=UsePurpose.SIZING.value, purpose=UsePurpose.SIZING)
    )
    samples = tuple(
        FlowSample(
            location,
            Interval(calendar.interval.start + timedelta(days=i), calendar.interval.start + timedelta(days=i + 1)),
            Flow(v),
            Presence.PRESENT,
            provenance,
        )
        for i, v in enumerate(values)
    )
    pattern = import_pattern(
        magnitude,
        calendar,
        samples,
        derivation,
        intended_use=UsePurpose.SIZING.value,
        purpose=UsePurpose.SIZING,
        magnitude_assessment=annual,
    )
    daily = synthetic_acceptance(
        pattern_product(pattern, intended_use=UsePurpose.SIZING.value, purpose=UsePurpose.SIZING)
    )
    return replace(pattern, shape_assessment=daily, shape_evidence=daily.findings)


def synthetic_inputs(calendar: AccountingYear):
    donor_natural = tuple(
        synthetic_pattern("donor", calendar, c, (Fraction(4), Fraction(8)) + (Fraction(8),) * (calendar.days - 2))
        for c in DesignClass
    )
    recipient_natural = tuple(
        synthetic_pattern("recipient", calendar, c, (Fraction(6), Fraction(10)) + (Fraction(10),) * (calendar.days - 2))
        for c in DesignClass
    )
    donor = EcologicalMemberCandidate(
        donor_natural[0].location,
        calendar,
        donor_natural[0].magnitude.provenance,
        EcologicalRegimeMethod.STUDY,
        "pre-quality-study-v1",
        tuple(
            ClassEcologicalRegime(
                c, tuple(replace(s, value=Flow(s.value.value / 2)) for s in p.samples if s.value is not None)
            )
            for c, p in zip(DesignClass, donor_natural, strict=True)
        ),
        (donor_natural[0].magnitude.provenance,),
    )
    tests = []
    for aspect in QualificationAspect:
        criterion = ScientificCriterion(
            aspect.value,
            CriterionRole.MANDATORY,
            "absolute normalized synthetic mismatch",
            "fixed donor-recipient pair",
            "1",
            ErrorMeasure.VALUE,
            Aggregation.EACH_CASE,
            Comparison.AT_MOST,
            0.1,
            ("pair",),
            "Explicit illustrative 0.1 mismatch limit; not national policy",
        )
        observation = DiagnosticObservation(
            aspect.value,
            "pair",
            0.05,
            None,
            "1",
            criterion.formula,
            criterion.domain,
            "stipulated independent donor-recipient comparison",
        )
        tests.append(QualificationTest(aspect, criterion, (observation,)))
    profile = TransferProfile(
        "transfer-v1",
        donor.location,
        recipient_natural[0].location,
        datetime(2026, 9, 1, tzinfo=UTC),
        "Donor chosen by supplied regime and purpose evidence before calculation",
        tuple(tests),
        "Hypothetical donor uncertainty retained; no confidence guarantee",
        "Normalized-month means; compare leap-year variant separately",
    )
    findings = EvidenceFindings(
        transfer_scope(donor, donor_natural, recipient_natural, profile),
        recipient_natural[0].magnitude.provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("Assumed accepted exact synthetic relationship, not site certification",),
    )
    return donor, donor_natural, recipient_natural, profile, findings, TransferRegister("register-v1", ())


def synthetic_transfer():
    return transfer_ecological_regime(
        *synthetic_inputs(AccountingYear(2023, 1, 0)), evaluated_at=datetime(2026, 9, 5, tzinfo=UTC)
    )


def main() -> None:
    result = synthetic_transfer()
    assert result.candidate is not None
    print(
        "Transferred pre-quality first days:",
        [str(s.value.value) for s in result.candidate.classes[0].samples[:2] if s.value is not None],
    )
    reference = result.recipient_natural[0]
    profile = PresumptiveProfile(
        "hypothetical-floor-v1",
        "recipient own P25 present-climate natural design reference",
        presumptive_reference_identity(reference),
        (
            SeasonalFraction("first-season", 0, 180, Fraction(1, 5)),
            SeasonalFraction("second-season", 180, reference.calendar.days, Fraction(1, 4)),
        ),
        "Explicit hypothetical seasonal fractions; not adopted national values",
        "limited-evidence floor; uncertainty retained from reference",
    )
    floor = presumptive_floor(reference, profile)
    print("Base floor first day:", floor.samples[0].value)
    print("Missing reference:", presumptive_floor(None, profile).checks.finding.value)
    print("Local quality/receptors/floor checks still required. No new obligation from a floor-only output.")


if __name__ == "__main__":
    main()
