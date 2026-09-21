"""Typed source/composition proof for supported qualified-transfer families."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from examples.ecological_transfer import synthetic_inputs
from examples.requirement_chain import accepted_evidence
from fishy.ecological_transfer import TransferResult, transfer_ecological_regime
from fishy.evidence import CheckFinding
from fishy.pattern_calendar import AccountingYear
from fishy.quantities import Flow
from fishy.requirement_composition import compose_requirement
from fishy.requirement_construction import ClassComposition, MemberConstruction, NaturalRouteInputs, assess_construction
from fishy.requirement_family import (
    ClassRequirement,
    FamilyBasis,
    RequirementFamily,
    RequirementMember,
    candidate_scope,
)


@pytest.fixture(scope="module")
def transfer_construction():
    source = transfer_ecological_regime(
        *synthetic_inputs(AccountingYear(2023, 1, 0)), evaluated_at=datetime(2026, 9, 5, tzinfo=UTC)
    )
    candidate = source.candidate
    assert candidate is not None
    assert candidate.provenance.reference_kind is not None
    assert candidate.provenance.reference_member is not None
    compositions = tuple(
        ClassComposition(c.design, compose_requirement(s, s.provenance)) for c in candidate.classes for s in c.samples
    )
    family = RequirementFamily(
        FamilyBasis(
            candidate.location,
            candidate.calendar.interval,
            candidate.provenance.scenario,
            candidate.method.value,
            candidate.provenance.configuration_version,
            "inactive-quality",
            candidate.provenance.reference_kind,
        ),
        tuple(
            ClassRequirement(
                c.design,
                tuple(
                    sample
                    for comp in compositions
                    if comp.design is c.design and (sample := comp.result.candidate) is not None
                ),
            )
            for c in candidate.classes
        ),
    )
    member = RequirementMember(
        candidate.provenance.reference_member,
        "recipient reconstruction",
        family,
        accepted_evidence(candidate_scope(family), family.classes[0].samples[0].provenance),
        "donor relationship uncertainty retained",
    )
    from test_natural_routing import natural

    return member, MemberConstruction(
        member.identifier, source, compositions, NaturalRouteInputs(candidate.location, natural(), ())
    )


def test_actual_qualified_transfer_recomputed_from_its_original_inputs(transfer_construction):
    member, construction = transfer_construction
    result = assess_construction(member, construction)
    assert result.checks.finding is CheckFinding.PASS
    assert isinstance(result.recomputed_source, TransferResult)
    assert result.recomputed_source.candidate == construction.source.candidate
    assert len(result.compositions) == 4 * 365
    assert result.compositions[0].result.candidate is not None
    assert result.compositions[0].result.candidate.value == Flow(3)
    assert result.compositions[1].result.candidate is not None
    assert result.compositions[1].result.candidate.value == Flow(5)


def test_changed_transfer_source_does_not_reuse_final_acceptance(transfer_construction):
    member, construction = transfer_construction
    changed = replace(construction.source, qualification=None)
    result = assess_construction(member, replace(construction, source=changed))
    assert result.checks.finding is CheckFinding.FAIL
    assert isinstance(result.recomputed_source, TransferResult)
    assert result.recomputed_source.candidate is None


def test_relabelled_method_cannot_replace_actual_source(transfer_construction):
    member, construction = transfer_construction
    wrong = replace(
        member, candidate=replace(member.candidate, basis=replace(member.candidate.basis, method="natural_study"))
    )
    with pytest.raises(ValueError, match="actual typed source"):
        assess_construction(wrong, construction)
