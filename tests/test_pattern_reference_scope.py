from dataclasses import replace
from fractions import Fraction

from test_daily_patterns import TARGET, magnitude, pool, profile, synthetic_acceptance, year

from fishy.daily_patterns import annual_magnitude_product, construct_pattern, pattern_product
from fishy.evidence import CheckFinding, UseRestriction
from fishy.scientific_acceptance import UsePurpose


def test_unused_reference_at_same_location_does_not_supply_restriction():
    used = pool((year(2019),), (Fraction(99, 100),))
    unused = replace(
        pool((year(2018),), (Fraction(1, 10),)), restrictions=(UseRestriction("unrelated 2018 scope", ("screen",)),)
    )
    refs = (used, unused)
    settings = replace(profile(refs, band=Fraction(0)), acceptance_profile="synthetic-acceptance-v1")
    annual = magnitude()
    annual_assessment = synthetic_acceptance(
        annual_magnitude_product(annual, intended_use="screen", purpose=UsePurpose.SCREENING)
    )
    initial = construct_pattern(
        annual,
        TARGET,
        refs,
        settings,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
    )
    assessment = synthetic_acceptance(pattern_product(initial, intended_use="screen", purpose=UsePurpose.SCREENING))
    result = construct_pattern(
        annual,
        TARGET,
        refs,
        settings,
        shape_assessment=assessment,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
    )
    assert len(result.retained) == 1
    assert result.retained[0].source.calendar.year == 2019
    assert next(c for c in result.use_checks.checks if c.check_id == "source_restrictions").finding is CheckFinding.PASS
