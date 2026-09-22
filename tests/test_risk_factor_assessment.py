import duckdb
from mortgage_risk.risk_factor_assessment import FIELDS, profile


def test_profile_distinguishes_missing_invalid_and_valid_values():
    c=duckdb.connect()
    c.execute('CREATE TABLE factors(reporting_month_raw VARCHAR,'+','.join(f'{name} VARCHAR' for name in FIELDS)+')')
    for fico,channel in [(None,None),('bad','Z'),('720','R')]:
        c.execute('INSERT INTO factors(reporting_month_raw,borrower_fico,channel) VALUES (?,?,?)',['012011',fico,channel])
    result=profile(c)
    assert result['borrower_fico'][0]['missing']==1
    assert result['borrower_fico'][0]['conversion_failures']==1
    assert result['borrower_fico'][0]['minimum']==720
    assert result['channel'][0]['unsupported_codes']==1
    assert result['channel'][0]['missing']==1
    c.close()


def test_profiles_keep_snapshots_separate():
    c=duckdb.connect()
    c.execute('CREATE TABLE factors(reporting_month_raw VARCHAR,'+','.join(f'{name} VARCHAR' for name in FIELDS)+')')
    c.execute("INSERT INTO factors(reporting_month_raw,borrower_fico) VALUES ('012011','700'),('032026',NULL)")
    rows=profile(c)['borrower_fico']
    assert [r['missing'] for r in rows]==[0,1]
    assert [r['records'] for r in rows]==[1,1]
    c.close()
