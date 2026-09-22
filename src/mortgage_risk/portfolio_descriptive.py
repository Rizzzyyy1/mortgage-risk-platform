"""Phase 2F: descriptive cohort outputs, not fitted probabilities or loss estimates."""
import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
import duckdb


def event_rows_sql():
    return """
    WITH ordered AS (
      SELECT loan_id,reporting_month,delinquency_status,zero_balance_code,
        lag(reporting_month) OVER (PARTITION BY loan_id ORDER BY reporting_month) previous_month
      FROM panel
    ), classified AS (
      SELECT *, CASE
        WHEN date_diff('month',previous_month,reporting_month)>1 THEN 'gap_censor'
        WHEN zero_balance_code IN ('01','06','16','96') AND try_cast(delinquency_status AS INTEGER)>=3 THEN 'ambiguous_same_month'
        WHEN zero_balance_code IN ('02','03','09','15') THEN 'default_proxy'
        WHEN nullif(trim(zero_balance_code),'') IS NOT NULL AND zero_balance_code NOT IN ('01','02','03','06','09','15','16','96') THEN 'unsupported_code'
        WHEN try_cast(delinquency_status AS INTEGER) BETWEEN 3 AND 99 THEN 'default_proxy'
        WHEN zero_balance_code='01' THEN 'payoff_or_maturity'
        WHEN zero_balance_code IN ('06','16','96') THEN 'other_exit'
        WHEN delinquency_status IS NULL OR NOT regexp_full_match(delinquency_status,'[0-9]{2}') THEN 'unknown_status'
        ELSE NULL END AS candidate_event
      FROM ordered
    ) SELECT *, CASE WHEN candidate_event='gap_censor' THEN previous_month ELSE reporting_month END AS candidate_time
      FROM classified
    """


def loan_outcomes_sql():
    return """
    WITH aggregates AS (
      SELECT loan_id,min(reporting_month) entry_month,max(reporting_month) last_month,count(*) observed_months,
        arg_min(struct_pack(value:=delinquency_status),reporting_month).value entry_delinquency,
        arg_min(struct_pack(kind:=candidate_event,dt:=candidate_time,observed:=reporting_month),reporting_month)
          FILTER(WHERE candidate_event IS NOT NULL) stop
      FROM event_rows GROUP BY 1
    ), labels AS (
      SELECT *, stop.kind AS first_stop,stop.dt AS stop_month,stop.observed AS stop_observed_month,
        entry_month+INTERVAL '12 months' AS horizon_month,
        CASE WHEN stop.observed=entry_month THEN false
          WHEN try_cast(entry_delinquency AS INTEGER) BETWEEN 0 AND 2 THEN true ELSE false END AS at_risk_at_entry
      FROM aggregates
    ) SELECT * EXCLUDE(stop),
      CASE WHEN NOT at_risk_at_entry THEN 'ineligible_at_entry'
        WHEN stop_month<=horizon_month AND first_stop IN ('default_proxy','payoff_or_maturity') THEN first_stop
        WHEN stop_month<horizon_month AND first_stop IS NOT NULL THEN 'censored_or_unresolved'
        WHEN stop_month=horizon_month AND first_stop NOT IN ('gap_censor') THEN 'censored_or_unresolved'
        WHEN last_month>=horizon_month THEN 'observed_event_free_12m'
        ELSE 'incomplete_followup' END AS outcome_12m
      FROM labels
    """


def run(root):
    root=Path(root).resolve();start=time.perf_counter()
    inp=root/'artifacts/runs/exposure_eligibility/7b7177c3473345d091dd1cd19d24799e'
    prior=json.loads((inp/'eligibility_result.json').read_text())
    if prior['engineering_status']!='pass':raise ValueError('Input eligibility not accepted')
    out=root/'artifacts/runs/phase2f'/uuid.uuid4().hex;out.mkdir(parents=True)
    c=duckdb.connect(str(out/'descriptive.db'));c.execute("SET memory_limit='2GB'");c.execute('SET threads=2')
    def lit(p):return str(p).replace("'","''")
    def query(q):
        cur=c.execute(q);names=[x[0] for x in cur.description];return [dict(zip(names,r)) for r in cur.fetchall()]
    c.execute(f"CREATE VIEW panel AS SELECT * FROM read_parquet('{lit(inp/'exposure_eligibility.parquet')}')")
    print('Building monthly profiles and explicit exclusion categories',flush=True)
    c.execute('''CREATE TABLE monthly AS SELECT reporting_month,count(*) records,count(distinct loan_id) loans,
      count(current_actual_upb) known_balance_records,sum(current_actual_upb) reported_balance,
      count(*) FILTER(WHERE exposure_eligible) eligible_records,sum(usable_reported_exposure) usable_reported_exposure,
      count(*) FILTER(WHERE try_cast(delinquency_status AS INTEGER)>=3) observed_90plus_records
      FROM panel GROUP BY 1 ORDER BY 1''')
    parts=[]
    for dimension,column in [('eligibility','exposure_eligibility_reason'),('delinquency','delinquency_status'),('modification','reported_modification_status'),('exit_code','zero_balance_code')]:
        parts.append(f"SELECT reporting_month,'{dimension}' dimension,coalesce(nullif(trim({column}),''),'not_reported') category,count(*) records,count(current_actual_upb) known_balance_records,coalesce(sum(current_actual_upb),0) reported_balance,coalesce(sum(usable_reported_exposure),0) usable_reported_exposure FROM panel GROUP BY 1,2,3")
    c.execute('CREATE TABLE categories AS '+' UNION ALL '.join(parts))
    print('Building observed event candidates and one first-stop outcome per loan',flush=True)
    c.execute(f"COPY ({event_rows_sql()}) TO '{lit(out/'event_rows.parquet')}' (FORMAT PARQUET)")
    c.execute(f"CREATE VIEW event_rows AS SELECT * FROM read_parquet('{lit(out/'event_rows.parquet')}')")
    c.execute('CREATE TABLE loan_outcomes AS '+loan_outcomes_sql())
    c.execute('''CREATE TABLE monthly_first_stops AS SELECT stop_month,first_stop,count(*) loans,
      count(*) FILTER(WHERE NOT at_risk_at_entry) prevalent_or_unresolved_at_entry
      FROM loan_outcomes WHERE first_stop IS NOT NULL GROUP BY 1,2 ORDER BY 1,2''')
    print('Reconciling categories, input totals, and loan outcomes',flush=True)
    differences=query('''SELECT a.reporting_month,a.dimension FROM
      (SELECT reporting_month,dimension,sum(records) n,sum(known_balance_records) k,sum(reported_balance) b,sum(usable_reported_exposure) e FROM categories GROUP BY 1,2) a
      JOIN monthly m USING(reporting_month)
      WHERE a.n!=m.records OR a.k!=m.known_balance_records OR a.b IS DISTINCT FROM coalesce(m.reported_balance,0) OR a.e IS DISTINCT FROM coalesce(m.usable_reported_exposure,0)''')
    accepted=root/'artifacts/runs/historical_ingest/fullquarter_replacement/7a30ef59b2e74c518133ddf5923c92c9/historical_monthly.parquet'
    c.execute(f"CREATE VIEW accepted AS SELECT * FROM read_parquet('{lit(accepted)}')")
    input_differences=query('''WITH a AS(SELECT reporting_month,count(*) n,count(current_actual_upb) k,coalesce(sum(current_actual_upb),0) b FROM accepted GROUP BY 1)
      SELECT reporting_month FROM a FULL JOIN monthly m USING(reporting_month)
      WHERE a.n IS DISTINCT FROM m.records OR a.k IS DISTINCT FROM m.known_balance_records OR a.b IS DISTINCT FROM coalesce(m.reported_balance,0)''')
    counts=query('SELECT count(*) records,count(distinct loan_id) loans,count(distinct reporting_month) AS "months" FROM panel')[0]
    outcomes=query('SELECT outcome_12m,count(*) loans FROM loan_outcomes GROUP BY 1 ORDER BY 1')
    stops=query("SELECT coalesce(first_stop,'observation_end') first_stop,count(*) loans FROM loan_outcomes GROUP BY 1 ORDER BY 1")
    eligibility=query("SELECT category,sum(records) records FROM categories WHERE dimension='eligibility' GROUP BY 1 ORDER BY 1")
    expected={x['exposure_eligibility_reason']:x['records'] for x in prior['eligibility_counts']}
    eligibility_match={x['category']:x['records'] for x in eligibility}==expected
    for table in ('monthly','categories','loan_outcomes','monthly_first_stops'):
        c.execute(f"COPY {table} TO '{lit(out/(table+'.parquet'))}' (FORMAT PARQUET)")
    result=dict(phase='2F',input_run=str(inp),source_checksum_inherited=prior['source_checksum_sha256_inherited'],counts=counts,
      category_reconciliation_differences=differences,input_monthly_differences=input_differences,eligibility_counts_match=eligibility_match,
      first_stops=stops,outcomes_12m=outcomes,monthly=query('SELECT * FROM monthly ORDER BY 1'),
      event_candidate_counts=query("SELECT candidate_event,count(*) records FROM event_rows WHERE candidate_event IS NOT NULL GROUP BY 1 ORDER BY 1"),
      status='pass' if not differences and not input_differences and eligibility_match and counts['records']==prior['output_records'] and sum(x['loans'] for x in outcomes)==counts['loans'] else 'failed',
      elapsed_seconds=round(time.perf_counter()-start,3),timestamp_utc=datetime.now(timezone.utc).isoformat(),output_directory=str(out),
      limitations=['90+ delinquency or codes02/03/09/15 is a project default proxy, not a vendor/regulatory default standard.',
      'Code01 combines payoff and maturity; true prepayment is not separately validated.',
      '12-month labels start at each first observation and are retrospective outcomes, not prediction features or probabilities.',
      'Unknown states, ambiguous same-month events, gaps and other exits censor; no re-entry after first stop.',
      'Current vendor release may contain revisions unavailable historically; no point-in-time vintage claim.',
      'Reported exposure eligibility limitations from Phase2E remain.'])
    c.close();(out/'descriptive_result.json').write_text(json.dumps(result,indent=2,default=str))
    print(json.dumps({'status':result['status'],'result':str(out/'descriptive_result.json'),'seconds':result['elapsed_seconds']}),flush=True)
    return result

if __name__=='__main__':
    run(Path(__file__).resolve().parents[2])
