from __future__ import annotations

import csv
import hashlib
import json
import re
import tempfile
import time
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import duckdb
from mortgage_risk.vendor_codes import code_issue

SCHEMA_VERSION = "sample-ingest-v1"
SCHEMA_REFERENCE = "Fannie Mae Single-Family Loan Performance sample; glossary and file layout verified for the inspected fields."
EXPECTED_FIELD_COUNT = 108
HISTORICAL_SCHEMA_VERSION = "historical-ingest-v1"
HISTORICAL_SCHEMA_REFERENCE = (
    "Fannie Mae Single-Family Loan Performance historical quarter; official glossary defines a 113-field layout "
    "with field 1 Reference Pool ID, field 2 Loan Identifier, field 3 Monthly Reporting Period, and fields 111-113 as Classic FICO values."
)
HISTORICAL_EXPECTED_FIELD_COUNT = 113
POSITION_MAP = {
    "loan_id": 1,
    "reporting_month": 2,
    "original_upb": 9,
    "current_actual_upb": 11,
    "delinquency_status": 39,
    "modification_flag": 41,
    "zero_balance_code": 43,
}
HISTORICAL_POSITION_MAP = {
    "reference_pool_id": 0,
    "loan_id": 1,
    "reporting_month": 2,
    "current_actual_upb": 11,
    "zero_balance_code": 43,
    "origination_fico": 110,
    "issuance_fico": 111,
    "current_fico": 112,
}


def detect_vendor_schema(row: list[str] | tuple[str, ...]) -> str:
    """Return the canonical schema name for a parser-supported Fannie Mae row shape."""
    width = len(row)
    if width == EXPECTED_FIELD_COUNT:
        return "sample-v1"
    if width == HISTORICAL_EXPECTED_FIELD_COUNT:
        return "historical-v1"
    raise ValueError(f"Unexpected vendor row width: expected 108 or 113 fields, got {width}.")


def iter_vendor_rows(path: str | Path):
    """Yield nonblank rows and the detected schema without storing the whole file in memory."""
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.reader(handle, delimiter="|"), start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            yield row_number, row, detect_vendor_schema(row)


def parse_reporting_month(value: Any) -> tuple[date | None, str | None]:
    """Parse the vendor MMYYYY reporting period into a date at month start."""
    raw = str(value).strip() if value is not None else ""
    if raw == "":
        return None, "missing_reporting_period"
    if not re.fullmatch(r"\d{6}", raw):
        return None, "invalid_reporting_period"
    month = int(raw[:2])
    year = int(raw[2:])
    if month < 1 or month > 12:
        return None, "invalid_reporting_period"
    try:
        return date(year, month, 1), None
    except ValueError:
        return None, "invalid_reporting_period"


def _normalize_decimal(raw: Any, *, field_name: str) -> Decimal | None:
    text = str(raw).strip() if raw is not None else ""
    if text == "":
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric value for {field_name}: {raw!r}") from exc


def _read_nonblank_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows: list[list[str]] = []
        for row_number, row in enumerate(csv.reader(handle, delimiter="|"), start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            rows.append([cell for cell in row])
    if not rows:
        raise ValueError(f"No nonblank rows found in sample file: {path}")
    expected = len(rows[0])
    for row_number, row in enumerate(rows, start=1):
        if len(row) != expected:
            raise ValueError(
                f"Unexpected field count in row {row_number}: expected {expected}, got {len(row)}. "
                f"Source file: {path}"
            )
    if expected != EXPECTED_FIELD_COUNT:
        raise ValueError(
            f"Unexpected vendor field count: expected {EXPECTED_FIELD_COUNT}, got {expected}. "
            f"Source file: {path}"
        )
    return rows


def _row_value(row: list[str], position: int) -> str:
    if position < 0 or position >= len(row):
        raise ValueError(f"Requested field index {position} is out of range for row length {len(row)}")
    return row[position]


def _sha256_stream_file(path: str | Path) -> str:
    """Compute a SHA-256 digest without reading the full file into memory."""
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reconcile_rows(records: list[dict[str, Any]]) -> dict[str, Any]:
    loan_month_keys: list[tuple[str, str]] = []
    duplicate_keys: list[tuple[str, str]] = []
    monthly_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    monthly_nonzero_balance_count: dict[str, int] = defaultdict(int)
    monthly_missing_balance_count: dict[str, int] = defaultdict(int)
    monthly_zero_balance_count: dict[str, int] = defaultdict(int)

    for record in records:
        loan_id = record["loan_id"]
        reporting_month = record["reporting_month"]
        key = (loan_id, reporting_month.isoformat()[:7])
        loan_month_keys.append(key)
        monthly_totals[reporting_month.isoformat()[:7]] += record["current_actual_upb"] or Decimal("0")
        if record["current_actual_upb"] is None:
            monthly_missing_balance_count[reporting_month.isoformat()[:7]] += 1
        elif record["current_actual_upb"] == Decimal("0"):
            monthly_zero_balance_count[reporting_month.isoformat()[:7]] += 1
        else:
            monthly_nonzero_balance_count[reporting_month.isoformat()[:7]] += 1

    counts = defaultdict(int)
    for key in loan_month_keys:
        counts[key] += 1
    duplicate_keys.extend([key for key, value in counts.items() if value > 1])

    balance_totals = {
        month: str(total.quantize(Decimal("0.01"))) for month, total in sorted(monthly_totals.items())
    }
    return {
        "distinct_loan_count": len({record["loan_id"] for record in records}),
        "distinct_month_count": len({record["reporting_month"].isoformat()[:7] for record in records}),
        "duplicate_loan_month_keys": len(duplicate_keys),
        "duplicate_key_examples": [list(key) for key in duplicate_keys[:10]],
        "monthly_balance_totals": balance_totals,
        "monthly_nonzero_balance_count": dict(sorted(monthly_nonzero_balance_count.items())),
        "monthly_missing_balance_count": dict(sorted(monthly_missing_balance_count.items())),
        "monthly_zero_balance_count": dict(sorted(monthly_zero_balance_count.items())),
    }


def select_deterministic_loan_ids(path: str | Path, *, max_loans: int | None = 1000) -> list[str]:
    """Select a stable, outcome-independent subset of loan identifiers from the source file."""
    if max_loans is not None and max_loans <= 0:
        raise ValueError("max_loans must be positive or None for full-file selection.")

    unique_ids: set[str] = set()
    for _, row, _ in iter_vendor_rows(path):
        loan_id = row[1].strip() if len(row) > 1 else ""
        if loan_id:
            unique_ids.add(loan_id)

    if not unique_ids:
        raise ValueError(f"No loan identifiers found in source file: {path}")

    if max_loans is None:
        return sorted(unique_ids)
    return sorted(unique_ids)[:max_loans]


def ingest_sample_file(
    sample_path: str | Path,
    *,
    db_path: str | Path,
    parquet_path: str | Path,
) -> dict[str, Any]:
    """Read the vendor sample into a validated monthly table and parquet output."""
    sample_file = Path(sample_path)
    db_target = Path(db_path)
    parquet_target = Path(parquet_path)
    db_target.parent.mkdir(parents=True, exist_ok=True)
    parquet_target.parent.mkdir(parents=True, exist_ok=True)

    raw_rows = _read_nonblank_rows(sample_file)
    row_count = len(raw_rows)
    checksum = _sha256_stream_file(sample_file)

    parsed_rows: list[dict[str, Any]] = []
    date_conversion_failures = 0
    missing_loan_id = 0
    missing_reporting_month = 0
    missing_original_upb = 0
    missing_current_upb = 0
    zero_original_upb = 0
    zero_current_upb = 0
    invalid_original_upb = 0
    invalid_current_upb = 0

    for row_number, row in enumerate(raw_rows, start=1):
        source_record_number = row_number
        loan_id_raw = _row_value(row, POSITION_MAP["loan_id"]) if len(row) > POSITION_MAP["loan_id"] else ""
        loan_id = loan_id_raw.strip()
        if loan_id == "":
            missing_loan_id += 1
            raise ValueError(f"Missing loan_id on source record {source_record_number} in {sample_file}")

        reporting_raw = _row_value(row, POSITION_MAP["reporting_month"]) if len(row) > POSITION_MAP["reporting_month"] else ""
        reporting_month, err = parse_reporting_month(reporting_raw)
        if err is not None:
            if err == "missing_reporting_period":
                missing_reporting_month += 1
            date_conversion_failures += 1
            raise ValueError(
                f"Invalid reporting period on source record {source_record_number}: {reporting_raw!r}"
            )

        original_upb_raw = _row_value(row, POSITION_MAP["original_upb"]) if len(row) > POSITION_MAP["original_upb"] else ""
        current_upb_raw = _row_value(row, POSITION_MAP["current_actual_upb"]) if len(row) > POSITION_MAP["current_actual_upb"] else ""

        original_upb = _normalize_decimal(original_upb_raw, field_name="original_upb")
        current_upb = _normalize_decimal(current_upb_raw, field_name="current_actual_upb")

        if original_upb is None:
            missing_original_upb += 1
        elif original_upb == Decimal("0"):
            zero_original_upb += 1
        if current_upb is None:
            missing_current_upb += 1
        elif current_upb == Decimal("0"):
            zero_current_upb += 1

        delinquency_status_raw = _row_value(row, POSITION_MAP["delinquency_status"]) if len(row) > POSITION_MAP["delinquency_status"] else ""
        modification_flag_raw = _row_value(row, POSITION_MAP["modification_flag"]) if len(row) > POSITION_MAP["modification_flag"] else ""
        zero_balance_code_raw = _row_value(row, POSITION_MAP["zero_balance_code"]) if len(row) > POSITION_MAP["zero_balance_code"] else ""

        record = {
            "source_filename": sample_file.name,
            "source_record_number": source_record_number,
            "loan_id": loan_id,
            "reporting_month": reporting_month,
            "reporting_month_text": reporting_raw,
            "original_upb": original_upb,
            "original_upb_raw": original_upb_raw,
            "current_actual_upb": current_upb,
            "current_actual_upb_raw": current_upb_raw,
            "delinquency_status": delinquency_status_raw.strip() or None,
            "delinquency_status_raw": delinquency_status_raw,
            "modification_flag": modification_flag_raw.strip() or None,
            "modification_flag_raw": modification_flag_raw,
            "zero_balance_code": zero_balance_code_raw.strip() or None,
            "zero_balance_code_raw": zero_balance_code_raw,
        }
        parsed_rows.append(record)

    if len(parsed_rows) != row_count:
        raise ValueError(
            "Row count mismatch before and after parse: "
            f"raw={row_count}, parsed={len(parsed_rows)}"
        )

    reconciliation = _reconcile_rows(parsed_rows)
    result = {
        "schema_version": SCHEMA_VERSION,
        "schema_reference": SCHEMA_REFERENCE,
        "source_path": str(sample_file),
        "source_checksum_sha256": checksum,
        "raw_nonblank_records": row_count,
        "parsed_records": len(parsed_rows),
        "output_rows": len(parsed_rows),
        "distinct_loan_count": reconciliation["distinct_loan_count"],
        "distinct_month_count": reconciliation["distinct_month_count"],
        "duplicate_loan_month_keys": reconciliation["duplicate_loan_month_keys"],
        "duplicate_key_examples": reconciliation["duplicate_key_examples"],
        "date_conversion_failures": date_conversion_failures,
        "missing_loan_id_count": missing_loan_id,
        "missing_reporting_period_count": missing_reporting_month,
        "missing_original_upb_count": missing_original_upb,
        "missing_current_upb_count": missing_current_upb,
        "zero_original_upb_count": zero_original_upb,
        "zero_current_upb_count": zero_current_upb,
        "monthly_balance_totals": reconciliation["monthly_balance_totals"],
        "monthly_key_balance_counts": {
            "nonzero": reconciliation["monthly_nonzero_balance_count"],
            "missing": reconciliation["monthly_missing_balance_count"],
            "zero": reconciliation["monthly_zero_balance_count"],
        },
        "min_reporting_month": min(record["reporting_month"] for record in parsed_rows).isoformat(),
        "max_reporting_month": max(record["reporting_month"] for record in parsed_rows).isoformat(),
        "overall_status": "pass",
        "record_mismatches": 0,
    }

    if result["duplicate_loan_month_keys"] != 0 or result["date_conversion_failures"] != 0:
        result["overall_status"] = "failed"
        result["record_mismatches"] = 1

    conn = duckdb.connect(str(db_target))
    conn.execute(
        """
        CREATE TABLE sample_monthly (
            source_filename VARCHAR,
            source_record_number BIGINT,
            loan_id VARCHAR,
            reporting_month DATE,
            reporting_month_text VARCHAR,
            original_upb DECIMAL(18,2),
            original_upb_raw VARCHAR,
            current_actual_upb DECIMAL(18,2),
            current_actual_upb_raw VARCHAR,
            delinquency_status VARCHAR,
            delinquency_status_raw VARCHAR,
            modification_flag VARCHAR,
            modification_flag_raw VARCHAR,
            zero_balance_code VARCHAR,
            zero_balance_code_raw VARCHAR
        )
        """
    )

    conn.executemany(
        """
        INSERT INTO sample_monthly (
            source_filename,
            source_record_number,
            loan_id,
            reporting_month,
            reporting_month_text,
            original_upb,
            original_upb_raw,
            current_actual_upb,
            current_actual_upb_raw,
            delinquency_status,
            delinquency_status_raw,
            modification_flag,
            modification_flag_raw,
            zero_balance_code,
            zero_balance_code_raw
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                record["source_filename"],
                record["source_record_number"],
                record["loan_id"],
                record["reporting_month"],
                record["reporting_month_text"],
                record["original_upb"],
                record["original_upb_raw"],
                record["current_actual_upb"],
                record["current_actual_upb_raw"],
                record["delinquency_status"],
                record["delinquency_status_raw"],
                record["modification_flag"],
                record["modification_flag_raw"],
                record["zero_balance_code"],
                record["zero_balance_code_raw"],
            )
            for record in parsed_rows
        ],
    )

    row_count_db = conn.execute("SELECT COUNT(*) FROM sample_monthly").fetchone()[0]
    if row_count_db != len(parsed_rows):
        raise ValueError(f"DuckDB row count mismatch: expected {len(parsed_rows)}, found {row_count_db}")

    conn.execute(f"COPY sample_monthly TO '{parquet_target.as_posix()}' (FORMAT PARQUET)")
    conn.close()

    result["database_path"] = str(db_target)
    result["parquet_path"] = str(parquet_target)
    result["database_row_count"] = row_count_db
    result["parquet_exists"] = parquet_target.exists()
    result["duckdb_output_verified"] = result["parquet_exists"] and db_target.exists()
    result["schema_version"] = SCHEMA_VERSION
    return result


def ingest_historical_file(
    historical_path: str | Path,
    *,
    selected_loan_ids: list[str] | None = None,
    max_loans: int = 1000,
    db_path: str | Path,
    parquet_path: str | Path,
) -> dict[str, Any]:
    """Read a bounded subset of a vendor historical quarter into a versioned monthly table."""
    source_path = Path(historical_path)
    db_target = Path(db_path)
    parquet_target = Path(parquet_path)
    db_target.parent.mkdir(parents=True, exist_ok=True)
    parquet_target.parent.mkdir(parents=True, exist_ok=True)

    progress: list[dict[str, Any]] = []
    source_scan_start = time.perf_counter()

    if selected_loan_ids is None:
        selected_loan_ids = select_deterministic_loan_ids(source_path, max_loans=max_loans)
    selected_set = set(selected_loan_ids)
    if not selected_set:
        raise ValueError("At least one selected loan identifier is required for a historical pilot.")

    checksum_hex = _sha256_stream_file(source_path)

    monthly_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    monthly_nonzero_balance_count: dict[str, int] = defaultdict(int)
    monthly_missing_balance_count: dict[str, int] = defaultdict(int)
    monthly_zero_balance_count: dict[str, int] = defaultdict(int)
    loan_ids_seen: set[str] = set()
    months_seen: set[str] = set()
    key_counts: dict[tuple[str, str], int] = defaultdict(int)
    duplicate_key_examples: list[tuple[str, str]] = []
    retained_record_count = 0
    invalid_reporting_period_count = 0
    unknown_code_counts: dict[str, int] = defaultdict(int)
    source_nonblank_records = 0

    csv_temp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        prefix="historical_bulk_",
        suffix=".csv",
        dir=db_target.parent,
        delete=False,
    )
    bulk_csv_path = Path(csv_temp.name)
    csv_writer = csv.writer(csv_temp, delimiter=",", quoting=csv.QUOTE_MINIMAL)

    try:
        for row_number, row, schema_name in iter_vendor_rows(source_path):
            source_nonblank_records += 1
            if schema_name != "historical-v1":
                raise ValueError(
                    f"Unexpected vendor schema for historical ingestion: row {row_number} in {source_path} has {len(row)} fields, expected 113."
                )

            loan_id = row[1].strip() if len(row) > 1 else ""
            if not loan_id or loan_id not in selected_set:
                continue

            reporting_raw = row[2].strip() if len(row) > 2 else ""
            reporting_month, err = parse_reporting_month(reporting_raw)
            if err is not None:
                invalid_reporting_period_count += 1
                raise ValueError(f"Invalid reporting period on historical row {row_number}: {reporting_raw!r}")

            current_upb_raw = row[HISTORICAL_POSITION_MAP["current_actual_upb"]] if len(row) > HISTORICAL_POSITION_MAP["current_actual_upb"] else ""
            current_upb = _normalize_decimal(current_upb_raw, field_name="current_actual_upb")
            original_upb_raw = row[9] if len(row) > 9 else ""
            original_upb = _normalize_decimal(original_upb_raw, field_name="original_upb")
            delinquency_status_raw = row[39] if len(row) > 39 else ""
            modification_flag_raw = row[41] if len(row) > 41 else ""
            zero_balance_code_raw = row[43] if len(row) > 43 else ""

            for field, value in (("delinquency_status", delinquency_status_raw), ("modification_flag", modification_flag_raw), ("zero_balance_code", zero_balance_code_raw)):
                if code_issue(field, value):
                    unknown_code_counts[f"{field}:{value.strip()}"] += 1

            month_key = reporting_month.isoformat()[:7]
            loan_ids_seen.add(loan_id)
            months_seen.add(month_key)
            key_counts[(loan_id, month_key)] += 1
            retained_record_count += 1
            monthly_totals[month_key] += current_upb or Decimal("0")
            if current_upb is None:
                monthly_missing_balance_count[month_key] += 1
            elif current_upb == Decimal("0"):
                monthly_zero_balance_count[month_key] += 1
            else:
                monthly_nonzero_balance_count[month_key] += 1

            csv_writer.writerow([
                source_path.name,
                row_number,
                loan_id,
                reporting_month.isoformat(),
                reporting_raw,
                "" if original_upb is None else format(original_upb, "f"),
                original_upb_raw,
                "" if current_upb is None else format(current_upb, "f"),
                current_upb_raw,
                delinquency_status_raw.strip() or "",
                delinquency_status_raw,
                modification_flag_raw.strip() or "",
                modification_flag_raw,
                zero_balance_code_raw.strip() or "",
                zero_balance_code_raw,
            ])
        
        progress.append({
            "stage": "scan_source",
            "elapsed_seconds": round(time.perf_counter() - source_scan_start, 6),
            "processed_rows": source_nonblank_records,
            "details": "Validated vendor rows and prepared accepted historical records for bulk load.",
        })
        csv_temp.flush()
        csv_temp.close()

        conn = duckdb.connect(str(db_target))
        conn.execute("PRAGMA memory_limit='4GB'")
        conn.execute(f"PRAGMA temp_directory='{(db_target.parent / 'duckdb_tmp').as_posix()}'")
        (db_target.parent / 'duckdb_tmp').mkdir(parents=True, exist_ok=True)
        conn.execute(
            """
            CREATE TABLE historical_monthly (
                source_filename VARCHAR,
                source_record_number BIGINT,
                loan_id VARCHAR,
                reporting_month DATE,
                reporting_month_text VARCHAR,
                original_upb DECIMAL(18,2),
                original_upb_raw VARCHAR,
                current_actual_upb DECIMAL(18,2),
                current_actual_upb_raw VARCHAR,
                delinquency_status VARCHAR,
                delinquency_status_raw VARCHAR,
                modification_flag VARCHAR,
                modification_flag_raw VARCHAR,
                zero_balance_code VARCHAR,
                zero_balance_code_raw VARCHAR
            )
            """
        )

        load_start = time.perf_counter()
        escaped_path = str(bulk_csv_path).replace("'", "''")
        conn.execute(
            f"COPY historical_monthly FROM '{escaped_path}' (FORMAT CSV, HEADER FALSE, DELIM ',', QUOTE '\"', ESCAPE '\"', NULL '')"
        )
        row_count_db = conn.execute("SELECT COUNT(*) FROM historical_monthly").fetchone()[0]
        if row_count_db != retained_record_count:
            raise ValueError(f"DuckDB row count mismatch: expected {retained_record_count}, found {row_count_db}")
        progress.append({
            "stage": "bulk_load",
            "elapsed_seconds": round(time.perf_counter() - load_start, 6),
            "processed_rows": row_count_db,
            "details": "Bulk-load validated records into the historical monthly table via COPY from staging CSV.",
        })

        parquet_start = time.perf_counter()
        conn.execute(f"COPY historical_monthly TO '{parquet_target.as_posix()}' (FORMAT PARQUET)")
        progress.append({
            "stage": "write_parquet",
            "elapsed_seconds": round(time.perf_counter() - parquet_start, 6),
            "processed_rows": row_count_db,
            "details": "Persist the typed historical table to Parquet.",
        })

        if retained_record_count == 0:
            raise ValueError(f"No rows retained for selected loan IDs in {source_path}.")

        duplicate_keys = [key for key, count in key_counts.items() if count > 1]
        duplicate_key_examples = duplicate_keys[:10]
        if duplicate_key_examples:
            duplicate_key_examples = [list(key) for key in duplicate_key_examples]

        min_month = min(months_seen) if months_seen else None
        max_month = max(months_seen) if months_seen else None
        result = {
            "schema_version": HISTORICAL_SCHEMA_VERSION,
            "schema_reference": HISTORICAL_SCHEMA_REFERENCE,
            "source_path": str(source_path),
            "source_checksum_sha256": checksum_hex,
            "raw_nonblank_records": source_nonblank_records,
            "selected_loan_ids": sorted(selected_set),
            "selected_loan_count": len(selected_set),
            "retained_record_count": retained_record_count,
            "distinct_loan_count": len(loan_ids_seen),
            "distinct_month_count": len(months_seen),
            "duplicate_loan_month_keys": len(duplicate_keys),
            "duplicate_key_examples": duplicate_key_examples,
            "min_reporting_month": min_month,
            "max_reporting_month": max_month,
            "monthly_balance_totals": {month: str(total.quantize(Decimal('0.01'))) for month, total in sorted(monthly_totals.items())},
            "monthly_key_balance_counts": {
                "nonzero": dict(sorted(monthly_nonzero_balance_count.items())),
                "missing": dict(sorted(monthly_missing_balance_count.items())),
                "zero": dict(sorted(monthly_zero_balance_count.items())),
            },
            "unknown_code_counts": dict(sorted(unknown_code_counts.items())),
            "invalid_reporting_period_count": invalid_reporting_period_count,
            "overall_status": "pass" if len(duplicate_keys) == 0 and invalid_reporting_period_count == 0 and not unknown_code_counts else "failed",
            "record_mismatches": 0,
            "progress": progress,
        }

        conn.close()
        result["database_path"] = str(db_target)
        result["dataset_path"] = str(parquet_target)
        result["database_row_count"] = row_count_db
        result["parquet_exists"] = parquet_target.exists()
        result["duckdb_output_verified"] = result["parquet_exists"] and db_target.exists()
        result["source_schema"] = "historical-v1"
        result["selected_loan_ids"] = sorted(selected_set)
        return result
    finally:
        if bulk_csv_path.exists():
            bulk_csv_path.unlink(missing_ok=True)


def _build_parser() -> Any:
    parser = __import__("argparse").ArgumentParser(description="Ingest the Fannie Mae sample into a validated monthly table.")
    parser.add_argument("--input", default="data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv")
    parser.add_argument("--db", default=None)
    parser.add_argument("--parquet", default=None)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    result = ingest_sample_file(
        args.input,
        db_path=args.db or "artifacts/runs/sample_ingest/sample_monthly.db",
        parquet_path=args.parquet or "artifacts/runs/sample_ingest/sample_monthly.parquet",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
