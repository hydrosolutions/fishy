"""scenario : GregorianDay → IssuedObligation × DeliveryComparison × FloorComparison.

Hypothetical fixed values exercise the proposed Uzbek arithmetic, not policy.
"""

from datetime import UTC, datetime, timedelta

from fishy.comparison_evidence import Attribution, AttributionFinding, ButForFlow, ComparisonEvidence
from fishy.delivery_assessment import assess_issued_delivery
from fishy.duties import Deliverability, Delivery, Floor, Obligation, Requirement
from fishy.evidence import Check, CheckFinding, CorrectionState, OfficialAdmissibility, ProductionMethod, Provenance
from fishy.floor_assessment import assess_floor
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow, FlowBounds
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval
from fishy.uzbek_issuance import issue_obligation


def scenario_evidence(
    threshold: Floor | Obligation, actual: Delivery | None, but_for: ButForFlow | None = None
) -> ComparisonEvidence:
    """Explicit supported fictional evidence, never observed or officially admitted."""
    names = ("coverage", "infill", "authentication", "reconciliation", "uncertainty")
    if isinstance(threshold, Floor):
        names += ("abstraction_metering", "downstream_of_conduct")
    return ComparisonEvidence(
        threshold,
        actual,
        but_for,
        tuple(
            Check(name, CheckFinding.PASS, ("stipulated fictional support; full stated interval; no confidence claim",))
            for name in names
        ),
        None,
        OfficialAdmissibility.PENDING,
        Attribution(
            AttributionFinding.UNASSESSED,
            "scenario cannot attribute responsibility",
            Check("operator_control", CheckFinding.UNKNOWN, ("not investigated",)),
        ),
        "hypothetical-evidence-v1",
    )


def scenario(day: datetime):
    """Assess one fixed UTC day; iterate real calendar dates for an annual schedule."""
    period = Interval(day, day + timedelta(days=1))
    location = Location(
        Reach("river-reach", "v1", WaterBody("river", "v1")), CalculationSection("downstream", "v1"), "map-v1"
    )
    provenance = Provenance(
        "invented inputs",
        "hypothetical",
        None,
        "fishy-source-revision",
        "synthetic-v1",
        "assumptions-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )

    def sample(value):
        amount = Flow(value)
        return FlowSample(
            location,
            period,
            amount,
            Presence.PRESENT,
            provenance,
            FlowBounds(
                amount,
                amount,
                "assumed fixed fictional value",
                "synthetic-v1",
                "joint fixed values; not estimated confidence",
            ),
        )

    issue = issue_obligation(
        Requirement(sample(10), "requirement-v1"),
        Deliverability(sample(6), "capacity-v1"),
        version="issued-v1",
        provenance=provenance,
    )
    actual = Delivery(sample(5), "delivery-v1")
    delivery = assess_issued_delivery(issue.obligation, actual, evidence=scenario_evidence(issue.obligation, actual))
    # The floor does not enter issuance and capacity does not enter its comparator.
    floor = Floor(sample(8), "floor-v1")
    but_for = ButForFlow(sample(9), "balance-v1", "hypothetical abstraction")
    prohibition = assess_floor(floor, actual, but_for, evidence=scenario_evidence(floor, actual, but_for))
    return issue, delivery, prohibition


if __name__ == "__main__":
    issued, delivery, floor = scenario(datetime(2020, 2, 29, tzinfo=UTC))
    print("obligation", issued.obligation.sample.value)
    print("ecological deficit", issued.ecological_deficit)
    print("delivery shortfall", delivery.raw_shortfall, delivery.numerical)
    print("fixed floor comparison", floor.numerical)
    print("official finding", floor.official.finding)
