"""Run one synthetic Kazakh annual/seasonal configuration, without Taqsim or Uzbek inputs.

uv run python examples/kazakh_allocation.py
"""

from datetime import UTC, datetime
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
from fishy.kazakh_allocation import (
    AllocationRoute,
    AnnualQuantile,
    NaturalAnnualReference,
    NaturalExceedance,
    ObservationRoute,
    initial_allocation,
    shifted_class,
)
from fishy.quantities import Volume
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
from fishy.time import Interval


def main() -> None:
    location = Location(
        Reach("synthetic-reach", "v1", WaterBody("synthetic-body", "v1")),
        CalculationSection("synthetic-section", "v1"),
        "map-v1",
    )
    identity = ReportingIdentity(
        Basin("synthetic-basin", "v1"), River("synthetic-river", "v1", 0), location, "district-section-1"
    )
    history = Interval(datetime(1990, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC))
    year = Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC))
    provenance = Provenance(
        "synthetic illustration, not field evidence",
        "example",
        "natural-member-1",
        "fishy",
        "data-v1",
        "config-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
        limitations=("No scientific site validation or legal certification",),
    )

    def support(product: str, period: Interval, use: str) -> EvidenceFindings:
        return EvidenceFindings(
            EvidenceScope(product, location.reach.identifier, provenance.reference_member, period, use),
            provenance,
            Computability.COMPUTABLE,
            NumericalValidity.VALID,
            Disclosure.COMPLETE,
            ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
            OfficialAdmissibility.PENDING,
            ("Accepted only for this synthetic example",),
        )

    reference = NaturalAnnualReference(
        location,
        history,
        tuple(
            AnnualQuantile(probability, Volume(value * 1_000_000))
            for probability, value in zip(
                (NaturalExceedance.P50, NaturalExceedance.P75, NaturalExceedance.P90, NaturalExceedance.P97),
                (100, 80, 60, 40),
                strict=True,
            )
        ),
        ObservationRoute.ADEQUATE,
        provenance,
        support("natural_annual_reference", history, "initial_allocation"),
    )
    months = tuple(
        Interval(datetime(2024, m, 1, tzinfo=UTC), datetime(2024 + (m == 12), m % 12 + 1, 1, tzinfo=UTC))
        for m in range(1, 13)
    )
    for design in DesignClass:
        initial = initial_allocation(reference, design, AllocationRoute.MEDIAN_NORMALISED)
        probability = shifted_class(design)
        pattern = SeasonalShape(
            location,
            year,
            probability,
            tuple(ShapeOrdinate(month, Fraction(1)) for month in months),
            provenance,
            support(f"seasonal_shape_P{probability.value}", year, "seasonal_allocation"),
        )
        seasonal = seasonal_schedule(initial, year, ShapeChoice.SHIFTED_CLASS, pattern)
        report = appendix1_report(initial, year, seasonal.samples, ScheduleStage.INITIAL, identity)
        print(
            f"P{design.value}: alpha={initial.coefficient}; annual={report.annual.million_m3} million m3; "
            f"February share={float(report.monthly[1].annual_share_percent):.6f}%"
        )
    print("These initial schedules still need applicable ecological/bounds and source-interpretation assessments.")


if __name__ == "__main__":
    main()
