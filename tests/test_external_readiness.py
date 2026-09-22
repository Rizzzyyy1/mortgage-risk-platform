import json
import pytest
from mortgage_risk.artifact_integrity import create_manifest
from mortgage_risk.external_readiness import check


def setup(root):
    (root/'configs').mkdir()
    cfg={'candidate':'candidate.json','benchmark':'benchmark.json','development_result':'result.json','expected_source':'data/2011Q1.csv','cohort':'2011Q1'}
    for name in ['candidate.json','benchmark.json','result.json']:(root/name).write_text('{}')
    (root/'configs/external_evaluation.json').write_text(json.dumps(cfg))
    paths=['configs/external_evaluation.json','candidate.json','benchmark.json','result.json']
    (root/'configs/external_evaluation_integrity.json').write_text(json.dumps(create_manifest(root,paths)))


def test_missing_source_is_explicitly_pending(tmp_path):
    setup(tmp_path);r=check(tmp_path)
    assert r['status']=='waiting_for_reserved_cohort' and not r['model_promoted']


def test_source_presence_does_not_mean_acceptance(tmp_path):
    setup(tmp_path);(tmp_path/'data').mkdir();(tmp_path/'data/2011Q1.csv').write_text('unvalidated')
    r=check(tmp_path)
    assert r['status']=='source_present_validation_required' and not r['external_evaluation_completed']


def test_changed_candidate_fails_closed(tmp_path):
    setup(tmp_path);(tmp_path/'candidate.json').write_text('{"changed":true}')
    with pytest.raises(ValueError,match='integrity'):check(tmp_path)
