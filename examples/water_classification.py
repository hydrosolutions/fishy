"""Synthetic Order111 selected-row class matches, independent of Uzbek policy."""

from dataclasses import replace
from datetime import UTC, date, datetime

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.flows import Presence
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval
from fishy.water_classification import (
    CellInterpretation,
    ClassificationObservation,
    Order111Profile,
    RangeMeaning,
    SourceValue,
    UnitBasis,
    UseInterpretation,
    UseMapping,
    WaterClass,
    WaterScope,
    WaterUse,
    assess_order111,
    assess_order111_use,
    source_row,
)


def main() -> None:
    location = Location(
        Reach("example-reach", "1", WaterBody("example-river", "1")), CalculationSection("example-section", "1"), "1"
    )
    period = Interval(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))
    provenance = Provenance(
        "synthetic supplied saprobity study",
        "example",
        None,
        "example",
        "1",
        "1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    row = source_row("order111:63")
    # Closed endpoints are a labelled candidate, not an unprinted legal operator.
    interpretations = tuple(
        CellInterpretation(
            row.identifier, cls, "synthetic closed-endpoint interpretation", range_meaning=RangeMeaning.CLOSED
        )
        for cls in tuple(WaterClass)[1:5]
    )
    profile = Order111Profile(
        "saprobity-only",
        "1",
        "example",
        location,
        period,
        WaterScope.RIVER,
        date(2026, 1, 2),
        (row.identifier,),
        "supplied study interval",
        interpretations,
    )
    for value in ("0.5", "1.25", "2", "3", "3.75", "4.1"):
        sample = ClassificationObservation(
            row.identifier,
            SourceValue(value, value, row.unit, row.name),
            location,
            period,
            "supplied study interval",
            Presence.PRESENT,
            provenance,
        )
        result = assess_order111(profile, (sample,))
        print(value, "selected-row matches:", tuple(int(cls) for cls in result.supported_matches))
    # Explicit scaled-count interpretation supplies meaning, not a source transcription repair.
    bacteria = source_row("order111:68")
    counts = UnitBasis.TOTAL_BACTERIA_MILLIONS_PER_ML
    count_choice = CellInterpretation(
        bacteria.identifier,
        WaterClass.THREE,
        "illustrative scaled count interpretation",
        unit_basis=counts,
        range_meaning=RangeMeaning.CLOSED,
    )
    count_profile = replace(
        profile,
        identifier="bacterial-count-candidate",
        required_rows=(bacteria.identifier,),
        interpretations=(count_choice,),
    )
    count_sample = ClassificationObservation(
        bacteria.identifier,
        SourceValue(2, 2, counts.value, bacteria.name),
        location,
        period,
        "supplied study interval",
        Presence.PRESENT,
        provenance,
    )
    count_result = assess_order111(count_profile, (count_sample,))
    print("interpreted2 million cells/ml, class3:", count_result.classes[2].summary.finding.value)
    print(
        "same sample without unit interpretation:",
        assess_order111(replace(count_profile, interpretations=()), (count_sample,)).classes[2].summary.finding.value,
    )
    for mapping in (None, UseMapping.DESCRIPTIVE, UseMapping.MATRIX):
        choice = None if mapping is None else UseInterpretation(mapping, "labelled scenario; not legal resolution")
        use = assess_order111_use(WaterClass.FOUR, WaterUse.DRINKING_INTENSIVE, choice)
        print("class4 intensive drinking:", mapping, use.finding.value)
    print("No unique overall class, national compliance, or treatment adequacy is inferred.")


if __name__ == "__main__":
    main()
