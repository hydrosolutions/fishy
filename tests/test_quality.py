"""Configured quality tests use synthetic evidence, not national policy defaults."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.evidence import CheckFinding, Completeness, CorrectionState, ProductionMethod, Provenance
from fishy.flows import Presence
from fishy.physical import ConstituentSample
from fishy.quality import (
    Censoring,
    ChemicalBehavior,
    ChemicalIdentity,
    Comparison,
    GroupMember,
    GroupTarget,
    ObservationAdmission,
    ObservationKind,
    ProfileStatus,
    QualityBounds,
    QualityObservation,
    QualityProfile,
    QualityTarget,
    QualityValue,
    RelativeTarget,
    UnresolvedTarget,
    assess_quality,
    from_constituent_sample,
    quality_range,
)
from fishy.quantities import Volume
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

LOCATION = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
PERIOD = Interval(datetime(2020, 1, 1, tzinfo=UTC), datetime(2020, 1, 2, tzinfo=UTC))
PROVENANCE = Provenance(
    "synthetic", "case", None, "1", "1", "1", ProductionMethod.ILLUSTRATIVE, CorrectionState.ORIGINAL
)
SALT = ChemicalIdentity("salt", "NaCl", "as NaCl", "dissolved", ChemicalBehavior.CONSERVATIVE)
A = ChemicalIdentity("a", "A", "as A", "dissolved", ChemicalBehavior.CONSERVATIVE)
B = ChemicalIdentity("b", "B", "as B", "dissolved", ChemicalBehavior.CONSERVATIVE)


def profile(targets, required=None):
    return QualityProfile(
        "selected",
        "1",
        "synthetic",
        "test instrument",
        "1",
        "test category",
        "screen",
        LOCATION,
        PERIOD,
        "case",
        ProfileStatus.SCENARIO,
        tuple(t.identifier for t in targets) if required is None else required,
        targets,
        "configured at supplied section",
        "defensible supplied bounds",
        "explicit scenario",
    )


def value(n, unit="mg/l"):
    return QualityValue(n, unit)


def observation(n, chemical=SALT, upper=None, unit="mg/l", **kwargs):
    bounds = QualityBounds(value(n, unit), value(n if upper is None else upper, unit), "supplied interval", "synthetic")
    return QualityObservation(
        chemical.identifier,
        chemical,
        bounds,
        LOCATION,
        PERIOD,
        "interval mean",
        Presence.PRESENT,
        PROVENANCE,
        ObservationKind.SYNTHETIC,
        "supplied supported inputs",
        "section interval",
        **kwargs,
    )


def target(limit=500, chemical=SALT, operator=Comparison.LE, identifier="individual", unit="mg/l"):
    return QualityTarget(identifier, chemical, operator, value(limit, unit), "interval mean", "synthetic clause")


def group(operator=Comparison.LE):
    return GroupTarget(
        "group",
        (GroupMember(A, value(100)), GroupMember(B, value(50))),
        operator,
        "interval mean",
        "synthetic rule",
        "configured scenario only",
    )


@pytest.mark.parametrize(
    ("operator", "lo", "hi", "expected"),
    [
        (Comparison.LE, 0, 500, CheckFinding.PASS),
        (Comparison.LE, 501, 600, CheckFinding.FAIL),
        (Comparison.LE, 0, 600, CheckFinding.UNKNOWN),
        (Comparison.LT, 500, 500, CheckFinding.FAIL),
        (Comparison.LT, 0, 500, CheckFinding.UNKNOWN),
        (Comparison.GE, 500, 600, CheckFinding.PASS),
        (Comparison.GE, 0, 499, CheckFinding.FAIL),
        (Comparison.GE, 0, 600, CheckFinding.UNKNOWN),
        (Comparison.GT, 500, 500, CheckFinding.FAIL),
        (Comparison.GT, 500, 600, CheckFinding.UNKNOWN),
    ],
)
def test_whole_interval_and_strict_endpoints(operator, lo, hi, expected):
    result = assess_quality(profile((target(operator=operator),)), (observation(lo, upper=hi),))
    assert result.summary.finding is expected
    assert result.results[0].lower == Fraction(lo, 1000)


def test_profile_override_version_isolation():
    original = profile((target(10),))
    before = assess_quality(original, (observation(8),))
    scenario = original.override(
        identifier="alternative",
        version="2",
        scenario="alternative",
        targets=(target(5),),
        interpretation="hypothetical tighter limit",
    )
    obs = replace(observation(8), provenance=replace(PROVENANCE, scenario="alternative"))
    after = assess_quality(scenario, (obs,))
    assert before.summary.finding is CheckFinding.PASS
    assert after.summary.finding is CheckFinding.FAIL
    assert original.targets[0].limit == value(10)
    assert scenario.parent_profile == "selected@1"
    assert assess_quality(scenario, (observation(8),)).summary.finding is CheckFinding.UNKNOWN
    with pytest.raises(FrozenInstanceError):
        original.version = "2"
    with pytest.raises(ValueError, match="new profile"):
        original.override(identifier="selected", version="1", scenario="x", targets=(target(5),), interpretation="x")


def test_required_failure_survives_missing_member_and_omitted_target():
    selected = profile((target(100, A), group()), ("individual", "group", "required-but-omitted"))
    result = assess_quality(selected, (observation(120, A),))
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert [check.finding for check in result.summary.checks] == [
        CheckFinding.FAIL,
        CheckFinding.UNKNOWN,
        CheckFinding.UNKNOWN,
    ]
    with pytest.raises(ValueError, match="nonempty"):
        profile(())


@pytest.mark.parametrize(
    ("operator", "expected"),
    [
        (Comparison.LE, CheckFinding.PASS),
        (Comparison.LT, CheckFinding.FAIL),
        (Comparison.UNRESOLVED_UPPER, CheckFinding.UNKNOWN),
    ],
)
def test_group_equality_interpretations(operator, expected):
    result = assess_quality(profile((group(operator),)), (observation(40, A), observation(30, B)))
    assert result.results[0].lower == result.results[0].upper == 1
    assert result.summary.finding is expected


def test_groups_intervals_lower_and_range():
    lo = replace(group(Comparison.GE), identifier="group-low", limit=Fraction(1, 2))
    hi = replace(group(), identifier="group-high")
    result = assess_quality(profile((lo, hi)), (observation(40, A, upper=50), observation(10, B, upper=30)))
    assert result.results[0].lower == Fraction(3, 5)
    assert result.results[0].upper == Fraction(11, 10)
    assert result.results[0].check.finding is CheckFinding.PASS
    assert result.results[1].check.finding is CheckFinding.UNKNOWN


def test_individual_range_retains_both_bounds():
    selected = profile(quality_range("salt range", SALT, value(300), value(500), "interval mean", "synthetic"))
    result = assess_quality(selected, (observation(200),))
    assert [r.check.finding for r in result.results] == [CheckFinding.FAIL, CheckFinding.PASS]
    with pytest.raises(ValueError, match="ordered"):
        quality_range("invalid", SALT, value(5), value(3), "mean", "source")


def test_tds_stays_outside_ionic_sum_and_positive_denominators():
    tds = ChemicalIdentity("tds", "dry residue", "dry residue", "dissolved", ChemicalBehavior.TOTAL_DISSOLVED_SOLIDS)
    with pytest.raises(ValueError, match="TDS"):
        replace(group(), members=(GroupMember(tds, value(1000)), GroupMember(A, value(100))))
    for denominator in (value(0), value(3, "degC")):
        with pytest.raises(ValueError, match="positive concentration"):
            GroupMember(A, denominator)
    with pytest.raises(ValueError, match="nonempty"):
        replace(group(), authority="")


def test_non_detect_interval_not_zero_and_unknown_reporting_limit():
    detected = observation(0, upper=600, censoring=Censoring.NON_DETECT)
    result = assess_quality(profile((target(),)), (detected,))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.results[0].upper == Fraction(3, 5)
    unknown = replace(detected, bounds=None, presence=Presence.MISSING, reasons=("unknown reporting limit",))
    assert assess_quality(profile((target(),)), (unknown,)).summary.finding is CheckFinding.UNKNOWN
    assert detected.censoring is Censoring.NON_DETECT


def test_chemical_basis_and_sampling_identity_are_not_inferred():
    ion = ChemicalIdentity("nitrite", "NO2-", "NO2 ion mass", "dissolved", ChemicalBehavior.PROCESS)
    nitrogen = replace(ion, reporting_basis="N in nitrite")
    result = assess_quality(profile((target("0.2", nitrogen),)), (observation("0.2", ion),))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert "reporting basis" in result.results[0].check.reasons[0]
    assert (
        assess_quality(profile((target(),)), (replace(observation(100), basis="annual bulletin"),)).summary.finding
        is CheckFinding.UNKNOWN
    )
    unresolved = UnresolvedTarget("range", "source cell 0,3–3,0 has no selected interpretation", "source table")
    assert assess_quality(profile((unresolved,)), ()).summary.finding is CheckFinding.UNKNOWN


def test_units_nonfinite_negatives_and_immutable_collections():
    assert value(500).value == Fraction(1, 2)
    assert value(500, "mg/L") == value("0.5", "kg/m3")
    for n in (float("nan"), float("inf"), -1):
        with pytest.raises(ValueError):
            value(n)
    with pytest.raises(ValueError, match="unsupported"):
        value(100, "uS/cm")
    with pytest.raises(TypeError):
        replace(SALT, components=["Cl"])
    with pytest.raises(ValueError, match="duplicate"):
        assess_quality(profile((target(),)), (observation(1), observation(2)))


@pytest.mark.parametrize(
    ("name", "unit", "amount", "limit", "operator"),
    [
        ("temperature", "degC", -2, 0, Comparison.LE),
        ("pH", "pH", -1, 0, Comparison.LE),
        ("oxygen", "mg/l", 6, 4, Comparison.GE),
        ("nutrient", "mg/l", 2, 1, Comparison.LE),
    ],
)
def test_supplied_supported_and_unsupported_process_states(name, unit, amount, limit, operator):
    chemical = ChemicalIdentity(name, name, name, "supplied process basis", ChemicalBehavior.PROCESS)
    obs = observation(amount, chemical, unit=unit)
    selected = profile((target(limit, chemical, operator, unit=unit),))
    supported = assess_quality(selected, (obs,))
    assert supported.summary.finding is (CheckFinding.FAIL if name == "nutrient" else CheckFinding.PASS)
    unsupported = replace(obs, presence=Presence.UNSUPPORTED, reasons=("outside model support/domain",))
    assert assess_quality(selected, (unsupported,)).summary.finding is CheckFinding.UNKNOWN


def test_relative_temperature_uses_explicit_supported_reference_and_uncertainty():
    temperature = ChemicalIdentity("temperature", "water temperature", "degC", "water", ChemicalBehavior.PROCESS)
    target_ = RelativeTarget(
        "increase",
        temperature,
        Comparison.LE,
        value(3, "degC"),
        "interval mean",
        "synthetic source",
        "warmest-month-reference",
        "preceding-ten-year warmest month",
        Interval(datetime(2010, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC)),
    )
    selected = profile((target_,))
    current = observation(23, temperature, unit="degC")
    reference = replace(
        observation(20, temperature, unit="degC"),
        identifier="warmest-month-reference",
        basis="preceding-ten-year warmest month",
        interval=Interval(datetime(2010, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC)),
    )
    assert assess_quality(selected, (current,), references=(reference,)).summary.finding is CheckFinding.PASS
    assert assess_quality(selected, (current,)).summary.finding is CheckFinding.UNKNOWN
    uncertain = replace(
        reference, bounds=QualityBounds(value(19, "degC"), value(21, "degC"), "supplied bounds", "study")
    )
    result = assess_quality(selected, (current,), references=(uncertain,))
    assert (result.results[0].lower, result.results[0].upper) == (2, 4)
    assert result.summary.finding is CheckFinding.UNKNOWN


def test_observation_admission_preserves_missing_fields_and_original_identity():
    admission = ObservationAdmission(
        publisher="publisher",
        original_url="https://example.org/original",
        retrieved=date(2026, 9, 19),
        observed=date(2020, 1, 1),
        station="station",
        determinand="salt",
        chemical_form="NaCl",
        unit="mg/l",
        sampling_basis="interval mean",
        quality_flags=("provisional",),
        licence="restricted",
        transformations=(),
    )
    obs = replace(
        observation(100),
        kind=ObservationKind.MEASUREMENT,
        admission=admission,
        provenance=replace(PROVENANCE, production_method=ProductionMethod.OBSERVED),
    )
    result = assess_quality(profile((target(),)), (obs,))
    assert "admission field missing: analytical_method" in result.limitations
    assert result.results[0].observations[0].admission == admission
    assert result.summary.finding is CheckFinding.PASS
    with pytest.raises(ValueError, match="admission"):
        replace(obs, admission=None)


def test_constituent_sample_exact_conversion_without_water_or_mass_mutation():
    sample = ConstituentSample(
        "salt",
        "NaCl",
        "as NaCl",
        PERIOD,
        LOCATION,
        Fraction(9),
        Volume(15),
        Fraction(3, 5),
        Presence.PRESENT,
        PROVENANCE,
        (),
    )
    obs = from_constituent_sample(sample, chemical=SALT, basis="interval mean")
    result = assess_quality(profile((target(),), ("individual", "missing")), (obs,))
    assert result.results[0].lower == Fraction(3, 5)
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert sample.mass_kg == 9 and sample.water == Volume(15)
    assert obs.provenance == sample.provenance
    process = replace(SALT, behavior=ChemicalBehavior.PROCESS)
    assert from_constituent_sample(sample, chemical=process, basis="interval mean").presence is Presence.UNSUPPORTED
    with pytest.raises(ValueError, match="identity"):
        from_constituent_sample(sample, chemical=replace(SALT, reporting_basis="as N"), basis="interval mean")


@pytest.mark.parametrize(
    "presence", [Presence.DRY, Presence.MISSING, Presence.ABSENT, Presence.OUTSIDE_HORIZON, Presence.UNSUPPORTED]
)
def test_physical_unavailable_states_survive_quality_conversion(presence):
    sample = ConstituentSample(
        "salt",
        "NaCl",
        "as NaCl",
        PERIOD,
        LOCATION,
        None,
        None,
        None,
        presence,
        PROVENANCE,
        ("physical " + presence.value,),
    )
    obs = from_constituent_sample(sample, chemical=SALT, basis="interval mean")
    assert obs.presence is presence
    assert assess_quality(profile((target(),)), (obs,)).summary.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "case_id",
    [
        "missing_group_member",
        "censored_upper",
        "unit_conversion",
        "invalid_group_limit",
        "group_equality_interpretations",
        "nitrite_reporting_basis_unresolved",
        "source_range_not_automatically_interval",
        "missing_group_member_preserves_individual_failure",
    ],
)
def test_reviewed_assessment_fixtures(case_id):
    """Original source identifiers map to current public operations, not legacy schemas."""
    if case_id == "missing_group_member":
        result = assess_quality(profile((group(),)), (observation(20, A),))
        assert result.summary.finding is CheckFinding.UNKNOWN
    elif case_id == "censored_upper":
        result = assess_quality(profile((target(),)), (observation(0, upper=600, censoring=Censoring.NON_DETECT),))
        assert result.summary.finding is CheckFinding.UNKNOWN
    elif case_id == "unit_conversion":
        assert value(500).value == Fraction(1, 2)
        assert 10 * value(500).value == 5
    elif case_id == "invalid_group_limit":
        with pytest.raises(ValueError, match="positive concentration"):
            GroupMember(A, value(0))
    elif case_id == "group_equality_interpretations":
        results = tuple(
            assess_quality(profile((group(operator),)), (observation(40, A), observation(30, B))).summary.finding
            for operator in (Comparison.LE, Comparison.LT, Comparison.UNRESOLVED_UPPER)
        )
        assert results == (CheckFinding.PASS, CheckFinding.FAIL, CheckFinding.UNKNOWN)
    elif case_id == "nitrite_reporting_basis_unresolved":
        ion = ChemicalIdentity("nitrite", "NO2-", "NO2 ion mass", "dissolved", ChemicalBehavior.PROCESS)
        nitrogen = replace(ion, reporting_basis="N in nitrite")
        assert (
            assess_quality(profile((target("0.2", nitrogen),)), (observation("0.2", ion),)).summary.finding
            is CheckFinding.UNKNOWN
        )
    elif case_id == "source_range_not_automatically_interval":
        unresolved = UnresolvedTarget("range", "0,3–3,0 uninterpreted context-dependent source cell", "source table")
        assert assess_quality(profile((unresolved,)), ()).summary.finding is CheckFinding.UNKNOWN
    else:
        result = assess_quality(profile((target(100, A), group())), (observation(120, A),))
        assert result.summary.finding is CheckFinding.FAIL
        assert result.summary.completeness is Completeness.INCOMPLETE


def test_relative_reference_rejects_unrelated_interval():
    temperature = ChemicalIdentity("temperature", "water temperature", "degC", "water", ChemicalBehavior.PROCESS)
    reference_period = Interval(datetime(2010, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC))
    relative = RelativeTarget(
        "increase",
        temperature,
        Comparison.LE,
        value(3, "degC"),
        "interval mean",
        "source",
        "reference",
        "preceding-ten-year warmest month",
        reference_period,
    )
    wrong = replace(
        observation(20, temperature, unit="degC"), identifier="reference", basis="preceding-ten-year warmest month"
    )
    result = assess_quality(profile((relative,)), (observation(23, temperature, unit="degC"),), references=(wrong,))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert "reference interval mismatch" in result.results[0].check.reasons


def test_simulated_provenance_cannot_become_original_measurement():
    simulated = replace(PROVENANCE, production_method=ProductionMethod.SIMULATED)
    with pytest.raises(ValueError, match="production method"):
        replace(
            observation(100), provenance=simulated, kind=ObservationKind.MEASUREMENT, admission=ObservationAdmission()
        )


def test_chemical_behavior_cannot_be_inferred_from_omission():
    with pytest.raises(TypeError):
        ChemicalIdentity("oxygen", "O2", "as O2", "dissolved")  # ty: ignore[missing-argument]


def test_supplied_supported_conversion_is_explicit_scoped_and_attributable():
    from fishy.quality import QualityConversion, convert_quality

    ion = ChemicalIdentity("nitrite", "NO2-", "NO2 ion mass", "dissolved", ChemicalBehavior.PROCESS)
    nitrogen = replace(ion, reporting_basis="N in nitrite")
    observed = observation("0.2", ion)
    selected = profile((target("0.1", nitrogen),))
    assert assess_quality(selected, (observed,)).summary.finding is CheckFinding.UNKNOWN
    conversion = QualityConversion(
        ion, nitrogen, Fraction(14, 46), "supplied hypothetical molar basis", observed.domain
    )
    converted = convert_quality(observed, conversion)
    assert converted.bounds is not None
    assert converted.bounds.lower.value == Fraction(7, 115000)
    assert assess_quality(selected, (converted,)).summary.finding is CheckFinding.PASS
    assert observed.chemical == ion
    assert converted.provenance.source == observed.provenance.source
    assert "factor=7/23" in converted.provenance.dependencies[-1]
    with pytest.raises(ValueError, match="domain"):
        convert_quality(observed, replace(conversion, domain="other compartment"))
    with pytest.raises(ValueError, match="source chemical"):
        convert_quality(converted, conversion)
    with pytest.raises(ValueError, match="positive"):
        replace(conversion, factor=Fraction(0))


@pytest.mark.parametrize("kind", ["individual", "group", "reference"])
def test_excluded_warmup_cannot_pass_quality_checks(kind):
    blocked = replace(observation(10, A), provenance=replace(PROVENANCE, excluded_warmup=(PERIOD,)))
    if kind == "individual":
        selected = profile((target(100, A), target(100, B, identifier="independent")))
        result = assess_quality(selected, (blocked, observation(10, B)))
        assert result.results[1].check.finding is CheckFinding.PASS
    elif kind == "group":
        result = assess_quality(profile((group(),)), (blocked, observation(10, B)))
    else:
        reference = replace(blocked, identifier="reference")
        relative = RelativeTarget(
            "relative", A, Comparison.LE, value(100), "interval mean", "source", "reference", "interval mean", PERIOD
        )
        result = assess_quality(profile((relative,)), (observation(20, A),), references=(reference,))
    assert result.summary.finding is CheckFinding.UNKNOWN
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert "warm-up" in " ".join(result.results[0].check.reasons)


def test_synthetic_kind_cannot_claim_observed_production():
    with pytest.raises(ValueError, match="production method"):
        replace(observation(100), provenance=replace(PROVENANCE, production_method=ProductionMethod.OBSERVED))


@pytest.mark.parametrize("kind", list(ObservationKind))
@pytest.mark.parametrize("method", list(ProductionMethod))
def test_observation_kind_and_production_method_consistency(kind, method):
    permitted = {
        ObservationKind.MEASUREMENT: {ProductionMethod.OBSERVED, ProductionMethod.IMPORTED},
        ObservationKind.AGGREGATE: {ProductionMethod.OBSERVED, ProductionMethod.IMPORTED},
        ObservationKind.MODEL: {
            ProductionMethod.SIMULATED,
            ProductionMethod.RECONSTRUCTED,
            ProductionMethod.IMPORTED,
            ProductionMethod.ILLUSTRATIVE,
        },
        ObservationKind.SYNTHETIC: {ProductionMethod.ILLUSTRATIVE, ProductionMethod.IMPORTED},
    }
    changes = {
        "kind": kind,
        "provenance": replace(PROVENANCE, production_method=method),
        "admission": ObservationAdmission(),
    }
    if method in permitted[kind]:
        assert replace(observation(100), **changes).provenance.production_method is method
    else:
        with pytest.raises(ValueError, match="production method"):
            replace(observation(100), **changes)


@pytest.mark.parametrize(
    "start,end,expected",
    [
        (-24, 0, CheckFinding.PASS),
        (24, 48, CheckFinding.PASS),
        (12, 48, CheckFinding.UNKNOWN),
        (-12, 12, CheckFinding.UNKNOWN),
    ],
)
def test_warmup_overlap_uses_half_open_actual_intervals(start, end, expected):
    exclusion = Interval(PERIOD.start + timedelta(hours=start), PERIOD.start + timedelta(hours=end))
    obs = replace(observation(100), provenance=replace(PROVENANCE, excluded_warmup=(exclusion,)))
    assert assess_quality(profile((target(),)), (obs,)).summary.finding is expected
