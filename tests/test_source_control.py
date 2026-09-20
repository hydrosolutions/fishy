"""Fixed-discharge source control checks retain original chemical tests."""

from dataclasses import replace
from fractions import Fraction

import pytest
from test_mixing import LOCATION, PERIOD, PROVENANCE, SALT, SUPPORT, group, target

from fishy.mixing import CheckOutcome, Endpoint, LoadRate
from fishy.quality import Comparison, QualityValue
from fishy.quantities import Flow
from fishy.source_control import (
    ControlledLoad,
    DrainBoundary,
    recheck_drain_control,
    screen_single_load,
    solve_drain_control,
)


def drain(discharge=10, other=3, controlled=4):
    return DrainBoundary(
        LOCATION,
        PERIOD,
        Flow(discharge),
        (ControlledLoad(SALT, LoadRate(other), LoadRate(controlled)),),
        SUPPORT,
        PROVENANCE,
    )


def test_single_load_control_and_background_failure():
    result = screen_single_load(Flow(10), QualityValue(500, "mg/l"), LoadRate(3), LoadRate(4))
    assert result.allowance == LoadRate(2) and result.reduction == LoadRate(2)
    assert result.outcome is CheckOutcome.PASS
    failed = screen_single_load(Flow(10), QualityValue("0.5", "kg/m3"), LoadRate(6), LoadRate(4))
    assert failed.outcome is CheckOutcome.FAIL
    assert failed.allowance is None and failed.reduction is None
    dry = screen_single_load(Flow(0), QualityValue("0.5", "kg/m3"), LoadRate(0), LoadRate(0))
    assert dry.outcome is CheckOutcome.INDETERMINATE


def test_common_drain_factor_and_changed_background():
    base = drain()
    result = solve_drain_control(base, (target(),))
    assert (result.factor_interval.lower, result.factor_interval.upper) == (0, Fraction(1, 2))
    assert result.outcome is CheckOutcome.PASS
    assert recheck_drain_control(base, (target(),), Fraction(1, 2))[0].outcome is CheckOutcome.PASS
    assert recheck_drain_control(base, (target(),), Fraction(1))[0].outcome is CheckOutcome.FAIL
    changed = solve_drain_control(drain(other=4), (target(),))
    assert changed.factor_interval.upper == Fraction(1, 4)
    assert result.boundary.discharge == Flow(10)


def test_drain_group_lower_upper_and_strict_factor():
    selected = (group((SALT,), ("0.4",), Comparison.GE), target("0.5", Comparison.LT))
    result = solve_drain_control(drain(), selected)
    assert (result.factor_interval.lower, result.factor_interval.upper) == (Fraction(1, 4), Fraction(1, 2))
    assert result.factor_interval.upper_endpoint is Endpoint.OPEN
    checks = recheck_drain_control(drain(), selected, Fraction(1, 2))
    assert [c.outcome for c in checks] == [CheckOutcome.PASS, CheckOutcome.FAIL]
    checks = recheck_drain_control(drain(), selected, Fraction(1, 4))
    assert all(c.outcome is CheckOutcome.PASS for c in checks)


def test_drain_background_alone_failure_and_dry_unsupported():
    assert solve_drain_control(drain(other=6), (target(),)).outcome is CheckOutcome.FAIL
    assert solve_drain_control(drain(discharge=0), (target(),)).outcome is CheckOutcome.INDETERMINATE
    changed = replace(drain(), support=replace(SUPPORT, limitations=("drain water removed too; rebalance required",)))
    assert solve_drain_control(changed, (target(),)).outcome is CheckOutcome.INDETERMINATE


def test_zero_controlled_load_strict_equality_and_invalid_factor():
    result = solve_drain_control(drain(other=5, controlled=0), (target(operator=Comparison.LT),))
    assert result.factor_interval.empty and result.outcome is CheckOutcome.FAIL
    for value in (Fraction(-1), Fraction(2), 0.5):
        with pytest.raises(ValueError):
            recheck_drain_control(drain(), (target(),), value)  # ty: ignore[invalid-argument-type]


def test_common_factor_intersects_independent_group_and_range():
    from fishy.quality import ChemicalBehavior, ChemicalIdentity

    other = ChemicalIdentity("other", "other", "other mass", "dissolved", ChemicalBehavior.CONSERVATIVE)
    base = drain(other=1, controlled=8)
    selected = (target("0.3", Comparison.GE, identifier="lower"), target())
    raw = solve_drain_control(base, selected)
    assert (raw.factor_interval.lower, raw.factor_interval.upper) == (Fraction(1, 4), Fraction(1, 2))
    base = replace(base, loads=(*base.loads, ControlledLoad(other, LoadRate(1), LoadRate(8))))
    grouped = group((SALT, other), (1, 1))
    combined = solve_drain_control(base, (*selected, grouped))
    assert combined.factor_interval.upper == Fraction(1, 2)
    assert all(
        check.outcome is CheckOutcome.PASS
        for check in recheck_drain_control(base, (*selected, grouped), Fraction(1, 2))
    )
    stricter = group((SALT, other), ("0.8", "0.8"))
    combined = solve_drain_control(base, (*selected, stricter))
    assert (combined.factor_interval.lower, combined.factor_interval.upper) == (Fraction(1, 4), Fraction(3, 8))
    assert combined.factor_interval.upper_binding == ("group",)


def test_excluded_warmup_cannot_size_or_recheck_drain_control():
    blocked = replace(drain(), provenance=replace(PROVENANCE, excluded_warmup=(PERIOD,)))
    result = solve_drain_control(blocked, (target(),))
    assert result.outcome is CheckOutcome.INDETERMINATE
    assert "warm-up" in " ".join(result.unresolved)
    assert recheck_drain_control(blocked, (target(),), Fraction(0))[0].outcome is CheckOutcome.INDETERMINATE
