import json
import time
import pytest
from mortgage_risk.frozen_input_manifest import build_manifest, verify_manifest, REQUIRED_KEYS


def make_inputs(tmp_path):
    paths = {}
    for key in REQUIRED_KEYS:
        p = tmp_path / f'{key}.json'
        p.write_text(json.dumps({'content': key}))
        paths[key] = p.name
    return paths


def test_build_manifest_records_current_hashes_and_is_dated_now(tmp_path):
    paths = make_inputs(tmp_path)
    manifest = build_manifest(tmp_path, paths)
    assert set(manifest['entries']) == set(REQUIRED_KEYS)
    assert 'never backdated' in manifest['note']
    created = time.strptime(manifest['created_at'], '%Y-%m-%dT%H:%M:%SZ')
    assert created.tm_year >= 2026


def test_build_manifest_raises_on_missing_required_key(tmp_path):
    paths = make_inputs(tmp_path)
    del paths['benchmark']
    with pytest.raises(ValueError, match='missing required'):
        build_manifest(tmp_path, paths)


def test_build_manifest_raises_when_a_listed_file_does_not_exist(tmp_path):
    paths = make_inputs(tmp_path)
    paths['candidate'] = 'does_not_exist.json'
    with pytest.raises(ValueError, match='file not found'):
        build_manifest(tmp_path, paths)


def test_build_manifest_cross_checks_against_historical_record(tmp_path):
    paths = make_inputs(tmp_path)
    manifest = build_manifest(tmp_path, paths)
    hist_path = tmp_path / 'historical.json'
    hist_path.write_text(json.dumps({'candidate_sha256': manifest['entries']['candidate']['sha256'],
                                      'benchmark_sha256': 'WRONG'}))
    manifest2 = build_manifest(tmp_path, paths, historical_record_path='historical.json',
                                historical_key_map={'candidate': 'candidate_sha256', 'benchmark': 'benchmark_sha256'})
    cc = manifest2['cross_check_against_historical_record']
    assert cc['candidate']['matches'] is True
    assert cc['benchmark']['matches'] is False


def test_verify_manifest_passes_when_nothing_changed(tmp_path):
    paths = make_inputs(tmp_path)
    manifest = build_manifest(tmp_path, paths)
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest))
    assert verify_manifest(manifest_path, tmp_path) is True


def test_verify_manifest_raises_on_missing_manifest_file(tmp_path):
    with pytest.raises(ValueError, match='not found'):
        verify_manifest(tmp_path / 'nope.json', tmp_path)


def test_verify_manifest_raises_on_missing_required_input(tmp_path):
    paths = make_inputs(tmp_path)
    manifest = build_manifest(tmp_path, paths)
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest))
    (tmp_path / paths['candidate']).unlink()
    with pytest.raises(ValueError, match='missing'):
        verify_manifest(manifest_path, tmp_path)


def test_verify_manifest_raises_on_changed_input_content(tmp_path):
    paths = make_inputs(tmp_path)
    manifest = build_manifest(tmp_path, paths)
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest))
    (tmp_path / paths['benchmark']).write_text(json.dumps({'content': 'MUTATED'}))
    with pytest.raises(ValueError, match='changed since the manifest'):
        verify_manifest(manifest_path, tmp_path)


def test_verify_manifest_raises_when_a_required_key_is_unlisted(tmp_path):
    paths = make_inputs(tmp_path)
    manifest = build_manifest(tmp_path, paths)
    del manifest['entries']['protocol']
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='does not list required'):
        verify_manifest(manifest_path, tmp_path)
