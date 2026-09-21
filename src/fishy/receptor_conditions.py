"""assess_receptor_conditions : DeliveryStep × FlowSample × DeliveryAssessment? × ControlEquivalent? → ReceptorConditionAssessment.

Original receptor goals and physical accounts constrain the exact final candidate.
Native source evidence stays attached to its original scope; fresh acceptance is
required for the final schedule. No state inversion or new pathway allocation occurs.
"""

from dataclasses import dataclass

from fishy.evidence import Check, CheckFinding, CheckSummary
from fishy.flows import Coverage, FlowSample, Presence
from fishy.receptor_delivery import (
    BoundInclusion,
    ControlEquivalent,
    DeliveryAssessment,
    DeliveryStep,
    ProcessTest,
    WaterExchange,
    WaterRelationship,
    assess_delivery,
    control_equivalent,
)
from fishy.requirement_checks import sample_subject


@dataclass(frozen=True)
class ReceptorConditionAssessment:
    source: DeliveryStep
    final: FlowSample
    supplied: DeliveryAssessment | None
    mapping: ControlEquivalent | None
    original: DeliveryAssessment
    recomputed: DeliveryAssessment | None
    constraints: tuple[Check, ...]
    checks: CheckSummary


def _comparison(identifier: str, condition: bool, reason: str) -> Check:
    return Check(identifier, CheckFinding.PASS if condition else CheckFinding.FAIL, (reason,))


def _exchange_identity(exchanges: tuple[WaterExchange, ...]):
    return tuple(
        (x.carrier, x.direction, x.amount, x.other_location)
        for x in sorted(exchanges, key=lambda exchange: exchange.carrier)
    )


def _process_constraints(identifier: str, original: ProcessTest, fresh: ProcessTest, supported: CheckFinding):
    same_domain = (original.identifier, original.variable, original.units, original.reference, original.source) == (
        fresh.identifier,
        fresh.variable,
        fresh.units,
        fresh.reference,
        fresh.source,
    )
    checks = [
        _comparison(
            identifier + ":domain", same_domain, "original variable, units, physical basis and relation remain binding"
        )
    ]
    lower = original.lower is None or fresh.lower is not None and fresh.lower >= original.lower
    upper = original.upper is None or fresh.upper is not None and fresh.upper <= original.upper
    boundary = original.boundary is BoundInclusion.INCLUSIVE or fresh.boundary is BoundInclusion.STRICT
    # Inclusive endpoints are safe only when the fresh bound is strictly tighter.
    if not boundary:
        boundary = (original.lower is None or fresh.lower is not None and fresh.lower > original.lower) and (
            original.upper is None or fresh.upper is not None and fresh.upper < original.upper
        )
    checks.append(
        _comparison(
            identifier + ":criterion",
            lower and upper and boundary,
            "fresh criteria cannot remove or relax original state/salinity bounds",
        )
    )
    finding = CheckFinding.UNKNOWN
    if same_domain and fresh.value is not None and supported is not CheckFinding.UNKNOWN:
        strict = original.boundary is BoundInclusion.STRICT
        passed = (
            original.lower is None or (fresh.value > original.lower if strict else fresh.value >= original.lower)
        ) and (original.upper is None or (fresh.value < original.upper if strict else fresh.value <= original.upper))
        finding = CheckFinding.PASS if passed else CheckFinding.FAIL
    checks.append(
        Check(
            identifier + ":original_value",
            finding,
            ("fresh supported state evaluated against original criterion; original evidence is not relabelled",),
        )
    )
    return checks


def assess_receptor_conditions(
    source: DeliveryStep,
    final: FlowSample,
    supplied: DeliveryAssessment | None,
    mapping: ControlEquivalent | None,
) -> ReceptorConditionAssessment:
    """Recompute native physics and retain all original goals after final uplift.

    Storage targets are exact selected endpoints in the native API, not inferred
    lower bounds. Initial water, named exchanges, losses and pathway inventories
    cannot be replaced to reduce the original water need. A changed physical
    relationship requires a separate supported contract, not an identity relabel.
    """
    if not isinstance(source, DeliveryStep) or not isinstance(final, FlowSample):
        raise TypeError("actual original DeliveryStep and final FlowSample required")
    if supplied is not None and not isinstance(supplied, DeliveryAssessment):
        raise TypeError("fresh receptor input must be a DeliveryAssessment")
    if mapping is not None and not isinstance(mapping, ControlEquivalent):
        raise TypeError("typed final control mapping required")
    original = assess_delivery((source,), period=source.balance.context.period)
    checks = [Check("original:" + c.check_id, c.finding, c.reasons) for c in original.checks.checks]
    constraints = [
        Check(
            "final_coverage",
            CheckFinding.PASS
            if final.presence is Presence.PRESENT and final.coverage is Coverage.COMPLETE and final.value is not None
            else CheckFinding.UNKNOWN,
            ("supported complete final control-flow value required",),
        )
    ]
    original_context = source.balance.context
    constraints.append(
        _comparison(
            "source_interval",
            original_context.period == final.interval,
            "no implicit change of receptor assessment interval",
        )
    )
    constraints.append(
        _comparison(
            "source_scenario",
            original_context.provenance.scenario == final.provenance.scenario,
            "source and final must share the physical scenario",
        )
    )
    if mapping is None:
        constraints.append(
            Check("mapping", CheckFinding.UNKNOWN, ("final receptor contribution needs its actual control mapping",))
        )
    else:
        mapped = control_equivalent(mapping.mapping, mapping.evidence)
        m = mapped.mapping
        exact = (m.control, m.context.period, m.context.candidate, m.context.receptor) == (
            final.location,
            final.interval,
            sample_subject(final),
            original_context.receptor,
        )
        exact = exact and all(
            getattr(m.context.provenance, f) == getattr(final.provenance, f)
            for f in (
                "scenario",
                "reference_member",
                "reference_kind",
                "configuration_version",
                "data_version",
                "software_version",
            )
        )
        constraints.append(
            _comparison(
                "mapping_identity", exact, "mapping must identify the exact final control, receiver and candidate"
            )
        )
        constraints.append(
            Check(
                "mapping",
                CheckFinding.UNKNOWN
                if mapped.upstream is None or final.value is None
                else CheckFinding.PASS
                if mapped.upstream == final.value
                else CheckFinding.FAIL,
                mapped.reasons or ("recomputed mapping must equal actual final flow",),
            )
        )
    recomputed = None
    if supplied is None or not supplied.steps:
        constraints.append(
            Check("final_schedule", CheckFinding.UNKNOWN, ("fresh final receptor schedule/evidence missing",))
        )
    elif len(supplied.steps) != 1:
        constraints.append(
            Check("final_schedule", CheckFinding.UNKNOWN, ("one exact matching daily receptor step required",))
        )
    else:
        fresh = supplied.steps[0].step
        context = fresh.balance.context
        exact = (context.receptor, context.period, context.candidate, context.domain) == (
            original_context.receptor,
            final.interval,
            sample_subject(final),
            original_context.domain,
        )
        exact = exact and all(
            getattr(context.provenance, f) == getattr(final.provenance, f)
            for f in (
                "scenario",
                "reference_member",
                "reference_kind",
                "configuration_version",
                "data_version",
                "software_version",
            )
        )
        constraints.append(
            _comparison(
                "final_identity",
                exact,
                "fresh native assessment must bind exact final sample and original receptor domain",
            )
        )
        recomputed = assess_delivery((fresh,), period=context.period)
        checks.extend(Check("final:" + c.check_id, c.finding, c.reasons) for c in recomputed.checks.checks)
        current = recomputed.steps[0]
        native = {c.check_id: c.finding for c in current.checks.checks}
        constraints.append(
            _comparison(
                "storage_initial",
                source.balance.initial == fresh.balance.initial,
                "original initial water inventory remains fixed",
            )
        )
        constraints.append(
            _comparison(
                "storage_exchanges",
                _exchange_identity(source.balance.exchanges) == _exchange_identity(fresh.balance.exchanges),
                "named source exchanges and destinations remain fixed; a drain cannot vanish",
            )
        )
        constraints.append(
            _comparison(
                "storage_relation",
                (source.balance.relation, source.balance.uncertainty)
                == (fresh.balance.relation, fresh.balance.uncertainty),
                "original supported storage relation and uncertainty remain fixed",
            )
        )
        if source.state_objective is None:
            if source.balance.target is not None:
                constraints.append(
                    _comparison(
                        "objective_kind",
                        fresh.state_objective is None,
                        "a selected storage target cannot be replaced by a different state objective",
                    )
                )
            if source.balance.target is None or fresh.balance.target is None:
                constraints.append(
                    Check("storage_target", CheckFinding.UNKNOWN, ("original and final storage targets required",))
                )
            else:
                constraints.append(
                    _comparison(
                        "storage_target",
                        source.balance.target == fresh.balance.target,
                        "native storage target is an exact endpoint, not a newly chosen lower target",
                    )
                )
                constraints.append(
                    Check(
                        "original_storage_value",
                        CheckFinding.UNKNOWN
                        if current.final_storage is None
                        else CheckFinding.PASS
                        if current.final_storage == source.balance.target
                        else CheckFinding.FAIL,
                        ("fresh physical storage rechecked against original target",),
                    )
                )
        else:
            old = source.state_objective
            new = fresh.state_objective
            if new is None:
                constraints.append(
                    Check("state_objective", CheckFinding.UNKNOWN, ("original coupled-state objective missing",))
                )
            else:
                fields = (
                    "relation",
                    "boundary_conditions",
                    "uncertainty",
                    "required_temporal_support",
                    "expected_intervals",
                    "required_salinity",
                    "salinity_domain",
                    "salinity_support",
                )
                constraints.append(
                    _comparison(
                        "state_relation",
                        all(getattr(old, f) == getattr(new, f) for f in fields),
                        "original quantity/salinity representation, domain and temporal criteria remain fixed",
                    )
                )
                constraints.append(
                    _comparison(
                        "state_temporal_support",
                        new.temporal_support is old.required_temporal_support,
                        "fresh state must cover original required temporal statistic",
                    )
                )
                constraints.extend(
                    _process_constraints(
                        "quantity",
                        old.quantity.test,
                        new.quantity.test,
                        native.get("quantity:" + new.quantity.test.identifier, CheckFinding.UNKNOWN),
                    )
                )
        old_paths = {p.pathway.identifier: p for p in source.pathways}
        new_paths = {p.pathway.identifier: p for p in fresh.pathways}
        for identifier in source.required_pathways:
            label = "pathway:" + identifier
            old = old_paths.get(identifier)
            new = new_paths.get(identifier)
            if old is None or new is None or identifier not in fresh.required_pathways:
                constraints.append(
                    Check(label, CheckFinding.UNKNOWN, ("original required pathway or its fresh input missing",))
                )
                continue
            a, b = old.pathway, new.pathway
            fixed = (
                "control",
                "release_period",
                "travel_time",
                "initial_storage",
                "final_storage",
                "predecessor",
                "predecessor_period",
                "relation",
                "boundary_conditions",
                "uncertainty",
            )
            constraints.append(
                _comparison(
                    label + ":relation",
                    all(getattr(a, f) == getattr(b, f) for f in fixed)
                    and _exchange_identity(a.losses) == _exchange_identity(b.losses),
                    "original pathway relation, inventories, named losses and predecessor remain fixed",
                )
            )
            constraints.append(
                _comparison(
                    label + ":domain",
                    b.minimum_release.value >= a.minimum_release.value
                    and b.capacity.value <= a.capacity.value
                    and b.rise_m3_s2 <= a.rise_m3_s2
                    and b.fall_m3_s2 <= a.fall_m3_s2,
                    "fresh release domain and ramp criteria cannot relax original limits",
                )
            )
            q = new.release.value / a.release_period.seconds
            rate = (q - a.predecessor.value) / a.release_period.seconds
            supported = native.get(identifier + ":capacity", CheckFinding.UNKNOWN) is not CheckFinding.UNKNOWN
            for suffix, valid in (
                ("original_domain", a.minimum_release.value <= q <= a.capacity.value),
                ("original_ramping", -a.fall_m3_s2 <= rate <= a.rise_m3_s2),
            ):
                constraints.append(
                    Check(
                        label + ":" + suffix,
                        CheckFinding.UNKNOWN if not supported else CheckFinding.PASS if valid else CheckFinding.FAIL,
                        ("fresh release evaluated with original domain and ramp limits",),
                    )
                )
        old_processes = {p.test.identifier: p for p in source.processes}
        new_processes = {p.test.identifier: p for p in fresh.processes}
        for identifier in source.required_processes:
            old = old_processes.get(identifier)
            new = new_processes.get(identifier)
            if old is None or new is None or identifier not in fresh.required_processes:
                constraints.append(
                    Check("process:" + identifier, CheckFinding.UNKNOWN, ("original required process input missing",))
                )
            else:
                constraints.extend(
                    _process_constraints(
                        "process:" + identifier,
                        old.test,
                        new.test,
                        native.get("process:" + identifier, CheckFinding.UNKNOWN),
                    )
                )
        if mapping is not None:
            m = mapping.mapping
            paths = tuple(
                p
                for p in fresh.pathways
                if p.pathway.control == final.location and p.pathway.release_period == final.interval
            )
            actual = sum(p.release.value / p.pathway.release_period.seconds for p in paths)
            expected = final.value if m.relationship is WaterRelationship.SAME_WATER else m.receptor
            complete = bool(source.required_pathways) and set(source.required_pathways) <= set(new_paths)
            constraints.append(
                Check(
                    "mapped_release",
                    CheckFinding.UNKNOWN
                    if not complete or expected is None
                    else CheckFinding.PASS
                    if actual == expected.value
                    else CheckFinding.FAIL,
                    ("same-water carries full final flow; lateral carries mapped diversion; missing is not zero",),
                )
            )
    checks.extend(constraints)
    return ReceptorConditionAssessment(
        source, final, supplied, mapping, original, recomputed, tuple(constraints), CheckSummary(tuple(checks))
    )
