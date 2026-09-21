from dataclasses import replace
from fractions import Fraction
import pytest
from test_daily_patterns import pool,year,profile,magnitude,TARGET,synthetic_acceptance
from fishy.daily_patterns import construct_pattern,pattern_product,annual_magnitude_product
from fishy.scientific_acceptance import UsePurpose
from fishy.evidence import CheckFinding

def test_duplicate_retained_sources_cannot_manufacture_support():
    ref=pool((year(),),(Fraction(99,100),))
    settings=replace(profile((ref,),sources=2),acceptance_profile="synthetic-acceptance-v1")
    annual=magnitude()
    annual_assessment=synthetic_acceptance(annual_magnitude_product(annual,intended_use="screen",purpose=UsePurpose.SCREENING))
    args=dict(intended_use="screen",purpose=UsePurpose.SCREENING,magnitude_assessment=annual_assessment)
    initial=construct_pattern(annual,TARGET,(ref,),settings,**args)
    assessment=synthetic_acceptance(pattern_product(initial,intended_use="screen",purpose=UsePurpose.SCREENING))
    candidate=construct_pattern(annual,TARGET,(ref,),settings,shape_assessment=assessment,**args)
    assert candidate.use_checks.finding is CheckFinding.FAIL
    with pytest.raises(ValueError):
        replace(candidate,retained=candidate.retained*2)

def test_duplicate_support_changes_overall_finding():
    ref=pool((year(),),(Fraction(99,100),))
    settings=replace(profile((ref,),sources=2),acceptance_profile="synthetic-acceptance-v1")
    annual=magnitude()
    annual_assessment=synthetic_acceptance(annual_magnitude_product(annual,intended_use="screen",purpose=UsePurpose.SCREENING))
    args=dict(intended_use="screen",purpose=UsePurpose.SCREENING,magnitude_assessment=annual_assessment)
    initial=construct_pattern(annual,TARGET,(ref,),settings,**args)
    assessment=synthetic_acceptance(pattern_product(initial,intended_use="screen",purpose=UsePurpose.SCREENING))
    candidate=construct_pattern(annual,TARGET,(ref,),settings,shape_assessment=assessment,**args)
    assert candidate.use_checks.finding is CheckFinding.FAIL
    changed=replace(candidate,retained=candidate.retained*2)
    assert changed.use_checks.finding is not CheckFinding.PASS
