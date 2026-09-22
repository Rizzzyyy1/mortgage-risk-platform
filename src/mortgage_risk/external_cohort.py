"""Reserved-cohort adapter: source controls, frozen features, then labels."""
import json,time,uuid
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint
from mortgage_risk.external_readiness import check
from mortgage_risk.portfolio_descriptive import event_rows_sql,loan_outcomes_sql
from mortgage_risk.expanded_features import feature_sql


def label_sql():
    return """SELECT f.loan_id,f.reporting_month,CASE
      WHEN stop_month<=DATE '2013-01-01' AND first_stop IN ('default_proxy','payoff_or_maturity') THEN first_stop
      WHEN stop_month<DATE '2013-01-01' AND first_stop IS NOT NULL THEN 'censored_or_unresolved'
      WHEN stop_month=DATE '2013-01-01' AND first_stop!='gap_censor' THEN 'censored_or_unresolved'
      WHEN last_month>=DATE '2013-01-01' THEN 'observed_event_free_12m'
      ELSE 'incomplete_followup' END outcome_12m
      FROM expanded f JOIN outcomes o USING(loan_id)"""


def run(root):
    root=Path(root).resolve();start=time.perf_counter();state=check(root)
    if state['status']!='source_present_validation_required':raise ValueError('Reserved source absent')
    cfg=json.loads((root/'configs/external_evaluation.json').read_text())
    if (cfg['snapshot_date'],cfg['horizon_date'])!=('2012-01-01','2013-01-01'):raise ValueError('Adapter not validated for a changed date contract')
    source=Path(state['expected_source']);before=source.stat();receipt=json.loads(Path(str(source)+'.receipt.json').read_text())
    if before.st_size!=receipt['bytes']:raise ValueError('Source size changed')
    out=root/'artifacts/runs/external_cohort'/uuid.uuid4().hex;out.mkdir(parents=True)
    c=duckdb.connect(str(out/'cohort.db'));c.execute("SET memory_limit='2GB'");c.execute('SET threads=2')
    c.read_csv(str(source),header=False,sep='|',columns={f'c{i}':'VARCHAR' for i in range(113)},quotechar='',escapechar='',parallel=False).create_view('raw')
    print('Bulk scanning 113-column source; retaining event fields and snapshot-only predictors',flush=True)
    feature_positions={'borrower_fico':23,'ltv':19,'dti':22,'original_term':12,'occupancy':29,'purpose':26}
    extras=','.join(f"CASE WHEN c2='012012' THEN nullif(trim(c{pos}),'') END {name}" for name,pos in feature_positions.items())
    c.execute("CREATE TABLE panel AS SELECT c1 loan_id,c2 month_raw,CASE WHEN regexp_full_match(c2,'[0-9]{6}') THEN cast(try_strptime(c2,'%m%Y') AS DATE) END reporting_month,nullif(trim(c39),'') delinquency_status,nullif(trim(c43),'') zero_balance_code,nullif(trim(c41),'') modification_status,"+extras+" FROM raw")
    def query(sql):
        cur=c.execute(sql);return [dict(zip([x[0] for x in cur.description],r)) for r in cur.fetchall()]
    invalid=c.execute("SELECT count(*) FROM panel WHERE loan_id IS NULL OR NOT regexp_full_match(loan_id,'[0-9]{12}') OR reporting_month IS NULL").fetchone()[0]
    duplicates=c.execute('SELECT count(*) FROM (SELECT loan_id,reporting_month FROM panel GROUP BY 1,2 HAVING count(*)>1)').fetchone()[0]
    if invalid or duplicates:raise ValueError(f'Invalid keys {invalid}; duplicates {duplicates}')
    old=root/'artifacts/runs/phase2f/64d49545a270488ca411e6a731e59465/loan_outcomes.parquet'
    c.read_parquet(str(old)).create_view('original_cohort')
    overlap=c.execute('SELECT count(DISTINCT loan_id) FROM panel JOIN original_cohort USING(loan_id)').fetchone()[0]
    if overlap:raise ValueError('Reserved loans overlap original cohort')
    source_summary=query('SELECT count(*) records,count(DISTINCT loan_id) loans,min(reporting_month) first_month,max(reporting_month) last_month FROM panel')[0]
    print('Checking pre-snapshot eligibility and freezing features before future outcomes',flush=True)
    c.execute("CREATE VIEW presnapshot AS SELECT * FROM panel WHERE reporting_month<=DATE '2012-01-01'")
    c.execute('CREATE TABLE past_events AS '+event_rows_sql().replace('FROM panel','FROM presnapshot'))
    c.execute('CREATE TABLE past_outcomes AS '+loan_outcomes_sql().replace('FROM event_rows','FROM past_events'))
    c.execute("CREATE VIEW training AS SELECT p.loan_id,p.reporting_month,try_cast(p.delinquency_status AS INTEGER) delinquency_months,p.modification_status FROM presnapshot p JOIN past_outcomes o USING(loan_id) WHERE p.reporting_month=DATE '2012-01-01' AND o.at_risk_at_entry AND o.first_stop IS NULL AND try_cast(p.delinquency_status AS INTEGER) BETWEEN 0 AND 2")
    c.execute("CREATE VIEW factors AS SELECT loan_id,month_raw reporting_month_raw,borrower_fico,ltv,dti,original_term,occupancy,purpose FROM panel WHERE reporting_month=DATE '2012-01-01'")
    # Reuse identical normalization, but do not assign a development role to external data.
    c.execute('CREATE TABLE expanded AS SELECT * EXCLUDE(development_split) FROM ('+feature_sql()+')')
    snapshots=c.execute("SELECT count(*) FROM panel WHERE reporting_month=DATE '2012-01-01'").fetchone()[0]
    count=c.execute('SELECT count(*) FROM expanded').fetchone()[0]
    if not count or count!=c.execute('SELECT count(*) FROM training').fetchone()[0]:raise ValueError('Feature join mismatch')
    quality={name:query(f'SELECT {name}_quality quality,count(*) records FROM expanded GROUP BY 1') for name in feature_positions}
    if any(x['quality']=='invalid' for rows in quality.values() for x in rows):raise ValueError('Invalid predictor values require review before outcomes')
    path=out/'features.parquet';c.execute('COPY expanded TO ? (FORMAT PARQUET)',[str(path)])
    feature_receipt={'feature_sha256':fingerprint(path),'records':count,'snapshot_records':snapshots,'excluded_snapshot_records':snapshots-count,'quality':quality,'overlap_with_original_cohort':overlap,'protocol_sha256':fingerprint(root/'configs/external_evaluation.json')}
    (out/'feature_freeze.json').write_text(json.dumps(feature_receipt,indent=2)+'\n')
    print('Features frozen; constructing outcomes with the established competing-event contract',flush=True)
    c.execute('CREATE TABLE event_rows AS '+event_rows_sql())
    c.execute('CREATE TABLE outcomes AS '+loan_outcomes_sql())
    c.execute('CREATE TABLE labels AS '+label_sql())
    if c.execute('SELECT count(*) FROM labels').fetchone()[0]!=count:raise ValueError('Label count mismatch')
    c.execute('COPY labels TO ? (FORMAT PARQUET)',[str(out/'labels.parquet')])
    if (source.stat().st_size,source.stat().st_mtime_ns)!=(before.st_size,before.st_mtime_ns):raise ValueError('Source changed during processing')
    result={'status':'pass_for_reserved_cohort_adapter','source':receipt,'source_summary':source_summary,'duplicates':duplicates,'invalid_keys':invalid,'feature_freeze':feature_receipt,'outcomes':query('SELECT outcome_12m,count(*) records FROM labels GROUP BY 1'),'implementation_sha256':fingerprint(__file__),'elapsed_seconds':time.perf_counter()-start,'limitations':['File cohort identity derives from user download and filename, not a vendor-signed acquisition manifest.','113-column schema matches inspected glossary positions; full balance audit is outside this predictor/event adapter.','Current release may contain revisions unavailable at historical prediction time.','No fitting, recalibration or promotion.']}
    c.close();(out/'cohort_result.json').write_text(json.dumps(result,indent=2,default=str)+'\n');print(out,flush=True)
    return result

if __name__=='__main__':run(Path(__file__).resolve().parents[2])
