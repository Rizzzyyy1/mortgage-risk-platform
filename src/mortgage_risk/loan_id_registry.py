"""Extracts a full, cohort-wide distinct loan-ID registry from a raw historical quarterly CSV via
one bounded, single-column scan -- used to verify TRUE cross-cohort loan-ID disjointness without
re-ingesting or reprocessing the full loan-month panel (no balance bridges, no event/outcome
construction). This exists because redevelopment_final_evaluation.py previously passed the
2012Q1 CALIBRATION cohort's snapshot-eligible feature subset as if it were the full 2012Q1
population when checking 2013Q1 disjointness -- a loan present in 2012Q1 but excluded from that
snapshot (e.g. failing an eligibility check) would never have been checked. This module builds
the genuinely full registry so that gap can be closed with supplemental, non-destructive evidence
(see overlap_verification.py) without rerunning or regenerating the frozen final evaluation.
"""
import json
import time
from pathlib import Path
import duckdb
from mortgage_risk.artifact_integrity import fingerprint

RAW_COLUMNS = 113


def build(root, cohort, source_relpath):
    root = Path(root).resolve()
    source = root / source_relpath
    if not source.exists():
        raise ValueError(f'Source file not found: {source}')
    start = time.perf_counter()

    conn = duckdb.connect()
    conn.read_csv(str(source), header=False, sep='|', columns={f'c{i}': 'VARCHAR' for i in range(RAW_COLUMNS)},
                  quotechar='', escapechar='', parallel=False).create_view('raw')
    conn.execute("CREATE TABLE ids AS SELECT DISTINCT c1 loan_id FROM raw")
    invalid = conn.execute(
        "SELECT count(*) FROM ids WHERE loan_id IS NULL OR NOT regexp_full_match(loan_id,'[0-9]{12}')"
    ).fetchone()[0]
    if invalid:
        raise ValueError(f'{invalid} invalid loan_id value(s) in {cohort} raw scan')
    total = conn.execute('SELECT count(*) FROM ids').fetchone()[0]

    out_dir = root / 'artifacts/runs/loan_id_registry'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{cohort}_loan_ids.parquet'
    conn.execute(f"COPY ids TO '{str(out_path).replace(chr(39), chr(39) * 2)}' (FORMAT PARQUET)")
    conn.close()

    result = {
        'status': 'pass_for_loan_id_registry',
        'cohort': cohort,
        'source_relpath': source_relpath,
        'source_sha256': fingerprint(source),
        'distinct_loan_count': total,
        'output_path': str(out_path.relative_to(root)),
        'output_sha256': fingerprint(out_path),
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': time.perf_counter() - start,
    }
    (out_dir / f'{cohort}_loan_ids.receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'cohort': cohort, 'distinct_loan_count': total,
                       'output': str(out_path)}), flush=True)
    return result


if __name__ == '__main__':
    _root = Path(__file__).resolve().parents[2]
    build(_root, cohort='2012Q1', source_relpath='data/raw/fannie_mae_loan_performance/2012Q1.csv')
