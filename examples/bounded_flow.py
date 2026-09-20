"""Demonstrate both explicit correction orders on one synthetic annual interval."""

from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

from fishy.evidence import (
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.flow_bounds import AnnualReferenceVolume, CorrectionOrder, DesignBounds, correct_schedule
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow, Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.spawning import TimedCoefficient, coefficient_scope
from fishy.time import Interval


def main() -> None:
    location = Location(Reach("river-reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
    year = Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC))
    source = Provenance(
        "synthetic arithmetic, not biological calibration",
        "candidate",
        "natural",
        "example",
        "data1",
        "config1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )

    def sample(value: int) -> FlowSample:
        return FlowSample(location, year, Flow(value), Presence.PRESENT, source)

    bounds = DesignBounds(
        (sample(3),),
        (sample(5),),
        (sample(10),),
        AnnualReferenceVolume(location, year, Volume(5 * year.seconds), Presence.PRESENT, source),
        AnnualReferenceVolume(location, year, Volume(10 * year.seconds), Presence.PRESENT, source),
        "Order 179-НҚ:2025-07-23",
    )
    findings = EvidenceFindings(
        coefficient_scope(location, year, source),
        source,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("arithmetic discriminator only, not a spawning calendar",),
    )
    coefficient = TimedCoefficient(location, year, Fraction(3, 2), source, findings)
    result_source = replace(source, correction_state=CorrectionState.CORRECTED)
    for order in CorrectionOrder:
        result = correct_schedule((sample(8),), bounds, (coefficient,), order, result_source)
        assert result.samples[0].value is not None and result.actual_volume is not None
        print(
            order.value,
            "m3/s=",
            result.samples[0].value.value,
            "m3=",
            result.actual_volume.value,
            "conflicts=",
            ",".join(c.value for c in result.intervals[0].conflicts),
        )


if __name__ == "__main__":
    main()
