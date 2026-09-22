from __future__ import annotations

from pathlib import Path

import pytest

from mortgage_risk import cli
from mortgage_risk.ingestion import (
    detect_vendor_schema,
    ingest_historical_file,
    select_deterministic_loan_ids,
)


def _make_sample_row(loan_id: str, reporting_period: str, *, field_count: int = 108) -> list[str]:
    return ["", loan_id, reporting_period] + [""] * (field_count - 3)


def _make_historical_row(loan_id: str, reporting_period: str, *, field_count: int = 113) -> list[str]:
    row = ["", loan_id, reporting_period] + [""] * (field_count - 3)
    row[108] = "7"
    row[109] = "8"
    row[110] = "9"
    row[111] = "10"
    row[112] = "11"
    return row


def test_detect_vendor_schema_handles_sample_and_historical_rows():
    sample_row = _make_sample_row("L-001", "082009")
    historical_row = _make_historical_row("L-001", "082009")

    assert detect_vendor_schema(sample_row) == "sample-v1"
    assert detect_vendor_schema(historical_row) == "historical-v1"

    with pytest.raises(ValueError):
        detect_vendor_schema(["x"] * 99)


def test_select_deterministic_loan_ids_is_stable_for_historical_subset(tmp_path):
    path = tmp_path / "historical.csv"
    rows = []
    for loan_id in ["loan-010", "loan-002", "loan-003", "loan-001"]:
        for reporting_period in ["012010", "022010"]:
            rows.append(_make_historical_row(loan_id, reporting_period))
    path.write_text("\n".join("|".join(row) for row in rows), encoding="utf-8-sig")

    selected = select_deterministic_loan_ids(path, max_loans=2)

    assert selected == ["loan-001", "loan-002"]


def test_ingest_historical_file_streams_selected_loans(tmp_path):
    path = tmp_path / "historical.csv"
    rows = []
    for loan_id in ["loan-001", "loan-002", "loan-999"]:
        for reporting_period in ["012010", "022010"]:
            rows.append(_make_historical_row(loan_id, reporting_period))
    path.write_text("\n".join("|".join(row) for row in rows), encoding="utf-8-sig")

    result = ingest_historical_file(
        path,
        selected_loan_ids=["loan-001", "loan-002"],
        db_path=tmp_path / "historical_monthly.db",
        parquet_path=tmp_path / "historical_monthly.parquet",
    )

    assert result["schema_version"] == "historical-ingest-v1"
    assert result["selected_loan_count"] == 2
    assert result["retained_record_count"] == 4
    assert result["distinct_month_count"] == 2
    assert result["distinct_loan_count"] == 2
    assert (tmp_path / "historical_monthly.db").exists()
    assert (tmp_path / "historical_monthly.parquet").exists()


def test_historical_cli_all_records_mode_keeps_every_eligible_row(tmp_path):
    path = tmp_path / "historical.csv"
    rows = []
    for loan_id in ["loan-001", "loan-002", "loan-003"]:
        for reporting_period in ["012010", "022010"]:
            rows.append(_make_historical_row(loan_id, reporting_period))
    path.write_text("\n".join("|".join(row) for row in rows), encoding="utf-8-sig")

    code = cli.main([
        "historical-ingest",
        "--input",
        str(path),
        "--output-dir",
        str(tmp_path / "historical_run"),
        "--all-records",
    ])

    assert code == 0
    run_dir = tmp_path / "historical_run"
    assert run_dir.exists()
    assert any((run_dir / child / "historical_ingest_result.json").exists() for child in run_dir.iterdir() if child.is_dir())


def test_ingest_historical_file_reports_stage_progress(tmp_path):
    path = tmp_path / "historical.csv"
    rows = []
    for loan_id in ["loan-001", "loan-002"]:
        for reporting_period in ["012010", "022010"]:
            rows.append(_make_historical_row(loan_id, reporting_period))
    path.write_text("\n".join("|".join(row) for row in rows), encoding="utf-8-sig")

    result = ingest_historical_file(
        path,
        selected_loan_ids=["loan-001", "loan-002"],
        db_path=tmp_path / "historical_monthly.db",
        parquet_path=tmp_path / "historical_monthly.parquet",
    )

    assert "progress" in result
    assert any(event["stage"] == "bulk_load" for event in result["progress"])
    assert any(event["stage"] == "write_parquet" for event in result["progress"])
