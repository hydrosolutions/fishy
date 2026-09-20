"""spawning_schedule : BiologicalTiming × CoefficientChoice × FlowSamples → TimedCoefficients.

Order 179-НҚ (2025), paragraphs 25–27 and Appendices 3–4. Interpretations
produce scenario candidates, not official reconciliation of the published stars.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from fractions import Fraction

from fishy.design_conditions import DesignClass
from fishy.evidence import (
    CheckFinding,
    EvidenceFindings,
    EvidenceScope,
    ProductionMethod,
    Provenance,
    permitted_use,
    warmup_restrictions,
)
from fishy.flows import Coverage, FlowSample, Presence
from fishy.quantities import SignedState, StateVariable, finite_number
from fishy.spatial import Location
from fishy.time import Interval

SOURCE = "Kazakhstan Order 179-НҚ (2025), paragraphs 25–27, Appendices 3–4"
STAR_HEADINGS = (
    "Официальные сроки весенне-летнего запрета*",
    "Ориентировочные коэффициенты экостока ** (K/K/K/Ксезонное)",
)


class EligibilityInterpretation(StrEnum):
    PERCENTAGE_WORDING = "percentage_wording"
    DRY_YEAR_WORDING = "dry_year_wording"


class SpawningEligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNRESOLVED = "unresolved"


def spawning_eligibility(design: DesignClass, interpretation: EligibilityInterpretation | None) -> SpawningEligibility:
    if not isinstance(design, DesignClass):
        raise TypeError("parse a DesignClass first")
    if interpretation is None:
        return SpawningEligibility.UNRESOLVED
    if not isinstance(interpretation, EligibilityInterpretation):
        raise TypeError("eligibility interpretation requires enum")
    eligible = (
        design.value <= 75 if interpretation is EligibilityInterpretation.PERCENTAGE_WORDING else design.value >= 75
    )
    return SpawningEligibility.ELIGIBLE if eligible else SpawningEligibility.INELIGIBLE


class TemporalBasis(StrEnum):
    DAILY_STAGE = "daily_stage"
    MONTHLY_AVERAGE = "monthly_average"


class CoefficientInterpretation(StrEnum):
    LISTED_VALUE = "listed_value"
    WEIGHTED_STUDY = "weighted_study"


class StarRelevance(StrEnum):
    NOT_RELIED_UPON = "not_relied_upon"
    AFFECTS_ELIGIBILITY = "affects_eligibility"


@dataclass(frozen=True)
class BasinCoefficients:
    row: int
    basin: str
    waters: str
    approximate_dates: str
    species: str
    phases: str
    migration: Fraction
    spawning: Fraction
    incubation: Fraction
    seasonal: Fraction
    source: str = SOURCE
    starred_headings: tuple[str, str] = STAR_HEADINGS


# Exact printed values; no clamping and no recomputation of printed averages.
APPENDIX3 = tuple(
    (name, Fraction(lo), Fraction(hi))
    for name, lo, hi in (
        ("migration", "1.10", "1.15"),
        ("spawning", "1.25", "1.30"),
        ("incubation/hatching", "1.05", "1.10"),
        ("seasonal", "1.13", "1.18"),
    )
)
APPENDIX4 = tuple(
    BasinCoefficients(
        i,
        name,
        waters,
        dates,
        species,
        phases,
        Fraction(values[0]),
        Fraction(values[1]),
        Fraction(values[2]),
        Fraction(values[3]),
    )
    for i, name, waters, dates, species, phases, values in (
        (
            1,
            "Жайык-Каспийский",
            "Река Жайык, озеро Шалкар, река Кигаш",
            "15.05–15.06 / 01.05–31.05 / 25.05–15.08",
            "Судак, щука, сазан",
            "Нерест, инкубация",
            ("1.15", "1.3", "1.1", "1.18"),
        ),
        (
            2,
            "Арало-Сырдарьинский",
            "Река Сырдарья, Шардаринское водохранилищеще, Северное Аралское море",
            "20.04–10.06 / 01.04–20.05 / 01.05–10.06",
            "Сазан, толстолобик, лещ",
            "Миграция, нерест",
            ("1.2", "1.25", "1.1", "1.18"),
        ),
        (
            3,
            "Балкаш-Алакольский",
            "река Иле, озеро Балкаш, Капшагайское водохранилище",
            "15.04–01.06",
            "Сазан, карась, судак",
            "Миграция, нерест, инкубация",
            ("1.1", "1.3", "1.1", "1.16"),
        ),
        (
            4,
            "Ертисский",
            "Река Ертис, Бухтарминское водохранилище, озеро Жайсан",
            "10.05–10.06 / 16.04–30.05 / 15.04–30.05",
            "Щука, лещ, судак",
            "Миграция, нерест, инкубация",
            ("1.2", "1.25", "1.1", "1.18"),
        ),
        (
            5,
            "Есильский",
            "река Есиль и притоки",
            "20.04–20.05 / 15.04–15.05 / 20.05–20.06",
            "Судак, щука, сазан",
            "Миграция, нерест, инкубация",
            ("1.15", "1.2", "1.1", "1.15"),
        ),
        (
            6,
            "Нура-Сарысу",
            "Реки Нура, Сарысу и притоки",
            "20.04–20.05 / 01.05–30.06",
            "Сазан, судак",
            "Миграция, нерест, инкубация",
            ("1.1", "1.2", "1.05", "1.11"),
        ),
        (
            7,
            "Тобол-Торгайский",
            "Реки Тобол, Торгай",
            "10.04–10.05 / 20.05–30.06 / 20.05–10.06",
            "Щука, карась, лещ",
            "Миграция, нерест, инкубация",
            ("1.1", "1.2", "1.05", "1.11"),
        ),
        (
            8,
            "Шу-Таласский",
            "Реки Шу, Талас, Аса",
            "01.03–01.07 / 15.04–31.05 / 15.04–30.06",
            "Сазан, карась, судак",
            "Миграция, нерест",
            ("1.15", "1.25", "1.1", "1.16"),
        ),
    )
)


def coefficient_scope(location: Location, interval: Interval, provenance: Provenance) -> EvidenceScope:
    return EvidenceScope(
        "spawning_coefficient", location.reach.identifier, provenance.reference_member, interval, "spawning_correction"
    )


@dataclass(frozen=True)
class TimedCoefficient:
    location: Location
    interval: Interval
    value: Fraction | None
    provenance: Provenance
    findings: EvidenceFindings | None
    presence: Presence = Presence.PRESENT
    reasons: tuple[str, ...] = ()
    supporting_evidence: tuple[EvidenceFindings, ...] = ()
    supporting_observations: tuple[FlowSample, ...] = ()
    required_support: tuple[EvidenceScope, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.location, Location)
            or not isinstance(self.interval, Interval)
            or not isinstance(self.provenance, Provenance)
        ):
            raise TypeError("coefficient requires typed location, interval and provenance")
        if not isinstance(self.presence, Presence):
            raise TypeError("presence requires Presence")
        if self.value is not None:
            value = finite_number(self.value)
            if value < 0:
                raise ValueError("coefficient must be nonnegative")
            object.__setattr__(self, "value", value)
        if self.presence is Presence.PRESENT and self.value is None:
            raise ValueError("present coefficient requires value")
        if self.presence is not Presence.PRESENT and (self.value is not None or not self.reasons):
            raise ValueError("unavailable coefficient needs reasons and no value")
        if not isinstance(self.reasons, tuple) or any(not isinstance(s, str) or not s.strip() for s in self.reasons):
            raise ValueError("reasons require immutable nonempty strings")
        if self.findings is not None and not isinstance(self.findings, EvidenceFindings):
            raise TypeError("findings require EvidenceFindings")
        if not isinstance(self.supporting_evidence, tuple) or any(
            not isinstance(f, EvidenceFindings) for f in self.supporting_evidence
        ):
            raise TypeError("supporting evidence requires immutable findings")
        if not isinstance(self.supporting_observations, tuple) or any(
            not isinstance(o, FlowSample) for o in self.supporting_observations
        ):
            raise TypeError("observations require immutable FlowSample records")
        if not isinstance(self.required_support, tuple) or any(
            not isinstance(scope, EvidenceScope) for scope in self.required_support
        ):
            raise TypeError("required support requires immutable EvidenceScope records")
        if len(set(self.required_support)) != len(self.required_support):
            raise ValueError("duplicate required support scopes")


@dataclass(frozen=True)
class BiologicalTiming:
    species: str
    baseline_onset: datetime
    annual_shift_days: int
    stage_days: tuple[int, int, int]
    onset_water_temperature: SignedState
    optimal_temperature: SignedState
    findings: EvidenceFindings
    location: Location

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location):
            raise TypeError("biological timing requires Location")
        if not isinstance(self.species, str) or not self.species.strip():
            raise ValueError("species must be identified")
        if type(self.annual_shift_days) is not int or abs(self.annual_shift_days) > 15:
            raise ValueError("annual onset shift must be within +/-15 days")
        if (
            not isinstance(self.stage_days, tuple)
            or len(self.stage_days) != 3
            or any(type(d) is not int or d <= 0 for d in self.stage_days)
        ):
            raise ValueError("three positive whole-day stage durations required")
        for state in (self.onset_water_temperature, self.optimal_temperature):
            if not isinstance(state, SignedState) or state.variable is not StateVariable.TEMPERATURE:
                raise TypeError("biological onset requires water-temperature states")
        if not isinstance(self.findings, EvidenceFindings):
            raise TypeError("timing requires scoped evidence")
        _ = self.period

    @property
    def onset(self) -> datetime:
        return self.baseline_onset + timedelta(days=self.annual_shift_days)

    @property
    def period(self) -> Interval:
        return Interval(self.onset, self.onset + timedelta(days=sum(self.stage_days)))


@dataclass(frozen=True)
class WeightedStudy:
    stage_values: tuple[Fraction, Fraction, Fraction]
    stage_weights: tuple[Fraction, Fraction, Fraction]
    period: Interval
    findings: EvidenceFindings
    location: Location

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location):
            raise TypeError("weighted study requires Location")
        for name in ("stage_values", "stage_weights"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or len(values) != 3:
                raise ValueError("study requires three immutable stage values/weights")
            parsed = tuple(finite_number(x) for x in values)
            if any(x < 0 for x in parsed):
                raise ValueError("study coefficients and weights must be nonnegative")
            object.__setattr__(self, name, parsed)
        if sum(self.stage_weights) <= 0:
            raise ValueError("study stage weights need positive total")
        if not isinstance(self.period, Interval) or not isinstance(self.findings, EvidenceFindings):
            raise TypeError("study requires period and scoped evidence")

    @property
    def average(self) -> Fraction:
        return sum((v * w for v, w in zip(self.stage_values, self.stage_weights, strict=True)), Fraction()) / sum(
            self.stage_weights
        )


def _support(findings: EvidenceFindings, scope: EvidenceScope, provenance: Provenance) -> tuple[str, ...]:
    if findings.provenance != provenance:
        return ("evidence provenance/version mismatch",)
    check = permitted_use(findings, scope)
    return warmup_restrictions(findings.provenance, scope.period) + (
        () if check.finding is CheckFinding.PASS else ("evidence not supported for exact scope", *check.reasons)
    )


def spawning_schedule(
    location: Location,
    intervals: tuple[Interval, ...],
    provenance: Provenance,
    design: DesignClass,
    eligibility_interpretation: EligibilityInterpretation | None,
    temporal_basis: TemporalBasis,
    coefficient_interpretation: CoefficientInterpretation | None,
    star_relevance: StarRelevance,
    timing: BiologicalTiming | None,
    coefficient_findings: tuple[EvidenceFindings, ...],
    *,
    basin_row: int | None = None,
    study: WeightedStudy | None = None,
    daily_observations: tuple[FlowSample, ...] = (),
) -> tuple[TimedCoefficient, ...]:
    """Construct only requested periods; no calendar dates substitute for biology.

    Output remains an interpreted candidate. Exact coefficient scope is required for
    each requested interval, including explicit neutral values outside the season.
    """
    if not isinstance(temporal_basis, TemporalBasis) or not isinstance(star_relevance, StarRelevance):
        raise TypeError("temporal basis and star relevance require enums")
    if coefficient_interpretation is not None and not isinstance(coefficient_interpretation, CoefficientInterpretation):
        raise TypeError("coefficient interpretation requires enum")
    if not intervals or not isinstance(intervals, tuple):
        raise ValueError("request explicit immutable intervals")
    ordered = sorted(intervals)
    if any(a.end > b.start for a, b in zip(ordered, ordered[1:], strict=False)):
        raise ValueError("duplicate/overlapping coefficient intervals")
    if len({f.scope for f in coefficient_findings}) != len(coefficient_findings):
        raise ValueError("duplicate coefficient evidence scopes")
    eligibility = spawning_eligibility(design, eligibility_interpretation)
    reasons: list[str] = []
    if eligibility is SpawningEligibility.UNRESOLVED:
        reasons.append("eligibility interpretation missing")
    if coefficient_interpretation is None:
        reasons.append("coefficient interpretation missing")
    if star_relevance is StarRelevance.AFFECTS_ELIGIBILITY:
        reasons.append("unexplained Appendix 4 stars affect eligibility")
    if timing is None:
        reasons.append("species, biological water-temperature onset and stage duration evidence missing")
    else:
        if timing.location != location:
            reasons.append("biological timing location/version mismatch")
        scope = EvidenceScope(
            "spawning_timing",
            location.reach.identifier,
            provenance.reference_member,
            timing.period,
            "spawning_correction",
        )
        reasons.extend(_support(timing.findings, scope, provenance))
        if timing.onset_water_temperature.value < timing.optimal_temperature.value:
            reasons.append("water temperature has not reached biological onset threshold")
    row = None
    if coefficient_interpretation is CoefficientInterpretation.LISTED_VALUE:
        if type(basin_row) is not int or basin_row not in range(1, 9):
            reasons.append("published basin row missing or unsupported")
        else:
            row = APPENDIX4[basin_row - 1]
    if coefficient_interpretation is CoefficientInterpretation.WEIGHTED_STUDY:
        if study is None:
            reasons.append("weighted study missing")
        elif timing is not None:
            if study.location != location:
                reasons.append("weighted study location/version mismatch")
            scope = EvidenceScope(
                "spawning_weighted_average",
                location.reach.identifier,
                provenance.reference_member,
                timing.period,
                "spawning_correction",
            )
            reasons.extend(_support(study.findings, scope, provenance))
            if study.period != timing.period:
                reasons.append("study covered period differs from biological season")
            if temporal_basis is TemporalBasis.DAILY_STAGE:
                reasons.append("weighted average cannot replace daily-stage values")
    trace = (
        SOURCE,
        f"design={design.value}; eligibility={eligibility_interpretation}; temporal_basis={temporal_basis}",
        f"coefficient_interpretation={coefficient_interpretation}; basin_row={basin_row}; stars={star_relevance}",
        "interpreted candidate; source stars unresolved; not legal certification",
    )
    supporting_evidence = ()
    if timing is not None:
        trace += (
            f"species={timing.species}; onset={timing.onset.isoformat()}; stage_days={timing.stage_days}; annual_shift_days={timing.annual_shift_days}",
        )
        supporting_evidence += (timing.findings,)
    if study is not None:
        trace += (
            f"study stage_values={study.stage_values}; stage_weights={study.stage_weights}; period={study.period}",
        )
        supporting_evidence += (study.findings,)
    outputs = []
    for interval in intervals:
        scope = coefficient_scope(location, interval, provenance)
        findings = next((f for f in coefficient_findings if f.scope == scope), None)
        local = list(reasons)
        if findings is None:
            local.append("coefficient evidence missing for interval")
        else:
            local.extend(_support(findings, scope, provenance))
        local.extend(warmup_restrictions(provenance, interval))
        value = Fraction(1)
        observations: tuple[FlowSample, ...] = ()
        if timing is not None and eligibility is SpawningEligibility.ELIGIBLE:
            active = interval.start < timing.period.end and timing.period.start < interval.end
            if temporal_basis is TemporalBasis.DAILY_STAGE:
                if (
                    interval.seconds != 86400
                    or interval.start.hour
                    or interval.start.minute
                    or interval.start.second
                    or interval.start.microsecond
                ):
                    local.append("daily-stage branch requires whole UTC days")
                if active:
                    observations = tuple(
                        o for o in daily_observations if o.interval == interval and o.location == location
                    )
                    if len(observations) != 1:
                        local.append("daily observation missing or duplicated")
                    else:
                        o = observations[0]
                        if (
                            o.presence is not Presence.PRESENT
                            or o.provenance.production_method is not ProductionMethod.OBSERVED
                            or o.coverage is not Coverage.COMPLETE
                            or o.provenance.scenario != provenance.scenario
                            or o.provenance.reference_member != provenance.reference_member
                            or warmup_restrictions(o.provenance, interval)
                        ):
                            local.append("daily observation unsupported")
                    start = timing.onset
                    stage = None
                    for index, days in enumerate(timing.stage_days):
                        end = start + timedelta(days=days)
                        if start <= interval.start and interval.end <= end:
                            stage = index
                        start = end
                    if stage is None:
                        local.append("daily interval crosses biological stage boundary")
                    elif row is not None:
                        value = (row.migration, row.spawning, row.incubation)[stage]
            else:
                start = interval.start
                next_month = (
                    start.replace(year=start.year + 1, month=1, day=1)
                    if start.month == 12
                    else start.replace(month=start.month + 1, day=1)
                )
                if (
                    start.day != 1
                    or (start.hour, start.minute, start.second, start.microsecond) != (0, 0, 0, 0)
                    or interval.end != next_month
                ):
                    local.append("monthly-average branch requires whole calendar months")
                if active:
                    if row is not None:
                        value = row.seasonal
                    elif study is not None:
                        value = study.average
        outputs.append(
            TimedCoefficient(
                location,
                interval,
                None if local else value,
                provenance,
                findings,
                Presence.UNSUPPORTED if local else Presence.PRESENT,
                tuple(local) + trace,
                supporting_evidence,
                observations,
                tuple(finding.scope for finding in supporting_evidence),
            )
        )
    return tuple(outputs)
