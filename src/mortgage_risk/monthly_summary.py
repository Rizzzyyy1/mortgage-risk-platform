from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from mortgage_risk import __version__


def read_latest_ingest_run(base_dir: Path | str = "artifacts/runs/sample_ingest") -> tuple[Path, Path, dict[str, Any]]:
    base_path = Path(base_dir)
    runs = [run_path for run_path in base_path.glob("*") if run_path.is_dir()]
    if not runs:
        raise FileNotFoundError(f"No successful sample-ingest runs found under {base_path}")

    def run_sort_key(run_path: Path) -> tuple[datetime, str]:
        metadata_path = run_path / "sample_ingest_result.json"
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                timestamp = metadata.get("timestamp_utc")
                if timestamp:
                    return (datetime.fromisoformat(timestamp.replace("Z", "+00:00")), run_path.name)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        return (datetime.fromtimestamp(run_path.stat().st_mtime, tz=timezone.utc), run_path.name)

    latest = max(runs, key=run_sort_key)
    metadata_path = latest / "sample_ingest_result.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing ingestion metadata: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    db_path = Path(metadata["database_path"])
    parquet_path = Path(metadata["dataset_path"])
    return latest, db_path, metadata


def read_selected_ingest_run(base_dir: Path | str = "artifacts/runs/sample_ingest", run_id: str | None = None) -> tuple[Path, Path, dict[str, Any]]:
    base_path = Path(base_dir)
    if run_id is None:
        return read_latest_ingest_run(base_path)

    selected = base_path / run_id
    metadata_path = selected / "sample_ingest_result.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Selected ingestion run '{run_id}' is missing metadata at {metadata_path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    db_path = Path(metadata["database_path"])
    parquet_path = Path(metadata["dataset_path"])
    return selected, db_path, metadata


def _month_key(value: Any) -> str:
    return str(value).split("T", 1)[0][:7]


def _sum_known_balances(records: list[dict[str, Any]]) -> Decimal:
    total = Decimal("0")
    for row in records:
        value = row.get("current_actual_upb")
        if value is not None:
            total += Decimal(str(value))
    return total


def _month_index(value: Any) -> int:
    month = value if isinstance(value, datetime) else value
    if month is None:
        raise ValueError("Month value is required for bridge calculations.")
    return month.year * 12 + month.month


def _money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _compute_bridge_residual(
    prior_total: Decimal,
    current_total: Decimal,
    continuing_change: Decimal,
    newly_observed_total: Decimal,
    missing_to_known_total: Decimal,
    disappearing_total: Decimal,
    known_to_missing_total: Decimal,
) -> Decimal:
    bridge_total = (
        continuing_change
        + newly_observed_total
        + missing_to_known_total
        + disappearing_total
        + known_to_missing_total
    )
    return _money(current_total - prior_total - bridge_total)


def _resolve_monthly_table_name(conn: duckdb.DuckDBPyConnection) -> str:
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    matches = tables & {"historical_monthly", "sample_monthly"}
    if len(matches) != 1:
        raise ValueError("Expected exactly one supported monthly table; selection is ambiguous or absent.")
    return matches.pop()


def _calculate_balance_bridge(conn: duckdb.DuckDBPyConnection, table_name: str | None = None) -> tuple[list[dict[str, Any]], Decimal]:
    table_name = table_name or _resolve_monthly_table_name(conn)
    month_rows = conn.execute(
        f"SELECT DISTINCT reporting_month FROM {table_name} WHERE reporting_month IS NOT NULL ORDER BY reporting_month"
    ).fetchall()
    bridge_rows: list[dict[str, Any]] = []
    max_abs = Decimal("0.00")
    tolerance = Decimal("0.01")

    for index in range(len(month_rows) - 1):
        prior_month = month_rows[index][0]
        current_month = month_rows[index + 1][0]
        if _month_index(current_month) - _month_index(prior_month) != 1:
            continue

        values = conn.execute(f"""
            WITH p AS (SELECT loan_id, current_actual_upb AS b FROM {table_name} WHERE reporting_month = ?),
                 c AS (SELECT loan_id, current_actual_upb AS b FROM {table_name} WHERE reporting_month = ?)
            SELECT coalesce(sum(p.b),0), coalesce(sum(c.b),0),
              coalesce(sum(CASE WHEN p.b IS NOT NULL AND c.b IS NOT NULL THEN c.b-p.b ELSE 0 END),0),
              coalesce(sum(CASE WHEN p.loan_id IS NULL THEN c.b ELSE 0 END),0),
              coalesce(sum(CASE WHEN p.loan_id IS NOT NULL AND p.b IS NULL THEN c.b ELSE 0 END),0),
              -coalesce(sum(CASE WHEN c.loan_id IS NULL THEN p.b ELSE 0 END),0),
              -coalesce(sum(CASE WHEN c.loan_id IS NOT NULL AND c.b IS NULL THEN p.b ELSE 0 END),0)
            FROM p FULL OUTER JOIN c USING (loan_id)
        """, [prior_month, current_month]).fetchone()
        prior_total, current_total, continuing_change, newly_observed_total, missing_to_known_total, disappearing_total, known_to_missing_total = values
        residual = _compute_bridge_residual(
            prior_total,
            current_total,
            continuing_change,
            newly_observed_total,
            missing_to_known_total,
            disappearing_total,
            known_to_missing_total,
        )
        bridge_total = (
            continuing_change
            + newly_observed_total
            + missing_to_known_total
            + disappearing_total
            + known_to_missing_total
        )
        max_abs = max(max_abs, abs(residual))

        bridge_rows.append({
            "prior_month": prior_month.isoformat(),
            "current_month": current_month.isoformat(),
            "prior_total_known_balance": str(prior_total),
            "current_total_known_balance": str(current_total),
            "balance_change_continuing_known": str(_money(continuing_change)),
            "newly_observed_known_balance": str(_money(newly_observed_total)),
            "missing_to_known_balance": str(_money(missing_to_known_total)),
            "disappearing_known_balance": str(_money(disappearing_total)),
            "known_to_missing_balance": str(_money(known_to_missing_total)),
            "bridge_component_total": str(_money(bridge_total)),
            "residual": str(residual),
            "status": "pass" if abs(residual) <= tolerance else "failed",
        })

    return bridge_rows, max_abs


def build_monthly_portfolio_summary(db_path: str | Path, *, output_dir: str | Path) -> dict[str, Any]:
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"DuckDB file does not exist: {db_file}")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    run_dir = output_root / f"monthly_summary_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_file), read_only=True)
    conn.execute("SET memory_limit='2GB'")
    conn.execute("SET threads=2")
    table_name = _resolve_monthly_table_name(conn)

    summary_query = f"""
        WITH base AS (
            SELECT
                loan_id,
                reporting_month,
                current_actual_upb,
                delinquency_status,
                modification_flag,
                zero_balance_code
            FROM {table_name}
        )
        SELECT
            reporting_month,
            COUNT(DISTINCT loan_id) AS observed_loan_count,
            COUNT(DISTINCT CASE WHEN current_actual_upb IS NOT NULL THEN loan_id END) AS loans_with_known_current_balance,
            COUNT(DISTINCT CASE WHEN current_actual_upb IS NULL THEN loan_id END) AS loans_with_missing_current_balance,
            COUNT(DISTINCT CASE WHEN current_actual_upb = 0 THEN loan_id END) AS loans_with_zero_current_balance,
            SUM(CASE WHEN current_actual_upb IS NOT NULL THEN current_actual_upb ELSE 0 END) AS total_known_current_balance,
            AVG(CASE WHEN current_actual_upb IS NOT NULL THEN current_actual_upb END) AS avg_known_current_balance
        FROM base
        GROUP BY reporting_month
        ORDER BY reporting_month
    """
    monthly_rows = conn.execute(summary_query).fetchall()

    category_query = f"""
        WITH base AS (
            SELECT
                loan_id,
                reporting_month,
                current_actual_upb,
                COALESCE(NULLIF(TRIM(delinquency_status), ''), 'missing') AS delinquency_status,
                COALESCE(NULLIF(TRIM(modification_flag), ''), 'missing') AS modification_flag,
                COALESCE(NULLIF(TRIM(zero_balance_code), ''), 'missing') AS zero_balance_code
            FROM {table_name}
        )
        SELECT
            reporting_month,
            delinquency_status AS category_name,
            'delinquency' AS category_type,
            COUNT(DISTINCT loan_id) AS category_count,
            SUM(CASE WHEN current_actual_upb IS NOT NULL THEN current_actual_upb ELSE 0 END) AS category_balance_total
        FROM base
        GROUP BY reporting_month, delinquency_status
        UNION ALL
        SELECT
            reporting_month,
            modification_flag AS category_name,
            'modification' AS category_type,
            COUNT(DISTINCT loan_id) AS category_count,
            SUM(CASE WHEN current_actual_upb IS NOT NULL THEN current_actual_upb ELSE 0 END) AS category_balance_total
        FROM base
        GROUP BY reporting_month, modification_flag
        UNION ALL
        SELECT
            reporting_month,
            zero_balance_code AS category_name,
            'termination' AS category_type,
            COUNT(DISTINCT loan_id) AS category_count,
            SUM(CASE WHEN current_actual_upb IS NOT NULL THEN current_actual_upb ELSE 0 END) AS category_balance_total
        FROM base
        GROUP BY reporting_month, zero_balance_code
        ORDER BY reporting_month, category_type, category_name
    """
    category_rows = conn.execute(category_query).fetchall()

    diagnostics_query = f"""
      WITH ordered AS (
        SELECT loan_id, reporting_month, current_actual_upb,
          lag(current_actual_upb) OVER w prev_balance,
          lag(reporting_month) OVER w prev_month,
          lead(reporting_month) OVER w next_month
        FROM {table_name} WINDOW w AS (PARTITION BY loan_id ORDER BY reporting_month)
      )
      SELECT o.*, flags.diagnostic_flag FROM ordered o,
      LATERAL (VALUES
        (CASE WHEN current_actual_upb IS NULL THEN 'missing_balance' END),
        (CASE WHEN current_actual_upb < 0 THEN 'negative_balance' END),
        (CASE WHEN date_diff('month',prev_month,reporting_month)=1 AND current_actual_upb>prev_balance THEN 'balance_increase' END),
        (CASE WHEN date_diff('month',prev_month,reporting_month)>1 THEN 'monthly_gap' END)
      ) flags(diagnostic_flag) WHERE diagnostic_flag IS NOT NULL
    """
    diagnostics_path = run_dir / 'diagnostics.parquet'
    escaped_diagnostics = str(diagnostics_path).replace("'", "''")
    conn.execute(f"COPY ({diagnostics_query}) TO '{escaped_diagnostics}' (FORMAT PARQUET)")
    diagnostic_counts = [dict(zip(('flag','rows','affected_loans'), row)) for row in conn.execute(
        "SELECT diagnostic_flag,count(*),count(distinct loan_id) FROM read_parquet(?) GROUP BY 1 ORDER BY 1", [str(diagnostics_path)]).fetchall()]
    diagnostics_rows = conn.execute("SELECT * FROM read_parquet(?) ORDER BY loan_id,reporting_month,diagnostic_flag LIMIT 100",[str(diagnostics_path)]).fetchall()

    source_totals_query = f"""
        SELECT reporting_month, SUM(current_actual_upb) AS total_known_current_balance
        FROM {table_name}
        WHERE current_actual_upb IS NOT NULL
        GROUP BY reporting_month
        ORDER BY reporting_month
    """
    source_totals = {row[0].isoformat(): Decimal(str(row[1])) for row in conn.execute(source_totals_query).fetchall()}
    bridge_rows, max_abs_residual = _calculate_balance_bridge(conn, table_name)
    conn.close()

    monthly_summary = []
    for row in monthly_rows:
        month_key = row[0].isoformat()
        known_balance_total = Decimal(str(row[5]))
        source_total = source_totals.get(month_key, Decimal("0"))
        monthly_summary.append({
            "reporting_month": month_key,
            "observed_loan_count": int(row[1]),
            "loans_with_known_current_balance": int(row[2]),
            "loans_with_missing_current_balance": int(row[3]),
            "loans_with_zero_current_balance": int(row[4]),
            "total_known_current_balance": str(known_balance_total),
            "avg_known_current_balance": str(row[6]),
            "avg_known_balance_denominator": int(row[2]) if row[2] else 0,
            "reconciliation_to_source_total": str(known_balance_total == source_total),
        })

    category_summary = []
    for row in category_rows:
        category_summary.append({
            "reporting_month": row[0].isoformat(),
            "category_name": row[1],
            "category_type": row[2],
            "category_count": int(row[3]),
            "category_balance_total": str(row[4]),
        })

    diagnostics = []
    for row in diagnostics_rows:
        diagnostics.append({
            "loan_id": row[0],
            "reporting_month": row[1].isoformat(),
            "current_actual_upb": str(row[2]) if row[2] is not None else None,
            "prev_balance": str(row[3]) if row[3] is not None else None,
            "prev_month": row[4].isoformat() if row[4] is not None else None,
            "next_month": row[5].isoformat() if row[5] is not None else None,
            "diagnostic_flag": row[6],
        })

    source_total_mismatches = [
        item for item in monthly_summary if item["reconciliation_to_source_total"] == "False"
    ]
    bridge_failures = [item for item in bridge_rows if item["status"] == "failed"]
    tolerance = Decimal("0.01")
    bridge_status = "pass" if not bridge_failures else "failed"
    summary_payload = {
        "schema_version": "monthly-summary-v1",
        "package_version": __version__,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_run_id": db_file.parent.parent.name if db_file.parent.name == "sample_ingest" else db_file.parent.name,
        "input_database_path": str(db_file),
        "output_directory": str(run_dir),
        "monetary_precision": "0.01",
        "reconciliation_tolerance": str(tolerance),
        "bridge_max_abs_residual": str(max_abs_residual),
        "bridge_reconciliation_status": bridge_status,
        "source_total_reconciliation_status": "pass" if not source_total_mismatches else "failed",
        "overall_status": "pass" if not source_total_mismatches and not bridge_failures else "failed",
        "reconciliation_mismatches": source_total_mismatches,
        "bridge_failures": bridge_failures,
        "balance_bridge": bridge_rows,
        "monthly_summary": monthly_summary,
        "category_detail": category_summary,
        "diagnostics": diagnostics,
        "diagnostics_preview_limit": 100,
        "diagnostic_counts": diagnostic_counts,
        "diagnostics_path": str(diagnostics_path.resolve()),
        "observed_population_note": "Observed input cohort only; reported balances are not validated economic exposure or representative market estimates.",
        "eligible_reporting_portfolio_note": "No reporting-portfolio subset is applied in this stage. The output remains the observed sample population as defined in target_definitions.md.",
    }

    (run_dir / "monthly_portfolio_summary.json").write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    return summary_payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Summarize the monthly loan performance sample and exposure diagnostics.")
    parser.add_argument("--db", default=None, help="Path to the validated sample-monthly DuckDB file.")
    parser.add_argument("--output-dir", default="artifacts/runs/monthly_summary", help="Directory for summary outputs.")
    args = parser.parse_args()

    latest_run, db_path, _ = read_latest_ingest_run()
    result = build_monthly_portfolio_summary(args.db or db_path, output_dir=args.output_dir)
    print(json.dumps({
        "status": "pass",
        "run_id": latest_run.name,
        "records": len(result["monthly_summary"]),
        "output_dir": result["output_directory"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
