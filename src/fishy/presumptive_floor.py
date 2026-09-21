"""presumptive_floor : AcceptedNaturalReference × SeasonalFractions → DailyBaseFloor.

Pure proposed Uzbek fallback. No full regime or newly derived obligation follows.
"""

from dataclasses import dataclass, replace
from fractions import Fraction
from hashlib import sha256

from fishy.daily_patterns import DailyPattern, PatternMethod, pattern_product
from fishy.evidence import Check, CheckFinding, CheckSummary, ProductionMethod, ReferenceKind
from fishy.flows import FlowSample
from fishy.quantities import Flow, finite_number
from fishy.scientific_acceptance import UsePurpose


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty source, version and justification required")


def _floor_sample(sample: FlowSample, fraction: Fraction, version: str) -> FlowSample:
    assert sample.value is not None
    source = sample.provenance
    provenance = replace(
        source,
        source="presumptive base floor",
        configuration_version=version,
        production_method=ProductionMethod.ILLUSTRATIVE
        if source.production_method is ProductionMethod.ILLUSTRATIVE
        else ProductionMethod.RECONSTRUCTED,
        limitations=(
            *source.limitations,
            "output uncertainty not propagated; original input support retained separately",
        ),
    )
    return replace(
        sample,
        value=Flow(fraction * sample.value.value),
        uncertainty=None,
        provenance=provenance,
        components=(sample,),
        reasons=(*sample.reasons, "input uncertainty is not the uncertainty of the derived floor"),
    )


@dataclass(frozen=True)
class SeasonalFraction:
    name: str
    start_day: int
    end_day: int
    fraction: Fraction

    def __post_init__(self) -> None:
        _text(self.name)
        if (
            type(self.start_day) is not int
            or type(self.end_day) is not int
            or not 0 <= self.start_day < self.end_day <= 366
        ):
            raise ValueError("season requires explicit [start_day, end_day) accounting-year offsets")
        f = finite_number(self.fraction)
        if not 0 <= f <= 1:
            raise ValueError("presumptive fraction must lie in [0,1]")
        object.__setattr__(self, "fraction", f)


@dataclass(frozen=True)
class PresumptiveProfile:
    version: str
    reference_definition: str
    reference_identity: str
    seasons: tuple[SeasonalFraction, ...]
    adoption_or_scenario_basis: str
    uncertainty: str

    def __post_init__(self) -> None:
        for value in (
            self.version,
            self.reference_definition,
            self.reference_identity,
            self.adoption_or_scenario_basis,
            self.uncertainty,
        ):
            _text(value)
        if not isinstance(self.seasons, tuple) or any(not isinstance(s, SeasonalFraction) for s in self.seasons):
            raise TypeError("immutable seasonal fraction schedule required")
        days = [d for s in self.seasons for d in range(s.start_day, s.end_day)]
        if len(days) != len(set(days)):
            raise ValueError("overlapping presumptive seasons")


def presumptive_reference_identity(reference: DailyPattern) -> str:
    """Bind the supplied record; an unavailable pattern is not a numerical product."""
    identity = (
        ("unavailable-pattern", reference)
        if reference.method is PatternMethod.UNAVAILABLE
        else pattern_product(reference, intended_use=reference.requested_use, purpose=reference.purpose)
    )
    return sha256(repr(identity).encode()).hexdigest()


@dataclass(frozen=True)
class PresumptiveFloor:
    """Base floor only. No ecological regime, full requirement or new obligation."""

    samples: tuple[FlowSample, ...]
    fractions: tuple[Fraction, ...]
    checks: CheckSummary
    reference: DailyPattern | None
    profile: PresumptiveProfile | None


def presumptive_floor(reference: DailyPattern | None, profile: PresumptiveProfile | None) -> PresumptiveFloor:
    """Multiply explicitly chosen seasonal fractions by the accepted reference."""
    if reference is not None and not isinstance(reference, DailyPattern):
        raise TypeError("accepted daily reference pattern required")
    if profile is not None and not isinstance(profile, PresumptiveProfile):
        raise TypeError("explicit presumptive profile required")
    if reference is None or profile is None:
        return PresumptiveFloor(
            (),
            (),
            CheckSummary(
                (
                    Check(
                        "basis",
                        CheckFinding.UNKNOWN,
                        ("pending — no computable basis: reference or seasonal schedule missing",),
                    ),
                )
            ),
            reference,
            profile,
        )
    checks = [
        Check(
            "reference", reference.use_checks.finding, tuple(r for c in reference.use_checks.checks for r in c.reasons)
        )
    ]
    if reference.method is PatternMethod.UNAVAILABLE:
        checks.append(Check("reference_product", CheckFinding.UNKNOWN, ("numerical daily pattern unavailable",)))
    exact = profile.reference_identity == presumptive_reference_identity(reference)
    natural = reference.magnitude.provenance.reference_kind is ReferenceKind.PRESENT_CLIMATE_NATURAL
    checks.append(
        Check(
            "reference_definition",
            CheckFinding.PASS if exact and natural and reference.purpose is UsePurpose.SIZING else CheckFinding.FAIL,
            (profile.reference_definition,),
        )
    )
    by_day = {d: s.fraction for s in profile.seasons for d in range(s.start_day, s.end_day)}
    checks.append(
        Check(
            "seasons",
            CheckFinding.PASS if set(by_day) == set(range(reference.calendar.days)) else CheckFinding.UNKNOWN,
            ("complete non-overlapping seasonal schedule required",),
        )
    )
    summary = CheckSummary(tuple(checks))
    fractions = tuple(by_day[d] for d in range(reference.calendar.days)) if summary.finding is CheckFinding.PASS else ()
    samples = (
        tuple(
            _floor_sample(s, f, profile.version)
            for s, f in zip(reference.samples, fractions, strict=True)
            if s.value is not None
        )
        if fractions
        else ()
    )
    return PresumptiveFloor(samples, fractions, summary, reference, profile)
