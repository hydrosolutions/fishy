"""transfer_characteristic : QualifiedCatchments × HydrologicalCharacteristic → TransferredCharacteristic (pure).

BAFU 2011 Appendix A4 transfers characteristic quantities, not condition classes
or off-plot classifications. Catchment similarity remains supplied site evidence.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import CorrectionState, warmup_restrictions
from fishy.hydrological_condition import MANUAL, AssessmentContext, AssessmentState
from fishy.quantities import Area, Number, finite_number


class Characteristic(StrEnum):
    MEAN_FLOW = "MQ"
    FLOOD_DAILY = "MHQ_daily"
    FLOOD_INSTANTANEOUS = "MHQ_instantaneous"
    LOW_FLOW = "Q347"
    PARDE_COEFFICIENT = "Pk"
    FLOOD_FREQUENCY = "fHQ"
    SEASONALITY_X = "seasonality_x"
    SEASONALITY_Y = "seasonality_y"
    LOW_FLOW_DURATION = "dQ347"
    LOW_FLOW_VARIATION = "CV_Q347"


_UNITS = {
    Characteristic.MEAN_FLOW: "m3/s",
    Characteristic.FLOOD_DAILY: "m3/s",
    Characteristic.FLOOD_INSTANTANEOUS: "m3/s",
    Characteristic.LOW_FLOW: "m3/s",
    Characteristic.PARDE_COEFFICIENT: "1",
    Characteristic.FLOOD_FREQUENCY: "events/year",
    Characteristic.SEASONALITY_X: "1",
    Characteristic.SEASONALITY_Y: "1",
    Characteristic.LOW_FLOW_DURATION: "days",
    Characteristic.LOW_FLOW_VARIATION: "%",
}
_AREA_DEPENDENT = (
    Characteristic.MEAN_FLOW,
    Characteristic.FLOOD_DAILY,
    Characteristic.FLOOD_INSTANTANEOUS,
    Characteristic.LOW_FLOW,
)


@dataclass(frozen=True, init=False)
class HydrologicalValue:
    characteristic: Characteristic
    value: Fraction
    unit: str

    def __init__(self, characteristic: Characteristic, value: Number, unit: str) -> None:
        if not isinstance(characteristic, Characteristic) or unit != _UNITS[characteristic]:
            raise ValueError("characteristic/unit mismatch")
        parsed = finite_number(value)
        if characteristic in (Characteristic.SEASONALITY_X, Characteristic.SEASONALITY_Y):
            if not -1 <= parsed <= 1:
                raise ValueError("seasonality Cartesian component must lie in [-1, 1]")
        elif parsed < 0:
            raise ValueError("hydrological characteristic cannot be negative")
        object.__setattr__(self, "characteristic", characteristic)
        object.__setattr__(self, "value", parsed)
        object.__setattr__(self, "unit", unit)


class Suitability(StrEnum):
    SUITABLE = "suitable"
    UNSUITABLE = "unsuitable"
    UNRESOLVED = "unresolved"


class TransferSetting(StrEnum):
    SAME_WATERCOURSE = "same_watercourse"
    NEIGHBOURING_CATCHMENT = "neighbouring_catchment"


@dataclass(frozen=True)
class TransferQualification:
    setting: TransferSetting
    hydrological_similarity: Suitability
    no_significant_intervening_change: Suitability
    karst_uncertainty: str
    evidence: str

    def __post_init__(self) -> None:
        if not isinstance(self.setting, TransferSetting) or any(
            not isinstance(s, Suitability)
            for s in (
                self.hydrological_similarity,
                self.no_significant_intervening_change,
            )
        ):
            raise TypeError("transfer qualification requires domain states")
        if not all(isinstance(s, str) and s.strip() for s in (self.karst_uncertainty, self.evidence)):
            raise ValueError("transfer requires similarity and karst uncertainty evidence")


@dataclass(frozen=True)
class CatchmentCharacteristic:
    context: AssessmentContext
    area: Area
    value: HydrologicalValue
    qualification: TransferQualification
    catchment_units: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, kind in (
            (self.context, AssessmentContext),
            (self.area, Area),
            (self.value, HydrologicalValue),
            (self.qualification, TransferQualification),
        ):
            if not isinstance(value, kind):
                raise TypeError(f"catchment characteristic requires {kind.__name__}")
        if self.area.value <= 0:
            raise ValueError("donor catchment area must be positive")
        if not isinstance(self.catchment_units, tuple) or any(
            not isinstance(u, str) or not u.strip() for u in self.catchment_units
        ):
            raise TypeError("prepared catchment units require immutable identifiers")
        if len(set(self.catchment_units)) != len(self.catchment_units):
            raise ValueError("duplicate catchment units")


@dataclass(frozen=True)
class TransferredCharacteristic:
    context: AssessmentContext
    area: Area
    value: HydrologicalValue | None
    state: AssessmentState
    donors: tuple[CatchmentCharacteristic, ...]
    route: str
    reasons: tuple[str, ...]
    weights: tuple[Fraction, ...] = ()
    source: str = MANUAL + ", Appendix A4, pp. 106–107"


def _source_restrictions(context: AssessmentContext) -> tuple[str, ...]:
    reasons = warmup_restrictions(context.provenance, context.period)
    if context.provenance.correction_state is CorrectionState.MISSING:
        reasons += ("source correction state is missing",)
    return reasons


def _inputs(context: AssessmentContext, area: Area, donors: tuple[CatchmentCharacteristic, ...]) -> tuple[str, ...]:
    if not isinstance(context, AssessmentContext) or not isinstance(area, Area):
        raise TypeError("transfer requires typed target context and area")
    if area.value <= 0:
        raise ValueError("target area must be positive")
    if not isinstance(donors, tuple) or not donors or any(not isinstance(d, CatchmentCharacteristic) for d in donors):
        raise TypeError("transfer requires immutable catchment characteristics")
    if len({d.context.location for d in donors}) != len(donors):
        raise ValueError("duplicate donor locations")
    first = donors[0].value
    reasons = list(_source_restrictions(context))
    for donor in donors:
        reasons.extend(_source_restrictions(donor.context))
        if donor.value.characteristic is not first.characteristic or donor.value.unit != first.unit:
            raise ValueError("donor characteristics differ")
        if donor.context.period != context.period or any(
            getattr(donor.context.provenance, f) != getattr(context.provenance, f)
            for f in ("scenario", "reference_member", "reference_kind")
        ):
            raise ValueError("donors must represent the same reference/altered state, member and period")
        q = donor.qualification
        if (
            q.hydrological_similarity is not Suitability.SUITABLE
            or q.no_significant_intervening_change is not Suitability.SUITABLE
        ):
            reasons.append("required catchment similarity or absence of intervening significant change not supported")
        if not Fraction(3, 10) <= donor.area.value / area.value <= Fraction(5, 2):
            reasons.append("donor area outside source 30–250% similarity domain")
    return tuple(dict.fromkeys(reasons))


def _result(
    context: AssessmentContext,
    area: Area,
    donors: tuple[CatchmentCharacteristic, ...],
    route: str,
    value: Fraction | float | None,
    reasons: tuple[str, ...],
    weights: tuple[Fraction, ...] = (),
) -> TransferredCharacteristic:
    first = donors[0].value
    output = HydrologicalValue(first.characteristic, value, first.unit) if value is not None else None
    return TransferredCharacteristic(
        context,
        area,
        output,
        AssessmentState.ASSESSED if output is not None else AssessmentState.UNDETERMINED,
        donors,
        route,
        reasons,
        weights,
    )


def _independent(donors: tuple[CatchmentCharacteristic, ...]) -> tuple[str, ...]:
    """Prepared atomic catchment membership proves branch independence."""
    if len(donors) < 2:
        return ()
    if any(not d.catchment_units for d in donors):
        return ("independent donor catchment membership not supplied",)
    units = [u for d in donors for u in d.catchment_units]
    if len(set(units)) != len(units):
        raise ValueError("nested/overlapping donor catchments cannot be summed")
    return ()


def interpolate_discharge(
    context: AssessmentContext,
    area: Area,
    upstream: tuple[CatchmentCharacteristic, ...],
    downstream: CatchmentCharacteristic,
) -> TransferredCharacteristic:
    """A4 linear area interpolation: one or two disjoint upstream donors."""
    if not isinstance(upstream, tuple) or len(upstream) not in (1, 2):
        raise ValueError("A4 interpolation requires one or two upstream stations")
    donors = (*upstream, downstream)
    reasons = _inputs(context, area, donors) + _independent(upstream)
    if downstream.value.characteristic not in _AREA_DEPENDENT:
        raise ValueError("area interpolation applies to MQ, MHQ and Q347 only")
    upstream_area = sum(d.area.value for d in upstream)
    if not upstream_area <= area.value <= downstream.area.value or downstream.area.value <= upstream_area:
        raise ValueError("interpolation requires strictly separated bracketing combined catchment areas")
    if reasons:
        return _result(context, area, donors, "area interpolation", None, reasons)
    upstream_value = sum(d.value.value for d in upstream)
    weight = (area.value - upstream_area) / (downstream.area.value - upstream_area)
    value = upstream_value + (downstream.value.value - upstream_value) * weight
    if value < 0:
        return _result(
            context, area, donors, "area interpolation", None, ("transferred discharge is physically infeasible",)
        )
    return _result(context, area, donors, "area interpolation", value, (), (1 - weight, weight))


def extrapolate_discharge(
    context: AssessmentContext, area: Area, donors: tuple[CatchmentCharacteristic, ...]
) -> TransferredCharacteristic:
    """A4 one/two donor sums; exponent 1 for MQ/Q347, 0.7 for MHQ."""
    reasons = _inputs(context, area, donors) + _independent(donors)
    if len(donors) not in (1, 2) or donors[0].value.characteristic not in _AREA_DEPENDENT:
        raise ValueError("A4 extrapolation requires one/two donors of MQ, MHQ or Q347")
    if reasons:
        return _result(context, area, donors, "area extrapolation", None, reasons)
    ratio = area.value / sum(d.area.value for d in donors)
    total = sum(d.value.value for d in donors)
    if donors[0].value.characteristic in (Characteristic.FLOOD_DAILY, Characteristic.FLOOD_INSTANTANEOUS):
        value = float(total) * float(ratio) ** 0.7
        reasons = ("MHQ exponent 0.7 evaluated in binary64; relative numerical tolerance 1e-12",)
    else:
        value = total * ratio
    if len(donors) == 1 and donors[0].area.value < 5_000_000:
        reasons += (
            "source recommends at least 5 km2 for a sole donor; smaller donor retained with supplied suitability",
        )
    return _result(context, area, donors, "area extrapolation", value, reasons)


def transfer_area_independent(
    context: AssessmentContext, area: Area, donors: tuple[CatchmentCharacteristic, ...]
) -> TransferredCharacteristic:
    """A4 area-difference weights, NOT inverse-distance weights.

    Circular seasonality is transferred via its Cartesian x/y components, never
    by averaging calendar dates across the year boundary.
    """
    reasons = _inputs(context, area, donors)
    if donors[0].value.characteristic in _AREA_DEPENDENT:
        raise ValueError("area-dependent quantity needs discharge transfer")
    if reasons:
        return _result(context, area, donors, "area-independent transfer", None, reasons)
    if len(donors) == 1:
        return _result(context, area, donors, "area-independent transfer", donors[0].value.value, (), (Fraction(1),))
    distances = tuple(abs(d.area.value - area.value) for d in donors)
    total = sum(distances)
    if total == 0:
        return _result(
            context,
            area,
            donors,
            "area-independent transfer",
            None,
            ("A4 weights undefined when every donor area equals target area",),
        )
    weights = tuple((1 - distance / total) / (len(donors) - 1) for distance in distances)
    value = sum((d.value.value * w for d, w in zip(donors, weights, strict=True)), Fraction())
    return _result(context, area, donors, "area-independent transfer", value, (), weights)


@dataclass(frozen=True, init=False)
class SpecificDischarge:
    """Specific MQ/MHQ/Q347 in litres per second per square kilometre."""

    characteristic: Characteristic
    litres_per_second_per_km2: Fraction
    source: str

    def __init__(self, characteristic: Characteristic, value: Number, source: str) -> None:
        if characteristic not in _AREA_DEPENDENT:
            raise ValueError("specific discharge requires MQ, MHQ or Q347")
        parsed = finite_number(value)
        if parsed < 0 or not isinstance(source, str) or not source.strip():
            raise ValueError("specific discharge must be nonnegative and attributable")
        object.__setattr__(self, "characteristic", characteristic)
        object.__setattr__(self, "litres_per_second_per_km2", parsed)
        object.__setattr__(self, "source", source)


@dataclass(frozen=True)
class SpecificDischargeEstimate:
    context: AssessmentContext
    area: Area
    specific: SpecificDischarge
    qualification: TransferQualification
    value: HydrologicalValue | None
    state: AssessmentState
    reasons: tuple[str, ...]
    source: str = MANUAL + ", Appendix A4, specific-discharge extrapolation"


def estimate_specific_discharge(
    context: AssessmentContext, area: Area, specific: SpecificDischarge, qualification: TransferQualification
) -> SpecificDischargeEstimate:
    for value, kind in (
        (context, AssessmentContext),
        (area, Area),
        (specific, SpecificDischarge),
        (qualification, TransferQualification),
    ):
        if not isinstance(value, kind):
            raise TypeError(f"specific-discharge estimate requires {kind.__name__}")
    if area.value <= 0:
        raise ValueError("target area must be positive")
    source_restrictions = _source_restrictions(context)
    if source_restrictions:
        return SpecificDischargeEstimate(
            context, area, specific, qualification, None, AssessmentState.UNDETERMINED, source_restrictions
        )
    if (
        qualification.hydrological_similarity is not Suitability.SUITABLE
        or qualification.no_significant_intervening_change is not Suitability.SUITABLE
    ):
        return SpecificDischargeEstimate(
            context,
            area,
            specific,
            qualification,
            None,
            AssessmentState.UNDETERMINED,
            ("specific discharge representativeness unresolved or unsuitable",),
        )
    value = HydrologicalValue(
        specific.characteristic, specific.litres_per_second_per_km2 * area.value / 1_000_000_000, "m3/s"
    )
    return SpecificDischargeEstimate(context, area, specific, qualification, value, AssessmentState.ASSESSED, ())
