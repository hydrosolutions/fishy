"""calendar_example : CompleteDailyVolumes → CalendarMappingDemonstration.

Run from the repository with ``uv run python examples/calendar_mapping.py``.
These synthetic values illustrate arithmetic, not accepted reference evidence.
"""

from fractions import Fraction

from fishy.pattern_calendar import AccountingYear, half_volume_marker, map_calendar, shift_year


def main() -> None:
    source = AccountingYear(2023, 1, 0)
    target = AccountingYear(2024, 1, 0)
    volumes = tuple(Fraction(day == 31) for day in range(source.days))
    mapped = map_calendar(source, volumes, target)
    assert mapped[31:33] == (Fraction(28, 29), Fraction(1, 29))
    assert sum(mapped, Fraction()) == 1
    print(f"Mapped February days 1 and 2: {mapped[31]}, {mapped[32]}")
    print(f"Mapped annual total: {sum(mapped, Fraction())}")

    early = tuple(Fraction(day in (99, 100)) for day in range(source.days))
    late = tuple(Fraction(day in (103, 104)) for day in range(source.days))
    first = half_volume_marker(early, 90, 120)
    second = half_volume_marker(late, 90, 120)
    assert first is not None and second is not None
    median = (first + second) / 2
    print(f"Half-volume markers in days: {first / 86400}, {second / 86400}")
    print(f"Median in days: {median / 86400}")
    print(f"Shifts in days: {(median - first) / 86400}, {(median - second) / 86400}")

    # A delay needs previous-year data. Even a known dry edge cannot prove
    # that an unknown adjacent year was dry. No wrapping or zero filling.
    unsupported = shift_year(source, early, source, median - first)
    assert unsupported.shares is None
    print(f"Without adjacent data: {unsupported.reason}")


if __name__ == "__main__":
    main()
