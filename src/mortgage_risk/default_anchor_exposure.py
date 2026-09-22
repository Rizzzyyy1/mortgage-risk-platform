"""Milestone 2: default-anchor exposure. For every default-proxy episode (loss_workout_linkage
v2), retains the reported balance, masking/terminal status and exposure-eligibility reason at
the *original default anchor month only* (never at resolution or any other month), reusing the
accepted exposure_eligibility.parquet categories unchanged. This does not substitute original
balance for missing/masked exposure, does not treat masked/missing exposure as zero, does not
reclassify unresolved masking ages 0/6, and does not use a terminal-month zero UPB as anchor
exposure. It additionally carries a separately named, explicitly aged "prior supported balance"
proxy (the most recent eligible reported balance at or before the anchor) for loans whose anchor
month itself is not directly usable; this proxy is never presented as exact anchor exposure.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint

# Anchor-row classification, in priority order. 'terminal_same_month' is this module's own label
# (not an exposure_eligibility.py category): it flags a default anchor whose own row is already
# the terminal/disposition row, so the general eligibility rule excludes it from
# usable_reported_exposure even though a raw reported balance may still be present. Every other
# label is the accepted exposure_eligibility_reason value, reused unchanged.
ANCHOR_CLASSIFICATION_SQL = """
CASE
  WHEN e.exposure_eligibility_reason='terminal_record' AND e.reporting_month=w.resolution_month THEN 'terminal_same_month'
  ELSE e.exposure_eligibility_reason
END
"""

PRIOR_BALANCE_SQL = """
WITH ordered AS (
  SELECT loan_id, reporting_month, usable_reported_exposure,
    last_value(usable_reported_exposure IGNORE NULLS) OVER (
      PARTITION BY loan_id ORDER BY reporting_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS prior_supported_balance,
    last_value(CASE WHEN usable_reported_exposure IS NOT NULL THEN reporting_month END IGNORE NULLS) OVER (
      PARTITION BY loan_id ORDER BY reporting_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS prior_supported_balance_month
  FROM exposure_eligibility
)
SELECT * FROM ordered
"""


def run(root):
    root = Path(root).resolve()
    start = time.perf_counter()
    eligibility_dir = root / 'artifacts/runs/exposure_eligibility/7b7177c3473345d091dd1cd19d24799e'
    workout_dir = root / 'artifacts/runs/loss_workout_linkage/b2ebdeb7319a4a6486c84b4ad02414f1'
    eligibility_result = json.loads((eligibility_dir / 'eligibility_result.json').read_text())
    if eligibility_result['engineering_status'] != 'pass':
        raise ValueError('Input exposure-eligibility run not accepted')
    workout_result = json.loads((workout_dir / 'workout_linkage_result.json').read_text())
    if workout_result['status'] != 'pass':
        raise ValueError('Input v2 workout-linkage run not accepted')
    out = root / 'artifacts/runs/default_anchor_exposure' / uuid.uuid4().hex
    out.mkdir(parents=True)
    conn = duckdb.connect(str(out / 'exposure.db'))
    conn.execute("SET memory_limit='2GB'")
    conn.execute('SET threads=2')

    def lit(path):
        return str(path).replace("'", "''")

    conn.execute(f"CREATE VIEW exposure_eligibility AS SELECT * FROM read_parquet('{lit(eligibility_dir / 'exposure_eligibility.parquet')}')")
    conn.execute(f"CREATE VIEW workout_episodes AS SELECT * FROM read_parquet('{lit(workout_dir / 'workout_episodes.parquet')}')")
    conn.execute(f"CREATE VIEW prior_balance AS {PRIOR_BALANCE_SQL}")

    default_count = conn.execute('SELECT count(*) FROM workout_episodes').fetchone()[0]
    duplicate_defaults = conn.execute('SELECT count(*) - count(DISTINCT loan_id) FROM workout_episodes').fetchone()[0]
    unmatched_anchor_rows = conn.execute("""
        SELECT count(*) FROM workout_episodes w
        ANTI JOIN exposure_eligibility e ON w.loan_id = e.loan_id AND w.anchor_month = e.reporting_month
    """).fetchone()[0]

    conn.execute(f"""
        CREATE TABLE anchor_exposure AS
        SELECT w.loan_id, w.anchor_month, w.category AS workout_category, w.resolution_month,
          w.has_loss_fields, e.current_actual_upb AS anchor_current_actual_upb,
          e.masking_status AS anchor_masking_status,
          e.terminal_record_status AS anchor_terminal_record_status,
          e.exposure_eligibility_reason AS anchor_exposure_eligibility_reason,
          ({ANCHOR_CLASSIFICATION_SQL}) AS anchor_exposure_classification,
          p.prior_supported_balance, p.prior_supported_balance_month,
          date_diff('month', p.prior_supported_balance_month, w.anchor_month) AS prior_supported_balance_age_months
        FROM workout_episodes w
        JOIN exposure_eligibility e ON w.loan_id = e.loan_id AND w.anchor_month = e.reporting_month
        JOIN prior_balance p ON w.loan_id = p.loan_id AND w.anchor_month = p.reporting_month
    """)
    conn.execute(f"COPY anchor_exposure TO '{lit(out / 'anchor_exposure.parquet')}' (FORMAT PARQUET)")

    joined_count = conn.execute('SELECT count(*) FROM anchor_exposure').fetchone()[0]
    duplicate_joined = conn.execute('SELECT count(*) - count(DISTINCT loan_id) FROM anchor_exposure').fetchone()[0]
    negative_proxy_age = conn.execute(
        'SELECT count(*) FROM anchor_exposure WHERE prior_supported_balance_age_months < 0'
    ).fetchone()[0]

    def classification_breakdown(where=''):
        rows = conn.execute(f"""
            SELECT anchor_exposure_classification, count(*) loans,
              count(*) FILTER(WHERE prior_supported_balance IS NOT NULL) with_prior_balance_proxy,
              round(avg(prior_supported_balance_age_months) FILTER(WHERE anchor_exposure_classification!='eligible_positive_reported_balance' AND prior_supported_balance IS NOT NULL), 2) avg_proxy_age_months_when_needed
            FROM anchor_exposure {where} GROUP BY 1 ORDER BY 1
        """).fetchall()
        return [{'classification': c, 'loans': n, 'with_prior_balance_proxy': p, 'avg_proxy_age_months_when_needed': a} for c, n, p, a in rows]

    all_breakdown = classification_breakdown()
    disposed_breakdown = classification_breakdown("WHERE workout_category='disposed_credit_exit'")
    directly_usable_all = sum(r['loans'] for r in all_breakdown if r['classification'] == 'eligible_positive_reported_balance')
    directly_usable_disposed = sum(r['loans'] for r in disposed_breakdown if r['classification'] == 'eligible_positive_reported_balance')
    proxy_available_no_direct_all = conn.execute("""
        SELECT count(*) FROM anchor_exposure
        WHERE anchor_exposure_classification!='eligible_positive_reported_balance' AND prior_supported_balance IS NOT NULL
    """).fetchone()[0]
    no_exposure_evidence_all = conn.execute("""
        SELECT count(*) FROM anchor_exposure
        WHERE anchor_exposure_classification!='eligible_positive_reported_balance' AND prior_supported_balance IS NULL
    """).fetchone()[0]

    # A small, manually traceable sample: one loan per classification, printed into the result
    # for direct inspection rather than only aggregate counts.
    sample = conn.execute("""
        SELECT DISTINCT ON (anchor_exposure_classification) loan_id, anchor_month, workout_category,
          anchor_current_actual_upb, anchor_masking_status, anchor_terminal_record_status,
          anchor_exposure_classification, prior_supported_balance, prior_supported_balance_age_months
        FROM anchor_exposure ORDER BY anchor_exposure_classification, loan_id
    """).fetchall()
    sample_columns = [d[0] for d in conn.description]
    sample_rows = [dict(zip(sample_columns, r)) for r in sample]

    checks = {
        'default_count': default_count,
        'duplicate_defaults_in_workout_input': duplicate_defaults,
        'unmatched_anchor_rows': unmatched_anchor_rows,
        'joined_count': joined_count,
        'joined_matches_population': joined_count == default_count,
        'duplicate_joined_rows': duplicate_joined,
        'negative_proxy_age_months_found': negative_proxy_age,
        'no_look_ahead_confirmed': negative_proxy_age == 0,
    }
    status = 'pass' if (
        not checks['duplicate_defaults_in_workout_input'] and not checks['unmatched_anchor_rows']
        and checks['joined_matches_population'] and not checks['duplicate_joined_rows']
        and checks['no_look_ahead_confirmed']
    ) else 'failed'

    result = {
        'status': status,
        'scope': 'Reported balance, masking status, terminal status and exposure-eligibility reason at the ORIGINAL default anchor month only, for every workout-linkage v2 default episode. A separately named prior-supported-balance proxy is also reported with its age, never as exact anchor exposure. No severity/LGD, no exposure model, no substituted or imputed balance.',
        'checks': checks,
        'classification_breakdown_all_defaults': all_breakdown,
        'classification_breakdown_disposed_credit_exit_only': disposed_breakdown,
        'coverage_summary': {
            'all_defaults': default_count,
            'directly_usable_at_anchor': directly_usable_all,
            'directly_usable_share': round(directly_usable_all / default_count, 4),
            'prior_balance_proxy_available_when_anchor_not_usable': proxy_available_no_direct_all,
            'no_exposure_evidence_at_or_before_anchor': no_exposure_evidence_all,
            'disposed_credit_exit_loans': len([r for r in disposed_breakdown]) and sum(r['loans'] for r in disposed_breakdown),
            'disposed_credit_exit_directly_usable_at_anchor': directly_usable_disposed,
            'disposed_credit_exit_directly_usable_share': round(directly_usable_disposed / sum(r['loans'] for r in disposed_breakdown), 4) if disposed_breakdown else None,
        },
        'manually_traceable_sample': sample_rows,
        'input_eligibility_run': str(eligibility_dir),
        'input_workout_run': str(workout_dir),
        'eligibility_result_sha256': fingerprint(eligibility_dir / 'eligibility_result.json'),
        'workout_result_sha256': fingerprint(workout_dir / 'workout_linkage_result.json'),
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': round(time.perf_counter() - start, 3),
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'output_directory': str(out),
        'limitations': [
            'anchor_current_actual_upb is the raw reported balance at the anchor month exactly as retained by exposure_eligibility; a NULL/masked/terminal/zero-unexplained value is never substituted with original UPB, a prior balance, or zero.',
            'terminal_same_month means the anchor row is itself the disposition row (immediate default-to-disposition, no intervening months); the general eligibility rule still excludes it from usable_reported_exposure because it is terminal, not because the balance is unknown.',
            'prior_supported_balance is a separately named proxy only: the most recent eligible reported balance at or before the anchor month, with its exact age in months. It is not asserted to equal exposure at default and must not be substituted for anchor exposure without an explicitly justified methodology.',
            'masking ages 0 and 6 remain unresolved, unchanged from exposure_eligibility; this module does not reclassify them.',
            'This quantifies exposure availability; it does not compute LGD, net loss, or any severity model.',
        ],
    }
    conn.close()
    (out / 'default_anchor_exposure_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'status': status, 'result': str(out / 'default_anchor_exposure_result.json'), 'seconds': result['elapsed_seconds']}), flush=True)
    return result


if __name__ == '__main__':
    run(Path(__file__).resolve().parents[2])
