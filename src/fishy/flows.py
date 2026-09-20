"""flow_observations : LocatedIntervalReadings → AttributedFlowSamples; aggregate_flow preserves volume."""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

import polars as pl

from fishy.evidence import Provenance
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

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location) or not isinstance(self.interval, Interval):
            raise TypeError("flow sample requires typed location and interval")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("flow sample requires Provenance")
        if not isinstance(self.presence, Presence) or not isinstance(self.coverage, Coverage):
            raise TypeError("presence and coverage require domain enums")
        if self.value is not None and not isinstance(self.value, Flow):
            raise TypeError("flow sample value requires Flow")
        object.__setattr__(self, "reasons", tuple(self.reasons))
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


def check_flow_intervals(samples: tuple[FlowSample, ...]) -> None:
    """Refuse duplicates/overlap and mixed identities; retain gaps rather than filling."""
    if not samples:
        raise ValueError("flow input must identify at least one interval")
    first = samples[0]
    for sample in samples:
        if sample.location != first.location or sample.provenance != first.provenance:
            raise ValueError("flow samples have incompatible location or source/scenario/member versions")
    ordered = sorted(samples, key=lambda sample: sample.interval.start)
    for before, after in zip(ordered, ordered[1:], strict=False):
        if before.interval.end > after.interval.start:
            raise ValueError("duplicate or overlapping flow intervals")


def aggregate_flow(samples: tuple[FlowSample, ...]) -> FlowSample:
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
    reasons = tuple(dict.fromkeys(reason for sample in ordered for reason in sample.reasons))
    resolution = "aggregation loses within-interval resolution; no subinterval compliance inference"
    if any(s.presence is not Presence.PRESENT or s.coverage is not Coverage.COMPLETE for s in ordered):
        return FlowSample(
            first.location,
            interval,
            None,
            Presence.UNSUPPORTED,
            first.provenance,
            reasons=(*reasons, "incomplete or unsupported aggregation input", resolution),
        )
    volume = sum((interval_volume(s.value, s.interval).value for s in ordered if s.value is not None), Fraction())
    return FlowSample(
        first.location,
        interval,
        mean_discharge(Volume(volume), interval),
        Presence.PRESENT,
        first.provenance,
        reasons=(*reasons, resolution, "aggregate uncertainty not supplied"),
    )


def daily_discharge(samples: tuple[FlowSample, ...]) -> pl.DataFrame:
    """Exact supported UTC daily means to native diagnostic data; no year-length gate.

    Pass samples[0].provenance and samples[0].location separately to diagnostics.
    Missing/unsupported dates are refused, never dropped or infilled.
    """
    check_flow_intervals(samples)
    ordered = sorted(samples, key=lambda sample: sample.interval.start)
    for sample in ordered:
        if sample.presence is not Presence.PRESENT or sample.coverage is not Coverage.COMPLETE:
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
