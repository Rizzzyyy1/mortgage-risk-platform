import numpy as np
import pytest
from mortgage_risk.calibration_remediation import adjust, fit_offsets, fold_ids


def test_offset_fit_recovers_known_class_frequencies():
    p = np.tile([.2, .3, .5], (100, 1))
    y = np.repeat([0, 1, 2], [10, 20, 70])
    a = fit_offsets(p, y)
    q = adjust(p, a)
    assert np.allclose(q.mean(axis=0), [.1, .2, .7], atol=1e-7)
    assert np.allclose(q.sum(axis=1), 1)
    assert np.allclose(adjust(p, [0, 0]), p)
    assert np.all(p == [.2, .3, .5])


def test_invalid_inputs_fail_closed_and_fold_assignment_is_stable():
    with pytest.raises(ValueError):
        adjust([[0, .3, .7]], [0, 0])
    with pytest.raises(ValueError):
        fit_offsets(np.tile([.2, .3, .5], (3, 1)), [0, 0, 1])
    assert fold_ids(['a', 'b', 'a']).tolist() == [fold_ids(['a'])[0], fold_ids(['b'])[0], fold_ids(['a'])[0]]
