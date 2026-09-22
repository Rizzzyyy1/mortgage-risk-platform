"""Fail-closed frozen-input verification: reject missing, changed or unlisted required inputs
BEFORE any cohort/label processing begins. This closes the freeze-enforcement gap the publication
review found -- redevelopment_final_evaluation.py previously recorded hashes of its inputs only
AFTER scoring, which cannot detect or block a changed/substituted input before an expensive run.

A manifest built by build_manifest() is a forward-looking control for FUTURE executions. Its
creation timestamp is genuine and is never backdated, and building or verifying it does NOT
retroactively prove that the historical run it references was itself gated this way -- it only
establishes, from the moment of creation onward, that a mismatch will be rejected before
processing. Where a historical run already recorded its own input hashes (e.g.
final_evaluation_result.json), build_manifest() can additionally cross-check the current file
hashes against that historical record, which IS meaningful evidence that nothing has changed
since that run.
"""
import json
import time
from pathlib import Path
from mortgage_risk.artifact_integrity import fingerprint

REQUIRED_KEYS = ('candidate', 'benchmark', 'calibration_result', 'protocol')


def build_manifest(root, paths, historical_record_path=None, historical_key_map=None):
    root = Path(root).resolve()
    missing_keys = [k for k in REQUIRED_KEYS if k not in paths]
    if missing_keys:
        raise ValueError(f'Manifest is missing required key(s): {missing_keys}')

    entries = {}
    for key, relpath in paths.items():
        full = root / relpath
        if not full.exists():
            raise ValueError(f'Cannot build manifest: {key} file not found at {relpath}')
        entries[key] = {'path': relpath, 'sha256': fingerprint(full)}

    cross_check = None
    if historical_record_path is not None:
        historical = json.loads((root / historical_record_path).read_text())
        cross_check = {}
        for key, hist_key in (historical_key_map or {}).items():
            if key in entries and hist_key in historical:
                cross_check[key] = {
                    'current_sha256': entries[key]['sha256'],
                    'historical_sha256': historical[hist_key],
                    'matches': entries[key]['sha256'] == historical[hist_key],
                }

    return {
        'schema_version': 1,
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'note': (
            "Forward-looking control for future executions only. This timestamp is genuine and was "
            "never backdated. Building or verifying this manifest does not prove the historical run "
            "referenced by cross_check_against_historical_record was itself gated by this check -- "
            "only that, as of creation, the listed files matched that run's own recorded hashes "
            "where a historical record was available."
        ),
        'entries': entries,
        'cross_check_against_historical_record': cross_check,
    }


def verify_manifest(manifest_path, root):
    root = Path(root).resolve()
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise ValueError(f'Frozen-input manifest not found: {manifest_path}')
    manifest = json.loads(manifest_path.read_text())
    entries = manifest.get('entries', {})
    missing_keys = [k for k in REQUIRED_KEYS if k not in entries]
    if missing_keys:
        raise ValueError(f'Manifest does not list required input(s): {missing_keys}')
    for key, entry in entries.items():
        full = root / entry['path']
        if not full.exists():
            raise ValueError(f'Required frozen input missing: {key} ({entry["path"]})')
        actual = fingerprint(full)
        if actual != entry['sha256']:
            raise ValueError(
                f'Required frozen input changed since the manifest was built: {key} ({entry["path"]}) '
                f'expected {entry["sha256"]} got {actual}'
            )
    return True
