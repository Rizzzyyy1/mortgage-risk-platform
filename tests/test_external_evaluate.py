import numpy as np
import pytest
from sklearn.metrics import roc_auc_score
from mortgage_risk.external_evaluate import auc_bins,weighted_auc,calibration_diagnostics


def test_weighted_auc_accounts_for_ties():
    y=np.array([0,1,0,2]);s=np.array([.5,.5,.8,.1]);w=np.array([2,1,1,3])
    assert weighted_auc(auc_bins(y,s),w)==pytest.approx(roc_auc_score(y==0,s,sample_weight=w))


def test_calibration_is_diagnostic_and_keeps_input():
    p=np.array([.2]*10+[.8]*10);before=p.copy();y=np.array([1]*2+[0]*8+[1]*8+[0]*2)
    r=calibration_diagnostics(y,p)
    assert r['intercept']==pytest.approx(0,abs=1e-6)
    assert r['slope']==pytest.approx(1,abs=1e-6)
    assert np.array_equal(p,before)
