"""evaluate_graduated_entry : GraduatedCurve × EntryStatistic × LargeRiverScreen → EntryResult (pure).

Appendix A step 7's proposed Uzbek curve, not the literal Swiss table.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import Check, CheckFinding
from fishy.quantities import Flow, finite_number
from fishy.scientific_acceptance import (
    HydrologicalProduct,
    HydrologicalProductKind,
    ScientificAssessment,
    TemporalResolution,
    UsePurpose,
)


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("source, version and decision basis must be nonempty")


class ParameterBasis(StrEnum):
    HYPOTHETICAL = "explicit_hypothetical_settings"
    ADOPTED = "supplied_adoption_evidence"


@dataclass(frozen=True)
class GraduatedSegment:
    breakpoint: Flow
    anchor: Flow
    marginal_rate: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.breakpoint, Flow) or not isinstance(self.anchor, Flow):
            raise TypeError("breakpoint and anchor require Flow")
        rate = finite_number(self.marginal_rate)
        if rate < 0:
            raise ValueError("marginal rate must be nonnegative")
        object.__setattr__(self, "marginal_rate", rate)


@dataclass(frozen=True)
class GraduatedCurve:
    version: str
    segments: tuple[GraduatedSegment, ...]
    basis: ParameterBasis
    source: str

    def __post_init__(self) -> None:
        _text(self.version)
        _text(self.source)
        if not isinstance(self.basis, ParameterBasis):
            raise TypeError("explicit parameter basis required")
        if (
            not isinstance(self.segments, tuple)
            or not self.segments
            or any(not isinstance(s, GraduatedSegment) for s in self.segments)
        ):
            raise ValueError("nonempty immutable segment table required")
        for left, right in zip(self.segments, self.segments[1:], strict=False):
            delta = right.breakpoint.value - left.breakpoint.value
            if delta <= 0:
                raise ValueError("breakpoints must strictly increase")
            if right.anchor.value != left.anchor.value + left.marginal_rate * delta:
                raise ValueError("entry curve must be exactly continuous at every junction")
            if right.marginal_rate > left.marginal_rate:
                raise ValueError("entry curve must be concave")

    def evaluate(self, value: Flow) -> tuple[Flow, GraduatedSegment] | None:
        if not isinstance(value, Flow):
            raise TypeError("Flow required")
        applicable = tuple(s for s in self.segments if s.breakpoint.value <= value.value)
        if not applicable:
            return None
        segment = applicable[-1]
        return Flow(segment.anchor.value + segment.marginal_rate * (value.value - segment.breakpoint.value)), segment


@dataclass(frozen=True)
class LargeRiverScreen:
    """Reject when input >= threshold AND slope <= limit AND retained share <= limit.

    This explicit scenario criterion is one configurable screen, not a national rule.
    Sensitivity and expert/adoption basis are supplied, never inferred from flatness.
    """

    curve_version: str
    minimum_input: Flow
    maximum_marginal_rate: Fraction
    maximum_retained_share: Fraction
    basis: ParameterBasis
    source: str
    sensitivity: str

    def __post_init__(self) -> None:
        for value in (self.curve_version, self.source, self.sensitivity):
            _text(value)
        if not isinstance(self.minimum_input, Flow) or not isinstance(self.basis, ParameterBasis):
            raise TypeError("typed screen settings required")
        for name in ("maximum_marginal_rate", "maximum_retained_share"):
            value = finite_number(getattr(self, name))
            if value < 0:
                raise ValueError("screen limits must be nonnegative")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class EntryStatistic:
    product: HydrologicalProduct
    assessment: ScientificAssessment

    def __post_init__(self) -> None:
        if not isinstance(self.product, HydrologicalProduct) or not isinstance(self.assessment, ScientificAssessment):
            raise TypeError("exact hydrological product and scientific assessment required")
        if self.product.kind is not HydrologicalProductKind.LOW_FLOW_STATISTIC:
            raise ValueError("entry requires a daily low-flow statistic, not an annual magnitude")
        if self.product.result_value is None:
            raise ValueError("entry statistic requires its exact scalar value")
        if self.product.resolution is not TemporalResolution.DAILY:
            raise ValueError("entry statistic requires supported daily equivalence")
        if self.product.purpose is not UsePurpose.SIZING:
            raise ValueError("entry requires sizing evidence, not screening permission")


class EntryStatus(StrEnum):
    FLOOR_ONLY = "floor_only"
    UNAVAILABLE = "unavailable"
    REFUSED = "refused"


@dataclass(frozen=True)
class EntryResult:
    status: EntryStatus
    floor: Flow | None
    candidate: Flow | None
    statistic: EntryStatistic
    curve: GraduatedCurve | None
    screen: LargeRiverScreen | None
    checks: tuple[Check, ...]


def evaluate_graduated_entry(
    statistic: EntryStatistic, curve: GraduatedCurve | None, screen: LargeRiverScreen | None
) -> EntryResult:
    """Return an uncapped base floor only; quality and issuance are separate."""
    permission = statistic.assessment.acceptance_for(statistic.product)
    checks = [permission]
    value = statistic.product.result_value
    assert value is not None
    if permission.finding is not CheckFinding.PASS:
        return EntryResult(EntryStatus.UNAVAILABLE, None, None, statistic, curve, screen, tuple(checks))
    if curve is None:
        checks.append(Check("table", CheckFinding.UNKNOWN, ("explicit graduated table missing",)))
        return EntryResult(EntryStatus.UNAVAILABLE, None, None, statistic, curve, screen, tuple(checks))
    evaluated = curve.evaluate(value)
    if evaluated is None:
        checks.append(Check("table_domain", CheckFinding.UNKNOWN, ("input below configured table domain",)))
        return EntryResult(EntryStatus.UNAVAILABLE, None, None, statistic, curve, screen, tuple(checks))
    candidate, segment = evaluated
    if candidate.value >= value.value:
        checks.append(Check("floor_less_than_input", CheckFinding.FAIL, ("floor >= input; no cap permitted",)))
        return EntryResult(EntryStatus.REFUSED, None, candidate, statistic, curve, screen, tuple(checks))
    if screen is None:
        checks.append(Check("large_river_screen", CheckFinding.UNKNOWN, ("reproducible screen missing",)))
        return EntryResult(EntryStatus.UNAVAILABLE, None, candidate, statistic, curve, screen, tuple(checks))
    if screen.curve_version != curve.version or screen.basis is not curve.basis:
        raise ValueError("screen must refer to this curve version and parameter basis")
    failed = (
        value.value >= screen.minimum_input.value
        and segment.marginal_rate <= screen.maximum_marginal_rate
        and candidate.value / value.value <= screen.maximum_retained_share
    )
    checks.append(
        Check(
            "large_river_screen",
            CheckFinding.FAIL if failed else CheckFinding.PASS,
            ("configured marginal-response and retained-share criterion",),
        )
    )
    return EntryResult(
        EntryStatus.REFUSED if failed else EntryStatus.FLOOR_ONLY,
        None if failed else candidate,
        candidate,
        statistic,
        curve,
        screen,
        tuple(checks),
    )
