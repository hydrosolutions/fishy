"""assess_floor : Floor × Delivery × ButForFlow × ComparisonEvidence → FloorComparison.

F is fixed. The comparison is A - min(F, P), with no deliverability operand.
Marginal supports imply no independence or inferred joint confidence guarantee.
"""

from dataclasses import dataclass
from enum import StrEnum

from fishy.comparison_evidence import (
    ButForFlow,
    ComparisonEvidence,
    MarginBounds,
    NumericalFinding,
    official_comparison,
    responsibility,
    sample_computability,
)
from fishy.duties import Delivery, Floor
from fishy.evidence import Check, CheckFinding, Computability
from fishy.quantities import Flow


class JointSupportKind(StrEnum):
    ENCLOSING = "supported_enclosing_margin"
    FINITE_DRAWS = "finite_draw_extrema_only"


@dataclass(frozen=True)
class JointMargin:
    """An externally supported enclosure of the same fixed-floor comparison."""

    floor: Floor
    actual: Delivery
    but_for: ButForFlow
    margin: MarginBounds
    kind: JointSupportKind
    method: str
    source: str
    dependence: str
    coverage: str

    def __post_init__(self) -> None:
        if (
            type(self.floor) is not Floor
            or type(self.actual) is not Delivery
            or not isinstance(self.but_for, ButForFlow)
            or not isinstance(self.margin, MarginBounds)
            or not isinstance(self.kind, JointSupportKind)
        ):
            raise TypeError("joint margin requires typed operands, bounds and support kind")
        for text in (self.method, self.source, self.dependence, self.coverage):
            if not isinstance(text, str) or not text.strip():
                raise ValueError("joint enclosure requires method, source, dependence and coverage")


@dataclass(frozen=True)
class FloorComparison:
    floor: Floor
    actual: Delivery | None
    but_for: ButForFlow | None
    evidence: ComparisonEvidence
    raw_shortfall: Flow | None
    rectangular_margin: MarginBounds | None
    joint_margin: JointMargin | None
    margin: MarginBounds | None
    numerical: NumericalFinding
    reasons: tuple[str, ...]
    official: Check
    responsibility: Check


def assess_floor(
    floor: Floor,
    actual: Delivery | None,
    but_for: ButForFlow | None,
    *,
    evidence: ComparisonEvidence,
    joint_margin: JointMargin | None = None,
) -> FloorComparison:
    """Missing/rejected prerequisite support is unavailable, not overlapping support.

    Finite draws do not supply an enclosing support: retain the valid rectangular
    result without tightening it, and record that the requested joint route failed.
    No result creates a duty, replaces the floor, or decides legal liability.
    """
    if type(floor) is not Floor or (actual is not None and type(actual) is not Delivery):
        raise TypeError("floor comparison requires Floor and actual Delivery")
    if but_for is not None and not isinstance(but_for, ButForFlow):
        raise TypeError("floor comparison requires ButForFlow")
    if evidence.threshold != floor or evidence.actual != actual or evidence.but_for != but_for:
        raise ValueError("evidence does not bind exact floor operands and versions")
    if joint_margin is not None and (
        joint_margin.floor != floor or joint_margin.actual != actual or joint_margin.but_for != but_for
    ):
        raise ValueError("joint margin does not bind exact comparison operands and versions")
    raw = None
    rectangle = None
    margin = None
    reasons = []
    if (
        sample_computability(floor.sample) is not Computability.COMPUTABLE
        or actual is None
        or but_for is None
        or sample_computability(actual.sample) is not Computability.COMPUTABLE
        or sample_computability(but_for.sample) is not Computability.COMPUTABLE
    ):
        reasons.append("complete supported floor, actual and but-for interval required")
    else:
        assert floor.sample.value is not None and actual.sample.value is not None and but_for.sample.value is not None
        F = floor.sample.value.value
        raw = Flow(max(0, min(F, but_for.sample.value.value) - actual.sample.value.value))
        A, P = actual.sample.uncertainty, but_for.sample.uncertainty
        if A is None or P is None:
            reasons.append("actual and but-for uncertainty required; missing is not singleton support")
        elif evidence.admission.finding is CheckFinding.PASS:
            rectangle = MarginBounds(A.lower.value - min(F, P.upper.value), A.upper.value - min(F, P.lower.value))
            margin = rectangle
            if joint_margin is not None:
                if joint_margin.kind is JointSupportKind.FINITE_DRAWS:
                    reasons.append("finite draws do not establish enclosing support; rectangular result retained")
                else:
                    if joint_margin.margin.lower < rectangle.lower or joint_margin.margin.upper > rectangle.upper:
                        raise ValueError("tightened joint enclosure must lie within marginal enclosure")
                    margin = joint_margin.margin
    if evidence.admission.finding is not CheckFinding.PASS:
        reasons.append("required evidence missing or rejected")
    finding = margin.finding if margin is not None else NumericalFinding.UNAVAILABLE
    return FloorComparison(
        floor,
        actual,
        but_for,
        evidence,
        raw,
        rectangle,
        joint_margin,
        margin,
        finding,
        tuple(reasons),
        official_comparison(evidence, finding),
        responsibility(evidence, finding),
    )
