"""natural_floor : RequirementFamily → FloorInvariant (pure).

The floor is min(final class95) over the complete year. Every class/day must be
at least that fixed value; crossing declines the family, never repairs it.
"""

from dataclasses import dataclass

from fishy.design_conditions import DesignClass
from fishy.evidence import Check, CheckFinding
from fishy.quantities import Flow
from fishy.requirement_family import RequirementFamily
from fishy.time import Interval


@dataclass(frozen=True)
class FloorCrossing:
    design: DesignClass
    interval: Interval
    requirement: Flow
    shortfall: Flow


@dataclass(frozen=True)
class FloorInvariant:
    family: RequirementFamily
    candidate: Flow
    attaining_intervals: tuple[Interval, ...]
    crossings: tuple[FloorCrossing, ...]
    check: Check


def natural_floor(family: RequirementFamily) -> FloorInvariant:
    """Numerical diagnostic only; required final checks must pass before issue."""
    if not isinstance(family, RequirementFamily):
        raise TypeError("natural floor requires a complete uncapped RequirementFamily")
    dry = family.samples(DesignClass.DRY)
    value = min(s.value.value for s in dry if s.value is not None)
    crossings = tuple(
        FloorCrossing(c.design, s.interval, s.value, Flow(value - s.value.value))
        for c in family.classes
        for s in c.samples
        if s.value is not None and s.value.value < value
    )
    return FloorInvariant(
        family,
        Flow(value),
        tuple(s.interval for s in dry if s.value == Flow(value)),
        crossings,
        Check(
            "natural_floor",
            CheckFinding.FAIL if crossings else CheckFinding.PASS,
            ("floor exceeds another class; decline complete family and descend without repair",) if crossings else (),
        ),
    )
