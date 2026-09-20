"""Supplied Kazakh illustration: InitialAllocation → BoundedSchedule × MonthlyAnnualReport.

Run: uv run python examples/supplied_kazakh_scenario.py
All settings and studies are synthetic. No calibration, legal certification or simulator.
Comparisons and presentation live here, outside the Fishy package.
"""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction

from fishy.basin import Basin, River
from fishy.design_conditions import DesignClass
from fishy.evidence import (
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
)
from fishy.flow_bounds import AnnualReferenceVolume, CorrectionOrder, DesignBounds, annual_bound_scope, correct_schedule
from fishy.flows import FlowSample, Presence
from fishy.kazakh_allocation import (
    AllocationRoute,
    AnnualQuantile,
    InitialAllocation,
    NaturalAnnualReference,
    NaturalExceedance,
    ObservationRoute,
    initial_allocation,
    shifted_class,
)
from fishy.kazakh_review import (
    BasinChange,
    ChangeState,
    StudyReview,
    assess_review,
    order179_applicability,
)
from fishy.quantities import Flow, SignedState, StateVariable, Volume
from fishy.seasonal_allocation import (
    ReportingIdentity,
    ScheduleStage,
    SeasonalShape,
    ShapeChoice,
    ShapeOrdinate,
    appendix1_report,
    seasonal_schedule,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.spawning import (
    BiologicalTiming,
    CoefficientInterpretation,
    EligibilityInterpretation,
    StarRelevance,
    TemporalBasis,
    coefficient_scope,
    spawning_schedule,
)
from fishy.time import Interval
from fishy.water_classification import (
    CellInterpretation,
    ClassificationObservation,
    Order111Profile,
    RangeMeaning,
    SourceValue,
    UseInterpretation,
    UseMapping,
    WaterClass,
    WaterScope,
    WaterUse,
    assess_order111,
    assess_order111_use,
    source_row,
)

LOCATION = Location(
    Reach("illustrative-reach", "v1", WaterBody("illustrative-body", "v1")),
    CalculationSection("illustrative-section", "v1"),
    "map-v1",
)
IDENTITY = ReportingIdentity(
    Basin("illustrative-basin", "v1"), River("illustrative-river", "v1", 0), LOCATION, "district-section-1"
)
HISTORY = Interval(datetime(1990, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC))
YEAR = Interval(datetime(2028, 1, 1, tzinfo=UTC), datetime(2029, 1, 1, tzinfo=UTC))
MONTHS = tuple(
    Interval(datetime(2028, m, 1, tzinfo=UTC), datetime(2028 + (m == 12), m % 12 + 1, 1, tzinfo=UTC))
    for m in range(1, 13)
)
PROVENANCE = Provenance(
    "synthetic supplied Kazakh studies, not field evidence",
    "kazakh-illustration",
    "natural-member-1",
    "fishy supplied-scenario example",
    "data-v1",
    "config-v1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
    ReferenceKind.PRESENT_CLIMATE_NATURAL,
    limitations=("Synthetic settings, not calibration or legal status",),
)
SOURCE179 = "Order 179-НҚ, 23 July 2025; held Ministry original"


def support(scope: EvidenceScope, provenance: Provenance) -> EvidenceFindings:
    return EvidenceFindings(
        scope,
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("Supported only within this synthetic illustration",),
    )


def scoped_support(
    product: str, period: Interval, use: str, provenance: Provenance, location: Location = LOCATION
) -> EvidenceFindings:
    return support(
        EvidenceScope(product, location.reach.identifier, provenance.reference_member, period, use), provenance
    )


def natural_reference(observations: ObservationRoute, provenance: Provenance = PROVENANCE) -> NaturalAnnualReference:
    reconstruction = (
        scoped_support("annual_monthly_reconstruction", HISTORY, "initial_allocation", provenance)
        if observations is ObservationRoute.INSUFFICIENT
        else None
    )
    return NaturalAnnualReference(
        LOCATION,
        HISTORY,
        tuple(
            AnnualQuantile(p, Volume(v * 1_000_000))
            for p, v in zip(
                (NaturalExceedance.P50, NaturalExceedance.P75, NaturalExceedance.P90, NaturalExceedance.P97),
                (100, 80, 60, 40),
                strict=True,
            )
        ),
        observations,
        provenance,
        scoped_support("natural_annual_reference", HISTORY, "initial_allocation", provenance),
        reconstruction,
    )


def biological_timing(provenance: Provenance) -> BiologicalTiming:
    onset = datetime(2028, 4, 15, tzinfo=UTC)
    period = Interval(onset, onset + timedelta(days=6))
    temperature = SignedState(StateVariable.TEMPERATURE, 15, "degC", "water at biological onset")
    return BiologicalTiming(
        "Сазан",
        onset,
        0,
        (2, 2, 2),
        temperature,
        temperature,
        scoped_support("spawning_timing", period, "spawning_correction", provenance),
        LOCATION,
        YEAR,
        scoped_support("spawning_timing_applicability", YEAR, "spawning_correction", provenance),
    )


def source_bounds(provenance: Provenance) -> DesignBounds:
    def schedule(annual: Volume) -> tuple[FlowSample, ...]:
        return tuple(
            FlowSample(LOCATION, m, Flow(annual.value / YEAR.seconds), Presence.PRESENT, provenance) for m in MONTHS
        )

    def annual(value: Volume) -> AnnualReferenceVolume:
        return AnnualReferenceVolume(
            LOCATION,
            YEAR,
            value,
            Presence.PRESENT,
            provenance,
            support(annual_bound_scope(LOCATION, YEAR, provenance), provenance),
        )

    # Imported annual-design hydrographs, not percentiles of daily flows.
    return DesignBounds(
        schedule(Volume(10_000_000)),
        schedule(Volume(20_000_000)),
        schedule(Volume(100_000_000)),
        annual(Volume(20_000_000)),
        annual(Volume(100_000_000)),
        SOURCE179,
    )


def corrected_design(initial: InitialAllocation, *, basin_row: int = 2):
    provenance = initial.reference.provenance
    probability = shifted_class(initial.design)
    shape = SeasonalShape(
        LOCATION,
        YEAR,
        probability,
        tuple(ShapeOrdinate(m, Fraction(1)) for m in MONTHS),
        provenance,
        scoped_support(f"seasonal_shape_P{probability.value}", YEAR, "seasonal_allocation", provenance),
    )
    seasonal = seasonal_schedule(initial, YEAR, ShapeChoice.SHIFTED_CLASS, shape)
    coefficients = spawning_schedule(
        LOCATION,
        MONTHS,
        provenance,
        initial.design,
        EligibilityInterpretation.DRY_YEAR_WORDING,
        TemporalBasis.MONTHLY_AVERAGE,
        CoefficientInterpretation.LISTED_VALUE,
        StarRelevance.NOT_RELIED_UPON,
        biological_timing(provenance),
        tuple(support(coefficient_scope(LOCATION, m, provenance), provenance) for m in MONTHS),
        basin_row=basin_row,
    )
    corrected = correct_schedule(
        seasonal.samples,
        source_bounds(provenance),
        coefficients,
        CorrectionOrder.CORRECTION_THEN_BOUNDS,
        replace(provenance, correction_state=CorrectionState.CORRECTED),
    )
    report = appendix1_report(initial, YEAR, corrected.samples, ScheduleStage.CORRECTED, IDENTITY)
    return corrected, report


def chemical_classification(provenance: Provenance):
    from fishy.quality import Comparison

    rows = (source_row("order111:02"), source_row("order111:27"))
    choices = (
        CellInterpretation(
            "order111:27",
            WaterClass.ONE,
            "explicit upper-limit interpretation for nitrite ion, not nitrogen",
            bare_operator=Comparison.LE,
        ),
    )
    profile = Order111Profile(
        "oxygen and nitrite selected profile",
        provenance.configuration_version,
        provenance.scenario,
        LOCATION,
        YEAR,
        WaterScope.RIVER,
        date(2029, 1, 1),
        tuple(row.identifier for row in rows),
        "supplied study interval extrema",
        choices,
    )
    observations = tuple(
        ClassificationObservation(
            row.identifier,
            SourceValue(value, value, row.unit, row.name),
            LOCATION,
            YEAR,
            profile.basis,
            Presence.PRESENT,
            provenance,
        )
        for row, value in zip(rows, ("7", "0.05"), strict=True)
    )
    return assess_order111(profile, observations)


def selected_classification(provenance: Provenance):
    # This selected numerical profile is not the national full-parameter inventory.
    row = source_row("order111:63")
    choices = tuple(
        CellInterpretation(
            row.identifier, WaterClass(c), "synthetic closed-range selection", range_meaning=RangeMeaning.CLOSED
        )
        for c in range(2, 6)
    )
    profile = Order111Profile(
        "selected row63 illustration",
        provenance.configuration_version,
        provenance.scenario,
        LOCATION,
        YEAR,
        WaterScope.RIVER,
        date(2029, 1, 1),
        (row.identifier,),
        "supplied study representative value",
        choices,
    )
    observation = ClassificationObservation(
        row.identifier,
        SourceValue(3, 3, row.unit, row.name),
        LOCATION,
        YEAR,
        profile.basis,
        Presence.PRESENT,
        provenance,
    )
    return assess_order111(profile, (observation,))


def review_inventory(provenance: Provenance):
    applicability = order179_applicability(date(2029, 1, 1), 23, provenance)
    return assess_review(
        applicability,
        StudyReview(date(2028, 1, 1), provenance),
        BasinChange(ChangeState.UNCHANGED, provenance),
        BasinChange(ChangeState.UNCHANGED, provenance),
    )


def main() -> None:
    # Imported separately so this file also works as a directly executed example.
    from supplied_basin_context import prepared_basin, supplied_tributary_account
    from supplied_ecological_studies import supplied_assessments

    from fishy.basin import mouth_to_source
    from fishy.evidence import CheckFinding

    print(
        f"Basin={IDENTITY.basin.identifier}; river={IDENTITY.river.identifier}; section={LOCATION.section.identifier}"
    )
    for design in DesignClass:
        initial = initial_allocation(
            natural_reference(ObservationRoute.ADEQUATE), design, AllocationRoute.MEDIAN_NORMALISED
        )
        corrected, report = corrected_design(initial)
        studies = supplied_assessments(corrected.samples)
        topology = prepared_basin(IDENTITY, YEAR, PROVENANCE)
        assert mouth_to_source(topology)[0].location == LOCATION
        assert report.annual.volume is not None
        account = supplied_tributary_account(topology, IDENTITY, YEAR, PROVENANCE, report.annual.volume, report.design)
        assert account.volume == report.annual.volume
        assert corrected.annual_checks.finding is CheckFinding.PASS
        assert all(a.numerical.finding is CheckFinding.PASS for a in studies)
        print(
            f"P{design.value}: initial={initial.volume}; actual={report.annual.million_m3} million m3; "
            f"February={report.monthly[1].annual_share_percent}% of actual annual volume; "
            f"{len(studies)} supplied-study assessments pass; {corrected.status.value}"
        )
    chemical = chemical_classification(PROVENANCE)
    assert chemical.classes[0].summary.finding is CheckFinding.PASS
    print("Selected oxygen/nitrite class1 cells pass numerically; scientific acceptance is separate.")
    quality = selected_classification(PROVENANCE)
    assert quality.supported_matches == (WaterClass.FOUR,)
    use = assess_order111_use(
        WaterClass.FOUR,
        WaterUse.DRINKING_INTENSIVE,
        UseInterpretation(UseMapping.DESCRIPTIVE, "labelled scenario mapping"),
    )
    print(f"Selected Order111 profile: class4; drinking use: {use.finding}; intensive treatment not established")
    review = review_inventory(PROVENANCE)
    print(f"Study review: {review.state}; source applicability: {review.applicability.status}")
    print("Complete configured numerical checks, not full source replication. Official admissibility remains pending.")


if __name__ == "__main__":
    main()
