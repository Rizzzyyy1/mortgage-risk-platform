from decimal import Decimal
import hashlib
import json
import pytest
from mortgage_risk.demo import build_demo


def test_vendor_free_demo_is_reproducible_and_reconciled(tmp_path):
    a, b = tmp_path/'first', tmp_path/'second'
    r = build_demo(a)
    build_demo(b)
    assert r['curve'][-1]['default_cif'] == pytest.approx(.1)
    assert r['curve'][-1]['payoff_or_maturity_cif'] == pytest.approx(.2)
    assert r['curve'][-1]['survival'] == pytest.approx(.7)
    assert Decimal(r['scenarios']['adverse']['remaining_life_expected_loss']) > Decimal(r['scenarios']['baseline']['remaining_life_expected_loss'])
    assert (a/'manifest.json').read_bytes() == (b/'manifest.json').read_bytes()
    for name, digest in json.loads((a/'manifest.json').read_text()).items():
        assert hashlib.sha256((a/name).read_bytes()).hexdigest() == digest


def test_demo_preserves_existing_directory(tmp_path):
    with pytest.raises(FileExistsError):
        build_demo(tmp_path)
