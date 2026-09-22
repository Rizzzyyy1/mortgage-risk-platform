import json
from unittest.mock import Mock
import pytest
import mortgage_risk.redevelopment_final_evaluation as rfe
from mortgage_risk.frozen_input_manifest import build_manifest, REQUIRED_KEYS


def never_call(*args, **kwargs):
    raise AssertionError('run_adapter must never be called when the frozen-input gate fails')


def test_run_raises_and_never_reaches_adapter_when_manifest_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(rfe, 'run_adapter', Mock(side_effect=never_call))
    (tmp_path / 'configs').mkdir()
    with pytest.raises(ValueError, match='not found'):
        rfe.run(tmp_path)
    rfe.run_adapter.assert_not_called()


def test_run_raises_and_never_reaches_adapter_when_a_required_input_changed(tmp_path, monkeypatch):
    monkeypatch.setattr(rfe, 'run_adapter', Mock(side_effect=never_call))
    configs = tmp_path / 'configs'
    configs.mkdir()
    paths = {}
    for key in REQUIRED_KEYS:
        p = configs / f'{key}.json'
        p.write_text(json.dumps({'content': key}))
        paths[key] = f'configs/{key}.json'
    manifest = build_manifest(tmp_path, paths)
    (configs / 'redevelopment_final_evaluation_manifest.json').write_text(json.dumps(manifest))

    # Mutate a required input AFTER the manifest was built -- exactly the scenario the gate exists
    # to catch: a changed input must be rejected before any cohort/label processing.
    (configs / 'benchmark.json').write_text(json.dumps({'content': 'MUTATED'}))

    with pytest.raises(ValueError, match='changed since the manifest'):
        rfe.run(tmp_path)
    rfe.run_adapter.assert_not_called()


def test_run_raises_when_manifest_omits_a_required_input(tmp_path, monkeypatch):
    monkeypatch.setattr(rfe, 'run_adapter', Mock(side_effect=never_call))
    configs = tmp_path / 'configs'
    configs.mkdir()
    paths = {}
    for key in REQUIRED_KEYS:
        p = configs / f'{key}.json'
        p.write_text(json.dumps({'content': key}))
        paths[key] = f'configs/{key}.json'
    manifest = build_manifest(tmp_path, paths)
    del manifest['entries']['calibration_result']
    (configs / 'redevelopment_final_evaluation_manifest.json').write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match='does not list required'):
        rfe.run(tmp_path)
    rfe.run_adapter.assert_not_called()
