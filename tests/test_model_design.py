import hashlib,json
from pathlib import Path
import duckdb
import pytest
from mortgage_risk.model_design import validate_splits,run,FEATURES


def config():return json.loads((Path(__file__).parents[1]/'configs/model_design.json').read_text())


def test_split_overlap_and_horizon_rejected():
    rows=config()['splits'];validate_splits(rows)
    rows[1]['snapshot_date']='2012-01-01'
    with pytest.raises(ValueError):validate_splits(rows)
    rows=config()['splits'];rows[1]['hash_prefixes']='ab'
    with pytest.raises(ValueError):validate_splits(rows)


def test_end_to_end_feature_separation_and_asof_entry(tmp_path):
    cfg=config();e=tmp_path/cfg['eligibility_run'];o=tmp_path/cfg['event_run'];e.mkdir(parents=True);o.mkdir(parents=True)
    c=duckdb.connect();c.execute('CREATE TABLE p(loan_id VARCHAR,reporting_month DATE,delinquency_status VARCHAR,loan_age INT,original_upb DECIMAL(18,2),usable_reported_exposure DECIMAL(18,2),reported_modification_status VARCHAR)')
    c.execute('CREATE TABLE o(loan_id VARCHAR,at_risk_at_entry BOOLEAN,first_stop VARCHAR,stop_month DATE,stop_observed_month DATE,last_month DATE)')
    for split in cfg['splits']:
        loan=next(str(n) for n in range(1000) if hashlib.md5(str(n).encode()).hexdigest()[0] in split['hash_prefixes'])
        date=split['snapshot_date'];year=int(date[:4]);end=f'{year}-03-01'
        c.execute('INSERT INTO p VALUES (?,?,?,12,100000,NULL,?)',[loan,date,'00','N'])
        c.execute('INSERT INTO o VALUES (?,true,?,?,?,?)',[loan,'default_proxy',end,end,end])
    c.execute('COPY p TO ? (FORMAT PARQUET)',[str(e/'exposure_eligibility.parquet')]);c.execute('COPY o TO ? (FORMAT PARQUET)',[str(o/'loan_outcomes.parquet')])
    (e/'eligibility_result.json').write_text(json.dumps({'engineering_status':'pass'}));(o/'descriptive_result.json').write_text(json.dumps({'status':'pass'}))
    cp=tmp_path/'config.json';cp.write_text(json.dumps(cfg));r=run(tmp_path,cp)
    assert r['selected_loans']==3 and r['loan_overlap']==0
    assert all(x['outcome_12m']=='default_proxy' for x in r['split_outcomes'])
    for split in ['train','validation','test']:
        f=Path(r['output_directory'])/(split+'_features.parquet')
        names=[x[0] for x in c.execute('SELECT * FROM read_parquet(?)',[str(f)]).description]
        assert names==['loan_id','reporting_month']+FEATURES
        assert c.execute('SELECT eligible_reported_balance FROM read_parquet(?)',[str(f)]).fetchone()[0] is None
    # Changing a future event alters retrospective labels but not exported features.
    c.execute("UPDATE o SET first_stop='payoff_or_maturity'")
    c.execute('COPY o TO ? (FORMAT PARQUET)',[str(o/'loan_outcomes.parquet')])
    later=run(tmp_path,cp)
    for split in ['train','validation','test']:
        a=str(Path(r['output_directory'])/(split+'_features.parquet'));b=str(Path(later['output_directory'])/(split+'_features.parquet'))
        assert c.execute('SELECT * FROM read_parquet(?)',[a]).fetchall()==c.execute('SELECT * FROM read_parquet(?)',[b]).fetchall()
    assert all(x['outcome_12m']=='payoff_or_maturity' for x in later['split_outcomes'])
