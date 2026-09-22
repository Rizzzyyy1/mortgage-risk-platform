import duckdb
from mortgage_risk.external_cohort import label_sql


def test_external_horizon_default_and_censor_boundaries():
    c=duckdb.connect()
    c.execute("CREATE TABLE expanded AS SELECT x::VARCHAR loan_id,DATE '2012-01-01' reporting_month FROM range(4) t(x)")
    c.execute("""CREATE TABLE outcomes AS SELECT * FROM (VALUES
    ('0','default_proxy',DATE '2013-01-01',DATE '2013-01-01'),
    ('1','gap_censor',DATE '2013-01-01',DATE '2013-02-01'),
    ('2','unknown_status',DATE '2013-01-01',DATE '2013-02-01'),
    ('3',NULL::VARCHAR,NULL::DATE,DATE '2012-12-01')) t(loan_id,first_stop,stop_month,last_month)""")
    values={r[0]:r[2] for r in c.execute(label_sql()).fetchall()}
    assert values=={'0':'default_proxy','1':'observed_event_free_12m','2':'censored_or_unresolved','3':'incomplete_followup'}
    c.close()
