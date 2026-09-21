from dataclasses import replace
from datetime import timedelta
from fractions import Fraction

import pytest
from fishy.scientific_acceptance import UsePurpose
from test_daily_patterns import TARGET, magnitude, pool, profile, synthetic_acceptance, year

from fishy.daily_patterns import annual_magnitude_product, construct_pattern, import_pattern, pattern_product
from fishy.evidence import CheckFinding
from fishy.pattern_calendar import AccountingYear
from fishy.quantities import Flow
from fishy.time import Interval


def accepted():
    ref = pool((year(),), (Fraction(99, 100),))
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
    daily_assessment = synthetic_acceptance(pattern_product(first, intended_use="screen", purpose=UsePurpose.SCREENING))
    result = construct_pattern(
        annual,
        TARGET,
        (ref,),
        settings,
        shape_assessment=daily_assessment,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
    )
    assert result.use_checks.finding is CheckFinding.PASS
    return result


def test_replacement_cannot_retain_acceptance_for_changed_hydrograph():
    original = accepted()
    changed = (
        replace(original.samples[0], value=Flow(9)),
        replace(original.samples[1], value=Flow(7)),
        *original.samples[2:],
    )
    with pytest.raises(ValueError):
        replace(original, samples=changed, shape=tuple(s.value.value / 8 for s in changed), retained=())


def test_import_cannot_change_receiving_accounting_month():
    original = accepted()
    calendar = AccountingYear(2022, 7, 0)
    samples = tuple(
        replace(
            s,
            interval=Interval(
                calendar.interval.start + timedelta(days=i), calendar.interval.start + timedelta(days=i + 1)
            ),
        )
        for i, s in enumerate(original.samples)
    )
    with pytest.raises(ValueError):
        import_pattern(
            original.magnitude,
            calendar,
            samples,
            original.magnitude.derivation,
            intended_use="screen",
            purpose=UsePurpose.SCREENING,
        )


def test_actual_source_cluster_cannot_be_withheld_validation_cluster():
    ref = pool((year(cluster="heldout-climate-2010"),), (Fraction(99, 100),))
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
    daily_assessment = synthetic_acceptance(pattern_product(first, intended_use="screen", purpose=UsePurpose.SCREENING))
    assert "heldout-climate-2010" in daily_assessment.evidence.validation.validation_clusters
    result = construct_pattern(
        annual,
        TARGET,
        (ref,),
        settings,
        shape_assessment=daily_assessment,
        intended_use="screen",
        purpose=UsePurpose.SCREENING,
        magnitude_assessment=annual_assessment,
    )
    assert result.use_checks.finding is not CheckFinding.PASS
