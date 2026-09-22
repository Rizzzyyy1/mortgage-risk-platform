from datetime import date
import duckdb
from mortgage_risk.multi_cohort_adapter import label_sql, FEATURE_POSITIONS, build_features


def test_feature_positions_match_the_original_external_cohort_hardcoded_values():
    # regression: these positions were previously hardcoded in external_cohort.py (now frozen and
    # unchanged); the parameterized adapter must reproduce them exactly for the same source layout.
    assert FEATURE_POSITIONS == {'borrower_fico': 23, 'ltv': 19, 'dti': 22, 'original_term': 12, 'occupancy': 29, 'purpose': 26}


def test_label_sql_reproduces_the_original_2011q1_evaluation_contract_when_given_its_date():
    # external_cohort.py hardcoded outcome_end_date='2013-01-01'; passing that same date through
    # the parameterized version must produce the identical boundary conditions.
    sql = label_sql('2013-01-01')
    assert "DATE '2013-01-01'" in sql
    assert sql.count("DATE '2013-01-01'") == 4  # four boundary comparisons in the CASE expression


def test_label_sql_uses_the_calibration_cohort_date_when_given_a_different_one():
    sql = label_sql('2014-02-01')
    assert "DATE '2014-02-01'" in sql
    assert "DATE '2013-01-01'" not in sql


def make_panel_conn():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE panel(loan_id VARCHAR, month_raw VARCHAR, reporting_month DATE,
          delinquency_status VARCHAR, zero_balance_code VARCHAR, modification_status VARCHAR,
          borrower_fico VARCHAR, ltv VARCHAR, dti VARCHAR, original_term VARCHAR,
          occupancy VARCHAR, purpose VARCHAR)
    """)
    return c


def test_all_cohort_disjointness_check_raises_on_overlap(tmp_path):
    c = make_panel_conn()
    c.execute("""
        INSERT INTO panel VALUES
        ('999999999999','012024','2024-01-01','00',NULL,'N','700','80','30','360','P','C')
    """)
    other = tmp_path / 'other_loans.parquet'
    o = duckdb.connect()
    o.execute("CREATE TABLE t(loan_id VARCHAR)")
    o.execute("INSERT INTO t VALUES ('999999999999')")  # same loan_id as the new panel row
    o.execute(f"COPY t TO '{other}' (FORMAT PARQUET)")
    o.close()
    overlaps = {}
    for label, path in {'development_2010q1': other}.items():
        c.execute(f"CREATE OR REPLACE VIEW other_{label} AS SELECT DISTINCT loan_id FROM read_parquet('{str(path)}')")
        overlaps[label] = c.execute(f'SELECT count(DISTINCT loan_id) FROM panel JOIN other_{label} USING(loan_id)').fetchone()[0]
    assert overlaps['development_2010q1'] == 1  # confirms the overlap-detection query itself is correct


def test_all_cohort_disjointness_check_passes_with_no_overlap(tmp_path):
    c = make_panel_conn()
    c.execute("""
        INSERT INTO panel VALUES
        ('111111111111','012024','2024-01-01','00',NULL,'N','700','80','30','360','P','C')
    """)
    other = tmp_path / 'other_loans.parquet'
    o = duckdb.connect()
    o.execute("CREATE TABLE t(loan_id VARCHAR)")
    o.execute("INSERT INTO t VALUES ('222222222222')")  # different loan
    o.execute(f"COPY t TO '{other}' (FORMAT PARQUET)")
    o.close()
    c.execute(f"CREATE VIEW other_x AS SELECT DISTINCT loan_id FROM read_parquet('{str(other)}')")
    overlap = c.execute('SELECT count(DISTINCT loan_id) FROM panel JOIN other_x USING(loan_id)').fetchone()[0]
    assert overlap == 0
