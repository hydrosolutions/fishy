"""U7: supported spatial composition and the complete natural-floor invariant."""

from dataclasses import replace
from fractions import Fraction

from test_requirement_family import family

from examples.requirement_chain import (
    TARGET,
    final_assessment,
    lateral,
    provenance,
    quality,
    samples,
)
from examples.requirement_chain import (
    accepted_evidence as evidence,
)
from fishy.design_conditions import DesignClass
from fishy.evidence import CheckFinding
from fishy.natural_floor import natural_floor
from fishy.quality_activation import QualityRoute
from fishy.quantities import Flow
from fishy.receptor_delivery import WaterRelationship, delivery_scope
from fishy.requirement_checks import FinalCondition, assess_requirement, sample_subject
from fishy.requirement_composition import compose_requirement


def test_final_95_minimum_crosses_other_class_declines_without_repair():
    values: dict[DesignClass, int | tuple[int, ...]] = dict.fromkeys(DesignClass, 7)
    values[DesignClass.DRY] = 2
    values[DesignClass.WET] = (1,) + (7,) * 365
    f = family("A", values)
    result = natural_floor(f)
    assert result.candidate == Flow(2)
    assert len(result.crossings) == 1
    assert result.crossings[0].design is DesignClass.WET
    assert result.crossings[0].shortfall == Flow(1)
    assert result.check.finding is CheckFinding.FAIL
    assert f.samples(DesignClass.WET)[0].value == Flow(1)


def test_floor_minimum_uses_entire_final_year_not_summer():
    values: dict[DesignClass, int | tuple[int, ...]] = dict.fromkeys(DesignClass, 8)
    values[DesignClass.DRY] = (2,) + (8,) * 365
    result = natural_floor(family("A", values))
    assert result.candidate == Flow(2)
    assert result.attaining_intervals[0].start.month == 1
    assert result.check.finding is CheckFinding.PASS


def test_same_water_max_and_lateral_signed_balance():
    base = samples(TARGET, 3, "A")[0]
    mapped = lateral(Flow(3), base.interval, "A", "synthetic")
    mapping = replace(mapped.mapping, receptor=Flow(2))
    # Existing control_equivalent binds acceptance to the exact changed mapping.
    lateral_e = evidence(delivery_scope(mapping.context, mapping), provenance("A"))
    out = compose_requirement(base, provenance("A"), mapping=mapping, mapping_evidence=lateral_e)
    assert out.candidate is not None
    assert out.candidate.value == Flow(5)
    shared = replace(mapping, relationship=WaterRelationship.SAME_WATER)
    out = compose_requirement(
        base,
        provenance("A"),
        mapping=shared,
        mapping_evidence=evidence(delivery_scope(shared.context, shared), provenance("A")),
    )
    assert out.candidate is not None
    assert out.candidate.value == Flow(3)


def test_missing_mapping_keeps_separate_requirements_visible():
    base = samples(TARGET, 3, "A")[0]
    mapping = lateral(Flow(3), base.interval, "A", "synthetic").mapping
    result = compose_requirement(base, provenance("A"), mapping=mapping)
    assert result.candidate is None
    assert result.base.value == Flow(3)
    assert result.mapping is not None
    assert result.mapping.mapping.receptor == Flow(1)
    assert result.checks.finding is CheckFinding.UNKNOWN


def test_active_quality_survives_direct_floor_and_no_requirement_is_created():
    base = samples(TARGET, 3, "A")[0]
    q = quality(Flow(3), base.interval, "A", route=QualityRoute.FLOOR_ONLY)
    result = compose_requirement(base, provenance("A"), quality=q)
    assert result.candidate is not None
    assert result.candidate.value == Flow(9)
    assert q.floor == Flow(9)
    assert q.requirement is None


def test_recheck_candidate_binding_and_all_actual_physical_operators():
    sample = samples(TARGET, 12, "selected", section="U")[0]
    result = final_assessment(sample)
    assert result.checks.finding is CheckFinding.PASS
    assert result.quality.total == Flow(11)
    assert result.mapping.upstream == Flow(12)
    assert result.receptor.checks.finding is CheckFinding.PASS
    assert result.hydraulics.finding is CheckFinding.PASS
    assert result.study.supported_flow == Flow(12)
    assert sample_subject(replace(sample, value=Flow(13))) != sample_subject(sample)


def test_known_quality_failure_survives_missing_hydraulics():
    sample = samples(TARGET, 12, "selected")[0]
    q = quality(Flow(9), sample.interval, "selected", source_concentration=Fraction(2))
    result = assess_requirement(sample, (FinalCondition.QUALITY, FinalCondition.HYDRAULICS), quality=q)
    assert result.quality is not None
    assert result.quality.outcome.value == "fail"
    assert result.checks.finding is CheckFinding.FAIL
    assert any(c.finding is CheckFinding.UNKNOWN for c in result.checks.checks)


def test_empty_final_conditions_cannot_pass():
    sample = samples(TARGET, 12, "selected", section="U")[0]
    assert assess_requirement(sample, ()).checks.finding is CheckFinding.UNKNOWN


def test_same_water_uplift_rechecks_quality_at_actual_shared_flow_not_old_lower_bound():
    from dataclasses import replace

    from fishy.mixing import CheckOutcome
    from fishy.quality import Comparison
    from fishy.receptor_delivery import control_equivalent

    sample = samples(TARGET, 10, "selected", section="U")[0]
    q = quality(Flow(9), sample.interval, "selected")
    target = q.quality.targets[0]
    lower = replace(target, identifier="minimum-concentration", operator=Comparison.GE)
    q = replace(q, quality=replace(q.quality, targets=(target, lower)))
    raw = lateral(Flow(9), sample.interval, "selected", sample_subject(sample)).mapping
    raw = replace(raw, relationship=WaterRelationship.SAME_WATER, receptor=Flow(10))
    mapped = control_equivalent(raw, evidence(delivery_scope(raw.context, raw), raw.context.provenance))
    result = assess_requirement(sample, (FinalCondition.QUALITY, FinalCondition.MAPPING), quality=q, mapping=mapped)
    assert result.quality is not None
    assert result.quality.total == Flow(10)
    assert result.quality.outcome is CheckOutcome.FAIL
    assert result.checks.finding is CheckFinding.FAIL
