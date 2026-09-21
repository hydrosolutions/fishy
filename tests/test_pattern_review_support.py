from dataclasses import replace
from fractions import Fraction

import pytest
from fishy.scientific_acceptance import UsePurpose
from test_daily_patterns import TARGET, magnitude, pool, profile, synthetic_acceptance, year

from fishy.daily_patterns import annual_magnitude_product, construct_pattern, pattern_product
from fishy.evidence import CheckFinding


def test_duplicate_retained_sources_cannot_manufacture_support():
    ref = pool((year(),), (Fraction(99, 100),))
    settings = replace(profile((ref,), sources=2), acceptance_profile="synthetic-acceptance-v1")
    annual = magnitude()
    annual_assessment = synthetic_acceptance(
        annual_magnitude_product(annual, intended_use="screen", purpose=UsePurpose.SCREENING)
    )
    initial = construct_pattern(
        annual,
        TARGET,
        (ref,),
        settings,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
    )
    assessment = synthetic_acceptance(pattern_product(initial, intended_use="screen", purpose=UsePurpose.SCREENING))
    candidate = construct_pattern(
        annual,
        TARGET,
        (ref,),
        settings,
        shape_assessment=assessment,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
    )
    assert candidate.use_checks.finding is CheckFinding.FAIL
    with pytest.raises(ValueError):
        replace(candidate, retained=candidate.retained * 2)
