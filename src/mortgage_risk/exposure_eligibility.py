"""Conservative observed-exposure eligibility; glossary 2026-09-10 pp1,4."""
from pathlib import Path
from datetime import datetime, timezone
import json
import time
import uuid
import duckdb


def month_date_sql(field):
    return f"CASE WHEN regexp_full_match({field},'[0-9]{{6}}') THEN cast(try_strptime({field},'%m%Y') AS DATE) END"


def eligibility_sql(table='joined'):
    # Identifiers are internal, never arbitrary command-line inputs.
    if table != 'joined':
        raise ValueError('Expected internal joined table')
    return """
    WITH history AS (
      SELECT *,
        max(CASE WHEN zero_balance_code IN ('01','02','03','06','09','15','16','96') THEN reporting_month END)
          OVER (PARTITION BY loan_id ORDER BY reporting_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS last_observed_terminal_month,
        last_value(CASE WHEN modification_flag IN ('Y','N') THEN modification_flag END IGNORE NULLS)
          OVER (PARTITION BY loan_id ORDER BY reporting_month ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS previously_observed_modification_status
      FROM joined
    ), states AS (
      SELECT *,
       CASE WHEN loan_age IS NULL OR loan_age<0 OR origination_date IS NULL OR first_payment_date IS NULL
          OR origination_date>reporting_month
          OR first_payment_date<origination_date
          OR abs(date_diff('month',origination_date,reporting_month)-loan_age)>1
          THEN 'unresolved'
        WHEN loan_age IN (0,6) THEN 'unresolved'
        WHEN loan_age BETWEEN 1 AND 5 THEN 'masked'
        WHEN loan_age>=7 THEN 'unmasked'
        ELSE 'unresolved' END AS masking_status,
       CASE WHEN nullif(trim(zero_balance_code),'') IS NOT NULL AND zero_balance_code NOT IN ('01','02','03','06','09','15','16','96') THEN 'unresolved'
        WHEN nullif(trim(zero_balance_effective_date_raw),'') IS NOT NULL AND zero_balance_effective_date IS NULL THEN 'unresolved'
        WHEN zero_balance_effective_date>reporting_month THEN 'unresolved'
        WHEN last_observed_terminal_month IS NOT NULL THEN 'terminal'
        WHEN zero_balance_effective_date<=reporting_month THEN 'unresolved'
        ELSE 'not_observed_terminal' END AS terminal_record_status,
       CASE WHEN modification_flag IN ('Y','N') THEN modification_flag ELSE 'unknown_not_reported' END AS reported_modification_status
      FROM history
    ), reasons AS (
      SELECT *, CASE
       WHEN terminal_record_status='terminal' THEN 'terminal_record'
       WHEN terminal_record_status='unresolved' THEN 'terminal_status_unresolved'
       WHEN masking_status='masked' THEN 'masked_early_life'
       WHEN masking_status='unresolved' THEN 'masking_or_age_unresolved'
       WHEN current_actual_upb IS NULL THEN 'missing_reported_balance'
       WHEN current_actual_upb<0 THEN 'negative_reported_balance'
       WHEN current_actual_upb=0 THEN 'unmasked_zero_unexplained'
       ELSE 'eligible_positive_reported_balance' END AS exposure_eligibility_reason
      FROM states
    )
    SELECT *, exposure_eligibility_reason='eligible_positive_reported_balance' AS exposure_eligible,
      CASE WHEN exposure_eligibility_reason='eligible_positive_reported_balance' THEN current_actual_upb END AS usable_reported_exposure
    FROM reasons
    """


def assert_join_keys(conn):
    results={}
    for name in ('base','supplement'):
        results[name+'_duplicates']=conn.execute(f'SELECT count(*) FROM (SELECT loan_id,reporting_month,count(*) n FROM {name} GROUP BY 1,2 HAVING n>1)').fetchone()[0]
        results[name+'_missing_keys']=conn.execute(f"SELECT count(*) FROM {name} WHERE loan_id IS NULL OR trim(loan_id)='' OR reporting_month IS NULL").fetchone()[0]
    results['base_unmatched']=conn.execute('SELECT count(*) FROM base b ANTI JOIN supplement s USING(loan_id,reporting_month,source_record_number)').fetchone()[0]
    results['supplement_unmatched']=conn.execute('SELECT count(*) FROM supplement s ANTI JOIN base b USING(loan_id,reporting_month,source_record_number)').fetchone()[0]
    if any(results.values()): raise ValueError(f'Unsafe supplemental join: {results}')
    return results


def run(root, output=None, supplement=None):
    root=Path(root).resolve();start=time.perf_counter()
    source=root/'data/raw/fannie_mae_loan_performance/2010Q1.csv'
    base_dir=root/'artifacts/runs/historical_ingest/fullquarter_replacement/7a30ef59b2e74c518133ddf5923c92c9'
    meta=json.loads((base_dir/'historical_ingest_result.json').read_text())
    out=Path(output) if output else root/'artifacts/runs/exposure_eligibility'/uuid.uuid4().hex
    out.mkdir(parents=True,exist_ok=False)
    c=duckdb.connect(str(out/'eligibility.db'));c.execute("SET memory_limit='2GB'");c.execute('SET threads=2');c.execute("SET preserve_insertion_order=true")
    def query(q,args=None):
        r=c.execute(q,args or []);names=[x[0] for x in r.description];return [dict(zip(names,x)) for x in r.fetchall()]
    def escaped(p):return str(p).replace("'","''")
    c.execute(f"CREATE VIEW base AS SELECT * FROM read_parquet('{escaped(base_dir/'historical_monthly.parquet')}')")
    before=source.stat();scan_seconds=0
    if supplement is None:
        print('Streaming one supplemental CSV scan: dates and loan age only',flush=True)
        scan=time.perf_counter();supplement=out/'supplement.parquet'
        cols='{'+','.join(f"'c{i}':'VARCHAR'" for i in range(113))+'}'
        # Serial scan + insertion order preserves record ordinals. Phase 2D found no blank records;
        # exact join checks below reject any ordinal mismatch rather than accepting a shifted join.
        c.execute('SET threads=1')
        sql=f"""SELECT row_number() OVER ()::BIGINT source_record_number,
         c1 loan_id,c2 reporting_period_raw,{month_date_sql('c2')} reporting_month,
         c13 origination_date_raw,{month_date_sql('c13')} origination_date,
         c14 first_payment_date_raw,{month_date_sql('c14')} first_payment_date,
         c15 loan_age_raw,CASE WHEN regexp_full_match(c15,'-?[0-9]+') THEN try_cast(c15 AS INTEGER) END loan_age,
         c44 zero_balance_effective_date_raw,{month_date_sql('c44')} zero_balance_effective_date
         FROM read_csv('{escaped(source)}',header=false,delim='|',columns={cols},parallel=false,strict_mode=true,ignore_errors=false)"""
        c.execute(f"COPY ({sql}) TO '{escaped(supplement)}' (FORMAT PARQUET)")
        c.execute('SET threads=2');scan_seconds=time.perf_counter()-scan
        after=source.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Source changed during supplemental scan')
    supplement=Path(supplement).resolve()
    input_supplement=supplement
    projections=["CASE WHEN regexp_full_match(loan_age_raw,'-?[0-9]+') THEN try_cast(loan_age_raw AS INTEGER) END AS loan_age"]
    for raw,parsed in [('reporting_period_raw','reporting_month'),('origination_date_raw','origination_date'),('first_payment_date_raw','first_payment_date'),('zero_balance_effective_date_raw','zero_balance_effective_date')]:
        projections.append(f"{month_date_sql(raw)} AS {parsed}")
    supplement=out/'supplement_validated.parquet'
    c.execute(f"COPY (SELECT * EXCLUDE(reporting_month,origination_date,first_payment_date,zero_balance_effective_date,loan_age), {','.join(projections)} FROM read_parquet('{escaped(input_supplement)}')) TO '{escaped(supplement)}' (FORMAT PARQUET)")
    c.execute(f"CREATE VIEW supplement AS SELECT * FROM read_parquet('{escaped(supplement)}')")
    print('Checking exact supplemental keys and one-to-one join',flush=True)
    joins=assert_join_keys(c)
    c.execute('CREATE VIEW joined AS SELECT b.*,s.* EXCLUDE(loan_id,reporting_month,source_record_number) FROM base b JOIN supplement s USING(loan_id,reporting_month,source_record_number)')
    base_count=c.execute('select count(*) from base').fetchone()[0];joined_count=c.execute('select count(*) from joined').fetchone()[0]
    if base_count!=joined_count:raise ValueError('Join count changed')
    invalid_dates=query("""SELECT count(*) FILTER(WHERE origination_date_raw IS NOT NULL AND (NOT regexp_full_match(origination_date_raw,'[0-9]{6}') OR origination_date IS NULL)) invalid_origination,
      count(*) FILTER(WHERE first_payment_date_raw IS NOT NULL AND (NOT regexp_full_match(first_payment_date_raw,'[0-9]{6}') OR first_payment_date IS NULL)) invalid_first_payment,
      count(*) FILTER(WHERE zero_balance_effective_date_raw IS NOT NULL AND (NOT regexp_full_match(zero_balance_effective_date_raw,'[0-9]{6}') OR zero_balance_effective_date IS NULL)) invalid_terminal_date,
      count(*) FILTER(WHERE loan_age_raw IS NOT NULL AND loan_age IS NULL) invalid_numeric_age, count(*) FILTER(WHERE loan_age<0) negative_age_unresolved FROM supplement""")[0]
    print('Writing conservative eligibility layer and as-of modification history',flush=True)
    target=out/'exposure_eligibility.parquet'
    c.execute(f"COPY ({eligibility_sql()}) TO '{escaped(target)}' (FORMAT PARQUET)")
    c.execute(f"CREATE VIEW eligibility AS SELECT * FROM read_parquet('{escaped(target)}')")
    monthly=query('''SELECT reporting_month,exposure_eligibility_reason,count(*) records,count(current_actual_upb) known_balance_records,coalesce(sum(current_actual_upb),0) reported_balance,sum(usable_reported_exposure) usable_reported_exposure FROM eligibility GROUP BY 1,2 ORDER BY 1,2''')
    mismatches=query('''WITH a AS (SELECT reporting_month,count(*) n,coalesce(sum(current_actual_upb),0) b FROM base GROUP BY 1),z AS (SELECT reporting_month,count(*) n,coalesce(sum(current_actual_upb),0) b FROM eligibility GROUP BY 1) SELECT * FROM a FULL JOIN z USING(reporting_month) WHERE a.n IS DISTINCT FROM z.n OR a.b IS DISTINCT FROM z.b''')
    groups=query('SELECT exposure_eligibility_reason,count(*) records,count(distinct loan_id) loans FROM eligibility GROUP BY 1 ORDER BY 1')
    masking=query('SELECT masking_status,count(*) records FROM eligibility GROUP BY 1 ORDER BY 1')
    modification=query("SELECT terminal_record_status,previously_observed_modification_status,count(*) records FROM eligibility WHERE modification_flag IS NULL OR trim(modification_flag)='' GROUP BY 1,2 ORDER BY 1,2")
    age_consistency=query("SELECT date_diff('month',origination_date,reporting_month)-loan_age AS difference,count(*) records FROM supplement GROUP BY 1 ORDER BY 1")
    total=c.execute('select count(*) from eligibility').fetchone()[0]
    leakage_errors=c.execute("SELECT count(*) FROM eligibility WHERE exposure_eligible AND (masking_status!='unmasked' OR terminal_record_status!='not_observed_terminal' OR usable_reported_exposure IS DISTINCT FROM current_actual_upb OR current_actual_upb<=0)").fetchone()[0]
    result=dict(schema_version='exposure-eligibility-v1',input_run_id=base_dir.name,source_path=str(source),source_checksum_sha256_inherited=meta['source_checksum_sha256'],source_size=before.st_size,source_mtime_ns=before.st_mtime_ns,checksum_note='Inherited from accepted ingestion; source size/mtime checked during one supplemental scan, not a new content checksum.',schema_reference='Glossary 2026-09-10 PDF page1 fields2,3,12,14,15,16; page4 fields44,45',masking_policy='Conservative intersection: ages1-5 masked;0,6 unresolved;>=7 unmasked only with present/plausible dates and age/note-month difference <=1. The +/-1 check is a project plausibility tolerance, not a vendor equation. No boundary convention is claimed verified.',join_checks=joins,base_records=base_count,joined_records=joined_count,output_records=total,invalid_fields=invalid_dates,monthly_reconciliation_differences=mismatches,eligibility_invariant_errors=leakage_errors,eligibility_counts=groups,masking_counts=masking,blank_modification_history=modification,age_note_month_differences=age_consistency,monthly_summary=monthly,input_supplement_path=str(input_supplement),supplement_path=str(supplement),eligibility_path=str(target.resolve()),output_directory=str(out.resolve()),supplement_scan_seconds=round(scan_seconds,3),elapsed_seconds=round(time.perf_counter()-start,3),timestamp_utc=datetime.now(timezone.utc).isoformat(),engineering_status='pass' if total==base_count and not mismatches and not leakage_errors else 'failed',descriptive_readiness='qualified: eligible reported exposures only; show exclusions; no market representativeness or full-cohort economic balance claim')
    c.close();(out/'eligibility_result.json').write_text(json.dumps(result,indent=2,default=str))
    print(json.dumps({'result':str(out/'eligibility_result.json'),'status':result['engineering_status'],'seconds':result['elapsed_seconds']}),flush=True)
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--project',default=str(Path(__file__).resolve().parents[2]));parser.add_argument('--supplement');parser.add_argument('--output');a=parser.parse_args();run(a.project,a.output,a.supplement)
