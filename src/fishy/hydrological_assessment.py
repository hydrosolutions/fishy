"""assess_river_hydrology : ReferenceConditions × InventorySurvey × IndicatorResults → HydrologicalAssessment (pure).

Composes one supplied HYDMOD-F configuration. It does not run a simulator,
select national policy, alter a release prescription, or compare scenarios.
"""

from dataclasses import dataclass, replace

from fishy.evidence import Completeness
from fishy.flow_interventions import (
    InterventionScreen,
    InterventionType,
    LandscapeBasis,
    ReferenceConditions,
    ReferenceSuitability,
    SiteSelection,
    WaterBodyKind,
    indicator_selection,
    reference_eligibility,
    reference_limitations,
)
from fishy.hydrological_condition import (
    MANUAL,
    AssessmentContext,
    AssessmentState,
    HydrologicalCondition,
    HydrologyClass,
    Indicator,
    IndicatorResult,
    assess_hydrology,
)


@dataclass(frozen=True)
class InventorySurvey:
    """Explicit coverage distinguishes a surveyed empty inventory from missing data."""

    local: tuple[InterventionScreen, ...]
    upstream: tuple[InterventionScreen, ...]
    coverage: Completeness
    source: str
    version: str

    def __post_init__(self) -> None:
        if not isinstance(self.coverage, Completeness):
            raise TypeError("inventory coverage requires Completeness")
        for values in (self.local, self.upstream):
            if not isinstance(values, tuple) or any(not isinstance(s, InterventionScreen) for s in values):
                raise TypeError("inventory requires immutable InterventionScreen records")
        if not all(isinstance(s, str) and s.strip() for s in (self.source, self.version)):
            raise ValueError("inventory needs attributable survey source and version")
        identities = [i.identifier for s in (*self.local, *self.upstream) for i in s.interventions]
        if len(set(identities)) != len(identities):
            raise ValueError("an intervention cannot be counted twice in the inventory")


@dataclass(frozen=True)
class HydrologicalAssessment:
    reference: ReferenceConditions
    inventory: InventorySurvey
    site_selection: tuple[SiteSelection, ...]
    calculations: tuple[IndicatorResult, ...]
    selection: tuple[IndicatorResult, ...]
    condition: HydrologicalCondition


def assess_river_hydrology(
    context: AssessmentContext,
    reference: ReferenceConditions,
    inventory: InventorySurvey,
    calculations: tuple[IndicatorResult, ...],
    site_selection: tuple[SiteSelection, ...] = (),
) -> HydrologicalAssessment:
    """Retain numerical calculations even when reference or inventory limits use.

    A supplied calculation may add a situational indicator to Table 9's indicative
    selection. It cannot make missing inventory complete or classify a canal/lake.
    Independent raw calculations remain inspectable in ``calculations``.
    """
    if (
        not isinstance(context, AssessmentContext)
        or not isinstance(reference, ReferenceConditions)
        or not isinstance(inventory, InventorySurvey)
    ):
        raise TypeError("typed context, reference and inventory required")
    # Reuse the strict nine-position input/context contract before composition.
    assess_hydrology(context, calculations)
    if not isinstance(site_selection, tuple) or any(not isinstance(s, SiteSelection) for s in site_selection):
        raise TypeError("site selections require immutable SiteSelection records")
    for screen in (*inventory.local, *inventory.upstream):
        for intervention in screen.interventions:
            other = intervention.context
            if other.period != context.period or any(
                getattr(other.provenance, f) != getattr(context.provenance, f)
                for f in ("scenario", "reference_member", "configuration_version")
            ):
                raise ValueError("inventory and calculations differ in scenario/member, period or configuration")
        if screen in inventory.local and any(i.context.location != context.location for i in screen.interventions):
            raise ValueError("local inventory belongs to another location; use attributed upstream inventory")
    for choice in site_selection:
        if (
            choice.provenance.scenario != context.provenance.scenario
            or choice.provenance.reference_member != context.provenance.reference_member
        ):
            raise ValueError("site selection belongs to another scenario/member")
    selection = indicator_selection(context, inventory.local, upstream=inventory.upstream, site=site_selection)
    if not inventory.local and not inventory.upstream and inventory.coverage is Completeness.COMPLETE:
        # A complete no-intervention survey is positive screening evidence.
        base = tuple(
            IndicatorResult(
                i,
                context,
                AssessmentState.SCREENED,
                HydrologyClass.HIGH,
                (),
                MANUAL + ", §§4–5.11",
                ("complete survey: no relevant interventions",),
                (inventory,),
            )
            for i in Indicator
        )
        choices = {s.indicator for s in site_selection}
        selection = tuple(s if s.indicator in choices else b for s, b in zip(selection, base, strict=True))
    local_impoundment = any(
        intervention.kind is InterventionType.IMPOUNDMENT
        for screen in inventory.local
        for intervention in screen.interventions
    )
    if local_impoundment:
        selection = tuple(
            IndicatorResult(
                indicator,
                context,
                AssessmentState.NOT_APPLICABLE,
                None,
                (),
                MANUAL + ", §4.2",
                ("local impounded reach is inventoried, not classified as a river",),
                (inventory,),
            )
            for indicator in Indicator
        )
    usable_reference = (
        reference.water_body is WaterBodyKind.RIVER
        and reference.landscape is LandscapeBasis.CURRENT
        and reference.suitability is ReferenceSuitability.SUPPORTED
        and not reference_limitations(context, reference)
    )
    if local_impoundment:
        condition = assess_hydrology(context, selection)
    elif not usable_reference:
        limited = tuple(reference_eligibility(context, i, reference) for i in Indicator)
        condition = assess_hydrology(context, limited)
    else:
        supplied = {r.indicator: r for r in selection} | {r.indicator: r for r in calculations}
        selected = []
        for screen in selection:
            r = supplied[screen.indicator]
            if inventory.coverage is Completeness.INCOMPLETE:
                if r.state is AssessmentState.SCREENED:
                    r = replace(
                        r,
                        state=AssessmentState.UNDETERMINED,
                        classification=None,
                        reasons=(*r.reasons, "incomplete inventory cannot establish nonrequired indicator"),
                    )
                else:
                    r = replace(
                        r, coverage=Completeness.INCOMPLETE, reasons=(*r.reasons, "inventory coverage incomplete")
                    )
            selected.append(replace(r, inputs=(*r.inputs, reference, inventory)))
        condition = assess_hydrology(context, tuple(selected))
    return HydrologicalAssessment(reference, inventory, site_selection, calculations, selection, condition)
