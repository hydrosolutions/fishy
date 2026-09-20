"""seasonal_schedule : InitialAllocation × SeasonalShape → AttributedFlowSamples (pure).

appendix1_report : InitialAllocation × AttributedFlowSamples → MonthlyAnnualReport.
Uses elapsed durations, never daily disaggregation or post-correction normalisation.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from fractions import Fraction

from fishy.basin import Basin, River
from fishy.evidence import EvidenceFindings, ProductionMethod, Provenance
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, check_flow_intervals, interval_use
from fishy.kazakh_allocation import (
    AllocationStatus,
    DesignClass,
    InitialAllocation,
    NaturalExceedance,
    evidence_reasons,
    shifted_class,
)
from fishy.quantities import Flow, Volume, finite_number
from fishy.spatial import Location
from fishy.time import Interval


class ShapeChoice(StrEnum):
    DESIGN_CLASS = "design_class_shape"
    SHIFTED_CLASS = "shifted_class_shape"


@dataclass(frozen=True)
class ShapeOrdinate:
    interval: Interval
    value: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.interval, Interval):
            raise TypeError("shape ordinate requires Interval")
        value = finite_number(self.value)
        if value < 0:
            raise ValueError("shape must be nonnegative")
        object.__setattr__(self, "value", value)


def _year(period: Interval) -> None:
    start, end = period.start, period.end
    if start != datetime(start.year, 1, 1, tzinfo=start.tzinfo) or end != datetime(
        start.year + 1, 1, 1, tzinfo=start.tzinfo
    ):
        raise ValueError("accounting period must be a complete Gregorian calendar year")


@dataclass(frozen=True)
class SeasonalShape:
    location: Location
    year: Interval
    exceedance: NaturalExceedance
    ordinates: tuple[ShapeOrdinate, ...]
    provenance: Provenance
    evidence: EvidenceFindings

    def __post_init__(self) -> None:
        _year(self.year)
        if not isinstance(self.location, Location) or not isinstance(self.exceedance, NaturalExceedance):
            raise TypeError("shape requires location and natural exceedance")
        if (
            not isinstance(self.ordinates, tuple)
            or not self.ordinates
            or any(not isinstance(p, ShapeOrdinate) for p in self.ordinates)
        ):
            raise TypeError("shape needs immutable nonempty ordinates")
        if not isinstance(self.provenance, Provenance) or not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("shape requires provenance and evidence")
        points = self.ordinates
        if points[0].interval.start != self.year.start or points[-1].interval.end != self.year.end:
            raise ValueError("shape must cover receiving calendar")
        if any(a.interval.end != b.interval.start for a, b in zip(points, points[1:], strict=False)):
            raise ValueError("shape intervals must be ordered, complete and nonoverlapping")
        if sum((p.value * p.interval.seconds for p in points), Fraction()) != self.year.seconds:
            raise ValueError("duration-weighted shape mean must equal one exactly")


@dataclass(frozen=True)
class SeasonalAllocation:
    initial: InitialAllocation
    choice: ShapeChoice | None
    shape: SeasonalShape | None
    samples: tuple[FlowSample, ...]
    reasons: tuple[str, ...]


def seasonal_schedule(
    initial: InitialAllocation, year: Interval, choice: ShapeChoice | None, shape: SeasonalShape | None
) -> SeasonalAllocation:
    """Select one supported imported shape. Missing choice preserves initial magnitude."""
    _year(year)
    reasons = initial.reasons
    if choice is not None and not isinstance(choice, ShapeChoice):
        raise TypeError("shape choice requires ShapeChoice")
    if choice is None:
        reasons += ("seasonal shape interpretation missing",)
    if shape is None:
        reasons += ("supported seasonal shape missing",)
    else:
        reference = initial.reference
        if shape.year != year or shape.location != reference.location:
            raise ValueError("shape receiving year/location mismatch")
        if any(
            getattr(shape.provenance, f) != getattr(reference.provenance, f)
            for f in ("scenario", "reference_member", "reference_kind")
        ):
            raise ValueError("shape and annual reference must share scenario/reference basis")
        expected = (
            NaturalExceedance(initial.design.value)
            if choice is ShapeChoice.DESIGN_CLASS
            else shifted_class(initial.design)
        )
        if choice is not None and shape.exceedance != expected:
            raise ValueError("shape exceedance disagrees with explicit interpretation")
        reasons += evidence_reasons(
            shape.evidence,
            shape.location,
            year,
            shape.provenance,
            f"seasonal_shape_P{shape.exceedance.value}",
            "seasonal_allocation",
        )
    if reasons or initial.status is not AllocationStatus.SUPPORTED or initial.volume is None or shape is None:
        return SeasonalAllocation(initial, choice, shape, (), reasons or ("initial allocation unsupported",))
    findings = (initial.reference.evidence, *initial.supporting_evidence, shape.evidence)
    if initial.reference.reconstruction is not None:
        findings += (initial.reference.reconstruction,)
    support_notes = tuple(
        note
        for finding in findings
        for note in (
            f"{finding.scope.product}: scientific={finding.scientific_adequacy.value}; "
            f"official={finding.official_admissibility.value}; disclosure={finding.disclosure.value}; "
            f"source={finding.provenance.source}; data={finding.provenance.data_version}",
            *finding.provenance.limitations,
            *(f"{finding.scope.product}: {reason}" for reason in finding.reasons),
            *(
                f"{finding.scope.product}: {restriction.reason}; prohibited uses={restriction.prohibited_uses}"
                for restriction in finding.restrictions
            ),
        )
    )
    production = (
        ProductionMethod.ILLUSTRATIVE
        if any(finding.provenance.production_method is ProductionMethod.ILLUSTRATIVE for finding in findings)
        else ProductionMethod.IMPORTED
    )
    provenance = replace(
        shape.provenance,
        production_method=production,
        dependencies=(
            *shape.provenance.dependencies,
            initial.source,
            initial.reference.provenance.source,
            f"annual route={initial.route}; shape choice={choice}; original shape method={shape.provenance.production_method}",
        ),
        limitations=tuple(
            dict.fromkeys(
                (
                    *shape.provenance.limitations,
                    *initial.reference.provenance.limitations,
                    *support_notes,
                    "interpreted initial allocation, not a complete ecological assessment",
                )
            )
        ),
    )
    samples = tuple(
        FlowSample(
            shape.location,
            p.interval,
            Flow(initial.volume.value * p.value / year.seconds),
            Presence.PRESENT,
            provenance,
        )
        for p in shape.ordinates
    )
    return SeasonalAllocation(initial, choice, shape, samples, ())


@dataclass(frozen=True)
class ReportCell:
    interval: Interval
    flow: Flow | None
    volume: Volume | None
    annual_share_percent: Fraction | None
    presence: Presence
    reasons: tuple[str, ...]

    @property
    def million_m3(self) -> Fraction | None:
        return None if self.volume is None else self.volume.value / 1_000_000


@dataclass(frozen=True)
class ReportingIdentity:
    basin: Basin
    river: River
    location: Location
    water_management_section_code: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.basin, Basin)
            or not isinstance(self.river, River)
            or not isinstance(self.location, Location)
        ):
            raise TypeError("report requires basin, river and physical location identities")
        if not isinstance(self.water_management_section_code, str) or not self.water_management_section_code.strip():
            raise ValueError("source water-management section code required")


@dataclass(frozen=True)
class MonthlyAnnualReport:
    initial: InitialAllocation
    year: Interval
    monthly: tuple[ReportCell, ...]
    annual: ReportCell
    samples: tuple[FlowSample, ...]
    stage: str
    identity: ReportingIdentity | None
    limitations: tuple[str, ...]

    @property
    def design(self) -> DesignClass:
        return self.initial.design

    @property
    def location(self) -> Location:
        return self.initial.reference.location


def _cell(period: Interval, samples: tuple[FlowSample, ...]) -> ReportCell:
    relevant = tuple(s for s in samples if s.interval.start < period.end and period.start < s.interval.end)
    if not relevant:
        return ReportCell(period, None, None, None, Presence.MISSING, ("no schedule for reporting interval",))
    if any(s.interval.start < period.start or s.interval.end > period.end for s in relevant):
        return ReportCell(
            period, None, None, None, Presence.UNSUPPORTED, ("coarse interval mean cannot establish subinterval flow",)
        )
    complete = (
        relevant[0].interval.start == period.start
        and relevant[-1].interval.end == period.end
        and all(a.interval.end == b.interval.start for a, b in zip(relevant, relevant[1:], strict=False))
    )
    reasons = tuple(dict.fromkeys(r for s in relevant for r in s.reasons))
    if not complete or any(
        s.presence is not Presence.PRESENT
        or s.coverage is not Coverage.COMPLETE
        or interval_use(s) is IntervalUse.EXCLUDED_WARMUP
        for s in relevant
    ):
        states = {s.presence for s in relevant}
        presence = next(iter(states)) if len(states) == 1 and Presence.PRESENT not in states else Presence.UNSUPPORTED
        return ReportCell(
            period, None, None, None, presence, (*reasons, "incomplete or unavailable reporting coverage")
        )
    volume = Volume(sum((s.value.value * s.interval.seconds for s in relevant if s.value is not None), Fraction()))
    return ReportCell(period, Flow(volume.value / period.seconds), volume, None, Presence.PRESENT, reasons)


class ScheduleStage(StrEnum):
    INITIAL = "initial_seasonal"
    CORRECTED = "corrected"
    OPERATIONAL = "operational_year_adjustment"


def appendix1_report(
    initial: InitialAllocation,
    year: Interval,
    samples: tuple[FlowSample, ...],
    stage: ScheduleStage,
    identity: ReportingIdentity | None = None,
) -> MonthlyAnnualReport:
    """Report actual supplied schedule, including corrections; zero shares are undefined.

    Missing schedules retain the independently supported initial annual magnitude
    on ``report.initial``; they do not fabricate monthly values.
    """
    _year(year)
    if not isinstance(stage, ScheduleStage):
        raise TypeError("report requires explicit schedule stage")
    if not isinstance(samples, tuple):
        raise TypeError("report samples require an immutable tuple")
    if samples:
        check_flow_intervals(samples)
        reference = initial.reference
        if any(
            s.location != reference.location or s.interval.start < year.start or s.interval.end > year.end
            for s in samples
        ):
            raise ValueError("schedule location/year mismatch")
        if any(
            any(
                getattr(s.provenance, f) != getattr(reference.provenance, f)
                for f in ("scenario", "reference_member", "reference_kind")
            )
            for s in samples
        ):
            raise ValueError("schedule and initial allocation identity mismatch")
    ordered = tuple(sorted(samples, key=lambda s: s.interval.start))
    annual = _cell(year, ordered)
    months = tuple(
        Interval(
            datetime(year.start.year, m, 1, tzinfo=year.start.tzinfo),
            datetime(year.start.year + (m == 12), m % 12 + 1, 1, tzinfo=year.start.tzinfo),
        )
        for m in range(1, 13)
    )
    monthly = tuple(_cell(month, ordered) for month in months)
    if annual.volume is not None and annual.volume.value > 0:
        monthly = tuple(
            replace(cell, annual_share_percent=cell.volume.value / annual.volume.value * 100)
            if cell.volume is not None
            else cell
            for cell in monthly
        )
        annual = replace(annual, annual_share_percent=Fraction(100))
    else:
        reason = "zero annual volume has undefined shares" if annual.volume is not None else "annual total unavailable"
        monthly = tuple(replace(cell, reasons=(*cell.reasons, reason)) for cell in monthly)
        annual = replace(annual, reasons=(*annual.reasons, reason))
    if identity is not None and identity.location != initial.reference.location:
        raise ValueError("reporting identity differs from calculation location")
    limitations = ("basin/river reporting identity not supplied",) if identity is None else ()
    return MonthlyAnnualReport(initial, year, monthly, annual, ordered, stage.value, identity, limitations)
