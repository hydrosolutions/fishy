"""interval_duration : GregorianInterval → ElapsedSeconds (exact, UTC-normalised)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from fractions import Fraction


class Calendar(StrEnum):
    GREGORIAN = "gregorian"


@dataclass(frozen=True, order=True)
class Interval:
    """Half-open bounds; timezone interpretation belongs to the importing caller."""

    start: datetime
    end: datetime
    calendar: Calendar = Calendar.GREGORIAN

    def __post_init__(self) -> None:
        if not isinstance(self.calendar, Calendar):
            raise TypeError("calendar must be Calendar")
        for name in ("start", "end"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("interval bounds require explicit timezone interpretation")
            object.__setattr__(self, name, value.astimezone(UTC))
        if self.end <= self.start:
            raise ValueError("interval must have positive elapsed duration")

    @property
    def seconds(self) -> Fraction:
        delta = self.end - self.start
        return Fraction((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds, 1000000)
