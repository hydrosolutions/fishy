"""Public evidence contracts: attribution, independent findings, required coverage."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from fishy.duties import Delivery, DutyApplicability, Obligation, SuppliedDuty, assess_duty
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
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
    ReferenceKind,
    ScientificAdequacy,
    UseRestriction,
    aggregate_checks,
    permitted_use,
)
from fishy.flows import FlowSample, Presence
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


@pytest.fixture
def period() -> Interval:
    return Interval(datetime(2024, 2, 29, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC))


@pytest.fixture
def provenance(period: Interval) -> Provenance:
    return Provenance(
        source="station release 2",
        scenario="managed",
        reference_member="reference-A",
        software_version="revision-1",
        data_version="data-2",
        configuration_version="configuration-3",
        production_method=ProductionMethod.RECONSTRUCTED,
        correction_state=CorrectionState.INFILLED,
        reference_kind=ReferenceKind.PRESENT_CLIMATE_NATURAL,
        dependencies=("shared rating curve",),
        limitations=("outside rating range",),
        excluded_warmup=(period,),
        predecessor_sources=("previous-year-release",),
    )


def test_provenance_is_immutable_and_scenario_changes_preserve_original(provenance: Provenance) -> None:
    revised = replace(provenance, scenario="alternative", configuration_version="configuration-4")
    assert provenance.scenario == "managed"
    assert revised.source == provenance.source
    assert revised.dependencies == ("shared rating curve",)
    assert revised.predecessor_sources == ("previous-year-release",)
    assert revised.production_method is ProductionMethod.RECONSTRUCTED
    assert revised.correction_state is CorrectionState.INFILLED
    with pytest.raises(FrozenInstanceError):
        provenance.scenario = "changed"  # ty: ignore[invalid-assignment]


@pytest.mark.parametrize("kind", list(ReferenceKind))
def test_reference_meanings_remain_distinct(provenance: Provenance, kind: ReferenceKind) -> None:
    assert replace(provenance, reference_kind=kind).reference_kind is kind


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", ""),
        ("scenario", " "),
        ("software_version", ""),
        ("reference_member", ""),
        ("correction_state", "original"),
        ("production_method", "observed"),
        ("reference_kind", "managed"),
        ("dependencies", ["mutable"]),
        ("excluded_warmup", []),
    ],
)
def test_invalid_provenance_rejected(provenance: Provenance, field: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(provenance, **{field: value})


@pytest.mark.parametrize(
    "states,expected,complete",
    [
        ((CheckFinding.PASS, CheckFinding.PASS), CheckFinding.PASS, Completeness.COMPLETE),
        ((CheckFinding.FAIL, CheckFinding.UNKNOWN), CheckFinding.FAIL, Completeness.INCOMPLETE),
        ((CheckFinding.PASS, CheckFinding.UNKNOWN), CheckFinding.UNKNOWN, Completeness.INCOMPLETE),
        ((CheckFinding.FAIL, CheckFinding.PASS), CheckFinding.FAIL, Completeness.COMPLETE),
    ],
)
def test_required_checks_preserve_failure_and_coverage(
    states: tuple[CheckFinding, CheckFinding],
    expected: CheckFinding,
    complete: Completeness,
) -> None:
    checks = (Check("R1/flow", states[0]), Check("R2/quality/group-member", states[1]))
    result = aggregate_checks(("R1/flow", "R2/quality/group-member"), checks)
    assert result.finding is expected
    assert result.completeness is complete
    assert result.checks == checks


@pytest.mark.parametrize("omitted", ["R2/flow", "R1/quality/sodium", "R1/daily-pattern"])
def test_omitted_reach_group_member_or_product_remains_unknown(omitted: str) -> None:
    result = aggregate_checks(("R1/annual-mean", omitted), (Check("R1/annual-mean", CheckFinding.PASS),))
    assert result.finding is CheckFinding.UNKNOWN
    assert result.completeness is Completeness.INCOMPLETE
    assert result.checks[1] == Check(omitted, CheckFinding.UNKNOWN, ("required check not supplied",))


def test_known_failure_survives_omission_and_preserves_reason() -> None:
    failed = Check("flow", CheckFinding.FAIL, ("delivery below supplied duty",))
    result = aggregate_checks(("flow", "quality"), (failed,))
    assert result.finding is CheckFinding.FAIL
    assert result.completeness is Completeness.INCOMPLETE
    assert result.checks[0] == failed


def test_empty_expected_set_cannot_pass() -> None:
    result = aggregate_checks((), ())
    assert result.finding is CheckFinding.UNKNOWN
    assert result.completeness is Completeness.INCOMPLETE


@pytest.mark.parametrize(
    "expected,checks",
    [
        (("flow", "flow"), ()),
        (("flow",), (Check("flow", CheckFinding.PASS), Check("flow", CheckFinding.FAIL))),
        (("flow",), (Check("undeclared", CheckFinding.PASS),)),
        ((), (Check("flow", CheckFinding.PASS),)),
    ],
)
def test_duplicate_and_undeclared_checks_rejected(expected: tuple[str, ...], checks: tuple[Check, ...]) -> None:
    with pytest.raises(ValueError):
        aggregate_checks(expected, checks)


def test_summary_rejects_mutable_checks() -> None:
    with pytest.raises(TypeError):
        CheckSummary([])  # ty: ignore[invalid-argument-type]


def test_scientific_acceptance_does_not_grant_official_admissibility(
    period: Interval,
    provenance: Provenance,
) -> None:
    scope = EvidenceScope("annual mean", "reach-1", "reference-A", period, "annual-volume screen")
    evidence = EvidenceFindings(
        scope,
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("independent study supports annual use", "authority decision pending"),
    )
    assert evidence.scientific_adequacy is ScientificAdequacy.ACCEPTED
    assert evidence.official_admissibility is OfficialAdmissibility.PENDING
    daily = replace(
        evidence,
        scope=replace(scope, product="daily minimum", intended_use="sizing"),
        scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED,
        reasons=("daily equivalence unsupported",),
    )
    assert daily.numerical_validity is NumericalValidity.VALID
    assert evidence.scope.product == "annual mean"
    assert daily.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED


def test_indicative_evidence_retains_reason_specific_sizing_prohibition(
    period: Interval,
    provenance: Provenance,
) -> None:
    restriction = UseRestriction("rating extrapolation unsupported", ("sizing",))
    result = EvidenceFindings(
        EvidenceScope("annual mean", "reach-1", None, period, "screening"),
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.NOT_ADMISSIBLE,
        ("short record supports screening only",),
        (restriction,),
    )
    assert result.restrictions == (restriction,)
    assert result.scope.intended_use == "screening"
    with pytest.raises(FrozenInstanceError):
        result.restrictions = ()  # ty: ignore[invalid-assignment]


def test_use_restriction_requires_reason_and_prohibited_use() -> None:
    with pytest.raises(ValueError):
        UseRestriction("", ("sizing",))
    with pytest.raises(ValueError):
        UseRestriction("unsupported", ())


@pytest.fixture
def accepted_evidence(period: Interval, provenance: Provenance) -> EvidenceFindings:
    return EvidenceFindings(
        EvidenceScope("annual mean", "reach-1", "reference-A", period, "screening"),
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("supported screening",),
    )


@pytest.mark.parametrize("status", [ScientificAdequacy.ACCEPTED, ScientificAdequacy.ACCEPTED_AS_INDICATIVE])
def test_permitted_scientific_use_does_not_need_official_promotion(
    accepted_evidence: EvidenceFindings,
    status: ScientificAdequacy,
) -> None:
    evidence = replace(accepted_evidence, scientific_adequacy=status)
    assert permitted_use(evidence, evidence.scope).finding is CheckFinding.PASS
    assert evidence.official_admissibility is OfficialAdmissibility.PENDING


@pytest.mark.parametrize(
    "field,value",
    [
        ("product", "daily minimum"),
        ("reach", "reach-2"),
        ("member", "reference-B"),
        ("intended_use", "sizing"),
        ("period", Interval(datetime(2023, 1, 1, tzinfo=UTC), datetime(2023, 1, 2, tzinfo=UTC))),
    ],
)
def test_permission_never_transfers_across_scope(
    accepted_evidence: EvidenceFindings,
    field: str,
    value: object,
) -> None:
    scope = replace(accepted_evidence.scope, **{field: value})
    assert permitted_use(accepted_evidence, scope).finding is CheckFinding.UNKNOWN
    invalid = replace(accepted_evidence, numerical_validity=NumericalValidity.INVALID)
    assert permitted_use(invalid, scope).finding is CheckFinding.UNKNOWN


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("computability", Computability.NOT_COMPUTABLE, CheckFinding.FAIL),
        ("numerical_validity", NumericalValidity.INVALID, CheckFinding.FAIL),
        ("scientific_adequacy", ScientificAdequacy.NOT_ACCEPTED, CheckFinding.FAIL),
        ("computability", Computability.UNKNOWN, CheckFinding.UNKNOWN),
        ("numerical_validity", NumericalValidity.UNKNOWN, CheckFinding.UNKNOWN),
        ("scientific_adequacy", ScientificAdequacy.UNKNOWN, CheckFinding.UNKNOWN),
    ],
)
def test_permission_enforces_scope_specific_evidence(
    accepted_evidence: EvidenceFindings,
    field: str,
    value: object,
    expected: CheckFinding,
) -> None:
    evidence = replace(accepted_evidence, **{field: value})
    assert permitted_use(evidence, evidence.scope).finding is expected


def test_restriction_blocks_indicative_use_even_with_unknown_checks(accepted_evidence: EvidenceFindings) -> None:
    evidence = replace(
        accepted_evidence,
        scientific_adequacy=ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        numerical_validity=NumericalValidity.UNKNOWN,
        restrictions=(UseRestriction("rating range prohibits this screen", ("screening",)),),
    )
    result = permitted_use(evidence, evidence.scope)
    assert result.finding is CheckFinding.FAIL
    assert "rating range prohibits this screen" in result.reasons


def test_unrelated_prohibition_does_not_block_supported_use(accepted_evidence: EvidenceFindings) -> None:
    evidence = replace(accepted_evidence, restrictions=(UseRestriction("no daily evidence", ("daily sizing",)),))
    assert permitted_use(evidence, evidence.scope).finding is CheckFinding.PASS


@pytest.mark.parametrize(
    "delivered,restricted,numerical,overall",
    [
        (3, False, CheckFinding.PASS, CheckFinding.PASS),
        (3, True, CheckFinding.PASS, CheckFinding.FAIL),
        (1, False, CheckFinding.FAIL, CheckFinding.FAIL),
    ],
)
def test_evidence_gate_and_real_duty_arithmetic_remain_independent(
    accepted_evidence: EvidenceFindings,
    delivered: int,
    restricted: bool,
    numerical: CheckFinding,
    overall: CheckFinding,
) -> None:
    evidence = replace(
        accepted_evidence,
        restrictions=(UseRestriction("rating range excludes screening", ("screening",)),) if restricted else (),
    )
    location = Location(
        Reach("reach-1", "v1", WaterBody("river", "v1")),
        CalculationSection("section", "v1"),
        "map-v1",
    )
    target = FlowSample(location, evidence.scope.period, Flow(2), Presence.PRESENT, evidence.provenance)
    actual = replace(target, value=Flow(delivered))
    duty = SuppliedDuty(
        "duty",
        "v1",
        "supplied discharge provision",
        DutyApplicability.HYPOTHETICAL,
        (Obligation(target, "v1"),),
        "supplied inventory",
        required_components=("discharge", "permitted_use"),
    )
    permission = permitted_use(evidence, evidence.scope)
    result = assess_duty(duty, (Delivery(actual, "delivery-v1"),), component_checks=(permission,))
    assert result.intervals[0].numerical.finding is numerical
    assert result.summary.finding is overall
    assert result.intervals[0].shortfall == Flow(max(0, 2 - delivered))
    assert result.summary.checks[-1] == permission
    assert evidence.official_admissibility is OfficialAdmissibility.PENDING
