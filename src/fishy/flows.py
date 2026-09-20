"""flow_observations : LocatedIntervalReadings → AttributedFlowSamples; aggregate_flow preserves volume."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

import polars as pl

from fishy.evidence import CorrectionState, Provenance
from fishy.quantities import Flow, FlowBounds, Volume, interval_volume, mean_discharge
from fishy.spatial import Location
from fishy.time import Interval


class Presence(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    ABSENT = "absent"
    OUTSIDE_HORIZON = "outside_horizon"
    UNSUPPORTED = "unsupported"
    DRY = "dry_undefined_concentration"


class Coverage(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


@dataclass(frozen=True)
class FlowSample:
    """A scalar reading, not an array wrapper; missing evidence never becomes zero."""

    location: Location
    interval: Interval
    value: Flow | None
    presence: Presence
    provenance: Provenance
    uncertainty: FlowBounds | None = None
    coverage: Coverage = Coverage.COMPLETE
    reasons: tuple[str, ...] = ()
    components: tuple[FlowSample, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.interval, Interval):
            raise TypeError("flow sample requires typed location and interval")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("flow sample requires Provenance")
        if self.provenance.correction_state is CorrectionState.MISSING and self.value is not None:
            raise ValueError("missing observation status cannot carry a numerical value")
        if not isinstance(self.presence, Presence) or not isinstance(self.coverage, Coverage):
            raise TypeError("presence and coverage require domain enums")
        if self.value is not None and not isinstance(self.value, Flow):
            raise TypeError("flow sample value requires Flow")
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if not isinstance(self.components, tuple) or any(not isinstance(item, FlowSample) for item in self.components):
            raise TypeError("aggregate components require immutable FlowSample records")
        if self.presence is Presence.PRESENT and self.value is None:
            raise ValueError("present flow needs a value, including explicit zero")
        if (
            self.presence in (Presence.MISSING, Presence.ABSENT, Presence.OUTSIDE_HORIZON, Presence.DRY)
            and self.value is not None
        ):
            raise ValueError("missing/absent/outside/dry-undefined flow cannot carry a value")
        if self.presence is Presence.DRY:
            raise ValueError("dry undefined denotes concentration, not zero water discharge")
        if (self.presence is not Presence.PRESENT or self.coverage is Coverage.PARTIAL) and not self.reasons:
            raise ValueError("unavailable or partial flow requires attributable reasons")
        if self.uncertainty is not None:
            if not isinstance(self.uncertainty, FlowBounds):
                raise TypeError("flow uncertainty requires FlowBounds")
            if (
                self.value is None
                or not self.uncertainty.lower.value <= self.value.value <= self.uncertainty.upper.value
            ):
                raise ValueError("flow value must lie inside its supplied uncertainty bounds")


class IntervalUse(StrEnum):
    ELIGIBLE = "eligible"
    EXCLUDED_WARMUP = "excluded_warmup"


def interval_use(sample: FlowSample) -> IntervalUse:
    """Warm-up exclusions apply even when their diagnostic numbers are present."""
    if any(
        sample.interval.start < period.end and period.start < sample.interval.end
        for period in sample.provenance.excluded_warmup
    ):
        return IntervalUse.EXCLUDED_WARMUP
    return IntervalUse.ELIGIBLE


def check_flow_intervals(samples: tuple[FlowSample, ...]) -> None:
    """Refuse duplicates/overlap and mixed identities; retain gaps rather than filling."""
    if not samples:
        raise ValueError("flow input must identify at least one interval")
    first = samples[0]
    for sample in samples:
        if sample.location != first.location:
            raise ValueError("flow samples have incompatible physical location/mapping")
        if any(
            getattr(sample.provenance, field) != getattr(first.provenance, field)
            for field in ("scenario", "reference_member", "reference_kind")
        ):
            raise ValueError("flow samples have incompatible scenario or reference identity")
    ordered = sorted(samples, key=lambda sample: sample.interval.start)
    for before, after in zip(ordered, ordered[1:], strict=False):
        if before.interval.end > after.interval.start:
            raise ValueError("duplicate or overlapping flow intervals")


def aggregate_flow(samples: tuple[FlowSample, ...], *, provenance: Provenance | None = None) -> FlowSample:
    """Whole contiguous intervals only; absent/unsupported inputs are not skipped.

    Aggregated uncertainty needs an externally supported dependence treatment.
    Numeric aggregation does not silently create uncertainty bounds.
    """
    check_flow_intervals(samples)
    ordered = sorted(samples, key=lambda sample: sample.interval.start)
    if any(a.interval.end != b.interval.start for a, b in zip(ordered, ordered[1:], strict=False)):
        raise ValueError("aggregation refuses uncovered gaps")
    interval = Interval(ordered[0].interval.start, ordered[-1].interval.end)
    first = ordered[0]
    if provenance is None:
        if any(sample.provenance != first.provenance for sample in ordered):
            raise ValueError("heterogeneous readings require explicit aggregate provenance")
        provenance = first.provenance
    if any(
        getattr(provenance, field) != getattr(first.provenance, field)
        for field in ("scenario", "reference_member", "reference_kind")
    ):
        raise ValueError("aggregate provenance must retain scenario and reference identity")
    reasons = tuple(dict.fromkeys(reason for sample in ordered for reason in sample.reasons))
    resolution = "aggregation loses within-interval resolution; no subinterval compliance inference"
    if any(
        s.presence is not Presence.PRESENT
        or s.coverage is not Coverage.COMPLETE
        or interval_use(s) is IntervalUse.EXCLUDED_WARMUP
        for s in ordered
    ):
        return FlowSample(
            first.location,
            interval,
            None,
            Presence.UNSUPPORTED,
            provenance,
            reasons=(*reasons, "incomplete or unsupported aggregation input", resolution),
            components=tuple(ordered),
        )
    volume = sum((interval_volume(s.value, s.interval).value for s in ordered if s.value is not None), Fraction())
    return FlowSample(
        first.location,
        interval,
        mean_discharge(Volume(volume), interval),
        Presence.PRESENT,
        provenance,
        reasons=(*reasons, resolution, "aggregate uncertainty not supplied"),
        components=tuple(ordered),
    )


def daily_discharge(samples: tuple[FlowSample, ...]) -> pl.DataFrame:
    """Exact supported UTC daily means to native diagnostic data; no year-length gate.

    Keep the input samples for per-interval source/correction history. The frame
    is only the numerical projection, not a replacement provenance record.
    Missing/unsupported dates are refused, never dropped or infilled.
    """
    check_flow_intervals(samples)
    ordered = sorted(samples, key=lambda sample: sample.interval.start)
    for sample in ordered:
        if (
            sample.presence is not Presence.PRESENT
            or sample.coverage is not Coverage.COMPLETE
            or interval_use(sample) is IntervalUse.EXCLUDED_WARMUP
        ):
            raise ValueError("daily diagnostic input includes unavailable or partial flow")
        start = sample.interval.start
        if sample.interval.seconds != 86400 or (start.hour, start.minute, start.second, start.microsecond) != (
            0,
            0,
            0,
            0,
        ):
            raise ValueError("daily means require whole UTC calendar days, not disaggregation")
    return pl.DataFrame(
        {
            "date": [s.interval.start.date() for s in ordered],
            "discharge_m3_s": [float(s.value.value) for s in ordered if s.value is not None],
        },
        schema={"date": pl.Date, "discharge_m3_s": pl.Float64},
    )
