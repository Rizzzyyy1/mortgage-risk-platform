#!/usr/bin/env python3
"""Inspect the local Fannie Mae sample file and capture reusable evidence.

This is intentionally limited to file-format and sample-profile inspection. It does not
attempt to interpret the official vendor codebook or perform modeling.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import median


COMMON_DELIMS = [",", "|", "\t", ";"]


def detect_encoding(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1", "cp1252"):
        try:
            with path.open("r", encoding=enc, newline="") as fh:
                fh.read(512)
            return enc
        except Exception:
            continue
    return "unknown"


def detect_delimiter(path: Path, sample_lines: list[str]) -> str | None:
    counts = {d: sum(line.count(d) for line in sample_lines[:25]) for d in COMMON_DELIMS}
    best = max(counts, key=counts.get)
    if counts[best] == 0:
        return None
    return best


def read_rows(path: Path):
    with path.open("r", encoding=detect_encoding(path), newline="") as fh:
        return [row for row in csv.reader(fh, delimiter="|") if row and any(cell.strip() for cell in row)]


def parse_reporting_period(value: str):
    if value is None:
        return None, "missing_reporting_period"
    value = str(value).strip()
    if value == "":
        return None, "missing_reporting_period"
    if not re.fullmatch(r"\d{6}", value):
        return None, "invalid_reporting_period"
    month = int(value[:2])
    year = int(value[2:])
    if month < 1 or month > 12:
        return None, "invalid_reporting_period"
    try:
        return date(year, month, 1), None
    except ValueError:
        return None, "invalid_reporting_period"


def summarize(path: Path) -> dict:
    raw_bytes = path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    sample = raw_bytes.decode(detect_encoding(path), errors="replace").splitlines()
    delimiter = detect_delimiter(path, sample)
    rows = read_rows(path)

    row_count = len(rows)
    blank_row_count = sum(1 for line in sample if not line.strip())
    field_counts = Counter(len(row) for row in rows)

    loan_id_values = []
    for row in rows:
        if len(row) > 2 and row[1].strip():
            loan_id_values.append(row[1])
        elif len(row) > 1 and row[0].strip():
            loan_id_values.append(row[0])
    loan_ids = sorted(set(loan_id_values))

    valid_periods = []
    invalid_periods = []
    loan_to_periods = defaultdict(list)
    records_by_key = defaultdict(list)
    for row in rows:
        if len(row) <= 2:
            invalid_periods.append((row, "missing_row_structure"))
            continue
        loan_id = row[1] if len(row) > 1 else row[0]
        reporting_value = row[2]
        reporting_date, error = parse_reporting_period(reporting_value)
        if error is not None:
            invalid_periods.append((loan_id, reporting_value, error))
            continue
        valid_periods.append((loan_id, reporting_date))
        loan_to_periods[loan_id].append(reporting_date)
        records_by_key[(loan_id, reporting_date.isoformat()[:7])].append(row)

    distinct_months = sorted({period for _, period in valid_periods})
    month_iso = [period.isoformat()[:7] for period in distinct_months]
    month_counts = Counter(period.isoformat()[:7] for _, period in valid_periods)
    duplicates = defaultdict(list)
    for row in rows:
        if len(row) <= 2:
            continue
        key = (row[1] if len(row) > 1 else row[0], row[2])
        duplicates[key].append(row)
    duplicate_keys = {key: value for key, value in duplicates.items() if len(value) > 1}
    conflicting_duplicate_keys = []
    for key, value in duplicate_keys.items():
        row_set = {tuple(item) for item in value}
        if len(row_set) > 1:
            conflicting_duplicate_keys.append(key)

    loan_counts = Counter(row[1] if len(row) > 1 else row[0] for row in rows)
    obs_counts = sorted(loan_counts.values())

    earliest = min(distinct_months) if distinct_months else None
    latest = max(distinct_months) if distinct_months else None
    summary = {
        "path": str(path),
        "size_bytes": len(raw_bytes),
        "sha256": digest,
        "encoding": detect_encoding(path),
        "delimiter": delimiter,
        "line_ending": "CRLF" if b"\r\n" in raw_bytes else "LF" if b"\n" in raw_bytes else "CR",
        "header_row_exists": False,
        "record_count": row_count,
        "blank_record_count": blank_row_count,
        "field_count_consistent": len(field_counts) == 1,
        "field_count_distribution": dict(sorted(field_counts.items())),
        "schema_verification_status": "provisional: physical read verified; official mapping not confirmed from vendor documentation",
        "schema_source": "https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data",
        "distinct_loan_count": len(loan_ids),
        "loan_observations_min": min(obs_counts) if obs_counts else 0,
        "loan_observations_median": median(obs_counts) if obs_counts else 0,
        "loan_observations_max": max(obs_counts) if obs_counts else 0,
        "earliest_reporting_period": earliest.isoformat() if earliest else None,
        "latest_reporting_period": latest.isoformat() if latest else None,
        "earliest_reporting_period_iso": earliest.isoformat() if earliest else None,
        "latest_reporting_period_iso": latest.isoformat() if latest else None,
        "distinct_month_count": len(distinct_months),
        "distinct_reporting_periods": month_iso,
        "duplicate_loan_month_keys": len(duplicate_keys),
        "conflicting_duplicate_loan_month_keys": len(conflicting_duplicate_keys),
        "invalid_reporting_period_count": len(invalid_periods),
        "invalid_reporting_period_examples": invalid_periods[:10],
        "semantic_findings_provisional": True,
        "physical_findings_valid": True,
        "blank_or_invalid_value_status": "blank values appear as empty strings; invalid reporting periods are counted explicitly without replacement",
        "severity_by_position": {},
    }
    return summary


def write_outputs(summary: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir.joinpath("inspection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    out_dir.joinpath("schema_reference.txt").write_text(
        "Official schema reference: https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data\n"
        "Current status: physical file facts are verified; official schema mapping remains provisional until the glossary/file-layout document or downloaded vendor package is inspected.\n"
        "Do not interpret field names as official without this evidence.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the local Fannie Mae sample file.")
    parser.add_argument("--path", default="data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv", help="Sample CSV file to inspect.")
    parser.add_argument("--out-dir", default=None, help="Directory for output JSON and reference notes.")
    args = parser.parse_args()

    path = Path(args.path)
    summary = summarize(path)
    out_dir = Path(args.out_dir) if args.out_dir else Path("artifacts/runs") / "phase1a_sample_inspection"
    write_outputs(summary, out_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
