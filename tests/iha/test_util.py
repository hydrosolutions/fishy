"""Tests for IHA utility functions."""

import numpy as np

from fishy.iha._util import (
    dates_to_components,
    extract_year_slices,
    rolling_mean,
    run_lengths,
)


class TestRollingMean:
    def test_window_1_is_identity(self) -> None:
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        np.testing.assert_allclose(rolling_mean(x, 1), x)

    def test_known_values(self) -> None:
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        np.testing.assert_allclose(rolling_mean(x, 3), [2.0, 3.0, 4.0])

    def test_output_length(self) -> None:
        x = np.arange(20, dtype=np.float64)
        window = 7
        result = rolling_mean(x, window)
        assert len(result) == len(x) - window + 1

    def test_constant_array(self) -> None:
        x = np.full(10, 5.0)
        result = rolling_mean(x, 3)
        np.testing.assert_allclose(result, np.full(8, 5.0))


class TestRunLengths:
    def test_empty_mask(self) -> None:
        result = run_lengths(np.array([], dtype=np.bool_))
        assert result.dtype == np.int64
        assert len(result) == 0

    def test_all_true(self) -> None:
        result = run_lengths(np.array([True] * 5))
        np.testing.assert_array_equal(result, [5])

    def test_all_false(self) -> None:
        result = run_lengths(np.array([False] * 5))
        assert len(result) == 0

    def test_alternating(self) -> None:
        mask = np.array([True, False, True, False, True])
        np.testing.assert_array_equal(run_lengths(mask), [1, 1, 1])

    def test_known_pattern(self) -> None:
        mask = np.array([True, True, True, False, False, True, True, False, True])
        np.testing.assert_array_equal(run_lengths(mask), [3, 2, 1])

    def test_leading_trailing_false(self) -> None:
        mask = np.array([False, False, True, True, False])
        np.testing.assert_array_equal(run_lengths(mask), [2])


class TestDatesToComponents:
    def test_known_date(self) -> None:
        dates = np.array(["2023-01-15"], dtype="datetime64[D]")
        years, months, doy = dates_to_components(dates)
        assert years[0] == 2023
        assert months[0] == 1
        assert doy[0] == 15

    def test_leap_year_dec_31(self) -> None:
        dates = np.array(["2024-12-31"], dtype="datetime64[D]")
        _, _, doy = dates_to_components(dates)
        assert doy[0] == 366

    def test_non_leap_year_dec_31(self) -> None:
        dates = np.array(["2023-12-31"], dtype="datetime64[D]")
        _, _, doy = dates_to_components(dates)
        assert doy[0] == 365

    def test_multiple_dates(self) -> None:
        dates = np.array(
            ["2022-06-15", "2023-01-01", "2024-03-01"],
            dtype="datetime64[D]",
        )
        years, months, doy = dates_to_components(dates)
        np.testing.assert_array_equal(years, [2022, 2023, 2024])
        np.testing.assert_array_equal(months, [6, 1, 3])
        np.testing.assert_array_equal(doy, [166, 1, 61])


class TestExtractYearSlices:
    def test_complete_year(self) -> None:
        dates = np.arange("2023-01-01", "2024-01-01", dtype="datetime64[D]")
        slices = extract_year_slices(dates)
        assert len(slices) == 1
        year, start, end = slices[0]
        assert year == 2023
        assert end - start == 365

    def test_partial_year_excluded(self) -> None:
        dates = np.arange("2023-01-01", "2023-07-20", dtype="datetime64[D]")
        slices = extract_year_slices(dates)
        assert len(slices) == 0

    def test_multiple_complete_years(self) -> None:
        dates = np.arange("2022-01-01", "2025-01-01", dtype="datetime64[D]")
        slices = extract_year_slices(dates)
        assert len(slices) == 3
        extracted_years = [s[0] for s in slices]
        assert extracted_years == [2022, 2023, 2024]

    def test_leap_year_complete(self) -> None:
        dates = np.arange("2024-01-01", "2025-01-01", dtype="datetime64[D]")
        slices = extract_year_slices(dates)
        assert len(slices) == 1
        year, start, end = slices[0]
        assert year == 2024
        assert end - start == 366

    def test_empty_dates(self) -> None:
        dates = np.array([], dtype="datetime64[D]")
        slices = extract_year_slices(dates)
        assert slices == []
