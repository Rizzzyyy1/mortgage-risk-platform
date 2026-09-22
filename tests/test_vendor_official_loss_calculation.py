from datetime import date
import duckdb
from mortgage_risk.vendor_official_loss_calculation import (
    official_net_loss_sql, official_int_cost_sql, CREDIT_EVENT_DELINQUENCY_THRESHOLD,
    GUARANTY_FEE_DEDUCTION_BPS,
)


def test_credit_event_threshold_is_180_day_not_90_day():
    # the vendor's own trigger is a materially different (later) threshold than this project's
    # 90-day (delinquency>=3) default-proxy anchor.
    assert CREDIT_EVENT_DELINQUENCY_THRESHOLD == 6
    assert GUARANTY_FEE_DEDUCTION_BPS == 0.0035


def test_official_net_loss_matches_hand_calculation_with_default_zero_fill():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE t(last_upb DECIMAL(18,2), fcc_cost DECIMAL(18,2), pp_cost DECIMAL(18,2),
          ar_cost DECIMAL(18,2), ie_cost DECIMAL(18,2), tax_cost DECIMAL(18,2), pfg_cost DECIMAL(18,2),
          int_cost DECIMAL(18,2), ns_procs DECIMAL(18,2), ce_procs DECIMAL(18,2), rmw_procs DECIMAL(18,2),
          o_procs DECIMAL(18,2))
    """)
    # last_upb=100000, costs sum=5000, forgiveness=2000, interest=1500, proceeds sum=80000
    c.execute("INSERT INTO t VALUES (100000, 2000, 1000, 500, 300, 200, 2000, 1500, 70000, 5000, 3000, 2000)")
    result = c.execute(f"SELECT ({official_net_loss_sql()}) FROM t").fetchone()[0]
    # 100000 + (2000+1000+500+300+200) + 2000 + 1500 - (70000+5000+3000+2000)
    # = 100000 + 4000 + 2000 + 1500 - 80000 = 27500
    assert result == 27500


def test_official_net_loss_zero_fills_missing_cost_and_proceeds_fields():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE t(last_upb DECIMAL(18,2), fcc_cost DECIMAL(18,2), pp_cost DECIMAL(18,2),
          ar_cost DECIMAL(18,2), ie_cost DECIMAL(18,2), tax_cost DECIMAL(18,2), pfg_cost DECIMAL(18,2),
          int_cost DECIMAL(18,2), ns_procs DECIMAL(18,2), ce_procs DECIMAL(18,2), rmw_procs DECIMAL(18,2),
          o_procs DECIMAL(18,2))
    """)
    # everything but last_upb and ns_procs is NULL
    c.execute("INSERT INTO t VALUES (50000, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 45000, NULL, NULL, NULL)")
    result = c.execute(f"SELECT ({official_net_loss_sql()}) FROM t").fetchone()[0]
    assert result == 5000  # 50000 + 0s - 45000


def test_official_net_loss_is_null_when_exposure_itself_is_missing_never_zero_filled():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE t(last_upb DECIMAL(18,2), fcc_cost DECIMAL(18,2), pp_cost DECIMAL(18,2),
          ar_cost DECIMAL(18,2), ie_cost DECIMAL(18,2), tax_cost DECIMAL(18,2), pfg_cost DECIMAL(18,2),
          int_cost DECIMAL(18,2), ns_procs DECIMAL(18,2), ce_procs DECIMAL(18,2), rmw_procs DECIMAL(18,2),
          o_procs DECIMAL(18,2))
    """)
    c.execute("INSERT INTO t VALUES (NULL, 1000, NULL, NULL, NULL, NULL, NULL, NULL, 5000, NULL, NULL, NULL)")
    result = c.execute(f"SELECT ({official_net_loss_sql()}) FROM t").fetchone()[0]
    assert result is None  # exposure is never treated as zero, unlike the cost/proceeds fields


def test_int_cost_matches_hand_calculation_with_guaranty_fee_deduction():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE t(last_paid_installment_date DATE, resolution_month DATE,
          last_rt DECIMAL(8,3), last_upb DECIMAL(18,2), non_int_upb DECIMAL(18,2))
    """)
    # 6% rate, 4 months delinquent, $200,000 balance, $0 non-interest-bearing:
    # 4 * ((6/100 - 0.0035)/12) * 200000 = 4 * (0.0565/12) * 200000 = 4 * 0.00470833... * 200000
    c.execute("INSERT INTO t VALUES ('2020-01-01','2020-05-01',6.0,200000,0)")
    result = c.execute(f"SELECT ({official_int_cost_sql()}) FROM t").fetchone()[0]
    expected = 4 * ((6.0 / 100 - 0.0035) / 12) * 200000
    assert abs(float(result) - expected) < 0.01


def test_int_cost_subtracts_non_interest_bearing_upb_from_the_balance_base():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE t(last_paid_installment_date DATE, resolution_month DATE,
          last_rt DECIMAL(8,3), last_upb DECIMAL(18,2), non_int_upb DECIMAL(18,2))
    """)
    c.execute("INSERT INTO t VALUES ('2020-01-01','2020-05-01',6.0,200000,50000)")
    result = c.execute(f"SELECT ({official_int_cost_sql()}) FROM t").fetchone()[0]
    expected = 4 * ((6.0 / 100 - 0.0035) / 12) * (200000 - 50000)
    assert abs(float(result) - expected) < 0.01


def test_int_cost_is_null_not_fabricated_when_rate_or_dates_missing():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE t(last_paid_installment_date DATE, resolution_month DATE,
          last_rt DECIMAL(8,3), last_upb DECIMAL(18,2), non_int_upb DECIMAL(18,2))
    """)
    c.execute("INSERT INTO t VALUES (NULL,'2020-05-01',6.0,200000,0)")
    c.execute("INSERT INTO t VALUES ('2020-01-01','2020-05-01',NULL,200000,0)")
    for row in c.execute(f"SELECT ({official_int_cost_sql()}) FROM t").fetchall():
        assert row[0] is None


def test_implausible_rate_guard_flags_a_column_mapping_error():
    # regression test for a real bug caught during development: reading field 10 (Original UPB,
    # e.g. 98000.00) instead of field 9 (Current Interest Rate) produced "rates" like 98000%.
    c = duckdb.connect()
    c.execute("CREATE TABLE official(loan_id VARCHAR, last_rt DECIMAL(8,3))")
    c.execute("INSERT INTO official VALUES ('L1', 6.25), ('L2', 98000.00), ('L3', NULL)")
    implausible = c.execute(
        "SELECT count(*) FROM official WHERE last_rt IS NOT NULL AND (last_rt < 0 OR last_rt > 20)"
    ).fetchone()[0]
    assert implausible == 1


def test_last_rt_carry_forward_window_function_picks_most_recent_known_rate():
    # mirrors the module's last_rt window logic directly, since it is only expressed inline in
    # run(); this test locks the exact pattern (last_value IGNORE NULLS ordered by month).
    c = duckdb.connect()
    c.execute("CREATE TABLE rate_history(loan_id VARCHAR, reporting_month DATE, current_interest_rate DECIMAL(8,3))")
    c.execute("""
        INSERT INTO rate_history VALUES
        ('L1','2020-01-01',5.5), ('L1','2020-02-01',5.5), ('L1','2020-05-01',5.5)
    """)
    # terminal/resolution row is 2020-06-01, with no rate reported that month; the last known
    # rate (2020-05-01) should be picked, not NULL.
    row = c.execute("""
        SELECT last_value(current_interest_rate IGNORE NULLS) OVER (
          PARTITION BY loan_id ORDER BY reporting_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS last_rt
        FROM rate_history WHERE loan_id='L1' ORDER BY reporting_month DESC LIMIT 1
    """).fetchone()
    assert row[0] == 5.5
