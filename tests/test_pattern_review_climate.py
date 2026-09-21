from dataclasses import replace
from fractions import Fraction

import pytest
from fishy.scientific_acceptance import UsePurpose
from test_daily_patterns import TARGET, magnitude, pool, profile, synthetic_acceptance, year

from fishy.annual_statistics import TrendTreatment
from fishy.daily_patterns import annual_magnitude_product, construct_pattern, pattern_product
from fishy.evidence import CheckFinding


@pytest.mark.parametrize(
    "trend, expected",
    [(TrendTreatment.UNTREATED, CheckFinding.FAIL), (TrendTreatment.UNASSESSED, CheckFinding.UNKNOWN)],
)
def test_actual_untreated_donor_climate_cannot_get_present_climate_permission(trend, expected):
    ref = pool((year(),), (Fraction(99, 100),))
    ref = replace(ref, reference=replace(ref.reference, trend=trend))
    settings = replace(profile((ref,)), acceptance_profile="synthetic-acceptance-v1")
    annual = magnitude()
    annual_assessment = synthetic_acceptance(
        annual_magnitude_product(annual, intended_use="screen", purpose=UsePurpose.SCREENING)
    )
    first = construct_pattern(
        annual,
        TARGET,
        (ref,),
        settings,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
    )
    assessment = synthetic_acceptance(pattern_product(first, intended_use="screen", purpose=UsePurpose.SCREENING))
    result = construct_pattern(
        annual,
        TARGET,
        (ref,),
        settings,
        shape_assessment=assessment,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
    )
    assert result.samples
    assert result.use_checks.finding is expected
    assert next(c for c in result.use_checks.checks if c.check_id == "source_climate_0").finding is expected
