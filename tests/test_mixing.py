"""Exact fixed-boundary mathematical cases, independent of any simulator."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.mixing import (
    BoundarySupport,
    CheckOutcome,
    Endpoint,
    Feasibility,
    FixedBoundary,
    FlowConstraints,
    LinearConstraint,
    LoadRate,
    MixingConstituent,
    intersect_constraints,
    recheck_mixing,
    solve_mixing,
)
from fishy.quality import (
    ChemicalBehavior,
    ChemicalIdentity,
    Comparison,
    GroupMember,
    GroupTarget,
    QualityTarget,
    QualityValue,
    RelativeTarget,
    UnresolvedTarget,
    quality_range,
)
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

LOCATION = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
PERIOD = Interval(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))
SUPPORT = BoundarySupport(
    "Synthetic conservative point case; fixed loads/composition, every carrier once, arrival excluded from background; completely mixed section"
)
PROVENANCE = Provenance(
    "synthetic fixed-boundary evidence",
    "example",
    "member",
    "1",
    "1",
    "1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
)
SALT = ChemicalIdentity("salt", "salt", "salt mass", "dissolved", ChemicalBehavior.CONSERVATIVE)


def boundary(background=10, load=8, source="0.1", chemical=SALT):
    return FixedBoundary(
        LOCATION,
        PERIOD,
        Flow(background),
        (MixingConstituent(chemical, LoadRate(load), QualityValue(source, "kg/m3")),),
        SUPPORT,
        PROVENANCE,
    )


def target(limit="0.5", operator=Comparison.LE, chemical=SALT, identifier="salt-limit"):
    return QualityTarget(
        identifier, chemical, operator, QualityValue(limit, "kg/m3"), "interval mean", "synthetic scenario"
    )


def group(chemicals, limits, operator=Comparison.LE, identifier="group"):
    return GroupTarget(
        identifier,
        tuple(GroupMember(c, QualityValue(t, "kg/m3")) for c, t in zip(chemicals, limits, strict=True)),
        operator,
        "interval mean",
        "synthetic",
        "explicit hypothetical grouping",
    )


@pytest.mark.parametrize(
    ("load", "source", "minimum", "total", "concentration"),
    [
        (8, "0.1", Fraction(15, 2), Fraction(35, 2), Fraction(1, 2)),
        (4, "0.1", Fraction(0), Fraction(10), Fraction(2, 5)),
    ],
    ids=["ordinary_dilution", "already_compliant"],
)
def test_dilution(load, source, minimum, total, concentration):
    result = solve_mixing(boundary(load=load, source=source), (target(),))
    assert result.status is Feasibility.FEASIBLE
    assert result.quality_interval.minimum == minimum
    assert result.quality_total == Flow(total)
    assert result.candidate is not None
    assert result.candidate.total == Flow(total)
    assert result.candidate.predictions[0][1].value == concentration
    assert result.candidate.outcome is CheckOutcome.PASS
    assert "salt-limit" in result.quality_interval.lower_binding if minimum else True


@pytest.mark.parametrize(("ecological", "arrival", "total"), [(20, 10, 20), (5, 0, 10)])
def test_ecological_total_no_double_count(ecological, arrival, total):
    base = boundary(load=8 if ecological == 20 else 4)
    result = solve_mixing(base, (target(),), FlowConstraints(LOCATION, PERIOD, ecological_total=Flow(ecological)))
    assert result.candidate is not None
    assert result.candidate.arrival == Flow(arrival)
    assert result.candidate.total == Flow(total)
    assert result.candidate.outcome is CheckOutcome.PASS


@pytest.mark.parametrize(
    ("load", "operator"),
    [(8, Comparison.LE), (5, Comparison.LT)],
    ids=["source_equals_limit", "strict_equality_zero_coefficient"],
)
def test_source_impossibility(load, operator):
    result = solve_mixing(boundary(load=load, source="0.5"), (target(operator=operator),))
    assert result.quality_interval.empty
    assert result.status is Feasibility.SOURCE_WATER_INFEASIBLE
    assert result.quality_interval.contradictions == ("salt-limit",)


def test_capacity_limited():
    result = solve_mixing(boundary(), (target(),), FlowConstraints(LOCATION, PERIOD, capacity=Flow(5)))
    assert result.status is Feasibility.CAPACITY_LIMITED
    assert result.quality_interval.minimum == Fraction(15, 2)
    assert result.candidate is None
    assert result.capacity_check is not None
    assert result.capacity_check.predictions[0][1].value == Fraction(17, 30)
    assert result.capacity_check.outcome is CheckOutcome.FAIL


def test_dirty_source_upper_bound_and_original_uplift_recheck():
    base = boundary(load=1, source=1)
    raw = solve_mixing(base, (target(),))
    assert (raw.quality_interval.lower, raw.quality_interval.upper) == (0, 8)
    assert raw.quality_interval.upper_binding == ("salt-limit",)
    result = solve_mixing(base, (target(),), FlowConstraints(LOCATION, PERIOD, ecological_total=Flow(20)))
    assert result.status is Feasibility.INDETERMINATE
    assert result.combined_interval.empty
    assert not result.unresolved
    assert "known conflicting" in result.reasons[0]
    assert recheck_mixing(base, (target(),), Flow(10)).outcome is CheckOutcome.FAIL


def test_dry_channel_open_interval_and_positive_base():
    base = boundary(0, 0)
    result = solve_mixing(base, (target(),))
    assert result.status is Feasibility.FEASIBLE
    assert result.quality_interval.lower_endpoint is Endpoint.OPEN
    assert result.quality_interval.infimum == 0
    assert result.quality_interval.minimum is None
    assert result.quality_total is None and result.candidate is None
    assert recheck_mixing(base, (target(),), Flow(0)).outcome is CheckOutcome.INDETERMINATE
    combined = solve_mixing(base, (target(),), FlowConstraints(LOCATION, PERIOD, ecological_total=Flow(3)))
    assert combined.quality_total is None
    assert combined.candidate is not None
    assert combined.candidate.total == Flow(3)


def test_grouped_upper_and_tds_standalone():
    a = ChemicalIdentity("chloride", "Cl", "Cl mass", "dissolved", ChemicalBehavior.CONSERVATIVE)
    b = ChemicalIdentity("sulphate", "SO4", "SO4 mass", "dissolved", ChemicalBehavior.CONSERVATIVE)
    base = FixedBoundary(
        LOCATION,
        PERIOD,
        Flow(10),
        (
            MixingConstituent(a, LoadRate("0.8"), QualityValue(0, "kg/m3")),
            MixingConstituent(b, LoadRate("0.3"), QualityValue(0, "kg/m3")),
        ),
        SUPPORT,
        PROVENANCE,
    )
    selected = group((a, b), ("0.1", "0.05"))
    result = solve_mixing(base, (selected,))
    assert result.quality_interval.minimum == 4
    assert result.candidate is not None
    assert result.candidate.checks[0].value == 1
    tds = ChemicalIdentity(
        "tds", "dry residue", "mass", "dissolved", ChemicalBehavior.TOTAL_DISSOLVED_SOLIDS, ("chloride", "sulphate")
    )
    base = replace(
        base,
        constituents=(
            MixingConstituent(tds, LoadRate(8), QualityValue(0, "kg/m3")),
            MixingConstituent(a, LoadRate("3.5"), QualityValue(0, "kg/m3")),
            MixingConstituent(b, LoadRate(1), QualityValue(0, "kg/m3")),
        ),
    )
    result = solve_mixing(base, (target(1, chemical=tds), group((a, b), ("0.35", "0.5"))))
    assert result.quality_interval.minimum == 2
    with pytest.raises(ValueError, match="TDS"):
        group((tds, a), (1, "0.35"))


def test_lower_and_upper_range_and_group_lower():
    base = boundary(load=1, source=1)
    selected = quality_range(
        "range", SALT, QualityValue("0.3", "kg/m3"), QualityValue("0.5", "kg/m3"), "interval mean", "synthetic"
    )
    result = solve_mixing(base, selected)
    assert (result.quality_interval.lower, result.quality_interval.upper) == (Fraction(20, 7), Fraction(8))
    lower = group((SALT,), ("0.3",), Comparison.GT)
    result = solve_mixing(base, (lower, target()))
    assert result.quality_interval.lower == Fraction(20, 7)
    assert result.quality_interval.lower_endpoint is Endpoint.OPEN
    assert recheck_mixing(base, (lower,), Flow(Fraction(20, 7))).outcome is CheckOutcome.FAIL


def test_strict_upper_open_minimum():
    selected = (target(operator=Comparison.LT),)
    result = solve_mixing(boundary(), selected)
    assert result.quality_interval.infimum == Fraction(15, 2)
    assert result.quality_interval.minimum is None and result.candidate is None
    assert recheck_mixing(boundary(), selected, Flow("7.5")).outcome is CheckOutcome.FAIL
    candidate = recheck_mixing(boundary(), selected, Flow(8))
    assert candidate.outcome is CheckOutcome.PASS
    assert candidate.predictions[0][1].value == Fraction(22, 45)
    result = solve_mixing(boundary(), selected, FlowConstraints(LOCATION, PERIOD, capacity=Flow("7.5")))
    assert result.status is Feasibility.CAPACITY_LIMITED


@pytest.mark.parametrize("a", [-2, 0, 2])
@pytest.mark.parametrize("rhs", [-2, 0, 2])
@pytest.mark.parametrize("endpoint", list(Endpoint))
def test_all_coefficient_signs_and_strictness(a, rhs, endpoint):
    constraint = LinearConstraint("original", Fraction(a), Fraction(rhs), endpoint)
    feasible = intersect_constraints((constraint,))
    for candidate in (Fraction(0), Fraction(1, 2), Fraction(1), Fraction(2), Fraction(100)):
        assert feasible.contains(candidate) == constraint.accepts(candidate)


def test_missing_group_member_preserves_supported_failure():
    missing = ChemicalIdentity("absent", "absent", "mass", "dissolved", ChemicalBehavior.CONSERVATIVE)
    selected = (target(), group((SALT, missing), (1, 1)))
    result = solve_mixing(boundary(), selected)
    assert result.status is Feasibility.INDETERMINATE and result.unresolved
    check = recheck_mixing(boundary(), selected, Flow(0))
    assert [c.outcome for c in check.checks] == [CheckOutcome.FAIL, CheckOutcome.INDETERMINATE]
    assert check.outcome is CheckOutcome.FAIL
    assert result.quality_total is None


def test_known_conflict_not_missing_and_operational_open_endpoint():
    selected = (target("0.6", Comparison.GE, identifier="lower"), target())
    result = solve_mixing(boundary(), selected)
    assert result.status is Feasibility.INDETERMINATE
    assert result.quality_interval.empty and not result.unresolved
    result = solve_mixing(
        boundary(load=4),
        (target(),),
        FlowConstraints(LOCATION, PERIOD, minimum=Flow(2), maximum=Flow(2), lower_endpoint=Endpoint.OPEN),
    )
    assert result.combined_interval.empty


def test_changed_background_recalculation_and_conservation():
    base = boundary()
    result = solve_mixing(base, (target(),))
    assert result.candidate is not None
    q = result.candidate.arrival.value
    assert (
        (base.constituents[0].background_load.value + q * base.constituents[0].source_concentration.value)
        == result.candidate.total.value * result.candidate.predictions[0][1].value
        == Fraction(35, 4)
    )
    changed = solve_mixing(replace(base, background=Flow(5)), (target(),))
    assert changed.quality_interval.minimum == Fraction(55, 4)
    assert result.quality_interval.minimum == Fraction(15, 2)


def test_unresolved_identity_support_and_process_boundaries():
    base = boundary()
    mismatched = replace(SALT, reporting_basis="other basis")
    for selected in (
        (target(chemical=mismatched),),
        (target(operator=Comparison.UNRESOLVED_UPPER),),
        (UnresolvedTarget("range", "uninterpreted source range", "source"),),
        (
            RelativeTarget(
                "relative", SALT, Comparison.LE, QualityValue(1, "kg/m3"), "mean", "source", "reference", "mean", PERIOD
            ),
        ),
    ):
        result = solve_mixing(base, selected)
        assert result.status is Feasibility.INDETERMINATE and result.unresolved
    unsupported = replace(base, support=BoundarySupport("flow-dependent returns", ("inputs vary with flow",)))
    result = solve_mixing(unsupported, (target(),))
    assert result.status is Feasibility.INDETERMINATE and result.candidate is None
    for name in ("pH", "temperature", "oxygen", "O2"):
        chemical = ChemicalIdentity(name, name, "mass", "dissolved", ChemicalBehavior.PROCESS)
        result = solve_mixing(boundary(chemical=chemical), (target(chemical=chemical),))
        assert result.status is Feasibility.INDETERMINATE and result.candidate is None


def test_invalid_input_units_identity_and_boundary():
    for invalid in (-1, "NaN", "inf"):
        with pytest.raises(ValueError):
            LoadRate(invalid)
    with pytest.raises(ValueError):
        LoadRate(1, "mg/L")
    with pytest.raises(ValueError):
        solve_mixing(boundary(), ())
    with pytest.raises(ValueError):
        solve_mixing(boundary(), (target(), target()))
    with pytest.raises(ValueError, match="match boundary"):
        solve_mixing(
            boundary(), (target(),), FlowConstraints(LOCATION, Interval(PERIOD.start, PERIOD.end + timedelta(days=1)))
        )
    with pytest.raises(ValueError, match="duplicate"):
        replace(boundary(), constituents=boundary().constituents * 2)
    with pytest.raises(ValueError, match="positive concentration"):
        group((SALT,), (0,))


def test_unsupported_process_has_no_conservative_prediction():
    oxygen = ChemicalIdentity("oxygen", "O2", "oxygen mass", "dissolved", ChemicalBehavior.PROCESS)
    result = recheck_mixing(boundary(chemical=oxygen), (target(chemical=oxygen),), Flow(8))
    assert result.outcome is CheckOutcome.INDETERMINATE
    assert result.predictions == ()


def test_carrier_water_load_and_separate_load_counted_once():
    # Two background carriers plus one separate load; additional arrival excluded.
    background_water = Flow(10).value + Flow(5).value
    background_load = (
        Flow(10).value * QualityValue("0.8", "kg/m3").value
        + Flow(5).value * QualityValue("0.2", "kg/m3").value
        + LoadRate(1).value
    )
    base = boundary(background_water, background_load, "0.1")
    result = solve_mixing(base, (target(),))
    assert result.candidate is not None
    assert result.candidate.arrival == Flow(Fraction(25, 4))
    assert result.candidate.total == Flow(Fraction(85, 4))
    assert result.candidate.predictions[0][1] == QualityValue("0.5", "kg/m3")
    assert result.boundary.provenance == PROVENANCE


def test_inclusive_singleton_and_strict_upper_at_same_bounds():
    base = boundary(load=1, source=1)
    lower = target("0.5", Comparison.GE, identifier="lower")
    result = solve_mixing(base, (lower, target()))
    assert result.quality_interval.minimum == result.quality_interval.upper == 8
    assert result.candidate is not None
    assert result.candidate.outcome is CheckOutcome.PASS
    result = solve_mixing(base, (lower, target(operator=Comparison.LT)))
    assert result.quality_interval.empty
    assert result.status is Feasibility.INDETERMINATE
    assert not result.unresolved
