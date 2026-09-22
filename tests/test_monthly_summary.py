from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import duckdb

from mortgage_risk.cli import run_monthly_summary
from mortgage_risk.monthly_summary import _compute_bridge_residual, build_monthly_portfolio_summary


def _make_synthetic_db(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
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
        INSERT INTO sample_monthly VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("sample.csv", 1, "A", "2024-01-01", "012024", Decimal("100000"), "100000.00", Decimal("100000"), "100000.00", "0", "0", "N", "N", "", ""),
            ("sample.csv", 2, "B", "2024-01-01", "012024", Decimal("75000"), "75000.00", Decimal("75000"), "75000.00", "R", "R", "N", "N", "", ""),
            ("sample.csv", 3, "C", "2024-01-01", "012024", Decimal("50000"), "50000.00", Decimal("0"), "0.00", "missing", "missing", "Y", "Y", "03", "03"),
            ("sample.csv", 4, "A", "2024-02-01", "022024", Decimal("100000"), "100000.00", Decimal("120000"), "120000.00", "0", "0", "N", "N", "", ""),
            ("sample.csv", 5, "B", "2024-02-01", "022024", Decimal("75000"), "75000.00", None, "", "R", "R", "N", "N", "", ""),
            ("sample.csv", 6, "C", "2024-02-01", "022024", Decimal("50000"), "50000.00", Decimal("0"), "0.00", "missing", "missing", "Y", "Y", "03", "03"),
            ("sample.csv", 7, "D", "2024-02-01", "022024", Decimal("60000"), "60000.00", Decimal("60000"), "60000.00", "0", "0", "N", "N", "", ""),
            ("sample.csv", 8, "A", "2024-03-01", "032024", Decimal("100000"), "100000.00", Decimal("120000"), "120000.00", "0", "0", "N", "N", "", ""),
            ("sample.csv", 9, "B", "2024-03-01", "032024", Decimal("75000"), "75000.00", Decimal("45000"), "45000.00", "R", "R", "N", "N", "", ""),
            ("sample.csv", 10, "D", "2024-03-01", "032024", Decimal("60000"), "60000.00", Decimal("55000"), "55000.00", "0", "0", "N", "N", "", ""),
        ],
    )
    conn.close()


def test_monthly_summary_and_diagnostics(tmp_path):
    db_path = tmp_path / "synthetic_sample_monthly.db"
    _make_synthetic_db(db_path)
    output_dir = tmp_path / "summary_output"

    summary = build_monthly_portfolio_summary(db_path, output_dir=output_dir)

    assert summary["monthly_summary"][0]["observed_loan_count"] == 3
    assert summary["monthly_summary"][1]["observed_loan_count"] == 4
    assert summary["monthly_summary"][0]["loans_with_zero_current_balance"] == 1
    assert summary["monthly_summary"][0]["avg_known_balance_denominator"] == 3
    assert any(item["diagnostic_flag"] == "balance_increase" for item in summary["diagnostics"])
    assert any(item["diagnostic_flag"] == "missing_balance" for item in summary["diagnostics"])
    assert summary["input_run_id"] == db_path.parent.name
    assert output_dir.exists()
    assert "monthly_summary_" in str(summary["output_directory"]) 


def test_run_monthly_summary_uses_explicit_input_run(tmp_path):
    db_dir = tmp_path / "artifacts" / "runs" / "sample_ingest" / "run_123"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "sample_monthly.db"
    _make_synthetic_db(db_path)

    (db_dir / "sample_ingest_result.json").write_text(
        '{"database_path": "' + str(db_path) + '", "dataset_path": "' + str(db_dir / "sample_monthly.parquet") + '"}',
        encoding="utf-8",
    )

    result = run_monthly_summary(project_root=tmp_path, input_run="run_123", output_dir=tmp_path / "artifacts" / "runs" / "monthly_summary")

    assert result["input_run_id"] == "run_123"
    assert result["input_db_path"] == str(db_path)
    assert result["overall_status"] == "pass"


def test_balance_bridge_components_and_tolerance(tmp_path):
    db_path = tmp_path / "bridge_sample_monthly.db"
    conn = duckdb.connect(str(db_path))
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
        INSERT INTO sample_monthly VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("sample.csv", 1, "A", "2024-01-01", "012024", Decimal("100000"), "100000.00", Decimal("100"), "100.00", "00", "00", "N", "N", "", ""),
            ("sample.csv", 2, "B", "2024-01-01", "012024", Decimal("50000"), "50000.00", Decimal("0"), "0.00", "00", "00", "N", "N", "", ""),
            ("sample.csv", 3, "D", "2024-01-01", "012024", Decimal("50000"), "50000.00", Decimal("50"), "50.00", "00", "00", "N", "N", "", ""),
            ("sample.csv", 4, "A", "2024-02-01", "022024", Decimal("100000"), "100000.00", Decimal("120"), "120.00", "00", "00", "N", "N", "", ""),
            ("sample.csv", 5, "B", "2024-02-01", "022024", Decimal("50000"), "50000.00", Decimal("0"), "0.00", "00", "00", "N", "N", "", ""),
            ("sample.csv", 6, "C", "2024-02-01", "022024", Decimal("30000"), "30000.00", Decimal("30"), "30.00", "00", "00", "N", "N", "", ""),
            ("sample.csv", 7, "E", "2024-02-01", "022024", Decimal("80000"), "80000.00", Decimal("80"), "80.00", "00", "00", "N", "N", "", ""),
            ("sample.csv", 8, "A", "2024-03-01", "032024", Decimal("100000"), "100000.00", Decimal("120"), "120.00", "00", "00", "N", "N", "", ""),
            ("sample.csv", 9, "B", "2024-03-01", "032024", Decimal("50000"), "50000.00", Decimal("0"), "0.00", "00", "00", "N", "N", "", ""),
            ("sample.csv", 10, "C", "2024-03-01", "032024", Decimal("30000"), "30000.00", Decimal("30"), "30.00", "00", "00", "N", "N", "", ""),
            ("sample.csv", 11, "E", "2024-03-01", "032024", Decimal("80000"), "80000.00", Decimal("80"), "80.00", "00", "00", "N", "N", "", ""),
        ],
    )
    conn.close()

    summary = build_monthly_portfolio_summary(db_path, output_dir=tmp_path / "bridge_output")
    pair = next(item for item in summary["balance_bridge"] if item["prior_month"] == "2024-01-01" and item["current_month"] == "2024-02-01")
    assert pair["balance_change_continuing_known"] == "20.00"
    assert pair["newly_observed_known_balance"] == "110.00"
    assert pair["known_to_missing_balance"] == "0.00"
    assert pair["missing_to_known_balance"] == "0.00"
    assert pair["disappearing_known_balance"] == "-50.00"
    assert pair["bridge_component_total"] == "80.00"
    assert pair["residual"] == "0.00"
    assert summary["bridge_max_abs_residual"] == "0.00"
    assert summary["overall_status"] == "pass"


def test_build_monthly_portfolio_summary_accepts_historical_table_name(tmp_path):
    db_path = tmp_path / "historical_monthly.db"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE historical_monthly (
            loan_id VARCHAR,
            reporting_month DATE,
            current_actual_upb DECIMAL(18,2),
            delinquency_status VARCHAR,
            modification_flag VARCHAR,
            zero_balance_code VARCHAR
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO historical_monthly VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("A", "2024-01-01", Decimal("100.00"), "00", "N", ""),
            ("B", "2024-01-01", Decimal("50.00"), "00", "N", ""),
            ("A", "2024-02-01", Decimal("120.00"), "00", "N", ""),
            ("B", "2024-02-01", Decimal("60.00"), "00", "N", ""),
            ("C", "2024-02-01", Decimal("30.00"), "00", "N", ""),
        ],
    )
    conn.close()

    summary = build_monthly_portfolio_summary(db_path, output_dir=tmp_path / "historical_summary")

    assert summary["overall_status"] == "pass"
    assert [row["reporting_month"] for row in summary["monthly_summary"]] == ["2024-01-01", "2024-02-01"]


def test_balance_bridge_detects_inconsistent_total():
    residual = _compute_bridge_residual(
        prior_total=Decimal("100.00"),
        current_total=Decimal("190.00"),
        continuing_change=Decimal("90.00"),
        newly_observed_total=Decimal("30.00"),
        missing_to_known_total=Decimal("0.00"),
        disappearing_total=Decimal("0.00"),
        known_to_missing_total=Decimal("0.00"),
    )

    assert residual == Decimal("-30.00")
