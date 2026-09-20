"""assess_ecological_conditions : ScopedStudyStates × SiteCriteria → EcologicalAssessment.

Pure supplied-study tests for Order 179 paragraphs 17(3), 24 and 28–32.
No hydraulic, gas, thermal or biological process is inferred from discharge.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    Computability,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    Provenance,
    _text,
    aggregate_checks,
    permitted_use,
    warmup_restrictions,
)
from fishy.flows import Coverage, FlowSample, Presence
from fishy.quality import QualityValue
from fishy.quantities import Flow, Number, SignedState, StateVariable, finite_number
from fishy.spatial import Location
from fishy.time import Interval


@dataclass(frozen=True)
class EcologicalScope:
    location: Location
    interval: Interval
    provenance: Provenance
    product: str
    intended_use: str
    source_version: str

    def __post_init__(self) -> None:
        for name, kind in (("location", Location), ("interval", Interval), ("provenance", Provenance)):
            if not isinstance(getattr(self, name), kind):
                raise TypeError(f"{name} requires {kind.__name__}")
        for name in ("product", "intended_use", "source_version"):
            _text(getattr(self, name), name)

    @property
    def evidence_scope(self) -> EvidenceScope:
        return EvidenceScope(
            self.product,
            self.location.reach.identifier,
            self.provenance.reference_member,
            self.interval,
            self.intended_use,
        )


class StateSupport(StrEnum):
    INTERVAL_ENVELOPE = "supported interval extrema and states"
    ENDPOINTS = "endpoints only"
    INTERVAL_MEAN = "interval means only"


@dataclass(frozen=True)
class EcologicalStudy:
    """One supplied study binds all operands and criteria to this exact scope.

    The location includes section, reach, water-body and mapping revisions.
    EvidenceFindings alone has only a reach identifier and cannot supply that identity.
    """

    scope: EcologicalScope
    findings: EvidenceFindings
    support: StateSupport
    relation: str
    criteria_source: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope, EcologicalScope) or not isinstance(self.findings, EvidenceFindings):
            raise TypeError("study requires scoped evidence")
        if self.findings.scope != self.scope.evidence_scope or self.findings.provenance != self.scope.provenance:
            raise ValueError("study findings must match scope and every provenance version")
        if not isinstance(self.support, StateSupport):
            raise TypeError("study requires temporal support")
        _text(self.relation, "relation")
        _text(self.criteria_source, "criteria_source")


class Provision(StrEnum):
    REQUIRED_STUDY = "required supplied-study condition"
    RECOMMENDATION = "recommendation, not mandatory coefficient"


@dataclass(frozen=True)
class EcologicalAssessment:
    scope: EcologicalScope
    study: EcologicalStudy | None
    clause: str
    provision: Provision
    numerical: CheckSummary
    scientific_use: Check
    diagnostics: tuple[tuple[str, str], ...]
    limitations: tuple[str, ...] = (
        "Supplied criteria are not national defaults or proof of biological adequacy.",
        "Official admissibility remains the supplied evidence finding; no legal certification.",
    )


def _check(name: str, passed: bool | None, reason: str = "supplied state compared with supplied criterion") -> Check:
    finding = CheckFinding.UNKNOWN if passed is None else CheckFinding.PASS if passed else CheckFinding.FAIL
    return Check(name, finding, (reason,))


def _result(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    clause: str,
    checks: tuple[Check, ...],
    diagnostics: tuple[tuple[str, str], ...] = (),
    provision: Provision = Provision.REQUIRED_STUDY,
    support: StateSupport = StateSupport.INTERVAL_ENVELOPE,
) -> EcologicalAssessment:
    reason = None
    scientific = _check("scientific_use", None, "study not supplied for exact scope")
    if study is None or study.scope != scope:
        reason = "study missing or incompatible location, interval, source or scenario/version"
    else:
        scientific = permitted_use(study.findings, scope.evidence_scope)
        if (
            study.findings.computability is not Computability.COMPUTABLE
            or study.findings.numerical_validity is not NumericalValidity.VALID
        ):
            reason = "numerical support is unavailable or invalid"
        elif warmup_restrictions(scope.provenance, scope.interval):
            reason = "excluded warm-up interval"
        elif study.support is not support:
            reason = "temporal support does not establish the requested interval conditions"
    if reason is not None:
        checks = tuple(_check(c.check_id, None, reason) for c in checks)
    return EcologicalAssessment(
        scope,
        study,
        clause,
        provision,
        aggregate_checks(tuple(c.check_id for c in checks), checks),
        scientific,
        diagnostics,
    )


def _state(value: SignedState | None, variable: StateVariable) -> None:
    if value is not None and (not isinstance(value, SignedState) or value.variable is not variable):
        raise TypeError(f"expected {variable.value} SignedState")


def _depth(value: SignedState | None) -> None:
    _state(value, StateVariable.STAGE)
    if value is not None and value.value < 0:
        raise ValueError("depth above bed cannot be negative")


def _state_ge(name: str, value: SignedState | None, limit: SignedState | None, variable: StateVariable) -> Check:
    _state(value, variable)
    _state(limit, variable)
    if value is None or limit is None:
        return _check(name, None, "state or site criterion missing")
    if value.domain != limit.domain:
        raise ValueError("state and criterion require the same datum/direction/domain")
    return _check(name, value.value >= limit.value)


def _depth_ge(name: str, value: SignedState | None, limit: SignedState | None) -> Check:
    _depth(value)
    _depth(limit)
    return _state_ge(name, value, limit, StateVariable.STAGE)


@dataclass(frozen=True, init=False)
class LevelRate:
    """Nonnegative magnitude of a stage change rate, metres per second."""

    value: Fraction

    def __init__(self, value: Number, unit: str = "m/s") -> None:
        if unit not in ("m/s", "m/hour", "m/day"):
            raise ValueError("level rate requires m/s, m/hour or m/day")
        amount = finite_number(value) / {"m/s": 1, "m/hour": 3600, "m/day": 86400}[unit]
        if amount < 0:
            raise ValueError("rise/fall magnitudes cannot be negative")
        object.__setattr__(self, "value", amount)


def assess_level_change(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    before: SignedState | None,
    after: SignedState | None,
    rise_limit: LevelRate | None,
    fall_limit: LevelRate | None,
) -> EcologicalAssessment:
    """Endpoint-average rates across scope.interval, never instantaneous maxima."""
    _state(before, StateVariable.STAGE)
    _state(after, StateVariable.STAGE)
    if before is not None and after is not None and before.domain != after.domain:
        raise ValueError("endpoint stage datums differ")
    for limit in (rise_limit, fall_limit):
        if limit is not None and not isinstance(limit, LevelRate):
            raise TypeError("rise/fall limits require LevelRate")
    rate = None if before is None or after is None else (after.value - before.value) / scope.interval.seconds
    checks = tuple(
        _check(name, None if rate is None or limit is None else max(direction * rate, Fraction()) <= limit.value)
        for name, direction, limit in (("rise", 1, rise_limit), ("fall", -1, fall_limit))
    )
    return _result(
        scope,
        study,
        "Order 179 17(3), 24, 31",
        checks,
        (
            ("signed_endpoint_rate_m/s", str(rate)),
            ("elapsed_seconds", str(scope.interval.seconds)),
            ("before", repr(before)),
            ("after", repr(after)),
            ("rise_limit", repr(rise_limit)),
            ("fall_limit", repr(fall_limit)),
            ("meaning", "endpoint average only; unseen fluctuations remain unassessed"),
        ),
        support=StateSupport.ENDPOINTS,
    )


@dataclass(frozen=True, init=False)
class Duration:
    seconds: Fraction

    def __init__(self, seconds: Number) -> None:
        value = finite_number(seconds)
        if value < 0:
            raise ValueError("duration cannot be negative")
        object.__setattr__(self, "seconds", value)


def assess_floodplain(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    minimum_depth: SignedState | None,
    required_depth: SignedState | None,
    inundation: Duration | None,
    required_inundation: Duration | None,
    minimum_velocity: SignedState | None,
    required_velocity: SignedState | None,
) -> EcologicalAssessment:
    """The supplied duration must cover the stated depth and biological phase jointly."""
    for duration in (inundation, required_inundation):
        if duration is not None and (not isinstance(duration, Duration) or duration.seconds > scope.interval.seconds):
            raise ValueError("inundation duration must fit the study interval")
    checks = (
        _depth_ge("floodplain_depth", minimum_depth, required_depth),
        _check(
            "inundation_duration",
            None
            if inundation is None or required_inundation is None
            else inundation.seconds >= required_inundation.seconds,
        ),
        _state_ge("floodplain_velocity", minimum_velocity, required_velocity, StateVariable.VELOCITY),
    )
    return _result(
        scope,
        study,
        "Order 179 17(3), 28",
        checks,
        (
            ("minimum_depth", repr(minimum_depth)),
            ("required_depth", repr(required_depth)),
            ("inundation", repr(inundation)),
            ("required_inundation", repr(required_inundation)),
            ("minimum_velocity", repr(minimum_velocity)),
            ("required_velocity", repr(required_velocity)),
            ("joint_depth_duration", "supplied study must establish coincidence, not separate marginal extrema"),
        ),
    )


def assess_oxygen_gas(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    minimum_oxygen: QualityValue | None,
    required_oxygen: QualityValue | None,
    minimum_gas_saturation: QualityValue | None,
    required_gas_saturation: QualityValue | None,
) -> EcologicalAssessment:
    checks = []
    for name, value, limit, unit in (
        ("oxygen", minimum_oxygen, required_oxygen, "kg/m3"),
        ("gas_saturation", minimum_gas_saturation, required_gas_saturation, "1"),
    ):
        for item in (value, limit):
            if item is not None and (not isinstance(item, QualityValue) or item.unit != unit or item.value < 0):
                raise ValueError("gas criteria require nonnegative concentration or dimensionless saturation")
        checks.append(_check(name, None if value is None or limit is None else value.value >= limit.value))
    return _result(
        scope,
        study,
        "Order 179 17(3), 29, 31",
        tuple(checks),
        (
            ("minimum_oxygen", repr(minimum_oxygen)),
            ("required_oxygen", repr(required_oxygen)),
            ("minimum_gas_saturation", repr(minimum_gas_saturation)),
            ("required_gas_saturation", repr(required_gas_saturation)),
        ),
    )


class Connection(StrEnum):
    CONNECTED = "connected"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


def assess_thermal_movement(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    minimum_temperature: SignedState | None,
    maximum_temperature: SignedState | None,
    lower_temperature: SignedState | None,
    upper_temperature: SignedState | None,
    minimum_velocity: SignedState | None,
    maximum_velocity: SignedState | None,
    lower_velocity: SignedState | None,
    upper_velocity: SignedState | None,
    fish_access: Connection,
) -> EcologicalAssessment:
    checks = []
    for name, minimum, maximum, lower, upper, variable in (
        (
            "temperature",
            minimum_temperature,
            maximum_temperature,
            lower_temperature,
            upper_temperature,
            StateVariable.TEMPERATURE,
        ),
        (
            "movement_velocity",
            minimum_velocity,
            maximum_velocity,
            lower_velocity,
            upper_velocity,
            StateVariable.VELOCITY,
        ),
    ):
        checks.extend(
            (_state_ge(name + "_lower", minimum, lower, variable), _state_ge(name + "_upper", upper, maximum, variable))
        )
        for a, b in ((minimum, maximum), (lower, upper)):
            if a is not None and b is not None and (a.domain != b.domain or a.value > b.value):
                raise ValueError("state extrema/criteria must be ordered with matching domains")
    if not isinstance(fish_access, Connection):
        raise TypeError("fish access requires Connection")
    checks.append(
        _check("fish_access", None if fish_access is Connection.UNKNOWN else fish_access is Connection.CONNECTED)
    )
    return _result(
        scope,
        study,
        "Order 179 17(3)",
        tuple(checks),
        tuple(
            (name, repr(value))
            for name, value in (
                ("minimum_temperature", minimum_temperature),
                ("maximum_temperature", maximum_temperature),
                ("lower_temperature", lower_temperature),
                ("upper_temperature", upper_temperature),
                ("minimum_velocity", minimum_velocity),
                ("maximum_velocity", maximum_velocity),
                ("lower_velocity", lower_velocity),
                ("upper_velocity", upper_velocity),
                ("fish_access", fish_access),
            )
        ),
    )


class IceState(StrEnum):
    OPEN_WATER_REMAINS = "not frozen to bed"
    FROZEN_TO_BED = "frozen to bed"
    UNKNOWN = "unknown"


def assess_winter_continuity(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    minimum_flow: Flow | None,
    required_flow: Flow | None,
    ice: IceState,
) -> EcologicalAssessment:
    for value in (minimum_flow, required_flow):
        if value is not None and not isinstance(value, Flow):
            raise TypeError("winter flow requires Flow")
    if required_flow is not None and required_flow.value <= 0:
        raise ValueError("continuous winter flow criterion must be positive")
    if not isinstance(ice, IceState):
        raise TypeError("ice condition requires IceState")
    return _result(
        scope,
        study,
        "Order 179 29, 32(3)",
        (
            _check(
                "continuous_flow",
                None if minimum_flow is None or required_flow is None else minimum_flow.value >= required_flow.value,
            ),
            _check("not_frozen_to_bed", None if ice is IceState.UNKNOWN else ice is IceState.OPEN_WATER_REMAINS),
        ),
        (("minimum_flow", repr(minimum_flow)), ("required_flow", repr(required_flow)), ("ice", ice.value)),
    )


@dataclass(frozen=True, init=False)
class WinterShare:
    fraction: Fraction
    interpretation: str

    def __init__(self, fraction: Number, interpretation: str) -> None:
        value = finite_number(fraction)
        if not Fraction(3, 10) <= value <= Fraction(1, 2):
            raise ValueError("select an explicit recommended lower share between 0.30 and 0.50")
        _text(interpretation, "interpretation")
        object.__setattr__(self, "fraction", value)
        object.__setattr__(self, "interpretation", interpretation)


def assess_winter_recommendation(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    flow: Flow | None,
    observed_long_term_monthly_low_flow: Flow | None,
    selection: WinterShare | None,
) -> EcologicalAssessment:
    """Regulated-water November or December monthly lower-bound recommendation.

    Call separately for each month. The study must establish the observed long-term
    mean monthly low-flow statistic. No 50% upper bound or deliverability cap exists.
    """
    start, end = scope.interval.start, scope.interval.end
    if (
        start.month not in (11, 12)
        or start.day != 1
        or end.day != 1
        or (start.hour, start.minute, start.second, start.microsecond) != (0, 0, 0, 0)
        or (end.hour, end.minute, end.second, end.microsecond) != (0, 0, 0, 0)
        or (end.year * 12 + end.month) - (start.year * 12 + start.month) != 1
    ):
        raise ValueError("recommendation needs one whole November or December UTC reporting month")
    for value in (flow, observed_long_term_monthly_low_flow):
        if value is not None and not isinstance(value, Flow):
            raise TypeError("monthly flows require Flow")
    if selection is not None and not isinstance(selection, WinterShare):
        raise TypeError("winter selection requires WinterShare")
    lower = (
        None
        if selection is None or observed_long_term_monthly_low_flow is None
        else selection.fraction * observed_long_term_monthly_low_flow.value
    )
    return _result(
        scope,
        study,
        "Order 179 30",
        (_check("recommended_monthly_lower_flow", None if lower is None or flow is None else flow.value >= lower),),
        (
            ("flow", repr(flow)),
            ("observed_long_term_monthly_low_flow", repr(observed_long_term_monthly_low_flow)),
            ("recommended_lower_m3/s", str(lower)),
            ("selection", str(selection)),
        ),
        Provision.RECOMMENDATION,
        StateSupport.INTERVAL_MEAN,
    )


def assess_special_release(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    minimum_supply: Flow | None,
    required_supply: Flow | None,
    floodplain_connection: Connection,
) -> EcologicalAssessment:
    """Assess supplied downstream arrival, not reservoir discharge or routing.

    Level-change and oxygen conditions remain separate required assessments.
    The study identifies the sensitive area and supported upstream release relation.
    """
    for value in (minimum_supply, required_supply):
        if value is not None and not isinstance(value, Flow):
            raise TypeError("special release supply requires Flow")
    if not isinstance(floodplain_connection, Connection):
        raise TypeError("floodplain access requires Connection")
    return _result(
        scope,
        study,
        "Order 179 24, 31",
        (
            _check(
                "sensitive_area_supply",
                None
                if minimum_supply is None or required_supply is None
                else minimum_supply.value >= required_supply.value,
            ),
            _check(
                "floodplain_connection",
                None if floodplain_connection is Connection.UNKNOWN else floodplain_connection is Connection.CONNECTED,
            ),
        ),
        (
            ("minimum_supply", repr(minimum_supply)),
            ("required_supply", repr(required_supply)),
            ("floodplain_connection", floodplain_connection.value),
        ),
    )


class Drying(StrEnum):
    WET = "wet throughout"
    NATURAL_SEASONAL = "supported natural seasonal drying"
    INDUCED = "harmful induced drying"
    UNKNOWN = "drying origin unresolved"


@dataclass(frozen=True)
class SmallRiverVelocity:
    minimum: SignedState
    interpretation: str

    def __post_init__(self) -> None:
        _state(self.minimum, StateVariable.VELOCITY)
        if not isinstance(self.minimum, SignedState) or not Fraction(1, 5) <= self.minimum.value <= Fraction(3, 5):
            raise ValueError("select a supported minimum velocity within 0.20–0.60 m/s")
        _text(self.interpretation, "interpretation")


def assess_small_river(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    drying: Drying,
    minimum_depth: SignedState | None,
    minimum_velocity: SignedState | None,
    selection: SmallRiverVelocity | None,
) -> EcologicalAssessment:
    if not isinstance(drying, Drying):
        raise TypeError("drying requires a supported domain state")
    _depth(minimum_depth)
    if selection is not None and not isinstance(selection, SmallRiverVelocity):
        raise TypeError("velocity selection requires SmallRiverVelocity")
    depth_limit = None if minimum_depth is None else SignedState(StateVariable.STAGE, "0.1", "m", minimum_depth.domain)
    return _result(
        scope,
        study,
        "Order 179 32(1), 32(4)",
        (
            _check(
                "induced_drying",
                None if drying is Drying.UNKNOWN else drying is not Drying.INDUCED,
                "natural seasonal drying is distinguished, not an exemption from all hydraulic provisions",
            ),
            _depth_ge("minimum_depth", minimum_depth, depth_limit),
            _state_ge(
                "selected_minimum_velocity",
                minimum_velocity,
                None if selection is None else selection.minimum,
                StateVariable.VELOCITY,
            ),
        ),
        (
            ("minimum_depth", repr(minimum_depth)),
            ("minimum_velocity", repr(minimum_velocity)),
            ("velocity_selection", str(selection)),
            ("drying", drying.value),
        ),
    )


def assess_seasonal_timing(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    natural_peak: datetime | None,
    managed_peak: datetime | None,
    allowed_shift: Duration | None,
) -> EcologicalAssessment:
    """Compare supplied natural and managed seasonal peaks, not annual volumes."""
    for peak in (natural_peak, managed_peak):
        if peak is not None:
            if not isinstance(peak, datetime) or peak.tzinfo is None or peak.utcoffset() is None:
                raise ValueError("peak time requires an explicit timezone")
            if not scope.interval.start <= peak < scope.interval.end:
                raise ValueError("seasonal peak must be within the study interval")
    if allowed_shift is not None and not isinstance(allowed_shift, Duration):
        raise TypeError("timing tolerance requires Duration")
    difference = None
    if natural_peak is not None and managed_peak is not None:
        difference = (
            Fraction()
            if natural_peak == managed_peak
            else Interval(min(natural_peak, managed_peak), max(natural_peak, managed_peak)).seconds
        )
    return _result(
        scope,
        study,
        "Order 179 24, 32(2)",
        (
            _check(
                "natural_peak_synchronisation",
                None if difference is None or allowed_shift is None else difference <= allowed_shift.seconds,
            ),
        ),
        (
            ("natural_peak", str(natural_peak)),
            ("managed_peak", str(managed_peak)),
            ("difference_seconds", str(difference)),
            ("allowed_shift", str(allowed_shift)),
        ),
    )


class CorrectionPosition(StrEnum):
    BEFORE_SPAWNING = "hydraulic correction before spawning correction"
    AFTER_SPAWNING = "hydraulic correction after spawning correction"


@dataclass(frozen=True)
class HydraulicCorrection:
    original: FlowSample
    adjustment: SignedState | None
    corrected: Flow | None
    position: CorrectionPosition | None
    assessment: EcologicalAssessment


def apply_hydraulic_correction(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    original: FlowSample,
    adjustment: SignedState | None,
    position: CorrectionPosition | None,
) -> HydraulicCorrection:
    """Apply a supplied model-derived additive discharge relation, not a solver.

    The study establishes depth/velocity sufficiency and the adjustment's validity
    at this original discharge. Position is explicit; this operation does not run
    spawning corrections or silently resolve their conflicts with source bounds.
    """
    if not isinstance(original, FlowSample):
        raise TypeError("hydraulic correction requires a located FlowSample")
    if (
        original.location != scope.location
        or original.interval != scope.interval
        or original.provenance != scope.provenance
    ):
        raise ValueError("hydraulic base must match exact study scope and provenance")
    _state(adjustment, StateVariable.EXCHANGE)
    if position is not None and not isinstance(position, CorrectionPosition):
        raise TypeError("hydraulic correction needs explicit CorrectionPosition")
    supported = original.presence is Presence.PRESENT and original.coverage is Coverage.COMPLETE
    value = None if original.value is None or adjustment is None else original.value.value + adjustment.value
    assessment = _result(
        scope,
        study,
        "Order 179 28",
        (
            _check(
                "hydraulic_relation",
                None if not supported or value is None or position is None else value >= 0,
                "supplied additive relation; negative discharge is infeasible, not clipped",
            ),
        ),
        (("adjustment", repr(adjustment)), ("position", str(position)), ("candidate_m3/s", str(value))),
    )
    corrected = Flow(value) if value is not None and assessment.numerical.finding is CheckFinding.PASS else None
    return HydraulicCorrection(original, adjustment, corrected, position, assessment)


def assess_thermal_variation(
    scope: EcologicalScope,
    study: EcologicalStudy | None,
    maximum_swing: SignedState | None,
    allowed_swing: SignedState | None,
) -> EcologicalAssessment:
    """Assess supplied within-period temperature swings against a site criterion.

    Endpoint differences and daily means cannot establish within-period swings.
    The common domain identifies temperature differences, not absolute temperature.
    """
    for value in (maximum_swing, allowed_swing):
        _state(value, StateVariable.TEMPERATURE)
        if value is not None and value.value < 0:
            raise ValueError("temperature swing is a nonnegative magnitude")
    check = _state_ge("temperature_swing", allowed_swing, maximum_swing, StateVariable.TEMPERATURE)
    return _result(
        scope,
        study,
        "Order 179 17(3)",
        (check,),
        (("maximum_swing", repr(maximum_swing)), ("allowed_swing", repr(allowed_swing))),
    )
