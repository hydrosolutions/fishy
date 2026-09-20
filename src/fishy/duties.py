"""assess_duty : SuppliedDuty × DeliveredFlows → AttributableShortfalls (no issuance or capping)."""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import Check, CheckFinding, CheckSummary, ProductionMethod, aggregate_checks
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, check_flow_intervals, interval_use
from fishy.quantities import Flow, Volume
from fishy.time import Interval


@dataclass(frozen=True)
class Requirement:
    sample: FlowSample
    version: str

    def __post_init__(self) -> None:
        _quantity(self.sample, self.version)


@dataclass(frozen=True)
class Floor:
    sample: FlowSample
    version: str

    def __post_init__(self) -> None:
        _quantity(self.sample, self.version)


@dataclass(frozen=True)
class Availability:
    sample: FlowSample
    version: str

    def __post_init__(self) -> None:
        _quantity(self.sample, self.version)


@dataclass(frozen=True)
class Deliverability:
    sample: FlowSample
    version: str

    def __post_init__(self) -> None:
        _quantity(self.sample, self.version)


@dataclass(frozen=True)
class Obligation:
    sample: FlowSample
    version: str

    def __post_init__(self) -> None:
        _quantity(self.sample, self.version)


@dataclass(frozen=True)
class Delivery:
    sample: FlowSample
    version: str

    def __post_init__(self) -> None:
        _quantity(self.sample, self.version)


def _quantity(sample: FlowSample, version: str) -> None:
    if not isinstance(sample, FlowSample):
        raise TypeError("quantity role requires FlowSample")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("quantity role requires a version")


class DutyApplicability(StrEnum):
    APPLICABLE = "authenticated_and_applicable"
    INAPPLICABLE = "located_but_inapplicable"
    UNRESOLVED = "unresolved"
    NONE_LOCATED = "none_located_after_search"
    HYPOTHETICAL = "hypothetical"


@dataclass(frozen=True)
class SuppliedDuty:
    """One independently attributable instrument; conflicts are not merged."""

    identifier: str
    version: str
    provision: str
    applicability: DutyApplicability
    schedule: tuple[Obligation, ...]
    search_record: str
    reasons: tuple[str, ...] = ()
    required_components: tuple[str, ...] = ("discharge",)

    def __post_init__(self) -> None:
        for name in ("identifier", "version", "provision", "search_record"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"duty requires {name}")
        if not isinstance(self.applicability, DutyApplicability):
            raise TypeError("duty applicability requires DutyApplicability")
        for name in ("schedule", "reasons", "required_components"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if any(type(item) is not Obligation for item in self.schedule):
            raise TypeError("duty schedule requires Obligation, not a floor or available water")
        if self.schedule:
            check_flow_intervals(tuple(item.sample for item in self.schedule))
            if any(item.version != self.version for item in self.schedule):
                raise ValueError("schedule must retain the supplied duty version")
        if self.applicability in (DutyApplicability.APPLICABLE, DutyApplicability.HYPOTHETICAL):
            if not self.schedule or "discharge" not in self.required_components:
                raise ValueError("a supplied discharge duty needs a schedule and discharge component")
        elif not self.reasons:
            raise ValueError("unresolved/inapplicable/unlocated duties need attributable reasons")
        if len(set(self.required_components)) != len(self.required_components) or any(
            not s for s in self.required_components
        ):
            raise ValueError("required duty components must be unique named checks")


class ComparisonKind(StrEnum):
    OBSERVATION = "observed_comparison_not_legal_compliance"
    PREDICTION = "scenario_prediction"
    FEASIBILITY = "supplied_deliverability_comparison"


@dataclass(frozen=True)
class IntervalAssessment:
    interval: Interval
    obligation: Obligation
    delivery: Delivery | Deliverability | None
    shortfall: Flow | None
    shortfall_volume: Volume | None
    numerical: Check
    uncertainty_finding: Check


@dataclass(frozen=True)
class DutyAssessment:
    duty: SuppliedDuty
    intervals: tuple[IntervalAssessment, ...]
    summary: CheckSummary
    interpretation: ComparisonKind

    @property
    def known_shortfall_volume(self) -> Volume:
        """Subtotal only; summary coverage identifies any unknown remaining shortfall."""
        return Volume(
            sum(
                (item.shortfall_volume.value for item in self.intervals if item.shortfall_volume is not None),
                Fraction(),
            )
        )


def assess_duty(
    duty: SuppliedDuty, deliveries: tuple[Delivery, ...], *, component_checks: tuple[Check, ...] = ()
) -> DutyAssessment:
    """Report supported numeric shortfalls; never claim legal responsibility.

    Required non-discharge components must be named in the duty and supplied as
    separate checks. Missing components remain unknown, even if discharge passes.
    """
    if any(type(item) is not Delivery for item in deliveries):
        raise TypeError("delivery assessment requires actual Delivery, not another quantity role")
    kind = (
        ComparisonKind.OBSERVATION
        if deliveries
        and all(item.sample.provenance.production_method is ProductionMethod.OBSERVED for item in deliveries)
        else ComparisonKind.PREDICTION
    )
    return _assess(duty, deliveries, component_checks, kind)


def assess_feasibility(duty: SuppliedDuty, deliverability: tuple[Deliverability, ...]) -> DutyAssessment:
    """Compare supported capacity without capping or changing any obligation."""
    if any(type(item) is not Deliverability for item in deliverability):
        raise TypeError("feasibility requires Deliverability")
    return _assess(duty, deliverability, (), ComparisonKind.FEASIBILITY)


def _assess(
    duty: SuppliedDuty,
    delivered: tuple[Delivery, ...] | tuple[Deliverability, ...],
    component_checks: tuple[Check, ...],
    kind: ComparisonKind,
) -> DutyAssessment:
    samples = tuple(item.sample for item in delivered)
    if samples:
        check_flow_intervals(samples)
    schedule = {item.sample.interval: item for item in duty.schedule}
    by_interval = {item.sample.interval: item for item in delivered}
    if set(by_interval) - set(schedule):
        raise ValueError("delivery interval does not match the exact duty interval; no implicit resampling")
    for item in delivered:
        if item.sample.location != schedule[item.sample.interval].sample.location:
            raise ValueError("delivery has incompatible physical location/mapping")
    if duty.applicability not in (DutyApplicability.APPLICABLE, DutyApplicability.HYPOTHETICAL):
        check = Check("applicability", CheckFinding.UNKNOWN, (duty.applicability.value, *duty.reasons))
        return DutyAssessment(duty, (), CheckSummary((check,)), kind)
    rows = []
    for obligation in duty.schedule:
        target = obligation.sample
        actual = by_interval.get(target.interval)
        check_id = f"discharge:{target.interval.start.isoformat()}/{target.interval.end.isoformat()}"
        reasons = ()
        shortfall = None
        volume = None
        finding = CheckFinding.UNKNOWN
        uncertainty = Check(check_id, CheckFinding.UNKNOWN, ("supported uncertainty comparison unavailable",))
        if actual is None:
            reasons = ("required delivery interval omitted",)
        elif (
            interval_use(target) is IntervalUse.EXCLUDED_WARMUP
            or interval_use(actual.sample) is IntervalUse.EXCLUDED_WARMUP
        ):
            reasons = ("excluded warm-up interval cannot establish satisfaction",)
        elif target.presence is not Presence.PRESENT or actual.sample.presence is not Presence.PRESENT:
            reasons = (
                f"duty {target.presence.value}; delivery {actual.sample.presence.value}",
                *target.reasons,
                *actual.sample.reasons,
            )
        elif target.coverage is not Coverage.COMPLETE or actual.sample.coverage is not Coverage.COMPLETE:
            reasons = ("partial interval cannot establish whole-interval satisfaction",)
        elif target.value is not None and actual.sample.value is not None:
            shortfall = Flow(max(Fraction(), target.value.value - actual.sample.value.value))
            volume = Volume(shortfall.value * target.interval.seconds)
            finding = CheckFinding.FAIL if shortfall.value else CheckFinding.PASS
            bounds = actual.sample.uncertainty
            if bounds is not None:
                bounded = (
                    CheckFinding.PASS
                    if bounds.lower.value >= target.value.value
                    else (CheckFinding.FAIL if bounds.upper.value < target.value.value else CheckFinding.UNKNOWN)
                )
                uncertainty = Check(check_id, bounded, (bounds.meaning, bounds.dependence))
        rows.append(
            IntervalAssessment(
                target.interval, obligation, actual, shortfall, volume, Check(check_id, finding, reasons), uncertainty
            )
        )
    # Keep every interval check in the summary, rather than lose incomplete coverage
    # when a known failure survives an unknown interval.
    expected = tuple(row.numerical.check_id for row in rows) + tuple(
        name for name in duty.required_components if name != "discharge"
    )
    if any(check.check_id == "discharge" for check in component_checks):
        raise ValueError("discharge check is computed, not supplied")
    summary = aggregate_checks(expected, tuple(row.numerical for row in rows) + component_checks)
    return DutyAssessment(duty, tuple(rows), summary, kind)
