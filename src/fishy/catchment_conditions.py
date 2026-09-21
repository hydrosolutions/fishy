"""propagate_indicator : DrainageNetwork × ReachOutlet × Indicator → ReachCondition (pure).

Prepared non-overlapping drainage topology replaces GIS, not the source area
weighting. Point classifications remain independently attributable.
"""

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import Completeness
from fishy.hydrological_condition import (
    MANUAL,
    AssessmentContext,
    AssessmentState,
    HydrologyClass,
    Indicator,
    IndicatorResult,
    Metric,
)
from fishy.quantities import Area, Flow, Volume


class IntermediateCondition(StrEnum):
    UNAFFECTED = "unaffected"
    UNASSESSED = "unassessed"


class ReachFeature(StrEnum):
    RIVER = "river"
    LAKE = "lake"


@dataclass(frozen=True)
class CatchmentNode:
    """Total catchment at a prepared section; upstream catchments are disjoint.

    affected_indicators declares the indicators assessed at this intervention,
    INCLUDING those with missing results. Other indicators continue upstream.
    local_condition describes only intermediate area, not all upstream area.
    """

    identifier: str
    context: AssessmentContext
    area: Area
    upstream: tuple[str, ...]
    affected_indicators: tuple[Indicator, ...]
    results: tuple[IndicatorResult, ...]
    local_condition: IntermediateCondition
    evidence: str
    feature: ReachFeature = ReachFeature.RIVER

    def __post_init__(self) -> None:
        for value in (self.identifier, self.evidence):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("catchment identity and evidence require nonempty text")
        if not isinstance(self.context, AssessmentContext) or not isinstance(self.area, Area):
            raise TypeError("catchment requires typed context and area")
        if self.area.value <= 0:
            raise ValueError("catchment area must be positive")
        if not isinstance(self.local_condition, IntermediateCondition) or not isinstance(self.feature, ReachFeature):
            raise TypeError("catchment condition and feature require domain enums")
        for values in (self.upstream, self.affected_indicators, self.results):
            if not isinstance(values, tuple):
                raise TypeError("catchment collections require tuples")
        if any(not isinstance(s, str) or not s.strip() for s in self.upstream):
            raise ValueError("upstream identifiers require text")
        if len(set(self.upstream)) != len(self.upstream) or self.identifier in self.upstream:
            raise ValueError("duplicate or self upstream relation")
        if any(not isinstance(i, Indicator) for i in self.affected_indicators):
            raise TypeError("affected indicators require Indicator")
        if len(set(self.affected_indicators)) != len(self.affected_indicators):
            raise ValueError("duplicate affected indicators")
        if any(not isinstance(r, IndicatorResult) for r in self.results):
            raise TypeError("point assessments require IndicatorResult")
        if len({r.indicator for r in self.results}) != len(self.results):
            raise ValueError("duplicate point indicator")
        if any(r.indicator not in self.affected_indicators or r.context != self.context for r in self.results):
            raise ValueError("point assessment must match its node context and declared indicators")
        if self.feature is ReachFeature.LAKE and self.results:
            raise ValueError("lakes are not classified as river reaches")


@dataclass(frozen=True)
class DrainageNetwork:
    nodes: tuple[CatchmentNode, ...]
    version: str
    evidence: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.nodes, tuple)
            or not self.nodes
            or any(not isinstance(n, CatchmentNode) for n in self.nodes)
        ):
            raise ValueError("drainage network requires immutable catchment nodes")
        if not all(isinstance(s, str) and s.strip() for s in (self.version, self.evidence)):
            raise ValueError("drainage network requires version and topology evidence")
        indexed = {n.identifier: n for n in self.nodes}
        if len(indexed) != len(self.nodes):
            raise ValueError("duplicate catchment node IDs")
        for node in self.nodes:
            if any(u not in indexed for u in node.upstream):
                raise ValueError("undeclared upstream node")
            if sum(indexed[u].area.value for u in node.upstream) > node.area.value:
                raise ValueError("upstream areas exceed receiving catchment")
            for u in node.upstream:
                other = indexed[u].context
                if other.period != node.context.period or any(
                    getattr(other.provenance, f) != getattr(node.context.provenance, f)
                    for f in ("scenario", "reference_member", "reference_kind", "configuration_version")
                ):
                    raise ValueError("propagation requires compatible scenario/member, period and configuration")

        # A common upstream catchment in two receiving branches would be counted twice.
        # Reject both cycles and reconverging/split topologies rather than guessing shares.
        def visit(identifier: str, seen: set[str]) -> None:
            if identifier in seen:
                raise ValueError("cyclic or overlapping/nested upstream catchments")
            seen.add(identifier)
            for upstream in indexed[identifier].upstream:
                visit(upstream, seen)

        for node in self.nodes:
            visit(node.identifier, set())


@dataclass(frozen=True)
class AreaContribution:
    node: CatchmentNode
    area: Area
    classification: HydrologyClass | None
    point_result: IndicatorResult | None
    reason: str


@dataclass(frozen=True)
class ReachCondition:
    result: IndicatorResult
    weighted_class: Fraction | None
    total_area: Area
    unassessed_area: Area
    contributions: tuple[AreaContribution, ...]
    network_version: str


def propagate_indicator(network: DrainageNetwork, outlet: str, indicator: Indicator) -> ReachCondition:
    """Nearest upstream intervention per indicator; ordinary half-up class rounding.

    Unrounded missing fraction <15% is omitted from the assessed denominator,
    while coverage remains incomplete. Exactly 15% has no approved source class.
    """
    if not isinstance(network, DrainageNetwork) or not isinstance(indicator, Indicator):
        raise TypeError("typed network and indicator required")
    nodes = {n.identifier: n for n in network.nodes}
    if outlet not in nodes:
        raise ValueError("outlet is not in the prepared network")
    target = nodes[outlet]
    source = MANUAL + ", §6.1.2, Figure 30"
    if target.feature is ReachFeature.LAKE:
        result = IndicatorResult(
            indicator,
            target.context,
            AssessmentState.NOT_APPLICABLE,
            None,
            (),
            source,
            ("lakes are not classified as river reaches",),
            (network,),
        )
        return ReachCondition(result, None, target.area, target.area, (), network.version)

    def collect(node: CatchmentNode) -> list[AreaContribution]:
        if indicator in node.affected_indicators:
            found = next((r for r in node.results if r.indicator is indicator), None)
            return [
                AreaContribution(
                    node,
                    node.area,
                    found.classification if found is not None else None,
                    found,
                    "nearest upstream intervention" if found is not None else "required point result missing",
                )
            ]
        if node.feature is ReachFeature.LAKE:
            # The source's lake reset needs a supplied reach-boundary decision;
            # an unqualified lake cannot erase upstream impacts.
            return [
                AreaContribution(
                    node, node.area, None, None, "lake influence/reset not supplied as a river point result"
                )
            ]
        contributions = [part for upstream in node.upstream for part in collect(nodes[upstream])]
        local = node.area.value - sum(nodes[u].area.value for u in node.upstream)
        if local > 0:
            unaffected = node.local_condition is IntermediateCondition.UNAFFECTED
            contributions.append(
                AreaContribution(
                    node,
                    Area(local),
                    HydrologyClass.HIGH if unaffected else None,
                    None,
                    "unaffected intermediate area" if unaffected else "intermediate area unassessed",
                )
            )
        return contributions

    parts = tuple(collect(target))
    if sum(p.area.value for p in parts) != target.area.value:
        raise ValueError("contributions do not partition target catchment")
    missing = sum((p.area.value for p in parts if p.classification is None), Fraction())
    ratio = missing / target.area.value
    coverage = (
        Completeness.INCOMPLETE
        if missing
        or any(p.point_result is not None and p.point_result.coverage is Completeness.INCOMPLETE for p in parts)
        else Completeness.COMPLETE
    )
    reasons: tuple[str, ...] = ()
    weighted = None
    classification = None
    if ratio == Fraction(15, 100):
        reasons = ("exactly 15% unassessed upstream area: source equality unresolved",)
    elif ratio > Fraction(15, 100):
        reasons = ("more than 15% unassessed upstream area",)
    else:
        weighted = sum(
            (p.area.value * int(p.classification) for p in parts if p.classification is not None), Fraction()
        ) / (target.area.value - missing)
        classification = HydrologyClass(
            (weighted + Fraction(1, 2)).numerator // (weighted + Fraction(1, 2)).denominator
        )
        if missing:
            reasons = ("unassessed areas below 15% omitted from weighted denominator; original coverage retained",)
    metrics = (Metric("unassessed_area_fraction", ratio, "1"),)
    if weighted is not None:
        metrics += (Metric("weighted_class", weighted, "class"),)
    result = IndicatorResult(
        indicator,
        target.context,
        AssessmentState.ASSESSED if classification is not None else AssessmentState.UNDETERMINED,
        classification,
        metrics,
        source,
        reasons,
        parts,
        coverage,
    )
    return ReachCondition(result, weighted, target.area, Area(missing), parts, network.version)


def propagate_hydrology(network: DrainageNetwork, outlet: str) -> tuple[ReachCondition, ...]:
    return tuple(propagate_indicator(network, outlet, i) for i in Indicator)


class BoundaryAction(StrEnum):
    CONTINUE = "continue"
    NEW_REACH = "new_reach"
    END_INFLUENCE = "end_influence"
    LAKE_EXCLUDED = "lake_excluded"


class InterventionInfluence(StrEnum):
    SIGNIFICANT = "significant"
    NONE = "none"


@dataclass(frozen=True)
class ReachBoundaryInputs:
    context: AssessmentContext
    starting_area: Area
    current_area: Area
    reference_mean: Flow
    groundwater_gain: Flow
    intervention: InterventionInfluence
    tributary: InterventionInfluence
    lake_volume: Volume | None
    upstream_classes: tuple[IndicatorResult, ...]
    evidence: str

    def __post_init__(self) -> None:
        if not isinstance(self.context, AssessmentContext):
            raise TypeError("reach boundary needs context")
        if any(not isinstance(a, Area) for a in (self.starting_area, self.current_area)):
            raise TypeError("reach boundary needs physical areas")
        if self.starting_area.value <= 0 or self.current_area.value < self.starting_area.value:
            raise ValueError("catchment growth requires positive ordered areas")
        if any(not isinstance(q, Flow) for q in (self.reference_mean, self.groundwater_gain)):
            raise TypeError("reach boundary needs interval mean Flow")
        if self.reference_mean.value <= 0:
            raise ValueError("reference mean must be positive")
        if any(not isinstance(x, InterventionInfluence) for x in (self.intervention, self.tributary)):
            raise TypeError("significance requires InterventionInfluence")
        if self.lake_volume is not None and not isinstance(self.lake_volume, Volume):
            raise TypeError("lake volume requires Volume")
        if not isinstance(self.upstream_classes, tuple) or any(
            not isinstance(r, IndicatorResult) for r in self.upstream_classes
        ):
            raise TypeError("upstream classes require IndicatorResult tuple")
        if len({r.indicator for r in self.upstream_classes}) != len(self.upstream_classes):
            raise ValueError("duplicate upstream indicators")
        if any(
            r.context.period != self.context.period
            or any(
                getattr(r.context.provenance, f) != getattr(self.context.provenance, f)
                for f in ("scenario", "reference_member", "configuration_version")
            )
            for r in self.upstream_classes
        ):
            raise ValueError("upstream boundary results require matching scenario/member, period and configuration")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("prepared boundary conditions require evidence")


@dataclass(frozen=True)
class ReachBoundary:
    inputs: ReachBoundaryInputs
    action: BoundaryAction
    reasons: tuple[str, ...]
    source: str = MANUAL + ", §6.1.1"


def delimit_reach(inputs: ReachBoundaryInputs) -> ReachBoundary:
    """Prepared source thresholds, not geometry or an inferred lake river class."""
    if not isinstance(inputs, ReachBoundaryInputs):
        raise TypeError("typed reach-boundary inputs required")
    reasons: list[str] = []
    if inputs.lake_volume is not None:
        if inputs.lake_volume.value > 10800 * inputs.reference_mean.value:
            return ReachBoundary(
                inputs,
                BoundaryAction.END_INFLUENCE,
                ("lake volume exceeds 3 h × incoming MQ; lake itself not classified",),
            )
        if inputs.lake_volume.value > 3600 * inputs.reference_mean.value:
            return ReachBoundary(
                inputs, BoundaryAction.NEW_REACH, ("lake volume exceeds 1 h × incoming MQ; lake itself not classified",)
            )
        return ReachBoundary(
            inputs, BoundaryAction.LAKE_EXCLUDED, ("lake itself not classified; no source volume threshold exceeded",)
        )
    if inputs.intervention is InterventionInfluence.SIGNIFICANT:
        reasons.append("significant intervention begins/restarts a reach")
    if inputs.tributary is InterventionInfluence.SIGNIFICANT:
        reasons.append("tributary carries significant upstream intervention")
    if (inputs.current_area.value - inputs.starting_area.value) / inputs.starting_area.value > Fraction(15, 100):
        reasons.append("catchment growth exceeds 15% of area at reach start")
    if inputs.groundwater_gain.value >= inputs.reference_mean.value:
        reasons.append("groundwater gain doubles mean flow")
    if reasons:
        return ReachBoundary(inputs, BoundaryAction.NEW_REACH, tuple(reasons))
    if len(inputs.upstream_classes) == len(Indicator) and all(
        r.classification is HydrologyClass.HIGH for r in inputs.upstream_classes
    ):
        return ReachBoundary(inputs, BoundaryAction.END_INFLUENCE, ("all nine indicators have reached class 1",))
    return ReachBoundary(inputs, BoundaryAction.CONTINUE, ("no supplied source reach-change/end criterion met",))


def screen_ended_influence(boundary: ReachBoundary, context: AssessmentContext) -> tuple[IndicatorResult, ...]:
    """Transfer a source-defined end of influence to a downstream river section.

    This is not a lake classification. A subsequent significant intervention
    requires its own assessment and must not be omitted from the prepared graph.
    """
    if not isinstance(boundary, ReachBoundary) or not isinstance(context, AssessmentContext):
        raise TypeError("typed boundary decision and downstream context required")
    if delimit_reach(boundary.inputs) != boundary or boundary.action is not BoundaryAction.END_INFLUENCE:
        raise ValueError("source-defined end of influence required")
    original = boundary.inputs.context
    if original.period != context.period or any(
        getattr(original.provenance, field) != getattr(context.provenance, field)
        for field in ("scenario", "reference_member", "configuration_version")
    ):
        raise ValueError("boundary and downstream context differ in scenario/member, period or configuration")
    # A class-based end inherits each indicator's original area/evidence coverage.
    # A source lake end instead rests on its independent >3 h × MQ volume rule.
    upstream = {r.indicator: r for r in boundary.inputs.upstream_classes}
    lake_end = boundary.inputs.lake_volume is not None
    return tuple(
        IndicatorResult(
            indicator,
            context,
            AssessmentState.SCREENED,
            HydrologyClass.HIGH,
            (),
            MANUAL + ", §6.1.1",
            boundary.reasons,
            (boundary,),
            Completeness.COMPLETE if lake_end else upstream[indicator].coverage,
        )
        for indicator in Indicator
    )
