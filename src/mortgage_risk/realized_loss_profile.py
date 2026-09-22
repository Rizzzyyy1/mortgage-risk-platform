"""Milestone 3: a narrowly labeled DESCRIPTIVE realized-loss profile for the complete-case,
exposure-supported subset of disposed_credit_exit episodes. This is explicitly NOT an LGD model,
NOT a severity estimate, and NOT representative of all defaults (see loss_workout_linkage: 75.9%
of default episodes never reach disposition). It computes one undiscounted nominal accounting
identity only for loans where every input is directly supported, never imputing a missing field
as zero and never clamping a negative or exposure-exceeding result.

Why this stops at "descriptive profile" rather than an accepted severity model: the project's
local glossary (crt-file-layout-and-glossary.pdf, pp. 5-6) states for EVERY one of fields 54-62
that "this field will be populated after the disclosed disposition date ... based on individual
CRT deal claims and reporting timelines." That ties population/completeness to a credit-risk-
transfer reinsurance claims process, not necessarily to the SF loan's own final economic
settlement — a populated field is not thereby proven final. Field 59 (Net Sales Proceeds) is
explicitly defined "net of any applicable selling expenses, such as fees and commissions," which
is a narrow netting scope distinct from the pre-sale foreclosure/holding cost fields (54-58), so
the double-counting risk between those groups is low, but is not eliminated for interest,
advances, forgiveness or deferred principal, none of which appear in the selected fields at all.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint

COST_FIELDS = ('foreclosure_costs', 'preservation_repair', 'asset_recovery_costs', 'holding_expenses_credits', 'taxes')
PROCEEDS_FIELDS = ('net_sales_proceeds', 'credit_enhancement_proceeds', 'repurchase_makewhole', 'other_foreclosure_proceeds')
ALL_LOSS_FIELDS = COST_FIELDS + PROCEEDS_FIELDS

NET_LOSS_SQL = (
    'anchor_current_actual_upb + (' + ' + '.join(COST_FIELDS) + ') - (' + ' + '.join(PROCEEDS_FIELDS) + ')'
)


def run(root):
    root = Path(root).resolve()
    start = time.perf_counter()
    feasibility_dir = root / 'artifacts/runs/loss_feasibility/30a0a02381af4b93807301fc6ef08d90'
    exposure_dir = root / 'artifacts/runs/default_anchor_exposure/62355abf161f4a9fbd86b0f6401beb36'
    feasibility_result = json.loads((feasibility_dir / 'feasibility_result.json').read_text())
    if not feasibility_result.get('source_stat_unchanged'):
        raise ValueError('Input loss-feasibility source stat check not clean')
    exposure_result = json.loads((exposure_dir / 'default_anchor_exposure_result.json').read_text())
    if exposure_result['status'] != 'pass':
        raise ValueError('Input default-anchor-exposure run not accepted')
    out = root / 'artifacts/runs/realized_loss_profile' / uuid.uuid4().hex
    out.mkdir(parents=True)
    conn = duckdb.connect(str(out / 'profile.db'))
    conn.execute("SET memory_limit='2GB'")
    conn.execute('SET threads=2')

    def lit(path):
        return str(path).replace("'", "''")

    conn.execute(f"CREATE VIEW loss_fields AS SELECT * FROM read_parquet('{lit(feasibility_dir / 'loss_fields.parquet')}')")
    conn.execute(f"CREATE VIEW anchor_exposure AS SELECT * FROM read_parquet('{lit(exposure_dir / 'anchor_exposure.parquet')}')")
    typed_fields = ','.join(f"try_cast({f} AS DECIMAL(18,2)) {f}" for f in ALL_LOSS_FIELDS)
    conn.execute(f"CREATE VIEW loss_fields_typed AS SELECT loan_id, {typed_fields} FROM loss_fields")

    disposed_count = conn.execute("SELECT count(*) FROM anchor_exposure WHERE workout_category='disposed_credit_exit'").fetchone()[0]
    duplicate_loss_field_loans = conn.execute('SELECT count(*) - count(DISTINCT loan_id) FROM loss_fields').fetchone()[0]
    unmatched_loss_field_loans = conn.execute("""
        SELECT count(*) FROM loss_fields_typed lf ANTI JOIN anchor_exposure a
          ON lf.loan_id = a.loan_id AND a.workout_category = 'disposed_credit_exit'
    """).fetchone()[0]

    all_fields_populated = ' AND '.join(f'{f} IS NOT NULL' for f in ALL_LOSS_FIELDS)
    conn.execute(f"""
        CREATE TABLE analysis_population AS
        SELECT a.loan_id, a.anchor_month, a.resolution_month, a.anchor_current_actual_upb,
          a.anchor_exposure_classification, lf.* EXCLUDE(loan_id),
          ({NET_LOSS_SQL}) AS net_loss
        FROM anchor_exposure a
        JOIN loss_fields_typed lf ON a.loan_id = lf.loan_id
        WHERE a.workout_category = 'disposed_credit_exit'
          AND a.anchor_exposure_classification = 'eligible_positive_reported_balance'
          AND {all_fields_populated}
    """)
    conn.execute(f"COPY analysis_population TO '{lit(out / 'analysis_population.parquet')}' (FORMAT PARQUET)")

    population_count = conn.execute('SELECT count(*) FROM analysis_population').fetchone()[0]
    exposure_supported_disposed = conn.execute(
        "SELECT count(*) FROM anchor_exposure WHERE workout_category='disposed_credit_exit' AND anchor_exposure_classification='eligible_positive_reported_balance'"
    ).fetchone()[0]
    all_fields_present_disposed = conn.execute(f"""
        SELECT count(*) FROM anchor_exposure a JOIN loss_fields_typed lf ON a.loan_id = lf.loan_id
        WHERE a.workout_category = 'disposed_credit_exit' AND {all_fields_populated}
    """).fetchone()[0]

    stats = conn.execute("""
        SELECT count(*), min(net_loss), max(net_loss),
          round(avg(net_loss), 2), median(net_loss),
          quantile_cont(net_loss, 0.25), quantile_cont(net_loss, 0.75),
          count(*) FILTER(WHERE net_loss < 0) AS net_gain_count,
          count(*) FILTER(WHERE net_loss > anchor_current_actual_upb) AS loss_exceeds_exposure_count,
          round(avg(net_loss / anchor_current_actual_upb), 4) AS avg_realized_loss_ratio,
          median(net_loss / anchor_current_actual_upb) AS median_realized_loss_ratio
        FROM analysis_population
    """).fetchone()
    (n, lmin, lmax, lmean, lmedian, lq25, lq75, gain_n, exceeds_n, ratio_mean, ratio_median) = stats

    cost_component_means = conn.execute(
        'SELECT ' + ','.join(f'round(avg({f}),2)' for f in ALL_LOSS_FIELDS) + ' FROM analysis_population'
    ).fetchone()
    component_means = dict(zip(ALL_LOSS_FIELDS, [str(v) for v in cost_component_means]))

    sample = conn.execute("""
        SELECT loan_id, anchor_month, resolution_month, anchor_current_actual_upb, net_loss,
          round(net_loss / anchor_current_actual_upb, 4) AS realized_loss_ratio
        FROM analysis_population ORDER BY net_loss ASC LIMIT 3
    """).fetchall()
    sample_hi = conn.execute("""
        SELECT loan_id, anchor_month, resolution_month, anchor_current_actual_upb, net_loss,
          round(net_loss / anchor_current_actual_upb, 4) AS realized_loss_ratio
        FROM analysis_population ORDER BY net_loss DESC LIMIT 3
    """).fetchall()
    sample_cols = [d[0] for d in conn.description]
    manually_traceable_sample = {
        'three_lowest_net_loss': [dict(zip(sample_cols, r)) for r in sample],
        'three_highest_net_loss': [dict(zip(sample_cols, r)) for r in sample_hi],
    }

    checks = {
        'disposed_credit_exit_population': disposed_count,
        'duplicate_loss_field_loans': duplicate_loss_field_loans,
        'unmatched_loss_field_loans_against_disposed': unmatched_loss_field_loans,
        'exposure_supported_disposed_loans': exposure_supported_disposed,
        'all_nine_fields_present_disposed_loans': all_fields_present_disposed,
        'analysis_population_count': population_count,
        'analysis_population_share_of_disposed': round(population_count / disposed_count, 4),
    }
    status = 'pass' if (
        not checks['duplicate_loss_field_loans'] and not checks['unmatched_loss_field_loans_against_disposed']
    ) else 'failed'

    result = {
        'status': status,
        'label': 'DESCRIPTIVE realized-loss profile, complete-case and exposure-supported disposed_credit_exit subset only. This is NOT an LGD model, NOT a severity estimate for use in any loss projection, and NOT representative of all defaults.',
        'checks': checks,
        'accounting_identity': 'net_loss = anchor_current_actual_upb (reported balance at the ORIGINAL default anchor month) + foreclosure_costs + preservation_repair + asset_recovery_costs + holding_expenses_credits + taxes - net_sales_proceeds - credit_enhancement_proceeds - repurchase_makewhole - other_foreclosure_proceeds. Undiscounted nominal dollars; no recovery-timing adjustment. No value is imputed for a missing field: any loan with a missing anchor exposure or a missing loss field is excluded from this population, not zero-filled.',
        'denominator_coverage': {
            'all_disposed_credit_exit_episodes': disposed_count,
            'with_directly_usable_anchor_exposure': exposure_supported_disposed,
            'with_all_nine_loss_fields_populated': all_fields_present_disposed,
            'analysis_population_both_conditions': population_count,
            'analysis_population_share_of_all_disposed_episodes': round(population_count / disposed_count, 4),
            'analysis_population_share_of_all_8750_default_episodes': round(population_count / 8750, 4),
        },
        'net_loss_distribution_usd': {
            'count': n, 'min': str(lmin), 'max': str(lmax), 'mean': str(lmean), 'median': str(lmedian),
            'p25': str(lq25), 'p75': str(lq75),
            'net_gain_count_loss_below_zero': gain_n,
            'loss_exceeds_exposure_count': exceeds_n,
        },
        'realized_loss_ratio_not_lgd': {
            'mean': str(ratio_mean), 'median': str(ratio_median),
            'note': 'net_loss divided by anchor exposure, for this complete-case subset only. Explicitly not called LGD: it excludes every episode without complete accounting or supported exposure, is not discounted, and is not shown to be representative of the 75.9% of default episodes that never reach disposition.',
        },
        'cost_and_proceeds_component_means_usd': component_means,
        'manually_traceable_sample': manually_traceable_sample,
        'blockers_before_this_could_become_an_accepted_severity_model': [
            'Field finality: the local glossary ties fields 54-62 to "individual CRT deal claims and reporting timelines," not to a confirmed final SF settlement date; a populated value is not proven to be the last, final revision. No evidence in this project confirms these amounts stop changing after the observed snapshot.',
            'Scope gaps not captured by any of the nine fields: missed/unpaid interest, servicer advances, principal forgiveness, deferred (non-interest-bearing) principal, and recovery-timing/discounting are all absent from this identity and from every source field inspected so far.',
            'Population coverage: this profile covers only {pop}/{disposed} ({share:.1%}) of disposed episodes and {pop}/8750 ({share_all:.2%}) of all default episodes; it is a complete-case subset, not a representative severity sample, and must never be applied to the 75.9% of episodes that do not reach disposition.'.format(
                pop=population_count, disposed=disposed_count, share=population_count / disposed_count, share_all=population_count / 8750),
            'No independent confirmation exists that the itemized cost fields (54-58) and the netted Net Sales Proceeds field (59) never overlap beyond the glossary\'s stated "selling expenses, such as fees and commissions" scope.',
        ],
        'input_feasibility_run': str(feasibility_dir),
        'input_exposure_run': str(exposure_dir),
        'feasibility_result_sha256': fingerprint(feasibility_dir / 'feasibility_result.json'),
        'exposure_result_sha256': fingerprint(exposure_dir / 'default_anchor_exposure_result.json'),
        'glossary_sha256': fingerprint(root / 'data/raw/fannie_mae_loan_performance/crt-file-layout-and-glossary.pdf'),
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': round(time.perf_counter() - start, 3),
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'output_directory': str(out),
    }
    conn.close()
    (out / 'realized_loss_profile_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'status': status, 'result': str(out / 'realized_loss_profile_result.json'), 'seconds': result['elapsed_seconds']}), flush=True)
    return result


if __name__ == '__main__':
    run(Path(__file__).resolve().parents[2])
