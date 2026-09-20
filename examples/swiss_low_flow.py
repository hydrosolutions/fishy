"""Synthetic imported Q347 → literal starting minimum; no simulator or permit claim."""

from datetime import UTC, datetime

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.low_flow import EstimateStatus, imported_q347
from fishy.quantities import Flow
from fishy.residual_flow import StartingMinimum, attributed_starting_minimum
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def example() -> StartingMinimum:
    location = Location(Reach("synthetic reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
    provenance = Provenance(
        "synthetic model study",
        "illustration",
        "member",
        "1",
        "1",
        "1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    period = Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2010, 1, 1, tzinfo=UTC))
    estimate = imported_q347(
        Flow(160, "l/s"),
        location,
        period,
        provenance,
        "synthetic Art. 59 model estimate; not certified",
        EstimateStatus.PRELIMINARY,
    )
    return attributed_starting_minimum(estimate)


if __name__ == "__main__":
    result = example()
    print(f"Q347={result.q347.value.value * 1000} l/s; starting minimum={result.value.value * 1000} l/s")
    print(result.q347.status)
