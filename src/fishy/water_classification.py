"""assess_order111 : Order111Profile × ClassificationObservations → ClassMatches (pure).

Selected source-cell tests are not a unique national class or an authorisation.
The held 2025 source is an unauthenticated CAWater replica, not a legal consolidation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import IntEnum, StrEnum
from fractions import Fraction

from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    CorrectionState,
    Provenance,
    _text,
    _texts,
    aggregate_checks,
    warmup_restrictions,
)
from fishy.flows import Presence
from fishy.quality import Comparison, compare_bounds
from fishy.quantities import Number, finite_number
from fishy.spatial import Location
from fishy.time import Interval
from fishy.water_classification_catalogue import SOURCE_ROWS, SourceRow

SOURCE_VERSION = "Order 111-НҚ, 2025-06-04; CAWater replica retrieved 2026-09-17"
SOURCE_SHA256 = "c8e0aa22c3c2eb35269e858120ffda7d61de409b3c7e702cb2cb9b9f2c126d38"
COMMENCEMENT = date(2025, 6, 10)
SOURCE_LIMITATIONS = (
    "Publisher-direct authentication and current legal currency unresolved; held CAWater replica only",
    "Selected-profile numerical matches do not establish a unique overall class or national compliance",
    "Scientific adequacy and official admissibility require separately scoped evidence findings",
    "No treatment adequacy, sanitary compliance, or oxygen/thermal physics inferred",
    "Scenario interpretations do not resolve missing operators, units, typography or source-table conflicts",
)


class WaterClass(IntEnum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6


class WaterScope(StrEnum):
    RIVER = "river"
    CANAL = "canal"
    IN_CHANNEL_RESERVOIR = "in_channel_reservoir"
    LAKE = "lake"
    SEA = "sea"
    CASPIAN_SEA = "Caspian Sea"
    ARAL_SEA = "Aral Sea"
    BALKHASH_LAKE = "Lake Balkhash"
    OTHER = "other_or_unknown"


class RangeMeaning(StrEnum):
    CLOSED = "closed_endpoints"
    OPEN = "open_endpoints"
    CLOSED_SORTED = "closed_endpoints_sorted_reversed_source"
    OUTSIDE = "outside_two_printed_pH_bounds"


class QualifiedCell(StrEnum):
    INDUSTRIAL_CALCIUM = "industrial_calcium_150"
    OTHER_CALCIUM = "other_calcium_180"
    ASTANA_PHOSPHATE = "Astana_phosphate_3.5"
    OTHER_PHOSPHATE = "outside_Astana_phosphate_0.7"


class RatioTypography(StrEnum):
    LITERAL_DIGITS = "literal_baseline_103_102"
    POWERS_OF_TEN = "scenario_powers_10_cubed_10_squared"


class BackgroundArithmetic(StrEnum):
    ADDITIVE_INCREMENT = "scenario_background_plus_10_despite_missing_source_plus"


class UnitBasis(StrEnum):
    TEMPERATURE_CELSIUS = "degC"
    TOTAL_BACTERIA_MILLIONS_PER_ML = "10^6 cells/ml"
    SAPROPHYTES_THOUSANDS_PER_ML = "10^3 cells/ml"
    DISSOLVED_ARSENIC_MG_PER_L = "mg/l"


class TemperatureSeason(StrEnum):
    SUMMER = "summer_20_to_28"
    WINTER = "winter_5_to_8"


class QualitativeMeaning(StrEnum):
    EXACT_STATE = "match_printed_absence_or_traces_state"


class QualitativeState(StrEnum):
    ABSENT = "absent"
    TRACES = "traces"
    OTHER_PRESENT = "present_other_than_traces"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CellInterpretation:
    row_id: str
    water_class: WaterClass
    evidence: str
    bare_operator: Comparison | None = None
    range_meaning: RangeMeaning | None = None
    qualified_cell: QualifiedCell | None = None
    ratio_typography: RatioTypography | None = None
    unit_basis: UnitBasis | None = None
    temperature_season: TemperatureSeason | None = None
    qualitative_meaning: QualitativeMeaning | None = None
    background_arithmetic: BackgroundArithmetic | None = None

    def __post_init__(self) -> None:
        _text(self.row_id, "row_id")
        _text(self.evidence, "interpretation evidence")
        _enum(self.water_class, WaterClass)
        for value, kind in (
            (self.bare_operator, Comparison),
            (self.range_meaning, RangeMeaning),
            (self.qualified_cell, QualifiedCell),
            (self.ratio_typography, RatioTypography),
            (self.unit_basis, UnitBasis),
            (self.temperature_season, TemperatureSeason),
            (self.qualitative_meaning, QualitativeMeaning),
            (self.background_arithmetic, BackgroundArithmetic),
        ):
            if value is not None:
                _enum(value, kind)
        if self.bare_operator is Comparison.UNRESOLVED_UPPER:
            raise ValueError("choose a supported bare-number operator or leave it unresolved")
        row = source_row(self.row_id)
        raw = row.cells[self.water_class - 1]
        if self.background_arithmetic is not None and (self.row_id, self.water_class) != (
            "order111:12",
            WaterClass.SIX,
        ):
            raise ValueError("missing-plus interpretation belongs only to suspended-matter class6")
        if self.unit_basis is not None:
            units = {
                "order111:01": UnitBasis.TEMPERATURE_CELSIUS,
                "order111:58-dissolved": UnitBasis.DISSOLVED_ARSENIC_MG_PER_L,
                "order111:68": UnitBasis.TOTAL_BACTERIA_MILLIONS_PER_ML,
                "order111:69": UnitBasis.SAPROPHYTES_THOUSANDS_PER_ML,
            }
            if self.row_id not in units or self.unit_basis is not units[self.row_id]:
                raise ValueError("unit interpretation does not apply to this source row")
        if self.temperature_season is not None:
            if self.row_id != "order111:01":
                raise ValueError("seasonal interpretation belongs only to merged temperature row1")
            raw = "20-28" if self.temperature_season is TemperatureSeason.SUMMER else "5-8"
        if self.qualitative_meaning is not None and raw not in ("отс.", "следы"):
            raise ValueError("qualitative interpretation requires a printed absence/traces cell")
        if self.row_id == "order111:64-ratio" and self.water_class is WaterClass.SIX:
            raw = raw.split(" или ")[0]
        qualified = (row.printed_row, self.water_class)
        if self.qualified_cell is not None:
            allowed = {
                ("18", WaterClass.SIX): (QualifiedCell.INDUSTRIAL_CALCIUM, QualifiedCell.OTHER_CALCIUM),
                ("32", WaterClass.THREE): (QualifiedCell.ASTANA_PHOSPHATE, QualifiedCell.OTHER_PHOSPHATE),
            }
            if qualified not in allowed or self.qualified_cell not in allowed[qualified]:
                raise ValueError("qualified interpretation does not apply to this source cell")
        if self.ratio_typography is not None and row.printed_row != "70":
            raise ValueError("ratio typography interpretation belongs only to row70")
        if self.bare_operator is not None:
            bare = re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", raw.strip())
            relative = row.printed_row == "12" and self.water_class is not WaterClass.SIX
            if not (bare or relative or qualified in (("18", WaterClass.SIX), ("32", WaterClass.THREE))):
                raise ValueError("bare-number interpretation cannot replace an explicit or unsupported source cell")
        if self.range_meaning is not None:
            if re.fullmatch(r">=?[0-9]+(?:[.,][0-9]+)?-<[0-9]+(?:[.,][0-9]+)?", raw.replace(" ", "")):
                raise ValueError("endpoint interpretation is unused: both source inequalities are printed")
            if qualified == ("8", WaterClass.SIX) and self.range_meaning is not RangeMeaning.OUTSIDE:
                raise ValueError("pH class6 requires the outside-disjunction interpretation, not an ordered range")
            if not re.fullmatch(r"[<>≤≥]?[0-9]+(?:[.,][0-9]+)?-[<>≤≥]?[0-9]+(?:[.,][0-9]+)?", raw.replace(" ", "")):
                raise ValueError("range interpretation requires a numerical source range")
            if self.range_meaning is RangeMeaning.OUTSIDE and qualified != ("8", WaterClass.SIX):
                raise ValueError("outside-range interpretation belongs only to source pH class6")
            if self.range_meaning is RangeMeaning.CLOSED_SORTED and qualified != ("70", WaterClass.THREE):
                raise ValueError("sorted-range interpretation belongs only to reversed row70 class3")


def _enum(value: object, kind: type) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"explicit {kind.__name__} required")


def source_row(identifier: str) -> SourceRow:
    """Look up a physical row, never a potentially duplicated printed row number."""
    for row in SOURCE_ROWS:
        if row.identifier == identifier:
            return row
    raise ValueError(f"unknown source row {identifier!r}")


@dataclass(frozen=True, init=False)
class SourceValue:
    """A value in the printed or explicitly interpreted unit and exact determinand.

    A CellInterpretation must name any supported missing/ambiguous-unit reading.
    No implicit ion/element, total/dissolved, concentration or bacterial-unit conversion.
    Negative values remain possible for signed potential and temperature only.
    """

    lower: Fraction
    upper: Fraction
    unit: str
    determinand: str

    def __init__(self, lower: Number, upper: Number, unit: str, determinand: str) -> None:
        lo, hi = finite_number(lower), finite_number(upper)
        if lo > hi:
            raise ValueError("unordered observation bounds")
        if not isinstance(unit, str):
            raise TypeError("source unit must preserve printed text, including an empty field")
        _text(determinand, "source determinand")
        object.__setattr__(self, "lower", lo)
        object.__setattr__(self, "upper", hi)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "determinand", determinand)


class MacroBenthos(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassificationObservation:
    row_id: str
    value: SourceValue | None
    location: Location
    interval: Interval
    basis: str
    presence: Presence
    provenance: Provenance
    reasons: tuple[str, ...] = ()
    background: SourceValue | None = None
    macro_benthos: MacroBenthos = MacroBenthos.UNKNOWN
    qualitative: QualitativeState = QualitativeState.UNKNOWN

    def __post_init__(self) -> None:
        row = source_row(self.row_id)
        for value, kind in (
            (self.location, Location),
            (self.interval, Interval),
            (self.presence, Presence),
            (self.provenance, Provenance),
        ):
            _enum(value, kind)
        _text(self.basis, "sampling basis")
        _texts(self.reasons, "reasons")
        for value in (self.value, self.background):
            if value is not None:
                _enum(value, SourceValue)
                if value.lower < 0 and str(row.printed_row) not in ("1", "15"):
                    raise ValueError("negative value outside signed temperature/potential domain")
        _enum(self.macro_benthos, MacroBenthos)
        _enum(self.qualitative, QualitativeState)
        if self.qualitative is not QualitativeState.UNKNOWN:
            if self.row_id not in ("order111:66", "order111:67"):
                raise ValueError("absence/traces observation belongs only to rows66/67")
            if self.value is not None:
                raise ValueError("qualitative absence/traces is not a numerical value")
        if self.provenance.correction_state is CorrectionState.MISSING and (
            self.value is not None
            or self.macro_benthos is not MacroBenthos.UNKNOWN
            or self.qualitative is not QualitativeState.UNKNOWN
        ):
            raise ValueError("missing observation status cannot carry numerical or qualitative evidence")
        if self.row_id == "order111:64-ratio" and self.value is not None and self.value.upper > 100:
            raise ValueError("subset-to-total macro-benthos percentage cannot exceed 100")
        if self.macro_benthos is not MacroBenthos.UNKNOWN and self.row_id != "order111:64-ratio":
            raise ValueError("macro-benthos evidence belongs only to the ratio row64")
        if self.macro_benthos is MacroBenthos.ABSENT and self.value is not None:
            raise ValueError("absent macro-benthos cannot supply a defined abundance ratio")
        if (
            self.presence is Presence.PRESENT
            and self.value is None
            and self.macro_benthos is MacroBenthos.UNKNOWN
            and self.qualitative is QualitativeState.UNKNOWN
        ):
            raise ValueError("present observation requires a value or explicit macro-benthos evidence")
        if self.presence is not Presence.PRESENT and not self.reasons:
            raise ValueError("unavailable observation requires reasons")
        if self.background is not None and str(row.printed_row) != "12":
            raise ValueError("background belongs only to source suspended-matter row")


@dataclass(frozen=True)
class Order111Profile:
    identifier: str
    version: str
    scenario: str
    location: Location
    interval: Interval
    scope: WaterScope
    calculation_date: date
    required_rows: tuple[str, ...]
    basis: str
    interpretations: tuple[CellInterpretation, ...] = ()

    def __post_init__(self) -> None:
        for name in ("identifier", "version", "scenario", "basis"):
            _text(getattr(self, name), name)
        for value, kind in (
            (self.location, Location),
            (self.interval, Interval),
            (self.scope, WaterScope),
            (self.calculation_date, date),
        ):
            _enum(value, kind)
        _texts(self.required_rows, "required rows")
        if not self.required_rows or len(set(self.required_rows)) != len(self.required_rows):
            raise ValueError("nonempty unique required physical rows required")
        for row_id in self.required_rows:
            source_row(row_id)
        if not isinstance(self.interpretations, tuple):
            raise TypeError("immutable interpretations required")
        keys = []
        for choice in self.interpretations:
            _enum(choice, CellInterpretation)
            if choice.row_id not in self.required_rows:
                raise ValueError("interpretation outside selected source profile")
            keys.append((choice.row_id, choice.water_class))
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate cell interpretations")


@dataclass(frozen=True)
class CellResult:
    row: SourceRow
    water_class: WaterClass
    raw_cell: str
    interpretation: CellInterpretation | None
    observation: ClassificationObservation | None
    check: Check


@dataclass(frozen=True)
class ClassAssessment:
    water_class: WaterClass
    cells: tuple[CellResult, ...]
    summary: CheckSummary


@dataclass(frozen=True)
class ClassMatches:
    profile: Order111Profile
    classes: tuple[ClassAssessment, ...]
    supported_matches: tuple[WaterClass, ...]
    unknown_classes: tuple[WaterClass, ...]
    limitations: tuple[str, ...]
    source_version: str = SOURCE_VERSION
    source_sha256: str = SOURCE_SHA256


def _scope_reasons(profile: Order111Profile) -> tuple[str, ...]:
    reasons = ()
    if profile.scope not in (WaterScope.RIVER, WaterScope.CANAL, WaterScope.IN_CHANNEL_RESERVOIR):
        reasons += ("Order111 numerical scope excludes seas/lakes; other scope unsupported",)
    if profile.calculation_date < COMMENCEMENT or profile.interval.start.date() < COMMENCEMENT:
        reasons += ("requested date/observation interval precedes source commencement 2025-06-10",)
    return reasons


def _observation_reasons(
    profile: Order111Profile,
    row: SourceRow,
    sample: ClassificationObservation | None,
    choice: CellInterpretation | None,
) -> tuple[str, ...]:
    if sample is None:
        return ("required source-row observation missing",)
    reasons = warmup_restrictions(sample.provenance, sample.interval)
    if sample.location != profile.location or sample.interval != profile.interval:
        reasons += ("location or interval mismatch; no disaggregation inferred",)
    if sample.provenance.scenario != profile.scenario or sample.basis != profile.basis:
        reasons += ("scenario or sampling basis mismatch",)
    if sample.presence is not Presence.PRESENT:
        reasons += sample.reasons
    expected_unit = row.unit if choice is None or choice.unit_basis is None else choice.unit_basis.value
    if sample.value is not None and (sample.value.unit != expected_unit or sample.value.determinand != row.name):
        reasons += ("source unit or determinand/form/reporting basis mismatch; no implicit conversion",)
    if sample.background is not None and (
        sample.background.unit != row.unit or sample.background.determinand != row.name
    ):
        reasons += ("background unit or determinand mismatch",)
    return reasons


_OPERATORS = {"<": Comparison.LT, ">": Comparison.GT, "≤": Comparison.LE, "≥": Comparison.GE}
_NUMBER = r"[0-9]+(?:[.,][0-9]+)?"


def _cell_test(
    row: SourceRow, water_class: WaterClass, sample: ClassificationObservation, choice: CellInterpretation | None
) -> tuple[CheckFinding, tuple[str, ...]]:
    raw = row.cells[water_class - 1]
    if raw in ("отс.", "следы"):
        if choice is None or choice.qualitative_meaning is None or sample.qualitative is QualitativeState.UNKNOWN:
            return CheckFinding.UNKNOWN, (
                "printed qualitative state requires supplied absence/traces and explicit exact-state interpretation",
            )
        expected = QualitativeState.ABSENT if raw == "отс." else QualitativeState.TRACES
        return (CheckFinding.PASS if sample.qualitative is expected else CheckFinding.FAIL), ()
    alternative = row.identifier == "order111:64-ratio" and water_class is WaterClass.SIX
    if alternative and sample.macro_benthos is MacroBenthos.ABSENT:
        return CheckFinding.PASS, ("supplied macro-benthos absence satisfies the printed qualitative alternative",)
    if sample.value is None:
        return CheckFinding.UNKNOWN, ("required numerical ratio missing; absence is not a numeric zero",)
    finding, reasons = _numeric_cell_test(row, water_class, sample, choice)
    if alternative and finding is CheckFinding.FAIL and sample.macro_benthos is MacroBenthos.UNKNOWN:
        return CheckFinding.UNKNOWN, ("numeric alternative fails; macro-benthos absence alternative unassessed",)
    return finding, reasons


def _numeric_cell_test(
    row: SourceRow, water_class: WaterClass, sample: ClassificationObservation, choice: CellInterpretation | None
) -> tuple[CheckFinding, tuple[str, ...]]:
    assert sample.value is not None
    lo, hi = sample.value.lower, sample.value.upper
    raw = row.cells[water_class - 1]
    if row.identifier == "order111:64-ratio" and water_class is WaterClass.SIX:
        raw = raw.split(" или ")[0]
    text = re.sub(r"\s+", "", raw).replace("−", "-").replace("–", "-")
    number = str(row.printed_row)
    if number == "1":
        if choice is None or choice.temperature_season is None or choice.unit_basis is None:
            return CheckFinding.UNKNOWN, (
                "merged temperature cells require explicit shared-seasonal-condition and Celsius typography interpretation",
            )
        text = "20-28" if choice.temperature_season is TemperatureSeason.SUMMER else "5-8"
    if number == "58" and row.unit == "-" and (choice is None or choice.unit_basis is None):
        return CheckFinding.UNKNOWN, ("dissolved arsenic source unit missing; mg/l not inherited",)
    if number in ("68", "69") and (choice is None or choice.unit_basis is None):
        return CheckFinding.UNKNOWN, ("bacterial count unit/exponent and glossary transcription unresolved",)
    if number == "70":
        if choice is None or choice.ratio_typography is None:
            return CheckFinding.UNKNOWN, ("row70 baseline 103/102 typography unresolved; no exponent repair",)
        if choice.ratio_typography is RatioTypography.POWERS_OF_TEN:
            text = text.replace("103", "1000").replace("102", "100")
    if number == "18" and water_class is WaterClass.SIX:
        if choice is None or choice.qualified_cell not in (
            QualifiedCell.INDUSTRIAL_CALCIUM,
            QualifiedCell.OTHER_CALCIUM,
        ):
            return CheckFinding.UNKNOWN, ("calcium industrial-use qualification requires explicit selection",)
        text = "150" if choice.qualified_cell is QualifiedCell.INDUSTRIAL_CALCIUM else "180"
    if number == "32" and water_class is WaterClass.THREE:
        if choice is None or choice.qualified_cell not in (
            QualifiedCell.ASTANA_PHOSPHATE,
            QualifiedCell.OTHER_PHOSPHATE,
        ):
            return CheckFinding.UNKNOWN, ("phosphate Astana qualification requires explicit selection",)
        text = "3.5" if choice.qualified_cell is QualifiedCell.ASTANA_PHOSPHATE else "0.7"
    if number == "12":
        if water_class is WaterClass.SIX and (choice is None or choice.background_arithmetic is None):
            return CheckFinding.UNKNOWN, ("source >Сфон.10,0 omits arithmetic operator; no plus inferred",)
        if sample.background is None:
            return CheckFinding.UNKNOWN, ("suspended matter requires supported same-scope background",)
        lo -= sample.background.upper
        hi -= sample.background.lower
        text = ">10.0" if water_class is WaterClass.SIX else text.split("+")[-1]
    text = text.replace("%", "")
    comparison = re.fullmatch(rf"([<>≤≥])({_NUMBER})", text)
    if comparison:
        return compare_bounds(lo, hi, Fraction(comparison[2].replace(",", ".")), _OPERATORS[comparison[1]]), ()
    bare = re.fullmatch(_NUMBER, text)
    if bare:
        if choice is None or choice.bare_operator is None:
            return CheckFinding.UNKNOWN, (
                "bare source number has no printed operator; explicit interpretation required",
            )
        return compare_bounds(lo, hi, Fraction(text.replace(",", ".")), choice.bare_operator), ()
    bounds = re.fullmatch(rf"([<>≤≥]?)({_NUMBER})-([<>≤≥]?)({_NUMBER})", text)
    if bounds:
        first, second = Fraction(bounds[2].replace(",", ".")), Fraction(bounds[4].replace(",", "."))
        if bounds[1] == "<" and bounds[3] == ">":
            if choice is None or choice.range_meaning is not RangeMeaning.OUTSIDE:
                return CheckFinding.UNKNOWN, ("pH outside-range notation requires explicit disjunction interpretation",)
            a = compare_bounds(lo, hi, first, Comparison.LT)
            b = compare_bounds(lo, hi, second, Comparison.GT)
            return (
                CheckFinding.PASS
                if CheckFinding.PASS in (a, b)
                else CheckFinding.FAIL
                if a is b is CheckFinding.FAIL
                else CheckFinding.UNKNOWN
            ), ()
        if (not bounds[1] or not bounds[3]) and (
            choice is None
            or choice.range_meaning
            not in (
                RangeMeaning.CLOSED,
                RangeMeaning.OPEN,
                RangeMeaning.CLOSED_SORTED,
            )
        ):
            return CheckFinding.UNKNOWN, ("range endpoint inclusion unspecified; explicit interpretation required",)
        if first > second:
            if choice is None or choice.range_meaning is not RangeMeaning.CLOSED_SORTED:
                return CheckFinding.UNKNOWN, ("reversed printed range; no endpoint reordering inferred",)
            first, second = second, first
        lower = (
            _OPERATORS[bounds[1]]
            if bounds[1]
            else (Comparison.GT if choice and choice.range_meaning is RangeMeaning.OPEN else Comparison.GE)
        )
        upper = (
            _OPERATORS[bounds[3]]
            if bounds[3]
            else (Comparison.LT if choice and choice.range_meaning is RangeMeaning.OPEN else Comparison.LE)
        )
        if lower not in (Comparison.GE, Comparison.GT) or upper not in (Comparison.LE, Comparison.LT):
            return CheckFinding.UNKNOWN, ("unsupported printed range directions",)
        summary = aggregate_checks(
            ("lower", "upper"),
            (
                Check("lower", compare_bounds(lo, hi, first, lower)),
                Check("upper", compare_bounds(lo, hi, second, upper)),
            ),
        )
        return summary.finding, ()
    return CheckFinding.UNKNOWN, ("qualitative or unsupported source cell; no numeric replacement inferred",)


def assess_order111(profile: Order111Profile, observations: tuple[ClassificationObservation, ...]) -> ClassMatches:
    """Test all six selected source profiles. Retain overlap, gaps and unknowns.

    Matching multiple classes is intentional. No worst-row, best-match or nearest-class
    algorithm is introduced by this operation.
    """
    _enum(profile, Order111Profile)
    if not isinstance(observations, tuple) or any(not isinstance(x, ClassificationObservation) for x in observations):
        raise TypeError("immutable classification observations required")
    by_row = {sample.row_id: sample for sample in observations}
    if len(by_row) != len(observations):
        raise ValueError("duplicate physical-row observations")
    if set(by_row) - set(profile.required_rows):
        raise ValueError("observation outside selected required rows")
    choices = {(x.row_id, x.water_class): x for x in profile.interpretations}
    classes = []
    for water_class in WaterClass:
        cells = []
        for row_id in profile.required_rows:
            row, sample = source_row(row_id), by_row.get(row_id)
            choice = choices.get((row_id, water_class))
            reasons = _scope_reasons(profile) + _observation_reasons(profile, row, sample, choice)
            finding = CheckFinding.UNKNOWN
            if not reasons:
                assert sample is not None
                finding, reasons = _cell_test(row, water_class, sample, choice)
                if finding is CheckFinding.UNKNOWN and not reasons:
                    reasons = ("observation bounds overlap source threshold",)
            cells.append(
                CellResult(
                    row, water_class, row.cells[water_class - 1], choice, sample, Check(row_id, finding, reasons)
                )
            )
        summary = aggregate_checks(profile.required_rows, tuple(x.check for x in cells))
        classes.append(ClassAssessment(water_class, tuple(cells), summary))
    limitations = (
        SOURCE_LIMITATIONS
        + _scope_reasons(profile)
        + tuple(
            dict.fromkeys(
                reason for sample in observations for reason in sample.provenance.limitations + sample.reasons
            )
        )
    )
    return ClassMatches(
        profile,
        tuple(classes),
        tuple(x.water_class for x in classes if x.summary.finding is CheckFinding.PASS),
        tuple(x.water_class for x in classes if x.summary.finding is CheckFinding.UNKNOWN),
        limitations,
    )


class WaterUse(StrEnum):
    ECOSYSTEM = "aquatic_ecosystems"
    SALMONIDS = "salmonids"
    CYPRINIDS = "cyprinids"
    DRINKING_SIMPLE = "drinking_food_industry_simple_treatment"
    DRINKING_NORMAL = "drinking_food_industry_normal_treatment"
    DRINKING_INTENSIVE = "drinking_food_industry_intensive_treatment"
    RECREATION = "tourism_sport_rest_bathing"
    IRRIGATION_UNTREATED = "irrigation_without_preparation"
    IRRIGATION_SETTLING = "irrigation_settling_basins"
    INDUSTRY = "industrial_processes_cooling"
    HYDROPOWER = "hydropower"
    TRANSPORT = "water_transport"
    MINING = "mineral_extraction"


class UseFinding(StrEnum):
    PERMITTED = "permitted_by_mapping_only"
    CONDITIONAL = "conditional_on_stated_preparation"
    NOT_PERMITTED = "not_permitted_by_mapping"
    NOT_RECOMMENDED = "not_recommended_by_description"
    UNRESOLVED = "unresolved"


class UseMapping(StrEnum):
    DESCRIPTIVE = "descriptive_table"
    MATRIX = "matrix_table"


@dataclass(frozen=True)
class UseInterpretation:
    mapping: UseMapping
    evidence: str

    def __post_init__(self) -> None:
        _enum(self.mapping, UseMapping)
        _text(self.evidence, "use interpretation evidence")


@dataclass(frozen=True)
class AttributedUse:
    table: str
    finding: UseFinding
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class UseAssessment:
    water_class: WaterClass
    use: WaterUse
    descriptive: AttributedUse
    matrix: AttributedUse
    interpretation: UseInterpretation | None
    finding: UseFinding
    sanitary_cross_references: tuple[str, ...]
    limitations: tuple[str, ...] = SOURCE_LIMITATIONS
    source_version: str = SOURCE_VERSION


_MATRIX_LAST_CLASS = {
    WaterUse.ECOSYSTEM: 2,
    WaterUse.SALMONIDS: 2,
    WaterUse.CYPRINIDS: 3,
    WaterUse.DRINKING_SIMPLE: 2,
    WaterUse.DRINKING_NORMAL: 3,
    WaterUse.DRINKING_INTENSIVE: 3,
    WaterUse.RECREATION: 3,
    WaterUse.IRRIGATION_UNTREATED: 4,
    WaterUse.IRRIGATION_SETTLING: 5,
    WaterUse.INDUSTRY: 5,
    WaterUse.HYDROPOWER: 6,
    WaterUse.TRANSPORT: 6,
    WaterUse.MINING: 6,
}
_DRINKING = (WaterUse.DRINKING_SIMPLE, WaterUse.DRINKING_NORMAL, WaterUse.DRINKING_INTENSIVE)
_IRRIGATION = (WaterUse.IRRIGATION_UNTREATED, WaterUse.IRRIGATION_SETTLING)
_SPECIAL = (WaterUse.HYDROPOWER, WaterUse.TRANSPORT, WaterUse.MINING)


def _descriptive_use(water_class: WaterClass, use: WaterUse) -> AttributedUse:
    finding, conditions = UseFinding.PERMITTED, ()
    if use in _DRINKING and water_class in (WaterClass.TWO, WaterClass.THREE, WaterClass.FOUR):
        conditions = (
            {
                WaterClass.TWO: "simple water preparation",
                WaterClass.THREE: "more effective purification",
                WaterClass.FOUR: "intensive (deep) treatment at intakes",
            }[water_class],
        )
        finding = UseFinding.CONDITIONAL
    elif water_class is WaterClass.THREE and use is WaterUse.SALMONIDS:
        finding = UseFinding.NOT_RECOMMENDED
    elif water_class is WaterClass.THREE and use in (WaterUse.ECOSYSTEM, WaterUse.CYPRINIDS):
        finding, conditions = (
            UseFinding.UNRESOLVED,
            ("Table1 does not give an explicit class3 ecosystem/cyprinid permission",),
        )
    elif water_class is WaterClass.FOUR and use is WaterUse.RECREATION:
        finding = UseFinding.NOT_RECOMMENDED
    elif water_class is WaterClass.FOUR and use not in (*_IRRIGATION, WaterUse.INDUSTRY, *_SPECIAL):
        finding = UseFinding.NOT_PERMITTED
    elif water_class is WaterClass.FIVE:
        if use in _IRRIGATION:
            finding, conditions = UseFinding.CONDITIONAL, ("settling in settling basins",)
        elif use in (WaterUse.INDUSTRY, *_SPECIAL):
            finding, conditions = (
                UseFinding.UNRESOLVED,
                (
                    "Table1 class5 industrial/irrigation sentence has an unresolved settling-qualification scope",
                    "...промышленного водопользования и целей орошения при применении методов отстаивания в картах отстаивания.",
                ),
            )
        else:
            finding = UseFinding.NOT_PERMITTED
    elif water_class is WaterClass.SIX:
        if use in _SPECIAL:
            finding, conditions = UseFinding.CONDITIONAL, ("only processes not requiring water-quality standards",)
        else:
            finding = UseFinding.NOT_RECOMMENDED
    return AttributedUse(f"Table1 class {int(water_class)}, PDF pp8–10", finding, conditions)


def assess_order111_use(
    water_class: WaterClass, use: WaterUse, interpretation: UseInterpretation | None = None
) -> UseAssessment:
    """Map a supplied class, not infer treatment adequacy or numerically select a class.

    Both tables always survive selection. Without selection, conflicting findings remain
    unresolved. This operation maps the held source only, not a dated legal permission.
    """
    _enum(water_class, WaterClass)
    _enum(use, WaterUse)
    if interpretation is not None:
        _enum(interpretation, UseInterpretation)
    descriptive = _descriptive_use(water_class, use)
    matrix = AttributedUse(
        f"Table2 {use.value}, PDF pp11–12",
        UseFinding.PERMITTED if water_class <= _MATRIX_LAST_CLASS[use] else UseFinding.NOT_PERMITTED,
        ("plus/minus records category/type-of-treatment mapping, not achieved treatment",),
    )
    if interpretation is not None:
        finding = descriptive.finding if interpretation.mapping is UseMapping.DESCRIPTIVE else matrix.finding
    elif (
        descriptive.finding in (UseFinding.PERMITTED, UseFinding.CONDITIONAL) and matrix.finding is UseFinding.PERMITTED
    ) or descriptive.finding is matrix.finding:
        finding = descriptive.finding
    else:
        finding = UseFinding.UNRESOLVED
    sanitary = ()
    if use in _DRINKING and water_class in (WaterClass.ONE, WaterClass.TWO, WaterClass.THREE):
        sanitary = ("Table1 note: ҚР ДСМ-138 (2022-11-24), registration30713; drinking safety separately required",)
    if use in _IRRIGATION and water_class in (WaterClass.FOUR, WaterClass.FIVE):
        sanitary = (
            "Table1 note: treatment to ҚР ДСМ-138 and ҚР ДСМ-44 (2022-05-16), registration28086, for irrigation; not assessed",
        )
    return UseAssessment(water_class, use, descriptive, matrix, interpretation, finding, sanitary)
