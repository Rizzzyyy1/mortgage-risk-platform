import duckdb
import pytest
from decimal import Decimal
from mortgage_risk.consolidated_validation import psi,calibration_status,validate_curve,permutation_attribution,prediction_metrics


def test_population_shift():
    assert psi([10,20],[10,20])==0
    assert psi([100,0],[0,100])>0
    with pytest.raises(ValueError):psi([0],[0])


def test_thresholds_are_sample_gated():
    c=dict(minimum_segment_loans=100,minimum_expected_defaults=20,oe_critical_low=.67,oe_critical_high=1.5,oe_warning_low=.8,oe_warning_high=1.25)
    assert calibration_status(7,.1,0,c)=='insufficient_support'
    assert calibration_status(1000,30,40,c)=='warning'
    assert calibration_status(1000,30,50,c)=='critical'
    assert calibration_status(1000,30,30,c)=='within_judgmental_band'


def test_independent_risk_recursion():
    rows=[dict(at_risk=4,defaults=1,payoff_or_maturity=1,censored=1,survival=.5,default_cif=.25,payoff_or_maturity_cif=.25),dict(at_risk=1,defaults=0,payoff_or_maturity=0,censored=1,survival=.5,default_cif=.25,payoff_or_maturity_cif=.25)]
    assert validate_curve(rows)==2
    rows[1]['survival']=.6
    with pytest.raises(ValueError):validate_curve(rows)


def test_independent_permutation_interactions():
    v={str(m):{'loss':str(sum(i+1 for i in range(4) if m&(1<<i))+(12 if m&3==3 else 0))} for m in range(16)}
    assert permutation_attribution(v,'loss')==[Decimal(7),Decimal(8),Decimal(3),Decimal(4)]


def test_independent_sql_metrics():
    c=duckdb.connect();c.execute("""CREATE TABLE predictions AS SELECT * FROM (VALUES
    ('default_proxy',.8,.1,.1),('payoff_or_maturity',.1,.8,.1),('observed_event_free_12m',.1,.1,.8)) t(outcome,p_default,p_payoff_maturity,p_event_free)""")
    m=prediction_metrics(c)
    assert m['default_auc']==1 and m['defaults']==1 and m['loans']==3
    assert m['multiclass_brier']==pytest.approx(.06)
