"""SyntheticStorageSchedule → DeliveryAssessment for a supplied fixed-delay pathway.

Run: uv run python examples/receptor_delivery.py
All numbers and scientific acceptances are illustrative, not site or policy data.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
from fishy.quantities import Flow, Volume
from fishy.receptor_delivery import (
    BoundInclusion,
    DeliveryAssessment,
    DeliveryContext,
    DeliveryStep,
    ExchangeDirection,
    Pathway,
    PathwayRelease,
    ProcessTest,
    StorageBalance,
    SupportedProcessTest,
    WaterExchange,
    assess_delivery,
    delivery_scope,
    map_arrival,
    storage_arrival,
)
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def supplied_delivery() -> DeliveryAssessment:
    """Construct and recheck one synthetic selected operating schedule."""
    reach = Reach("wetland-reach", "v1", WaterBody("wetland", "v1"))

    def location(name: str) -> Location:
        return Location(reach, CalculationSection(name, "v1"), "map-v1")

    start = datetime(2024, 1, 1, tzinfo=UTC)
    period = Interval(start, start + timedelta(days=1))
    provenance = Provenance(
        "synthetic storage study",
        "hypothetical operating schedule",
        "reference-1",
        "example-v1",
        "synthetic-v1",
        "config-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    context = DeliveryContext(
        location("wetland-storage"), period, "selected-schedule", "mixed wetland storage m3", provenance
    )

    def accepted(subject: object, source: str) -> EvidenceFindings:
        # This explicit illustrative acceptance does not authenticate site evidence.
        return EvidenceFindings(
            delivery_scope(context, subject),
            replace(provenance, source=source),
            Computability.COMPUTABLE,
            NumericalValidity.VALID,
            Disclosure.COMPLETE,
            ScientificAdequacy.ACCEPTED,
            OfficialAdmissibility.PENDING,
            ("synthetic example only; no ecological or legal certification",),
        )

    rain = WaterExchange("rain", context, ExchangeDirection.INFLOW, Volume(20), location("atmosphere"))
    evaporation = WaterExchange("evaporation", context, ExchangeDirection.OUTFLOW, Volume(10), location("atmosphere"))
    balance = StorageBalance(
        context,
        Volume(100),
        Volume(200),
        (rain, evaporation),
        "accepted synthetic storage balance v1",
        "exact synthetic inputs, not field uncertainty",
    )
    balance_evidence = accepted(balance, "synthetic storage study")
    need = storage_arrival(balance, balance_evidence)
    assert need.arrival is not None

    delay = timedelta(hours=6)
    release_period = Interval(period.start - delay, period.end - delay)
    seepage = WaterExchange("canal-seepage", context, ExchangeDirection.OUTFLOW, Volume(8), location("aquifer"))
    path = Pathway(
        "canal",
        context,
        location("control-gate"),
        release_period,
        delay,
        Volume(3),
        Volume(5),
        (seepage,),
        Flow(0),
        Flow(1),
        Flow(0),
        Interval(release_period.start - timedelta(days=1), release_period.start),
        Fraction(1),
        Fraction(1),
        "fixed-delay stock/loss account v1",
        "supplied in-transit stocks and fixed loss; adjacent interval means",
        "exact synthetic account, not field uncertainty",
    )
    candidate = map_arrival(path, need.arrival)
    assert candidate is not None
    selected = PathwayRelease(path, candidate, accepted(path, "synthetic pathway study"))

    # A supported compartment-model value, not the incoming water concentration.
    salinity = ProcessTest(
        "salinity",
        context,
        "resident conservative salt",
        "kg/m3",
        "representative mixed compartment; supplied whole-interval maximum",
        Fraction(3, 10),
        None,
        Fraction(1),
        BoundInclusion.INCLUSIVE,
        "synthetic independent process model v1",
    )
    step = DeliveryStep(
        balance,
        balance_evidence,
        (selected,),
        ("canal",),
        ("salinity",),
        (SupportedProcessTest(salinity, accepted(salinity, "synthetic process study")),),
        None,
    )
    step = replace(step, checking_evidence=accepted(step.checking_subject, "synthetic independent schedule audit"))
    return assess_delivery((step,), period=period)


def main() -> None:
    result = supplied_delivery()
    step = result.steps[0]
    assert step.residual.arrival is not None and step.final_storage is not None
    print("arrival_m3=", step.residual.arrival.value)
    print("control_m3=", step.pathways[0].selected.release.value)
    print("final_storage_m3=", step.final_storage.value)
    print("finding=", result.checks.finding.value)
    assert step.step.evidence is not None
    print("official_admissibility=", step.step.evidence.official_admissibility.value)


if __name__ == "__main__":
    main()
