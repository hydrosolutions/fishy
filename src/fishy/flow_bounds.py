"""correct_schedule : FlowSamples × DesignBounds × TimedCoefficients × CorrectionOrder → BoundedSchedule.

Order 179-НҚ (23 July 2025), paragraphs 17(2), 19(3–4), 25–27.
Both arithmetic orders are explicit interpreted candidates, not legal reconciliation.
Natural P99/P50 schedules describe annual design conditions, not daily percentiles.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Computability,
    CorrectionState,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    aggregate_checks,
    permitted_use,
    warmup_restrictions,
)
from fishy.flows import Coverage, FlowSample, Presence, check_flow_intervals
from fishy.quantities import Flow, Volume, interval_volume
from fishy.spatial import Location
from fishy.spawning import TimedCoefficient, coefficient_scope
from fishy.time import Interval


class CorrectionOrder(StrEnum):
    CORRECTION_THEN_BOUNDS = "correction_then_bounds"
    BOUNDS_THEN_CORRECTION = "bounds_then_correction"


class CandidateStatus(StrEnum):
    INTERPRETED = "interpreted_candidate"
    UNRESOLVED = "unresolved"


class BoundConflict(StrEnum):
    CROSSED = "crossed_bounds"
    SUPPRESSED_CORRECTION = "suppressed_correction"
    RAISED_CORRECTION = "lower_bound_overrides_correction"
    LOWER_EXCEEDED = "below_lower_bound"
    UPPER_EXCEEDED = "above_upper_bound"


def _identity(provenance: Provenance) -> tuple[str, str | None, ReferenceKind | None]:
    return provenance.scenario, provenance.reference_member, provenance.reference_kind


def annual_bound_scope(location: Location, interval: Interval, provenance: Provenance) -> EvidenceScope:
    return EvidenceScope(
        "natural_annual_bound", location.reach.identifier, provenance.reference_member, interval, "flow_bounds"
    )


@dataclass(frozen=True)
class AnnualReferenceVolume:
    """An attributed receiving-year volume; missing evidence is not zero."""

    location: Location
    interval: Interval
    value: Volume | None
    presence: Presence
    provenance: Provenance
    findings: EvidenceFindings | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.interval, Interval):
            raise TypeError("annual reference needs Location and Interval")
        start, end = self.interval.start, self.interval.end
        if (
            (start.month, start.day, start.hour, start.minute, start.second, start.microsecond) != (1, 1, 0, 0, 0, 0)
            or (end.month, end.day, end.hour, end.minute, end.second, end.microsecond) != (1, 1, 0, 0, 0, 0)
            or end.year != start.year + 1
        ):
            raise ValueError("annual reference requires one whole Gregorian accounting year")
        if not isinstance(self.presence, Presence) or not isinstance(self.provenance, Provenance):
            raise TypeError("annual reference needs typed presence/provenance")
        if self.value is not None and not isinstance(self.value, Volume):
            raise TypeError("annual reference needs Volume")
        if self.presence is Presence.PRESENT and self.value is None:
            raise ValueError("present annual reference needs a volume")
        if self.presence is not Presence.PRESENT and self.value is not None:
            raise ValueError("unavailable annual reference cannot carry a volume")
        if self.findings is not None and not isinstance(self.findings, EvidenceFindings):
            raise TypeError("annual reference findings require EvidenceFindings")
        if not isinstance(self.reasons, tuple) or any(not isinstance(s, str) or not s for s in self.reasons):
            raise TypeError("annual reference reasons require immutable nonempty text")
        if self.presence is not Presence.PRESENT and not self.reasons:
            raise ValueError("unavailable annual reference needs reasons")


@dataclass(frozen=True)
class DesignBounds:
    """Preserve three distinct schedules and two separate annual source bounds.

    The effective interval lower bound is max(recorded minimum, natural P99).
    No bound construction, daily percentile estimation or interpolation is implied.
    """

    recorded_minimum: tuple[FlowSample, ...]
    natural_p99: tuple[FlowSample, ...]
    natural_p50: tuple[FlowSample, ...]
    annual_p99: AnnualReferenceVolume
    annual_p50: AnnualReferenceVolume
    source_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_version, str) or not self.source_version.strip():
            raise ValueError("source version required")
        for samples in (self.recorded_minimum, self.natural_p99, self.natural_p50):
            if not isinstance(samples, tuple) or any(not isinstance(s, FlowSample) for s in samples):
                raise TypeError("bounds require immutable FlowSample schedules")
            check_flow_intervals(samples)
        if not isinstance(self.annual_p99, AnnualReferenceVolume) or not isinstance(
            self.annual_p50, AnnualReferenceVolume
        ):
            raise TypeError("annual bounds require AnnualReferenceVolume")
        if (self.annual_p99.location, self.annual_p99.interval, _identity(self.annual_p99.provenance)) != (
            self.annual_p50.location,
            self.annual_p50.interval,
            _identity(self.annual_p50.provenance),
        ):
            raise ValueError("annual bounds have incompatible location, calendar or reference")


@dataclass(frozen=True)
class BoundAdjustment:
    """Signed m3/s delta at one named operation; no lost/clipped adjustment."""

    constraint: str
    before: Flow
    after: Flow

    @property
    def delta_m3_s(self) -> Fraction:
        return self.after.value - self.before.value


@dataclass(frozen=True)
class IntervalCorrection:
    original: FlowSample
    coefficient: TimedCoefficient | None
    lower: Flow | None
    upper: Flow | None
    pre_bound: Flow | None
    adjustments: tuple[BoundAdjustment, ...]
    corrected: FlowSample
    conflicts: tuple[BoundConflict, ...]
    scientific_use: Check


@dataclass(frozen=True)
class BoundedSchedule:
    intervals: tuple[IntervalCorrection, ...]
    bounds: DesignBounds
    order: CorrectionOrder | None
    status: CandidateStatus
    actual_volume: Volume | None
    supported_volume: Volume
    annual_checks: CheckSummary
    annual_scientific_use: tuple[Check, ...]
    reasons: tuple[str, ...]

    @property
    def samples(self) -> tuple[FlowSample, ...]:
        return tuple(item.corrected for item in self.intervals)


def _supported(sample: FlowSample) -> bool:
    return (
        sample.presence is Presence.PRESENT
        and sample.coverage is Coverage.COMPLETE
        and not warmup_restrictions(sample.provenance, sample.interval)
    )


def _annual_supported(bound: AnnualReferenceVolume) -> bool:
    if bound.presence is not Presence.PRESENT or warmup_restrictions(bound.provenance, bound.interval):
        return False
    if bound.findings is None:
        return True  # numerical source value remains useful; scientific permission is separate
    return (
        bound.findings.scope == annual_bound_scope(bound.location, bound.interval, bound.provenance)
        and bound.findings.provenance == bound.provenance
        and bound.findings.computability is Computability.COMPUTABLE
        and bound.findings.numerical_validity is NumericalValidity.VALID
    )


def _annual_permission(bound: AnnualReferenceVolume) -> Check:
    if bound.findings is None:
        return Check("annual_bound_use", CheckFinding.UNKNOWN, ("scientific findings not supplied",))
    if bound.findings.provenance != bound.provenance:
        return Check("annual_bound_use", CheckFinding.UNKNOWN, ("finding version differs from annual bound",))
    return permitted_use(bound.findings, annual_bound_scope(bound.location, bound.interval, bound.provenance))


def _coefficient_support(coefficient: TimedCoefficient | None) -> tuple[bool, Check]:
    if coefficient is None:
        return False, Check("coefficient_use", CheckFinding.UNKNOWN, ("timed coefficient missing",))
    scope = coefficient_scope(coefficient.location, coefficient.interval, coefficient.provenance)
    evidence = coefficient.findings
    valid = (
        evidence is not None
        and coefficient.presence is Presence.PRESENT
        and coefficient.value is not None
        and evidence.scope == scope
        and evidence.provenance == coefficient.provenance
        and evidence.computability is Computability.COMPUTABLE
        and evidence.numerical_validity is NumericalValidity.VALID
        and not warmup_restrictions(coefficient.provenance, coefficient.interval)
    )
    if evidence is None:
        main = Check("coefficient_use", CheckFinding.UNKNOWN, ("coefficient evidence missing",))
    elif evidence.provenance != coefficient.provenance:
        main = Check("coefficient_use", CheckFinding.UNKNOWN, ("finding version differs from coefficient",))
    else:
        main = permitted_use(evidence, scope)
    checks = [Check("main", main.finding, main.reasons)]
    checks.append(
        Check(
            "coefficient_availability",
            CheckFinding.PASS if valid else CheckFinding.UNKNOWN,
            ("coefficient numerical/temporal availability is assessed separately",),
        )
    )
    required = coefficient.required_support
    applicability = tuple(s for s in required if s.product == "spawning_timing_applicability")
    if len(applicability) != 1 or any(a.period.seconds > 366 * 86400 for a in applicability):
        checks.append(
            Check(
                "single_biological_cycle",
                CheckFinding.UNKNOWN,
                ("one explicit biological applicability cycle of at most 366 days is required",),
            )
        )
        applicability = ()
    if not any(
        a.period.start <= coefficient.interval.start and coefficient.interval.end <= a.period.end for a in applicability
    ):
        checks.append(
            Check(
                "temporal_applicability",
                CheckFinding.UNKNOWN,
                ("no declared biological applicability covers the requested interval",),
            )
        )
    for i, biological_scope in enumerate(s for s in required if s.product == "spawning_timing"):
        if not any(
            a.period.start <= biological_scope.period.start and biological_scope.period.end <= a.period.end
            for a in applicability
        ):
            checks.append(
                Check(
                    f"season_applicability_{i}",
                    CheckFinding.UNKNOWN,
                    ("biological season is outside declared temporal applicability",),
                )
            )
    if not any(s.product == "spawning_timing" for s in required):
        checks.append(
            Check("required_biology", CheckFinding.UNKNOWN, ("required biological support scopes were not declared",))
        )
    for i, expected in enumerate(required):
        matches = tuple(f for f in coefficient.supporting_evidence if f.scope == expected)
        if len(matches) != 1:
            checks.append(
                Check(f"required_{i}", CheckFinding.UNKNOWN, ("required supporting evidence missing or duplicated",))
            )
    for i, support in enumerate(coefficient.supporting_evidence):
        # Whole biological-season scopes can legitimately differ from monthly/daily
        # coefficient intervals. The declared scope, not the finding's own scope,
        # controls positive admission; every relied-upon rejection is retained.
        aligned = (
            support.provenance == coefficient.provenance
            and support.scope.reach == scope.reach
            and support.scope.member == scope.member
            and support.scope.intended_use == scope.intended_use
        )
        if not aligned or warmup_restrictions(support.provenance, support.scope.period):
            finding = Check(
                f"support_{i}", CheckFinding.UNKNOWN, ("supporting evidence does not bind coefficient identity/use",)
            )
        else:
            assessed = permitted_use(support, support.scope)
            if support.scope not in required and assessed.finding is CheckFinding.PASS:
                finding = Check(
                    f"support_{i}", CheckFinding.UNKNOWN, ("supporting scope not declared by coefficient derivation",)
                )
            else:
                finding = Check(f"support_{i}", assessed.finding, assessed.reasons)
        checks.append(finding)
    summary = aggregate_checks(tuple(c.check_id for c in checks), tuple(checks))
    return valid, Check(
        "coefficient_use", summary.finding, tuple(reason for check in checks for reason in check.reasons)
    )


def correct_schedule(
    samples: tuple[FlowSample, ...],
    bounds: DesignBounds,
    coefficients: tuple[TimedCoefficient | None, ...],
    order: CorrectionOrder | None,
    provenance: Provenance,
) -> BoundedSchedule:
    """Apply one explicitly selected candidate, preserving unresolved and failed intervals.

    Inputs must be caller-aligned whole intervals. A known crossing anywhere (including
    annual bounds) stops both operators before multiplication. Missing bounds affect
    only their interval; an incomplete schedule has no fabricated annual total.
    """
    if not isinstance(samples, tuple) or any(not isinstance(s, FlowSample) for s in samples):
        raise TypeError("samples require an immutable FlowSample schedule")
    check_flow_intervals(samples)
    if not isinstance(bounds, DesignBounds) or not isinstance(provenance, Provenance):
        raise TypeError("typed bounds and result provenance required")
    if order is not None and not isinstance(order, CorrectionOrder):
        raise TypeError("correction order requires explicit enum or None")
    if (
        provenance.production_method is ProductionMethod.OBSERVED
        or provenance.correction_state is not CorrectionState.CORRECTED
    ):
        raise ValueError("candidate provenance must describe a non-observed corrected calculation")
    if not isinstance(coefficients, tuple) or any(
        c is not None and not isinstance(c, TimedCoefficient) for c in coefficients
    ):
        raise TypeError("coefficients require immutable timed records or explicit None")
    sequences = (bounds.recorded_minimum, bounds.natural_p99, bounds.natural_p50)
    if any(len(s) != len(samples) for s in sequences) or len(coefficients) != len(samples):
        raise ValueError("every interval needs explicit bound/coefficient records, including missing")
    annual = bounds.annual_p99
    for i, sample in enumerate(samples):
        if sample.location != annual.location or _identity(sample.provenance) != _identity(provenance):
            raise ValueError("candidate and annual bound require the same location/scenario/reference")
        if _identity(sample.provenance) != _identity(annual.provenance):
            raise ValueError("annual bound reference differs from candidate")
        if not annual.interval.start <= sample.interval.start < sample.interval.end <= annual.interval.end:
            raise ValueError("sample is outside the annual accounting interval")
        for schedule in sequences:
            bound = schedule[i]
            if (bound.location, bound.interval, _identity(bound.provenance)) != (
                sample.location,
                sample.interval,
                _identity(sample.provenance),
            ):
                raise ValueError("bound schedule must be aligned in location, interval and reference")
        coefficient = coefficients[i]
        if coefficient is not None and (
            coefficient.location,
            coefficient.interval,
            _identity(coefficient.provenance),
        ) != (sample.location, sample.interval, _identity(sample.provenance)):
            raise ValueError("coefficient must be aligned in location, interval and reference")
    crossings: list[str] = []
    for i, (recorded, low, high) in enumerate(zip(*sequences, strict=True)):
        if (
            _supported(high)
            and high.value is not None
            and any(
                _supported(item) and item.value is not None and item.value.value > high.value.value
                for item in (recorded, low)
            )
        ):
            crossings.append(f"crossed interval bounds: {i}")
    if (
        _annual_supported(bounds.annual_p99)
        and _annual_supported(bounds.annual_p50)
        and bounds.annual_p99.value is not None
        and bounds.annual_p50.value is not None
        and bounds.annual_p99.value.value > bounds.annual_p50.value.value
    ):
        crossings.append("crossed annual bounds")
    outputs: list[IntervalCorrection] = []
    for i, sample in enumerate(samples):
        recorded, low, high = (s[i] for s in sequences)
        coefficient = coefficients[i]
        coefficient_ok, permission = _coefficient_support(coefficient)
        available = all(_supported(s) for s in (sample, recorded, low, high))
        lower = (
            Flow(max(recorded.value.value, low.value.value))
            if _supported(recorded) and _supported(low) and recorded.value is not None and low.value is not None
            else None
        )
        upper = high.value if _supported(high) else None
        reasons = list(crossings)
        if order is None:
            reasons.append("correction order unresolved")
        if not available:
            reasons.append("flow or design bound missing, partial, unsupported or excluded")
        if not coefficient_ok:
            reasons.append("timed coefficient numerical support unresolved")
        if reasons:
            corrected = FlowSample(
                sample.location,
                sample.interval,
                None,
                Presence.UNSUPPORTED,
                provenance,
                coverage=Coverage.PARTIAL,
                reasons=tuple(reasons),
                components=(sample, recorded, low, high),
            )
            outputs.append(
                IntervalCorrection(
                    sample,
                    coefficient,
                    lower,
                    upper,
                    None,
                    (),
                    corrected,
                    (BoundConflict.CROSSED,) if crossings else (),
                    permission,
                )
            )
            continue
        assert sample.value is not None and lower is not None and upper is not None
        assert coefficient is not None and coefficient.value is not None
        prebound = (
            Flow(sample.value.value * coefficient.value)
            if order is CorrectionOrder.CORRECTION_THEN_BOUNDS
            else sample.value
        )
        assert recorded.value is not None and low.value is not None
        after_recorded = Flow(max(prebound.value, recorded.value.value))
        after_low = Flow(max(after_recorded.value, low.value.value))
        after_high = Flow(min(after_low.value, upper.value))
        adjustments = (
            BoundAdjustment("recorded_long_term_minimum", prebound, after_recorded),
            BoundAdjustment("natural_annual_P99_hydrograph", after_recorded, after_low),
            BoundAdjustment("natural_annual_P50_hydrograph", after_low, after_high),
        )
        result = (
            after_high
            if order is CorrectionOrder.CORRECTION_THEN_BOUNDS
            else Flow(after_high.value * coefficient.value)
        )
        conflicts: list[BoundConflict] = []
        if order is CorrectionOrder.CORRECTION_THEN_BOUNDS:
            if result.value < prebound.value:
                conflicts.append(BoundConflict.SUPPRESSED_CORRECTION)
            elif result.value > prebound.value:
                conflicts.append(BoundConflict.RAISED_CORRECTION)
        if result.value < lower.value:
            conflicts.append(BoundConflict.LOWER_EXCEEDED)
        if result.value > upper.value:
            conflicts.append(BoundConflict.UPPER_EXCEEDED)
        corrected = FlowSample(
            sample.location,
            sample.interval,
            result,
            Presence.PRESENT,
            provenance,
            reasons=("interpreted candidate; correction priority unresolved", "uncertainty propagation not supplied"),
            components=(sample, recorded, low, high),
        )
        outputs.append(
            IntervalCorrection(
                sample, coefficient, lower, upper, prebound, adjustments, corrected, tuple(conflicts), permission
            )
        )
    supported_volume = Volume(
        sum(
            (
                interval_volume(item.corrected.value, item.corrected.interval).value
                for item in outputs
                if item.corrected.value is not None
            ),
            Fraction(),
        )
    )
    ordered = sorted(samples, key=lambda s: s.interval.start)
    full = (
        ordered[0].interval.start == annual.interval.start
        and ordered[-1].interval.end == annual.interval.end
        and all(a.interval.end == b.interval.start for a, b in zip(ordered, ordered[1:], strict=False))
        and all(item.corrected.value is not None for item in outputs)
    )
    total = supported_volume if full else None
    checks: list[Check] = []
    for name, bound, lower_test in (
        ("annual_P99_lower", bounds.annual_p99, True),
        ("annual_P50_upper", bounds.annual_p50, False),
    ):
        if not _annual_supported(bound) or bound.value is None:
            finding = CheckFinding.UNKNOWN
        elif not lower_test and supported_volume.value > bound.value.value:
            # Missing nonnegative flows cannot undo an already known upper failure.
            finding = CheckFinding.FAIL
        elif total is None:
            finding = CheckFinding.UNKNOWN
        else:
            satisfied = total.value >= bound.value.value if lower_test else total.value <= bound.value.value
            finding = CheckFinding.PASS if satisfied else CheckFinding.FAIL
        checks.append(Check(name, finding, ("actual recalculated volume; no renormalisation",)))
    reasons = tuple(crossings) + ("source priority remains unresolved under either arithmetic interpretation",)
    return BoundedSchedule(
        tuple(outputs),
        bounds,
        order,
        CandidateStatus.INTERPRETED
        if all(item.corrected.value is not None for item in outputs)
        else CandidateStatus.UNRESOLVED,
        total,
        supported_volume,
        aggregate_checks(("annual_P99_lower", "annual_P50_upper"), tuple(checks)),
        (_annual_permission(bounds.annual_p99), _annual_permission(bounds.annual_p50)),
        reasons,
    )
