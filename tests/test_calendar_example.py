"""Run the reader's calendar example through its actual entry point."""

from examples.calendar_mapping import main


def test_calendar_example(capsys) -> None:
    main()
    assert capsys.readouterr().out == (
        "Mapped February days 1 and 2: 28/29, 1/29\n"
        "Mapped annual total: 1\n"
        "Half-volume markers in days: 100, 104\n"
        "Median in days: 102\n"
        "Shifts in days: 2, -2\n"
        "Without adjacent data: missing left adjacent-year context\n"
    )
