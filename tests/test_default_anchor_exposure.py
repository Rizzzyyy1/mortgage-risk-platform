from datetime import date
import duckdb
from mortgage_risk.default_anchor_exposure import ANCHOR_CLASSIFICATION_SQL, PRIOR_BALANCE_SQL


def make_conn():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE exposure_eligibility(
            loan_id VARCHAR, reporting_month DATE, current_actual_upb DECIMAL(18,2),
            masking_status VARCHAR, terminal_record_status VARCHAR,
            exposure_eligibility_reason VARCHAR, usable_reported_exposure DECIMAL(18,2)
        )
    """)
    c.execute("""
        CREATE TABLE workout_episodes(
            loan_id VARCHAR, anchor_month DATE, category VARCHAR, resolution_month DATE,
            has_loss_fields BOOLEAN
        )
    """)
    return c


def test_prior_balance_picks_most_recent_eligible_value_at_or_before_each_row():
    c = make_conn()
    c.execute("""
        INSERT INTO exposure_eligibility VALUES
        ('L1','2020-01-01',1000,'unmasked','not_observed_terminal','eligible_positive_reported_balance',1000),
        ('L1','2020-02-01',NULL,'masked','not_observed_terminal','masked_early_life',NULL),
        ('L1','2020-03-01',990,'unmasked','not_observed_terminal','eligible_positive_reported_balance',990),
        ('L1','2020-04-01',NULL,'unresolved','terminal_status_unresolved','terminal_status_unresolved',NULL)
    """)
    rows = c.execute(f"{PRIOR_BALANCE_SQL} ORDER BY reporting_month").fetchall()
    cols = [d[0] for d in c.description]
    by_month = {dict(zip(cols, r))['reporting_month']: dict(zip(cols, r)) for r in rows}
    assert by_month[date(2020, 1, 1)]['prior_supported_balance'] == 1000
    # month 2 is masked (no usable value that month); the proxy carries forward month 1's value.
    assert by_month[date(2020, 2, 1)]['prior_supported_balance'] == 1000
    assert by_month[date(2020, 2, 1)]['prior_supported_balance_month'] == date(2020, 1, 1)
    # month 3 has its own eligible value, so the proxy is itself (age zero downstream).
    assert by_month[date(2020, 3, 1)]['prior_supported_balance'] == 990
    assert by_month[date(2020, 3, 1)]['prior_supported_balance_month'] == date(2020, 3, 1)
    # month 4 is unresolved; proxy still carries forward the most recent eligible value (month 3).
    assert by_month[date(2020, 4, 1)]['prior_supported_balance'] == 990
    assert by_month[date(2020, 4, 1)]['prior_supported_balance_month'] == date(2020, 3, 1)


def test_prior_balance_is_null_when_never_eligible_before_this_row():
    c = make_conn()
    c.execute("""
        INSERT INTO exposure_eligibility VALUES
        ('L2','2020-01-01',NULL,'masked','not_observed_terminal','masked_early_life',NULL),
        ('L2','2020-02-01',0,'unmasked','not_observed_terminal','unmasked_zero_unexplained',NULL)
    """)
    rows = c.execute(f"{PRIOR_BALANCE_SQL} ORDER BY reporting_month").fetchall()
    cols = [d[0] for d in c.description]
    for r in rows:
        row = dict(zip(cols, r))
        assert row['prior_supported_balance'] is None
        assert row['prior_supported_balance_month'] is None


def test_terminal_same_month_classification_overrides_terminal_record_only_at_the_anchor_row():
    c = make_conn()
    c.execute("""
        INSERT INTO exposure_eligibility VALUES
        ('L3','2020-03-01',5000,'unmasked','terminal','terminal_record',NULL)
    """)
    c.execute("""
        INSERT INTO workout_episodes VALUES ('L3','2020-03-01','disposed_credit_exit','2020-03-01',true)
    """)
    row = c.execute(f"""
        SELECT ({ANCHOR_CLASSIFICATION_SQL}) AS classification
        FROM workout_episodes w JOIN exposure_eligibility e
          ON w.loan_id=e.loan_id AND w.anchor_month=e.reporting_month
    """).fetchone()
    assert row[0] == 'terminal_same_month'


def test_terminal_record_at_a_later_resolution_month_is_not_relabeled_terminal_same_month():
    # anchor is delinquency-triggered (not itself terminal); disposition happens two months later.
    # exposure_eligibility_reason at the anchor row is a normal category, not 'terminal_record',
    # so the classification must pass through unchanged, not be overridden.
    c = make_conn()
    c.execute("""
        INSERT INTO exposure_eligibility VALUES
        ('L4','2020-01-01',8000,'unmasked','not_observed_terminal','eligible_positive_reported_balance',8000)
    """)
    c.execute("""
        INSERT INTO workout_episodes VALUES ('L4','2020-01-01','disposed_credit_exit','2020-03-01',true)
    """)
    row = c.execute(f"""
        SELECT ({ANCHOR_CLASSIFICATION_SQL}) AS classification
        FROM workout_episodes w JOIN exposure_eligibility e
          ON w.loan_id=e.loan_id AND w.anchor_month=e.reporting_month
    """).fetchone()
    assert row[0] == 'eligible_positive_reported_balance'


def test_masked_or_missing_anchor_balance_is_never_substituted():
    c = make_conn()
    c.execute("""
        INSERT INTO exposure_eligibility VALUES
        ('L5','2020-02-01',NULL,'masked','not_observed_terminal','masked_early_life',NULL)
    """)
    c.execute("""
        INSERT INTO workout_episodes VALUES ('L5','2020-02-01','still_delinquent_at_data_end',NULL,false)
    """)
    row = c.execute(f"""
        SELECT e.current_actual_upb, ({ANCHOR_CLASSIFICATION_SQL}) AS classification
        FROM workout_episodes w JOIN exposure_eligibility e
          ON w.loan_id=e.loan_id AND w.anchor_month=e.reporting_month
    """).fetchone()
    assert row[0] is None
    assert row[1] == 'masked_early_life'
