import duckdb
import pytest
from mortgage_risk.exposure_eligibility import eligibility_sql, assert_join_keys


def connection():
    c=duckdb.connect()
    c.execute('''CREATE TABLE joined(loan_id VARCHAR, reporting_month DATE, current_actual_upb DECIMAL(18,2), zero_balance_code VARCHAR, modification_flag VARCHAR, loan_age INTEGER, origination_date DATE, first_payment_date DATE, zero_balance_effective_date_raw VARCHAR, zero_balance_effective_date DATE)''')
    return c


def rows(c):
    q=c.execute(eligibility_sql()); names=[d[0] for d in q.description]
    return {str(r[1]):dict(zip(names,r)) for r in q.fetchall()}


def test_boundaries_and_zero():
    c=connection()
    for age in (0,1,5,6,7,8):
        c.execute("INSERT INTO joined VALUES ('a',?::DATE,?,NULL,'N',?,'2020-01-01','2020-02-01',NULL,NULL)",[f'2020-{age+1:02d}-01',0 if age==8 else 100,age])
    r=rows(c)
    assert [r[f'2020-{a+1:02d}-01']['masking_status'] for a in (0,1,5,6,7)]==['unresolved','masked','masked','unresolved','unmasked']
    assert r['2020-08-01']['usable_reported_exposure']==100
    assert r['2020-09-01']['exposure_eligibility_reason']=='unmasked_zero_unexplained'
    assert r['2020-09-01']['current_actual_upb']==0


@pytest.mark.parametrize('age,origin,first',[(-1,'2020-01-01','2020-02-01'),(None,'2020-01-01','2020-02-01'),(7,None,'2020-02-01'),(7,'2020-01-01',None),(20,'2020-01-01','2020-02-01'),(7,'2021-01-01','2021-02-01'),(7,'2020-01-01','2019-12-01')])
def test_inconsistent_dates(age,origin,first):
    c=connection();c.execute("INSERT INTO joined VALUES ('a','2020-08-01',100,NULL,'N',?,?,?,NULL,NULL)",[age,origin,first])
    assert rows(c)['2020-08-01']['masking_status']=='unresolved'


def test_terminal_blank_and_no_future_leakage():
    c=connection()
    c.execute("INSERT INTO joined VALUES ('a','2020-08-01',100,NULL,'Y',7,'2020-01-01','2020-02-01',NULL,NULL)")
    before=rows(c)['2020-08-01']
    c.execute("INSERT INTO joined VALUES ('a','2020-09-01',0,'01',NULL,8,'2020-01-01','2020-02-01','092020','2020-09-01')")
    after=rows(c)
    assert after['2020-08-01']==before
    terminal=after['2020-09-01']
    assert terminal['previously_observed_modification_status']=='Y'
    assert terminal['modification_flag'] is None
    assert terminal['reported_modification_status']=='unknown_not_reported'
    assert terminal['exposure_eligibility_reason']=='terminal_record'
    assert terminal['usable_reported_exposure'] is None


@pytest.mark.parametrize('raw,date',[('bad',None),('092020','2020-09-01')])
def test_unresolved_terminal_dates(raw,date):
    c=connection();c.execute("INSERT INTO joined VALUES ('a','2020-08-01',100,NULL,'N',7,'2020-01-01','2020-02-01',?,?)",[raw,date])
    assert rows(c)['2020-08-01']['terminal_record_status']=='unresolved'


def test_join_guard():
    c=duckdb.connect();c.execute("CREATE TABLE base AS SELECT 'a' loan_id, DATE '2020-01-01' reporting_month,1 source_record_number")
    c.execute('CREATE TABLE supplement AS SELECT * FROM base')
    assert not any(assert_join_keys(c).values())
    c.execute('INSERT INTO supplement SELECT * FROM base')
    with pytest.raises(ValueError,match='Unsafe supplemental join'):assert_join_keys(c)
    c.execute('DELETE FROM supplement');c.execute("INSERT INTO supplement VALUES ('a','2020-01-01',2)")
    with pytest.raises(ValueError):assert_join_keys(c)


def test_actual_supplement_date_expression():
    from mortgage_risk.exposure_eligibility import month_date_sql
    c=duckdb.connect()
    result=c.execute(f"SELECT {month_date_sql('raw')} FROM (VALUES ('022010'),('22010'),('132010'),(NULL)) t(raw)").fetchall()
    assert str(result[0][0])=='2010-02-01'
    assert result[1:]==[(None,),(None,),(None,)]
