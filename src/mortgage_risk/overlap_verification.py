"""Supplemental, read-only evidence closing the full-cohort overlap gap identified in the
publication review (artifacts/runs/publication_review/): redevelopment_final_evaluation.py had
checked the 2013Q1 final-test population against only the 2012Q1 CALIBRATION cohort's
snapshot-eligible features.parquet, not its full loan population. This module reuses already
-persisted evidence wherever possible and performs no refit, no recalibration, no rescoring, and
no rerun of the frozen final evaluation -- it only rejoins loan-ID sets already on disk (plus the
one narrow loan_id_registry.py extraction of the full 2012Q1 population) to verify true
disjointness retroactively. If real overlap is ever found, `all_disjoint` is False and release
acceptance must stop pending impact assessment -- this module does not itself gate anything.
"""
import json
import time
import uuid
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint


def load_ids(conn, path, column='loan_id'):
    return set(r[0] for r in conn.execute(f"SELECT DISTINCT {column} FROM read_parquet('{str(path).replace(chr(39), chr(39) * 2)}')").fetchall())


def run(root, eval_dir, registry_2012q1, registry_2011q1, historical_2010q1, old_snapshot_2012q1):
    root = Path(root).resolve()
    eval_dir = Path(eval_dir).resolve()
    start = time.perf_counter()

    frozen = json.loads((eval_dir / 'final_evaluation_result.json').read_text())
    if frozen['status'] != 'evaluated_not_promoted':
        raise ValueError('Unexpected frozen final-evaluation status')

    # Locate the persisted 2013Q1 adapter output whose features.parquet hash matches the frozen
    # record -- reused unchanged, never rescanned or rescored.
    features_2013q1 = None
    for candidate in (root / 'artifacts/runs/multi_cohort_adapter').glob('*/features.parquet'):
        if fingerprint(candidate) == frozen['features_sha256']:
            features_2013q1 = candidate
            break
    if features_2013q1 is None:
        raise ValueError('Could not locate the frozen 2013Q1 features.parquet by hash; supplemental verification cannot proceed without it')

    conn = duckdb.connect()
    ids_2013q1 = load_ids(conn, features_2013q1)
    ids_2012q1_full = load_ids(conn, registry_2012q1)
    ids_2011q1_full = load_ids(conn, registry_2011q1)
    ids_2010q1_full = load_ids(conn, historical_2010q1)
    ids_2012q1_old_snapshot = load_ids(conn, old_snapshot_2012q1)
    conn.close()

    overlaps = {
        '2012Q1_full_vs_2013Q1': sorted(ids_2012q1_full & ids_2013q1),
        '2012Q1_full_vs_2011Q1_full': sorted(ids_2012q1_full & ids_2011q1_full),
        '2012Q1_full_vs_2010Q1_full': sorted(ids_2012q1_full & ids_2010q1_full),
    }
    all_disjoint = all(len(v) == 0 for v in overlaps.values())

    # Demonstrates the gap was real in principle: the old snapshot-eligible check target is
    # necessarily a strict subset of the full 2012Q1 registry, so any loan present in 2012Q1 but
    # excluded from its scoring snapshot was structurally unreachable by the pre-fix check.
    gap = {
        'old_snapshot_2012Q1_loan_count': len(ids_2012q1_old_snapshot),
        'full_2012Q1_loan_count': len(ids_2012q1_full),
        'loans_in_full_registry_but_not_old_snapshot': len(ids_2012q1_full - ids_2012q1_old_snapshot),
        'old_snapshot_is_subset_of_full_registry': ids_2012q1_old_snapshot <= ids_2012q1_full,
    }

    out = root / 'artifacts/runs/overlap_verification' / uuid.uuid4().hex
    out.mkdir(parents=True)
    result = {
        'status': 'pass_full_disjointness_confirmed' if all_disjoint else 'FAIL_OVERLAP_DETECTED_STOP_RELEASE',
        'all_disjoint': all_disjoint,
        'note': 'Supplemental, non-destructive evidence. Does not rerun, rescore or alter the frozen 2013Q1 final evaluation.',
        'overlap_counts': {k: len(v) for k, v in overlaps.items()},
        'overlapping_loan_ids': overlaps if not all_disjoint else 'none found',
        'gap_this_fix_closes': gap,
        'source_features_2013q1_path': str(features_2013q1.relative_to(root)),
        'source_features_2013q1_sha256': frozen['features_sha256'],
        'registry_2012q1_sha256': fingerprint(registry_2012q1),
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': time.perf_counter() - start,
    }
    (out / 'overlap_verification_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'status': result['status'], 'all_disjoint': all_disjoint, 'result': str(out / 'overlap_verification_result.json')}), flush=True)
    return result, out


if __name__ == '__main__':
    _root = Path(__file__).resolve().parents[2]
    run(
        _root,
        eval_dir=_root / 'artifacts/runs/redevelopment_final_evaluation/21a27da4febc4ebdbeba08698e5b18f1',
        registry_2012q1=_root / 'artifacts/runs/loan_id_registry/2012Q1_loan_ids.parquet',
        registry_2011q1=_root / 'artifacts/runs/loan_id_registry/2011Q1_loan_ids.parquet',
        historical_2010q1=_root / 'artifacts/runs/historical_ingest/fullquarter_replacement/7a30ef59b2e74c518133ddf5923c92c9/historical_monthly.parquet',
        old_snapshot_2012q1=_root / 'artifacts/runs/multi_cohort_adapter/88d9f8338a0f40889447b4308983e4ea/features.parquet',
    )
