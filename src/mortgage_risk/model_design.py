"""Phase4A: fixed disjoint temporal landmark datasets; no model fitting."""
import json,hashlib,time,uuid
from pathlib import Path
import duckdb

FEATURES=['delinquency_months','loan_age_months','original_balance','eligible_reported_balance','modification_status']


def snapshot_sql():
    return """WITH snapshots AS (
      SELECT p.loan_id,p.reporting_month,s.split,
      try_cast(p.delinquency_status AS INTEGER) delinquency_months,
      CASE WHEN p.loan_age>=0 THEN p.loan_age END loan_age_months,
      CASE WHEN p.original_upb>0 THEN p.original_upb END original_balance,
      p.usable_reported_exposure eligible_reported_balance,p.reported_modification_status modification_status,
      o.first_stop,o.stop_month,o.stop_observed_month,o.last_month,
      p.reporting_month+INTERVAL '12 months' horizon_month
      FROM panel p JOIN splits s ON p.reporting_month=s.snapshot_date
      JOIN outcomes o USING(loan_id)
      WHERE contains(s.hash_prefixes,substr(md5(p.loan_id),1,1))
        AND o.at_risk_at_entry
        AND (o.stop_observed_month IS NULL OR o.stop_observed_month>p.reporting_month)
        AND try_cast(p.delinquency_status AS INTEGER) BETWEEN 0 AND 2
    ) SELECT *,CASE
      WHEN stop_month<=horizon_month AND first_stop IN ('default_proxy','payoff_or_maturity') THEN first_stop
      WHEN stop_month<horizon_month AND first_stop IS NOT NULL THEN 'censored_or_unresolved'
      WHEN stop_month=horizon_month AND first_stop!='gap_censor' THEN 'censored_or_unresolved'
      WHEN last_month>=horizon_month THEN 'observed_event_free_12m'
      ELSE 'incomplete_followup' END outcome_12m
      FROM snapshots"""


def validate_splits(rows):
    seen=set();previous_horizon=None
    from datetime import date
    if [r['split'] for r in rows]!=['train','validation','test']:raise ValueError('Expected ordered train/validation/test splits')
    for r in rows:
        dt=date.fromisoformat(r['snapshot_date']);prefixes=set(r['hash_prefixes'])
        if not prefixes or len(prefixes)!=len(r['hash_prefixes']) or not prefixes<=set('0123456789abcdef') or prefixes&seen:raise ValueError('Hash groups overlap or are invalid')
        if previous_horizon and dt<=previous_horizon:raise ValueError('Label horizon overlaps next split')
        previous_horizon=dt.replace(year=dt.year+1);seen|=prefixes
    if seen!=set('0123456789abcdef'):raise ValueError('Hash groups must cover population')


def run(root,config):
    root=Path(root).resolve();cfg=json.loads(Path(config).read_text());validate_splits(cfg['splits']);start=time.perf_counter()
    eligibility=root/cfg['eligibility_run'];events=root/cfg['event_run']
    if json.loads((eligibility/'eligibility_result.json').read_text())['engineering_status']!='pass' or json.loads((events/'descriptive_result.json').read_text())['status']!='pass':raise ValueError('Unaccepted inputs')
    out=root/'artifacts/runs/phase4a'/uuid.uuid4().hex;out.mkdir(parents=True)
    c=duckdb.connect(str(out/'design.db'));c.execute("SET memory_limit='1GB'");c.execute('SET threads=2')
    def lit(p):return str(p).replace("'","''")
    def query(q):
        cur=c.execute(q);names=[x[0] for x in cur.description];return [dict(zip(names,row)) for row in cur.fetchall()]
    c.execute(f"CREATE VIEW panel AS SELECT * FROM read_parquet('{lit(eligibility/'exposure_eligibility.parquet')}')")
    c.execute(f"CREATE VIEW outcomes AS SELECT * FROM read_parquet('{lit(events/'loan_outcomes.parquet')}')")
    if c.execute('SELECT count(*)-count(distinct loan_id) FROM outcomes').fetchone()[0]:raise ValueError('Duplicate outcome keys')
    c.execute('CREATE TABLE splits(split VARCHAR,snapshot_date DATE,hash_prefixes VARCHAR)')
    c.executemany('INSERT INTO splits VALUES (?,?,?)',[(r['split'],r['snapshot_date'],r['hash_prefixes']) for r in cfg['splits']])
    print('Creating disjoint landmark features and separate retrospective labels',flush=True)
    c.execute('CREATE TABLE design AS '+snapshot_sql())
    if c.execute('SELECT count(*)-count(distinct loan_id) FROM design').fetchone()[0]:raise ValueError('Loan overlap or duplicate snapshot')
    summary=query('SELECT split,outcome_12m,count(*) loans FROM design GROUP BY 1,2 ORDER BY 1,2')
    inventory=query("SELECT s.split,count(*) snapshot_records,count(*) FILTER(WHERE contains(s.hash_prefixes,substr(md5(p.loan_id),1,1))) assigned_hash_group FROM panel p JOIN splits s ON p.reporting_month=s.snapshot_date GROUP BY 1 ORDER BY 1")
    if {x['split'] for x in summary}!={'train','validation','test'}:raise ValueError('Empty split')
    missing=query('SELECT split,'+','.join(f'count(*) FILTER(WHERE {f} IS NULL) missing_{f}' for f in FEATURES)+' FROM design GROUP BY 1 ORDER BY 1')
    for split in ('train','validation','test'):
        c.execute(f"COPY (SELECT loan_id,reporting_month,{','.join(FEATURES)} FROM design WHERE split='{split}') TO '{lit(out/(split+'_features.parquet'))}' (FORMAT PARQUET)")
        c.execute(f"COPY (SELECT loan_id,reporting_month,horizon_month,outcome_12m FROM design WHERE split='{split}') TO '{lit(out/(split+'_labels.parquet'))}' (FORMAT PARQUET)")
    selected=sum(x['loans'] for x in summary)
    result=dict(phase='4A',status='pass',config=cfg,feature_allowlist=FEATURES,split_outcomes=summary,snapshot_inventory=inventory,
      selected_loans=selected,missing_features=missing,loan_overlap=0,
      implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),config_sha256=hashlib.sha256(Path(config).read_bytes()).hexdigest(),
      elapsed_seconds=round(time.perf_counter()-start,3),output_directory=str(out),
      limitations=['One acquisition cohort: seasoning and calendar period are confounded; no cross-vintage generalization claim.',
      'Current release may include historical revisions; as-of field selection is not point-in-time source certification.',
      'Censored/unknown labels retained: do not turn them into non-defaults or silently fit complete cases.',
      'No model, preprocessing, imputation or threshold was fitted. Fit preprocessing on training only; choose models on validation only; reserve test for final evaluation.',
      'FICO, LTV, DTI and maturity are not retained predictors. Exposure and payoff/maturity limitations remain.'])
    c.close();(out/'design_result.json').write_text(json.dumps(result,indent=2,default=str))
    lines=['# Phase 4A feature and evaluation design','', 'Five current-observation features; disjoint loans and non-overlapping 12-month label windows. No model fitted.','','| Split | Outcome | Loans |','|---|---|---:|']
    lines += [f"| {x['split']} | {x['outcome_12m']} | {x['loans']:,} |" for x in summary]
    lines += ['','## Limitations','']+['- '+x for x in result['limitations']]
    (out/'design_report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':'pass','result':str(out/'design_result.json')}),flush=True)
    return result

if __name__=='__main__':
    run(Path(__file__).resolve().parents[2],'configs/model_design.json')
