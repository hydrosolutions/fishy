"""Synthetic supplied-study tests, not basin calibration or adopted criteria."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.ecological_conditions import (
    Connection,
    CorrectionPosition,
    Drying,
    Duration,
    EcologicalScope,
    EcologicalStudy,
    IceState,
    LevelRate,
    Provision,
    SmallRiverVelocity,
    StateSupport,
    WinterShare,
    apply_hydraulic_correction,
    assess_floodplain,
    assess_level_change,
    assess_oxygen_gas,
    assess_seasonal_timing,
    assess_small_river,
    assess_special_release,
    assess_thermal_movement,
    assess_thermal_variation,
    assess_winter_continuity,
    assess_winter_recommendation,
)
from fishy.evidence import (
    CheckFinding,
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
    UseRestriction,
)
from fishy.flows import FlowSample, Presence
from fishy.quality import QualityValue
from fishy.quantities import Flow, SignedState, StateVariable
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


@pytest.fixture
def scope():
    return EcologicalScope(
        Location(Reach("reach", "r1", WaterBody("river", "w1")), CalculationSection("section", "s1"), "map1"),
        Interval(datetime(2024, 11, 1, tzinfo=UTC), datetime(2024, 12, 1, tzinfo=UTC)),
        Provenance(
            "synthetic study",
            "scenario",
            "reference",
            "software1",
            "data1",
            "config1",
            ProductionMethod.ILLUSTRATIVE,
            CorrectionState.ORIGINAL,
        ),
        "supplied ecology",
        "scenario assessment",
        "Order179-2025-held-ministry",
    )


def study(scope, support=StateSupport.INTERVAL_ENVELOPE, **changes):
    findings = EvidenceFindings(
        scope.evidence_scope,
        scope.provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("synthetic supplied study, not field evidence",),
    )
    return EcologicalStudy(
        scope,
        replace(findings, **changes),
        support,
        "supplied interval relation and extrema",
        "synthetic site criteria v1",
    )


def depth(value):
    return SignedState(StateVariable.STAGE, value, "m", "depth above bed")


def velocity(value):
    return SignedState(StateVariable.VELOCITY, value, "m/s", "downstream positive")


def temperature(value):
    return SignedState(StateVariable.TEMPERATURE, value, "degC", "water temperature")


def test_independent_complete_supplied_conditions(scope):
    evidence = study(scope)
    results = (
        assess_floodplain(
            scope, evidence, depth(1), depth("0.5"), Duration(86400), Duration(43200), velocity("0.4"), velocity("0.2")
        ),
        assess_oxygen_gas(
            scope,
            evidence,
            QualityValue(7, "mg/l"),
            QualityValue(6, "mg/l"),
            QualityValue("0.95", "1"),
            QualityValue("0.9", "1"),
        ),
        assess_thermal_movement(
            scope,
            evidence,
            temperature(10),
            temperature(15),
            temperature(8),
            temperature(18),
            velocity("0.3"),
            velocity("0.5"),
            velocity("0.2"),
            velocity("0.6"),
            Connection.CONNECTED,
        ),
        assess_winter_continuity(scope, evidence, Flow(3), Flow(2), IceState.OPEN_WATER_REMAINS),
        assess_special_release(scope, evidence, Flow(5), Flow(4), Connection.CONNECTED),
        assess_small_river(
            scope,
            evidence,
            Drying.WET,
            depth("0.1"),
            velocity("0.4"),
            SmallRiverVelocity(velocity("0.4"), "site selection"),
        ),
    )
    for result in results:
        assert result.numerical.finding is CheckFinding.PASS
        assert result.numerical.completeness is Completeness.COMPLETE
        assert result.scientific_use.finding is CheckFinding.PASS
        assert result.study is not None
        assert result.study.findings.official_admissibility is OfficialAdmissibility.PENDING
        assert result.scope == scope


@pytest.mark.parametrize(
    "delta,expected",
    [
        ("0.6", CheckFinding.PASS),
        ("0.6001", CheckFinding.FAIL),
        ("-0.2", CheckFinding.PASS),
        ("-0.2001", CheckFinding.FAIL),
    ],
)
def test_separate_rise_fall_real_elapsed(scope, delta, expected):
    scope = replace(scope, interval=Interval(scope.interval.start, scope.interval.start + timedelta(hours=2)))
    result = assess_level_change(
        scope,
        study(scope, StateSupport.ENDPOINTS),
        depth(2),
        depth(Fraction(2) + Fraction(delta)),
        LevelRate("0.3", "m/hour"),
        LevelRate("0.1", "m/hour"),
    )
    assert result.numerical.finding is expected
    assert dict(result.diagnostics)["elapsed_seconds"] == "7200"
    assert dict(result.diagnostics)["signed_endpoint_rate_m/s"] == str(Fraction(delta) / 7200)


def test_level_missing_predecessor_and_mean_cannot_pass(scope):
    result = assess_level_change(
        scope, study(scope, StateSupport.ENDPOINTS), None, depth(2), LevelRate(1), LevelRate(1)
    )
    assert result.numerical.finding is CheckFinding.UNKNOWN
    result = assess_level_change(
        scope, study(scope, StateSupport.INTERVAL_MEAN), depth(1), depth(2), LevelRate(1), LevelRate(1)
    )
    assert result.numerical.finding is CheckFinding.UNKNOWN


def test_known_failure_survives_missing_other_condition(scope):
    result = assess_floodplain(scope, study(scope), depth("0.1"), depth(1), None, None, velocity(1), velocity("0.5"))
    assert result.numerical.finding is CheckFinding.FAIL
    assert result.numerical.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize("flow,expected", [(3, CheckFinding.PASS), (9, CheckFinding.PASS), ("2.99", CheckFinding.FAIL)])
def test_winter_recommendation_is_lower_bound_not_upper_cap(scope, flow, expected):
    result = assess_winter_recommendation(
        scope,
        study(scope, StateSupport.INTERVAL_MEAN),
        Flow(flow),
        Flow(10),
        WinterShare("0.3", "supported minimum share selection"),
    )
    assert result.numerical.finding is expected
    assert result.provision is Provision.RECOMMENDATION
    assert dict(result.diagnostics)["recommended_lower_m3/s"] == "3"


def test_winter_selection_missing_and_non_november_refused(scope):
    assert (
        assess_winter_recommendation(
            scope, study(scope, StateSupport.INTERVAL_MEAN), Flow(10), Flow(10), None
        ).numerical.finding
        is CheckFinding.UNKNOWN
    )
    scope = replace(scope, interval=Interval(datetime(2024, 10, 1, tzinfo=UTC), datetime(2024, 11, 1, tzinfo=UTC)))
    with pytest.raises(ValueError, match="November or December"):
        assess_winter_recommendation(scope, study(scope), Flow(10), Flow(10), WinterShare("0.5", "explicit"))


@pytest.mark.parametrize(
    "drying,finding",
    [
        (Drying.WET, CheckFinding.PASS),
        (Drying.NATURAL_SEASONAL, CheckFinding.PASS),
        (Drying.INDUCED, CheckFinding.FAIL),
        (Drying.UNKNOWN, CheckFinding.UNKNOWN),
    ],
)
def test_drying_origin_is_not_inferred_from_zero_flow(scope, drying, finding):
    result = assess_small_river(scope, study(scope), drying, None, None, None)
    assert result.numerical.checks[0].finding is finding
    assert result.numerical.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize("threshold,expected", [("0.2", CheckFinding.PASS), ("0.6", CheckFinding.FAIL)])
def test_small_river_velocity_requires_selected_threshold(scope, threshold, expected):
    result = assess_small_river(
        scope,
        study(scope),
        Drying.WET,
        depth("0.1"),
        velocity("0.4"),
        SmallRiverVelocity(velocity(threshold), "supported site minimum"),
    )
    assert result.numerical.finding is expected
    assert (
        assess_small_river(scope, study(scope), Drying.WET, depth("0.1"), velocity("0.4"), None).numerical.finding
        is CheckFinding.UNKNOWN
    )


def test_depth_literal_and_frozen_conditions_fail(scope):
    assert (
        assess_small_river(
            scope,
            study(scope),
            Drying.WET,
            depth("0.0999"),
            velocity(1),
            SmallRiverVelocity(velocity("0.2"), "explicit"),
        ).numerical.finding
        is CheckFinding.FAIL
    )
    assert (
        assess_winter_continuity(scope, study(scope), Flow(0), Flow(1), IceState.FROZEN_TO_BED).numerical.finding
        is CheckFinding.FAIL
    )


def test_low_oxygen_thermal_and_movement_fail(scope):
    assert (
        assess_oxygen_gas(
            scope, study(scope), QualityValue(5, "mg/l"), QualityValue(6, "mg/l"), None, None
        ).numerical.finding
        is CheckFinding.FAIL
    )
    result = assess_thermal_movement(
        scope,
        study(scope),
        temperature(10),
        temperature(30),
        temperature(5),
        temperature(20),
        velocity(0),
        velocity(1),
        velocity("0.2"),
        velocity("0.6"),
        Connection.BLOCKED,
    )
    assert result.numerical.finding is CheckFinding.FAIL


def test_special_release_supply_and_connection_are_not_reservoir_discharge(scope):
    result = assess_special_release(scope, study(scope), Flow(2), Flow(3), Connection.UNKNOWN)
    assert result.numerical.finding is CheckFinding.FAIL
    assert result.numerical.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize("field", ["location", "interval", "provenance", "source_version"])
def test_evidence_cannot_transfer_exact_location_time_version(scope, field):
    replacements = {
        "location": replace(scope.location, section=replace(scope.location.section, version="s2")),
        "interval": Interval(scope.interval.start, scope.interval.end + timedelta(days=1)),
        "provenance": replace(scope.provenance, configuration_version="config2"),
        "source_version": "different-order-version",
    }
    result = assess_winter_continuity(
        replace(scope, **{field: replacements[field]}), study(scope), Flow(3), Flow(2), IceState.OPEN_WATER_REMAINS
    )
    assert result.numerical.finding is CheckFinding.UNKNOWN
    assert result.scientific_use.finding is CheckFinding.UNKNOWN


def test_numerical_scientific_official_statuses_are_separate(scope):
    result = assess_winter_continuity(
        scope,
        study(scope, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED),
        Flow(3),
        Flow(2),
        IceState.OPEN_WATER_REMAINS,
    )
    assert result.numerical.finding is CheckFinding.PASS
    assert result.scientific_use.finding is CheckFinding.FAIL
    assert result.study is not None
    assert result.study.findings.official_admissibility is OfficialAdmissibility.PENDING
    restricted = study(scope, restrictions=(UseRestriction("not for sizing", (scope.intended_use,)),))
    assert (
        assess_winter_continuity(
            scope, restricted, Flow(3), Flow(2), IceState.OPEN_WATER_REMAINS
        ).scientific_use.finding
        is CheckFinding.FAIL
    )
    invalid = study(scope, numerical_validity=NumericalValidity.INVALID)
    assert (
        assess_winter_continuity(scope, invalid, Flow(3), Flow(2), IceState.OPEN_WATER_REMAINS).numerical.finding
        is CheckFinding.UNKNOWN
    )


def test_missing_study_temporal_support_and_warmup_cannot_pass(scope):
    for evidence in (None, study(scope, StateSupport.INTERVAL_MEAN)):
        assert (
            assess_winter_continuity(scope, evidence, Flow(3), Flow(2), IceState.OPEN_WATER_REMAINS).numerical.finding
            is CheckFinding.UNKNOWN
        )
    scope = replace(scope, provenance=replace(scope.provenance, excluded_warmup=(scope.interval,)))
    assert (
        assess_winter_continuity(scope, study(scope), Flow(3), Flow(2), IceState.OPEN_WATER_REMAINS).numerical.finding
        is CheckFinding.UNKNOWN
    )


def test_natural_seasonal_peak_timing(scope):
    peak = scope.interval.start + timedelta(days=10)
    for shift, expected in [(2, CheckFinding.PASS), (3, CheckFinding.FAIL)]:
        result = assess_seasonal_timing(scope, study(scope), peak, peak + timedelta(days=shift), Duration(172800))
        assert result.numerical.finding is expected
    assert (
        assess_seasonal_timing(scope, study(scope), None, peak, Duration(0)).numerical.finding is CheckFinding.UNKNOWN
    )


@pytest.mark.parametrize("position", list(CorrectionPosition))
def test_supplied_hydraulic_correction_computes_supported_flow(scope, position):
    original = FlowSample(scope.location, scope.interval, Flow(8), Presence.PRESENT, scope.provenance)
    adjustment = SignedState(StateVariable.EXCHANGE, 2, "m3/s", "additive model-derived correction")
    result = apply_hydraulic_correction(scope, study(scope), original, adjustment, position)
    assert result.corrected == Flow(10)
    assert result.original.value == Flow(8)
    assert result.position is position
    assert result.assessment.numerical.finding is CheckFinding.PASS
    assert apply_hydraulic_correction(scope, study(scope), original, adjustment, None).corrected is None
    bad = SignedState(StateVariable.EXCHANGE, -9, "m3/s", adjustment.domain)
    result = apply_hydraulic_correction(scope, study(scope), original, bad, position)
    assert result.corrected is None
    assert result.assessment.numerical.finding is CheckFinding.FAIL


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", True, -1])
def test_invalid_quantities_fail_loud(value):
    for constructor in (LevelRate, Duration):
        with pytest.raises((ValueError, TypeError)):
            constructor(value)


@pytest.mark.parametrize("value", ["0.29", "0.51", "nan", True])
def test_invalid_winter_share(value):
    with pytest.raises((ValueError, TypeError)):
        WinterShare(value, "explicit")


def test_domain_states_mutability_and_units_fail_loud(scope):
    with pytest.raises(FrozenInstanceError):
        scope.product = "mutated"
    with pytest.raises(TypeError):
        assess_small_river(scope, study(scope), True, depth(1), velocity(1), None)  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError):
        SmallRiverVelocity(velocity("0.61"), "explicit")
    with pytest.raises(ValueError):
        assess_floodplain(scope, study(scope), depth(-1), depth(0), None, None, None, None)
    with pytest.raises(ValueError, match="same datum"):
        assess_small_river(
            scope,
            study(scope),
            Drying.WET,
            depth(1),
            SignedState(StateVariable.VELOCITY, 1, "m/s", "upstream positive"),
            SmallRiverVelocity(velocity("0.2"), "explicit"),
        )
    with pytest.raises(ValueError):
        assess_oxygen_gas(scope, study(scope), QualityValue(1, "pH"), QualityValue(1, "pH"), None, None)
    with pytest.raises(ValueError, match="match scope"):
        EcologicalStudy(
            scope,
            replace(study(scope).findings, provenance=replace(scope.provenance, data_version="different")),
            StateSupport.INTERVAL_ENVELOPE,
            "relation",
            "criteria",
        )


@pytest.mark.parametrize("change", ["mapping", "reach", "water_body", "scenario", "data_version", "software_version"])
def test_study_cannot_transfer_physical_or_production_versions(scope, change):
    if change == "mapping":
        other = replace(scope, location=replace(scope.location, mapping_version="mapping2"))
    elif change == "reach":
        other = replace(scope, location=replace(scope.location, reach=replace(scope.location.reach, version="r2")))
    elif change == "water_body":
        other = replace(
            scope,
            location=replace(
                scope.location,
                reach=replace(scope.location.reach, water_body=replace(scope.location.reach.water_body, version="w2")),
            ),
        )
    else:
        other = replace(scope, provenance=replace(scope.provenance, **{change: "different"}))
    result = assess_winter_continuity(other, study(scope), Flow(3), Flow(2), IceState.OPEN_WATER_REMAINS)
    assert result.numerical.finding is CheckFinding.UNKNOWN
    assert result.scientific_use.finding is CheckFinding.UNKNOWN


def test_temperature_swings_need_sufficient_temporal_support(scope):
    swing = SignedState(StateVariable.TEMPERATURE, 3, "degC", "temperature difference magnitude")
    limit = SignedState(StateVariable.TEMPERATURE, 2, "degC", swing.domain)
    assert assess_thermal_variation(scope, study(scope), swing, limit).numerical.finding is CheckFinding.FAIL
    assert assess_thermal_variation(scope, study(scope), limit, limit).numerical.finding is CheckFinding.PASS
    assert (
        assess_thermal_variation(scope, study(scope, StateSupport.INTERVAL_MEAN), limit, limit).numerical.finding
        is CheckFinding.UNKNOWN
    )
