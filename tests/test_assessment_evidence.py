"""acceptance : ScopedEvidence × SuppliedDuty → RestrictedPartialAssessment."""

from dataclasses import replace

from test_duties import duty, samples

from fishy.duties import Delivery, assess_duty
from fishy.evidence import (
    Check,
    CheckFinding,
    Completeness,
    Computability,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ScientificAdequacy,
    UseRestriction,
    aggregate_checks,
    permitted_use,
)
from fishy.quantities import Volume


def test_supported_annual_output_does_not_manufacture_complete_regime_or_erase_restriction():
    sample = samples((3,))[0]
    scope = EvidenceScope("annual mean", sample.location.reach.identifier, None, sample.interval, "annual screen")
    evidence = EvidenceFindings(
        scope,
        sample.provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("short record supports stated limited use",),
        (UseRestriction("rating range excludes daily sizing", ("daily sizing",)),),
    )
    assert permitted_use(evidence, scope).finding is CheckFinding.PASS
    different_use = replace(scope, intended_use="daily sizing")
    assert permitted_use(evidence, different_use).finding is CheckFinding.UNKNOWN
    explicitly_sized = replace(evidence, scope=different_use)
    assert permitted_use(explicitly_sized, different_use).finding is CheckFinding.FAIL
    partial = aggregate_checks(
        ("annual mean", "daily regime", "quality", "receptor"), (Check("annual mean", CheckFinding.PASS),)
    )
    assert partial.finding is CheckFinding.UNKNOWN
    assert partial.completeness is Completeness.INCOMPLETE
    assert evidence.official_admissibility is OfficialAdmissibility.PENDING


def test_supplied_evidence_gate_preserves_numeric_shortfall_and_required_coverage():
    sample = samples((1,))[0]
    scope = EvidenceScope("delivery", sample.location.reach.identifier, None, sample.interval, "delivery assessment")
    evidence = EvidenceFindings(
        scope,
        sample.provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.NOT_ACCEPTED,
        OfficialAdmissibility.PENDING,
        ("rating extrapolation not accepted",),
    )
    result = assess_duty(
        duty((2,), required_components=("discharge", "permitted_use", "velocity")),
        (Delivery(sample, "1"),),
        component_checks=(permitted_use(evidence, scope),),
    )
    assert result.known_shortfall_volume == Volume(86400)
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert "rating extrapolation not accepted" in result.summary.checks[1].reasons
