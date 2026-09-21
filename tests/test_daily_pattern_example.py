"""Check the reader example's complete-year candidate and import path."""

from dataclasses import replace
from fractions import Fraction

import pytest

from examples.daily_patterns import _reference, build_example, main
from fishy.daily_patterns import AnalogueReference, PatternMethod, construct_pattern
from fishy.evidence import CheckFinding
from fishy.quantities import Flow, Volume
from fishy.scientific_acceptance import UsePurpose


def test_daily_example_preserves_scale_support_and_import() -> None:
    candidate, unsupported, imported = build_example()
    assert candidate.method is PatternMethod.CALENDAR
    assert candidate.magnitude.value == Flow(8)
    assert candidate.volume == unsupported.volume == imported.volume == Volume(252288000)
    assert candidate.shape is not None
    assert tuple(x / 365 for x in candidate.shape[:4]) == (
        Fraction(3, 8),
        Fraction(3, 8),
        Fraction(1, 4),
        Fraction(),
    )
    assert len(candidate.samples) == 365
    assert sum(candidate.shape, Fraction()) == 365
    assert candidate.membership.source_count == 2
    assert candidate.membership.climate_cluster_count == 1
    assert tuple(c.probability.value for c in candidate.selected) == (Fraction(2, 3), Fraction(2, 3))
    assert candidate.support.finding is CheckFinding.PASS
    assert candidate.use_checks.finding is CheckFinding.UNKNOWN
    assert candidate.shape_evidence is None
    assert unsupported.support.finding is CheckFinding.FAIL
    assert unsupported.use_checks.finding is CheckFinding.FAIL
    assert unsupported.samples == candidate.samples
    assert unsupported.profile is not None and unsupported.profile.band == 0
    assert imported.method is PatternMethod.IMPORTED
    assert imported.samples == candidate.samples
    assert imported.shape == candidate.shape
    assert imported.use_checks.finding is CheckFinding.UNKNOWN
    assert any("import equation:" in reason for reason in imported.reasons)
    assert any("import reproduction:" in reason for reason in imported.reasons)


def test_daily_example_output(capsys) -> None:
    main()
    assert capsys.readouterr().out == (
        "Selected years / climate clusters: 2 / 1\n"
        "Selected full-reference probabilities: 2/3, 2/3\n"
        "Receiving annual mean: 8 m3/s\n"
        "Design-year volume: 252288000 m3\n"
        "Numerical support: pass\n"
        "Scientific-use checks: unknown\n"
        "Two-cluster requirement: fail; numerical candidate retained\n"
        "Imported schedule unchanged: True\n"
    )


def test_example_refuses_source_outside_frozen_profile_period() -> None:
    candidate, _, _ = build_example()
    assert candidate.profile is not None
    source = candidate.selected[0].source
    pool = AnalogueReference(_reference((source,)), (source,))
    settings = replace(candidate.profile, reference_period=candidate.calendar.interval)
    with pytest.raises(ValueError, match="outside frozen profile reference period"):
        construct_pattern(
            candidate.magnitude,
            candidate.calendar,
            (pool,),
            settings,
            intended_use="exploratory",
            purpose=UsePurpose.SCREENING,
        )
