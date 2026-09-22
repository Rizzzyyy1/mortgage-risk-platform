"""Redevelopment Milestone: the ONE final evaluation, on 2013Q1, after the model and calibration
are fully frozen. Builds 2013Q1 features AND labels together in this single step -- by
construction, no earlier step in this redevelopment (multi_cohort_adapter for 2012Q1,
redevelopment_model, redevelopment_calibration) ever imports this module or reads 2013Q1, so the
outcome-blindness restriction is structural, not just a convention. Reuses external_evaluate.py's
exact statistical functions (calibration_diagnostics, auc_bins, weighted_auc, comparison_gates)
unchanged, applied to the frozen redevelopment model against the SAME quantitative gates already
frozen for the original (failed) 2011Q1 evaluation -- see configs/redevelopment_final_evaluation.json.
No refit, no recalibration, no repeated tuning against this result.
"""
import json
import time
import uuid
from pathlib import Path
import duckdb
import numpy as np
from threadpoolctl import threadpool_limits
from mortgage_risk.artifact_integrity import fingerprint
from mortgage_risk.estimated_models import CLASSES, predict
from mortgage_risk.challenger import transform, predict_export, evaluate
from mortgage_risk.external_evaluate import calibration_diagnostics, auc_bins, weighted_auc, comparison_gates
from mortgage_risk.multi_cohort_adapter import run as run_adapter


def run(root):
    root = Path(root).resolve()
    start = time.perf_counter()
    cfg_path = root / 'configs/redevelopment_final_evaluation.json'
    cfg = json.loads(cfg_path.read_text())
    calibration_result = json.loads((root / cfg['calibration_result']).read_text())
    if calibration_result['status'] != 'pass_for_calibration':
        raise ValueError('Frozen calibration run not accepted')

    out = root / 'artifacts/runs/redevelopment_final_evaluation' / uuid.uuid4().hex
    out.mkdir(parents=True)
    (out / 'protocol.json').write_text(json.dumps(cfg, indent=2) + '\n')

    print('Building the 2013Q1 final-test cohort: features AND labels together, only now that the model and calibration are frozen', flush=True)
    other_cohorts = {
        '2010Q1_full': root / 'artifacts/runs/historical_ingest/fullquarter_replacement/7a30ef59b2e74c518133ddf5923c92c9/historical_monthly.parquet',
        '2011Q1_full': root / 'artifacts/runs/loan_id_registry/2011Q1_loan_ids.parquet',
        '2012Q1_full': Path(calibration_result['cohort_adapter_dir']) / 'features.parquet',
    }
    adapter_result, adapter_dir = run_adapter(
        root, cohort='2013Q1', source_relpath='data/raw/fannie_mae_loan_performance/2013Q1.csv',
        snapshot_date=cfg['snapshot_date'], outcome_end_date=cfg['outcome_end_date'],
        other_cohort_loan_id_parquets=other_cohorts, build_labels_now=True,
    )
    if adapter_result['status'] != 'pass_for_cohort_adapter':
        raise ValueError('2013Q1 adapter did not pass')

    candidate = json.loads((root / cfg['frozen_evaluation_model']).read_text())
    benchmark = json.loads((root / cfg['benchmark']).read_text())
    state = candidate['preprocessing']
    if candidate['classes'] != CLASSES or benchmark['classes'] != CLASSES:
        raise ValueError('Class ordering mismatch')

    conn = duckdb.connect()
    conn.execute(f"CREATE VIEW features AS SELECT * FROM read_parquet('{adapter_dir / 'features.parquet'}')")
    conn.execute(f"CREATE VIEW labels AS SELECT * FROM read_parquet('{adapter_dir / 'labels.parquet'}')")
    for table in ('features', 'labels'):
        if conn.execute(f'SELECT count(*)-count(DISTINCT (loan_id,reporting_month)) FROM {table}').fetchone()[0]:
            raise ValueError('Duplicate keys')
    for a, b in [('features', 'labels'), ('labels', 'features')]:
        if conn.execute(f'SELECT count(*) FROM {a} ANTI JOIN {b} USING(loan_id,reporting_month)').fetchone()[0]:
            raise ValueError('Unmatched labels')
    total = conn.execute('SELECT count(*) FROM features').fetchone()[0]
    if total > 2000000:
        raise ValueError('Snapshot exceeds bounded in-memory scoring design')
    conn.execute(
        "CREATE VIEW scoring AS SELECT f.*,coalesce(cast(delinquency_months AS VARCHAR),'missing')||'|'||coalesce(modification_status,'unknown_not_reported') benchmark_group FROM features f"
    )
    names = state['numeric_names']
    cats = state['category_names']
    raw = conn.execute('SELECT loan_id,' + ','.join(names + cats) + ' FROM scoring ORDER BY loan_id').fetchall()
    numeric = np.array([[float(v) if v is not None else np.nan for v in r[1:1 + len(names)]] for r in raw])
    categorical = np.array([r[1 + len(names):] for r in raw], dtype=str)

    print(f'Scoring {total} eligible 2013Q1 loans once, with frozen coefficients and frozen calibration', flush=True)
    with threadpool_limits(limits=2):
        p = predict_export(transform(numeric, categorical, state), candidate)
    q = np.asarray([predict(benchmark, g) for g in categorical[:, 0]])

    labels = conn.execute('SELECT loan_id,outcome_12m FROM labels ORDER BY loan_id').fetchall()
    if [r[0] for r in raw] != [r[0] for r in labels]:
        raise ValueError('Scoring order mismatch')
    mask = np.array([r[1] in CLASSES for r in labels])
    y = np.array([CLASSES.index(r[1]) for r in labels if r[1] in CLASSES])
    ap, bp = p[mask], q[mask]
    metrics = {'candidate': evaluate(y, ap), 'benchmark': evaluate(y, bp)}
    diagnostic = calibration_diagnostics(y == 0, ap[:, 0])

    loss_diff = -np.log(np.clip(ap[np.arange(len(y)), y], 1e-15, 1)) + np.log(np.clip(bp[np.arange(len(y)), y], 1e-15, 1))
    brier_diff = np.sum((ap - np.eye(3)[y]) ** 2, axis=1) - np.sum((bp - np.eye(3)[y]) ** 2, axis=1)
    aa, bb = auc_bins(y, ap[:, 0]), auc_bins(y, bp[:, 0])
    rng = np.random.default_rng(cfg['seed'])
    samples = []
    print('Computing fixed paired bootstrap comparisons; no selection or recalibration', flush=True)
    with threadpool_limits(limits=2):
        for _ in range(cfg['bootstrap_repeats']):
            w = np.bincount(rng.integers(0, len(y), len(y)), minlength=len(y))
            samples.append([float(w @ loss_diff / len(y)), float(w @ brier_diff / len(y)), weighted_auc(aa, w) - weighted_auc(bb, w)])
    intervals = {name: np.nanquantile(np.asarray(samples)[:, i], [.025, .975]).tolist() for i, name in enumerate(['log_loss', 'brier', 'auc'])}

    segments = []
    groups = {
        'delinquency': categorical[mask, 0], 'occupancy': categorical[mask, 1], 'purpose': categorical[mask, 2],
        'fico_band': np.array(['missing' if np.isnan(v) else '<660' if v < 660 else '660-719' if v < 720 else '720+' for v in numeric[mask, 0]]),
        'ltv_band': np.array(['missing' if np.isnan(v) else '<=80' if v <= 80 else '>80' for v in numeric[mask, 1]]),
    }
    for field, values in groups.items():
        for value in sorted(set(values)):
            m = values == value
            segments.append({'field': field, 'value': value, 'candidate': evaluate(y[m], ap[m]), 'benchmark': evaluate(y[m], bp[m]),
                              'insufficient_support': int((y[m] == 0).sum()) < 20 or int(m.sum()) < 100})

    drift = {
        'numeric': {name: {'missing_fraction': float(np.isnan(numeric[:, i]).mean()), 'observed_mean': float(np.nanmean(numeric[:, i])),
                            'development_imputed_mean': state['means'][i], 'mean_shift_in_development_sd': float((np.nanmean(numeric[:, i]) - state['means'][i]) / state['scales'][i])}
                    for i, name in enumerate(names)},
        'unseen_categories': {name: int((~np.isin(categorical[:, i], state['categories'][i])).sum()) for i, name in enumerate(cats)},
        'note': 'All eligible 2013Q1 covariates; development reference uses frozen known-outcome preprocessing.',
    }
    with (out / 'predictions.csv').open('w', newline='') as f:
        import csv
        writer = csv.writer(f)
        writer.writerow(['loan_id', 'candidate_default', 'candidate_payoff', 'candidate_event_free', 'benchmark_default', 'benchmark_payoff', 'benchmark_event_free'])
        writer.writerows((r[0], *a, *b) for r, a, b in zip(raw, p, q))
    conn.read_csv(str(out / 'predictions.csv'), header=True, all_varchar=False).create_view('saved_predictions')
    conn.execute('COPY saved_predictions TO ? (FORMAT PARQUET)', [str(out / 'predictions.parquet')])

    unresolved = total - len(y)
    gates = comparison_gates(cfg, metrics, unresolved, total, intervals)
    result = {
        'status': 'evaluated_not_promoted',
        'quantitative_gates': gates, 'all_quantitative_gates_pass': all(gates.values()),
        'metrics': metrics, 'calibration_diagnostics': diagnostic, 'paired_difference_intervals95': intervals,
        'coverage': {'total': total, 'known': len(y), 'unresolved': unresolved,
                     'default_rate_bounds': [int((y == 0).sum()) / total, (int((y == 0).sum()) + unresolved) / total]},
        'segments': segments, 'drift': drift,
        'protocol_sha256': fingerprint(cfg_path),
        'candidate_sha256': fingerprint(root / cfg['frozen_evaluation_model']),
        'benchmark_sha256': fingerprint(root / cfg['benchmark']),
        'features_sha256': fingerprint(adapter_dir / 'features.parquet'),
        'labels_sha256': fingerprint(adapter_dir / 'labels.parquet'),
        'calibration_result_sha256': fingerprint(root / cfg['calibration_result']),
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': time.perf_counter() - start,
        'model_promoted': False,
        'limitations': [
            'Single untouched final-test cohort; no broader cycle/economic coverage claim.',
            'Conditional complete-case outcome; censoring bounds reported.',
            'Calibration diagnostic here is diagnostic only and never applied to predictions.',
            'Bootstrap conditional on the frozen model; does not include development/calibration/model-selection uncertainty.',
            'Segment support and deterioration require review even if quantitative gates pass.',
            'This is the definitive, one-time use of 2013Q1 for this model; no refit or repeated tuning against this result is permitted.',
        ],
    }
    conn.close()
    (out / 'final_evaluation_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'status': 'evaluated_not_promoted', 'all_quantitative_gates_pass': result['all_quantitative_gates_pass'], 'result': str(out / 'final_evaluation_result.json')}), flush=True)
    return result, out


if __name__ == '__main__':
    run(Path(__file__).resolve().parents[2])
