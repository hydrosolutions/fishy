"""example : SuppliedSchedule × ObservedFlows → IndependentDailyShortfalls."""

from datetime import UTC, datetime, timedelta

from fishy.duties import Delivery, DutyApplicability, Obligation, SuppliedDuty, assess_duty
from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow, Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def main() -> None:
    location = Location(
        Reach("river-reach", "geometry-1", WaterBody("river", "boundary-1")),
        CalculationSection("section", "1"),
        "map-1",
    )
    observed = Provenance(
        "synthetic gauge",
        "observed-example",
        None,
        "instrument-1",
        "data-1",
        "configuration-1",
        ProductionMethod.OBSERVED,
        CorrectionState.ORIGINAL,
    )
    prescribed = Provenance(
        "supplied instrument",
        "issued",
        None,
        "schedule-import-1",
        "duty-1",
        "configuration-1",
        ProductionMethod.IMPORTED,
        CorrectionState.ORIGINAL,
    )
    start = datetime(2020, 2, 28, tzinfo=UTC)
    periods = tuple(Interval(start + timedelta(days=i), start + timedelta(days=i + 1)) for i in range(2))
    duty = SuppliedDuty(
        "independent release duty",
        "1",
        "synthetic provision",
        DutyApplicability.APPLICABLE,
        tuple(
            Obligation(FlowSample(location, period, Flow(value), Presence.PRESENT, prescribed), "1")
            for period, value in zip(periods, (2, 3), strict=True)
        ),
        "synthetic search record; not a legal authentication",
    )
    delivery = tuple(
        Delivery(FlowSample(location, period, Flow(value), Presence.PRESENT, observed), "1")
        for period, value in zip(periods, (1.5, 3.5), strict=True)
    )
    result = assess_duty(duty, delivery)
    assert result.known_shortfall_volume == Volume(43200)
    print(
        "Daily shortfall (m3/s):", [float(row.shortfall.value) if row.shortfall else None for row in result.intervals]
    )
    print("Known shortfall volume (m3):", result.known_shortfall_volume.value)
    print("Numerical finding:", result.summary.finding.value, result.summary.completeness.value)
    print("Interpretation:", result.interpretation.value)
    print("No uncertainty or legal responsibility finding is inferred.")


if __name__ == "__main__":
    main()
