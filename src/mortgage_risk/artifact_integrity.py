"""Local artifact integrity controls; hashes detect changes, not authenticity."""
import hashlib
import json
from pathlib import Path


def safe_path(root, relative):
    root = Path(root).resolve()
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Manifest paths must be relative and confined to the project')
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('Manifest path escapes project')
    return resolved


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def create_manifest(root, paths):
    paths = list(paths)
    if not paths or len(set(paths)) != len(paths):
        raise ValueError('Expected a nonempty unique artifact list')
    return {'schema_version': 1, 'files': {p: fingerprint(safe_path(root, p)) for p in sorted(paths)}}


def verify_manifest(root, manifest_path, required):
    manifest = json.loads(Path(manifest_path).read_text())
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('files'), dict):
        raise ValueError('Unsupported integrity manifest')
    required = set(required)
    if not required or not required.issubset(manifest['files']):
        raise ValueError('Integrity manifest does not cover all required inputs')
    for relative, expected in manifest['files'].items():
        if fingerprint(safe_path(root, relative)) != expected:
            raise ValueError(f'Artifact integrity mismatch: {relative}')
    return manifest
