"""Derived Appendix A entry supplements; exact arithmetic, no adopted settings."""

from dataclasses import replace
from fractions import Fraction

import pytest
from test_scientific_acceptance import product, supplied

from fishy.evidence import CheckFinding
from fishy.graduated_entry import (
    EntryStatistic,
    EntryStatus,
    GraduatedCurve,
    GraduatedSegment,
    LargeRiverScreen,
    ParameterBasis,
    evaluate_graduated_entry,
)
from fishy.quantities import Flow
from fishy.residual_flow import statutory_minimum
from fishy.scientific_acceptance import (
    DailyDerivation,
    HydrologicalProductKind,
    RatingSupport,
    TemporalResolution,
    UsePurpose,
    assess_scientific_use,
)


def curve():
    return GraduatedCurve(
        "synthetic-v1",
        (
            GraduatedSegment(Flow(0), Flow(0), Fraction(".8")),
            GraduatedSegment(Flow(10), Flow(8), Fraction(".2")),
            GraduatedSegment(Flow(20), Flow(10), Fraction(".1")),
        ),
        ParameterBasis.HYPOTHETICAL,
        "derived Appendix A synthetic continuous curve; not policy",
    )


def screen():
    return LargeRiverScreen(
        "synthetic-v1",
        Flow(100),
        Fraction(".1"),
        Fraction(".3"),
        ParameterBasis.HYPOTHETICAL,
        "illustrative screen, not policy",
        "sensitivity 90/100/110",
    )


def statistic(value=10, *, indicative=False, rating=RatingSupport.WITHIN_RANGE, derivation=DailyDerivation.NATIVE):
    subject = replace(
        product(),
        kind=HydrologicalProductKind.LOW_FLOW_STATISTIC,
        resolution=TemporalResolution.DAILY,
        purpose=UsePurpose.SIZING,
        target_probability=Fraction(347, 365),
        statistic_name="pooled daily Q347",
        result_value=Flow(value),
        scope=replace(product().scope, intended_use=UsePurpose.SIZING.value),
    )
    record, evidence = supplied(subject)
    if indicative:
        record = replace(record, indicative_basis="short synthetic record: supported limited sizing with uncertainty")
    evidence = replace(evidence, rating=rating, daily_derivation=derivation, frozen_record=record)
    return EntryStatistic(subject, assess_scientific_use(record, evidence))


def test_continuity_concavity_junction_equality_and_unrounded_values():
    c = curve()
    assert c.evaluate(Flow(10))[0] == Flow(8)
    assert c.evaluate(Flow(20))[0] == Flow(10)
    assert c.evaluate(Flow("10.000001"))[0] == Flow("8.0000002")
    with pytest.raises(ValueError, match="continuous"):
        replace(c, segments=(c.segments[0], replace(c.segments[1], anchor=Flow("8.00001"))))
    with pytest.raises(ValueError, match="concave"):
        replace(c, segments=(c.segments[0], replace(c.segments[1], marginal_rate=Fraction(".9"))))


def test_literal_swiss_jumps_remain_independent_and_refused_as_uzbek_curve():
    assert statutory_minimum(Flow(500, "l/s")) == Flow(280, "l/s")
    assert statutory_minimum(Flow(40, "l/s")) == Flow(50, "l/s")
    with pytest.raises(ValueError, match="continuous"):
        GraduatedCurve(
            "literal",
            (
                GraduatedSegment(Flow(160, "l/s"), Flow(130, "l/s"), Fraction(".44")),
                GraduatedSegment(Flow(500, "l/s"), Flow(280, "l/s"), Fraction(".31")),
            ),
            ParameterBasis.HYPOTHETICAL,
            "independent Swiss comparator",
        )


def test_supported_and_indicative_entry_floor_only():
    for indicative in (False, True):
        result = evaluate_graduated_entry(statistic(indicative=indicative), curve(), screen())
        assert result.status is EntryStatus.FLOOR_ONLY
        assert result.floor == Flow(8)
        assert result.statistic.assessment.findings.official_admissibility.value == "pending"


@pytest.mark.parametrize("value", [0, 1])
def test_floor_equal_or_greater_than_input_refuses_without_cap(value):
    c = GraduatedCurve(
        "synthetic-v1",
        (GraduatedSegment(Flow(0), Flow(1), Fraction(0)),),
        ParameterBasis.HYPOTHETICAL,
        "synthetic constant anchor",
    )
    result = evaluate_graduated_entry(statistic(value), c, screen())
    assert result.status is EntryStatus.REFUSED
    assert result.candidate == Flow(1)
    assert result.floor is None


def test_large_river_exact_screen_and_missing_screen_retained():
    assert evaluate_graduated_entry(statistic(99), curve(), screen()).status is EntryStatus.FLOOR_ONLY
    result = evaluate_graduated_entry(statistic(100), curve(), screen())
    assert result.status is EntryStatus.REFUSED
    assert result.candidate == Flow(18)
    missing = evaluate_graduated_entry(statistic(), curve(), None)
    assert missing.status is EntryStatus.UNAVAILABLE and missing.candidate == Flow(8)
    assert missing.checks[-1].finding is CheckFinding.UNKNOWN
    assert evaluate_graduated_entry(statistic(), None, None).status is EntryStatus.UNAVAILABLE


def test_rating_and_unsupported_daily_disaggregation_cannot_size():
    for s in (
        statistic(indicative=True, rating=RatingSupport.OUTSIDE_RANGE),
        statistic(derivation=DailyDerivation.DISAGGREGATED),
    ):
        assert evaluate_graduated_entry(s, curve(), screen()).status is EntryStatus.UNAVAILABLE


def test_annual_or_coarse_product_cannot_be_relabelled_as_entry():
    s = statistic()
    with pytest.raises(ValueError, match="daily low-flow"):
        replace(s.product, resolution=TemporalResolution.ANNUAL)
    with pytest.raises(ValueError):
        replace(s.product, resolution=TemporalResolution.DEKADAL)
    with pytest.raises(ValueError, match="not an annual"):
        EntryStatistic(product(), s.assessment)


@pytest.mark.parametrize(
    "changes",
    [
        {"result_value": Flow(11)},
        {"target_probability": Fraction(95, 100)},
        {"statistic_name": "another statistic"},
        {"reference_identity": "other reference"},
    ],
)
def test_changed_exact_statistic_does_not_inherit_acceptance(changes):
    s = statistic()
    changed = replace(s, product=replace(s.product, **changes))
    assert evaluate_graduated_entry(changed, curve(), screen()).status is EntryStatus.UNAVAILABLE


def test_forged_output_label_cannot_override_failed_scientific_inputs():
    s = statistic(rating=RatingSupport.OUTSIDE_RANGE)
    accepted = statistic()
    forged = replace(s.assessment, findings=accepted.assessment.findings, checks=accepted.assessment.checks)
    assert evaluate_graduated_entry(replace(s, assessment=forged), curve(), screen()).status is EntryStatus.UNAVAILABLE


@pytest.mark.parametrize("changes", [{"target_probability": None}, {"result_value": None}])
def test_daily_low_flow_product_requires_probability_and_bound_scalar(changes):
    with pytest.raises(ValueError):
        replace(statistic().product, **changes)
