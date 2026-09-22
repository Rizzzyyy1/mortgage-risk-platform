"""Read-only persisted-output acceptance; no raw CSV re-ingestion."""
import json, time, uuid, hashlib
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import duckdb
from mortgage_risk.vendor_codes import code_issue
from mortgage_risk.monthly_summary import build_monthly_portfolio_summary

def main():
 root=Path(__file__).resolve().parents[2]
 run=root/'artifacts/runs/historical_ingest/fullquarter_replacement/7a30ef59b2e74c518133ddf5923c92c9'
 audit_path=root/'artifacts/runs/full_quarter_checks/d3507c50840346418b9c6f0d1d4dfc5b/full_quarter_raw_audit.json'
 out=root/'artifacts/runs/phase2d_acceptance'/uuid.uuid4().hex;out.mkdir(parents=True)
 start=time.perf_counter(); meta=json.loads((run/'historical_ingest_result.json').read_text());audit=json.loads(audit_path.read_text())
 c=duckdb.connect(str(run/'historical_monthly.db'),read_only=True);c.execute("SET memory_limit='2GB'");c.execute('SET threads=2')
 def rows(q,args=None):
  z=c.execute(q,args or []); names=[d[0] for d in z.description];return [dict(zip(names,r)) for r in z.fetchall()]
 print('Checking persisted counts, dates and keys',flush=True)
 counts=rows("SELECT count(*) records,count(distinct loan_id) loans,count(distinct reporting_month) AS month_count,min(reporting_month) first_month,max(reporting_month) last_month,count(*) FILTER(WHERE loan_id IS NULL OR trim(loan_id)='') missing_ids,count(*) FILTER(WHERE reporting_month IS NULL) missing_dates FROM historical_monthly")[0]
 dup=c.execute('select count(*) from (select loan_id,reporting_month from historical_monthly group by 1,2 having count(*)>1)').fetchone()[0]
 errors={}
 for field in ['current_actual_upb','original_upb']:
  errors[field]=rows(f"SELECT count(*) FILTER(WHERE nullif(trim({field}_raw),'') IS NOT NULL AND (try_cast({field}_raw AS DECIMAL(38,10)) IS NULL OR NOT isfinite(try_cast({field}_raw AS DOUBLE)))) conversion_errors,count(*) FILTER(WHERE try_cast(nullif(trim({field}_raw),'') AS DECIMAL(38,10)) IS DISTINCT FROM cast({field} AS DECIMAL(38,10))) raw_typed_differences FROM historical_monthly")[0]
 errors['dates']=c.execute("select count(*) from historical_monthly where NOT regexp_full_match(reporting_month_text,'[0-9]{6}') OR try_strptime(reporting_month_text,'%m%Y') IS NULL OR cast(try_strptime(reporting_month_text,'%m%Y') AS DATE) IS DISTINCT FROM reporting_month").fetchone()[0]
 query="SELECT reporting_month,count(*) n,sum(current_actual_upb) balance,count(*) FILTER(WHERE current_actual_upb IS NULL) missing FROM {} GROUP BY 1 ORDER BY 1"
 dbmonths=rows(query.format('historical_monthly'))
 par=str(run/'historical_monthly.parquet').replace("'","''")
 pqmonths=rows(query.format(f"read_parquet('{par}')"))
 schema_db=c.execute('describe historical_monthly').fetchall();schema_pq=c.execute(f"describe select * from read_parquet('{par}')").fetchall()
 schema_match=[r[:2] for r in schema_db]==[r[:2] for r in schema_pq]
 rawdiff=[]
 for r in dbmonths:
  k=r['reporting_month'].strftime('%m%Y')
  if r['n']!=audit['per_month_record_counts'].get(k) or (r['balance'] or Decimal(0))!=Decimal(audit['monthly_balance_totals'].get(k,'NaN')):rawdiff.append(r)
 print('Checking vendor domains and conditional missingness',flush=True)
 codes={};unsupported=0
 for field in ['delinquency_status','modification_flag','zero_balance_code']:
  vals=rows(f"select {field} AS code_value,count(*) records from historical_monthly group by 1 order by 1")
  for v in vals:
   v['issue']=code_issue(field,v['code_value']);unsupported+=v['records'] if v['issue'] else 0
   if not v['code_value']: v['classification']='missing_separately_assessed'
  codes[field]=vals
 blank_delinquency=c.execute("WITH x AS (select *,min(reporting_month) FILTER(WHERE nullif(trim(zero_balance_code),'') IS NOT NULL) OVER(PARTITION BY loan_id) removal_month from historical_monthly) select count(*) FILTER(WHERE nullif(trim(delinquency_status),'') IS NULL), count(*) FILTER(WHERE nullif(trim(delinquency_status),'') IS NULL AND reporting_month>removal_month),count(*) FILTER(WHERE nullif(trim(delinquency_status),'') IS NULL AND (removal_month IS NULL OR reporting_month<=removal_month)) FROM x").fetchone()
 blank_mod=c.execute("select count(*) from historical_monthly where nullif(trim(modification_flag),'') is null").fetchone()[0]
 c.close()
 print('Generating bounded full-quarter summaries and diagnostic Parquet',flush=True)
 summary=build_monthly_portfolio_summary(run/'historical_monthly.db',output_dir=out)
 categorydiff=[]
 for m in summary['monthly_summary']:
  for typ in ['delinquency','modification','termination']:
   cats=[r for r in summary['category_detail'] if r['reporting_month']==m['reporting_month'] and r['category_type']==typ]
   if sum(r['category_count'] for r in cats)!=m['observed_loan_count'] or sum((Decimal(r['category_balance_total']) for r in cats),Decimal(0))!=Decimal(m['total_known_current_balance']):categorydiff.append((m['reporting_month'],typ))
 engineering=(counts['records']==20983277 and counts['loans']==323174 and counts['month_count']==195 and not dup and not counts['missing_ids'] and not counts['missing_dates'] and not errors['dates'] and all(not v['conversion_errors'] and not v['raw_typed_differences'] for k,v in errors.items() if k!='dates') and schema_match and dbmonths==pqmonths and not rawdiff and len(dbmonths)==len(audit['per_month_record_counts']) and not categorydiff and summary['overall_status']=='pass')
 result=dict(input_run_id=run.name,input_metadata=str(run/'historical_ingest_result.json'),raw_audit_path=str(audit_path),raw_audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),raw_audit_limitation='Prior raw audit lacks embedded input checksum; source linkage is inherited from project records, not independently rehashed. Conversion checks here cover all retained raw balance strings; no CSV rescan.',counts=counts,duplicate_keys=dup,conversion_checks=errors,db_parquet_schema_match=schema_match,db_parquet_monthly_match=dbmonths==pqmonths,raw_monthly_differences=rawdiff,category_differences=categorydiff,vendor_codes=codes,unsupported_code_records=unsupported,blank_delinquency=dict(zip(['total','documented_post_removal','unresolved'],blank_delinquency)),blank_modification=blank_mod,vendor_reference='crt-file-layout-and-glossary.pdf, 2026-09-10, PDF page 4, fields 40/42/44; 97/98 CAS-only, not accepted for SF historical.',summary_path=str(Path(summary['output_directory'])/'monthly_portfolio_summary.json'),diagnostic_counts=summary['diagnostic_counts'],bridge_pairs=len(summary['balance_bridge']),bridge_failures=len(summary['bridge_failures']),bridge_max_abs_residual=summary['bridge_max_abs_residual'],tolerance=summary['reconciliation_tolerance'],engineering_status='pass' if engineering else 'failed',vendor_code_status='pass' if unsupported==0 and blank_delinquency[2]==0 and blank_mod==0 else 'needs_review',economic_exposure_status='not_ready',elapsed_seconds=round(time.perf_counter()-start,3),timestamp_utc=datetime.now(timezone.utc).isoformat())
 (out/'acceptance_result.json').write_text(json.dumps(result,indent=2,default=str))
 print(json.dumps({'result':str(out/'acceptance_result.json'),'engineering':result['engineering_status'],'codes':result['vendor_code_status'],'seconds':result['elapsed_seconds']}),flush=True)
if __name__=='__main__': main()
