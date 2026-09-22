from pathlib import Path
from datetime import date
from decimal import Decimal
import duckdb
from mortgage_risk.vendor_codes import code_issue
from mortgage_risk.monthly_summary import _calculate_balance_bridge, _resolve_monthly_table_name
import pytest

def test_sf_domains():
    assert code_issue('delinquency_status','99') is None
    assert code_issue('delinquency_status','XX') is None
    assert code_issue('delinquency_status','100')
    assert code_issue('modification_flag','Y') is None
    assert code_issue('modification_flag','yes')
    assert code_issue('zero_balance_code','97')
    assert code_issue('zero_balance_code','01') is None
    assert code_issue('zero_balance_code','') is None

def test_bridge_missing_entry_exit():
    c=duckdb.connect()
    c.execute('create table historical_monthly(loan_id varchar,reporting_month date,current_actual_upb decimal(18,2))')
    c.execute("insert into historical_monthly values ('a','2020-01-01',100),('a','2020-02-01',90),('b','2020-01-01',NULL),('c','2020-02-01',NULL),('d','2020-01-01',NULL),('d','2020-02-01',20),('e','2020-01-01',30),('e','2020-02-01',NULL)")
    rows,res=_calculate_balance_bridge(c)
    assert res==0
    assert Decimal(rows[0]['bridge_component_total']) == -20
    assert Decimal(rows[0]['missing_to_known_balance']) == 20
    assert Decimal(rows[0]['known_to_missing_balance']) == -30
    c.execute('create table sample_monthly(x int)')
    with pytest.raises(ValueError): _resolve_monthly_table_name(c)


def test_historical_ingestion_reports_unknown_codes(tmp_path):
    from mortgage_risk.ingestion import ingest_historical_file
    row=['']*113
    row[1]='0001';row[2]='012010';row[39]='XX';row[41]='Y';row[43]='97'
    src=tmp_path/'input.csv';src.write_text('|'.join(row))
    result=ingest_historical_file(src,selected_loan_ids=['0001'],db_path=tmp_path/'x.db',parquet_path=tmp_path/'x.parquet')
    assert result['unknown_code_counts']=={'zero_balance_code:97':1}
    assert result['overall_status']=='failed'


def test_diagnostics_keep_gaps_even_with_missing_balances(tmp_path):
    from mortgage_risk.monthly_summary import build_monthly_portfolio_summary
    path=tmp_path/'x.db';c=duckdb.connect(str(path))
    c.execute('create table historical_monthly(loan_id varchar,reporting_month date,current_actual_upb decimal(18,2),delinquency_status varchar,modification_flag varchar,zero_balance_code varchar)')
    c.execute("insert into historical_monthly values ('a','2020-01-01',NULL,'00','N',NULL),('a','2020-03-01',NULL,'00','N',NULL)")
    c.close()
    result=build_monthly_portfolio_summary(path,output_dir=tmp_path/'runs')
    counts={r['flag']:r['rows'] for r in result['diagnostic_counts']}
    assert counts=={'missing_balance':2,'monthly_gap':1}
    assert result['balance_bridge']==[]
    assert Path(result['diagnostics_path']).exists()
