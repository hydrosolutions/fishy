"""Source-cell, scope and use-mapping discriminators for the held Order111 replica."""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from fishy.evidence import CheckFinding, Completeness, CorrectionState, ProductionMethod, Provenance
from fishy.flows import Presence
from fishy.quality import Comparison
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval
from fishy.water_classification import (
    COMMENCEMENT,
    CellInterpretation,
    ClassificationObservation,
    Order111Profile,
    QualifiedCell,
    RangeMeaning,
    RatioTypography,
    SourceValue,
    UseFinding,
    UseInterpretation,
    UseMapping,
    WaterClass,
    WaterScope,
    WaterUse,
    assess_order111,
    assess_order111_use,
    source_row,
)
from fishy.water_classification_catalogue import SOURCE_ROWS

LOCATION = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
PERIOD = Interval(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))
PROVENANCE = Provenance(
    "synthetic discriminator",
    "scenario",
    None,
    "test",
    "1",
    "1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
)


def profile(*ids, choices=()):
    return Order111Profile(
        "selected source profile",
        "1",
        "scenario",
        LOCATION,
        PERIOD,
        WaterScope.RIVER,
        date(2026, 1, 2),
        ids,
        "supported daily sample",
        choices,
    )


def observation(row_id, value, upper=None, **kwargs):
    row = source_row(row_id)
    return ClassificationObservation(
        row_id,
        SourceValue(value, value if upper is None else upper, row.unit, row.name),
        LOCATION,
        PERIOD,
        "supported daily sample",
        Presence.PRESENT,
        PROVENANCE,
        **kwargs,
    )


def choice(row_id, cls, **kwargs):
    return CellInterpretation(row_id, WaterClass(cls), "explicit synthetic source interpretation", **kwargs)


def cell(row_id, cls, value, interpretation=None, **kwargs):
    result = assess_order111(
        profile(row_id, choices=() if interpretation is None else (interpretation,)),
        (observation(row_id, value, **kwargs),),
    )
    return result.classes[cls - 1].cells[0]


@pytest.mark.parametrize("cls,value", [(1, "0.5"), (2, "1.25"), (3, "2"), (4, "3"), (5, "3.75"), (6, "4.1")])
def test_numerical_match_each_class_without_false_unique_algorithm(cls, value):
    row_id = "order111:63"
    choices = tuple(choice(row_id, c, range_meaning=RangeMeaning.CLOSED) for c in range(2, 6))
    result = assess_order111(profile(row_id, choices=choices), (observation(row_id, value),))
    assert result.supported_matches == (WaterClass(cls),)
    assert result.unknown_classes == ()
    assert result.classes[cls - 1].summary.completeness is Completeness.COMPLETE
    assert result.source_version.startswith("Order 111")


def test_printed_gap_not_smoothed():
    row_id = "order111:63"
    choices = tuple(choice(row_id, c, range_meaning=RangeMeaning.CLOSED) for c in range(2, 6))
    result = assess_order111(profile(row_id, choices=choices), (observation(row_id, "1.505"),))
    assert result.supported_matches == ()
    assert all(x.summary.finding is CheckFinding.FAIL for x in result.classes)


def test_duplicate_limits_preserve_multiple_matches():
    result = assess_order111(profile("order111:02"), (observation("order111:02", 5),))
    assert result.supported_matches == (WaterClass.TWO, WaterClass.THREE)
    assert result.unknown_classes == (WaterClass.FOUR, WaterClass.FIVE)
    assert cell("order111:02", 4, 4).check.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "row_id,cls,value,finding",
    [
        ("order111:02", 1, 6, CheckFinding.PASS),
        ("order111:02", 1, "5.999", CheckFinding.FAIL),
        ("order111:03", 1, 90, CheckFinding.FAIL),
        ("order111:03", 1, "90.001", CheckFinding.PASS),
        ("order111:06", 1, 7, CheckFinding.FAIL),
        ("order111:07", 1, 15, CheckFinding.PASS),
        ("order111:23", 6, 15, CheckFinding.PASS),
        ("order111:65", 6, 5000, CheckFinding.FAIL),
        ("order111:65", 6, 5200, CheckFinding.PASS),
        ("order111:65", 6, 5500, CheckFinding.FAIL),
    ],
)
def test_printed_operators_and_open_ranges(row_id, cls, value, finding):
    assert cell(row_id, cls, value).check.finding is finding


def test_bare_values_require_explicit_direction_and_keep_raw():
    assert cell("order111:04", 1, 2).check.finding is CheckFinding.UNKNOWN
    c = choice("order111:04", 1, bare_operator=Comparison.LE)
    result = cell("order111:04", 1, 2, c)
    assert result.check.finding is CheckFinding.PASS
    assert result.raw_cell == "2,1"
    assert result.interpretation == c
    assert (
        cell("order111:04", 1, 2, choice("order111:04", 1, bare_operator=Comparison.GE)).check.finding
        is CheckFinding.FAIL
    )


def test_range_choices_and_ph_disjunction():
    assert cell("order111:08", 1, 7).check.finding is CheckFinding.UNKNOWN
    assert (
        cell("order111:08", 1, "6.5", choice("order111:08", 1, range_meaning=RangeMeaning.CLOSED)).check.finding
        is CheckFinding.PASS
    )
    assert (
        cell("order111:08", 1, "6.5", choice("order111:08", 1, range_meaning=RangeMeaning.OPEN)).check.finding
        is CheckFinding.FAIL
    )
    c = choice("order111:08", 6, range_meaning=RangeMeaning.OUTSIDE)
    assert cell("order111:08", 6, 9, c).check.finding is CheckFinding.FAIL
    assert cell("order111:08", 6, "9.1", c).check.finding is CheckFinding.PASS
    assert cell("order111:08", 6, 5, c, upper=10).check.finding is CheckFinding.UNKNOWN
    assert (
        cell("order111:22", 2, 40, choice("order111:22", 2, range_meaning=RangeMeaning.CLOSED)).check.finding
        is CheckFinding.PASS
    )
    assert (
        cell("order111:22", 2, 50, choice("order111:22", 2, range_meaning=RangeMeaning.CLOSED)).check.finding
        is CheckFinding.FAIL
    )


@pytest.mark.parametrize(
    "selection,value,finding",
    [
        (QualifiedCell.INDUSTRIAL_CALCIUM, 160, CheckFinding.FAIL),
        (QualifiedCell.OTHER_CALCIUM, 160, CheckFinding.PASS),
    ],
)
def test_calcium_qualification(selection, value, finding):
    assert cell("order111:18", 6, value).check.finding is CheckFinding.UNKNOWN
    assert (
        cell(
            "order111:18", 6, value, choice("order111:18", 6, qualified_cell=selection, bare_operator=Comparison.LE)
        ).check.finding
        is finding
    )


def test_astana_phosphate_qualification_and_no_ion_conversion():
    for selection, expected in [
        (QualifiedCell.ASTANA_PHOSPHATE, CheckFinding.PASS),
        (QualifiedCell.OTHER_PHOSPHATE, CheckFinding.FAIL),
    ]:
        assert (
            cell(
                "order111:32", 3, 2, choice("order111:32", 3, qualified_cell=selection, bare_operator=Comparison.LE)
            ).check.finding
            is expected
        )
    row_id = "order111:26"
    sample = observation(row_id, 10)
    sample = replace(sample, value=SourceValue(10, 10, "мг N/л", "nitrate as nitrogen"))
    result = assess_order111(profile(row_id), (sample,))
    assert result.classes[0].summary.finding is CheckFinding.UNKNOWN
    assert "form" in result.classes[0].cells[0].check.reasons[0]


def test_background_preserved_and_missing_class6_plus_not_repaired():
    row = source_row("order111:12")
    background = SourceValue(10, 10, row.unit, row.name)
    c = choice(row.identifier, 1, bare_operator=Comparison.LE)
    assert cell(row.identifier, 1, "10.25", c, background=background).check.finding is CheckFinding.PASS
    assert cell(row.identifier, 1, "10.26", c, background=background).check.finding is CheckFinding.FAIL
    assert cell(row.identifier, 1, 10, c).check.finding is CheckFinding.UNKNOWN
    assert cell(row.identifier, 6, 30, background=background).check.finding is CheckFinding.UNKNOWN


def test_row70_typography_never_silently_repaired():
    assert source_row("order111:70").cells == ("<103", ">103", "103-102", "<102", "<102", "<102")
    assert cell("order111:70", 1, 500).check.finding is CheckFinding.UNKNOWN
    literal = choice("order111:70", 1, ratio_typography=RatioTypography.LITERAL_DIGITS)
    power = choice("order111:70", 1, ratio_typography=RatioTypography.POWERS_OF_TEN)
    assert cell("order111:70", 1, 500, literal).check.finding is CheckFinding.FAIL
    assert cell("order111:70", 1, 500, power).check.finding is CheckFinding.PASS
    c = choice("order111:70", 3, ratio_typography=RatioTypography.POWERS_OF_TEN, range_meaning=RangeMeaning.CLOSED)
    assert cell("order111:70", 3, 500, c).check.finding is CheckFinding.UNKNOWN
    assert (
        cell("order111:70", 3, 500, replace(c, range_meaning=RangeMeaning.CLOSED_SORTED)).check.finding
        is CheckFinding.PASS
    )


def test_unresolved_cells_and_raw_catalogue_identity():
    assert len(SOURCE_ROWS) == 84
    assert len({x.identifier for x in SOURCE_ROWS}) == 84
    assert len([x for x in SOURCE_ROWS if x.printed_row == "41"]) == 4
    assert not any(x.printed_row == "42" for x in SOURCE_ROWS)
    for row_id in ("order111:01", "order111:58-dissolved", "order111:68", "order111:69", "order111:67"):
        assert cell(row_id, 1, 0).check.finding is CheckFinding.UNKNOWN
    assert source_row("order111:58-dissolved").unit == "-"


def test_known_failure_survives_missing_required_cell():
    result = assess_order111(profile("order111:02", "order111:03"), (observation("order111:02", 2),))
    assert result.classes[0].summary.finding is CheckFinding.FAIL
    assert result.classes[0].summary.completeness is Completeness.INCOMPLETE
    assert result.classes[0].cells[1].observation is None
    assert assess_order111(profile("order111:02"), ()).unknown_classes == tuple(WaterClass)


@pytest.mark.parametrize("scope", list(WaterScope))
def test_applicability(scope):
    p = replace(profile("order111:02"), scope=scope)
    result = assess_order111(p, (observation("order111:02", 6),))
    eligible = scope in (WaterScope.RIVER, WaterScope.CANAL, WaterScope.IN_CHANNEL_RESERVOIR)
    assert result.classes[0].summary.finding is (CheckFinding.PASS if eligible else CheckFinding.UNKNOWN)


def test_commencement_and_exact_identity_support():
    p = profile("order111:02")
    assert date(2025, 6, 10) == COMMENCEMENT
    result = assess_order111(replace(p, calculation_date=date(2025, 6, 9)), (observation("order111:02", 6),))
    assert result.unknown_classes == tuple(WaterClass)
    for sample in (
        replace(observation("order111:02", 6), basis="monthly mean"),
        replace(observation("order111:02", 6), provenance=replace(PROVENANCE, scenario="other")),
        replace(observation("order111:02", 6), presence=Presence.UNSUPPORTED, reasons=("oxygen process unsupported",)),
    ):
        assert assess_order111(p, (sample,)).unknown_classes == tuple(WaterClass)


@pytest.mark.parametrize(
    "mapping,expected",
    [
        (None, UseFinding.UNRESOLVED),
        (UseMapping.DESCRIPTIVE, UseFinding.CONDITIONAL),
        (UseMapping.MATRIX, UseFinding.NOT_PERMITTED),
    ],
)
def test_class4_drinking_conflict_all_branches(mapping, expected):
    interpretation = None if mapping is None else UseInterpretation(mapping, "labelled synthetic scenario")
    result = assess_order111_use(WaterClass.FOUR, WaterUse.DRINKING_INTENSIVE, interpretation)
    assert result.finding is expected
    assert result.descriptive.finding is UseFinding.CONDITIONAL
    assert result.matrix.finding is UseFinding.NOT_PERMITTED
    assert "intensive" in result.descriptive.conditions[0]
    assert any("treatment adequacy" in x for x in result.limitations)


@pytest.mark.parametrize(
    "use,last_class",
    [
        (WaterUse.ECOSYSTEM, 2),
        (WaterUse.SALMONIDS, 2),
        (WaterUse.CYPRINIDS, 3),
        (WaterUse.DRINKING_SIMPLE, 2),
        (WaterUse.DRINKING_NORMAL, 3),
        (WaterUse.DRINKING_INTENSIVE, 3),
        (WaterUse.RECREATION, 3),
        (WaterUse.IRRIGATION_UNTREATED, 4),
        (WaterUse.IRRIGATION_SETTLING, 5),
        (WaterUse.INDUSTRY, 5),
        (WaterUse.HYDROPOWER, 6),
        (WaterUse.TRANSPORT, 6),
        (WaterUse.MINING, 6),
    ],
)
def test_every_matrix_row_and_class(use, last_class):
    for cls in WaterClass:
        result = assess_order111_use(cls, use, UseInterpretation(UseMapping.MATRIX, "source matrix scenario"))
        assert result.finding is (UseFinding.PERMITTED if cls <= last_class else UseFinding.NOT_PERMITTED)


def test_descriptive_conditions_and_separate_sanitary_notes():
    for cls in WaterClass:
        for use in WaterUse:
            result = assess_order111_use(cls, use, UseInterpretation(UseMapping.DESCRIPTIVE, "source description"))
            assert result.finding is result.descriptive.finding
    assert assess_order111_use(WaterClass.TWO, WaterUse.DRINKING_SIMPLE).sanitary_cross_references
    assert assess_order111_use(WaterClass.FIVE, WaterUse.IRRIGATION_SETTLING).sanitary_cross_references
    assert assess_order111_use(WaterClass.SIX, WaterUse.MINING).descriptive.conditions


def test_invalid_domain_inputs_and_immutable_scenarios():
    with pytest.raises(ValueError):
        profile()
    with pytest.raises(ValueError):
        profile("order111:02", "order111:02")
    with pytest.raises(ValueError):
        profile("absent-row")
    with pytest.raises(ValueError):
        observation("order111:02", -1)
    with pytest.raises(ValueError):
        SourceValue(float("nan"), 1, "mg/l", "oxygen")
    with pytest.raises(ValueError):
        SourceValue(2, 1, "mg/l", "oxygen")
    with pytest.raises(ValueError):
        assess_order111(profile("order111:02"), (observation("order111:02", 6),) * 2)
    with pytest.raises(TypeError):
        assess_order111_use(4, WaterUse.DRINKING_INTENSIVE)  # ty: ignore[invalid-argument-type]
    p = profile("order111:04")
    earlier = assess_order111(p, (observation("order111:04", 2),))
    changed = replace(p, version="2", interpretations=(choice("order111:04", 1, bare_operator=Comparison.LE),))
    assert assess_order111(changed, (observation("order111:04", 2),)).classes[0].summary.finding is CheckFinding.PASS
    assert earlier.classes[0].summary.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "row_id,cls,kwargs",
    [
        ("order111:02", 1, {"bare_operator": Comparison.LE}),
        ("order111:02", 1, {"qualified_cell": QualifiedCell.ASTANA_PHOSPHATE}),
        ("order111:02", 1, {"range_meaning": RangeMeaning.CLOSED}),
        ("order111:02", 1, {"ratio_typography": RatioTypography.POWERS_OF_TEN}),
        ("order111:32", 3, {"qualified_cell": QualifiedCell.INDUSTRIAL_CALCIUM}),
        ("order111:63", 2, {"range_meaning": RangeMeaning.OUTSIDE}),
    ],
)
def test_unused_or_misattributed_interpretations_rejected(row_id, cls, kwargs):
    with pytest.raises(ValueError, match="interpretation"):
        choice(row_id, cls, **kwargs)


def test_class5_industrial_settling_qualification_not_silently_scoped():
    result = assess_order111_use(WaterClass.FIVE, WaterUse.INDUSTRY)
    assert result.descriptive.finding is UseFinding.UNRESOLVED
    assert "settling" in " ".join(result.descriptive.conditions)
    assert result.matrix.finding is UseFinding.PERMITTED
    assert result.finding is UseFinding.UNRESOLVED


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", "distinct supplied laboratory source"),
        ("reference_member", "separate reference member"),
        ("data_version", "revised laboratory dataset"),
        ("configuration_version", "revised observation configuration"),
        ("software_version", "revised producer software"),
    ],
)
def test_lineage_changes_retained_without_false_acceptance(field, value):
    sample = observation("order111:02", 6)
    changed = replace(sample, provenance=replace(sample.provenance, **{field: value}))
    result = assess_order111(profile(sample.row_id), (changed,))
    assert result.classes[0].summary.finding is CheckFinding.PASS
    used = result.classes[0].cells[0].observation
    assert used is not None
    assert used.provenance == changed.provenance
    assert (
        "Scientific adequacy and official admissibility require separately scoped evidence findings"
        in result.limitations
    )


def test_future_reference_is_attributed_numerical_scenario_not_present_climate_acceptance():
    from fishy.evidence import ReferenceKind

    sample = observation("order111:02", 6)
    future = replace(
        sample,
        provenance=replace(
            sample.provenance,
            reference_kind=ReferenceKind.FUTURE_CLIMATE_STRESS,
            limitations=("future stress illustration, not observed present-climate evidence",),
        ),
    )
    result = assess_order111(profile(sample.row_id), (future,))
    assert result.classes[0].summary.finding is CheckFinding.PASS
    assert result.classes[0].cells[0].observation == future
    assert "future stress illustration, not observed present-climate evidence" in result.limitations


def test_payload_scope_and_scenario_are_checked_against_independent_profile():
    sample = observation("order111:02", 6)
    incompatible = (
        replace(sample, provenance=replace(sample.provenance, scenario="unrelated scenario")),
        replace(sample, location=replace(LOCATION, section=CalculationSection("unrelated-section", "1"))),
        replace(sample, interval=Interval(datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC))),
    )
    for changed in incompatible:
        result = assess_order111(profile(sample.row_id), (changed,))
        assert result.supported_matches == ()
        assert result.unknown_classes == tuple(WaterClass)
        assert all(item.cells[0].check.reasons for item in result.classes)


def test_macrobenthos_numeric_alternative_is_evaluable():
    c = choice("order111:64-ratio", 6, range_meaning=RangeMeaning.CLOSED)
    result = cell("order111:64-ratio", 6, 90, c)
    assert result.check.finding is CheckFinding.PASS
    assert "или макробентос отсутствует" in result.raw_cell


@pytest.mark.parametrize(
    "value,meaning,expected",
    [
        (86, RangeMeaning.CLOSED, CheckFinding.PASS),
        (100, RangeMeaning.CLOSED, CheckFinding.PASS),
        (86, RangeMeaning.OPEN, CheckFinding.FAIL),
        (100, RangeMeaning.OPEN, CheckFinding.FAIL),
        (85, RangeMeaning.CLOSED, CheckFinding.FAIL),
    ],
)
def test_macrobenthos_numeric_branch_endpoints(value, meaning, expected):
    from fishy.water_classification import MacroBenthos

    assert (
        cell(
            "order111:64-ratio",
            6,
            value,
            choice("order111:64-ratio", 6, range_meaning=meaning),
            macro_benthos=MacroBenthos.PRESENT,
        ).check.finding
        is expected
    )


def test_macrobenthos_qualitative_alternative_and_unknown_not_zero():
    from fishy.water_classification import MacroBenthos

    c = choice("order111:64-ratio", 6, range_meaning=RangeMeaning.CLOSED)
    assert cell("order111:64-ratio", 6, 85, c).check.finding is CheckFinding.UNKNOWN
    sample = ClassificationObservation(
        "order111:64-ratio",
        None,
        LOCATION,
        PERIOD,
        "supported daily sample",
        Presence.PRESENT,
        PROVENANCE,
        macro_benthos=MacroBenthos.ABSENT,
    )
    result = assess_order111(profile(sample.row_id), (sample,))
    assert result.supported_matches == (WaterClass.SIX,)
    assert result.unknown_classes == tuple(WaterClass)[:5]
    used = result.classes[5].cells[0].observation
    assert used is not None and used.value is None
    mismatched = replace(sample, location=replace(LOCATION, section=CalculationSection("different", "1")))
    assert assess_order111(profile(sample.row_id), (mismatched,)).supported_matches == ()
    with pytest.raises(ValueError, match="defined abundance ratio"):
        observation(sample.row_id, 0, macro_benthos=MacroBenthos.ABSENT)
    with pytest.raises(ValueError, match="only"):
        observation("order111:02", 6, macro_benthos=MacroBenthos.PRESENT)


def test_missing_correction_provenance_cannot_supply_numeric_payload():
    with pytest.raises(ValueError, match="missing"):
        replace(observation("order111:02", 6), provenance=replace(PROVENANCE, correction_state=CorrectionState.MISSING))


@pytest.mark.parametrize("meaning", [RangeMeaning.CLOSED, RangeMeaning.OPEN])
def test_fully_printed_endpoint_operators_reject_unused_interpretation(meaning):
    with pytest.raises(ValueError, match="interpretation"):
        choice("order111:65", 6, range_meaning=meaning)


def test_macrobenthos_ratio_cannot_exceed_subset_percentage():
    with pytest.raises(ValueError, match="100"):
        observation("order111:64-ratio", 101)


def interpreted_unit_result(row_id, value, choices):
    row = source_row(row_id)
    sample = observation(row_id, value)
    selected = choices[0].unit_basis
    assert selected is not None
    sample = replace(sample, value=SourceValue(value, value, selected.value, row.name))
    return assess_order111(profile(row_id, choices=choices), (sample,))


@pytest.mark.parametrize(
    "row_id,values",
    [
        ("order111:68", ("0.25", "0.75", "2", "4", "7", "10.25")),
        ("order111:69", ("0.25", "2", "7", "20", "70", "110")),
    ],
)
def test_bacterial_counts_all_six_classes_with_explicit_scaled_unit_interpretation(row_id, values):
    from fishy.water_classification import UnitBasis

    unit = UnitBasis.TOTAL_BACTERIA_MILLIONS_PER_ML if row_id.endswith("68") else UnitBasis.SAPROPHYTES_THOUSANDS_PER_ML
    choices = tuple(
        choice(row_id, c, unit_basis=unit, range_meaning=RangeMeaning.CLOSED if c in range(2, 6) else None)
        for c in range(1, 7)
    )
    for cls, value in enumerate(values, 1):
        result = interpreted_unit_result(row_id, value, choices)
        assert result.supported_matches == (WaterClass(cls),)
        assert result.unknown_classes == ()
        assert result.classes[cls - 1].cells[0].row.unit != unit.value
    assert cell(row_id, 1, "0.25").check.finding is CheckFinding.UNKNOWN
    # Source gaps and strict end caps survive the unit interpretation.
    gap = "1.05" if row_id.endswith("68") else "5.05"
    assert interpreted_unit_result(row_id, gap, choices).supported_matches == ()
    cap = "10.5" if row_id.endswith("68") else "120"
    assert interpreted_unit_result(row_id, cap, choices).classes[5].summary.finding is CheckFinding.FAIL


def test_missing_dissolved_arsenic_unit_requires_explicit_attributed_choice():
    from fishy.water_classification import UnitBasis

    row_id = "order111:58-dissolved"
    c = choice(row_id, 1, unit_basis=UnitBasis.DISSOLVED_ARSENIC_MG_PER_L, bare_operator=Comparison.LE)
    result = interpreted_unit_result(row_id, "0.001", (c,))
    assert result.classes[0].summary.finding is CheckFinding.PASS
    assert result.classes[0].cells[0].row.unit == "-"
    assert (
        cell(row_id, 1, "0.001", choice(row_id, 1, bare_operator=Comparison.LE)).check.finding is CheckFinding.UNKNOWN
    )
    assert interpreted_unit_result(row_id, "0.003", (c,)).classes[0].summary.finding is CheckFinding.FAIL


@pytest.mark.parametrize(
    "season,value,expected",
    [
        ("summer", 20, CheckFinding.PASS),
        ("summer", 28, CheckFinding.PASS),
        ("summer", 29, CheckFinding.FAIL),
        ("winter", 5, CheckFinding.PASS),
        ("winter", 8, CheckFinding.PASS),
        ("winter", 4, CheckFinding.FAIL),
    ],
)
def test_merged_temperature_explicit_shared_seasonal_condition(season, value, expected):
    from fishy.water_classification import TemperatureSeason, UnitBasis

    selected = TemperatureSeason.SUMMER if season == "summer" else TemperatureSeason.WINTER
    choices = tuple(
        choice(
            "order111:01",
            c,
            unit_basis=UnitBasis.TEMPERATURE_CELSIUS,
            temperature_season=selected,
            range_meaning=RangeMeaning.CLOSED,
        )
        for c in range(1, 7)
    )
    result = interpreted_unit_result("order111:01", value, choices)
    assert all(x.summary.finding is expected for x in result.classes)
    assert result.classes[0].cells[0].raw_cell.startswith("Летом")
    assert result.classes[5].cells[0].raw_cell.startswith("Зимой")
    assert cell("order111:01", 1, value).check.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "row_id,cls,state,expected",
    [
        ("order111:66", 1, "absent", CheckFinding.PASS),
        ("order111:66", 2, "traces", CheckFinding.FAIL),
        ("order111:67", 1, "absent", CheckFinding.PASS),
        ("order111:67", 4, "traces", CheckFinding.FAIL),
        ("order111:67", 5, "traces", CheckFinding.PASS),
        ("order111:67", 6, "absent", CheckFinding.FAIL),
    ],
)
def test_supplied_qualitative_states_do_not_become_numeric_zero(row_id, cls, state, expected):
    from fishy.water_classification import QualitativeMeaning, QualitativeState

    sample = ClassificationObservation(
        row_id,
        None,
        LOCATION,
        PERIOD,
        "supported daily sample",
        Presence.PRESENT,
        PROVENANCE,
        qualitative=QualitativeState(state),
    )
    c = choice(row_id, cls, qualitative_meaning=QualitativeMeaning.EXACT_STATE)
    result = assess_order111(profile(row_id, choices=(c,)), (sample,))
    assert result.classes[cls - 1].summary.finding is expected
    assert assess_order111(profile(row_id), (sample,)).classes[cls - 1].summary.finding is CheckFinding.UNKNOWN
    if row_id == "order111:66":
        assert result.classes[2].summary.finding is CheckFinding.UNKNOWN
    with pytest.raises(ValueError, match="missing"):
        replace(sample, provenance=replace(PROVENANCE, correction_state=CorrectionState.MISSING))


def test_interpretations_cannot_change_unrelated_unit_or_qualitative_cells():
    from fishy.water_classification import QualitativeMeaning, TemperatureSeason, UnitBasis

    with pytest.raises(ValueError, match="unit interpretation"):
        choice("order111:02", 1, unit_basis=UnitBasis.DISSOLVED_ARSENIC_MG_PER_L)
    with pytest.raises(ValueError, match="seasonal interpretation"):
        choice("order111:02", 1, temperature_season=TemperatureSeason.SUMMER)
    with pytest.raises(ValueError, match="qualitative interpretation"):
        choice("order111:66", 3, qualitative_meaning=QualitativeMeaning.EXACT_STATE)


@pytest.mark.parametrize("row", SOURCE_ROWS, ids=lambda row: row.identifier)
def test_every_source_cell_has_attributed_evaluation_route(row):
    """Coverage, not an assertion that these synthetic interpretations are accepted law."""
    import re

    from fishy.water_classification import (
        MacroBenthos,
        QualitativeMeaning,
        QualitativeState,
        TemperatureSeason,
        UnitBasis,
    )

    for cls in WaterClass:
        raw = row.cells[cls - 1]
        options = {}
        sample = observation(row.identifier, 1)
        if row.identifier == "order111:01":
            options.update(
                unit_basis=UnitBasis.TEMPERATURE_CELSIUS,
                temperature_season=TemperatureSeason.SUMMER,
                range_meaning=RangeMeaning.CLOSED,
            )
        elif row.identifier == "order111:58-dissolved":
            options["unit_basis"] = UnitBasis.DISSOLVED_ARSENIC_MG_PER_L
        elif row.identifier == "order111:68":
            options["unit_basis"] = UnitBasis.TOTAL_BACTERIA_MILLIONS_PER_ML
        elif row.identifier == "order111:69":
            options["unit_basis"] = UnitBasis.SAPROPHYTES_THOUSANDS_PER_ML
        elif row.identifier == "order111:70":
            options["ratio_typography"] = RatioTypography.LITERAL_DIGITS
        if row.identifier == "order111:12" and cls is WaterClass.SIX:
            from fishy.water_classification import BackgroundArithmetic

            options["background_arithmetic"] = BackgroundArithmetic.ADDITIVE_INCREMENT
        if raw in ("отс.", "следы"):
            options["qualitative_meaning"] = QualitativeMeaning.EXACT_STATE
            sample = replace(sample, value=None, qualitative=QualitativeState.ABSENT)
        elif row.identifier == "order111:18" and cls is WaterClass.SIX:
            options.update(qualified_cell=QualifiedCell.OTHER_CALCIUM, bare_operator=Comparison.LE)
        elif row.identifier == "order111:32" and cls is WaterClass.THREE:
            options.update(qualified_cell=QualifiedCell.OTHER_PHOSPHATE, bare_operator=Comparison.LE)
        elif row.identifier == "order111:12":
            if cls is not WaterClass.SIX:
                options["bare_operator"] = Comparison.LE
            sample = replace(sample, background=SourceValue(0, 0, row.unit, row.name))
        elif re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", raw):
            options["bare_operator"] = Comparison.LE
        elif "-" in raw and row.identifier != "order111:01":
            if row.identifier == "order111:08" and cls is WaterClass.SIX:
                options["range_meaning"] = RangeMeaning.OUTSIDE
            elif row.identifier == "order111:70":
                options["range_meaning"] = RangeMeaning.CLOSED_SORTED
            elif not (raw.startswith(">") and "-<" in raw):
                options["range_meaning"] = RangeMeaning.CLOSED
        if row.identifier == "order111:64-ratio":
            sample = replace(sample, macro_benthos=MacroBenthos.PRESENT)
        if "unit_basis" in options:
            sample = replace(sample, value=SourceValue(1, 1, options["unit_basis"].value, row.name))
        selected = choice(row.identifier, int(cls), **options)
        result = assess_order111(profile(row.identifier, choices=(selected,)), (sample,))
        assert result.classes[cls - 1].summary.finding in (CheckFinding.PASS, CheckFinding.FAIL)


@pytest.mark.parametrize("value,expected", [(20, CheckFinding.FAIL), ("20.001", CheckFinding.PASS)])
def test_missing_background_plus_only_runs_under_explicit_additive_scenario(value, expected):
    from fishy.water_classification import BackgroundArithmetic

    row = source_row("order111:12")
    c = choice(row.identifier, 6, background_arithmetic=BackgroundArithmetic.ADDITIVE_INCREMENT)
    sample = observation(row.identifier, value, background=SourceValue(10, 10, row.unit, row.name))
    result = assess_order111(profile(row.identifier, choices=(c,)), (sample,))
    assert result.classes[5].summary.finding is expected
    assert result.classes[5].cells[0].raw_cell == ">Сфон. 10,0"
    assert assess_order111(profile(row.identifier), (sample,)).classes[5].summary.finding is CheckFinding.UNKNOWN
    with pytest.raises(ValueError, match="missing-plus"):
        choice(row.identifier, 5, background_arithmetic=BackgroundArithmetic.ADDITIVE_INCREMENT)


def test_additive_background_candidate_cannot_bypass_support():
    from fishy.water_classification import BackgroundArithmetic

    row = source_row("order111:12")
    c = choice(row.identifier, 6, background_arithmetic=BackgroundArithmetic.ADDITIVE_INCREMENT)
    p = profile(row.identifier, choices=(c,))
    missing = observation(row.identifier, 30)
    wrong_unit = observation(row.identifier, 30, background=SourceValue(10, 10, "kg/m3", row.name))
    valid = observation(row.identifier, 30, background=SourceValue(10, 10, row.unit, row.name))
    wrong_basis = replace(valid, basis="unsupported monthly average")
    wrong_location = replace(valid, location=replace(LOCATION, section=CalculationSection("other", "1")))
    wrong_period = replace(valid, interval=Interval(datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC)))
    warmup = replace(valid, provenance=replace(PROVENANCE, excluded_warmup=(PERIOD,)))
    for sample in (missing, wrong_unit, wrong_basis, wrong_location, wrong_period, warmup):
        assert assess_order111(p, (sample,)).classes[5].summary.finding is CheckFinding.UNKNOWN
