"""Milestone (2026-09-22, follow-on): resolves the vendor event-definition question left open by
vendor_method_reconciliation.py by retrieving and inspecting Fannie Mae's own official R
reference implementation, then implements its exact credit-event trigger, exposure basis and
Net Loss/Net Severity formula, compared field-for-field against this project's own default-proxy
anchor. This does not replace realized_loss_profile.py's original 1,880-loan complete-case figure
(preserved, unread-only referenced here); it adds a separately named, wider "official-formula"
variant covering every disposed_credit_exit loan, zero-filling only the specific fields the vendor
code itself zero-fills, never exposure/dates.

Provenance of the official code, recorded exactly as retrieved:
- Product page (Wayback snapshot 2026-07-22 of capitalmarkets.fanniemae.com's Single-Family Loan
  Performance Data page) links "Code (Primary)" to
  https://capitalmarkets.fanniemae.com/media/document/zip/FNMA_SF_Loan_Performance_r_Primary.zip
  (this is the CURRENT capitalmarkets.fanniemae.com domain, not the legacy
  loanperformancedata.fanniemae.com domain that failed to resolve in the prior milestone).
- That URL is Cloudflare-blocked live from this environment (403/JS challenge), so a Wayback
  Machine snapshot was used: http://web.archive.org/web/20250401064526/<that URL>, which itself
  redirects (per its recorded HTTP headers) to https://capitalmarkets.fanniemae.com/media/20936/display,
  archived 2025-04-01 06:45:27 GMT, Content-Type application/zip, 13,152 bytes,
  x-archive-orig-last-modified: Fri, 02 Aug 2024 13:56:53 GMT (i.e. the files date from mid-2024).
- Retrieved 2026-09-22. Zip SHA-256: 00b6798d614ed6af75ed1e79e8908bbb0526f166d4367e4be0334af70ecd6418.
- Extracted files and their individual SHA-256: LPPUB_Infile.R
  7b97ae1b127cc50b9e53e23accec9706bad285750c461f07b47dba4ca625d791; LPPUB_StatFile.R
  41fa02114623008fd3a99d6d075442e0826666883b58f32dde5977af79e25257;
  LPPUB_StatFile_Production.R d6539dbdf3729879a97905d452bb2890b7b8035b2cdc00d8c035877f09a7fccc
  (the file inspected for this milestone); LPPUB_StatSummary.R
  af626778f8aaf96db7b33323027c79a4c526a73c0e88b0921a85211e2b1a8c87.
- This is a historical/archived copy, not a live-verified current implementation; it is used here
  for historical interpretation of the methodology, consistent with the project's own
  April-2024-vintage source data, not presented as necessarily identical to whatever Fannie Mae
  serves today. No access control was bypassed: the files were served by the Internet Archive at
  a public, unauthenticated URL.

Verified from LPPUB_StatFile_Production.R (line numbers refer to that file as retrieved):
- Credit event trigger (line ~401): zero_balance_code IN ('02','03','09','15') OR
  (numeric delinquency_status >= 6 AND < 999). This is FCE_DTE/FCE_UPB -- a DIFFERENT concept
  from this project's default-proxy anchor (delinquency >= 3, i.e. 90 days, not 180) and from the
  exposure basis actually used in Net Loss (see below). FCE_UPB = zb_upb + act_upb at that row
  with no NA-coalescing, so it is frequently undefined for loans first triggered by the
  delinquency threshold rather than by an immediate disposition code (zb_upb is not yet populated
  before a disposition), which this module reports rather than assumes.
- Exposure basis used in Net Loss (LAST_UPB, line ~277): at the loan's LAST (terminal) observed
  row, COALESCE(upb_at_removal, current_actual_upb) -- i.e. field 46 preferred, current UPB as
  fallback, both read at the SAME terminal row (empirically the disposition row for
  disposed_credit_exit loans).
- LAST_RT (line ~278-288): NOT the rate at the terminal row. It is the rate from the most recent
  PRIOR row where current_interest_rate was populated, carried forward to (and including) the
  terminal row -- because current_interest_rate is frequently blank exactly on the terminal row
  (confirmed empirically in the prior milestone: ~89% blank there). This project's earlier
  estimated_foregone_interest used only the terminal-row rate (11.4% coverage); this module
  corrects that with the same carry-forward logic the vendor uses.
- INT_COST (line ~556): months(LPI_DTE, LAST_DTE) x ((LAST_RT/100 - 0.0035)/12) x
  (LAST_UPB - NON_INT_UPB). The 0.35-percentage-point deduction (35bp) is a guaranty/servicing-fee
  carve-out this project's earlier approximation did not include.
- NET_LOSS (line ~570) = LAST_UPB + FCC_COST + PP_COST + AR_COST + IE_COST + TAX_COST + PFG_COST
  + INT_COST - NS_PROCS - CE_PROCS - RMW_PROCS - O_PROCS, computed only when COMPLT_FLG==1
  (DISP_DTE populated and the loan's LAST_STAT in F/S/N/T, which maps 1:1 onto zero_balance_code
  09/03/02/15 -- an exact match to this project's disposed_credit_exit population). All of
  FCC_COST/PP_COST/AR_COST/IE_COST/TAX_COST/PFG_COST/CE_PROCS/NS_PROCS/RMW_PROCS/O_PROCS/INT_COST
  default to 0 when missing for these loans (line ~559-568); LAST_UPB itself is never zero-filled.
- NET_SEV (line ~571) = NET_LOSS / LAST_UPB, confirming Net Severity is a ratio to the SAME
  LAST_UPB used additively in Net Loss, not to a different exposure figure.
- FORECLOSURE_PRINCIPAL_WRITE_OFF_AMOUNT (field 80) is read from source but never used in the
  Net Loss/Severity formula. MODIR_COST/MODFB_COST (modification-related costs) are tracked as
  separate metrics, not summed into NET_LOSS -- this project's own formula was not missing a
  required term by omitting them.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint

CREDIT_EVENT_DELINQUENCY_THRESHOLD = 6  # vendor's FCE trigger; this project's own anchor uses 3
DISPOSITION_CODES = ('02', '03', '09', '15')
GUARANTY_FEE_DEDUCTION_BPS = 0.0035  # 35 basis points, subtracted from the note rate before INT_COST


def official_net_loss_sql(last_upb='last_upb', fcc='fcc_cost', pp='pp_cost', ar='ar_cost', ie='ie_cost',
                           tax='tax_cost', pfg='pfg_cost', int_cost='int_cost', ns='ns_procs',
                           ce='ce_procs', rmw='rmw_procs', o='o_procs'):
    return (f"{last_upb} + COALESCE({fcc},0) + COALESCE({pp},0) + COALESCE({ar},0) + COALESCE({ie},0) "
            f"+ COALESCE({tax},0) + COALESCE({pfg},0) + COALESCE({int_cost},0) "
            f"- COALESCE({ns},0) - COALESCE({ce},0) - COALESCE({rmw},0) - COALESCE({o},0)")


def official_int_cost_sql(lpi_date='last_paid_installment_date', last_date='resolution_month',
                           last_rt='last_rt', last_upb='last_upb', non_int_upb='non_int_upb'):
    return (
        f"CASE WHEN {lpi_date} IS NOT NULL AND {last_date} IS NOT NULL AND {last_rt} IS NOT NULL "
        f"AND {last_upb} IS NOT NULL AND {last_date} >= {lpi_date} THEN "
        f"date_diff('month', {lpi_date}, {last_date}) "
        f"* (({last_rt} / 100.0 - {GUARANTY_FEE_DEDUCTION_BPS}) / 12.0) "
        f"* ({last_upb} - COALESCE({non_int_upb}, 0)) END"
    )


def run(root):
    root = Path(root).resolve()
    start = time.perf_counter()
    source = root / 'data/raw/fannie_mae_loan_performance/2010Q1.csv'
    before = source.stat()
    workout_dir = root / 'artifacts/runs/loss_workout_linkage/b2ebdeb7319a4a6486c84b4ad02414f1'
    descriptive_dir = root / 'artifacts/runs/phase2f/64d49545a270488ca411e6a731e59465'
    eligibility_dir = root / 'artifacts/runs/exposure_eligibility/7b7177c3473345d091dd1cd19d24799e'
    feasibility_dir = root / 'artifacts/runs/loss_feasibility/30a0a02381af4b93807301fc6ef08d90'
    reconciliation_dir = root / 'artifacts/runs/vendor_method_reconciliation/b758ff00b5aa468da1b81d13e64626f8'
    profile_dir = root / 'artifacts/runs/realized_loss_profile/f63257e5acb54101abb2a4d0cb30e8a4'
    for d in (workout_dir, descriptive_dir, eligibility_dir, reconciliation_dir, profile_dir):
        result_file = next(d.glob('*_result.json'))
        payload = json.loads(result_file.read_text())
        status = payload.get('status') or payload.get('engineering_status')
        if status != 'pass':
            raise ValueError(f'Input run not accepted: {d}')
    feasibility_result = json.loads((feasibility_dir / 'feasibility_result.json').read_text())
    if not feasibility_result.get('source_stat_unchanged'):
        raise ValueError(f'Input run not accepted: {feasibility_dir}')

    out = root / 'artifacts/runs/vendor_official_loss_calculation' / uuid.uuid4().hex
    out.mkdir(parents=True)
    conn = duckdb.connect(str(out / 'official.db'))
    conn.execute("SET memory_limit='2GB'")
    conn.execute('SET threads=2')

    def lit(path):
        return str(path).replace("'", "''")

    conn.execute(f"CREATE VIEW workout_episodes AS SELECT * FROM read_parquet('{lit(workout_dir / 'workout_episodes.parquet')}')")
    conn.execute(f"CREATE VIEW event_rows AS SELECT * FROM read_parquet('{lit(descriptive_dir / 'event_rows.parquet')}')")
    conn.execute(f"CREATE VIEW exposure_eligibility AS SELECT * FROM read_parquet('{lit(eligibility_dir / 'exposure_eligibility.parquet')}')")
    conn.execute(f"CREATE VIEW loss_fields AS SELECT * FROM read_parquet('{lit(feasibility_dir / 'loss_fields.parquet')}')")
    conn.execute(f"CREATE VIEW vendor_rows AS SELECT * FROM read_parquet('{lit(reconciliation_dir / 'vendor_rows.parquet')}')")
    conn.execute(f"CREATE VIEW prior_conservative_population AS SELECT * FROM read_parquet('{lit(profile_dir / 'analysis_population.parquet')}')")

    conn.execute("CREATE TABLE disposed AS SELECT loan_id, anchor_month, resolution_month FROM workout_episodes WHERE category = 'disposed_credit_exit'")
    disposed_count = conn.execute('SELECT count(*) FROM disposed').fetchone()[0]

    # --- Credit-event trigger comparison: the vendor's own FCE_DTE vs. this project's anchor ---
    print('Computing the vendor\'s own credit-event trigger (delinquency>=6 OR disposition code) from accepted event_rows', flush=True)
    conn.execute("""
        CREATE TABLE fce AS
        SELECT d.loan_id, min(e.reporting_month) AS fce_date
        FROM disposed d
        JOIN event_rows e ON d.loan_id = e.loan_id
        WHERE e.zero_balance_code IN ('02','03','09','15')
           OR (try_cast(e.delinquency_status AS INTEGER) >= 6 AND try_cast(e.delinquency_status AS INTEGER) < 999)
        GROUP BY 1
    """)
    fce_coverage = conn.execute('SELECT count(*) FROM fce').fetchone()[0]
    trigger_comparison = conn.execute("""
        SELECT
          count(*), count(*) FILTER(WHERE f.fce_date = d.anchor_month),
          count(*) FILTER(WHERE f.fce_date > d.anchor_month), count(*) FILTER(WHERE f.fce_date < d.anchor_month),
          round(avg(date_diff('month', d.anchor_month, f.fce_date)), 2),
          median(date_diff('month', d.anchor_month, f.fce_date)),
          min(date_diff('month', d.anchor_month, f.fce_date)), max(date_diff('month', d.anchor_month, f.fce_date))
        FROM disposed d JOIN fce f ON d.loan_id = f.loan_id
    """).fetchone()

    # --- Bounded, single-pass scan for current_interest_rate across ALL months of the 2,108
    # disposed loans (not just their terminal row), because LAST_RT is the vendor's own
    # last-known-value-carried-forward rate, not the terminal-row rate. ---
    print(f'Scanning 2010Q1 once for current_interest_rate across all months of {disposed_count} disposed loans', flush=True)
    conn.execute("CREATE TABLE disposed_loan_ids AS SELECT loan_id FROM disposed")
    columns = {f'c{i}': 'VARCHAR' for i in range(113)}
    conn.execute(f"CREATE VIEW raw AS SELECT * FROM read_csv('{lit(source)}', header=false, sep='|', columns={columns}, quote='', escape='', parallel=False)")
    conn.execute("""
        CREATE TABLE rate_history AS
        SELECT r.c1 AS loan_id, try_strptime(r.c2, '%m%Y')::DATE AS reporting_month,
          try_cast(nullif(trim(r.c8), '') AS DECIMAL(8,3)) AS current_interest_rate
        FROM raw r JOIN disposed_loan_ids ids ON r.c1 = ids.loan_id
        WHERE nullif(trim(r.c8), '') IS NOT NULL
    """)
    after = source.stat()
    source_stat_unchanged = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    if not source_stat_unchanged:
        raise ValueError('Source changed during scan')
    conn.execute(f"COPY rate_history TO '{lit(out / 'rate_history.parquet')}' (FORMAT PARQUET)")

    conn.execute("""
        CREATE VIEW last_rt AS
        SELECT d.loan_id,
          last_value(rh.current_interest_rate IGNORE NULLS) OVER (
            PARTITION BY d.loan_id ORDER BY rh.reporting_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
          ) AS last_rt, rh.reporting_month
        FROM disposed d JOIN rate_history rh ON d.loan_id = rh.loan_id
    """)
    conn.execute("""
        CREATE TABLE last_rt_at_resolution AS
        SELECT d.loan_id, (
          SELECT lr.last_rt FROM last_rt lr WHERE lr.loan_id = d.loan_id AND lr.reporting_month <= d.resolution_month
          ORDER BY lr.reporting_month DESC LIMIT 1
        ) AS last_rt
        FROM disposed d
    """)

    # --- Terminal-row (resolution_month-matched) vendor fields, reused from the prior accepted
    # extraction; never joined on loan_id alone (see vendor_method_reconciliation.py for why). ---
    conn.execute("""
        CREATE VIEW vendor_typed AS
        SELECT loan_id, try_strptime(reporting_month_raw,'%m%Y')::DATE reporting_month,
          try_cast(upb_at_removal AS DECIMAL(18,2)) upb_at_removal,
          try_strptime(last_paid_installment_date_raw,'%m%Y')::DATE last_paid_installment_date,
          try_cast(modification_nib_upb AS DECIMAL(18,2)) modification_nib_upb,
          try_cast(principal_forgiveness_amount AS DECIMAL(18,2)) principal_forgiveness_amount
        FROM vendor_rows
    """)
    conn.execute("""
        CREATE VIEW vendor_terminal AS
        SELECT d.loan_id, d.resolution_month,
          v.upb_at_removal, v.last_paid_installment_date, v.modification_nib_upb, v.principal_forgiveness_amount
        FROM disposed d
        LEFT JOIN vendor_typed v ON d.loan_id = v.loan_id AND v.reporting_month = d.resolution_month
    """)
    conn.execute(f"""
        CREATE VIEW current_upb_at_resolution AS
        SELECT loan_id, reporting_month, current_actual_upb
        FROM exposure_eligibility
    """)

    typed_loss = ','.join(f"try_cast({f} AS DECIMAL(18,2)) {f}" for f in
                           ('foreclosure_costs', 'preservation_repair', 'asset_recovery_costs', 'holding_expenses_credits',
                            'taxes', 'net_sales_proceeds', 'credit_enhancement_proceeds', 'repurchase_makewhole', 'other_foreclosure_proceeds'))
    conn.execute(f"CREATE VIEW loss_fields_typed AS SELECT loan_id, {typed_loss} FROM loss_fields")

    conn.execute(f"""
        CREATE TABLE official AS
        SELECT d.loan_id, d.anchor_month, d.resolution_month,
          COALESCE(t.upb_at_removal, u.current_actual_upb) AS last_upb,
          t.upb_at_removal, u.current_actual_upb AS current_actual_upb_at_resolution,
          t.last_paid_installment_date, r.last_rt,
          COALESCE(t.modification_nib_upb, 0) AS non_int_upb,
          COALESCE(t.principal_forgiveness_amount, 0) AS pfg_cost,
          lf.foreclosure_costs AS fcc_cost, lf.preservation_repair AS pp_cost, lf.asset_recovery_costs AS ar_cost,
          lf.holding_expenses_credits AS ie_cost, lf.taxes AS tax_cost,
          lf.net_sales_proceeds AS ns_procs, lf.credit_enhancement_proceeds AS ce_procs,
          lf.repurchase_makewhole AS rmw_procs, lf.other_foreclosure_proceeds AS o_procs
        FROM disposed d
        LEFT JOIN vendor_terminal t ON d.loan_id = t.loan_id
        LEFT JOIN current_upb_at_resolution u ON d.loan_id = u.loan_id AND u.reporting_month = d.resolution_month
        LEFT JOIN last_rt_at_resolution r ON d.loan_id = r.loan_id
        LEFT JOIN loss_fields_typed lf ON d.loan_id = lf.loan_id
    """)
    duplicate_official_rows = conn.execute('SELECT count(*) - count(DISTINCT loan_id) FROM official').fetchone()[0]
    if duplicate_official_rows:
        raise ValueError(f'official table has {duplicate_official_rows} duplicate loan rows')

    conn.execute(f"ALTER TABLE official ADD COLUMN int_cost DECIMAL(20,2)")
    conn.execute(f"UPDATE official SET int_cost = ({official_int_cost_sql()})")
    conn.execute(f"ALTER TABLE official ADD COLUMN official_net_loss DECIMAL(20,2)")
    conn.execute(f"UPDATE official SET official_net_loss = ({official_net_loss_sql()}) WHERE last_upb IS NOT NULL")
    conn.execute("ALTER TABLE official ADD COLUMN official_net_severity DECIMAL(20,6)")
    conn.execute("UPDATE official SET official_net_severity = official_net_loss / last_upb WHERE last_upb IS NOT NULL AND last_upb != 0")
    conn.execute(f"COPY official TO '{lit(out / 'official.parquet')}' (FORMAT PARQUET)")

    missing_last_upb = conn.execute('SELECT count(*) FROM official WHERE last_upb IS NULL').fetchone()[0]
    official_population = conn.execute('SELECT count(*) FROM official WHERE official_net_loss IS NOT NULL').fetchone()[0]
    official_stats = conn.execute("""
        SELECT count(*), round(avg(official_net_loss),2), round(median(official_net_loss),2),
          min(official_net_loss), max(official_net_loss),
          count(*) FILTER(WHERE official_net_loss < 0), count(*) FILTER(WHERE official_net_loss > last_upb),
          round(avg(official_net_severity),4), median(official_net_severity)
        FROM official WHERE official_net_loss IS NOT NULL
    """).fetchone()
    int_cost_coverage = conn.execute('SELECT count(*) FROM official WHERE int_cost IS NOT NULL').fetchone()[0]
    rate_coverage = conn.execute('SELECT count(*) FROM official WHERE last_rt IS NOT NULL').fetchone()[0]
    # A mortgage note rate outside 0-20% is implausible and indicates a parsing/column error
    # (this caught a real off-by-one column bug during development: an early version read field
    # 10, Original UPB, instead of field 9, Current Interest Rate, producing "rates" like 98000).
    implausible_rate_count = conn.execute('SELECT count(*) FROM official WHERE last_rt IS NOT NULL AND (last_rt < 0 OR last_rt > 20)').fetchone()[0]
    if implausible_rate_count:
        raise ValueError(f'{implausible_rate_count} loans have an implausible last_rt outside 0-20%; likely a column-mapping error')

    # --- Compare against the ORIGINAL, preserved 1,880-loan complete-case figure ---
    conn.execute("CREATE VIEW original_1880 AS SELECT loan_id, net_loss AS original_conservative_net_loss FROM prior_conservative_population")
    overlap = conn.execute("""
        SELECT count(*), round(avg(o.official_net_loss - p.original_conservative_net_loss),2),
          round(median(o.official_net_loss - p.original_conservative_net_loss),2)
        FROM official o JOIN original_1880 p ON o.loan_id = p.loan_id WHERE o.official_net_loss IS NOT NULL
    """).fetchone()
    original_population_count = conn.execute('SELECT count(*) FROM original_1880').fetchone()[0]

    exclusion_reasons = conn.execute("""
        SELECT
          count(*) FILTER(WHERE last_upb IS NULL) AS missing_exposure,
          count(*) FILTER(WHERE last_upb IS NOT NULL AND official_net_loss IS NULL) AS other_exclusion
        FROM official
    """).fetchone()

    recent_disposition_count = conn.execute("SELECT count(*) FROM official WHERE resolution_month >= '2025-03-01'").fetchone()[0]

    checks = {
        'disposed_credit_exit_population': disposed_count,
        'fce_coverage': fce_coverage,
        'fce_coverage_matches_population': fce_coverage == disposed_count,
        'duplicate_official_rows': duplicate_official_rows,
        'missing_last_upb': missing_last_upb,
        'official_population': official_population,
        'original_1880_population_unchanged': original_population_count == 1880,
    }
    status = 'pass' if (
        checks['fce_coverage_matches_population'] and not checks['duplicate_official_rows']
        and checks['original_1880_population_unchanged']
    ) else 'failed'

    result = {
        'status': status,
        'scope': 'Implements Fannie Mae\'s own official credit-event trigger, exposure basis and Net Loss/Net Severity formula (from the retrieved LPPUB_StatFile_Production.R), compared against this project\'s default-proxy anchor. Adds a separately named, wider official-formula population; the original realized_loss_profile.py 1,880-loan complete-case figure is preserved unchanged and re-verified present.',
        'source_stat_unchanged': source_stat_unchanged,
        'checks': checks,
        'code_provenance': {
            'zip_url': 'https://capitalmarkets.fanniemae.com/media/document/zip/FNMA_SF_Loan_Performance_r_Primary.zip',
            'retrieved_via': 'Wayback Machine snapshot 2025-04-01T06:45:26Z (live URL is Cloudflare-blocked from this environment); redirects per its own archived headers to https://capitalmarkets.fanniemae.com/media/20936/display',
            'retrieval_date': datetime.now(timezone.utc).date().isoformat(),
            'file_last_modified_per_archived_headers': '2024-08-02T13:56:53Z',
            'zip_sha256': '00b6798d614ed6af75ed1e79e8908bbb0526f166d4367e4be0334af70ecd6418',
            'inspected_file': 'LPPUB_StatFile_Production.R',
            'inspected_file_sha256': 'd6539dbdf3729879a97905d452bb2890b7b8035b2cdc00d8c035877f09a7fccc',
            'note': 'A historical archived copy, used for historical methodology interpretation; not verified identical to whatever the live site currently serves. Retrieved from a public, unauthenticated Internet Archive URL; no access control was bypassed.',
        },
        'credit_event_trigger_comparison': {
            'vendor_definition': 'zero_balance_code IN (02,03,09,15) OR delinquency_status >= 6 (whichever first) -- a 180-day threshold, not this project\'s 90-day default-proxy anchor',
            'project_definition': 'zero_balance_code IN (02,03,09,15) OR delinquency_status >= 3 (whichever first) -- Phase 2F first_stop, unchanged',
            'population_compared': disposed_count,
            'fce_date_equals_anchor_month': trigger_comparison[1],
            'fce_date_after_anchor_month': trigger_comparison[2],
            'fce_date_before_anchor_month': trigger_comparison[3],
            'mean_month_difference_fce_minus_anchor': str(trigger_comparison[4]),
            'median_month_difference_fce_minus_anchor': trigger_comparison[5],
            'min_month_difference': trigger_comparison[6], 'max_month_difference': trigger_comparison[7],
            'note': 'Confirms matching balances do NOT establish matching event definitions: the two triggers agree on the SAME month for only a minority of loans; for the rest the vendor\'s 180-day threshold fires later than this project\'s 90-day anchor whenever delinquency escalates before an immediate disposition.',
        },
        'official_formula_coverage': {
            'last_upb_available': disposed_count - missing_last_upb,
            'last_upb_missing': missing_last_upb,
            'last_rt_available_via_carry_forward': rate_coverage,
            'int_cost_computed': int_cost_coverage,
            'note': 'last_rt now uses the vendor\'s own last-known-rate-carried-forward logic, not the terminal-row rate alone (which was only 11.4% populated in the prior milestone); this materially improves interest-cost coverage.',
        },
        'official_net_loss_distribution_usd': {
            'population': official_stats[0], 'mean': str(official_stats[1]), 'median': str(official_stats[2]),
            'min': str(official_stats[3]), 'max': str(official_stats[4]),
            'net_gain_count': official_stats[5], 'loss_exceeds_exposure_count': official_stats[6],
            'mean_net_severity': str(official_stats[7]), 'median_net_severity': str(official_stats[8]),
        },
        'comparison_to_original_1880_loan_figure': {
            'original_population_preserved_unchanged': original_population_count,
            'overlap_population': overlap[0],
            'mean_difference_official_minus_original': str(overlap[1]),
            'median_difference_official_minus_original': str(overlap[2]),
            'note': 'Computed only for loans in BOTH populations, to isolate the effect of the corrected formula (rate carry-forward, 35bp deduction, non-interest-bearing-UPB offset, forgiveness as an additive cost) from the effect of the wider population.',
        },
        'population_before_and_after': {
            'original_1880_complete_case_exposure_supported': 1880,
            'vendor_official_all_disposed_with_last_upb': official_population,
            'disposed_credit_exit_total': disposed_count,
            'excluded_missing_exposure_last_upb': exclusion_reasons[0],
            'excluded_other': exclusion_reasons[1],
        },
        'revision_and_as_of_limitations': [
            'This project\'s own default-proxy anchor (90-day) and the vendor\'s FCE trigger (180-day) are genuinely different definitions; equal LAST_UPB values for many loans do not establish that the two triggers fire on the same date (see credit_event_trigger_comparison).',
            f'{recent_disposition_count} of {disposed_count} disposed loans ({recent_disposition_count/disposed_count:.1%}) have a resolution month within the last 12 months of available data; per the official FAQ, proceeds/expenses for recent dispositions are more likely still updating, so their official_net_loss is less likely to be final than an older disposition\'s.',
            'PFG_COST/NON_INT_UPB are read from the SAME resolution-month row as the other terminal fields; the R code\'s exact join chain for these two fields specifically was not traced with full certainty (unlike the exactly-confirmed FCC/PP/AR/IE/TAX/NS/CE/RMW/O/LAST_UPB/LAST_RT/INT_COST logic), so a small discrepancy from the live vendor figure is possible for loans with nonzero forgiveness or modification-related non-interest-bearing UPB.',
            'This is still a retrospective descriptive statistic, now for a wider, officially-defined population. It is not a predictive LGD model: population selection (only disposed loans; the 75.9% of default episodes that never reach disposition are excluded by definition, same as before), cured/unresolved workouts, exposure timing, recovery timing and independent model validation all remain open regardless of formula fidelity.',
        ],
        'input_workout_run': str(workout_dir), 'input_descriptive_run': str(descriptive_dir),
        'input_eligibility_run': str(eligibility_dir), 'input_feasibility_run': str(feasibility_dir),
        'input_reconciliation_run': str(reconciliation_dir), 'input_profile_run': str(profile_dir),
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': round(time.perf_counter() - start, 3),
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'output_directory': str(out),
    }
    conn.close()
    (out / 'vendor_official_loss_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'status': status, 'result': str(out / 'vendor_official_loss_result.json'), 'seconds': result['elapsed_seconds']}), flush=True)
    return result


if __name__ == '__main__':
    run(Path(__file__).resolve().parents[2])
