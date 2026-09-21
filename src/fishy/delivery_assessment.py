"""assess_issued_delivery : Obligation × Delivery × ComparisonEvidence → DeliveryComparison.

The immutable issued obligation is never recapped from actual delivery. Nominal
shortfall and supported uncertainty findings remain separate per exact interval.
"""

from dataclasses import dataclass

from fishy.comparison_evidence import (
    ComparisonEvidence,
    MarginBounds,
    NumericalFinding,
    official_comparison,
    responsibility,
    sample_computability,
)
from fishy.duties import Delivery, Obligation
from fishy.evidence import Check, CheckFinding, Computability
from fishy.quantities import Flow, Volume


@dataclass(frozen=True)
class DeliveryComparison:
    obligation: Obligation
    actual: Delivery | None
    evidence: ComparisonEvidence
    raw_shortfall: Flow | None
    raw_shortfall_volume: Volume | None
    margin: MarginBounds | None
    numerical: NumericalFinding
    reasons: tuple[str, ...]
    official: Check
    responsibility: Check


def assess_issued_delivery(
    obligation: Obligation, actual: Delivery | None, *, evidence: ComparisonEvidence
) -> DeliveryComparison:
    """Assess one whole issued interval; callers never offset deficits with surpluses."""
    if type(obligation) is not Obligation or (actual is not None and type(actual) is not Delivery):
        raise TypeError("delivery comparison requires Obligation and actual Delivery")
    if evidence.threshold != obligation or evidence.actual != actual or evidence.but_for is not None:
        raise ValueError("evidence does not bind exact delivery operands and versions")
    raw = None
    volume = None
    margin = None
    reasons = []
    if (
        sample_computability(obligation.sample) is not Computability.COMPUTABLE
        or actual is None
        or sample_computability(actual.sample) is not Computability.COMPUTABLE
    ):
        reasons.append("complete supported issued obligation and actual interval required")
    else:
        assert obligation.sample.value is not None and actual.sample.value is not None
        raw = Flow(max(0, obligation.sample.value.value - actual.sample.value.value))
        volume = Volume(raw.value * obligation.sample.interval.seconds)
        if actual.sample.uncertainty is None:
            reasons.append("actual uncertainty unavailable; point estimate is not certain")
        elif evidence.admission.finding is CheckFinding.PASS:
            bounds = actual.sample.uncertainty
            margin = MarginBounds(
                bounds.lower.value - obligation.sample.value.value, bounds.upper.value - obligation.sample.value.value
            )
    if evidence.admission.finding is not CheckFinding.PASS:
        reasons.append("required evidence missing or rejected")
    finding = margin.finding if margin is not None else NumericalFinding.UNAVAILABLE
    return DeliveryComparison(
        obligation,
        actual,
        evidence,
        raw,
        volume,
        margin,
        finding,
        tuple(reasons),
        official_comparison(evidence, finding),
        responsibility(evidence, finding),
    )
