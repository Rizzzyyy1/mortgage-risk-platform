import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from mortgage_risk.challenger import fit_transformer,transform,predict_export,evaluate


def test_preprocessing_uses_development_only_and_handles_unseen():
    x=np.array([[1.],[3.],[np.nan]]);cat=np.array([['a'],['b'],['a']])
    state=fit_transformer(x,cat,['x'],['c'])
    test=transform(np.array([[100.],[np.nan]]),np.array([['new'],['a']]),state)
    assert state['medians']==[2.]
    assert test[0,-1]==1
    assert test[1,0]==0 and test[1,1]==1
    assert state['means']==[2.]


def test_all_missing_feature_fails_explicitly():
    with pytest.raises(ValueError,match='All-missing'):
        fit_transformer(np.array([[np.nan]]),np.array([['a']]),['x'],['c'])


def test_export_probabilities_match_library():
    x=np.array([[-3.],[-2.],[0.],[1.],[3.],[4.]])
    y=np.array([0,0,1,1,2,2]);m=LogisticRegression(solver="newton-cholesky").fit(x,y)
    exported={'coefficients':m.coef_.tolist(),'intercepts':m.intercept_.tolist()}
    assert np.allclose(predict_export(x,exported),m.predict_proba(x),atol=1e-12)


def test_metrics_hand_calculated():
    y=np.array([0,1,2]);p=np.full((3,3),1/3)
    r=evaluate(y,p)
    assert r['log_loss']==pytest.approx(np.log(3))
    assert r['multiclass_brier']==pytest.approx(2/3)
    assert r['default_auc']==.5 and r['observed_expected']==1
    with pytest.raises(ValueError):evaluate(y,p*2)
