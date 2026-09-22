"""Outcome-blind profiling of candidate factors on five explicit snapshots."""
import json
import time
import uuid
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint

FIELDS = {'channel':4,'original_rate':8,'current_rate':9,'original_term':13,
          'ltv':20,'cltv':21,'borrowers':22,'dti':23,'borrower_fico':24,
          'coborrower_fico':25,'first_time_buyer':26,'purpose':27,'property_type':28,
          'units':29,'occupancy':30,'state':31,'msa':32,'mi_percentage':34,
          'amortization':35,'payment_history':41,'origination_fico_new':111}
NUMERIC = {'original_rate','current_rate','original_term','ltv','cltv','borrowers','dti','borrower_fico','coborrower_fico','units','mi_percentage','origination_fico_new'}
CODES = {'channel':['R','C','B'],'first_time_buyer':['Y','N'],'purpose':['C','R','P','U'],
         'property_type':['CO','CP','PU','MH','SF'],'occupancy':['P','S','I','U'],'amortization':['ARM','FRM']}
SNAPSHOTS = ['012011','012013','012015','122025','032026']


def profile(conn):
    results={}
    for name in FIELDS:
        extra=''
        if name in NUMERIC:
            extra=f',count(*) FILTER(WHERE {name} IS NOT NULL AND (try_cast({name} AS DOUBLE) IS NULL OR NOT isfinite(try_cast({name} AS DOUBLE)))) conversion_failures,min(try_cast({name} AS DOUBLE)) minimum,max(try_cast({name} AS DOUBLE)) maximum'
        elif name in CODES:
            allowed=','.join("'"+x+"'" for x in CODES[name]);extra=f',count(*) FILTER(WHERE {name} IS NOT NULL AND {name} NOT IN ({allowed})) unsupported_codes'
        cur=conn.execute(f'SELECT reporting_month_raw,count(*) records,count(*) FILTER(WHERE {name} IS NULL) missing,count(DISTINCT {name}) distinct_values {extra} FROM factors GROUP BY 1 ORDER BY 1')
        results[name]=[dict(zip([x[0] for x in cur.description],row)) for row in cur.fetchall()]
    return results


def run(root):
    root=Path(root).resolve();start=time.perf_counter()
    source=root/'data/raw/fannie_mae_loan_performance/2010Q1.csv';before=source.stat()
    out=root/'artifacts/runs/risk_factor_assessment'/uuid.uuid4().hex;out.mkdir(parents=True)
    c=duckdb.connect(str(out/'assessment.db'));c.execute("SET memory_limit='1GB'");c.execute('SET threads=2')
    columns={f'c{i}':'VARCHAR' for i in range(113)}
    c.read_csv(str(source),header=False,sep='|',columns=columns,quotechar='',escapechar='',parallel=False).create_view('raw')
    selection=', '.join(f"nullif(trim(c{pos-1}),'') AS {name}" for name,pos in FIELDS.items())
    dates=','.join("'"+x+"'" for x in SNAPSHOTS)
    print('Scanning source once for five snapshots; no outcomes accessed',flush=True)
    c.execute(f"CREATE TABLE factors AS SELECT c1 loan_id,c2 reporting_month_raw,{selection} FROM raw WHERE c2 IN ({dates})")
    if source.stat().st_size!=before.st_size or source.stat().st_mtime_ns!=before.st_mtime_ns:raise ValueError('Source changed during scan')
    duplicates=c.execute('SELECT count(*)-count(DISTINCT (loan_id,reporting_month_raw)) FROM factors').fetchone()[0]
    missing=c.execute("SELECT count(*) FROM factors WHERE loan_id IS NULL OR trim(loan_id)=''").fetchone()[0]
    if duplicates or missing:raise ValueError('Unsafe snapshot keys')
    base_dir=root/'artifacts/runs/historical_ingest/fullquarter_replacement/7a30ef59b2e74c518133ddf5923c92c9'
    c.read_parquet(str(base_dir/'historical_monthly.parquet')).create_view('base_all')
    c.execute(f"CREATE VIEW selected_base AS SELECT loan_id,strftime(reporting_month,'%m%Y') reporting_month_raw FROM base_all WHERE strftime(reporting_month,'%m%Y') IN ({dates})")
    unmatched={direction:c.execute(f'SELECT count(*) FROM {a} ANTI JOIN {b} USING(loan_id,reporting_month_raw)').fetchone()[0] for direction,a,b in [('source_only','factors','selected_base'),('base_only','selected_base','factors')]}
    if any(unmatched.values()):raise ValueError('Snapshot source/base disagreement')
    profiles=profile(c)
    cur=c.execute('SELECT reporting_month_raw,count(*) FILTER(WHERE try_cast(cltv AS DOUBLE)<try_cast(ltv AS DOUBLE)) cltv_below_ltv,count(*) FILTER(WHERE try_cast(borrower_fico AS DOUBLE) NOT BETWEEN 300 AND 850) fico_plausibility_flags,count(*) FILTER(WHERE try_cast(dti AS DOUBLE) NOT BETWEEN 0 AND 100) dti_plausibility_flags FROM factors GROUP BY 1 ORDER BY 1')
    relationships=[dict(zip([x[0] for x in cur.description],row)) for row in cur.fetchall()]
    c.execute('COPY factors TO ? (FORMAT PARQUET)',[str(out/'snapshot_factors.parquet')])
    result={'status':'pass_for_snapshot_inventory','profiles':profiles,'relationships':relationships,'mapping':FIELDS,'snapshots':SNAPSHOTS,'duplicates':duplicates,'missing_keys':missing,'unmatched':unmatched,'retained_rows':c.execute('SELECT count(*) FROM factors').fetchone()[0],'source_size':before.st_size,'source_mtime_ns':before.st_mtime_ns,'accepted_ingest_metadata_sha256':fingerprint(base_dir/'historical_ingest_result.json'),'source_checksum_note':'No fresh whole-source checksum; inherited accepted-source lineage and stat stability only.','glossary_sha256':fingerprint(root/'data/raw/fannie_mae_loan_performance/crt-file-layout-and-glossary.pdf'),'implementation_sha256':fingerprint(__file__),'elapsed_seconds':time.perf_counter()-start,'limitations':['All observed loans at selected snapshots, not eligible model risk sets.','No labels, outcomes or model fits accessed.','Numeric plausibility checks are project judgments, not complete vendor validity rules.','Current release is not certified point-in-time history.']}
    c.close();(out/'assessment_result.json').write_text(json.dumps(result,indent=2)+'\n');print(out,flush=True)
    return result

if __name__=='__main__':run(Path(__file__).resolve().parents[2])
