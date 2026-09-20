"""example : SimulatedIntervalVolumes × SuppliedDuty → PredictedDeliveryShortfalls."""

from dataclasses import replace
from datetime import datetime
from fractions import Fraction

import polars as pl
from taqsim import ConservationQuantum, IntervalVolume, TimeAxis, WaterSystem
from taqsim.constituents import ConservativeTransport, Constituent, RunMetadata

from fishy.duties import Delivery, DutyApplicability, Obligation, SuppliedDuty, assess_duty
from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.flows import FlowSample, Presence
from fishy.physical import ExchangeView, PhysicalProjection, TimeInterpretation
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody


def main() -> None:
    # The operating model receives water volumes, never the assessed duty as a demand.
    model = WaterSystem(time=TimeAxis("2020-02-28", 2), quantum=ConservationQuantum.LITRE)
    model.source(
        "inflow",
        IntervalVolume(
            pl.DataFrame(
                {
                    "time": [datetime(2020, 2, 28), datetime(2020, 2, 29)],
                    "value": [129600.0, 302400.0],
                }
            ),
            "m3",
            "1d",
            "0.001 m3",
        ),
    )
    model.reach("river", "inflow", "outlet")
    # Missing chemistry remains missing. It does not disable independent water.
    model.configure_transport(
        ConservativeTransport(
            (Constituent("salt", "dissolved salt", "as salt"),),
            metadata=RunMetadata(scenario="synthetic managed"),
        )
    )
    physical = model.build().run(bytes(16)).physical
    assert physical is not None
    location = Location(
        Reach("reach", "1", WaterBody("water-body", "1")), CalculationSection("section", "1"), "mapping-1"
    )
    source = Provenance(
        "synthetic volumes",
        "synthetic managed",
        None,
        "taqsim:396ad093c2b6f240e702a3b05aee1fb96a69b3f7;incidence:665da4e0d81ab28921b8d5d2edbb9be27f4ec612",
        "1",
        "1",
        ProductionMethod.SIMULATED,
        CorrectionState.ORIGINAL,
    )
    projection = PhysicalProjection(physical, location, "outlet", source, ExchangeView.INCOMING, TimeInterpretation.UTC)
    samples = projection.flows()
    assert [sample.value.value for sample in samples if sample.value is not None] == [Fraction(3, 2), Fraction(7, 2)]
    duty_source = replace(source, source="supplied illustrative duty", production_method=ProductionMethod.ILLUSTRATIVE)
    duty = SuppliedDuty(
        "daily-duty",
        "issued-1",
        "synthetic supplied schedule",
        DutyApplicability.HYPOTHETICAL,
        tuple(
            Obligation(FlowSample(location, sample.interval, Flow(value), Presence.PRESENT, duty_source), "issued-1")
            for sample, value in zip(samples, (2, 3), strict=True)
        ),
        "illustrative fixture, no legal search claim",
    )
    assessment = assess_duty(duty, tuple(Delivery(sample, "model-1") for sample in samples))
    assert [item.shortfall.value for item in assessment.intervals if item.shortfall is not None] == [Fraction(1, 2), 0]
    assert assessment.known_shortfall_volume.value == 43200
    print("Scenario prediction: shortfalls [0.5, 0] m3/s; total 43200 m3.")
    print("No later-surplus cancellation. Not observed compliance or water-quality acceptance.")


if __name__ == "__main__":
    main()
