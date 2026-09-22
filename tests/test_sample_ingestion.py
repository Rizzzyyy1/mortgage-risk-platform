from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from mortgage_risk.ingestion import ingest_sample_file, parse_reporting_month


def test_parse_reporting_month_handles_mm_yyyy_and_invalid_values():
    parsed, err = parse_reporting_month("082009")
    assert parsed == date(2009, 8, 1)
    assert err is None

    parsed, err = parse_reporting_month("132019")
    assert parsed is None
    assert err == "invalid_reporting_period"

    parsed, err = parse_reporting_month("")
    assert parsed is None
    assert err == "missing_reporting_period"


@pytest.mark.vendor_data
def test_ingest_sample_file_reconciles_vendor_sample(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    sample_path = project_root / "data" / "raw" / "fannie_mae_loan_performance" / "sf-loan-performance-data-sample.csv"

    if not sample_path.exists():
        pytest.skip("Optional vendor integration: local vendor sample is absent")

    db_path = tmp_path / "sample_monthly.db"
    parquet_path = tmp_path / "sample_monthly.parquet"

    result = ingest_sample_file(sample_path, db_path=db_path, parquet_path=parquet_path)

    assert result["raw_nonblank_records"] == 757
    assert result["parsed_records"] == 757
    assert result["output_rows"] == 757
    assert result["distinct_loan_count"] == 8
    assert result["distinct_month_count"] == 132
    assert result["duplicate_loan_month_keys"] == 0
    assert result["date_conversion_failures"] == 0
    assert parquet_path.exists()
    assert db_path.exists()


def test_zero_and_missing_balances_remain_distinct(tmp_path):
    rows = []
    for row_index in range(1, 4):
        row = ["" for _ in range(108)]
        row[1] = f"loan-{row_index:02d}"
        row[2] = "082009"
        row[9] = "100000.00"
        row[11] = "100000.00" if row_index == 1 else "0.00" if row_index == 2 else ""
        row[39] = "00"
        row[41] = "N"
        row[43] = "" if row_index != 3 else "03"
        rows.append("|".join(row))

    csv_path = tmp_path / "zero_missing_sample.csv"
    csv_path.write_text("\n".join(rows), encoding="utf-8-sig")

    result = ingest_sample_file(csv_path, db_path=tmp_path / "zero_missing.db", parquet_path=tmp_path / "zero_missing.parquet")

    assert result["monthly_key_balance_counts"]["zero"] == {"2009-08": 1}
    assert result["monthly_key_balance_counts"]["missing"] == {"2009-08": 1}
    assert result["parsed_records"] == 3


def test_ingest_sample_file_rejects_malformed_rows(tmp_path):
    bad_csv = tmp_path / "bad_sample.csv"
    bad_csv.write_text(
        "\n".join([
            "|900000000001|082009|R|Other|Other||5.375|5.375|55000.00||0.00|240|082009|102009|0|240|240|092029|55|55|1|36|714|",
            "|900000000001|082009|R|Other|Other||5.375|5.375|55000.00||0.00|240|082009|102009|0|240|240|092029|55|55|1|36|714|",
            "|900000000001|badmonth|R|Other|Other||5.375|5.375|55000.00||0.00|240|082009|102009|0|240|240|092029|55|55|1|36|714|",
        ]),
        encoding="utf-8-sig",
    )

    with pytest.raises(ValueError):
        ingest_sample_file(bad_csv, db_path=tmp_path / "bad.db", parquet_path=tmp_path / "bad.parquet")


def test_read_latest_ingest_run_uses_timestamp_not_name(tmp_path):
    older = tmp_path / "run_z"
    newer = tmp_path / "run_a"
    older.mkdir()
    newer.mkdir()

    (older / "sample_ingest_result.json").write_text(
        '{"database_path": "older.db", "dataset_path": "older.parquet", "timestamp_utc": "2024-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )
    (newer / "sample_ingest_result.json").write_text(
        '{"database_path": "newer.db", "dataset_path": "newer.parquet", "timestamp_utc": "2025-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )

    latest_dir, _, _ = __import__("mortgage_risk.monthly_summary", fromlist=["read_latest_ingest_run"]).read_latest_ingest_run(tmp_path)

    assert latest_dir.name == "run_a"
