"""Training-only candidate features; preserves raw values and fits no preprocessing."""
import json
import uuid
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint

RANGES={'borrower_fico':(300,850),'ltv':(1,97),'dti':(0,100),'original_term':(1,600)}
CATEGORIES={'occupancy':['P','S','I','U'],'purpose':['C','R','P','U']}


def feature_sql():
    parts=[]
    for name,(low,high) in RANGES.items():
        valid=f"regexp_full_match(f.{name},'[0-9]+') AND try_cast(f.{name} AS INTEGER) BETWEEN {low} AND {high}"
        parts += [f'f.{name} {name}_raw',f'CASE WHEN {valid} THEN cast(f.{name} AS INTEGER) END {name}',f"CASE WHEN f.{name} IS NULL THEN 'missing' WHEN {valid} THEN 'valid' ELSE 'invalid' END {name}_quality"]
    for name,codes in CATEGORIES.items():
        allowed=','.join("'"+x+"'" for x in codes)
        parts += [f'f.{name} {name}_raw',f"CASE WHEN f.{name} IN ({allowed}) THEN f.{name} ELSE 'MISSING_OR_INVALID' END {name}",f"CASE WHEN f.{name} IS NULL THEN 'missing' WHEN f.{name} IN ({allowed}) THEN 'valid' ELSE 'invalid' END {name}_quality"]
    return "SELECT t.*, CASE WHEN substr(md5('expanded-v1:'||t.loan_id),1,1) IN ('0','1','2') THEN 'internal_validation' ELSE 'development' END development_split,"+','.join(parts)+" FROM training t JOIN factors f ON t.loan_id=f.loan_id AND strftime(t.reporting_month,'%m%Y')=f.reporting_month_raw"


def build(conn):
    for table,key in [('training','loan_id,reporting_month'),('factors','loan_id,reporting_month_raw')]:
        if conn.execute(f'SELECT count(*) FROM (SELECT {key},count(*) n FROM {table} GROUP BY {key} HAVING n>1)').fetchone()[0]:raise ValueError('Duplicate feature keys')
    conn.execute('CREATE TABLE expanded AS '+feature_sql())
    expected=conn.execute('SELECT count(*) FROM training').fetchone()[0]
    if conn.execute('SELECT count(*) FROM expanded').fetchone()[0]!=expected:raise ValueError('Feature join lost training records')
    return expected


def run(root):
    root=Path(root).resolve()
    train=root/'artifacts/runs/phase4a/346469500fc34c66b760aeb21def6ffe/train_features.parquet'
    factors=root/'artifacts/runs/risk_factor_assessment/00fd2e4a925d4d2fa284ceb1efd01a4e/snapshot_factors.parquet'
    out=root/'artifacts/runs/expanded_features'/uuid.uuid4().hex;out.mkdir(parents=True)
    c=duckdb.connect();c.execute("SET memory_limit='1GB'")
    c.read_parquet(str(train)).create_view('training');c.read_parquet(str(factors)).create_view('factors')
    if c.execute("SELECT count(*) FROM training WHERE reporting_month!=DATE '2011-01-01' OR substr(md5(loan_id),1,1) NOT IN ('0','1','2','3','4','5','6','7','8','9','a','b')").fetchone()[0]:raise ValueError('Not the authorized original training population')
    count=build(c)
    def rows(sql):
        cur=c.execute(sql);return [dict(zip([x[0] for x in cur.description],r)) for r in cur.fetchall()]
    quality={k:rows(f'SELECT development_split,{k}_quality quality,count(*) records FROM expanded GROUP BY 1,2 ORDER BY 1,2') for k in list(RANGES)+list(CATEGORIES)}
    splits=rows('SELECT development_split,count(*) records FROM expanded GROUP BY 1 ORDER BY 1')
    if len(splits)!=2:raise ValueError('Empty internal split')
    c.execute('COPY expanded TO ? (FORMAT PARQUET)',[str(out/'expanded_features.parquet')])
    result={'status':'pass_for_feature_preparation','records':count,'splits':splits,'quality':quality,'ranges':RANGES,'range_note':'Project plausibility checks; not complete vendor rules. No clipping or imputation.','split_rule':'md5(expanded-v1: + loan_id) first hex digit 0/1/2 => internal validation; remainder development. Original training loans only.','input_sha256':{'training':fingerprint(train),'factors':fingerprint(factors)},'implementation_sha256':fingerprint(__file__),'limitations':['Internal split is same-date exploratory validation, not fresh out-of-time or external validation.','Outcome labels not accessed. No imputation, scaling, model fitting or feature selection based on outcomes.','Current source vintage is not certified point-in-time.','New independent cohort required for external acceptance.']}
    (out/'feature_result.json').write_text(json.dumps(result,indent=2)+'\n');c.close();print(out)
    return result

if __name__=='__main__':run(Path(__file__).resolve().parents[2])
