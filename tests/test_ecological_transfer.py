"""U6 complete-calendar transfer/fallback witnesses; exact Fraction tolerance zero."""

from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

import pytest

from examples.ecological_transfer import synthetic_inputs, synthetic_pattern
from fishy.design_conditions import DesignClass
from fishy.ecological_transfer import (
    TransferEdge,
    TransferRegister,
    map_monthly_ratios,
    transfer_ecological_regime,
    transfer_scope,
)
from fishy.evidence import CheckFinding, ReferenceKind, UseRestriction
from fishy.natural_baseline import EcologicalRegimeMethod
from fishy.pattern_calendar import AccountingYear, map_calendar
from fishy.presumptive_floor import (
    PresumptiveProfile,
    SeasonalFraction,
    presumptive_floor,
    presumptive_reference_identity,
)
from fishy.quantities import Flow

NOW = datetime(2026, 9, 5, tzinfo=UTC)


@pytest.fixture(scope="module")
def inputs():
    return synthetic_inputs(AccountingYear(2023, 1, 0))


def run(args):
    return transfer_ecological_regime(*args, evaluated_at=NOW)


def requalify(args):
    donor, dn, rn, profile, evidence, register = args
    return (
        donor,
        dn,
        rn,
        profile,
        replace(evidence, scope=transfer_scope(donor, dn, rn, profile), provenance=rn[0].magnitude.provenance),
        register,
    )


def test_u6_complete_family_ecological_two_four_to_three_five(inputs):
    result = run(inputs)
    assert result.checks.finding is CheckFinding.PASS
    assert result.candidate is not None
    for c in result.candidate.classes:
        assert tuple(s.value for s in c.samples) == (Flow(3),) + (Flow(5),) * 364
    assert all(m.ratios == (Fraction(1, 2),) * 365 for m in result.mappings)
    assert result.candidate.method is EcologicalRegimeMethod.TRANSFER
    assert result.candidate.provenance.reference_member == "recipient-member"
    assert result.register.edges == (TransferEdge(inputs[0].location, inputs[2][0].location, inputs[3].version),)
    # Only the typed pre-quality donor participates, not its separately supplied quality 5/6.
    assert result.donor.classes[0].samples[0].value == Flow(2)
    assert result.candidate.classes[0].samples[0].value != Flow(Fraction(5, 4) * 6)


def test_ratio_calendar_mapping_is_not_volume_mapping():
    source, target = AccountingYear(2023, 1, 0), AccountingYear(2024, 1, 0)
    ratios = (Fraction(1),) * source.days
    assert map_monthly_ratios(source, ratios, target) == (Fraction(1),) * 366
    assert map_calendar(source, ratios, target)[31] == Fraction(28, 29)
    spike = (Fraction(),) * 31 + (Fraction(1),) + (Fraction(),) * 333
    mapped = map_monthly_ratios(source, spike, target)
    assert mapped[31:33] == (Fraction(1), Fraction(1, 28))
    assert sum(mapped[31:60]) == Fraction(29, 28)
    assert map_monthly_ratios(source, spike, source) == spike


@pytest.mark.parametrize("target", [AccountingYear(2024, 10, 0), AccountingYear(2024, 1, 60)])
def test_unsupported_calendar_mapping_refused(target):
    with pytest.raises(ValueError, match="matching"):
        map_monthly_ratios(AccountingYear(2023, 1, 0), (Fraction(1),) * 365, target)


@pytest.mark.parametrize("requirement", [0, 2])
def test_zero_donor_denominator_including_zero_over_zero_unavailable(inputs, requirement):
    donor, dn, rn, profile, evidence, register = inputs
    altered = synthetic_pattern(
        "donor", donor.calendar, DesignClass.WET, (Fraction(), Fraction(12)) + (Fraction(8),) * 363
    )
    first = donor.classes[0]
    donor = replace(
        donor,
        classes=(
            replace(first, samples=(replace(first.samples[0], value=Flow(requirement)), *first.samples[1:])),
            *donor.classes[1:],
        ),
    )
    result = run(requalify((donor, (altered, *dn[1:]), rn, profile, evidence, register)))
    assert result.candidate is None
    assert any("zero donor denominator" in r for c in result.checks.checks for r in c.reasons)
    assert len(result.mappings) == 3  # Supported independent classes remain diagnostic, never an issued subset.


def test_finite_ratio_recipient_zero_is_zero(inputs):
    donor, dn, rn, profile, evidence, register = inputs
    altered = synthetic_pattern(
        "recipient", donor.calendar, DesignClass.WET, (Fraction(), Fraction(16)) + (Fraction(10),) * 363
    )
    result = run(requalify((donor, dn, (altered, *rn[1:]), profile, evidence, register)))
    assert result.candidate is not None
    assert result.candidate.classes[0].samples[0].value == Flow(0)


def test_above_one_not_clipped_has_adequacy_flag(inputs):
    donor, dn, rn, profile, evidence, register = inputs
    donor = replace(
        donor,
        classes=tuple(replace(c, samples=tuple(replace(s, value=Flow(16)) for s in c.samples)) for c in donor.classes),
    )
    result = run(requalify((donor, dn, rn, profile, evidence, register)))
    assert result.candidate is not None
    assert result.candidate.classes[0].samples[0].value == Flow(24)
    assert result.mappings[0].above_one_days == tuple(range(365))
    assert result.mappings[0].adequacy_check.finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "unqualified",
        "restricted",
        "late-choice",
        "wrong-scope",
        "changed-donor",
        "missing-class",
        "wrong-shift",
        "unsupported-pattern",
        "chain",
        "cycle",
        "transferred",
    ],
)
def test_unsupported_inputs_do_not_produce_candidate(inputs, fault):
    donor, dn, rn, profile, evidence, register = inputs
    if fault == "missing":
        profile = None
    elif fault == "unqualified":
        profile = replace(profile, qualification=profile.qualification[:-1])
    elif fault == "restricted":
        evidence = replace(evidence, restrictions=(UseRestriction("not permitted for sizing", ("obligation sizing",)),))
    elif fault == "late-choice":
        profile = replace(profile, chosen_at=NOW)
    elif fault == "wrong-scope":
        evidence = replace(evidence, scope=replace(evidence.scope, member="other"))
    elif fault == "changed-donor":
        donor = replace(donor, profile_version="different-donor-study")
    elif fault == "missing-class":
        dn = dn[:-1]
    elif fault == "wrong-shift":
        dn = (dn[1], *dn[1:])
    elif fault == "unsupported-pattern":
        p = rn[0]
        rn = (replace(p, shape_assessment=None, shape_evidence=None), *rn[1:])
    elif fault == "chain":
        register = TransferRegister("chain", (TransferEdge(rn[0].location, donor.location, "earlier"),))
    elif fault == "cycle":
        register = TransferRegister(
            "cycle",
            (
                TransferEdge(donor.location, rn[0].location, "old"),
                TransferEdge(rn[0].location, donor.location, "reverse"),
            ),
        )
    elif fault == "transferred":
        donor = replace(donor, method=EcologicalRegimeMethod.TRANSFER)
    result = run((donor, dn, rn, profile, evidence, register))
    assert result.candidate is None
    assert result.checks.finding is not CheckFinding.PASS


def test_numeric_qualification_observations_are_evaluated(inputs):
    donor, dn, rn, profile, evidence, register = inputs
    q = profile.qualification[0]
    q = replace(q, observations=(replace(q.observations[0], candidate=0.2),))
    profile = replace(profile, qualification=(q, *profile.qualification[1:]))
    result = run(requalify((donor, dn, rn, profile, evidence, register)))
    assert result.candidate is None
    assert next(c for c in result.checks.checks if c.check_id == "regime").finding is CheckFinding.FAIL


def profile_for(reference):
    return PresumptiveProfile(
        "hypothetical-v1",
        "explicit own-class present-climate natural daily reference",
        presumptive_reference_identity(reference),
        (
            SeasonalFraction("winter", 0, 60, Fraction(1, 5)),
            SeasonalFraction("rest", 60, reference.calendar.days, Fraction(1, 4)),
        ),
        "assumed scenario, not national adoption",
        "high uncertainty retained",
    )


def test_presumptive_daily_fractions_no_regime_or_obligation(inputs):
    reference = inputs[2][0]
    result = presumptive_floor(reference, profile_for(reference))
    assert result.checks.finding is CheckFinding.PASS
    assert result.samples[0].value == Flow(Fraction(6, 5))
    assert result.samples[59].value == Flow(2)
    assert result.samples[60].value == Flow(Fraction(5, 2))
    assert not hasattr(result, "candidate")
    assert not hasattr(result, "obligation")
    assert not hasattr(result, "requirement")


@pytest.mark.parametrize(
    "fault",
    [
        "missing-reference",
        "missing-profile",
        "missing-season",
        "unsupported-reference",
        "wrong-reference",
        "future-reference",
    ],
)
def test_presumptive_missing_basis_is_not_zero(inputs, fault):
    reference = inputs[2][0]
    profile = profile_for(reference)
    if fault == "missing-reference":
        reference = None
    elif fault == "missing-profile":
        profile = None
    elif fault == "missing-season":
        profile = replace(profile, seasons=profile.seasons[:1])
    elif fault == "unsupported-reference":
        reference = replace(reference, shape_assessment=None, shape_evidence=None)
    elif fault == "wrong-reference":
        profile = replace(profile, reference_identity="other")
    elif fault == "future-reference":
        # Hydrology rejects a future-climate relabelling before floor sizing.
        with pytest.raises(ValueError, match="reference identity"):
            replace(
                reference.magnitude,
                provenance=replace(reference.magnitude.provenance, reference_kind=ReferenceKind.FUTURE_CLIMATE_STRESS),
            )
        return
    result = presumptive_floor(reference, profile)
    assert result.samples == ()
    assert result.checks.finding is not CheckFinding.PASS


def test_full_leap_year_transfer_and_presumptive():
    args = synthetic_inputs(AccountingYear(2024, 1, 0))
    result = run(args)
    assert result.candidate is not None
    assert len(result.candidate.classes[0].samples) == 366
    floor = presumptive_floor(args[2][0], profile_for(args[2][0]))
    assert len(floor.samples) == 366


@pytest.mark.parametrize("fraction", [-1, 2, float("nan"), float("inf")])
def test_invalid_presumptive_fraction_rejected(fraction):
    with pytest.raises(ValueError):
        SeasonalFraction("bad", 0, 365, fraction)


def test_incomplete_ratio_calendar_rejected():
    with pytest.raises(ValueError, match="complete"):
        map_monthly_ratios(AccountingYear(2023, 1, 0), (Fraction(1),) * 364, AccountingYear(2024, 1, 0))


def test_fallback_routes_recompute_sources_and_remember_failures(inputs):
    from fishy.evidence import Check, CheckSummary
    from fishy.natural_routing import NaturalRoute, RouteFailure, select_natural_route
    from fishy.spatial import DesignationState, Eligibility, Origin, PreparedClassification, UseCategory

    classification = PreparedClassification(
        Origin.NATURAL,
        DesignationState.NONE,
        Eligibility.NOT_APPLICABLE,
        UseCategory.AGRICULTURE_IRRIGATION,
        ("irrigation",),
        "synthetic natural origin",
        "v1",
    )
    transfer = run(inputs)
    reference = inputs[2][0]
    floor = presumptive_floor(reference, profile_for(reference))
    decision = select_natural_route(classification, (), transfer=transfer, presumptive=floor)
    assert decision.selected is NaturalRoute.TRANSFER
    failure = RouteFailure(
        NaturalRoute.TRANSFER, CheckFinding.FAIL, ("local quality upper bound failed after transfer",)
    )
    assert (
        select_natural_route(classification, (), (failure,), transfer=transfer, presumptive=floor).selected
        is NaturalRoute.PRESUMPTIVE
    )
    floor_failure = RouteFailure(NaturalRoute.PRESUMPTIVE, CheckFinding.UNKNOWN, ("local receptor evidence missing",))
    pending = select_natural_route(classification, (), (failure, floor_failure), transfer=transfer, presumptive=floor)
    assert pending.selected is NaturalRoute.PENDING
    assert pending.failures == (failure, floor_failure)
    false_pass = CheckSummary((Check("forged-pass", CheckFinding.PASS),))
    unsupported = replace(transfer, qualification=None, checks=false_pass)
    assert (
        select_natural_route(classification, (), transfer=unsupported, presumptive=floor).selected
        is NaturalRoute.PRESUMPTIVE
    )
    missing_floor = replace(presumptive_floor(None, None), checks=false_pass, samples=floor.samples)
    assert (
        select_natural_route(classification, (), transfer=unsupported, presumptive=missing_floor).selected
        is NaturalRoute.PENDING
    )


def test_known_zero_denominator_survives_missing_qualification(inputs):
    donor, dn, rn, profile, _, register = inputs
    altered = synthetic_pattern(
        "donor", donor.calendar, DesignClass.WET, (Fraction(), Fraction(12)) + (Fraction(8),) * 363
    )
    result = run((donor, (altered, *dn[1:]), rn, profile, None, register))
    assert result.candidate is None
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)


def test_full_transfer_maps_nonleap_donor_to_leap_recipient(inputs):
    donor, dn, _, profile, evidence, register = inputs
    calendar = AccountingYear(2024, 1, 0)
    rn = tuple(synthetic_pattern("recipient", calendar, c, (Fraction(10),) * 366) for c in DesignClass)
    result = run(requalify((donor, dn, rn, profile, evidence, register)))
    assert result.candidate is not None
    assert result.candidate.calendar == calendar
    assert all(s.value == Flow(5) for c in result.candidate.classes for s in c.samples)
    assert result.mappings[0].mapped == (Fraction(1, 2),) * 366


def test_supported_presumptive_zero_is_not_missing(inputs):
    reference = inputs[2][0]
    profile = replace(profile_for(reference), seasons=(SeasonalFraction("all-year", 0, 365, Fraction()),))
    result = presumptive_floor(reference, profile)
    assert result.checks.finding is CheckFinding.PASS
    assert tuple(s.value for s in result.samples) == (Flow(0),) * 365


def test_derived_values_never_inherit_untransformed_reference_uncertainty(inputs):
    from examples.ecological_transfer import synthetic_acceptance
    from fishy.daily_patterns import pattern_product
    from fishy.quantities import FlowBounds
    from fishy.scientific_acceptance import UsePurpose

    donor, dn, rn, profile, evidence, register = inputs
    first = rn[0]
    bounded_samples = tuple(
        replace(s, uncertainty=FlowBounds(s.value, s.value, "stipulated singleton", "synthetic", "fixed"))
        for s in first.samples
    )
    bounded = replace(first, samples=bounded_samples, shape_assessment=None, shape_evidence=None)
    assessment = synthetic_acceptance(
        pattern_product(bounded, intended_use=UsePurpose.SIZING.value, purpose=UsePurpose.SIZING)
    )
    bounded = replace(bounded, shape_assessment=assessment, shape_evidence=assessment.findings)
    result = run(requalify((donor, dn, (bounded, *rn[1:]), profile, evidence, register)))
    assert result.candidate is not None
    sample = result.candidate.classes[0].samples[0]
    assert sample.value == Flow(3)
    assert sample.uncertainty is None
    assert sample.components[0].uncertainty == bounded_samples[0].uncertainty
    floor = presumptive_floor(bounded, profile_for(bounded))
    assert floor.samples[0].value == Flow(Fraction(6, 5))
    assert floor.samples[0].uncertainty is None
    assert floor.samples[0].components == (bounded_samples[0],)


def unavailable_pattern(reference):
    from fishy.daily_patterns import construct_pattern

    return construct_pattern(
        reference.magnitude,
        reference.calendar,
        (),
        None,
        intended_use=reference.requested_use,
        purpose=reference.purpose,
        magnitude_assessment=reference.magnitude_assessment,
    )


def test_presumptive_native_unavailable_reference(inputs):
    reference = inputs[2][0]
    unavailable = unavailable_pattern(reference)
    result = presumptive_floor(unavailable, profile_for(reference))
    assert result.samples == result.fractions == ()
    assert result.reference == unavailable
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)
    assert any("pattern profile missing" in r for c in result.checks.checks for r in c.reasons)
    assert presumptive_reference_identity(unavailable) != presumptive_reference_identity(reference)
    assert presumptive_reference_identity(unavailable) == presumptive_reference_identity(unavailable_pattern(reference))


@pytest.mark.parametrize("side", ["donor", "recipient"])
def test_transfer_native_unavailable_pattern(inputs, side):
    donor, dn, rn, profile, evidence, register = inputs
    if side == "donor":
        dn = (unavailable_pattern(dn[0]), *dn[1:])
    else:
        rn = (unavailable_pattern(rn[0]), *rn[1:])
    result = run((donor, dn, rn, profile, evidence, register))
    assert result.candidate is None
    assert result.mappings == ()
    assert result.register == register
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)
    assert any("pattern profile missing" in r for c in result.checks.checks for r in c.reasons)
    assert transfer_scope(donor, dn, rn, profile) != evidence.scope
    # A freshly bound qualification cannot turn a missing numerical product into a candidate.
    assert run(requalify((donor, dn, rn, profile, evidence, register))).candidate is None


def test_native_unavailable_preserves_known_failure_and_fallback(inputs):
    from fishy.natural_routing import NaturalRoute, select_natural_route
    from fishy.spatial import DesignationState, Eligibility, Origin, PreparedClassification, UseCategory

    donor, dn, rn, profile, evidence, register = inputs
    zero = synthetic_pattern(
        "donor", donor.calendar, DesignClass.WET, (Fraction(), Fraction(12)) + (Fraction(8),) * 363
    )
    missing = (unavailable_pattern(rn[0]), *rn[1:])
    transfer = run((donor, (zero, *dn[1:]), missing, profile, evidence, register))
    assert transfer.candidate is None
    assert transfer.checks.finding is CheckFinding.FAIL
    assert any("zero donor denominator" in r for c in transfer.checks.checks for r in c.reasons)
    assert any(c.finding is CheckFinding.UNKNOWN for c in transfer.checks.checks)
    classification = PreparedClassification(
        Origin.NATURAL,
        DesignationState.NONE,
        Eligibility.NOT_APPLICABLE,
        UseCategory.AGRICULTURE_IRRIGATION,
        ("irrigation",),
        "synthetic natural origin",
        "v1",
    )
    floor = presumptive_floor(rn[0], profile_for(rn[0]))
    assert (
        select_natural_route(classification, (), transfer=transfer, presumptive=floor).selected
        is NaturalRoute.PRESUMPTIVE
    )
    unavailable_floor = presumptive_floor(missing[0], profile_for(rn[0]))
    assert (
        select_natural_route(classification, (), transfer=transfer, presumptive=unavailable_floor).selected
        is NaturalRoute.PENDING
    )


@pytest.mark.parametrize("side", ["donor", "recipient"])
def test_transfer_rejects_mixed_reference_family(inputs, side):
    donor, dn, rn, profile, evidence, register = inputs
    altered = synthetic_pattern(side, donor.calendar, DesignClass.WET, (Fraction(100),) * 365)
    if side == "donor":
        dn = (altered, *dn[1:])
    else:
        rn = (altered, *rn[1:])
    family = dn if side == "donor" else rn
    assert len({p.magnitude.reference_identity for p in family}) == 2
    assert all(p.use_checks.finding is CheckFinding.PASS for p in family)
    result = run(requalify((donor, dn, rn, profile, evidence, register)))
    assert result.candidate is None
    assert result.checks.finding is CheckFinding.FAIL
    assert any("reference identity" in r for c in result.checks.checks for r in c.reasons)


def test_unavailable_identity_does_not_create_numerical_product(inputs):
    from fishy.daily_patterns import pattern_product

    unavailable = unavailable_pattern(inputs[2][0])
    assert unavailable.samples == ()
    assert unavailable.shape is None
    with pytest.raises(ValueError, match="no numerical daily product"):
        pattern_product(unavailable, intended_use=unavailable.requested_use, purpose=unavailable.purpose)
    with pytest.raises(ValueError, match="cannot assert a shape"):
        replace(unavailable, shape=(Fraction(1),))
    with pytest.raises(TypeError, match="daily reference"):
        presumptive_floor("malformed", profile_for(inputs[2][0]))  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="DailyPattern families"):
        run((inputs[0], list(inputs[1]), *inputs[2:]))
