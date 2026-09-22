"""Parameterized cohort adapter for the frozen multi-cohort redevelopment design
(configs/multi_cohort_redevelopment.json). Generalizes external_cohort.py (which remains
untouched and immutable, describing only the original 2011Q1/2012-01/2013-01 evaluation) to an
arbitrary source file, snapshot date and outcome-end date, reusing the identical event/outcome
contract and feature logic. Source controls (checksum, size, layout), then frozen snapshot-time
features, then (only when explicitly requested) future-outcome labels -- the two are always
separable calls so a cohort's labels can be withheld past its features being built, which is how
the 2013Q1 final-test outcome-blindness restriction is enforced structurally, not just by
convention.
"""
import json
import time
import uuid
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint
from mortgage_risk.portfolio_descriptive import event_rows_sql, loan_outcomes_sql
from mortgage_risk.expanded_features import feature_sql

FEATURE_POSITIONS = {'borrower_fico': 23, 'ltv': 19, 'dti': 22, 'original_term': 12, 'occupancy': 29, 'purpose': 26}


def label_sql(outcome_end_date):
    return f"""SELECT f.loan_id,f.reporting_month,CASE
      WHEN stop_month<=DATE '{outcome_end_date}' AND first_stop IN ('default_proxy','payoff_or_maturity') THEN first_stop
      WHEN stop_month<DATE '{outcome_end_date}' AND first_stop IS NOT NULL THEN 'censored_or_unresolved'
      WHEN stop_month=DATE '{outcome_end_date}' AND first_stop!='gap_censor' THEN 'censored_or_unresolved'
      WHEN last_month>=DATE '{outcome_end_date}' THEN 'observed_event_free_12m'
      ELSE 'incomplete_followup' END outcome_12m
      FROM expanded f JOIN outcomes o USING(loan_id)"""


def build_features(conn, source, snapshot_date, other_cohort_loan_id_parquets):
    """Scans the source CSV once; verifies keys, all-cohort loan-ID disjointness and snapshot
    eligibility; freezes snapshot-time predictors only. Returns the in-memory 'expanded' table
    name and a dict of diagnostic counts. Never reads a row from beyond snapshot_date."""
    conn.read_csv(str(source), header=False, sep='|', columns={f'c{i}': 'VARCHAR' for i in range(113)},
                  quotechar='', escapechar='', parallel=False).create_view('raw')
    extras = ','.join(f"CASE WHEN c2=strftime(DATE '{snapshot_date}','%m%Y') THEN nullif(trim(c{pos}),'') END {name}"
                       for name, pos in FEATURE_POSITIONS.items())
    conn.execute(
        "CREATE TABLE panel AS SELECT c1 loan_id,c2 month_raw,"
        "CASE WHEN regexp_full_match(c2,'[0-9]{6}') THEN cast(try_strptime(c2,'%m%Y') AS DATE) END reporting_month,"
        "nullif(trim(c39),'') delinquency_status,nullif(trim(c43),'') zero_balance_code,"
        f"nullif(trim(c41),'') modification_status,{extras} FROM raw"
    )
    invalid = conn.execute("SELECT count(*) FROM panel WHERE loan_id IS NULL OR NOT regexp_full_match(loan_id,'[0-9]{12}') OR reporting_month IS NULL").fetchone()[0]
    duplicates = conn.execute('SELECT count(*) FROM (SELECT loan_id,reporting_month FROM panel GROUP BY 1,2 HAVING count(*)>1)').fetchone()[0]
    if invalid or duplicates:
        raise ValueError(f'Invalid keys {invalid}; duplicates {duplicates}')
    overlaps = {}
    for label, path in other_cohort_loan_id_parquets.items():
        conn.execute(f"CREATE OR REPLACE VIEW other_{label} AS SELECT DISTINCT loan_id FROM read_parquet('{str(path).replace(chr(39), chr(39)*2)}')")
        overlaps[label] = conn.execute(f'SELECT count(DISTINCT loan_id) FROM panel JOIN other_{label} USING(loan_id)').fetchone()[0]
    if any(overlaps.values()):
        raise ValueError(f'Loan-ID overlap with other cohorts: {overlaps}')
    source_summary = dict(zip(
        ['records', 'loans', 'first_month', 'last_month'],
        conn.execute('SELECT count(*) records,count(DISTINCT loan_id) loans,min(reporting_month) first_month,max(reporting_month) last_month FROM panel').fetchone()
    ))
    conn.execute(f"CREATE VIEW presnapshot AS SELECT * FROM panel WHERE reporting_month<=DATE '{snapshot_date}'")
    conn.execute('CREATE TABLE past_events AS ' + event_rows_sql().replace('FROM panel', 'FROM presnapshot'))
    conn.execute('CREATE TABLE past_outcomes AS ' + loan_outcomes_sql().replace('FROM event_rows', 'FROM past_events'))
    conn.execute(
        "CREATE VIEW training AS SELECT p.loan_id,p.reporting_month,try_cast(p.delinquency_status AS INTEGER) delinquency_months,p.modification_status "
        f"FROM presnapshot p JOIN past_outcomes o USING(loan_id) WHERE p.reporting_month=DATE '{snapshot_date}' "
        "AND o.at_risk_at_entry AND o.first_stop IS NULL AND try_cast(p.delinquency_status AS INTEGER) BETWEEN 0 AND 2"
    )
    conn.execute(f"CREATE VIEW factors AS SELECT loan_id,month_raw reporting_month_raw,borrower_fico,ltv,dti,original_term,occupancy,purpose FROM panel WHERE reporting_month=DATE '{snapshot_date}'")
    conn.execute('CREATE TABLE expanded AS SELECT * EXCLUDE(development_split) FROM (' + feature_sql() + ')')
    snapshot_count = conn.execute(f"SELECT count(*) FROM panel WHERE reporting_month=DATE '{snapshot_date}'").fetchone()[0]
    count = conn.execute('SELECT count(*) FROM expanded').fetchone()[0]
    if not count or count != conn.execute('SELECT count(*) FROM training').fetchone()[0]:
        raise ValueError('Feature join mismatch')
    quality = {name: conn.execute(f'SELECT {name}_quality quality,count(*) records FROM expanded GROUP BY 1').fetchall() for name in FEATURE_POSITIONS}
    if any(row[0] == 'invalid' for rows in quality.values() for row in rows):
        raise ValueError('Invalid predictor values require review before outcomes')
    return {'source_summary': source_summary, 'invalid_keys': invalid, 'duplicates': duplicates,
            'overlaps': overlaps, 'snapshot_records': snapshot_count, 'feature_records': count,
            'quality': {k: [{'quality': r[0], 'records': r[1]} for r in v] for k, v in quality.items()}}


def build_labels(conn, outcome_end_date, expected_count):
    conn.execute('CREATE TABLE event_rows AS ' + event_rows_sql())
    conn.execute('CREATE TABLE outcomes AS ' + loan_outcomes_sql())
    conn.execute('CREATE TABLE labels AS ' + label_sql(outcome_end_date))
    if conn.execute('SELECT count(*) FROM labels').fetchone()[0] != expected_count:
        raise ValueError('Label count mismatch')
    return conn.execute('SELECT outcome_12m,count(*) records FROM labels GROUP BY 1').fetchall()


def run(root, cohort, source_relpath, snapshot_date, outcome_end_date, other_cohort_loan_id_parquets, build_labels_now):
    root = Path(root).resolve()
    start = time.perf_counter()
    source = root / source_relpath
    receipt_path = Path(str(source) + '.receipt.json')
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
    before = source.stat()
    if receipt and before.st_size != receipt['bytes']:
        raise ValueError('Source size changed since receipt')
    out = root / 'artifacts/runs/multi_cohort_adapter' / uuid.uuid4().hex
    out.mkdir(parents=True)
    conn = duckdb.connect(str(out / 'cohort.db'))
    conn.execute("SET memory_limit='2GB'")
    conn.execute('SET threads=2')
    print(f'Bulk scanning {cohort} ({source.stat().st_size/1e9:.1f} GB); snapshot {snapshot_date}, features only until labels are explicitly requested', flush=True)
    feature_info = build_features(conn, source, snapshot_date, other_cohort_loan_id_parquets)
    path = out / 'features.parquet'
    conn.execute('COPY expanded TO ? (FORMAT PARQUET)', [str(path)])
    feature_receipt = {'cohort': cohort, 'snapshot_date': snapshot_date, 'feature_sha256': fingerprint(path),
                        **feature_info, 'other_cohorts_checked': list(other_cohort_loan_id_parquets)}
    (out / 'feature_freeze.json').write_text(json.dumps(feature_receipt, indent=2, default=str) + '\n')
    label_counts = None
    if build_labels_now:
        print(f'Constructing outcomes through {outcome_end_date}', flush=True)
        label_counts = build_labels(conn, outcome_end_date, feature_info['feature_records'])
        conn.execute('COPY labels TO ? (FORMAT PARQUET)', [str(out / 'labels.parquet')])
    after = source.stat()
    if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
        raise ValueError('Source changed during processing')
    result = {
        'status': 'features_frozen_labels_withheld' if not build_labels_now else 'pass_for_cohort_adapter',
        'cohort': cohort, 'snapshot_date': snapshot_date,
        'outcome_end_date': outcome_end_date if build_labels_now else None,
        'source_receipt': receipt, 'feature_freeze': feature_receipt,
        'outcomes': [{'outcome_12m': r[0], 'records': r[1]} for r in label_counts] if label_counts else None,
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': time.perf_counter() - start,
        'limitations': [
            'File cohort identity derives from user download and filename, not a vendor-signed acquisition manifest.',
            '113-column schema matches inspected glossary positions; full balance audit is outside this predictor/event adapter.',
            'Current release may contain revisions unavailable at historical prediction time.',
            'No fitting, recalibration or promotion performed by this adapter.',
        ],
    }
    conn.close()
    (out / 'cohort_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'status': result['status'], 'result': str(out / 'cohort_result.json')}), flush=True)
    return result, out
