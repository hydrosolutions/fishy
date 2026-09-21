from dataclasses import replace
from fractions import Fraction
from test_daily_patterns import pool,year,profile,magnitude,TARGET,synthetic_acceptance
from fishy.daily_patterns import construct_pattern,pattern_product,annual_magnitude_product
from fishy.annual_statistics import TrendTreatment
from fishy.scientific_acceptance import UsePurpose
from fishy.evidence import CheckFinding

def test_actual_untreated_donor_climate_cannot_get_present_climate_permission():
    ref=pool((year(),),(Fraction(99,100),))
    ref=replace(ref,reference=replace(ref.reference,trend=TrendTreatment.UNTREATED))
    settings=replace(profile((ref,)),acceptance_profile="synthetic-acceptance-v1")
    annual=magnitude()
    annual_assessment=synthetic_acceptance(annual_magnitude_product(annual,intended_use="screen",purpose=UsePurpose.SCREENING))
    args=dict(intended_use="screen",purpose=UsePurpose.SCREENING,magnitude_assessment=annual_assessment)
    first=construct_pattern(annual,TARGET,(ref,),settings,**args)
    assessment=synthetic_acceptance(pattern_product(first,intended_use="screen",purpose=UsePurpose.SCREENING))
    result=construct_pattern(annual,TARGET,(ref,),settings,shape_assessment=assessment,**args)
    assert result.samples
    assert result.use_checks.finding is not CheckFinding.PASS
