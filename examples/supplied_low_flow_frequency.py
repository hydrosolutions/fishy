"""Attribute a supplied seven-day minimum estimate to its recurrence probability.

Run with ``uv run python examples/supplied_low_flow_frequency.py``.
The numerical estimate and all source identifiers are illustrative.
"""

from datetime import UTC, datetime

from fishy.evidence import (
    CorrectionState,
    EvidenceScope,
    ProductionMethod,
    Provenance,
    ReferenceKind,
)
from fishy.low_flow_frequency import LowFlowReturnPeriod
from fishy.quantities import Flow
from fishy.scientific_acceptance import (
    HydrologicalProduct,
    HydrologicalProductKind,
    TemporalResolution,
    UsePurpose,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def supplied_minimum_product() -> HydrologicalProduct:
    recurrence = LowFlowReturnPeriod(10)
    location = Location(Reach("upstream", "1", WaterBody("river", "1")), CalculationSection("gauge", "1"), "1")
    provenance = Provenance(
        "illustrative imported minimum estimate",
        "screening-study",
        "natural-a",
        "example-v1",
        "synthetic-data-v1",
        "minimum-profile-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
    )
    period = Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC))
    return HydrologicalProduct(
        scope=EvidenceScope(
            "seven-day annual minimum; Tr10 supplied estimate v1",
            "upstream",
            "natural-a",
            period,
            "minimum-flow screening",
        ),
        provenance=provenance,
        kind=HydrologicalProductKind.DURATION_MINIMUM,
        statistic_name="annual minimum seven-day mean discharge at ten-year recurrence",
        units="m3/s",
        calendar="January-December UTC fixed 86400-second days",
        resolution=TemporalResolution.ANNUAL,
        purpose=UsePurpose.SCREENING,
        target_probability=recurrence.exceedance_probability,
        duration_days=7,
        location=location,
        climate_basis="present climate 2000-2019",
        population="one minimum complete seven-day mean per complete accounting year",
        reference_identity="synthetic-minimum-population-content-v1",
        result_identity="synthetic-external-minimum-estimate-content-v1",
        result_value=Flow(2),
        low_flow_return_period=recurrence,
    )


if __name__ == "__main__":
    product = supplied_minimum_product()
    recurrence = product.low_flow_return_period
    assert recurrence is not None
    print("Return period (years):", recurrence.years)
    print("Minimum nonexceedance probability:", recurrence.nonexceedance_probability)
    print("Minimum exceedance probability:", product.target_probability)
    print("Supplied estimate:", product.result_value)
    print("Scientific acceptance requires its own frozen review; no daily hydrograph is implied.")
