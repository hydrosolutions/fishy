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
