"""Explicit source use prohibitions remain controlling after numerical construction."""

from dataclasses import replace
from fractions import Fraction

import pytest
from test_daily_patterns import TARGET, magnitude, pool, profile, synthetic_acceptance, year

from fishy.daily_patterns import annual_magnitude_product, construct_pattern, pattern_product
from fishy.evidence import CheckFinding, UseRestriction
from fishy.scientific_acceptance import UsePurpose


@pytest.mark.parametrize(
    "purpose, expected", [(UsePurpose.SCREENING, CheckFinding.PASS), (UsePurpose.SIZING, CheckFinding.FAIL)]
)
def test_inherited_donor_rating_prohibition_is_scoped(purpose, expected):
    reference = replace(
        pool((year(),), (Fraction(99, 100),)),
        restrictions=(UseRestriction("donor rating-range sizing prohibition", (UsePurpose.SIZING.value,)),),
    )
    settings = replace(profile((reference,)), acceptance_profile="synthetic-acceptance-v1")
    annual = magnitude()
    annual_assessment = synthetic_acceptance(
        annual_magnitude_product(annual, intended_use="pattern study", purpose=purpose)
    )
    exploratory = construct_pattern(
        annual,
        TARGET,
        (reference,),
        settings,
        intended_use="pattern study",
        purpose=purpose,
        magnitude_assessment=annual_assessment,
    )
    assessment = synthetic_acceptance(pattern_product(exploratory, intended_use="pattern study", purpose=purpose))
    result = construct_pattern(
        annual,
        TARGET,
        (reference,),
        settings,
        intended_use="pattern study",
        purpose=purpose,
        magnitude_assessment=annual_assessment,
        shape_assessment=assessment,
    )
    assert result.samples == exploratory.samples
    assert result.use_checks.finding is expected
    assert next(c for c in result.use_checks.checks if c.check_id == "source_restrictions").finding is expected
    assert annual_assessment.acceptance_for(annual_assessment.record.product).finding is CheckFinding.PASS
