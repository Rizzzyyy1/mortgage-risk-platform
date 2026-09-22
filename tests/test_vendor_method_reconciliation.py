from datetime import date
import duckdb
from mortgage_risk.vendor_method_reconciliation import foregone_interest_sql, NEW_FIELDS


def make_conn():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE t(loan_id VARCHAR, last_paid_installment_date DATE, disposition_date DATE,
        upb_at_removal DECIMAL(18,2), current_interest_rate DECIMAL(8,3))
    """)
    return c


def test_foregone_interest_matches_hand_calculation():
    c = make_conn()
    # $200,000 at 6% annual (0.5%/month) for 4 months delinquent: 200000 * 0.005 * 4 = 4000.00
    c.execute("INSERT INTO t VALUES ('L1','2020-01-01','2020-05-01',200000,6.0)")
    result = c.execute(f"SELECT ({foregone_interest_sql()}) FROM t").fetchone()[0]
    assert result == 4000.00


def test_foregone_interest_is_null_when_upb_at_removal_missing():
    c = make_conn()
    c.execute("INSERT INTO t VALUES ('L2','2020-01-01','2020-05-01',NULL,6.0)")
    result = c.execute(f"SELECT ({foregone_interest_sql()}) FROM t").fetchone()[0]
    assert result is None


def test_foregone_interest_is_null_when_rate_missing():
    c = make_conn()
    c.execute("INSERT INTO t VALUES ('L3','2020-01-01','2020-05-01',200000,NULL)")
    result = c.execute(f"SELECT ({foregone_interest_sql()}) FROM t").fetchone()[0]
    assert result is None


def test_foregone_interest_is_null_when_dates_missing():
    c = make_conn()
    c.execute("INSERT INTO t VALUES ('L4',NULL,'2020-05-01',200000,6.0)")
    c.execute("INSERT INTO t VALUES ('L5','2020-01-01',NULL,200000,6.0)")
    for loan_id in ('L4', 'L5'):
        result = c.execute(f"SELECT ({foregone_interest_sql()}) FROM t WHERE loan_id=?", [loan_id]).fetchone()[0]
        assert result is None


def test_foregone_interest_is_null_not_negative_when_dates_implausible():
    # disposition before last paid installment is implausible; the guard must return NULL
    # rather than a fabricated negative interest figure.
    c = make_conn()
    c.execute("INSERT INTO t VALUES ('L6','2020-05-01','2020-01-01',200000,6.0)")
    result = c.execute(f"SELECT ({foregone_interest_sql()}) FROM t").fetchone()[0]
    assert result is None


def test_foregone_interest_zero_when_disposition_equals_last_paid_month():
    c = make_conn()
    c.execute("INSERT INTO t VALUES ('L7','2020-03-01','2020-03-01',200000,6.0)")
    result = c.execute(f"SELECT ({foregone_interest_sql()}) FROM t").fetchone()[0]
    assert result == 0


def test_new_fields_cover_expected_glossary_positions():
    # 46 UPB at Time of Removal, 51 Last Paid Installment Date, 63/64 modification/forgiveness,
    # 80 foreclosure write-off, 106-108 alternative delinquency resolution / count / deferral.
    assert set(NEW_FIELDS.keys()) == {46, 51, 63, 64, 80, 106, 107, 108}


def test_vendor_anchored_and_faq_zero_filled_loss_arithmetic():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE comparison(anchor_current_actual_upb DECIMAL(18,2), upb_at_removal DECIMAL(18,2),
        total_costs_zero_filled DECIMAL(18,2), total_proceeds_zero_filled DECIMAL(18,2),
        estimated_foregone_interest DECIMAL(18,2))
    """)
    # anchor=100000, removal=95000 (amortized down before disposition), costs=5000, proceeds=80000, interest=1200
    c.execute("INSERT INTO comparison VALUES (100000, 95000, 5000, 80000, 1200)")
    row = c.execute("""
        SELECT anchor_current_actual_upb + total_costs_zero_filled - total_proceeds_zero_filled AS faq_zero_filled,
          COALESCE(upb_at_removal, anchor_current_actual_upb) + total_costs_zero_filled
            + COALESCE(estimated_foregone_interest,0) - total_proceeds_zero_filled AS vendor_anchored
        FROM comparison
    """).fetchone()
    assert row[0] == 25000  # 100000 + 5000 - 80000
    assert row[1] == 21200  # 95000 + 5000 + 1200 - 80000


def test_vendor_anchored_falls_back_to_anchor_upb_when_removal_upb_missing():
    c = duckdb.connect()
    c.execute("""
        CREATE TABLE comparison(anchor_current_actual_upb DECIMAL(18,2), upb_at_removal DECIMAL(18,2),
        total_costs_zero_filled DECIMAL(18,2), total_proceeds_zero_filled DECIMAL(18,2),
        estimated_foregone_interest DECIMAL(18,2))
    """)
    c.execute("INSERT INTO comparison VALUES (100000, NULL, 5000, 80000, NULL)")
    row = c.execute("""
        SELECT COALESCE(upb_at_removal, anchor_current_actual_upb) + total_costs_zero_filled
          + COALESCE(estimated_foregone_interest,0) - total_proceeds_zero_filled AS vendor_anchored
        FROM comparison
    """).fetchone()
    assert row[0] == 25000  # falls back to anchor UPB, treats missing interest as 0, matching COALESCE, not silent NULL propagation
