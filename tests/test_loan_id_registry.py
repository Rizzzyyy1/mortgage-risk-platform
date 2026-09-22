import json
from pathlib import Path
import pytest
from mortgage_risk.loan_id_registry import build, RAW_COLUMNS


def write_raw_csv(path, loan_ids):
    lines = []
    for loan_id in loan_ids:
        cols = [''] * RAW_COLUMNS
        cols[1] = loan_id  # c1
        cols[2] = '012011'  # c2, reporting month, arbitrary but well-formed
        lines.append('|'.join(cols))
    path.write_text('\n'.join(lines), encoding='utf-8')


def test_build_extracts_distinct_loan_ids_only(tmp_path):
    source = tmp_path / 'synthetic.csv'
    write_raw_csv(source, ['900000000001', '900000000002', '900000000001'])  # one duplicate row
    result = build(tmp_path, cohort='TESTQ1', source_relpath='synthetic.csv')
    assert result['status'] == 'pass_for_loan_id_registry'
    assert result['distinct_loan_count'] == 2
    out_path = tmp_path / 'artifacts/runs/loan_id_registry/TESTQ1_loan_ids.parquet'
    assert out_path.exists()

    import duckdb
    conn = duckdb.connect()
    ids = {r[0] for r in conn.execute(f"SELECT loan_id FROM read_parquet('{out_path}')").fetchall()}
    assert ids == {'900000000001', '900000000002'}

    receipt = json.loads((tmp_path / 'artifacts/runs/loan_id_registry/TESTQ1_loan_ids.receipt.json').read_text())
    assert receipt['distinct_loan_count'] == 2
    assert receipt['cohort'] == 'TESTQ1'


def test_build_raises_on_malformed_loan_id(tmp_path):
    source = tmp_path / 'synthetic.csv'
    write_raw_csv(source, ['900000000001', 'not-a-loan-id'])
    with pytest.raises(ValueError, match='invalid loan_id'):
        build(tmp_path, cohort='TESTQ1', source_relpath='synthetic.csv')


def test_build_raises_when_source_missing(tmp_path):
    with pytest.raises(ValueError, match='not found'):
        build(tmp_path, cohort='TESTQ1', source_relpath='does_not_exist.csv')
