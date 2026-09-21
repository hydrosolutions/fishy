"""Annual synthetic operator witnesses, not scientific validation or policy limits."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction
from math import exp

import pytest

from fishy.annual_statistics import (
    AnnualEstimator,
    AnnualExclusion,
    AnnualReference,
    ExceedanceProbability,
    ImportedDerivation,
    TrendTreatment,
    annual_mean,
    annual_use_checks,
    empirical_estimate,
    empirical_membership,
    fit_zero_mixture,
    fitted_estimate,
    fitted_membership,
    import_annual_estimate,
)
from fishy.evidence import (
    CheckFinding,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
    UseRestriction,
)
from fishy.flows import Coverage, FlowSample, Presence
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

LOCATION = Location(Reach("reach", "1", WaterBody("river", "1")), CalculationSection("section", "1"), "1")
PROVENANCE = Provenance(
    "synthetic",
    "scenario",
    "member",
    "test",
    "1",
    "1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
    ReferenceKind.PRESENT_CLIMATE_NATURAL,
)


def period(year):
    return Interval(datetime(year, 1, 1, tzinfo=UTC), datetime(year + 1, 1, 1, tzinfo=UTC))


def reference(values=(40, 30, 20, 10)):
    samples = tuple(
        FlowSample(LOCATION, period(2000 + i), Flow(v), Presence.PRESENT, PROVENANCE) for i, v in enumerate(values)
    )
    return AnnualReference(
        samples,
        Interval(samples[0].interval.start, samples[-1].interval.end),
        "present climate",
        1,
        0,
        (),
        TrendTreatment.COMMON_CLIMATE,
        "synthetic climate assessment",
    )


def estimate(ref=None, target=".5", fit=False):
    operator = fitted_estimate if fit else empirical_estimate
    return operator(ref or reference(), ExceedanceProbability(target), provenance=PROVENANCE, profile_version="1")


def findings(value, use="annual screen"):
    return EvidenceFindings(
        value.scope(use),
        value.provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("synthetic supported limited annual use",),
    )


def test_weibull_interpolation_support_exact_neighbours():
    result = estimate()
    assert result.value == Flow(25)
    assert [n.probability.value for n in result.neighbours] == [Fraction(2, 5), Fraction(3, 5)]
    assert estimate(target=".4").value == Flow(30)
    unavailable = estimate(target=".99")
    assert unavailable.value is None
    assert unavailable.probability_support_distance == Fraction(19, 100)
    assert "outside Weibull support" in unavailable.reasons[0]
    assert annual_use_checks(unavailable, findings(unavailable), "annual screen").finding is CheckFinding.FAIL
    assert estimate(target=".01").value is None


def test_ties_remain_repeated_and_order_does_not_change_membership():
    ref = reference((40, 20, 20, 10))
    assert [p.exceedance.value for p in empirical_membership(ref)] == [
        Fraction(1, 5),
        Fraction(1, 2),
        Fraction(1, 2),
        Fraction(4, 5),
    ]
    assert len(ref.values) == 4
    assert estimate(ref).value == Flow(20)
    reversed_ref = replace(ref, observations=ref.observations[::-1])
    assert empirical_membership(reversed_ref) == empirical_membership(ref)[::-1]


def test_zero_mixture_parameters_quantiles_and_atom_membership():
    ref = reference((0, exp(-1), 1, exp(1)))
    fit = fit_zero_mixture(ref)
    assert fit.zero_fraction == Fraction(1, 4)
    assert fit.log_mean == pytest.approx(0, abs=1e-14)
    assert fit.log_variance == pytest.approx(2 / 3, abs=1e-14)
    assert float(estimate(ref, ".375", fit=True).value.value) == pytest.approx(1, abs=1e-14)
    assert estimate(ref, ".75", fit=True).value == Flow(0)
    assert fitted_membership(ref, fit)[0].exceedance.value == Fraction(7, 8)
    assert fit.jumps[0].fitted_left == 0
    assert fit.jumps[0].fitted_right == 0.25
    assert fit.distribution_distance == max(j.distance for j in fit.jumps)


@pytest.mark.parametrize("values", [(0, 0, 0), (0, 1, 1), (1, 1, 1), (0, 0, 1)])
def test_invalid_positive_fit_even_at_zero_atom(values):
    ref = reference(values)
    result = estimate(ref, ".99", fit=True)
    assert result.value is None
    assert result.fit.log_variance is None
    with pytest.raises(ValueError, match="unavailable"):
        fitted_membership(ref, result.fit)
    assert estimate(ref).value is not None


def test_distribution_diagnostic_evaluates_left_and_right_of_tied_jumps():
    fit = fit_zero_mixture(reference((1, 2, 2, 2)))
    first = fit.jumps[-1]
    assert first.empirical_left == 0.25
    assert first.empirical_right == 1
    assert first.distance == max(abs(0.25 - first.fitted_left), abs(1 - first.fitted_right))
    assert first.distance > abs(1 - first.fitted_right)  # left side is discriminating here


def test_complete_volume_weighted_annual_means_and_leap_duration():
    interval = period(2000)
    split = datetime(2000, 2, 1, tzinfo=UTC)
    samples = (
        FlowSample(LOCATION, Interval(interval.start, split), Flow(2), Presence.PRESENT, PROVENANCE),
        FlowSample(LOCATION, Interval(split, interval.end), Flow(4), Presence.PRESENT, PROVENANCE),
    )
    result = annual_mean(samples, accounting_start_month=1, utc_offset_minutes=0, provenance=PROVENANCE)
    assert result.value == Flow(Fraction(2 * 31 + 4 * 335, 366))
    assert result.value != Flow(3)
    assert result.components == samples
    for year, seconds in [(2000, 31622400), (2001, 31536000)]:
        sample = FlowSample(LOCATION, period(year), Flow(8), Presence.PRESENT, PROVENANCE)
        output = annual_mean((sample,), accounting_start_month=1, utc_offset_minutes=0, provenance=PROVENANCE)
        assert output.value is not None
        assert output.value.value * output.interval.seconds == 8 * seconds


def test_missing_overlap_partial_and_identity_are_not_annual_observations():
    ref = reference()
    bad = [
        replace(ref.observations[0], value=None, presence=Presence.MISSING, reasons=("missing",)),
        replace(ref.observations[0], coverage=Coverage.PARTIAL, reasons=("gap",)),
        replace(ref.observations[0], provenance=replace(PROVENANCE, reference_member="other")),
    ]
    for item in bad:
        with pytest.raises(ValueError):
            replace(ref, observations=(item,) + ref.observations[1:])
    with pytest.raises(ValueError, match="overlapping"):
        replace(ref, observations=ref.observations + ref.observations[:1])
    with pytest.raises(ValueError, match="missing year"):
        replace(ref, observations=ref.observations[:1] + ref.observations[2:])
    excluded = replace(
        ref,
        observations=ref.observations[:1] + ref.observations[2:],
        exclusions=(AnnualExclusion(period(2001), "missing year retained as exclusion"),),
    )
    assert len(excluded.values) == 3
    missing = bad[0]
    unsupported = annual_mean((missing,), accounting_start_month=1, utc_offset_minutes=0, provenance=PROVENANCE)
    assert unsupported.presence is Presence.UNSUPPORTED and unsupported.value is None


def test_fixed_offset_accounting_year_and_unresolved_partial_year():
    zone = timezone(timedelta(hours=5))
    interval = Interval(datetime(2000, 10, 1, tzinfo=zone), datetime(2001, 10, 1, tzinfo=zone))
    sample = FlowSample(LOCATION, interval, Flow(1), Presence.PRESENT, PROVENANCE)
    ref = AnnualReference((sample,), interval, "reference climate", 10, 300, (), TrendTreatment.COMMON_CLIMATE, "study")
    assert estimate(ref).value == Flow(1)
    with pytest.raises(ValueError, match="midnight"):
        replace(ref, utc_offset_minutes=0)
    partial = replace(sample, interval=Interval(interval.start, interval.end - timedelta(days=1)))
    with pytest.raises(ValueError, match="complete accounting year"):
        annual_mean((partial,), accounting_start_month=10, utc_offset_minutes=300, provenance=PROVENANCE)


def test_trend_and_rating_restrictions_bind_without_destroying_numbers():
    trend = estimate(replace(reference(), trend=TrendTreatment.UNTREATED))
    assert trend.value == Flow(25)
    assert annual_use_checks(trend, findings(trend), "annual screen").finding is CheckFinding.FAIL
    unknown = estimate(replace(reference(), trend=TrendTreatment.UNASSESSED))
    assert annual_use_checks(unknown, findings(unknown), "annual screen").finding is CheckFinding.UNKNOWN
    current = estimate()
    supported = findings(current)
    assert annual_use_checks(current, supported, "annual screen").finding is CheckFinding.PASS
    assert supported.official_admissibility is OfficialAdmissibility.PENDING
    restricted = replace(
        supported, restrictions=(UseRestriction("rating-range sizing prohibition", ("annual screen",)),)
    )
    assert annual_use_checks(current, restricted, "annual screen").finding is CheckFinding.FAIL
    assert (
        annual_use_checks(
            current, replace(restricted, scientific_adequacy=ScientificAdequacy.UNKNOWN), "annual screen"
        ).finding
        is CheckFinding.FAIL
    )
    assert (
        annual_use_checks(
            current, replace(supported, scope=replace(supported.scope, product="annual")), "annual screen"
        ).finding
        is CheckFinding.UNKNOWN
    )
    wrong = replace(supported, provenance=replace(PROVENANCE, scenario="other"))
    assert annual_use_checks(current, wrong, "annual screen").finding is CheckFinding.FAIL


def derivation():
    return ImportedDerivation(
        "q(P,t)=exp(a+b*t+sigma*Phi^-1(1-P))",
        "MLE version 1 parameters artifact",
        "annual complete calibration data artifact",
        ("withheld errors artifact",),
        "target inside declared domain",
        "external joint error study",
        "script/data hash artifact",
        ("year",),
        "present climate scenario 2026",
    )


def test_supported_import_and_missing_nonstationary_derivation():
    ref = replace(reference(), trend=TrendTreatment.UNTREATED)
    imported = import_annual_estimate(
        ref,
        ExceedanceProbability(".99"),
        Flow(7),
        estimator=AnnualEstimator.IMPORTED_NONSTATIONARY,
        profile_version="study-1",
        provenance=PROVENANCE,
        derivation=derivation(),
    )
    assert imported.value == Flow(7)
    assert imported.derivation == derivation()
    assert imported.probability_support_distance == Fraction(19, 100)
    assert annual_use_checks(imported, findings(imported), "annual screen").finding is CheckFinding.PASS
    with pytest.raises(ValueError, match="covariates"):
        import_annual_estimate(
            ref,
            imported.target,
            Flow(7),
            estimator=AnnualEstimator.IMPORTED_NONSTATIONARY,
            profile_version="study-1",
            provenance=PROVENANCE,
            derivation=replace(derivation(), covariates=()),
        )
    stationary = replace(imported, estimator=AnnualEstimator.IMPORTED_STATIONARY)
    assert annual_use_checks(stationary, findings(stationary), "annual screen").finding is CheckFinding.FAIL
    with pytest.raises(ValueError, match="attribution"):
        replace(derivation(), equation="")


@pytest.mark.parametrize("invalid", [0, 1, -1, "nan", "inf", True])
def test_invalid_probabilities(invalid):
    with pytest.raises((ValueError, TypeError)):
        ExceedanceProbability(invalid)
