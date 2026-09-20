"""aggregate_checks : RequiredCheckIds × CheckFindings → CheckSummary (pure).

Immutable provenance and scoped evidence preserve supplied judgements, not infer them.
"""

from dataclasses import dataclass
from enum import StrEnum

from fishy.time import Interval


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")


def _texts(values: tuple[str, ...], name: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    for value in values:
        _text(value, name)


class ProductionMethod(StrEnum):
    OBSERVED = "observed"
    SIMULATED = "simulated"
    RECONSTRUCTED = "reconstructed"
    IMPORTED = "imported"
    ILLUSTRATIVE = "illustrative"


class CorrectionState(StrEnum):
    ORIGINAL = "original"
    CORRECTED = "corrected"
    INFILLED = "infilled"
    MISSING = "missing"


class ReferenceKind(StrEnum):
    PRESENT_CLIMATE_NATURAL = "present_climate_natural"
    NATURALISED_HISTORICAL = "naturalised_historical"
    FUTURE_CLIMATE_STRESS = "future_climate_stress"
    OBSERVED = "observed"
    MANAGED = "managed"


@dataclass(frozen=True)
class Provenance:
    source: str
    scenario: str
    reference_member: str | None
    software_version: str
    data_version: str
    configuration_version: str
    production_method: ProductionMethod
    correction_state: CorrectionState
    reference_kind: ReferenceKind | None = None
    dependencies: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    excluded_warmup: tuple[Interval, ...] = ()
    predecessor_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("source", "scenario", "software_version", "data_version", "configuration_version"):
            _text(getattr(self, name), name)
        if self.reference_member is not None:
            _text(self.reference_member, "reference_member")
        for name in ("dependencies", "limitations", "predecessor_sources"):
            _texts(getattr(self, name), name)
        if not isinstance(self.production_method, ProductionMethod):
            raise TypeError("production_method must be ProductionMethod")
        if not isinstance(self.correction_state, CorrectionState):
            raise TypeError("correction_state must be CorrectionState")
        if self.reference_kind is not None and not isinstance(self.reference_kind, ReferenceKind):
            raise TypeError("reference_kind must be ReferenceKind")
        if not isinstance(self.excluded_warmup, tuple) or any(
            not isinstance(period, Interval) for period in self.excluded_warmup
        ):
            raise TypeError("excluded_warmup must be a tuple of Interval")


class CheckFinding(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class Completeness(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class Check:
    check_id: str
    finding: CheckFinding
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.check_id, "check_id")
        if not isinstance(self.finding, CheckFinding):
            raise TypeError("finding must be CheckFinding")
        _texts(self.reasons, "reasons")


@dataclass(frozen=True)
class CheckSummary:
    """A complete set of attributable checks, including explicit unknown omissions."""

    checks: tuple[Check, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.checks, tuple) or any(not isinstance(check, Check) for check in self.checks):
            raise TypeError("checks must be a tuple of Check")
        if len({check.check_id for check in self.checks}) != len(self.checks):
            raise ValueError("duplicate check IDs")

    @property
    def completeness(self) -> Completeness:
        if not self.checks or any(check.finding is CheckFinding.UNKNOWN for check in self.checks):
            return Completeness.INCOMPLETE
        return Completeness.COMPLETE

    @property
    def finding(self) -> CheckFinding:
        if any(check.finding is CheckFinding.FAIL for check in self.checks):
            return CheckFinding.FAIL
        if self.completeness is Completeness.INCOMPLETE:
            return CheckFinding.UNKNOWN
        return CheckFinding.PASS


def aggregate_checks(expected_ids: tuple[str, ...], checks: tuple[Check, ...]) -> CheckSummary:
    """Require declared IDs; omitted reach/group checks remain unknown, never skipped."""
    _texts(expected_ids, "expected_ids")
    if len(set(expected_ids)) != len(expected_ids):
        raise ValueError("duplicate expected check IDs")
    supplied = CheckSummary(checks)
    by_id = {check.check_id: check for check in supplied.checks}
    if set(by_id) - set(expected_ids):
        raise ValueError("undeclared check IDs")
    return CheckSummary(
        tuple(
            by_id[check_id]
            if check_id in by_id
            else Check(check_id, CheckFinding.UNKNOWN, ("required check not supplied",))
            for check_id in expected_ids
        )
    )


class Computability(StrEnum):
    COMPUTABLE = "computable"
    NOT_COMPUTABLE = "not_computable"
    UNKNOWN = "unknown"


class NumericalValidity(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class Disclosure(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNKNOWN = "unknown"


class ScientificAdequacy(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_AS_INDICATIVE = "accepted as indicative"
    NOT_ACCEPTED = "not accepted"
    UNKNOWN = "unknown"


class OfficialAdmissibility(StrEnum):
    ADMISSIBLE = "admissible"
    NOT_ADMISSIBLE = "not_admissible"
    PENDING = "pending"


@dataclass(frozen=True)
class EvidenceScope:
    product: str
    reach: str
    member: str | None
    period: Interval
    intended_use: str

    def __post_init__(self) -> None:
        for name in ("product", "reach", "intended_use"):
            _text(getattr(self, name), name)
        if self.member is not None:
            _text(self.member, "member")
        if not isinstance(self.period, Interval):
            raise TypeError("period must be Interval")


@dataclass(frozen=True)
class UseRestriction:
    """A supplied reason prohibits named uses within the finding's exact scope."""

    reason: str
    prohibited_uses: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.reason, "reason")
        _texts(self.prohibited_uses, "prohibited_uses")
        if not self.prohibited_uses:
            raise ValueError("a restriction must identify prohibited uses")


@dataclass(frozen=True)
class EvidenceFindings:
    """Independent supplied findings; numerical success never promotes acceptance."""

    scope: EvidenceScope
    provenance: Provenance
    computability: Computability
    numerical_validity: NumericalValidity
    disclosure: Disclosure
    scientific_adequacy: ScientificAdequacy
    official_admissibility: OfficialAdmissibility
    reasons: tuple[str, ...]
    restrictions: tuple[UseRestriction, ...] = ()

    def __post_init__(self) -> None:
        for name, kind in (
            ("scope", EvidenceScope),
            ("provenance", Provenance),
            ("computability", Computability),
            ("numerical_validity", NumericalValidity),
            ("disclosure", Disclosure),
            ("scientific_adequacy", ScientificAdequacy),
            ("official_admissibility", OfficialAdmissibility),
        ):
            if not isinstance(getattr(self, name), kind):
                raise TypeError(f"{name} must be {kind.__name__}")
        _texts(self.reasons, "reasons")
        if not isinstance(self.restrictions, tuple) or any(
            not isinstance(restriction, UseRestriction) for restriction in self.restrictions
        ):
            raise TypeError("restrictions must be a tuple of UseRestriction")


def permitted_use(findings: EvidenceFindings, scope: EvidenceScope) -> Check:
    """Check supplied scientific permission at exactly the requested scope.

    No finding transfers to another product, reach, member, period or use.
    Official admissibility is retained separately and never promoted here.
    """
    if not isinstance(findings, EvidenceFindings) or not isinstance(scope, EvidenceScope):
        raise TypeError("permitted_use requires EvidenceFindings and EvidenceScope")
    check_id = "permitted_use"
    if findings.scope != scope:
        return Check(check_id, CheckFinding.UNKNOWN, ("no evidence finding for the exact requested scope",))
    prohibitions = tuple(
        restriction.reason for restriction in findings.restrictions if scope.intended_use in restriction.prohibited_uses
    )
    failures = (
        (findings.computability is Computability.NOT_COMPUTABLE, "not computable for requested scope"),
        (findings.numerical_validity is NumericalValidity.INVALID, "numerically invalid for requested scope"),
        (
            findings.scientific_adequacy is ScientificAdequacy.NOT_ACCEPTED,
            "scientifically not accepted for requested use",
        ),
    )
    failed_reasons = prohibitions + tuple(reason for failed, reason in failures if failed)
    if failed_reasons:
        return Check(check_id, CheckFinding.FAIL, failed_reasons + findings.reasons)
    if (
        findings.computability is Computability.UNKNOWN
        or findings.numerical_validity is NumericalValidity.UNKNOWN
        or findings.scientific_adequacy is ScientificAdequacy.UNKNOWN
    ):
        return Check(check_id, CheckFinding.UNKNOWN, ("required evidence unresolved",) + findings.reasons)
    return Check(check_id, CheckFinding.PASS, findings.reasons)


def warmup_restrictions(provenance: Provenance, interval: Interval) -> tuple[str, ...]:
    """Return the supplied exclusion when any part of the requested interval overlaps."""
    if any(interval.start < excluded.end and excluded.start < interval.end for excluded in provenance.excluded_warmup):
        return ("requested interval overlaps excluded warm-up",)
    return ()
