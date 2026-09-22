import json
import duckdb
import pytest
from mortgage_risk.overlap_verification import run


def write_ids(conn, path, ids):
    conn.execute("CREATE TABLE t(loan_id VARCHAR)")
    for i in ids:
        conn.execute("INSERT INTO t VALUES (?)", [i])
    conn.execute(f"COPY t TO '{path}' (FORMAT PARQUET)")
    conn.execute("DROP TABLE t")


def build_fixture(tmp_path, ids_2013q1, ids_2012q1_full, ids_2012q1_old_snapshot, ids_2011q1_full=(), ids_2010q1_full=()):
    conn = duckdb.connect()
    eval_dir = tmp_path / 'eval'
    eval_dir.mkdir()
    features_path = eval_dir / 'features.parquet'
    write_ids(conn, features_path, ids_2013q1)
    (eval_dir / 'final_evaluation_result.json').write_text(json.dumps({
        'status': 'evaluated_not_promoted',
        'features_sha256': __import__('mortgage_risk.artifact_integrity', fromlist=['fingerprint']).fingerprint(features_path),
    }))
    # place a copy under a multi_cohort_adapter-like directory so the hash-search glob finds it
    adapter_dir = tmp_path / 'artifacts/runs/multi_cohort_adapter/fakehex'
    adapter_dir.mkdir(parents=True)
    write_ids(conn, adapter_dir / 'features.parquet', ids_2013q1)

    reg_2012 = tmp_path / '2012_full.parquet'
    write_ids(conn, reg_2012, ids_2012q1_full)
    old_snapshot = tmp_path / '2012_old_snapshot.parquet'
    write_ids(conn, old_snapshot, ids_2012q1_old_snapshot)
    reg_2011 = tmp_path / '2011_full.parquet'
    write_ids(conn, reg_2011, ids_2011q1_full)
    hist_2010 = tmp_path / '2010_full.parquet'
    write_ids(conn, hist_2010, ids_2010q1_full)
    conn.close()
    return eval_dir, reg_2012, reg_2011, hist_2010, old_snapshot


def test_confirms_full_disjointness_when_none_exists(tmp_path):
    eval_dir, reg_2012, reg_2011, hist_2010, old_snapshot = build_fixture(
        tmp_path, ids_2013q1=['A', 'B'], ids_2012q1_full=['C', 'D'], ids_2012q1_old_snapshot=['C'],
    )
    result, out = run(tmp_path, eval_dir, reg_2012, reg_2011, hist_2010, old_snapshot)
    assert result['status'] == 'pass_full_disjointness_confirmed'
    assert result['all_disjoint'] is True
    assert (out / 'overlap_verification_result.json').exists()


def test_regression_catches_overlap_outside_old_snapshot_eligibility(tmp_path):
    # Loan 'X' is in the full 2012Q1 population AND in 2013Q1, but was NOT in the calibration
    # cohort's snapshot-eligible subset -- exactly the gap the publication review found: the old
    # buggy check (2012Q1_full pointed at the snapshot subset) would never have seen 'X' at all.
    eval_dir, reg_2012, reg_2011, hist_2010, old_snapshot = build_fixture(
        tmp_path,
        ids_2013q1=['X', 'B'],
        ids_2012q1_full=['X', 'C'],
        ids_2012q1_old_snapshot=['C'],  # 'X' deliberately excluded -- outside snapshot eligibility
    )
    result, out = run(tmp_path, eval_dir, reg_2012, reg_2011, hist_2010, old_snapshot)
    assert result['status'] == 'FAIL_OVERLAP_DETECTED_STOP_RELEASE'
    assert result['all_disjoint'] is False
    assert result['overlapping_loan_ids']['2012Q1_full_vs_2013Q1'] == ['X']
    # confirms the overlap would have been invisible to the pre-fix snapshot-only check
    gap = result['gap_this_fix_closes']
    assert gap['old_snapshot_is_subset_of_full_registry'] is True
    assert gap['loans_in_full_registry_but_not_old_snapshot'] == 1


def test_raises_if_frozen_features_cannot_be_located_by_hash(tmp_path):
    eval_dir, reg_2012, reg_2011, hist_2010, old_snapshot = build_fixture(
        tmp_path, ids_2013q1=['A'], ids_2012q1_full=['C'], ids_2012q1_old_snapshot=['C'],
    )
    # corrupt the recorded hash so it no longer matches any persisted features.parquet
    record = json.loads((eval_dir / 'final_evaluation_result.json').read_text())
    record['features_sha256'] = 'deadbeef' * 8
    (eval_dir / 'final_evaluation_result.json').write_text(json.dumps(record))
    with pytest.raises(ValueError, match='Could not locate'):
        run(tmp_path, eval_dir, reg_2012, reg_2011, hist_2010, old_snapshot)


def test_raises_on_unexpected_frozen_status(tmp_path):
    eval_dir, reg_2012, reg_2011, hist_2010, old_snapshot = build_fixture(
        tmp_path, ids_2013q1=['A'], ids_2012q1_full=['C'], ids_2012q1_old_snapshot=['C'],
    )
    record = json.loads((eval_dir / 'final_evaluation_result.json').read_text())
    record['status'] = 'something_else'
    (eval_dir / 'final_evaluation_result.json').write_text(json.dumps(record))
    with pytest.raises(ValueError, match='Unexpected frozen'):
        run(tmp_path, eval_dir, reg_2012, reg_2011, hist_2010, old_snapshot)
