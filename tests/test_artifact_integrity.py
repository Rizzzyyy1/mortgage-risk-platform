import json
import pytest
from mortgage_risk.artifact_integrity import create_manifest, verify_manifest, safe_path


def test_mutation_is_detected(tmp_path):
    (tmp_path/'a').write_text('accepted')
    manifest=tmp_path/'receipt.json';manifest.write_text(json.dumps(create_manifest(tmp_path,['a'])))
    verify_manifest(tmp_path,manifest,['a'])
    (tmp_path/'a').write_text('changed')
    with pytest.raises(ValueError,match='integrity'):verify_manifest(tmp_path,manifest,['a'])


@pytest.mark.parametrize('path',['../outside','/etc/passwd'])
def test_external_paths_rejected(tmp_path,path):
    with pytest.raises(ValueError,match='relative'):safe_path(tmp_path,path)


def test_symlink_escape_rejected(tmp_path):
    (tmp_path/'outside').symlink_to(tmp_path.parent)
    with pytest.raises(ValueError,match='escapes'):safe_path(tmp_path,'outside/file')
