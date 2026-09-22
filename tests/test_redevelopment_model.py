from pathlib import Path
import duckdb
from mortgage_risk.redevelopment_model import load_population


def write_parquet(conn, rows, columns, path):
    placeholders = ','.join(columns)
    conn.execute(f"CREATE TABLE t({','.join(c + ' VARCHAR' for c in columns)})")
    for row in rows:
        conn.execute(f"INSERT INTO t VALUES ({','.join('?' for _ in row)})", list(row))
    conn.execute(f"COPY t TO '{path}' (FORMAT PARQUET)")
    conn.execute("DROP TABLE t")


def test_load_population_splits_known_from_unresolved_outcomes(tmp_path):
    conn = duckdb.connect()
    fcols = ['loan_id', 'reporting_month', 'delinquency_months', 'modification_status', 'borrower_fico', 'ltv', 'dti', 'original_term', 'occupancy', 'purpose', 'development_split']
    write_parquet(conn, [
        ('L1', '2011-01-01', '0', 'N', '700', '80', '30', '360', 'P', 'C', 'development'),
        ('L2', '2011-01-01', '1', 'N', '650', '85', '35', '360', 'P', 'C', 'development'),
    ], fcols, tmp_path / 'features.parquet')
    write_parquet(conn, [
        ('L1', '2011-01-01', 'default_proxy'),
        ('L2', '2011-01-01', 'censored_or_unresolved'),
    ], ['loan_id', 'reporting_month', 'outcome_12m'], tmp_path / 'labels.parquet')
    conn2 = duckdb.connect()
    numeric, categorical, y, coverage, rows = load_population(
        conn2, tmp_path / 'features.parquet', tmp_path / 'labels.parquet', 'x', split_filter='development'
    )
    assert coverage == {'total': 2, 'known': 1, 'unresolved': 1}
    assert len(y) == 1
    assert numeric.shape == (1, 4)


def test_load_population_filters_by_development_split(tmp_path):
    conn = duckdb.connect()
    fcols = ['loan_id', 'reporting_month', 'delinquency_months', 'modification_status', 'borrower_fico', 'ltv', 'dti', 'original_term', 'occupancy', 'purpose', 'development_split']
    write_parquet(conn, [
        ('L1', '2011-01-01', '0', 'N', '700', '80', '30', '360', 'P', 'C', 'development'),
        ('L2', '2011-01-01', '0', 'N', '650', '85', '35', '360', 'P', 'C', 'internal_validation'),
    ], fcols, tmp_path / 'features.parquet')
    write_parquet(conn, [
        ('L1', '2011-01-01', 'default_proxy'),
        ('L2', '2011-01-01', 'payoff_or_maturity'),
    ], ['loan_id', 'reporting_month', 'outcome_12m'], tmp_path / 'labels.parquet')
    conn2 = duckdb.connect()
    numeric, categorical, y, coverage, rows = load_population(
        conn2, tmp_path / 'features.parquet', tmp_path / 'labels.parquet', 'x', split_filter='development'
    )
    assert coverage['total'] == 1  # internal_validation row excluded by the split filter
    assert [r[0] for r in rows] == ['L1']


def test_load_population_raises_on_duplicate_keys(tmp_path):
    conn = duckdb.connect()
    fcols = ['loan_id', 'reporting_month', 'delinquency_months', 'modification_status', 'borrower_fico', 'ltv', 'dti', 'original_term', 'occupancy', 'purpose', 'development_split']
    write_parquet(conn, [
        ('L1', '2011-01-01', '0', 'N', '700', '80', '30', '360', 'P', 'C', 'development'),
        ('L1', '2011-01-01', '0', 'N', '700', '80', '30', '360', 'P', 'C', 'development'),
    ], fcols, tmp_path / 'features.parquet')
    write_parquet(conn, [('L1', '2011-01-01', 'default_proxy')], ['loan_id', 'reporting_month', 'outcome_12m'], tmp_path / 'labels.parquet')
    conn2 = duckdb.connect()
    try:
        load_population(conn2, tmp_path / 'features.parquet', tmp_path / 'labels.parquet', 'x')
        assert False, 'expected ValueError'
    except ValueError as e:
        assert 'Duplicate' in str(e)


def test_load_population_no_split_filter_uses_the_full_population(tmp_path):
    conn = duckdb.connect()
    fcols = ['loan_id', 'reporting_month', 'delinquency_months', 'modification_status', 'borrower_fico', 'ltv', 'dti', 'original_term', 'occupancy', 'purpose']
    write_parquet(conn, [
        ('L1', '2012-01-01', '0', 'N', '700', '80', '30', '360', 'P', 'C'),
        ('L2', '2012-01-01', '1', 'Y', '650', '85', '35', '360', 'S', 'R'),
    ], fcols, tmp_path / 'features.parquet')
    write_parquet(conn, [
        ('L1', '2012-01-01', 'observed_event_free_12m'),
        ('L2', '2012-01-01', 'payoff_or_maturity'),
    ], ['loan_id', 'reporting_month', 'outcome_12m'], tmp_path / 'labels.parquet')
    conn2 = duckdb.connect()
    numeric, categorical, y, coverage, rows = load_population(conn2, tmp_path / 'features.parquet', tmp_path / 'labels.parquet', 'x')
    assert coverage == {'total': 2, 'known': 2, 'unresolved': 0}
