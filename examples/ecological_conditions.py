"""One synthetic supplied ecological study; no simulator or Uzbek operands."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fishy.ecological_conditions import (
    Connection,
    CorrectionPosition,
    Drying,
    Duration,
    EcologicalScope,
    EcologicalStudy,
    IceState,
    LevelRate,
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
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.flows import FlowSample, Presence
from fishy.quality import QualityValue
from fishy.quantities import Flow, SignedState, StateVariable
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


def main() -> None:
    location = Location(
        Reach("synthetic-reach", "r1", WaterBody("synthetic-river", "w1")),
        CalculationSection("floodplain", "s1"),
        "map1",
    )
    interval = Interval(datetime(2024, 11, 1, tzinfo=UTC), datetime(2024, 12, 1, tzinfo=UTC))
    provenance = Provenance(
        "synthetic specialist study",
        "ecology-scenario",
        "reference1",
        "example1",
        "states1",
        "criteria1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    scope = EcologicalScope(
        location, interval, provenance, "ecological states", "illustrative assessment", "Order179-2025-held-ministry"
    )
    findings = EvidenceFindings(
        scope.evidence_scope,
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("synthetic inputs only",),
    )
    study = EcologicalStudy(
        scope,
        findings,
        StateSupport.INTERVAL_ENVELOPE,
        "supplied supported extrema, timing, access and additive discharge relation",
        "synthetic species/site criteria, not national defaults",
    )
    depth = SignedState(StateVariable.STAGE, "0.2", "m", "depth above bed")
    speed = SignedState(StateVariable.VELOCITY, "0.4", "m/s", "downstream positive")
    low = SignedState(StateVariable.TEMPERATURE, 8, "degC", "water temperature")
    high = SignedState(StateVariable.TEMPERATURE, 12, "degC", "water temperature")
    swing = SignedState(StateVariable.TEMPERATURE, 1, "degC", "temperature difference magnitude")
    results = (
        assess_level_change(
            scope,
            replace(study, support=StateSupport.ENDPOINTS),
            depth,
            depth,
            LevelRate("0.1", "m/day"),
            LevelRate("0.05", "m/day"),
        ),
        assess_floodplain(scope, study, depth, depth, Duration(86400), Duration(86400), speed, speed),
        assess_oxygen_gas(
            scope,
            study,
            QualityValue(7, "mg/l"),
            QualityValue(6, "mg/l"),
            QualityValue("0.95", "1"),
            QualityValue("0.9", "1"),
        ),
        assess_thermal_movement(scope, study, low, high, low, high, speed, speed, speed, speed, Connection.CONNECTED),
        assess_thermal_variation(scope, study, swing, swing),
        assess_winter_continuity(scope, study, Flow(4), Flow(3), IceState.OPEN_WATER_REMAINS),
        assess_winter_recommendation(
            scope,
            replace(study, support=StateSupport.INTERVAL_MEAN),
            Flow(9),
            Flow(10),
            WinterShare("0.4", "study-supported 40% lower bound"),
        ),
        assess_special_release(scope, study, Flow(4), Flow(3), Connection.CONNECTED),
        assess_small_river(scope, study, Drying.WET, depth, speed, SmallRiverVelocity(speed, "site minimum")),
        assess_seasonal_timing(
            scope, study, interval.start + timedelta(days=10), interval.start + timedelta(days=11), Duration(86400)
        ),
    )
    base = FlowSample(location, interval, Flow(8), Presence.PRESENT, provenance)
    correction = apply_hydraulic_correction(
        scope,
        study,
        base,
        SignedState(StateVariable.EXCHANGE, 2, "m3/s", "additive model-derived correction"),
        CorrectionPosition.BEFORE_SPAWNING,
    )
    assert correction.corrected == Flow(10)
    assert all(result.numerical.finding is CheckFinding.PASS for result in results)
    assert all(
        result.study is not None and result.study.findings.official_admissibility is OfficialAdmissibility.PENDING
        for result in results
    )
    print(f"{len(results)} supported numerical assessments pass; hydraulic correction 8 + 2 = 10 m3/s")
    print("Scientific use: indicative. Official admissibility: pending. No basin certification.")


if __name__ == "__main__":
    main()
