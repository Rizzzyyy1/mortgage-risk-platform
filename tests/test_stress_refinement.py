import json
from pathlib import Path
from decimal import Decimal
import pytest
from mortgage_risk.benchmark import project_example
from mortgage_risk.stress_refinement import stress_weights,present_value,shapley,run


def test_scalar_projection_is_preserved_by_constant_paths():
    a=project_example(100,0,2,.1,.2,.5)
    b=project_example(100,0,2,[.1,.1],[.2,.2],[.5,.5])
    assert a==b
    with pytest.raises(ValueError):project_example(100,0,2,[.1],.2,.5)
    with pytest.raises(ValueError):project_example(100,0,2,[.1,.9],[.2,.2],.5)


def test_stress_boundaries():
    w=stress_weights(120,24,60)
    assert w[0]==w[23]==1 and w[24]==pytest.approx(35/36)
    assert w[59]==w[-1]==0
    with pytest.raises(ValueError):stress_weights(12,24,60)


def test_pv_hand_calculation_and_recovery_tail():
    s=project_example(100,0,2,.1,.2,.5)['schedule']
    assert float(present_value(s,0,18)['timing_adjusted_pv_loss'])==pytest.approx(6.75)
    q=1.12**(1/12)
    expected=10/q+3.5/q**2-5/q**3-1.75/q**4
    assert float(present_value(s,.12,2)['timing_adjusted_pv_loss'])==pytest.approx(expected)
    assert float(present_value(s,.12,2)['undiscounted_recovery_beyond_loan_horizon'])==pytest.approx(6.75)
    assert Decimal(present_value(s,.12,18)['timing_adjusted_pv_loss'])>Decimal(present_value(s,.12,0)['timing_adjusted_pv_loss'])


def test_exact_interaction_allocation():
    assert shapley({0:0,1:1,2:2,3:7},2)==[Decimal(3),Decimal(4)]
    values={m:5+sum(v for i,v in enumerate([1,2,3,4]) if m&(1<<i))+(12 if m&3==3 else 0) for m in range(16)}
    assert [float(x) for x in shapley(values)]==pytest.approx([7,8,3,4])
    with pytest.raises(ValueError):shapley({0:0},2)


def test_full_refinement(tmp_path):
    inp=tmp_path/'input';inp.mkdir();cfg=json.loads((Path(__file__).parents[1]/'configs/stress_refinement.json').read_text());cfg['benchmark_run']='input'
    base=project_example(100000,.04,120,.001,.01,.2)
    prior=dict(status='pass',hypothetical_loan=dict(opening_balance=100000,annual_coupon=.04,remaining_months=120),pooled_first12=dict(default_hazard=.001,payoff_or_maturity_hazard=.01),illustrative_scenarios={'baseline':dict(assumptions={'lgd':.2},remaining_life_expected_loss=base['remaining_life_expected_loss'])})
    (inp/'benchmark_result.json').write_text(json.dumps(prior));cp=tmp_path/'config.json';cp.write_text(json.dumps(cfg))
    r=run(tmp_path,cp);assert r['status']=='pass'
    for metric,contributions in r['shapley_attribution'].items():
        delta=Decimal(r['adverse'][metric])-Decimal(r['baseline'][metric])
        assert abs(sum(Decimal(x) for x in contributions.values())-delta)<Decimal('0.00000001')
    assert Decimal(r['shapley_attribution']['remaining_life_expected_loss']['recovery_delay'])==0
