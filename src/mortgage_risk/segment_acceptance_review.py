"""Bounded acceptance-review milestone: quantify uncertainty around the frozen 2013Q1 final-test
segment results with a paired bootstrap over the SAME saved predictions and labels already
written by redevelopment_final_evaluation.py. This performs no refit, no recalibration, no new
scoring and no threshold change -- it rejoins the immutable predictions.parquet with the frozen
cohort's features.parquet purely to recover the segment labels (delinquency/FICO/LTV/occupancy/
purpose) used for grouping, cross-checks every point estimate against the frozen
final_evaluation_result.json segments (raising if any diverge), and reports a 95% bootstrap
interval around each segment's observed/expected ratio. The [0.8, 1.25] band already frozen for
the AGGREGATE calibration gate is shown alongside each segment purely as a reporting reference,
not as a new or retroactively-applied segment-level acceptance threshold.
"""
import json
import time
import uuid
from pathlib import Path
import duckdb
import numpy as np
from mortgage_risk.artifact_integrity import fingerprint

SEGMENT_FIELDS = ('delinquency', 'fico_band', 'ltv_band', 'occupancy', 'purpose')


def oe_direction(observed_expected):
    """O/E = observed defaults / expected defaults. Below 1 means fewer defaults happened than
    predicted, i.e. the model OVERPREDICTED (overstated) risk for that segment. Above 1 means
    more defaults happened than predicted, i.e. the model UNDERPREDICTED (understated) risk.
    This function exists so prose is generated from a checked classification rather than by
    hand -- a prior milestone's hand-written narrative reversed this direction in one place."""
    if observed_expected is None:
        return None
    if observed_expected < 1:
        return 'overprediction'
    if observed_expected > 1:
        return 'underprediction'
    return 'exact'


def ci_vs_band(ci, lower=0.8, upper=1.25):
    """Classify a 95% CI against a reference band, distinguishing an interval that lies entirely
    outside the band from one that merely has a point estimate outside it while the interval
    still overlaps the band. 'entirely_below'/'entirely_above' are the only two relationships
    that support a claim of separation with 95% confidence; 'overlaps_floor'/'overlaps_ceiling'
    mean the evidence does not establish that separation, even if the point estimate breaches
    the band."""
    if ci is None:
        return None
    lo, hi = ci
    if hi < lower:
        return 'entirely_below'
    if lo > upper:
        return 'entirely_above'
    if lo >= lower and hi <= upper:
        return 'entirely_within'
    if lo < lower and hi > upper:
        return 'spans_band'
    if lo < lower:
        return 'overlaps_floor'
    return 'overlaps_ceiling'


def bootstrap_oe(y_default, pd_hat, mask, seed, reps):
    n = int(mask.sum())
    if n == 0:
        return {'n': 0, 'observed': 0, 'expected': 0.0, 'observed_expected': None, 'oe_ci95': None}
    idx = np.nonzero(mask)[0]
    yy, pp = y_default[idx], pd_hat[idx]
    observed, expected = int(yy.sum()), float(pp.sum())
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(reps):
        w = rng.integers(0, n, n)
        e = pp[w].sum()
        samples.append(yy[w].sum() / e if e > 0 else np.nan)
    lo, hi = np.nanquantile(np.asarray(samples), [.025, .975]).tolist()
    return {
        'n': n, 'observed': observed, 'expected': round(expected, 2),
        'observed_expected': round(observed / expected, 4) if expected > 0 else None,
        'oe_ci95': [round(lo, 4), round(hi, 4)],
    }


def run(root, eval_dir, features_path, labels_path, seed=2026, reps=1000):
    root, eval_dir = Path(root).resolve(), Path(eval_dir).resolve()
    features_path, labels_path = Path(features_path).resolve(), Path(labels_path).resolve()
    start = time.perf_counter()
    frozen = json.loads((eval_dir / 'final_evaluation_result.json').read_text())
    if frozen['status'] != 'evaluated_not_promoted':
        raise ValueError('Unexpected frozen final-evaluation status')
    if fingerprint(features_path) != frozen['features_sha256'] or fingerprint(labels_path) != frozen['labels_sha256']:
        raise ValueError('Supplied features/labels do not match the frozen final-evaluation record')

    conn = duckdb.connect()
    conn.execute(f"CREATE VIEW preds AS SELECT * FROM read_parquet('{eval_dir / 'predictions.parquet'}')")
    conn.execute(
        f"CREATE VIEW feats AS SELECT loan_id, delinquency_months, borrower_fico, ltv, occupancy, purpose "
        f"FROM read_parquet('{features_path}')"
    )
    conn.execute(f"CREATE VIEW labels AS SELECT * FROM read_parquet('{labels_path}')")
    if conn.execute('SELECT count(*)-count(DISTINCT loan_id) FROM feats').fetchone()[0]:
        raise ValueError('Duplicate loan_id in the frozen features snapshot')

    rows = conn.execute(
        "SELECT p.loan_id, p.candidate_default, f.delinquency_months, f.borrower_fico, f.ltv, f.occupancy, f.purpose, l.outcome_12m "
        "FROM preds p JOIN feats f USING (loan_id) JOIN labels l USING (loan_id) "
        "WHERE l.outcome_12m IN ('default_proxy','payoff_or_maturity','observed_event_free_12m') ORDER BY p.loan_id"
    ).fetchall()
    if len(rows) != frozen['coverage']['known']:
        raise ValueError('Rejoined known-outcome row count does not match the frozen coverage record')

    pd_hat = np.array([r[1] for r in rows], dtype=float)
    delinq = np.array([r[2] for r in rows])
    fico = np.array([r[3] for r in rows], dtype=float)
    ltv = np.array([r[4] for r in rows], dtype=float)
    occupancy = np.array([r[5] if r[5] is not None else 'missing' for r in rows], dtype=str)
    purpose = np.array([r[6] if r[6] is not None else 'missing' for r in rows], dtype=str)
    y_default = np.array([1 if r[7] == 'default_proxy' else 0 for r in rows])

    groups = {
        'delinquency': np.array(['missing' if v is None else f'{int(v)}|N' for v in delinq]),
        'fico_band': np.array(['missing' if np.isnan(v) else '<660' if v < 660 else '660-719' if v < 720 else '720+' for v in fico]),
        'ltv_band': np.array(['missing' if np.isnan(v) else '<=80' if v <= 80 else '>80' for v in ltv]),
        'occupancy': occupancy,
        'purpose': purpose,
    }
    frozen_by_key = {(s['field'], s['value']): s['candidate'] for s in frozen['segments']}

    segments = []
    for field, values in groups.items():
        for value in sorted(set(values)):
            mask = values == value
            stat = bootstrap_oe(y_default, pd_hat, mask, seed, reps)
            key = (field, value)
            if key in frozen_by_key:
                fc = frozen_by_key[key]
                if fc['loans'] != stat['n'] or fc['defaults'] != stat['observed'] or abs(fc['expected_defaults'] - stat['expected']) > 0.02:
                    raise ValueError(f'Recomputed point estimate diverges from frozen record for {key}')
            segments.append({'field': field, 'value': value, **stat,
                              'within_frozen_aggregate_band_0.8_1.25': stat['observed_expected'] is not None and 0.8 <= stat['observed_expected'] <= 1.25,
                              'oe_direction': oe_direction(stat['observed_expected']),
                              'ci_vs_band_0.8_1.25': ci_vs_band(stat['oe_ci95']),
                              'insufficient_support': stat['observed'] < 20 or stat['n'] < 100})

    out = root / 'artifacts/runs/segment_acceptance_review' / uuid.uuid4().hex
    out.mkdir(parents=True)
    result = {
        'status': 'segment_uncertainty_quantified',
        'note': (
            'Reuses the saved 2013Q1 final-test predictions and labels only; no refit, no recalibration, '
            'no new scoring, no acceptance threshold changed or newly invented. The 0.8-1.25 band shown per '
            'segment is the SAME band already frozen for the AGGREGATE calibration gate; it was never formally '
            'prescribed as a segment-level acceptance gate, so it is shown here as a diagnostic reference only, '
            'not a retroactively-applied pass/fail rule. Each interval below is an independent per-segment 95% '
            'interval, not adjusted for multiple comparisons; it is not a simultaneous/family-wise guarantee '
            'across all segments reported. ci_vs_band_0.8_1.25 distinguishes an interval lying entirely outside '
            'the band (entirely_below/entirely_above, which supports separation at 95% confidence) from one that '
            'only has its point estimate outside the band while the interval still overlaps it '
            '(overlaps_floor/overlaps_ceiling/spans_band, which does not).'
        ),
        'source_final_evaluation_dir': str(eval_dir),
        'source_features_sha256': frozen['features_sha256'],
        'source_labels_sha256': frozen['labels_sha256'],
        'joined_known_outcome_rows': len(rows),
        'bootstrap_seed': seed, 'bootstrap_repeats': reps,
        'segments': segments,
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': time.perf_counter() - start,
    }
    (out / 'segment_acceptance_review_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    conn.close()
    print(json.dumps({'status': result['status'], 'result': str(out / 'segment_acceptance_review_result.json')}), flush=True)
    return result, out


if __name__ == '__main__':
    _root = Path(__file__).resolve().parents[2]
    run(
        _root,
        eval_dir=_root / 'artifacts/runs/redevelopment_final_evaluation/21a27da4febc4ebdbeba08698e5b18f1',
        features_path=_root / 'artifacts/runs/multi_cohort_adapter/c5816a430cb2484c9f6d9d90671bbee2/features.parquet',
        labels_path=_root / 'artifacts/runs/multi_cohort_adapter/c5816a430cb2484c9f6d9d90671bbee2/labels.parquet',
    )
