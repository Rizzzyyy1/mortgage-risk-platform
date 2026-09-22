"""Reconciles the project's descriptive realized-loss profile against Fannie Mae's own official
loss methodology (Loan Performance Data Tutorial, Feb 2021, and the SF Loan Performance FAQs,
2017), using SF-applicable glossary fields not previously extracted: 46 (UPB at the Time of
Removal, the vendor's own "Credit Event UPB" concept), 51 (Last Paid Installment Date, the
official basis for accrued-interest calculation), 63 (Modification-Related Non-Interest Bearing
UPB), 64 (Principal Forgiveness Amount), 80 (Foreclosure Principal Write-off Amount), and 9
(Current Interest Rate). Provenance: the official R reference implementation
(LPPUB_StatFile.R / LPPUB_StatFile_Production.R / LPPUB_StatSummary.R) is linked from
https://capitalmarkets.fanniemae.com/media/9066/display (accessible only via a May 2025 Wayback
Machine snapshot from this environment; the R code's own hosting domain,
loanperformancedata.fanniemae.com, did not resolve from this environment). The plain-English
field definitions in that tutorial and in the official FAQ (fetched directly from Fannie Mae's
own S3-hosted PDF) are used as the reconciliation basis; the exact R formula was not independently
executed. This is disclosed, not assumed away.

Applicability was verified field-by-field against the local combined CRT/SF glossary's own
CAS/CIRT/(SF) checkmark columns, not inferred from any single boilerplate phrase:
- Fields 46, 51, 63, 64, 80: checked SF-applicable (all three columns checked).
- Fields 77/78 (Current/Cumulative Credit Event Net Gain or Loss) and 85 (Delinquent Accrued
  Interest) and 110 (Interest Bearing UPB): checked NA for SF -- these vendor-computed
  convenience totals are CRT-only, so a comparable SF net-loss figure must be built from
  components, which is what realized_loss_profile.py already does.
- Fields 106/107/108 (Alternative Delinquency Resolution, its count, and Total Deferral Amount):
  SF-applicable but "populated starting with the July 2020 activity period" per the glossary --
  a real, checkable population-timing limit for a cohort whose defaults mostly precede July 2020,
  not a claim that deferral/forgiveness data is absent from the dataset (fields 63/64 are
  SF-applicable with no such date restriction and are checked directly below).
"""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint

NEW_FIELDS = {
    46: 'upb_at_removal', 51: 'last_paid_installment_date_raw', 63: 'modification_nib_upb',
    64: 'principal_forgiveness_amount', 80: 'foreclosure_principal_writeoff', 106: 'alt_delinquency_resolution',
    107: 'alt_delinquency_resolution_count', 108: 'total_deferral_amount',
}
RATE_FIELD = {9: 'current_interest_rate'}


def foregone_interest_sql(last_paid_installment_date='last_paid_installment_date', disposition_date='disposition_date',
                           upb_at_removal='upb_at_removal', current_interest_rate='current_interest_rate'):
    # A simple, explicitly labeled, non-compounding monthly approximation: months delinquent
    # (last paid installment date to disposition date) x monthly rate x UPB at removal. This is
    # NOT the vendor's own "Delinquent Accrued Interest" (field 85, CRT-only / NA for SF); it is
    # this project's own derived estimate, built only because the ingredients (date, rate,
    # balance) are SF-applicable even though the vendor's pre-computed convenience field is not.
    # Column references are parameterized so callers can alias them (e.g. a joined table) without
    # fragile string substitution on the returned SQL text.
    return (
        f"CASE WHEN {last_paid_installment_date} IS NOT NULL AND {disposition_date} IS NOT NULL "
        f"AND {upb_at_removal} IS NOT NULL AND {current_interest_rate} IS NOT NULL "
        f"AND {disposition_date} >= {last_paid_installment_date} THEN "
        f"{upb_at_removal} * ({current_interest_rate} / 100.0 / 12.0) * "
        f"date_diff('month', {last_paid_installment_date}, {disposition_date}) END"
    )


def run(root):
    root = Path(root).resolve()
    start = time.perf_counter()
    source = root / 'data/raw/fannie_mae_loan_performance/2010Q1.csv'
    before = source.stat()
    workout_dir = root / 'artifacts/runs/loss_workout_linkage/b2ebdeb7319a4a6486c84b4ad02414f1'
    exposure_dir = root / 'artifacts/runs/default_anchor_exposure/62355abf161f4a9fbd86b0f6401beb36'
    feasibility_dir = root / 'artifacts/runs/loss_feasibility/30a0a02381af4b93807301fc6ef08d90'
    profile_dir = root / 'artifacts/runs/realized_loss_profile/f63257e5acb54101abb2a4d0cb30e8a4'
    workout_result = json.loads(next(workout_dir.glob('*_result.json')).read_text())
    exposure_result = json.loads(next(exposure_dir.glob('*_result.json')).read_text())
    profile_result = json.loads(next(profile_dir.glob('*_result.json')).read_text())
    if workout_result['status'] != 'pass' or exposure_result['status'] != 'pass' or profile_result['status'] != 'pass':
        raise ValueError('One or more input runs not accepted')

    out = root / 'artifacts/runs/vendor_method_reconciliation' / uuid.uuid4().hex
    out.mkdir(parents=True)
    conn = duckdb.connect(str(out / 'reconciliation.db'))
    conn.execute("SET memory_limit='2GB'")
    conn.execute('SET threads=2')

    def lit(path):
        return str(path).replace("'", "''")

    columns = {f'c{i}': 'VARCHAR' for i in range(113)}
    conn.execute(f"CREATE VIEW raw AS SELECT * FROM read_csv('{lit(source)}', header=false, sep='|', columns={columns}, quote='', escape='', parallel=False)")
    field_select = ','.join(f"nullif(trim(c{pos - 1}),'') {name}" for pos, name in {**NEW_FIELDS, **RATE_FIELD}.items())
    where_clause = ' OR '.join(f"nullif(trim(c{pos - 1}),'') IS NOT NULL" for pos in NEW_FIELDS)
    print('Scanning 2010Q1 once for eight new SF-applicable fields (46,51,63,64,80,106,107,108) plus rate', flush=True)
    conn.execute(f"""
        CREATE TABLE vendor_rows AS
        SELECT c1 loan_id, c2 reporting_month_raw, {field_select}
        FROM raw WHERE {where_clause}
    """)
    after = source.stat()
    source_stat_unchanged = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    if not source_stat_unchanged:
        raise ValueError('Source changed during scan')

    field_coverage = {}
    for pos, name in NEW_FIELDS.items():
        conversion = f"try_strptime({name},'%m%Y')" if name.endswith('_date_raw') else f"try_cast({name} AS DECIMAL(20,2))"
        row = conn.execute(f"SELECT count({name}), count(DISTINCT loan_id) FILTER(WHERE {name} IS NOT NULL), "
                            f"count(*) FILTER(WHERE {name} IS NOT NULL AND {conversion} IS NULL) FROM vendor_rows").fetchone()
        field_coverage[name] = {'position': pos, 'nonblank_rows': row[0], 'loans': row[1], 'conversion_failures': row[2]}

    conn.execute(f"COPY vendor_rows TO '{lit(out / 'vendor_rows.parquet')}' (FORMAT PARQUET)")
    conn.execute(f"CREATE VIEW workout_episodes AS SELECT * FROM read_parquet('{lit(workout_dir / 'workout_episodes.parquet')}')")
    conn.execute(f"CREATE VIEW anchor_exposure AS SELECT * FROM read_parquet('{lit(exposure_dir / 'anchor_exposure.parquet')}')")
    conn.execute(f"CREATE VIEW loss_fields AS SELECT * FROM read_parquet('{lit(feasibility_dir / 'loss_fields.parquet')}')")
    conn.execute(f"CREATE VIEW analysis_population AS SELECT * FROM read_parquet('{lit(profile_dir / 'analysis_population.parquet')}')")

    typed_loss = ','.join(f"try_cast({f} AS DECIMAL(18,2)) {f}" for f in
                           ('foreclosure_costs', 'preservation_repair', 'asset_recovery_costs', 'holding_expenses_credits',
                            'taxes', 'net_sales_proceeds', 'credit_enhancement_proceeds', 'repurchase_makewhole', 'other_foreclosure_proceeds'))
    conn.execute(f"CREATE VIEW loss_fields_typed AS SELECT loan_id, try_strptime(reporting_month_raw,'%m%Y')::DATE disposition_date, {typed_loss} FROM loss_fields")
    conn.execute("""
        CREATE VIEW vendor_typed AS
        SELECT loan_id, try_strptime(reporting_month_raw,'%m%Y')::DATE reporting_month,
          try_cast(upb_at_removal AS DECIMAL(18,2)) upb_at_removal,
          try_strptime(last_paid_installment_date_raw,'%m%Y')::DATE last_paid_installment_date,
          try_cast(modification_nib_upb AS DECIMAL(18,2)) modification_nib_upb,
          try_cast(principal_forgiveness_amount AS DECIMAL(18,2)) principal_forgiveness_amount,
          try_cast(foreclosure_principal_writeoff AS DECIMAL(18,2)) foreclosure_principal_writeoff,
          try_cast(current_interest_rate AS DECIMAL(8,3)) current_interest_rate,
          alt_delinquency_resolution, total_deferral_amount
        FROM vendor_rows
    """)
    duplicate_loan_months = conn.execute('SELECT count(*) - count(DISTINCT (loan_id, reporting_month)) FROM vendor_typed').fetchone()[0]
    if duplicate_loan_months:
        raise ValueError(f'vendor_typed has {duplicate_loan_months} duplicate loan-month keys')

    # upb_at_removal/last_paid_installment_date/foreclosure_principal_writeoff/current_interest_rate
    # are populated "as a loan hits a Zero Balance Code" (the tutorial/FAQ language), so they are
    # joined to the SAME row as this loan's own resolution_month, never to an arbitrary qualifying
    # row -- a loan can have many other qualifying rows (e.g. a recurring alternative-delinquency-
    # resolution flag populated every month), and joining on loan_id alone would fan out one loan
    # into many result rows. Duplicate keys are asserted below before building comparison.
    conn.execute("""
        CREATE VIEW vendor_terminal AS
        SELECT w.loan_id, w.resolution_month, v.upb_at_removal, v.last_paid_installment_date,
          v.foreclosure_principal_writeoff, v.current_interest_rate
        FROM workout_episodes w
        LEFT JOIN vendor_typed v ON w.loan_id = v.loan_id AND v.reporting_month = w.resolution_month
        WHERE w.category = 'disposed_credit_exit'
    """)
    # Modification-related fields (63/64) and the alternative-delinquency-resolution fields
    # (106-108) can be populated on any row across a loan's life, not only its terminal row, so
    # they are aggregated per loan instead of month-matched: "ever" observed a nonzero value.
    conn.execute("""
        CREATE TABLE vendor_ever AS
        SELECT loan_id,
          max(modification_nib_upb) FILTER(WHERE modification_nib_upb != 0) AS max_modification_nib_upb,
          count(*) FILTER(WHERE modification_nib_upb IS NOT NULL AND modification_nib_upb != 0) > 0 AS ever_modification_nib_upb_nonzero,
          max(principal_forgiveness_amount) FILTER(WHERE principal_forgiveness_amount != 0) AS max_principal_forgiveness_amount,
          count(*) FILTER(WHERE principal_forgiveness_amount IS NOT NULL AND principal_forgiveness_amount != 0) > 0 AS ever_principal_forgiveness_nonzero,
          max(total_deferral_amount::DECIMAL(18,2)) FILTER(WHERE try_cast(total_deferral_amount AS DECIMAL(18,2)) != 0) AS max_total_deferral_amount,
          count(*) FILTER(WHERE total_deferral_amount IS NOT NULL AND try_cast(total_deferral_amount AS DECIMAL(18,2)) != 0) > 0 AS ever_total_deferral_amount_nonzero
        FROM vendor_typed GROUP BY loan_id
    """)
    duplicate_terminal_rows = conn.execute('SELECT count(*) - count(DISTINCT loan_id) FROM vendor_terminal').fetchone()[0]
    if duplicate_terminal_rows:
        raise ValueError(f'vendor_terminal join produced {duplicate_terminal_rows} duplicate loan rows')

    conn.execute(f"""
        CREATE TABLE comparison AS
        SELECT a.loan_id, a.anchor_month, a.resolution_month, a.anchor_current_actual_upb,
          a.net_loss AS project_net_loss_conservative,
          t.upb_at_removal, t.last_paid_installment_date, t.foreclosure_principal_writeoff, t.current_interest_rate,
          e.max_modification_nib_upb, e.ever_modification_nib_upb_nonzero,
          e.max_principal_forgiveness_amount, e.ever_principal_forgiveness_nonzero,
          e.max_total_deferral_amount, e.ever_total_deferral_amount_nonzero,
          lf.disposition_date,
          COALESCE(a.foreclosure_costs,0)+COALESCE(a.preservation_repair,0)+COALESCE(a.asset_recovery_costs,0)
            +COALESCE(a.holding_expenses_credits,0)+COALESCE(a.taxes,0) AS total_costs_zero_filled,
          COALESCE(a.net_sales_proceeds,0)+COALESCE(a.credit_enhancement_proceeds,0)
            +COALESCE(a.repurchase_makewhole,0)+COALESCE(a.other_foreclosure_proceeds,0) AS total_proceeds_zero_filled,
          ({foregone_interest_sql(last_paid_installment_date='t.last_paid_installment_date', disposition_date='a.resolution_month', upb_at_removal='t.upb_at_removal', current_interest_rate='t.current_interest_rate')}) AS estimated_foregone_interest
        FROM analysis_population a
        LEFT JOIN vendor_terminal t ON a.loan_id = t.loan_id
        LEFT JOIN vendor_ever e ON a.loan_id = e.loan_id
        LEFT JOIN loss_fields_typed lf ON a.loan_id = lf.loan_id
    """)
    conn.execute("""
        ALTER TABLE comparison ADD COLUMN vendor_anchored_net_loss DECIMAL(20,2);
        UPDATE comparison SET vendor_anchored_net_loss =
          COALESCE(upb_at_removal, anchor_current_actual_upb) + total_costs_zero_filled
          + COALESCE(estimated_foregone_interest,0) - total_proceeds_zero_filled;
    """)
    conn.execute("""
        ALTER TABLE comparison ADD COLUMN faq_zero_filled_net_loss DECIMAL(20,2);
        UPDATE comparison SET faq_zero_filled_net_loss =
          anchor_current_actual_upb + total_costs_zero_filled - total_proceeds_zero_filled;
    """)
    conn.execute(f"COPY comparison TO '{lit(out / 'comparison.parquet')}' (FORMAT PARQUET)")

    population_count = conn.execute('SELECT count(*) FROM analysis_population').fetchone()[0]
    matched_upb_at_removal = conn.execute('SELECT count(*) FROM comparison WHERE upb_at_removal IS NOT NULL').fetchone()[0]
    matched_last_paid = conn.execute('SELECT count(*) FROM comparison WHERE last_paid_installment_date IS NOT NULL').fetchone()[0]
    matched_rate = conn.execute('SELECT count(*) FROM comparison WHERE current_interest_rate IS NOT NULL').fetchone()[0]
    estimated_interest_available = conn.execute('SELECT count(*) FROM comparison WHERE estimated_foregone_interest IS NOT NULL').fetchone()[0]
    forgiveness_nonzero = conn.execute('SELECT count(*) FROM comparison WHERE ever_principal_forgiveness_nonzero').fetchone()[0]
    modification_nib_nonzero = conn.execute('SELECT count(*) FROM comparison WHERE ever_modification_nib_upb_nonzero').fetchone()[0]
    deferral_nonzero = conn.execute('SELECT count(*) FROM comparison WHERE ever_total_deferral_amount_nonzero').fetchone()[0]
    writeoff_nonzero = conn.execute('SELECT count(*) FROM comparison WHERE foreclosure_principal_writeoff IS NOT NULL AND foreclosure_principal_writeoff != 0').fetchone()[0]

    exposure_diff = conn.execute("""
        SELECT round(avg(upb_at_removal - anchor_current_actual_upb),2), round(median(upb_at_removal - anchor_current_actual_upb),2),
          min(upb_at_removal - anchor_current_actual_upb), max(upb_at_removal - anchor_current_actual_upb),
          count(*) FILTER(WHERE upb_at_removal > anchor_current_actual_upb), count(*) FILTER(WHERE upb_at_removal < anchor_current_actual_upb)
        FROM comparison WHERE upb_at_removal IS NOT NULL
    """).fetchone()

    loss_variants = conn.execute("""
        SELECT
          round(avg(project_net_loss_conservative),2), round(median(project_net_loss_conservative),2),
          round(avg(faq_zero_filled_net_loss),2), round(median(faq_zero_filled_net_loss),2),
          round(avg(vendor_anchored_net_loss) FILTER(WHERE upb_at_removal IS NOT NULL),2),
          round(median(vendor_anchored_net_loss) FILTER(WHERE upb_at_removal IS NOT NULL),2),
          count(*) FILTER(WHERE upb_at_removal IS NOT NULL)
        FROM comparison
    """).fetchone()

    # Bounded, deterministic, hand-traceable sample: one loan per requested category where
    # available, chosen by lowest loan_id for determinism.
    def one_sample(where):
        row = conn.execute(f"SELECT * FROM comparison WHERE {where} ORDER BY loan_id LIMIT 1").fetchone()
        if row is None:
            return None
        cols = [d[0] for d in conn.description]
        return dict(zip(cols, row))

    samples = {
        'complete_disposed_with_upb_at_removal': one_sample('upb_at_removal IS NOT NULL'),
        'missing_upb_at_removal': one_sample('upb_at_removal IS NULL'),
        'modification_or_forgiveness_present': one_sample('ever_principal_forgiveness_nonzero OR ever_modification_nib_upb_nonzero'),
        'foreclosure_writeoff_present': one_sample('foreclosure_principal_writeoff IS NOT NULL AND foreclosure_principal_writeoff!=0'),
        'negative_project_net_loss_net_gain': one_sample('project_net_loss_conservative < 0'),
        'project_net_loss_exceeds_exposure': one_sample('project_net_loss_conservative > anchor_current_actual_upb'),
    }
    cure_redefault_row = conn.execute("""
        SELECT loan_id, category, redefault_count, path_json FROM workout_episodes
        WHERE category='disposed_credit_exit' AND redefault_count>0 ORDER BY loan_id LIMIT 1
    """).fetchone()
    samples['cure_redefault_before_disposition'] = (
        {'loan_id': cure_redefault_row[0], 'category': cure_redefault_row[1],
         'redefault_count': cure_redefault_row[2], 'path_json': cure_redefault_row[3]}
        if cure_redefault_row else None
    )

    exit_type_samples = {}
    for code, label in [('02', 'third_party_sale'), ('03', 'short_sale'), ('09', 'deed_in_lieu_reo'), ('15', 'note_sale')]:
        row = conn.execute(f"""
            SELECT c.loan_id, c.resolution_month, c.anchor_current_actual_upb, c.upb_at_removal
            FROM comparison c JOIN loss_fields lf2 ON c.loan_id = lf2.loan_id
            WHERE lf2.exit_code = '{code}' ORDER BY c.loan_id LIMIT 1
        """).fetchone()
        if row:
            exit_type_samples[label] = {'loan_id': row[0], 'resolution_month': str(row[1]), 'anchor_current_actual_upb': str(row[2]), 'upb_at_removal': str(row[3]) if row[3] is not None else None}
    samples['by_exit_type'] = exit_type_samples

    result = {
        'status': 'pass',
        'scope': 'Field-level reconciliation of the project realized-loss profile against Fannie Mae\'s own official Loan Performance Data Tutorial (Feb 2021) and SF Loan Performance FAQ (2017) definitions, using SF-applicable glossary fields 46/51/63/64/80/9 not previously extracted. Descriptive comparison only; does not itself constitute an accepted LGD model.',
        'source_stat_unchanged': source_stat_unchanged,
        'field_coverage_full_2010Q1_scan': field_coverage,
        'population': {
            'complete_case_exposure_supported_disposed_loans': population_count,
            'matched_upb_at_removal': matched_upb_at_removal,
            'matched_upb_at_removal_share': round(matched_upb_at_removal / population_count, 4),
            'matched_last_paid_installment_date': matched_last_paid,
            'matched_current_interest_rate': matched_rate,
            'estimated_foregone_interest_available': estimated_interest_available,
            'ever_principal_forgiveness_nonzero': forgiveness_nonzero,
            'ever_modification_nib_upb_nonzero': modification_nib_nonzero,
            'ever_total_deferral_amount_nonzero': deferral_nonzero,
            'foreclosure_principal_writeoff_at_removal_nonzero': writeoff_nonzero,
        },
        'exposure_denominator_comparison_upb_at_removal_minus_anchor_upb': {
            'mean_difference': str(exposure_diff[0]), 'median_difference': str(exposure_diff[1]),
            'min_difference': str(exposure_diff[2]), 'max_difference': str(exposure_diff[3]),
            'removal_exceeds_anchor_count': exposure_diff[4], 'removal_below_anchor_count': exposure_diff[5],
            'note': 'anchor_current_actual_upb is the balance at the FIRST 90+ day default proxy month (this project\'s definition); upb_at_removal (field 46) is the vendor\'s own balance at the credit-event/removal month. These measure different things by design; the difference reflects scheduled amortization, capitalized arrears and any modification/forgiveness between the two dates, not an error in either figure.',
        },
        'net_loss_variants_usd': {
            'project_conservative_mean': str(loss_variants[0]), 'project_conservative_median': str(loss_variants[1]),
            'faq_zero_filled_mean': str(loss_variants[2]), 'faq_zero_filled_median': str(loss_variants[3]),
            'vendor_anchored_mean': str(loss_variants[4]), 'vendor_anchored_median': str(loss_variants[5]),
            'vendor_anchored_population': loss_variants[6],
            'definitions': {
                'project_conservative': 'realized_loss_profile.py Milestone 3 figure: anchor UPB + 5 cost fields - 4 proceeds fields, blanks excluded from the population (not zero-filled).',
                'faq_zero_filled': 'Same anchor UPB and cost/proceeds fields, but blanks in the nine fields are treated as zero per the official FAQ Q42 ("a NULL (blank) value should be treated as a zero (0)"), applied only to this named variant. NOTE: because realized_loss_profile.py\'s population is already restricted to loans with all nine fields present (complete-case), this variant is numerically identical to project_conservative for THIS population by construction -- there are no blanks left for the FAQ convention to fill here. The convention\'s real value would be in expanding the population to loans with some missing fields, which was not computed in this pass and remains a separate, well-scoped next step.',
                'vendor_anchored': 'upb_at_removal (official Credit-Event-UPB concept, field 46) in place of anchor UPB, plus this project\'s own estimated_foregone_interest (NOT the vendor\'s CRT-only Delinquent Accrued Interest field), plus the same zero-filled costs/proceeds. Only computed where upb_at_removal is present.',
            },
        },
        'manually_traceable_samples': {k: (v if v is None else {kk: str(vv) for kk, vv in v.items()}) for k, v in samples.items() if k != 'by_exit_type'},
        'manually_traceable_samples_by_exit_type': exit_type_samples,
        'methodology_comparison_table': [
            {'item': 'Credit-event definition and date', 'category': 'B', 'note': 'Official "Credit Event Date"/"Credit Event UPB" concepts are named and defined in the tutorial; the exact R-code trigger logic (which zero-balance codes / delinquency thresholds constitute a "credit event") was not independently inspected because the R code\'s hosting domain (loanperformancedata.fanniemae.com) did not resolve from this environment. This project\'s own default-proxy definition (03-99 delinquency or codes 02/03/09/15) remains a distinct, documented project convention, not asserted equal to the vendor\'s.'},
            {'item': 'Exposure denominator and timing', 'category': 'A', 'note': 'Resolved this session: field 46 (UPB at the Time of Removal) is SF-applicable and is the vendor\'s own credit-event exposure concept, distinct from this project\'s default-anchor UPB. Both are now computed and compared above (see exposure_denominator_comparison).'},
            {'item': 'First 90+ default vs. vendor event conventions', 'category': 'E', 'note': 'The tutorial defines a separate "First 180 Date"/"First 180 UPB" milestone (180-day, not 90-day, delinquency) alongside "Credit Event Date". Whether the vendor\'s R code treats "credit event" as equivalent to a specific zero-balance code, to First 180, or to something else was not independently confirmed (see item above); this remains genuinely unclear pending access to the R code.'},
            {'item': 'Credit-event/removal UPB vs. first-default UPB', 'category': 'A', 'note': 'Resolved: see exposure_denominator_comparison_upb_at_removal_minus_anchor_upb above.'},
            {'item': 'Interest calculation and required dates/rates', 'category': 'C', 'note': 'The vendor\'s own convenience fields (Delinquent Accrued Interest, field 85; Interest Bearing UPB, field 110) are confirmed NA for Single-Family in the local glossary\'s own checkmark columns -- CRT-only. Field 51 (Last Paid Installment Date) and field 9 (Current Interest Rate) ARE SF-applicable and are used here to derive a project-specific, clearly labeled, non-compounding foregone-interest approximation (estimated_foregone_interest); this is derivable under an explicit, disclosed convention, not an official vendor number.'},
            {'item': 'Expense and recovery categories', 'category': 'A', 'note': 'Already extracted and reconciled (loss_feasibility.py, realized_loss_profile.py): fields 54-58 (costs) and 59-62 (proceeds), all confirmed SF-applicable.'},
            {'item': 'Missing-value treatment', 'category': 'A', 'note': 'Resolved this session: the official FAQ (Q42) states blank should be treated as zero for these nine fields, directly overriding this project\'s earlier general no-zero-fill assumption for these specific fields. Applied as a separately named variant (faq_zero_filled_net_loss), not a silent change to the conservative figure.'},
            {'item': 'Forgiveness, non-interest-bearing UPB and deferrals', 'category': 'A', 'note': 'Resolved this session: fields 63 (Modification-Related Non-Interest Bearing UPB) and 64 (Principal Forgiveness Amount) are confirmed SF-applicable with no population-date restriction, and are now extracted and counted above. Fields 106-108 (Alternative Delinquency Resolution / count / Total Deferral Amount) are also SF-applicable but the glossary states they are "populated starting with the July 2020 activity period" -- a real, checkable population-timing limit for this cohort, not an assumption that forgiveness/deferral data is absent from the dataset.'},
            {'item': 'Observation cutoff, revisions and settlement completeness', 'category': 'A', 'note': 'Resolved and refined this session: the official SF-Primary FAQ (Q41/Q43, not the CRT-context glossary note previously cited) states proceeds/expenses populate on a 90-day lag after the Disposition Date and continue to be updated "in the same record" as activity occurs, especially for more recent Disposition Dates. This is a more directly SF-applicable explanation than the "individual CRT deal claims and reporting timelines" phrase this project\'s prior milestone leaned on; that phrase also appears on the CRT-only fields 77/78/85, suggesting it is shared glossary boilerplate rather than proof that SF proceeds depend on CRT reinsurance claims specifically. The underlying caution (populated is not proven final) still stands, now on firmer, SF-specific evidence.'},
        ],
        'input_workout_run': str(workout_dir), 'input_exposure_run': str(exposure_dir),
        'input_feasibility_run': str(feasibility_dir), 'input_profile_run': str(profile_dir),
        'tutorial_provenance': {
            'document': 'Fannie Mae Loan Performance Data Tutorial: Getting Started with Fannie Mae\'s Single-Family Dataset, February 2021',
            'accessed_via': 'Wayback Machine snapshot dated 2025-05-16 of https://capitalmarkets.fanniemae.com/media/9066/display (the live page returns a Cloudflare bot challenge from this environment)',
            'r_code_hosting_domain_not_reachable': 'loanperformancedata.fanniemae.com (DNS did not resolve from this environment; likely the legacy pre-Data-Dynamics portal)',
            'faq_document': 'Fannie Mae Single-Family Loan Performance Data Frequently Asked Questions, 2017 (fetched directly from Fannie Mae\'s S3-hosted PDF, https://s3.amazonaws.com/dq-blog-files/lppub_faq.pdf)',
        },
        'glossary_sha256': fingerprint(root / 'data/raw/fannie_mae_loan_performance/crt-file-layout-and-glossary.pdf'),
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': round(time.perf_counter() - start, 3),
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'output_directory': str(out),
        'limitations': [
            'This is a field-level and definitional reconciliation, not an execution of Fannie Mae\'s own R code against our data; no byte-identical replication is claimed.',
            'estimated_foregone_interest is this project\'s own simple approximation (UPB at removal x monthly rate x months since last paid installment), not the vendor\'s CRT-only Delinquent Accrued Interest field.',
            'vendor_anchored_net_loss and faq_zero_filled_net_loss are named, disclosed variants alongside the original conservative figure; none is presented as a validated LGD/severity model.',
            'The reconciliation population is still the 1,880-loan complete-case, exposure-supported disposed subset (21.5% of all default episodes), not a representative severity sample.',
        ],
    }
    conn.close()
    (out / 'vendor_reconciliation_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'status': 'pass', 'result': str(out / 'vendor_reconciliation_result.json'), 'seconds': result['elapsed_seconds']}), flush=True)
    return result


if __name__ == '__main__':
    run(Path(__file__).resolve().parents[2])
