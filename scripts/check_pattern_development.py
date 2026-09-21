"""reaggregate : DevelopmentCaseRows → DevelopmentSummary (pure).

Check retained development arithmetic, not hydrological or ecological validation.
Only main opens caller-supplied source files. No source data is bundled here.
"""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean


def reaggregate(rows: list[dict[str, str]]) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[row["station"], row["era"]].append(row)
    results = []
    for (station, era), cases in sorted(groups.items()):
        short = [c for c in cases if c["training_years"] == "14"]
        long = [c for c in cases if c["training_years"] == "50"]
        if len(short) + len(long) != len(cases):
            raise ValueError("unexpected training period")
        if {c["validation_year"] for c in short} != {c["validation_year"] for c in long}:
            raise ValueError("training comparisons need identical validation years")
        if any(c["dry"] not in ("True", "False") for c in cases):
            raise ValueError("invalid dry-case state")
        if len({(c["training_years"], c["validation_year"]) for c in cases}) != len(cases):
            raise ValueError("duplicate development case")
        mae14 = fmean(float(c["conditional_daily_shape_mae"]) for c in short)
        mae50 = fmean(float(c["conditional_daily_shape_mae"]) for c in long)
        benchmark = fmean(float(c["benchmark_daily_shape_mae"]) for c in long)
        dry = [c for c in long if c["dry"] == "True"]
        results.append(
            {
                "station": station,
                "era": era,
                "validation_years": len(long),
                "mae14": mae14,
                "mae50": mae50,
                "benchmark50": benchmark,
                "change_50_vs_14_percent": (mae50 / mae14 - 1) * 100,
                "change_50_vs_benchmark_percent": (mae50 / benchmark - 1) * 100,
                "dry_n": len(dry),
                "dry_min7_overestimates": sum(float(c["conditional_signed_min7_error"]) > 0 for c in dry),
            }
        )
    if not results:
        raise ValueError("empty development case table")
    return {
        "selected_rows": len(rows),
        "groups": results,
        "all_four_beat_benchmark": all(g["mae50"] < g["benchmark50"] for g in results),
        "three_of_four_improve_with_longer_record": sum(g["mae50"] < g["mae14"] for g in results),
        "dry_total": sum(g["dry_n"] for g in results),
        "dry_overestimates": sum(g["dry_min7_overestimates"] for g in results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--expected-csv-sha256", required=True)
    args = parser.parse_args()
    actual_hash = hashlib.sha256(args.cases.read_bytes()).hexdigest()
    if actual_hash != args.expected_csv_sha256:
        raise ValueError("CSV differs from declared authoritative package hash")
    with args.cases.open(newline="") as stream:
        actual = reaggregate(list(csv.DictReader(stream)))
    expected = json.loads(args.summary.read_text())
    tolerance = 1e-12
    for key, value in actual.items():
        if key != "groups" and value != expected[key]:
            raise ValueError(f"summary disagreement: {key}")
    if len(actual["groups"]) != len(expected["groups"]):
        raise ValueError("summary group count differs")
    for observed, reference in zip(actual["groups"], expected["groups"], strict=True):
        for key, value in observed.items():
            if isinstance(value, float):
                if not abs(value - reference[key]) <= tolerance:
                    raise ValueError(f"summary group disagrees: {key}")
            elif value != reference[key]:
                raise ValueError(f"summary group disagrees: {key}")
    print(
        json.dumps(
            {
                "numerical_summary": "pass",
                "selected_rows": actual["selected_rows"],
                "dry_total": actual["dry_total"],
                "dry_overestimates": actual["dry_overestimates"],
                "benchmark_groups_improved": sum(g["mae50"] < g["benchmark50"] for g in actual["groups"]),
                "longer_training_groups_improved": actual["three_of_four_improve_with_longer_record"],
                "arithmetic_tolerance": tolerance,
                "actual_csv_sha256": actual_hash,
                "actual_summary_sha256": hashlib.sha256(args.summary.read_bytes()).hexdigest(),
                "embedded_source_sha256": expected["source_cases_sha256"],
                "embedded_source_hash_check": "pass"
                if actual_hash == expected["source_cases_sha256"]
                else "fail: stale source attribution",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
