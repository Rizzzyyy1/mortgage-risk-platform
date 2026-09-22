import math,json
from pathlib import Path
import duckdb
import pytest
from mortgage_risk.estimated_models import fit,predict,metrics,auc_bootstrap,run,CLASSES


def test_smoothed_probabilities_and_unseen_fallback():
    hist=[dict(group_key='a',outcome=CLASSES[0],n=2),dict(group_key='a',outcome=CLASSES[2],n=8)]
    m=fit(hist,10);expected=(2+10*m['prior'][0])/20
    assert predict(m,'a')[0]==pytest.approx(expected)
    assert sum(predict(m,'a'))==pytest.approx(1)
    assert predict(m,'unseen')==m['prior']
    hist.append(dict(group_key='a',outcome='censored_or_unresolved',n=100))
    assert fit(hist,10)==m


def test_exact_metrics():
    rows=[dict(probs=[.8,.1,.1],outcome=CLASSES[0],n=1),dict(probs=[.1,.8,.1],outcome=CLASSES[1],n=1),dict(probs=[.1,.1,.8],outcome=CLASSES[2],n=1)]
    m=metrics(rows);assert m['default_auc']==1
    assert m['multiclass_log_loss']==pytest.approx(-math.log(.8))
    assert m['multiclass_brier']==pytest.approx(.06)
    assert m['observed_expected_default_ratio']==pytest.approx(1)
    assert auc_bootstrap(rows,20,1)['lower']==1


def test_auc_ties_and_invalid_probabilities():
    rows=[dict(probs=[.2,.3,.5],outcome=k,n=1) for k in CLASSES]
    assert metrics(rows)['default_auc']==.5
    with pytest.raises(ValueError):metrics([dict(probs=[.2,.3,.6],outcome=CLASSES[0],n=1)])
    with pytest.raises(ValueError):fit([],10)
    with pytest.raises(ValueError):fit([dict(group_key='a',outcome=CLASSES[0],n=1)],0)


def test_complete_runner(tmp_path):
    inp=tmp_path/'input';inp.mkdir();c=duckdb.connect()
    for split in ['train','validation','test']:
        c.execute('CREATE OR REPLACE TABLE f(loan_id VARCHAR,reporting_month DATE,delinquency_months INT,modification_status VARCHAR)')
        c.execute('CREATE OR REPLACE TABLE l(loan_id VARCHAR,reporting_month DATE,outcome_12m VARCHAR)')
        for i,k in enumerate(CLASSES+[CLASSES[2],'censored_or_unresolved']):
            c.execute("INSERT INTO f VALUES (?,'2020-01-01',0,'N')",[split+str(i)])
            c.execute("INSERT INTO l VALUES (?,'2020-01-01',?)",[split+str(i),k])
        c.execute('COPY f TO ? (FORMAT PARQUET)',[str(inp/(split+'_features.parquet'))])
        c.execute('COPY l TO ? (FORMAT PARQUET)',[str(inp/(split+'_labels.parquet'))])
    (inp/'design_result.json').write_text(json.dumps({'status':'pass'}))
    cfg=dict(input_run='input',smoothing_strengths=[10,100],bootstrap_repeats=20,seed=2026);cp=tmp_path/'config.json';cp.write_text(json.dumps(cfg))
    r=run(tmp_path,cp)
    assert r['status']=='pass'
    assert r['censoring_sensitivity']['test']['censored_or_unresolved']==1
    assert r['censoring_sensitivity']['test']['default_rate_upper']==.4
    assert r['test_metrics'][r['selected_model']]['loans']==4
    selection=json.loads((Path(r['output_directory'])/'selection.json').read_text())
    assert selection['selected']==min(selection['validation_metrics'],key=lambda k:(selection['validation_metrics'][k]['multiclass_log_loss'],k))
