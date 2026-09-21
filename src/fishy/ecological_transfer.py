"""transfer_ecological_regime : QualifiedDonor × NaturalDesignFamily → EcologicalMemberCandidate.

Pure operator. Outputs precede local quality/receptor assembly and issue.
"""

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from fractions import Fraction
from hashlib import sha256

from fishy.daily_patterns import DailyPattern, PatternMethod, pattern_product
from fishy.design_conditions import DesignClass
from fishy.evidence import (
    Check,
    CheckFinding,
    CheckSummary,
    EvidenceFindings,
    EvidenceScope,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    permitted_use,
)
from fishy.flows import FlowSample
from fishy.natural_baseline import ClassEcologicalRegime, EcologicalMemberCandidate, EcologicalRegimeMethod
from fishy.pattern_calendar import AccountingYear
from fishy.quantities import Flow
from fishy.scientific_acceptance import (
    DiagnosticObservation,
    ScientificCriterion,
    UsePurpose,
    compare_criterion,
)
from fishy.spatial import Location


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty source, version and justification required")


def _digest(value: object) -> str:
    return sha256(repr(value).encode()).hexdigest()


def _derived_provenance(source: Provenance, version: str, operation: str) -> Provenance:
    return replace(
        source,
        source=operation,
        configuration_version=version,
        production_method=ProductionMethod.ILLUSTRATIVE
        if source.production_method is ProductionMethod.ILLUSTRATIVE
        else ProductionMethod.RECONSTRUCTED,
        limitations=(
            *source.limitations,
            "output uncertainty not propagated; original input support retained separately",
        ),
    )


def _derived_sample(sample: FlowSample, factor: Fraction, version: str, operation: str) -> FlowSample:
    assert sample.value is not None
    return replace(
        sample,
        value=Flow(factor * sample.value.value),
        uncertainty=None,
        provenance=_derived_provenance(sample.provenance, version, operation),
        components=(sample,),
        reasons=(*sample.reasons, "input uncertainty is not the uncertainty of the derived requirement"),
    )


def map_monthly_ratios(
    source: AccountingYear,
    ratios: tuple[Fraction, ...],
    target: AccountingYear,
) -> tuple[Fraction, ...]:
    """Overlap means of dimensionless ratios, NOT conservative volume mapping."""
    if source.start_month != target.start_month or source.utc_offset_minutes != target.utc_offset_minutes:
        raise ValueError("matching accounting-year starts and fixed-day conventions required")
    if not isinstance(ratios, tuple) or len(ratios) != source.days:
        raise ValueError("ratios require a complete source accounting year")
    if any(not isinstance(r, Fraction) or r < 0 for r in ratios):
        raise ValueError("ratios must be finite nonnegative Fractions")
    result = []
    offset = 0
    for step in range(12):
        month = (source.start_month - 1 + step) % 12 + 1
        carry = (source.start_month - 1 + step) // 12
        ns = monthrange(source.year + carry, month)[1]
        nt = monthrange(target.year + carry, month)[1]
        for j in range(nt):
            lo, hi = Fraction(j, nt), Fraction(j + 1, nt)
            result.append(
                sum(
                    (
                        ratios[offset + i]
                        * max(Fraction(), min(hi, Fraction(i + 1, ns)) - max(lo, Fraction(i, ns)))
                        * nt
                        for i in range(ns)
                    ),
                    Fraction(),
                )
            )
        offset += ns
    return tuple(result)


@dataclass(frozen=True)
class TransferEdge:
    donor: Location
    recipient: Location
    profile_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.donor, Location) or not isinstance(self.recipient, Location):
            raise TypeError("directed register requires physical locations")
        _text(self.profile_version)


@dataclass(frozen=True)
class TransferRegister:
    version: str
    edges: tuple[TransferEdge, ...]

    def __post_init__(self) -> None:
        _text(self.version)
        if not isinstance(self.edges, tuple) or any(not isinstance(e, TransferEdge) for e in self.edges):
            raise TypeError("immutable directed transfer edges required")
        if len(set(self.edges)) != len(self.edges):
            raise ValueError("duplicate transfer edge")

    def reasons_for(self, edge: TransferEdge) -> tuple[str, ...]:
        # Reach identities, not section names, prevent a second section hiding a chain.
        edges = (*self.edges, edge) if edge not in self.edges else self.edges
        donors = {e.donor.reach for e in edges}
        recipients = {e.recipient.reach for e in edges}
        if donors & recipients:
            return ("directed register contains a chained, cyclic or self transfer",)
        return ()


class QualificationAspect(StrEnum):
    REGIME = "regime"
    INTERMITTENCY = "intermittency"
    PURPOSE = "ecological_purpose"
    RELATIONSHIP = "transferable_relationship"
    RECIPIENT = "recipient_evidence"


@dataclass(frozen=True)
class QualificationTest:
    """Supplied numeric criterion and attributable observations; no default limits."""

    aspect: QualificationAspect
    criterion: ScientificCriterion
    observations: tuple[DiagnosticObservation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.aspect, QualificationAspect) or not isinstance(self.criterion, ScientificCriterion):
            raise TypeError("qualification requires typed aspect and criterion")
        compare_criterion(self.criterion, self.observations)

    @property
    def check(self) -> Check:
        comparisons = compare_criterion(self.criterion, self.observations)
        summary = CheckSummary(tuple(Check(str(i), c.finding) for i, c in enumerate(comparisons)))
        return Check(self.aspect.value, summary.finding, (self.criterion.justification,))


@dataclass(frozen=True)
class TransferProfile:
    version: str
    donor: Location
    recipient: Location
    chosen_at: datetime
    choice_justification: str
    qualification: tuple[QualificationTest, ...]
    donor_uncertainty: str
    calendar_sensitivity: str

    def __post_init__(self) -> None:
        for value in (self.version, self.choice_justification, self.donor_uncertainty, self.calendar_sensitivity):
            _text(value)
        if not isinstance(self.donor, Location) or not isinstance(self.recipient, Location):
            raise TypeError("one explicit donor and recipient required")
        if not isinstance(self.chosen_at, datetime) or self.chosen_at.utcoffset() is None:
            raise ValueError("donor selection requires an aware pre-calculation date")
        if not isinstance(self.qualification, tuple) or any(
            not isinstance(q, QualificationTest) for q in self.qualification
        ):
            raise TypeError("immutable qualification tests required")
        if len({q.aspect for q in self.qualification}) != len(self.qualification):
            raise ValueError("duplicate qualification aspect")


def transfer_scope(
    donor: EcologicalMemberCandidate,
    donor_natural: tuple[DailyPattern, ...],
    recipient_natural: tuple[DailyPattern, ...],
    profile: TransferProfile,
) -> EvidenceScope:
    """Bind acceptance to exact pre-quality values, reference products and choice."""
    if not recipient_natural:
        raise ValueError("recipient reference required to define transfer evidence scope")
    recipient = recipient_natural[0]
    identity = (
        donor.location,
        donor.calendar,
        donor.provenance,
        donor.method,
        donor.profile_version,
        donor.classes,
        donor.evidence,
        profile,
        tuple(
            ("unavailable-pattern", p)
            if p.method is PatternMethod.UNAVAILABLE
            else pattern_product(p, intended_use=p.requested_use, purpose=p.purpose)
            for p in donor_natural
        ),
        tuple(
            ("unavailable-pattern", p)
            if p.method is PatternMethod.UNAVAILABLE
            else pattern_product(p, intended_use=p.requested_use, purpose=p.purpose)
            for p in recipient_natural
        ),
    )
    return EvidenceScope(
        "ecological-transfer:" + _digest(identity),
        profile.recipient.reach.identifier,
        recipient.magnitude.provenance.reference_member,
        recipient.calendar.interval,
        UsePurpose.SIZING.value,
    )


@dataclass(frozen=True)
class RatioMapping:
    design: DesignClass
    source_calendar: AccountingYear
    target_calendar: AccountingYear
    ratios: tuple[Fraction, ...]
    mapped: tuple[Fraction, ...]
    above_one_days: tuple[int, ...]

    @property
    def adequacy_check(self) -> Check:
        return Check(
            "ratio_above_one",
            CheckFinding.UNKNOWN if self.above_one_days else CheckFinding.PASS,
            (f"transfer adequacy review: donor ratio exceeds one at {self.above_one_days}",)
            if self.above_one_days
            else (),
        )


@dataclass(frozen=True)
class TransferResult:
    candidate: EcologicalMemberCandidate | None
    checks: CheckSummary
    mappings: tuple[RatioMapping, ...]
    donor: EcologicalMemberCandidate
    donor_natural: tuple[DailyPattern, ...]
    recipient_natural: tuple[DailyPattern, ...]
    profile: TransferProfile | None
    qualification: EvidenceFindings | None
    register: TransferRegister
    evaluated_at: datetime


def _natural_checks(patterns: tuple[DailyPattern, ...], name: str) -> tuple[Check, ...]:
    checks = []
    targets = {Fraction(int(c), 100) for c in DesignClass}
    if len(patterns) != 4 or {p.magnitude.target.value for p in patterns} != targets:
        return (Check(name, CheckFinding.UNKNOWN, ("complete unshifted four-class mapping required",)),)
    first = patterns[0]
    checks.append(
        Check(
            f"{name}_reference_identity",
            CheckFinding.PASS
            if all(p.magnitude.reference_identity == first.magnitude.reference_identity for p in patterns)
            else CheckFinding.FAIL,
            ("each natural family requires one exact annual reference identity",),
        )
    )
    for i, p in enumerate(patterns):
        if p.method is PatternMethod.UNAVAILABLE:
            checks.append(
                Check(f"{name}_{i}_product", CheckFinding.UNKNOWN, ("numerical daily pattern unavailable", *p.reasons))
            )
        same = (
            p.location,
            p.calendar,
            p.magnitude.provenance.reference_member,
            p.magnitude.provenance.scenario,
            p.requested_use,
        ) == (
            first.location,
            first.calendar,
            first.magnitude.provenance.reference_member,
            first.magnitude.provenance.scenario,
            first.requested_use,
        )
        checks.append(
            Check(
                f"{name}_{i}",
                p.use_checks.finding
                if same
                and p.purpose is UsePurpose.SIZING
                and p.magnitude.provenance.reference_kind is ReferenceKind.PRESENT_CLIMATE_NATURAL
                else CheckFinding.FAIL,
                tuple(r for c in p.use_checks.checks for r in c.reasons),
            )
        )
    return tuple(checks)


def transfer_ecological_regime(
    donor: EcologicalMemberCandidate,
    donor_natural: tuple[DailyPattern, ...],
    recipient_natural: tuple[DailyPattern, ...],
    profile: TransferProfile | None,
    qualification: EvidenceFindings | None,
    register: TransferRegister,
    *,
    evaluated_at: datetime,
) -> TransferResult:
    """Return one pre-quality transfer, or no candidate with retained failed checks.

    This does not run local quality, floor consistency or a baseline safeguard.
    Ratios above one compute and carry a required transfer-adequacy diagnostic.
    """
    for patterns in (donor_natural, recipient_natural):
        if not isinstance(patterns, tuple) or any(not isinstance(p, DailyPattern) for p in patterns):
            raise TypeError("immutable natural DailyPattern families required")
    if profile is not None and not isinstance(profile, TransferProfile):
        raise TypeError("typed transfer profile required")
    if qualification is not None and not isinstance(qualification, EvidenceFindings):
        raise TypeError("scoped transfer evidence required")
    if not isinstance(donor, EcologicalMemberCandidate):
        raise TypeError("only pre-quality ecological candidates can be transferred")
    if not isinstance(register, TransferRegister):
        raise TypeError("versioned directed register required")
    if not isinstance(evaluated_at, datetime) or evaluated_at.utcoffset() is None:
        raise ValueError("aware evaluation date required")
    checks = list(
        _natural_checks(donor_natural, "donor_natural") + _natural_checks(recipient_natural, "recipient_natural")
    )
    checks.append(
        Check(
            "original_donor",
            CheckFinding.FAIL if donor.method is EcologicalRegimeMethod.TRANSFER else CheckFinding.PASS,
            ("a transferred donor cannot seed a transfer",),
        )
    )
    if profile is None or not recipient_natural or not donor_natural:
        checks.append(Check("choice", CheckFinding.UNKNOWN, ("donor profile or natural reference missing",)))
    else:
        d, r = donor_natural[0], recipient_natural[0]
        same = donor.location == profile.donor == d.location and r.location == profile.recipient
        same = (
            same
            and donor.calendar == d.calendar
            and all(
                getattr(donor.provenance, name) == getattr(d.magnitude.provenance, name)
                for name in ("reference_member", "scenario", "reference_kind")
            )
        )
        checks.append(
            Check(
                "choice",
                CheckFinding.PASS if same and profile.chosen_at < evaluated_at else CheckFinding.FAIL,
                (profile.choice_justification,),
            )
        )
        calendar_ok = (d.calendar.start_month, d.calendar.utc_offset_minutes) == (
            r.calendar.start_month,
            r.calendar.utc_offset_minutes,
        )
        checks.append(
            Check("calendar", CheckFinding.PASS if calendar_ok else CheckFinding.FAIL, (profile.calendar_sensitivity,))
        )
        reasons = register.reasons_for(TransferEdge(profile.donor, profile.recipient, profile.version))
        checks.append(Check("register", CheckFinding.FAIL if reasons else CheckFinding.PASS, reasons))
        tests = {t.aspect: t for t in profile.qualification}
        checks.extend(
            tests[a].check if a in tests else Check(a.value, CheckFinding.UNKNOWN, ("qualification missing",))
            for a in QualificationAspect
        )
        if qualification is None:
            checks.append(Check("permission", CheckFinding.UNKNOWN, ("scoped transfer acceptance missing",)))
        else:
            permission = permitted_use(qualification, transfer_scope(donor, donor_natural, recipient_natural, profile))
            checks.append(
                Check(
                    "permission",
                    permission.finding if qualification.provenance == r.magnitude.provenance else CheckFinding.FAIL,
                    permission.reasons,
                )
            )
    mappings = []
    classes = []
    ready = CheckSummary(tuple(checks)).finding is CheckFinding.PASS
    if not ready:
        # An independently known invalid ratio survives other missing prerequisites.
        for index, pattern in enumerate(donor_natural):
            zeros = tuple(i for i, s in enumerate(pattern.samples) if s.value is not None and s.value.value == 0)
            if zeros:
                checks.append(
                    Check(
                        f"denominator_input_{index}",
                        CheckFinding.FAIL,
                        (f"zero donor denominator at day offsets {zeros}; including 0/0 unsupported",),
                    )
                )
    if ready:
        assert profile is not None
        ds = {p.magnitude.target.value: p for p in donor_natural}
        rs = {p.magnitude.target.value: p for p in recipient_natural}
        for c in donor.classes:
            d, r = ds[Fraction(int(c.design), 100)], rs[Fraction(int(c.design), 100)]
            zeros = tuple(i for i, s in enumerate(d.samples) if s.value is not None and s.value.value == 0)
            if zeros:
                checks.append(
                    Check(
                        f"denominator_{int(c.design)}",
                        CheckFinding.FAIL,
                        (f"zero donor denominator at day offsets {zeros}; including 0/0 unsupported",),
                    )
                )
                continue
            ratios = tuple(
                e.value.value / n.value.value
                for e, n in zip(c.samples, d.samples, strict=True)
                if e.value is not None and n.value is not None
            )
            mapped = map_monthly_ratios(d.calendar, ratios, r.calendar)
            mappings.append(
                RatioMapping(
                    c.design, d.calendar, r.calendar, ratios, mapped, tuple(i for i, v in enumerate(ratios) if v > 1)
                )
            )
            classes.append(
                ClassEcologicalRegime(
                    c.design,
                    tuple(
                        _derived_sample(s, v, profile.version, "qualified pre-quality ecological transfer")
                        for s, v in zip(r.samples, mapped, strict=True)
                        if s.value is not None
                    ),
                )
            )
    candidate = None
    if CheckSummary(tuple(checks)).finding is CheckFinding.PASS:
        assert profile is not None
        recipient = recipient_natural[0]
        candidate = EcologicalMemberCandidate(
            recipient.location,
            recipient.calendar,
            _derived_provenance(
                recipient.magnitude.provenance, profile.version, "qualified pre-quality ecological transfer"
            ),
            EcologicalRegimeMethod.TRANSFER,
            profile.version,
            tuple(classes),
            (
                replace(
                    recipient.magnitude.provenance,
                    source="qualified ecological transfer",
                    dependencies=(transfer_scope(donor, donor_natural, recipient_natural, profile).product,),
                ),
            ),
        )
    if candidate is not None:
        assert profile is not None
        edge = TransferEdge(profile.donor, profile.recipient, profile.version)
        if edge not in register.edges:
            register = replace(register, edges=(*register.edges, edge))
    return TransferResult(
        candidate,
        CheckSummary(tuple(checks)),
        tuple(mappings),
        donor,
        donor_natural,
        recipient_natural,
        profile,
        qualification,
        register,
        evaluated_at,
    )
