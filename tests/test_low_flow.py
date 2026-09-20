"""Synthetic Swiss hydrology witnesses; all numerical assertions are exact."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.evidence import (
    Check,
    CheckFinding,
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.flows import FlowSample, Presence
from fishy.low_flow import (
    DailyBasis,
    EstimateStatus,
    Q347Conventions,
    Q347Review,
    Q347Use,
    VerificationRoute,
    assess_q347,
    imported_q347,
    pooled_q347,
)
from fishy.quantities import Flow, FlowBounds
from fishy.residual_flow import attributed_starting_minimum, statutory_minimum
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

LOCATION = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
PROVENANCE = Provenance(
    "synthetic witness", "scenario", "member", "test", "1", "1", ProductionMethod.ILLUSTRATIVE, CorrectionState.ORIGINAL
)
CONVENTIONS = Q347Conventions("selected complete synthetic record; no correction", DailyBasis.DAILY_OBSERVATIONS)


def period(start=2001, end=2003):
    return Interval(datetime(start, 1, 1, tzinfo=UTC), datetime(end, 1, 1, tzinfo=UTC))


def series(start=2001, end=2003):
    p = period(start, end)
    result = []
    day = p.start
    while day < p.end:
        # Dry first year, wet second year. Their annual Q347s are 1 and 100 l/s.
        flow = 1 if day.year == start else 100
        result.append(
            FlowSample(
                LOCATION, Interval(day, day + timedelta(days=1)), Flow(flow, "l/s"), Presence.PRESENT, PROVENANCE
            )
        )
        day += timedelta(days=1)
    return tuple(result)


def imported(status=EstimateStatus.FINAL):
    return imported_q347(
        Flow(160, "l/s"),
        LOCATION,
        period(),
        PROVENANCE,
        "supported synthetic observation/model estimate",
        status,
        FlowBounds(Flow(150, "l/s"), Flow(170, "l/s"), "scenario range", "study", "supplied"),
    )


def review(estimate, route=VerificationRoute.NOT_APPLICABLE, use="final Q347 determination"):
    scope = EvidenceScope("Q347", "reach", "member", estimate.reference_period, use)
    findings = EvidenceFindings(
        scope,
        PROVENANCE,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("synthetic supplied scientific decision",),
    )
    passed = Check("supplied", CheckFinding.PASS, ("synthetic specialist evidence",))
    return Q347Review(
        estimate,
        Q347Use.INDICATIVE_SCENARIO if use == "indicative scenario" else Q347Use.FINAL_DETERMINATION,
        findings,
        passed,
        passed,
        passed,
        route,
        passed,
        None,
        "supplied applicability/exception assessment",
    ), scope


def test_pooled_not_mean_annual_and_short_accepted():
    samples = series()
    pooled = pooled_q347(samples, CONVENTIONS, PROVENANCE, EstimateStatus.FINAL)
    annual = [
        pooled_q347(
            tuple(s for s in samples if s.interval.start.year == y), CONVENTIONS, PROVENANCE, EstimateStatus.FINAL
        )
        for y in (2001, 2002)
    ]
    assert pooled.value == Flow(1, "l/s")
    assert sum(q.value.value for q in annual) / 2 == Flow("50.5", "l/s").value
    r, scope = review(pooled)
    assert assess_q347(pooled, r, scope).finding is CheckFinding.PASS
    assert r.findings.official_admissibility is OfficialAdmissibility.PENDING


def test_ten_year_meaning_and_leap_days():
    samples = series(2000, 2010)
    # Unique descending flows expose the exact rank, including leap days.
    samples = tuple(replace(s, value=Flow(len(samples) - i, "l/s")) for i, s in enumerate(samples))
    result = pooled_q347(samples, CONVENTIONS, PROVENANCE, EstimateStatus.PRELIMINARY)
    assert len(samples) == 3653
    assert result.value == Flow(184, "l/s")  # rank3470 of3653, not rounded Q95
    assert result.reference_period == period(2000, 2010)
    assert result.samples == samples
    assert result.conventions == CONVENTIONS


def test_daily_support_rejects_gaps_coarse_and_false_identity():
    samples = series()
    for invalid in (samples[1:], samples[:10] + samples[11:], samples + samples[:1]):
        with pytest.raises(ValueError):
            pooled_q347(invalid, CONVENTIONS, PROVENANCE, EstimateStatus.PRELIMINARY)
    with pytest.raises(ValueError, match="coarse"):
        pooled_q347(
            samples,
            replace(CONVENTIONS, daily_basis=DailyBasis.COARSE_REPETITION),
            PROVENANCE,
            EstimateStatus.PRELIMINARY,
        )
    with pytest.raises(ValueError, match="daily means"):
        pooled_q347(
            (replace(samples[0], interval=Interval(samples[0].interval.start, samples[30].interval.end)),),
            CONVENTIONS,
            PROVENANCE,
            EstimateStatus.PRELIMINARY,
        )
    with pytest.raises(ValueError, match="identity"):
        pooled_q347(samples, CONVENTIONS, replace(PROVENANCE, scenario="other"), EstimateStatus.PRELIMINARY)


def test_import_attribution_and_preliminary_scenario_not_final():
    estimate = imported(EstimateStatus.PRELIMINARY)
    r, scope = review(estimate)
    assert assess_q347(estimate, r, scope).finding is CheckFinding.UNKNOWN
    scenario_review, scenario_scope = review(estimate, use="indicative scenario")
    assert assess_q347(estimate, scenario_review, scenario_scope).finding is CheckFinding.PASS
    minimum = attributed_starting_minimum(estimate)
    assert minimum.value == Flow(130, "l/s")
    assert minimum.q347 is estimate
    assert minimum.q347.uncertainty is estimate.uncertainty


@pytest.mark.parametrize(
    "route",
    [
        VerificationRoute.REQUIRED,
        VerificationRoute.JUSTIFIED_EXCEPTION,
        VerificationRoute.NOT_APPLICABLE,
        VerificationRoute.UNRESOLVED,
    ],
)
def test_conditional_verification(route):
    estimate = imported()
    r, scope = review(estimate, route)
    result = assess_q347(estimate, r, scope)
    expected = (
        CheckFinding.UNKNOWN
        if route in (VerificationRoute.REQUIRED, VerificationRoute.UNRESOLVED)
        else CheckFinding.PASS
    )
    assert result.finding is expected
    if route is VerificationRoute.REQUIRED:
        assert (
            assess_q347(estimate, replace(r, verification_period=period(2000, 2003)), scope).finding
            is CheckFinding.PASS
        )
        assert (
            assess_q347(estimate, replace(r, verification_period=period(2000, 2002)), scope).finding
            is CheckFinding.UNKNOWN
        )


def test_failure_survives_missing_and_scoped_official_separation():
    estimate = imported()
    r, scope = review(estimate)
    failed = replace(
        r,
        influences=Check("influence", CheckFinding.FAIL, ("substantial abstraction",)),
        trend=Check("trend", CheckFinding.UNKNOWN),
    )
    result = assess_q347(estimate, failed, scope)
    assert result.finding is CheckFinding.FAIL
    assert result.completeness is Completeness.INCOMPLETE
    assert assess_q347(estimate, r, replace(scope, reach="other")).finding is CheckFinding.UNKNOWN
    assert (
        assess_q347(
            estimate, replace(r, findings=replace(r.findings, provenance=replace(PROVENANCE, scenario="other"))), scope
        ).finding
        is CheckFinding.UNKNOWN
    )


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        (0, 50),
        (1, 50),
        ("59.999", 50),
        (60, 50),
        ("60.001", "50.0008"),
        ("159.999", "129.9992"),
        (160, 130),
        ("160.001", "130.00044"),
        ("499.999", "279.59956"),
        (500, 280),
        ("500.001", "280.00031"),
        ("2499.999", "899.99969"),
        (2500, 900),
        ("2500.001", "900.000213"),
        ("9999.999", "2497.499787"),
        (10000, 2500),
        ("10000.001", "2500.00015"),
        ("59999.999", "9999.99985"),
        (60000, 10000),
        ("60000.001", 10000),
        (100000, 10000),
    ],
)
def test_literal_table(q, expected):
    assert statutory_minimum(Flow(q, "l/s")) == Flow(expected, "l/s")


@pytest.mark.parametrize("invalid", [-1, "nan", "inf", float("-inf")])
def test_invalid_amount(invalid):
    with pytest.raises(ValueError):
        statutory_minimum(Flow(invalid, "l/s"))


def test_zero_small_positive_and_uncapped():
    assert replace(imported(), value=Flow(0), uncertainty=None).permanent_flow is CheckFinding.FAIL
    assert (
        replace(imported(), value=Flow(Fraction(1, 1000), "l/s"), uncertainty=None).permanent_flow is CheckFinding.PASS
    )
    assert statutory_minimum(Flow(1, "l/s")).value > Flow(1, "l/s").value


def test_different_product_cannot_accept_q347():
    estimate = imported()
    r, scope = review(estimate)
    wrong = replace(scope, product="monthly mean")
    wrong_review = replace(r, findings=replace(r.findings, scope=wrong))
    assert assess_q347(estimate, wrong_review, wrong).finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize("change", ["section", "reach_version", "data_version", "configuration_version"])
def test_review_bound_to_complete_estimate(change):
    estimate = imported()
    r, scope = review(estimate)
    if change == "section":
        altered = replace(estimate, location=replace(estimate.location, section=CalculationSection("other", "1")))
    elif change == "reach_version":
        altered = replace(
            estimate, location=replace(estimate.location, reach=replace(estimate.location.reach, version="2"))
        )
    else:
        altered = replace(estimate, provenance=replace(estimate.provenance, **{change: "2"}))
    assert assess_q347(altered, r, scope).finding is CheckFinding.UNKNOWN


def test_pooled_carrier_cannot_lie():
    estimate = pooled_q347(series(), CONVENTIONS, PROVENANCE, EstimateStatus.FINAL)
    with pytest.raises(ValueError):
        replace(estimate, value=Flow(999, "l/s"))


def test_pooled_carrier_rejects_untyped_contributors():
    estimate = pooled_q347(series(), CONVENTIONS, PROVENANCE, EstimateStatus.FINAL)
    with pytest.raises(TypeError):
        replace(estimate, samples=("not a sample",), conventions="not conventions")


def test_pooled_cannot_promote_illustration_to_observation():
    with pytest.raises(ValueError):
        pooled_q347(
            series(),
            CONVENTIONS,
            replace(PROVENANCE, production_method=ProductionMethod.OBSERVED),
            EstimateStatus.FINAL,
        )


def test_typed_final_use_cannot_be_bypassed_by_scope_label():
    estimate = imported(EstimateStatus.PRELIMINARY)
    r, scope = review(estimate, VerificationRoute.REQUIRED, use="final determination")
    assert r.use is Q347Use.FINAL_DETERMINATION
    assert assess_q347(estimate, r, scope).finding is CheckFinding.UNKNOWN
    with pytest.raises(TypeError):
        replace(r, use="final determination")


def test_constructor_also_rejects_observed_promotion_and_method_conflict():
    estimate = pooled_q347(series(), CONVENTIONS, PROVENANCE, EstimateStatus.FINAL)
    with pytest.raises(ValueError):
        replace(estimate, provenance=replace(PROVENANCE, production_method=ProductionMethod.OBSERVED))
    with pytest.raises(ValueError):
        replace(estimate, method_description="mean annual Q347")
    with pytest.raises(ValueError):
        replace(imported(), samples=series())
