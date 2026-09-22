import duckdb
import pytest
from mortgage_risk.expanded_features import build


def fixture():
    c=duckdb.connect()
    c.execute("CREATE TABLE training AS SELECT 'x' loan_id,DATE '2011-01-01' reporting_month")
    c.execute("CREATE TABLE factors AS SELECT 'x' loan_id,'012011' reporting_month_raw,'720' borrower_fico,'80' ltv,NULL::VARCHAR dti,'360' original_term,'U' occupancy,'P' purpose")
    return c


def test_missing_and_unknown_remain_distinct():
    c=fixture();assert build(c)==1
    assert c.execute('SELECT dti,dti_quality,occupancy,occupancy_quality FROM expanded').fetchone()==(None,'missing','U','valid')


def test_invalid_preserved_not_clipped():
    c=fixture();c.execute("UPDATE factors SET borrower_fico='999',ltv='80.5'");build(c)
    assert c.execute('SELECT borrower_fico_raw,borrower_fico,borrower_fico_quality,ltv_quality FROM expanded').fetchone()==('999',None,'invalid','invalid')


def test_duplicate_join_rejected():
    c=fixture();c.execute('INSERT INTO factors SELECT * FROM factors')
    with pytest.raises(ValueError,match='Duplicate'):build(c)


def test_unmatched_join_rejected():
    c=fixture();c.execute("UPDATE factors SET loan_id='other'")
    with pytest.raises(ValueError,match='lost'):build(c)
