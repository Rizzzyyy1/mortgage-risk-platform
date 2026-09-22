from decimal import Decimal
import json
from pathlib import Path
import duckdb
import pytest
from mortgage_risk.benchmark import life_table,project_example,episode_sql,run


def test_hand_calculated_competing_risks_with_censoring():
    hist=[dict(duration=1,event_kind=k,loans=1) for k in ('default_proxy','payoff_or_maturity','censored')]+[dict(duration=2,event_kind='censored',loans=1)]
    curve,c0=life_table(hist,4)
    assert c0==0
    assert curve[0]['survival']==.5
    assert curve[0]['default_cif']==curve[0]['payoff_or_maturity_cif']==.25
    assert curve[1]['at_risk']==1
    assert curve[1]['survival']==.5


def test_immediate_censor_is_not_a_non_event():
    curve,c0=life_table([dict(duration=0,event_kind='censored',loans=1),dict(duration=1,event_kind='default_proxy',loans=1)],2)
    assert c0==1 and curve[0]['at_risk']==1 and curve[0]['default_cif']==1


def test_bad_risk_histogram_rejected():
    with pytest.raises(ValueError):life_table([dict(duration=-1,event_kind='censored',loans=1)],1)
    with pytest.raises(ValueError):life_table([dict(duration=0,event_kind='default_proxy',loans=1)],1)
    with pytest.raises(ValueError):life_table([dict(duration=1,event_kind='censored',loans=1)],2)


def test_hand_calculated_loss_and_single_survival_weight():
    r=project_example(100,0,2,.1,.2,.5)
    assert float(r['remaining_life_expected_loss'])==pytest.approx(6.75)
    assert float(r['expected_defaulted_balance'])==pytest.approx(13.5)
    assert r['default_probability_12m']==pytest.approx(.17)
    assert Decimal(r['schedule'][-1]['conditional_closing_balance'])==0
    assert r['schedule'][-1]['contractual_maturity_cif']==pytest.approx(.49)


def test_zero_default_and_amortization():
    r=project_example(100000,.04,120,0,.01,.2)
    assert Decimal(r['remaining_life_expected_loss'])==0
    balances=[Decimal(x['conditional_opening_balance']) for x in r['schedule']]
    assert all(a>b for a,b in zip(balances,balances[1:]))
    assert r['schedule'][-1]['survival']==0


def test_stress_and_competing_payoffs():
    base=project_example(100000,.04,120,.001,.01,.2)
    stress=project_example(100000,.04,120,.002,.007,.35)
    nopay=project_example(100000,.04,120,.001,0,.2)
    assert Decimal(stress['remaining_life_expected_loss'])>Decimal(base['remaining_life_expected_loss'])
    assert Decimal(nopay['remaining_life_expected_loss'])>Decimal(base['remaining_life_expected_loss'])
    assert base['remaining_life_default_probability']>base['default_probability_12m']


@pytest.mark.parametrize('hd,hp,lgd',[(.8,.3,.2),(-.1,.2,.2),(.1,.1,1.1),(float('nan'),.1,.2)])
def test_invalid_assumptions(hd,hp,lgd):
    with pytest.raises(ValueError):project_example(100,0,12,hd,hp,lgd)


def test_unknown_interval_vs_gap_censor_timing():
    c=duckdb.connect();c.execute("""CREATE TABLE outcomes AS SELECT * FROM (VALUES
      ('a',DATE '2020-01-01','unknown_status',DATE '2020-03-01',DATE '2020-04-01',true),
      ('b',DATE '2020-01-01','gap_censor',DATE '2020-03-01',DATE '2020-05-01',true),
      ('c',DATE '2020-01-01','default_proxy',DATE '2020-01-01',DATE '2020-05-01',false))
      t(loan_id,entry_month,first_stop,stop_month,last_month,at_risk_at_entry)""")
    rows=c.execute(episode_sql()+' ORDER BY loan_id').fetchall()
    assert [r[-1] for r in rows]==[1,2]


def test_complete_runner(tmp_path):
    inp=tmp_path/'input';inp.mkdir()
    c=duckdb.connect();c.execute("""CREATE TABLE outcomes AS SELECT * FROM (VALUES
      ('a',DATE '2020-01-01','default_proxy',DATE '2020-02-01',DATE '2020-02-01',true),
      ('b',DATE '2020-01-01','payoff_or_maturity',DATE '2020-02-01',DATE '2020-02-01',true),
      ('c',DATE '2020-01-01',NULL::VARCHAR,NULL::DATE,DATE '2021-01-01',true))
      t(loan_id,entry_month,first_stop,stop_month,last_month,at_risk_at_entry)""")
    c.execute('COPY outcomes TO ? (FORMAT PARQUET)',[str(inp/'loan_outcomes.parquet')])
    (inp/'descriptive_result.json').write_text(json.dumps(dict(status='pass',counts={'loans':3},source_checksum_inherited='fixture',outcomes_12m=[dict(outcome_12m='default_proxy',loans=1),dict(outcome_12m='payoff_or_maturity',loans=1)])))
    cfg=json.loads((Path(__file__).parents[1]/'configs/benchmark.json').read_text());cfg['input_run']='input'
    cp=tmp_path/'config.json';cp.write_text(json.dumps(cfg))
    r=run(tmp_path,cp)
    assert r['status']=='pass' and r['historical_12m']['default_cif']==pytest.approx(1/3)
    assert r['event_count_differences']==dict(default_proxy=0,payoff_or_maturity=0)
