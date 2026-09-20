"""Order 179 paragraphs 25–27 and Appendix 3–4 public-path discriminators."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.design_conditions import DesignClass
from fishy.evidence import (
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
    UseRestriction,
)
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow, SignedState, StateVariable
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.spawning import (
    APPENDIX3,
    APPENDIX4,
    STAR_HEADINGS,
    BiologicalTiming,
    CoefficientInterpretation,
    EligibilityInterpretation,
    SpawningEligibility,
    StarRelevance,
    TemporalBasis,
    TimedCoefficient,
    WeightedStudy,
    coefficient_scope,
    spawning_eligibility,
    spawning_schedule,
)
from fishy.time import Interval

LOCATION = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
PROVENANCE = Provenance(
    "synthetic supplied spawning study",
    "scenario",
    "reference",
    "1",
    "1",
    "1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
)
ONSET = datetime(2024, 4, 15, tzinfo=UTC)
MONTH = Interval(datetime(2024, 4, 1, tzinfo=UTC), datetime(2024, 5, 1, tzinfo=UTC))
PERIOD = Interval(ONSET, ONSET + timedelta(days=6))


def evidence(scope):
    return EvidenceFindings(
        scope,
        PROVENANCE,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic supplied support",),
    )


def study_scope(product, period=PERIOD):
    return EvidenceScope(product, LOCATION.reach.identifier, PROVENANCE.reference_member, period, "spawning_correction")


def biological_timing():
    return BiologicalTiming(
        "Сазан",
        ONSET,
        0,
        (2, 2, 2),
        SignedState(StateVariable.TEMPERATURE, 15, "degC", "water temperature at biological onset"),
        SignedState(StateVariable.TEMPERATURE, 15, "degC", "species onset threshold"),
        evidence(study_scope("spawning_timing")),
        LOCATION,
    )


TIMING = biological_timing()


def run(
    intervals: tuple[Interval, ...] = (MONTH,),
    *,
    location: Location = LOCATION,
    provenance: Provenance = PROVENANCE,
    design: DesignClass = DesignClass.MODERATELY_DRY,
    eligibility_interpretation: EligibilityInterpretation | None = EligibilityInterpretation.PERCENTAGE_WORDING,
    temporal_basis: TemporalBasis = TemporalBasis.MONTHLY_AVERAGE,
    coefficient_interpretation: CoefficientInterpretation | None = CoefficientInterpretation.LISTED_VALUE,
    star_relevance: StarRelevance = StarRelevance.NOT_RELIED_UPON,
    timing: BiologicalTiming | None = TIMING,
    coefficient_findings: tuple[EvidenceFindings, ...] | None = None,
    basin_row: int | None = 2,
    study: WeightedStudy | None = None,
    daily_observations: tuple[FlowSample, ...] = (),
):
    if coefficient_findings is None:
        coefficient_findings = tuple(evidence(coefficient_scope(LOCATION, i, PROVENANCE)) for i in intervals)
    return spawning_schedule(
        location,
        intervals,
        provenance,
        design,
        eligibility_interpretation,
        temporal_basis,
        coefficient_interpretation,
        star_relevance,
        timing,
        coefficient_findings,
        basin_row=basin_row,
        study=study,
        daily_observations=daily_observations,
    )


@pytest.mark.parametrize(
    "choice,expected",
    [
        (
            EligibilityInterpretation.PERCENTAGE_WORDING,
            (SpawningEligibility.ELIGIBLE, SpawningEligibility.ELIGIBLE, SpawningEligibility.INELIGIBLE),
        ),
        (
            EligibilityInterpretation.DRY_YEAR_WORDING,
            (SpawningEligibility.INELIGIBLE, SpawningEligibility.ELIGIBLE, SpawningEligibility.ELIGIBLE),
        ),
    ],
)
def test_eligibility_both_readings_equality(choice, expected):
    assert tuple(spawning_eligibility(DesignClass(c), choice) for c in (50, 75, 95)) == expected
    assert spawning_eligibility(DesignClass(25), None) is SpawningEligibility.UNRESOLVED


@pytest.mark.parametrize("value", [True, 50.0, "75", 0, 74, 100, 25])
def test_invalid_design(value):
    with pytest.raises(TypeError):
        spawning_eligibility(value, EligibilityInterpretation.PERCENTAGE_WORDING)


def test_all_published_values_not_reaveraged_or_clamped():
    expected = [
        ("1.15", "1.3", "1.1", "1.18"),
        ("1.2", "1.25", "1.1", "1.18"),
        ("1.1", "1.3", "1.1", "1.16"),
        ("1.2", "1.25", "1.1", "1.18"),
        ("1.15", "1.2", "1.1", "1.15"),
        ("1.1", "1.2", "1.05", "1.11"),
        ("1.1", "1.2", "1.05", "1.11"),
        ("1.15", "1.25", "1.1", "1.16"),
    ]
    assert tuple(row.row for row in APPENDIX4) == tuple(range(1, 9))
    for row, values in zip(APPENDIX4, expected, strict=True):
        assert (row.migration, row.spawning, row.incubation, row.seasonal) == tuple(Fraction(v) for v in values)
        assert row.starred_headings == STAR_HEADINGS
        assert row.basin and row.species and row.waters and row.phases and row.approximate_dates and row.source
    assert tuple((lo, hi) for _, lo, hi in APPENDIX3) == tuple(
        (Fraction(a), Fraction(b)) for a, b in [("1.10", "1.15"), ("1.25", "1.30"), ("1.05", "1.10"), ("1.13", "1.18")]
    )
    assert APPENDIX4[1].migration > APPENDIX3[0][2]
    assert run()[0].value == Fraction("1.18")
    assert run(basin_row=3)[0].value == Fraction("1.16")


def test_daily_stages_and_explicit_neutral_outside_season():
    days = tuple(Interval(ONSET + timedelta(days=i), ONSET + timedelta(days=i + 1)) for i in range(7))
    observations = tuple(
        FlowSample(
            LOCATION, d, Flow(8), Presence.PRESENT, replace(PROVENANCE, production_method=ProductionMethod.OBSERVED)
        )
        for d in days
    )
    result = run(days, temporal_basis=TemporalBasis.DAILY_STAGE, daily_observations=observations)
    assert tuple(c.value for c in result) == tuple(map(Fraction, ["1.2", "1.2", "1.25", "1.25", "1.1", "1.1", "1"]))
    assert all(c.findings.official_admissibility is OfficialAdmissibility.PENDING for c in result)
    missing = run(days, temporal_basis=TemporalBasis.DAILY_STAGE)
    assert missing[0].presence is Presence.UNSUPPORTED and missing[0].value is None
    assert missing[-1].value == 1


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"timing": None}, "species"),
        ({"eligibility_interpretation": None}, "eligibility"),
        ({"coefficient_interpretation": None}, "interpretation"),
        ({"coefficient_findings": ()}, "coefficient evidence"),
        ({"star_relevance": StarRelevance.AFFECTS_ELIGIBILITY}, "stars"),
        ({"basin_row": None}, "basin row"),
    ],
)
def test_missing_and_unresolved(overrides, reason):
    value = run(**overrides)[0]
    assert value.value is None and value.presence is Presence.UNSUPPORTED
    assert any(reason in r for r in value.reasons)


def test_scoped_support_not_generic_check_passthrough():
    finding = evidence(coefficient_scope(LOCATION, MONTH, PROVENANCE))
    for unsupported in [
        replace(finding, numerical_validity=NumericalValidity.INVALID),
        replace(finding, computability=Computability.UNKNOWN),
        replace(finding, restrictions=(UseRestriction("not for correction", ("spawning_correction",)),)),
        replace(finding, provenance=replace(PROVENANCE, scenario="other")),
        replace(finding, scope=replace(finding.scope, reach="other")),
    ]:
        assert run(coefficient_findings=(unsupported,))[0].value is None
    timing = biological_timing()
    assert (
        run(
            timing=replace(
                timing, findings=replace(timing.findings, scope=replace(timing.findings.scope, period=MONTH))
            )
        )[0].value
        is None
    )
    assert (
        run(
            timing=replace(timing, onset_water_temperature=SignedState(StateVariable.TEMPERATURE, 14, "degC", "water"))
        )[0].value
        is None
    )


def test_study_average_separate_weights_and_period():
    study = WeightedStudy(
        (Fraction("1.2"), Fraction("1.25"), Fraction("1.1")),
        (Fraction(1), Fraction(2), Fraction(1)),
        PERIOD,
        evidence(study_scope("spawning_weighted_average")),
        LOCATION,
    )
    result = run(coefficient_interpretation=CoefficientInterpretation.WEIGHTED_STUDY, study=study)
    assert result[0].value == Fraction("1.2")
    assert result[0].value != APPENDIX4[1].seasonal
    assert (
        run(coefficient_interpretation=CoefficientInterpretation.WEIGHTED_STUDY, study=replace(study, period=MONTH))[
            0
        ].value
        is None
    )
    assert run(coefficient_interpretation=CoefficientInterpretation.WEIGHTED_STUDY)[0].value is None


@pytest.mark.parametrize("shift", [-15, 15])
def test_shift_preserves_duration_and_requires_annual_evidence(shift):
    original = biological_timing()
    shifted = replace(original, annual_shift_days=shift)
    assert shifted.period.seconds == original.period.seconds
    assert shifted.onset - original.onset == timedelta(days=shift)
    assert run(timing=shifted)[0].value is None  # original-period evidence does not transfer
    shifted = replace(shifted, findings=evidence(study_scope("spawning_timing", shifted.period)))
    assert run(timing=shifted)[0].value is not None


@pytest.mark.parametrize("changes", [{"annual_shift_days": 16}, {"stage_days": (2, 0, 2)}, {"species": ""}])
def test_invalid_biology(changes):
    with pytest.raises(ValueError):
        replace(biological_timing(), **changes)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True])
def test_invalid_timed_coefficients(value):
    with pytest.raises((ValueError, TypeError)):
        TimedCoefficient(LOCATION, MONTH, value, PROVENANCE, None)


def test_monthly_cannot_prove_daily_stage_and_partial_month_refused():
    assert run(temporal_basis=TemporalBasis.DAILY_STAGE)[0].value is None
    assert run((PERIOD,))[0].value is None
    assert run(design=DesignClass(95))[0].value == 1
    with pytest.raises(ValueError, match="overlapping"):
        run((MONTH, MONTH))


def test_same_reach_other_section_mapping_or_version_cannot_reuse_evidence():
    for changed in (
        replace(LOCATION, section=CalculationSection("other-section", "1")),
        replace(LOCATION, mapping_version="2"),
        replace(LOCATION, reach=replace(LOCATION.reach, version="2")),
    ):
        assert run(location=changed)[0].value is None
    original = evidence(coefficient_scope(LOCATION, MONTH, PROVENANCE))
    for field in ("source", "data_version", "configuration_version", "software_version"):
        unsupported = replace(original, provenance=replace(PROVENANCE, **{field: "other"}))
        assert run(coefficient_findings=(unsupported,))[0].value is None


def test_simulated_daily_flow_cannot_select_observed_daily_branch():
    day = Interval(ONSET, ONSET + timedelta(days=1))
    simulated = FlowSample(
        LOCATION, day, Flow(8), Presence.PRESENT, replace(PROVENANCE, production_method=ProductionMethod.SIMULATED)
    )
    assert run((day,), temporal_basis=TemporalBasis.DAILY_STAGE, daily_observations=(simulated,))[0].value is None


@pytest.mark.parametrize(
    "field", ["source", "scenario", "reference_member", "data_version", "configuration_version", "software_version"]
)
@pytest.mark.parametrize("operand", ["coefficient", "biological_timing"])
def test_evidence_only_version_change_cannot_validate_itself(field, operand):
    if operand == "coefficient":
        finding = evidence(coefficient_scope(LOCATION, MONTH, PROVENANCE))
        finding = replace(finding, provenance=replace(finding.provenance, **{field: "unrelated"}))
        result = run(coefficient_findings=(finding,))
    else:
        timing = biological_timing()
        finding = replace(timing.findings, provenance=replace(timing.findings.provenance, **{field: "unrelated"}))
        result = run(timing=replace(timing, findings=finding))
    assert result[0].value is None
