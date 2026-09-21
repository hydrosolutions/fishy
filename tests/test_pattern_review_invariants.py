from dataclasses import replace
from fractions import Fraction

import pytest
from test_daily_patterns import PASS, construct, pool, profile, year


def test_retained_carrier_is_immutable():
    ref = pool((year(),), (Fraction(99, 100),))
    result = construct((ref,))
    with pytest.raises(TypeError):
        replace(result, retained=list(result.retained))


def test_stored_support_cannot_contradict_actual_contributions():
    ref = pool((year(),), (Fraction(99, 100),))
    result = construct((ref,), profile((ref,), sources=2))
    with pytest.raises(ValueError):
        replace(result, support=PASS)


def test_stored_membership_cannot_contradict_actual_contributions():
    ref = pool((year(),), (Fraction(99, 100),))
    result = construct((ref,))
    with pytest.raises(ValueError):
        replace(result, membership=replace(result.membership, climate_cluster_count=99))
