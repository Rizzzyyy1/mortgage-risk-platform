import duckdb
from mortgage_risk.portfolio_descriptive import event_rows_sql, loan_outcomes_sql


def setup(rows):
    c=duckdb.connect();c.execute('CREATE TABLE panel(loan_id VARCHAR,reporting_month DATE,delinquency_status VARCHAR,zero_balance_code VARCHAR)')
    c.executemany('INSERT INTO panel VALUES (?,?,?,?)',rows)
    return c


def outcome(c):
    c.execute('CREATE OR REPLACE VIEW event_rows AS '+event_rows_sql())
    q=c.execute(loan_outcomes_sql());names=[x[0] for x in q.description]
    return {r[0]:dict(zip(names,r)) for r in q.fetchall()}


def test_default_is_first_only_and_not_exposure_filtered():
    c=setup([('a','2020-01-01','00',None),('a','2020-02-01','03',None),('a','2020-03-01','04',None),('a','2020-04-01','00','01')])
    r=outcome(c)['a'];assert r['first_stop']=='default_proxy';assert str(r['stop_month'])=='2020-02-01';assert r['outcome_12m']=='default_proxy'


def test_payoff_and_ambiguous_tie():
    c=setup([('a','2020-01-01','00',None),('a','2020-02-01','00','01'),('b','2020-01-01','00',None),('b','2020-02-01','03','01')])
    r=outcome(c);assert r['a']['outcome_12m']=='payoff_or_maturity';assert r['b']['outcome_12m']=='censored_or_unresolved'


def test_gap_censors_before_later_default():
    c=setup([('a','2020-01-01','00',None),('a','2020-03-01','03',None)])
    r=outcome(c)['a'];assert r['first_stop']=='gap_censor';assert str(r['stop_month'])=='2020-01-01';assert r['outcome_12m']=='censored_or_unresolved'


def test_unknown_and_prevalent_entries():
    c=setup([('a','2020-01-01',None,None),('a','2020-02-01','00',None),('b','2020-01-01','03',None),('c','2020-01-01','00',None),('c','2020-02-01','XX',None),('c','2020-03-01','03',None)])
    r=outcome(c);assert r['a']['entry_delinquency'] is None
    assert r['a']['outcome_12m']==r['b']['outcome_12m']=='ineligible_at_entry'
    assert r['c']['outcome_12m']=='censored_or_unresolved'


def test_twelve_months_complete_and_incomplete():
    rows=[('a',f'2020-{m:02d}-01','00',None) for m in range(1,13)]+[('a','2021-01-01','00',None),('b','2020-01-01','00',None)]
    r=outcome(setup(rows));assert r['a']['outcome_12m']=='observed_event_free_12m';assert r['b']['outcome_12m']=='incomplete_followup'


def test_gap_after_completed_horizon_does_not_erase_followup():
    rows=[('a',f'2020-{m:02d}-01','00',None) for m in range(1,13)]+[('a','2021-01-01','00',None),('a','2021-03-01','03',None)]
    assert outcome(setup(rows))['a']['outcome_12m']=='observed_event_free_12m'


def test_event_exactly_horizon_counts_and_later_event_does_not():
    rows=[]
    for loan,eventmonth in [('a','2021-01-01'),('b','2021-02-01')]:
        rows.extend((loan,f'2020-{m:02d}-01','00',None) for m in range(1,13))
        rows.append((loan,'2021-01-01','03' if loan=='a' else '00',None))
        if loan=='b':rows.append((loan,eventmonth,'03',None))
    r=outcome(setup(rows));assert r['a']['outcome_12m']=='default_proxy';assert r['b']['outcome_12m']=='observed_event_free_12m'


def test_asof_candidates_do_not_change_with_future_rows():
    c=setup([('a','2020-01-01','00',None)])
    before=c.execute(event_rows_sql()).fetchall()
    c.execute("INSERT INTO panel VALUES ('a','2020-02-01','03',NULL)")
    after=c.execute('SELECT * FROM ('+event_rows_sql()+") WHERE reporting_month=DATE '2020-01-01'").fetchall()
    assert before==after


def test_credit_exit_and_noncredit_exit():
    rows=[]
    for code in ('02','03','09','15','06','16','96'):
        rows += [(code,'2020-01-01','00',None),(code,'2020-02-01','XX',code)]
    r=outcome(setup(rows))
    for code in ('02','03','09','15'):assert r[code]['outcome_12m']=='default_proxy'
    for code in ('06','16','96'):assert r[code]['outcome_12m']=='censored_or_unresolved'


def test_full_runner_reconciles_small_fixture(tmp_path):
    import json
    from mortgage_risk.portfolio_descriptive import run
    inp=tmp_path/'artifacts/runs/exposure_eligibility/7b7177c3473345d091dd1cd19d24799e';inp.mkdir(parents=True)
    accepted=tmp_path/'artifacts/runs/historical_ingest/fullquarter_replacement/7a30ef59b2e74c518133ddf5923c92c9';accepted.mkdir(parents=True)
    c=duckdb.connect()
    c.execute("""CREATE TABLE fixture AS SELECT 'a' loan_id,DATE '2020-01-01' reporting_month,'00' delinquency_status,NULL::VARCHAR zero_balance_code,
      100::DECIMAL(18,2) current_actual_upb,true exposure_eligible,100::DECIMAL(18,2) usable_reported_exposure,
      'N' reported_modification_status,'eligible_positive_reported_balance' exposure_eligibility_reason""")
    for path in [inp/'exposure_eligibility.parquet',accepted/'historical_monthly.parquet']:
        c.execute('COPY fixture TO ? (FORMAT PARQUET)',[str(path)])
    (inp/'eligibility_result.json').write_text(json.dumps(dict(engineering_status='pass',output_records=1,source_checksum_sha256_inherited='fixture',eligibility_counts=[dict(exposure_eligibility_reason='eligible_positive_reported_balance',records=1)])))
    r=run(tmp_path)
    assert r['status']=='pass'
    assert r['counts']==dict(records=1,loans=1,months=1)
    assert r['outcomes_12m']==[dict(outcome_12m='incomplete_followup',loans=1)]
