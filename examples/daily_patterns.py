"""daily_pattern_example : CompleteReferenceYears → ExploratoryDailyPatterns.

Run with ``uv run python examples/daily_patterns.py``. All records and study
settings are synthetic. They demonstrate calculations, not scientific acceptance.
"""

from dataclasses import replace
from datetime import timedelta
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
    AlignmentChoice,
    AlignmentSettings,
    AnalogueReference,
    DailyPattern,
    DailyReferenceYear,
    DonorEligibility,
    MembershipEstimator,
    PatternProfile,
    construct_pattern,
    import_pattern,
)
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    CorrectionState,
    ProductionMethod,
    Provenance,
    ReferenceKind,
)
from fishy.flows import FlowSample, Presence
from fishy.pattern_calendar import AccountingYear
from fishy.quantities import Flow
from fishy.scientific_acceptance import UsePurpose
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def _location(name: str) -> Location:
    return Location(Reach(name, "v1", WaterBody("synthetic-river", "v1")), CalculationSection(name, "v1"), "v1")


def _year(
    name: str, number: int, values: tuple[Fraction, ...], provenance: Provenance, quality: CheckSummary
) -> DailyReferenceYear:
    calendar = AccountingYear(number, 1, 0)
    samples = tuple(
        FlowSample(
            _location(name),
            Interval(calendar.interval.start + timedelta(days=i), calendar.interval.start + timedelta(days=i + 1)),
            Flow(value),
            Presence.PRESENT,
            provenance,
        )
        for i, value in enumerate(values)
    )
    return DailyReferenceYear(calendar, samples, str(number), quality)


def _reference(years: tuple[DailyReferenceYear, ...]) -> AnnualReference:
    return AnnualReference(
        tuple(
            FlowSample(y.location, y.calendar.interval, y.annual_mean, Presence.PRESENT, y.provenance) for y in years
        ),
        Interval(years[0].calendar.interval.start, years[-1].calendar.interval.end),
        "synthetic-common-climate",
        1,
        0,
        (),
        TrendTreatment.COMMON_CLIMATE,
        "Synthetic common-climate assumption for this arithmetic example only",
    )


def build_example() -> tuple[DailyPattern, DailyPattern, DailyPattern]:
    """Return computed, insufficient-support and imported numerical candidates."""
    provenance = Provenance(
        "synthetic-daily-pattern-example",
        "present",
        "natural-v1",
        "example-v1",
        "example-v1",
        "example-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    quality = CheckSummary((Check("synthetic-input-completeness", CheckFinding.PASS),))
    a = _year("a", 2019, (Fraction(1), Fraction(1), Fraction(2)) + (Fraction(),) * 362, provenance, quality)
    b = _year("b", 2019, (Fraction(20), Fraction(20)) + (Fraction(),) * 363, provenance, quality)
    pools = tuple(
        AnalogueReference(_reference((_year(name, 2018, (Fraction(1),) * 365, provenance, quality), dry)), (dry,))
        for name, dry in (("a", a), ("b", b))
    )
    # Full annual references include wet 2018, even though only dry 2019 is
    # supplied as a shape candidate. Both dry-year Weibull probabilities are 2/3.
    receiving_year = _year("receiver", 2019, (Fraction(8),) * 365, provenance, quality)
    target = ExceedanceProbability(Fraction(2, 3))
    magnitude = import_annual_estimate(
        _reference((receiving_year,)),
        target,
        Flow(8),
        estimator=AnnualEstimator.IMPORTED_STATIONARY,
        profile_version="synthetic-annual-v1",
        provenance=provenance,
        derivation=ImportedDerivation(
            "Q(P=2/3)=8 m3/s (supplied illustrative magnitude)",
            "No fitted parameters; fixed synthetic input",
            "Complete constant-8 synthetic receiving year 2019",
            ("Annual mean equals 8 m3/s",),
            "No scientific validation; illustrative arithmetic only",
            "No quantified uncertainty; not accepted for sizing",
            "examples/daily_patterns.py:build_example",
        ),
    )
    profile = PatternProfile(
        "synthetic-pattern-v1",
        target,
        Fraction(),
        "natural-v1",
        "present",
        "synthetic-common-climate",
        MembershipEstimator.EMPIRICAL,
        tuple(
            DonorEligibility(
                y.location, ("Synthetic matching seasonal regime, not field evidence",), quality, provenance
            )
            for y in (a, b)
        ),
        2,
        1,
        AlignmentSettings(AlignmentChoice.CALENDAR, 0, 365, Fraction()),
        "example-requires-independent-scientific-review",
        Interval(AccountingYear(2018, 1, 0).interval.start, AccountingYear(2019, 1, 0).interval.end),
    )
    calendar = AccountingYear(2023, 1, 0)
    candidate = construct_pattern(
        magnitude, calendar, pools, profile, intended_use="exploratory", purpose=UsePurpose.SCREENING
    )
    # Two synchronous donor years are still only one climate-year cluster.
    unsupported = construct_pattern(
        magnitude,
        calendar,
        pools,
        replace(profile, minimum_climate_clusters=2),
        intended_use="exploratory",
        purpose=UsePurpose.SCREENING,
    )
    imported = import_pattern(
        magnitude,
        calendar,
        candidate.samples,
        ImportedDerivation(
            "Q(day)=8*365*mean(normalized donor daily volumes)",
            "Equal weights for selected A/B years; no fitted daily parameters",
            "Two synthetic 2019 donor years; full 2018/2019 annual references",
            ("365 daily intervals; annual volume=252288000 m3",),
            "Daily shape and rare-tail acceptance not established",
            "No quantified uncertainty; not accepted for sizing",
            "examples/daily_patterns.py:build_example; calendar_average",
        ),
        intended_use="exploratory",
        purpose=UsePurpose.SCREENING,
    )
    return candidate, unsupported, imported


def main() -> None:
    candidate, unsupported, imported = build_example()
    assert candidate.volume is not None
    print(
        f"Selected years / climate clusters: {candidate.membership.source_count} / {candidate.membership.climate_cluster_count}"
    )
    print("Selected full-reference probabilities: " + ", ".join(str(c.probability.value) for c in candidate.selected))
    print(f"Receiving annual mean: {candidate.magnitude.value.value if candidate.magnitude.value else None} m3/s")
    print(f"Design-year volume: {candidate.volume.value} m3")
    print(f"Numerical support: {candidate.support.finding.value}")
    print(f"Scientific-use checks: {candidate.use_checks.finding.value}")
    print(f"Two-cluster requirement: {unsupported.support.finding.value}; numerical candidate retained")
    print(f"Imported schedule unchanged: {imported.samples == candidate.samples}")


if __name__ == "__main__":
    main()
