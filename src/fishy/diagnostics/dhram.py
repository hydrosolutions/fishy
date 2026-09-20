"""DHRAM classification : HydrologicalChanges × SupplementaryEvidence → AlterationRisk.

Black et al. (2005), Tables 3–4. This operation consumes attributable
source-defined summary indicators; it does not resolve conflicting descriptor
membership in that paper or generate a natural reference.
"""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class SupplementaryFinding(StrEnum):
    """Evidence for one source-defined anthropogenic alteration question."""

    CONFIRMED = "confirmed"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SupplementaryEvidence:
    """Independent evidence, not facts inferred from daily mean discharge."""

    subdaily_variation: SupplementaryFinding
    flow_cessation: SupplementaryFinding
    source: str

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("Supplementary evidence requires a source or missing-evidence reason")
        for finding in (self.subdaily_variation, self.flow_cessation):
            if not isinstance(finding, SupplementaryFinding):
                raise TypeError("Supplementary findings must be explicit domain states")


@dataclass(frozen=True)
class HydrologicalChanges:
    """Ten nonnegative percent changes, ordered 1a,1b,...,5a,5b.

    Missing summary indicators are None with an attributable reason. A caller
    must name the source profile of the underlying descriptor calculations.
    """

    percentages: tuple[float | None, ...]
    reasons: tuple[str, ...]
    profile: str

    def __post_init__(self) -> None:
        if not isinstance(self.percentages, tuple) or not isinstance(self.reasons, tuple):
            raise TypeError("Summary values and reasons must be immutable tuples")
        if len(self.percentages) != 10 or len(self.reasons) != 10:
            raise ValueError("DHRAM requires exactly ten summary indicators")
        if not self.profile.strip():
            raise ValueError("Descriptor source profile is required")
        for value, reason in zip(self.percentages, self.reasons, strict=True):
            if value is None:
                if not reason.strip():
                    raise ValueError("An unavailable summary indicator requires a reason")
            elif not isfinite(value) or value < 0:
                raise ValueError("Summary changes must be finite nonnegative percentages")


@dataclass(frozen=True)
class AlterationRisk:
    """Source risk class bounds preserve missing computation and evidence."""

    impact_points: tuple[int | None, ...]
    points_lower: int
    points_upper: int
    class_lower: int
    class_upper: int
    profile: str
    supplementary: SupplementaryEvidence
    reasons: tuple[str, ...]

    @property
    def classification(self) -> int | None:
        """A unique supported class, including a saturated class5 bound."""
        return self.class_lower if self.class_lower == self.class_upper else None


# Visually checked against the supplied original Table3, printed page433.
THRESHOLDS = (
    (19.9, 43.7, 67.5),
    (29.4, 97.6, 165.7),
    (42.9, 88.2, 133.4),
    (84.5, 122.7, 160.8),
    (7.0, 21.2, 35.5),
    (33.4, 50.3, 67.3),
    (36.4, 65.1, 93.8),
    (30.5, 76.1, 121.6),
    (46.0, 82.7, 119.4),
    (49.1, 79.9, 110.6),
)


def _risk_class(points: int) -> int:
    if points == 0:
        return 1
    if points <= 4:
        return 2
    if points <= 10:
        return 3
    if points <= 20:
        return 4
    return 5


def classify_dhram(changes: HydrologicalChanges, evidence: SupplementaryEvidence) -> AlterationRisk:
    """Apply literal threshold exceedances and independent +1 adjustments.

    Unknown indicators span zero to three points. Unknown supplementary
    findings span zero to one class. Bounds are epistemic possibilities,
    not scientific uncertainty intervals or a completeness claim.
    """
    points = tuple(
        None if value is None else sum(value > threshold for threshold in limits)
        for value, limits in zip(changes.percentages, THRESHOLDS, strict=True)
    )
    lower = sum(value for value in points if value is not None)
    upper = lower + 3 * points.count(None)
    findings = (evidence.subdaily_variation, evidence.flow_cessation)
    confirmed = findings.count(SupplementaryFinding.CONFIRMED)
    unknown = findings.count(SupplementaryFinding.UNKNOWN)
    reasons = tuple(reason for reason in changes.reasons if reason)
    if unknown:
        reasons += ("supplementary_evidence_incomplete",)
    return AlterationRisk(
        points,
        lower,
        upper,
        min(5, _risk_class(lower) + confirmed),
        min(5, _risk_class(upper) + confirmed + unknown),
        changes.profile,
        evidence,
        reasons,
    )
