"""Supplied FlowSamples → EcologicalAssessments for one synthetic Kazakh section.

Illustrative specialist outputs are supplied, not inferred from monthly discharge.
Every statement is scoped to the corrected schedule's location and scenario/version.
"""

from dataclasses import replace
from datetime import timedelta

from fishy.ecological_conditions import (
    Connection,
    Drying,
    Duration,
    EcologicalAssessment,
    EcologicalScope,
    EcologicalStudy,
    IceState,
    LevelRate,
    SmallRiverVelocity,
    StateSupport,
    WinterShare,
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
    Computability,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ScientificAdequacy,
)
from fishy.flows import FlowSample
from fishy.quality import QualityValue
from fishy.quantities import Flow, SignedState, StateVariable


def supplied_assessments(samples: tuple[FlowSample, ...]) -> tuple[EcologicalAssessment, ...]:
    results = []
    for sample in samples:
        scope = EcologicalScope(
            sample.location,
            sample.interval,
            sample.provenance,
            "supplied ecological states",
            "illustrative assessment",
            "Order179-2025-held-ministry",
        )
        findings = EvidenceFindings(
            scope.evidence_scope,
            scope.provenance,
            Computability.COMPUTABLE,
            NumericalValidity.VALID,
            Disclosure.COMPLETE,
            ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
            OfficialAdmissibility.PENDING,
            ("Synthetic specialist outputs for this corrected candidate only",),
        )
        study = EcologicalStudy(
            scope,
            findings,
            StateSupport.INTERVAL_ENVELOPE,
            "illustrative extrema, coincident inundation, connectivity and ice study",
            "synthetic site criteria, not nationally calibrated defaults",
        )
        depth = SignedState(StateVariable.STAGE, "0.2", "m", "depth above bed")
        speed = SignedState(StateVariable.VELOCITY, "0.4", "m/s", "downstream positive")
        low = SignedState(StateVariable.TEMPERATURE, 8, "degC", "water temperature")
        high = SignedState(StateVariable.TEMPERATURE, 12, "degC", "water temperature")
        swing = SignedState(StateVariable.TEMPERATURE, 1, "degC", "temperature difference")
        # Local stage, oxygen, temperature and access are independent supplied outputs.
        # No monthly-mean flow claims to prove an interval minimum or rapid stage change.
        results.extend(
            (
                assess_level_change(
                    scope,
                    replace(study, support=StateSupport.ENDPOINTS),
                    depth,
                    depth,
                    LevelRate("0.1", "m/day"),
                    LevelRate("0.05", "m/day"),
                ),
                assess_oxygen_gas(
                    scope,
                    study,
                    QualityValue(7, "mg/l"),
                    QualityValue(6, "mg/l"),
                    QualityValue("0.95", "1"),
                    QualityValue("0.9", "1"),
                ),
                assess_thermal_movement(
                    scope, study, low, high, low, high, speed, speed, speed, speed, Connection.CONNECTED
                ),
                assess_thermal_variation(scope, study, swing, swing),
                assess_small_river(
                    scope,
                    study,
                    Drying.WET,
                    depth,
                    speed,
                    SmallRiverVelocity(speed, "study-selected minimum within source range"),
                ),
                assess_special_release(scope, study, Flow(1), Flow("0.5"), Connection.CONNECTED),
            )
        )
        if sample.interval.start.month == 4:
            results.extend(
                (
                    assess_floodplain(
                        scope, study, depth, depth, Duration(6 * 86400), Duration(6 * 86400), speed, speed
                    ),
                    assess_seasonal_timing(
                        scope,
                        study,
                        sample.interval.start + timedelta(days=14),
                        sample.interval.start + timedelta(days=14),
                        Duration(86400),
                    ),
                )
            )
        if sample.interval.start.month in (11, 12, 1, 2):
            results.append(assess_winter_continuity(scope, study, Flow(1), Flow("0.5"), IceState.OPEN_WATER_REMAINS))
        if sample.interval.start.month in (11, 12):
            results.append(
                assess_winter_recommendation(
                    scope,
                    replace(study, support=StateSupport.INTERVAL_MEAN),
                    sample.value,
                    Flow(2),
                    WinterShare("0.4", "synthetic 40% recommended lower bound, not a cap"),
                )
            )
    return tuple(results)
