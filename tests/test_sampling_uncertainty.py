"""D.7 rule 4: enforce external sampling coverage and exact linear covariance."""

from dataclasses import replace
from fractions import Fraction

import pytest

from fishy.quantities import Flow
from fishy.sampling_uncertainty import (
    FlowCovariance,
    LinearFlowCoefficients,
    ReplicateFailure,
    ReplicateSeries,
    SamplingPlan,
    propagate_linear_covariance,
    sampling_intervals,
)


def plan():
    return SamplingPlan(
        years=(2000, 2001, 2002, 2003, 2004),
        block_length=2,
        replicate_count=3,
        indices=((4, 0, 2, 3, 1), (1, 2, 3, 4, 0), (0, 1, 4, 0, 3)),
        generator="external-generator",
        generator_version="1",
        seed=42,
        start_method="uniform",
        estimator="zero-mixture-lognormal",
        estimator_version="1",
        complete_year_evidence="Five complete calendar-year statistics",
        dependence_diagnostics="Lag correlations supplied by study",
        block_length_sensitivity="L=2 and L=3 compared",
    )


def series(p, outcomes=None, quantity="reach A"):
    return ReplicateSeries(
        quantity,
        p.estimator,
        p.estimator_version,
        "Refit each sampled sequence",
        p.indices,
        (Flow(10), Flow(30), Flow(20)) if outcomes is None else outcomes,
    )


def test_type7_flow_endpoints_and_attribution():
    p = plan()
    item = series(p)
    (result,) = sampling_intervals(p, (item,), Fraction(1, 5))
    assert result.interval is not None
    assert result.interval.lower == Flow(12)
    assert result.interval.upper == Flow(28)
    assert result.interval.confidence == Fraction(4, 5)
    assert result.interval.scope == "conditional stationary sampling"
    assert result.plan == p and result.series == item
    assert result.failed_count == 0


def test_all_failures_retained_no_survivor_interval():
    p = plan()
    first = ReplicateFailure(("Only one distinct positive value", "positive log variance is zero"))
    last = ReplicateFailure(("target unavailable",))
    (result,) = sampling_intervals(p, (series(p, (first, Flow(8), last)),), "0.05")
    assert result.interval is None
    assert result.failed_count == 2
    assert result.failures == ((0, first), (2, last))
    assert result.series.outcomes[1] == Flow(8)


@pytest.mark.parametrize(
    "changes",
    [
        {"years": (2000, 2001, 2003, 2004, 2005)},
        {"years": (2004, 2003, 2002, 2001, 2000)},
        {"block_length": 0},
        {"block_length": 5},
        {"block_length": 2.0},
        {"block_length": True},
        {"replicate_count": 1},
        {"replicate_count": 3.0},
        {"seed": True},
        {"start_method": "biased"},
        {"generator": ""},
        {"generator_version": ""},
        {"complete_year_evidence": ""},
        {"dependence_diagnostics": None},
        {"block_length_sensitivity": ""},
        {"block_length": 1},
        {"indices": ((4, 1, 2, 3, 1),) * 3},
        {"indices": ((4, 0, 2, 3),) * 3},
        {"indices": ((4, 0, 2, 3, 5),) * 3},
        {"indices": ((4, 0, 2, 3, 1),) * 2},
    ],
)
def test_plan_rejects_broken_contract(changes):
    with pytest.raises(ValueError):
        replace(plan(), **changes)


def test_l1_requires_independence_but_not_block_diagnostics():
    p = replace(
        plan(),
        block_length=1,
        independence_justification="Study supports independent annual anomalies",
        dependence_diagnostics=None,
        block_length_sensitivity=None,
    )
    assert sampling_intervals(p, (series(p),), ".1")[0].interval is not None


def test_related_quantities_use_identical_indices():
    p = plan()
    a, b = series(p), series(p, quantity="reach B")
    results = sampling_intervals(p, (a, b), ".1")
    assert len(results) == 2
    with pytest.raises(ValueError, match="same sampled"):
        sampling_intervals(p, (a, replace(b, indices=p.indices[::-1])), ".1")


@pytest.mark.parametrize(
    "changes",
    [
        {"estimator": "other"},
        {"estimator_version": "2"},
        {"outcomes": (Flow(1), Flow(2))},
    ],
)
def test_external_estimator_and_complete_coverage(changes):
    p = plan()
    with pytest.raises(ValueError):
        sampling_intervals(p, (replace(series(p), **changes),), ".1")


@pytest.mark.parametrize("alpha", [0, 1, -1, "NaN"])
def test_alpha_refused(alpha):
    p = plan()
    with pytest.raises(ValueError):
        sampling_intervals(p, (series(p),), alpha)


def test_exact_covariance_with_signed_coefficients_and_unit_conversion():
    c = LinearFlowCoefficients((1, -2))
    covariance = FlowCovariance(((4, 1), (1, 9)), "(m3/s)^2", "supported study")
    result = propagate_linear_covariance(c, covariance)
    assert result.squared_m3_per_s == 36
    assert result.covariance == covariance and result.coefficients == c
    small = FlowCovariance(((4000000, 1000000), (1000000, 9000000)), "(l/s)^2", "supported study")
    assert propagate_linear_covariance(c, small).squared_m3_per_s == 36
    assert not hasattr(result, "half_width")


@pytest.mark.parametrize("matrix", [((1, 1), (1, 1)), ((0, 0), (0, 2)), ((0, 0), (0, 0))])
def test_singular_psd_is_supported(matrix):
    covariance = FlowCovariance(matrix, "(m3/s)^2", "study")
    assert propagate_linear_covariance(LinearFlowCoefficients((1, -1)), covariance).squared_m3_per_s >= 0


@pytest.mark.parametrize(
    "matrix",
    [
        ((1, 2), (2, 1)),
        ((0, 1), (1, 2)),
        ((-1,),),
        ((1, 0), (1, 1)),
        ((1, 0),),
        (),
        (("NaN",),),
        ((1, 1), (1, "0.9999999999999999999999999999999999999999")),
    ],
)
def test_covariance_rejects_indefinite_asymmetric_nonfinite_and_nonsquare(matrix):
    with pytest.raises(ValueError):
        FlowCovariance(matrix, "(m3/s)^2", "study")


def test_incompatible_units_and_dimensions():
    with pytest.raises(ValueError, match="units"):
        FlowCovariance(((1,),), "m3", "study")
    with pytest.raises(ValueError, match="dimensions"):
        propagate_linear_covariance(LinearFlowCoefficients((1, 2)), FlowCovariance(((1,),), "(m3/s)^2", "study"))


def test_zero_ties_two_replicates_and_exact_fraction_quantiles():
    p = replace(plan(), replicate_count=2, indices=plan().indices[:2])
    (result,) = sampling_intervals(p, (series(p, (Flow(0), Flow(1))),), Fraction(1, 3))
    assert result.interval is not None
    assert result.interval.lower == Flow(Fraction(1, 6))
    assert result.interval.upper == Flow(Fraction(5, 6))
    (tied,) = sampling_intervals(p, (series(p, (Flow(0), Flow(0))),), Fraction(1, 3))
    assert tied.interval is not None
    assert tied.interval.lower == tied.interval.upper == Flow(0)


def test_failed_quantity_does_not_disable_supported_related_quantity():
    p = plan()
    failed = series(p, (ReplicateFailure(("fit failure",)),) * 3)
    failed_result, supported = sampling_intervals(p, (failed, series(p, quantity="independent output")), ".1")
    assert failed_result.interval is None and failed_result.failed_count == 3
    assert supported.interval is not None


def test_empty_reasons_missing_outcomes_and_duplicate_quantities_refused():
    p = plan()
    with pytest.raises(ValueError):
        ReplicateFailure(())
    with pytest.raises(ValueError):
        ReplicateFailure(("",))
    with pytest.raises(TypeError):
        series(p, (None, Flow(1), Flow(2)))
    with pytest.raises(ValueError):
        sampling_intervals(p, (), ".1")
    with pytest.raises(ValueError):
        sampling_intervals(p, (series(p), series(p)), ".1")
