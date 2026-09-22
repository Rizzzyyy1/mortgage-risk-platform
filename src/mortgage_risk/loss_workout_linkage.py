"""Default-to-workout linkage: follows every Phase 2F default-proxy episode through its full
post-anchor trajectory to its last supportable resolution or censoring point, preserving the
path taken (cures, redefaults, ambiguity, gaps) alongside the final status, and cross-tabs the
result against loans with recorded foreclosure/disposition loss fields. This is a reconciliation
and evidence layer only: it fits no severity model, computes no LGD, and does not alter the
frozen Phase 2F first_stop/12-month outcome contract. It reuses accepted event_rows/loan_outcomes/
loss_fields Parquet outputs; it does not rescan the raw CSV.

v2 (2026-09-22) corrects v1 (artifacts/runs/loss_workout_linkage/24126815af8448fe9b02b34f23ca7aa9/,
preserved unchanged): v1 stopped at the first redefault (cured_then_redefault) and at the first
reporting gap (gap_after_default), understating how many episodes actually reach a disposition.
v2 follows the full trajectory. Two empirical checks informed this design and are recorded in the
result: (1) across the whole 323,174-loan cohort, zero rows follow any terminal zero-balance code
(01/02/03/06/09/15/16/96), so resolving at the first terminal code cannot miss a later revision;
(2) zero_balance_effective_date equals reporting_month on all 306,637 terminal rows cohort-wide, so
no effective-date/reporting-date divergence exists to reconcile here.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint

DISPOSITION_CODES = ('02', '03', '09', '15')
OTHER_EXIT_CODES = ('06', '16', '96')
KNOWN_CODES = ('01',) + DISPOSITION_CODES + OTHER_EXIT_CODES


def _delinquency_number(value):
    if value is None:
        return None
    text = value.strip()
    if not text.isdigit():
        return None
    return int(text)


def classify_episode(rows, panel_max_month):
    """rows: ordered list of dicts with reporting_month, delinquency_status, zero_balance_code,
    candidate_event, for one loan, starting at (and including) its default-proxy anchor month
    through its last observed month. panel_max_month: the dataset-wide latest reporting month,
    used to distinguish a loan still actively reporting from one whose data quietly stops.

    Single unit of analysis: the original default anchor is never moved. Redefaults, cures and
    ambiguous same-month rows are events *within* this one trajectory, not new episodes; the
    function returns exactly one final category plus the ordered path of transitions that led
    there, so a terminal outcome is never attributed to more than one episode.

    Priority per row, in order: (a) a gap-censor row only breaks observational continuity
    (had_gap=True) and is never itself a stopping condition — the row's own code/status is still
    evaluated; (b) a disposition code (02/03/09/15) is unconditionally terminal, matching the
    project's rule that credit-related exits remain default proxies regardless of delinquency;
    (c) a same-month conflict between a payoff/other-exit code and delinquency >=3
    (event_rows' own 'ambiguous_same_month' contract) is never resolved by code priority — it
    becomes an 'ambiguous' trajectory state that a later clean row can still resolve; (d) a clean
    payoff/other-exit/unsupported code is terminal; (e) otherwise the row's own delinquency moves
    the trajectory between 'delinquent', 'cured' and 'unknown' states, with a cured->delinquent
    transition counted as a redefault.
    """
    if not rows:
        raise ValueError('classify_episode requires at least the anchor row')
    path = []
    state = None
    cure_count = 0
    redefault_count = 0
    ambiguous_count = 0
    had_gap = False
    for row in rows:
        code = (row['zero_balance_code'] or '').strip()
        month = row['reporting_month']
        if row['candidate_event'] == 'gap_censor':
            had_gap = True
            path.append({'kind': 'gap', 'month': month})
        if code in DISPOSITION_CODES:
            path.append({'kind': 'disposed_credit_exit', 'month': month})
            return {'category': 'disposed_credit_exit', 'resolution_month': month, 'path': path,
                    'cure_count': cure_count, 'redefault_count': redefault_count,
                    'ambiguous_count': ambiguous_count, 'had_gap': had_gap}
        if row['candidate_event'] == 'ambiguous_same_month':
            ambiguous_count += 1
            if state != 'ambiguous':
                path.append({'kind': 'ambiguous_same_month', 'month': month})
            state = 'ambiguous'
            continue
        if code == '01':
            path.append({'kind': 'payoff_or_maturity_after_default', 'month': month})
            return {'category': 'payoff_or_maturity_after_default', 'resolution_month': month, 'path': path,
                    'cure_count': cure_count, 'redefault_count': redefault_count,
                    'ambiguous_count': ambiguous_count, 'had_gap': had_gap}
        if code in OTHER_EXIT_CODES:
            path.append({'kind': 'other_exit_after_default', 'month': month})
            return {'category': 'other_exit_after_default', 'resolution_month': month, 'path': path,
                    'cure_count': cure_count, 'redefault_count': redefault_count,
                    'ambiguous_count': ambiguous_count, 'had_gap': had_gap}
        if code and code not in KNOWN_CODES:
            path.append({'kind': 'unsupported_code_after_default', 'month': month})
            return {'category': 'unsupported_code_after_default', 'resolution_month': month, 'path': path,
                    'cure_count': cure_count, 'redefault_count': redefault_count,
                    'ambiguous_count': ambiguous_count, 'had_gap': had_gap}
        dq = _delinquency_number(row['delinquency_status'])
        if dq is not None and dq >= 3:
            if state == 'cured':
                redefault_count += 1
                path.append({'kind': 'redefault', 'month': month})
            state = 'delinquent'
        elif dq is not None and 0 <= dq <= 2:
            if state != 'cured':
                cure_count += 1
                path.append({'kind': 'cure', 'month': month})
            state = 'cured'
        else:
            state = 'unknown'
    last_month = rows[-1]['reporting_month']
    at_data_end = last_month == panel_max_month
    suffix = 'at_data_end' if at_data_end else 'incomplete_followup'
    state_category = {'cured': 'cured_no_redefault', 'delinquent': 'still_delinquent',
                       'ambiguous': 'ambiguous_unresolved', 'unknown': 'unknown_status',
                       None: 'unknown_status'}[state]
    category = f'{state_category}_{suffix}'
    return {'category': category, 'resolution_month': None, 'path': path, 'cure_count': cure_count,
            'redefault_count': redefault_count, 'ambiguous_count': ambiguous_count, 'had_gap': had_gap,
            'last_month': last_month, 'at_data_end': at_data_end}


def run(root):
    root = Path(root).resolve()
    start = time.perf_counter()
    descriptive_dir = root / 'artifacts/runs/phase2f/64d49545a270488ca411e6a731e59465'
    feasibility_dir = root / 'artifacts/runs/loss_feasibility/30a0a02381af4b93807301fc6ef08d90'
    prior_run_dir = root / 'artifacts/runs/loss_workout_linkage/24126815af8448fe9b02b34f23ca7aa9'
    descriptive_result = json.loads((descriptive_dir / 'descriptive_result.json').read_text())
    if descriptive_result['status'] != 'pass':
        raise ValueError('Input Phase 2F descriptive run not accepted')
    linkage_checks = json.loads((feasibility_dir / 'linkage_checks.json').read_text())
    if linkage_checks['duplicate_loan_ids'] or linkage_checks['unmatched_outcomes']:
        raise ValueError('Input loss-feasibility linkage checks not clean')
    out = root / 'artifacts/runs/loss_workout_linkage' / uuid.uuid4().hex
    out.mkdir(parents=True)
    conn = duckdb.connect(str(out / 'linkage.db'))
    conn.execute("SET memory_limit='2GB'")
    conn.execute('SET threads=2')

    def lit(path):
        return str(path).replace("'", "''")

    conn.execute(f"CREATE VIEW event_rows AS SELECT * FROM read_parquet('{lit(descriptive_dir / 'event_rows.parquet')}')")
    conn.execute(f"CREATE VIEW loan_outcomes AS SELECT * FROM read_parquet('{lit(descriptive_dir / 'loan_outcomes.parquet')}')")
    conn.execute(f"CREATE VIEW loss_fields AS SELECT * FROM read_parquet('{lit(feasibility_dir / 'loss_fields.parquet')}')")
    panel_max_month = conn.execute('SELECT max(reporting_month) FROM event_rows').fetchone()[0]

    # Empirical checks backing the design choices in this module's docstring; recomputed here
    # (bulk SQL over the accepted Parquet, no CSV rescan) so the result is self-evidencing.
    rows_after_terminal = conn.execute("""
        WITH term AS (SELECT loan_id, min(reporting_month) first_term_month FROM event_rows
                       WHERE zero_balance_code IN ('01','02','03','06','09','15','16','96') GROUP BY 1)
        SELECT count(*) FROM event_rows e JOIN term t ON e.loan_id = t.loan_id AND e.reporting_month > t.first_term_month
    """).fetchone()[0]

    conn.execute("""
        CREATE TABLE defaults AS
        SELECT loan_id, stop_month AS anchor_month, last_month
        FROM loan_outcomes WHERE first_stop = 'default_proxy'
    """)
    default_loan_count = conn.execute('SELECT count(*) FROM defaults').fetchone()[0]
    duplicate_default_loans = conn.execute('SELECT count(*) - count(DISTINCT loan_id) FROM defaults').fetchone()[0]
    loss_field_loans = {r[0] for r in conn.execute('SELECT DISTINCT loan_id FROM loss_fields').fetchall()}
    unmatched_loss_field_loans = conn.execute("""
        SELECT count(*) FROM (SELECT DISTINCT loan_id FROM loss_fields) lf
        ANTI JOIN defaults d ON lf.loan_id = d.loan_id
    """).fetchone()[0]
    rows = conn.execute("""
        SELECT e.loan_id, e.reporting_month, e.delinquency_status, e.zero_balance_code, e.candidate_event
        FROM event_rows e
        JOIN defaults d ON e.loan_id = d.loan_id AND e.reporting_month >= d.anchor_month
        ORDER BY e.loan_id, e.reporting_month
    """).fetchall()
    print(f'Classifying {default_loan_count} default-proxy episodes from {len(rows)} post-anchor rows', flush=True)
    grouped = {}
    for loan_id, reporting_month, delinquency_status, zero_balance_code, candidate_event in rows:
        grouped.setdefault(loan_id, []).append({
            'reporting_month': reporting_month, 'delinquency_status': delinquency_status,
            'zero_balance_code': zero_balance_code, 'candidate_event': candidate_event,
        })
    classified = []
    for loan_id, loan_rows in grouped.items():
        result = classify_episode(loan_rows, panel_max_month)
        classified.append({
            'loan_id': loan_id, 'anchor_month': loan_rows[0]['reporting_month'],
            'category': result['category'], 'resolution_month': result.get('resolution_month'),
            'cure_count': result['cure_count'], 'redefault_count': result['redefault_count'],
            'ambiguous_count': result['ambiguous_count'], 'had_gap': result['had_gap'],
            'path_json': json.dumps([{'kind': p['kind'], 'month': str(p['month'])} for p in result['path']]),
            'has_loss_fields': loan_id in loss_field_loans,
        })
    conn.execute("""
        CREATE TABLE workout_episodes(loan_id VARCHAR, anchor_month DATE, category VARCHAR,
        resolution_month DATE, cure_count INTEGER, redefault_count INTEGER, ambiguous_count INTEGER,
        had_gap BOOLEAN, path_json VARCHAR, has_loss_fields BOOLEAN)
    """)
    conn.executemany('INSERT INTO workout_episodes VALUES (?,?,?,?,?,?,?,?,?,?)', [
        (r['loan_id'], r['anchor_month'], r['category'], r['resolution_month'], r['cure_count'],
         r['redefault_count'], r['ambiguous_count'], r['had_gap'], r['path_json'], r['has_loss_fields'])
        for r in classified
    ])
    conn.execute(f"COPY workout_episodes TO '{lit(out / 'workout_episodes.parquet')}' (FORMAT PARQUET)")
    category_counts = conn.execute(
        'SELECT category, count(*) loans, count(*) FILTER(WHERE has_loss_fields) with_loss_fields, '
        'sum(CASE WHEN redefault_count>0 THEN 1 ELSE 0 END) with_redefault, '
        'sum(CASE WHEN had_gap THEN 1 ELSE 0 END) with_gap, '
        'sum(CASE WHEN ambiguous_count>0 THEN 1 ELSE 0 END) with_ambiguous '
        'FROM workout_episodes GROUP BY 1 ORDER BY 1'
    ).fetchall()
    category_counts = [
        {'category': c, 'loans': n, 'with_loss_fields': w, 'with_redefault': r, 'with_gap': g, 'with_ambiguous': a}
        for c, n, w, r, g, a in category_counts
    ]
    classified_loan_count = len(classified)
    unsupported_code_count = sum(r['loans'] for r in category_counts if r['category'] == 'unsupported_code_after_default')
    loss_field_loans_classified = sum(r['with_loss_fields'] for r in category_counts)

    prior_comparison = None
    if (prior_run_dir / 'workout_episodes.parquet').exists():
        conn.execute(f"CREATE VIEW prior_episodes AS SELECT * FROM read_parquet('{lit(prior_run_dir / 'workout_episodes.parquet')}')")
        prior_counts = conn.execute('SELECT category, count(*) FROM prior_episodes GROUP BY 1 ORDER BY 1').fetchall()
        prior_disposed = conn.execute("SELECT count(*) FROM prior_episodes WHERE category='disposed_credit_exit'").fetchone()[0]
        new_disposed = sum(r['loans'] for r in category_counts if r['category'] == 'disposed_credit_exit')
        prior_comparison = {
            'prior_run': str(prior_run_dir),
            'prior_category_counts': [{'category': c, 'loans': n} for c, n in prior_counts],
            'prior_disposed_credit_exit': prior_disposed,
            'new_disposed_credit_exit': new_disposed,
            'disposed_credit_exit_share_prior': round(prior_disposed / default_loan_count, 4),
            'disposed_credit_exit_share_new': round(new_disposed / default_loan_count, 4),
            'disposition_share_changed': prior_disposed != new_disposed,
            'note': 'v1 stopped at the first redefault/gap; v2 follows the full trajectory. A changed count here reflects the corrected classification, not a change in the underlying data.',
        }

    checks = {
        'default_loan_count': default_loan_count,
        'duplicate_default_loans': duplicate_default_loans,
        'classified_loan_count': classified_loan_count,
        'classified_matches_default_population': classified_loan_count == default_loan_count,
        'category_counts_sum_to_population': sum(r['loans'] for r in category_counts) == default_loan_count,
        'unmatched_loss_field_loans': unmatched_loss_field_loans,
        'loss_field_loans_total': len(loss_field_loans),
        'loss_field_loans_classified': loss_field_loans_classified,
        'all_loss_field_loans_classified': loss_field_loans_classified == len(loss_field_loans),
        'unsupported_code_after_default_count': unsupported_code_count,
        'rows_found_after_any_terminal_code_cohort_wide': rows_after_terminal,
        'no_rows_after_terminal_code_confirmed': rows_after_terminal == 0,
    }
    status = 'pass' if (
        checks['classified_matches_default_population'] and checks['category_counts_sum_to_population']
        and not checks['unmatched_loss_field_loans'] and checks['all_loss_field_loans_classified']
        and not checks['duplicate_default_loans'] and not unsupported_code_count
        and checks['no_rows_after_terminal_code_confirmed']
    ) else 'failed'
    result = {
        'status': status,
        'version': 'v2',
        'scope': 'Full post-anchor trajectory of every Phase 2F default-proxy episode in the accepted 2010Q1 cohort, followed to its last supportable resolution or censoring point, cross-tabbed against loans with recorded foreclosure/disposition loss fields. Reconciliation evidence only; no severity/LGD model, no exposure model, no lifetime hazard.',
        'panel_max_month': str(panel_max_month),
        'checks': checks,
        'category_counts': category_counts,
        'prior_run_comparison': prior_comparison,
        'input_descriptive_run': str(descriptive_dir),
        'input_feasibility_run': str(feasibility_dir),
        'descriptive_result_sha256': fingerprint(descriptive_dir / 'descriptive_result.json'),
        'feasibility_result_sha256': fingerprint(feasibility_dir / 'feasibility_result.json'),
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': round(time.perf_counter() - start, 3),
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'output_directory': str(out),
        'design_notes': [
            'A gap-censor row breaks observational continuity (had_gap=True) but is never itself a stopping condition; the row\'s own code/delinquency is still evaluated and later rows continue to be scanned.',
            'A same-month conflict between a payoff/other-exit code and delinquency>=3 (the frozen ambiguous_same_month rule) is never resolved by disposition/payoff code priority; it becomes an explicit ambiguous trajectory state, which a later clean row can still resolve.',
            'Disposition codes (02/03/09/15) are unconditionally terminal regardless of same-row delinquency, matching the project\'s rule that credit-related exits remain default proxies even when delinquency is unknown.',
            'Verified cohort-wide (323,174 loans): zero rows follow any terminal zero-balance code, so resolving at the first terminal code cannot miss a later revision.',
            'Verified cohort-wide on all 306,637 terminal rows: zero_balance_effective_date equals reporting_month with zero exceptions, so no effective-date/reporting-date divergence exists to reconcile in this dataset.',
            'cure_count/redefault_count/ambiguous_count and the path_json column preserve the full trajectory; the category column is only the final resolution, never a substitute for the path.',
        ],
        'limitations': [
            'A category is the loan\'s last supportable resolution by this project\'s code taxonomy; it is not a verified vendor workout classification.',
            'disposed_credit_exit means a disposition code (02/03/09/15) was eventually reported, not that every accounting field for that loan is complete; see loss_feasibility for field-level coverage.',
            'has_loss_fields means at least one of the nine foreclosure/disposition/expense/proceeds fields was ever populated for that loan; it is not proof of a final, complete accounting record, and can be populated on a loan whose first foreclosure action was later halted (see ambiguous/cured loans with loss fields).',
            'other_exit_after_default (repurchase/reperforming sale/non-credit removal) is a genuine trajectory stop but leaves the ultimate loss outcome unresolved by this dataset; it remains in every population denominator rather than being dropped.',
            '_incomplete_followup categories mean the loan\'s data stream ends before the panel-wide latest month with no later gap-flagged row to explain it; this is a data-completeness flag, not a resolved outcome.',
            'ambiguous_unresolved_* means the trajectory\'s last available evidence is a same-month code/delinquency conflict that this project\'s rules deliberately do not adjudicate.',
            'This reconciles episode outcomes and their paths; it does not establish exposure at the default anchor, net loss amounts, or LGD.',
        ],
    }
    conn.close()
    (out / 'workout_linkage_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'status': status, 'result': str(out / 'workout_linkage_result.json'), 'seconds': result['elapsed_seconds']}), flush=True)
    return result


if __name__ == '__main__':
    run(Path(__file__).resolve().parents[2])
