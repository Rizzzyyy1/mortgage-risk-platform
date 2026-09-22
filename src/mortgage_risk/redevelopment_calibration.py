"""Redevelopment Milestone: calibrate the frozen development model on 2012Q1, its predefined
calibration role only. Builds the 2012Q1 cohort via multi_cohort_adapter.py, checked for
loan-ID disjointness against the FULL 2010Q1 and 2011Q1 populations (not just their snapshot-
feature subsets). Fits one pair of intercept offsets directly on 2012Q1's known outcomes (not
cross-fitted -- this cohort IS the calibration set, per its frozen role in
configs/multi_cohort_redevelopment.json) and accepts the adjustment only if it clears a tie
threshold FROZEN before any 2012Q1 label was read (configs/redevelopment_calibration.json).
Never reads 2013Q1. Preserves the frozen development-selection result unchanged.
"""
import json
import time
import uuid
from pathlib import Path
import duckdb
import numpy as np
from mortgage_risk.artifact_integrity import fingerprint
from mortgage_risk.estimated_models import CLASSES, predict
from mortgage_risk.challenger import transform, predict_export, evaluate
from mortgage_risk.calibration_remediation import adjust, fit_offsets
from mortgage_risk.multi_cohort_adapter import run as run_adapter


def run(root):
    root = Path(root).resolve()
    start = time.perf_counter()
    cfg_path = root / 'configs/redevelopment_calibration.json'
    cfg = json.loads(cfg_path.read_text())
    dev_model = json.loads((root / cfg['development_model_run']).read_text())
    if dev_model['status'] != 'pass_for_development_selection' or dev_model['selected'] != Path(cfg['development_model_candidate']).stem:
        raise ValueError('Frozen development-model run does not match the calibration protocol')

    out = root / 'artifacts/runs/redevelopment_calibration' / uuid.uuid4().hex
    out.mkdir(parents=True)
    (out / 'protocol.json').write_text(json.dumps(cfg, indent=2) + '\n')

    print('Building the 2012Q1 calibration cohort (its predefined role only)', flush=True)
    other_cohorts = {
        '2010Q1_full': root / 'artifacts/runs/historical_ingest/fullquarter_replacement/7a30ef59b2e74c518133ddf5923c92c9/historical_monthly.parquet',
        '2011Q1_full': root / 'artifacts/runs/loan_id_registry/2011Q1_loan_ids.parquet',
    }
    adapter_result, adapter_dir = run_adapter(
        root, cohort='2012Q1', source_relpath='data/raw/fannie_mae_loan_performance/2012Q1.csv',
        snapshot_date=cfg['snapshot_date'], outcome_end_date=cfg['outcome_end_date'],
        other_cohort_loan_id_parquets=other_cohorts, build_labels_now=True,
    )
    if adapter_result['status'] != 'pass_for_cohort_adapter':
        raise ValueError('2012Q1 adapter did not pass')

    candidate = json.loads((root / cfg['development_model_candidate']).read_text())
    benchmark = json.loads((root / cfg['development_model_benchmark']).read_text())
    state = candidate['preprocessing']
    conn = duckdb.connect()
    conn.execute(f"CREATE VIEW features AS SELECT * FROM read_parquet('{adapter_dir / 'features.parquet'}')")
    conn.execute(f"CREATE VIEW labels AS SELECT * FROM read_parquet('{adapter_dir / 'labels.parquet'}')")
    conn.execute(
        "CREATE VIEW scoring AS SELECT f.loan_id,f.borrower_fico,f.ltv,f.dti,f.original_term,"
        "coalesce(cast(f.delinquency_months AS VARCHAR),'missing')||'|'||coalesce(f.modification_status,'unknown_not_reported') benchmark_group,"
        "f.occupancy,f.purpose,l.outcome_12m FROM features f JOIN labels l USING(loan_id,reporting_month) ORDER BY f.loan_id"
    )
    rows = conn.execute('SELECT * FROM scoring').fetchall()
    known = [r for r in rows if r[-1] in CLASSES]
    coverage = {'total': len(rows), 'known': len(known), 'unresolved': len(rows) - len(known)}
    numeric = np.array([[float(v) if v is not None else np.nan for v in r[1:5]] for r in known])
    categorical = np.array([r[5:-1] for r in known], dtype=str)
    y = np.array([CLASSES.index(r[-1]) for r in known])
    observed_defaults = int((y == 0).sum())
    if observed_defaults < cfg['minimum_observed_defaults']:
        raise ValueError(f'Insufficient default support in 2012Q1: {observed_defaults} < {cfg["minimum_observed_defaults"]}')

    print(f'Scoring frozen candidate on {len(known)} known 2012Q1 outcomes ({observed_defaults} defaults)', flush=True)
    p = predict_export(transform(numeric, categorical, state), candidate)
    q_benchmark = np.asarray([predict(benchmark, g) for g in categorical[:, 0]])
    unchanged_metrics = evaluate(y, p)

    try:
        offsets = fit_offsets(p, y)
        if not np.isfinite(offsets).all():
            raise ValueError('Nonfinite calibration offsets')
        q = adjust(p, offsets)
        adjusted_metrics = evaluate(y, q)
        fit_status = 'converged'
    except Exception as e:
        offsets, q, adjusted_metrics, fit_status = None, None, None, f'rejected: {e}'

    if fit_status == 'converged':
        selected = 'adjusted' if adjusted_metrics['log_loss'] < unchanged_metrics['log_loss'] - cfg['log_loss_tie_threshold'] else 'unchanged'
    else:
        selected = 'unchanged'

    export = dict(candidate)
    if selected == 'adjusted':
        export['intercepts'] = (np.asarray(candidate['intercepts']) + np.r_[offsets, 0]).tolist()
        export['calibration_offsets'] = offsets.tolist()
        parity = float(np.max(np.abs(q - predict_export(transform(numeric, categorical, state), export))))
        if parity > 1e-10:
            raise ValueError('Calibrated export parity failure')
    else:
        parity = 0.0
    (out / 'frozen_evaluation_model.json').write_text(json.dumps(export, indent=2) + '\n')

    segments = []
    for field_idx, field in [(4, 'benchmark_group'), (5, 'occupancy'), (6, 'purpose')]:
        for value in sorted(set(categorical[:, field_idx - 4])):
            mask = categorical[:, field_idx - 4] == value
            defaults_n, loans_n = int((y[mask] == 0).sum()), int(mask.sum())
            segments.append({
                'field': field, 'value': value, 'loans': loans_n, 'defaults': defaults_n,
                'unchanged': evaluate(y[mask], p[mask]),
                'adjusted': evaluate(y[mask], q[mask]) if q is not None else None,
                'insufficient_support': defaults_n < cfg['segment_insufficient_support_defaults'] or loans_n < cfg['segment_insufficient_support_loans'],
            })

    result = {
        'status': 'pass_for_calibration',
        'cohort_adapter_result': adapter_result, 'cohort_adapter_dir': str(adapter_dir),
        'coverage': coverage, 'observed_defaults': observed_defaults,
        'unchanged_metrics': unchanged_metrics, 'adjusted_metrics': adjusted_metrics,
        'benchmark_metrics_for_reference': evaluate(y, q_benchmark),
        'calibration_fit_status': fit_status,
        'offsets': offsets.tolist() if offsets is not None else None,
        'selected': selected,
        'log_loss_improvement': (unchanged_metrics['log_loss'] - adjusted_metrics['log_loss']) if adjusted_metrics else None,
        'tie_threshold': cfg['log_loss_tie_threshold'],
        'export_parity_max_difference': parity,
        'segments': segments,
        'frozen_evaluation_model': str(out / 'frozen_evaluation_model.json'),
        'protocol_sha256': fingerprint(cfg_path),
        'candidate_sha256': fingerprint(root / cfg['development_model_candidate']),
        'benchmark_sha256': fingerprint(root / cfg['development_model_benchmark']),
        'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': time.perf_counter() - start,
        'limitations': [
            'This is a calibration-set fit on 2012Q1, not independent validation; only the one-time 2013Q1 final evaluation provides that.',
            'Intercept-only adjustment; no feature or hyperparameter search performed on 2012Q1.',
            'Sparse segments (see insufficient_support flags) are descriptive only, not separately adjusted.',
            'No promotion; the frozen_evaluation_model is used exactly once, for the 2013Q1 final evaluation, and nowhere else.',
        ],
    }
    conn.close()
    (out / 'redevelopment_calibration_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'status': 'pass_for_calibration', 'selected': selected, 'result': str(out / 'redevelopment_calibration_result.json')}), flush=True)
    return result, out


if __name__ == '__main__':
    run(Path(__file__).resolve().parents[2])
