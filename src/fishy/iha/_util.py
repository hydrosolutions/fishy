"""Internal utility functions for IHA computation."""

import numpy as np
from numpy.typing import NDArray


def rolling_mean(x: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    return np.convolve(x, np.ones(window, dtype=np.float64) / window, mode="valid")


def run_lengths(mask: NDArray[np.bool_]) -> NDArray[np.int64]:
    if len(mask) == 0:
        return np.empty(0, dtype=np.int64)

    padded = np.empty(len(mask) + 2, dtype=np.bool_)
    padded[0] = False
    padded[-1] = False
    padded[1:-1] = mask

    edges = np.flatnonzero(np.diff(padded.view(np.int8)))
    return (edges[1::2] - edges[::2]).astype(np.int64)


def dates_to_components(
    dates: NDArray[np.datetime64],
) -> tuple[NDArray[np.int32], NDArray[np.int32], NDArray[np.int32]]:
    years_dt = dates.astype("datetime64[Y]")
    years = years_dt.astype(np.int32) + 1970

    months_dt = dates.astype("datetime64[M]")
    months = (months_dt - years_dt).astype(np.int32) + 1

    day_of_year = (dates - years_dt).astype(np.int32) + 1

    return (
        years.astype(np.int32),
        months.astype(np.int32),
        day_of_year.astype(np.int32),
    )


def extract_year_slices(
    dates: NDArray[np.datetime64],
) -> list[tuple[int, int, int]]:
    years, _, _ = dates_to_components(dates)
    unique_years = np.unique(years)

    result: list[tuple[int, int, int]] = []
    for year in unique_years:
        year_start = np.datetime64(f"{year}-01-01")
        year_end = np.datetime64(f"{year + 1}-01-01")
        start = int(np.searchsorted(dates, year_start))
        end = int(np.searchsorted(dates, year_end))
        n_days = end - start
        expected = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
        if n_days == expected:
            result.append((int(year), start, end))

    return result
