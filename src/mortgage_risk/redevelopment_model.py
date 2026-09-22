"""Redevelopment Milestone: development-only model selection, frozen chronological design.
Trains on 2010Q1 development-split rows only (unchanged from the original challenger); selects
among the SAME fixed candidate grid using the full 2011Q1 population as a chronologically later,
out-of-cohort development-validation set, instead of 2010Q1's own same-cohort internal_validation
split. See configs/redevelopment_model.json for the frozen protocol and rationale. Does not read
2012Q1 (calibration) or 2013Q1 (final test). The original frozen challenger
(artifacts/runs/challenger/f94a630d661f4ea28f7a21c4a567c74c/) and its failed external evaluation
(artifacts/runs/external_evaluation/bb53b87c6a034af29614c2c5768b4b06/) are untouched and immutable.
"""
import json
import time
import uuid
import warnings
from collections import Counter
from pathlib import Path
import duckdb
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits
from mortgage_risk.artifact_integrity import fingerprint
from mortgage_risk.estimated_models import CLASSES, fit, predict
from mortgage_risk.challenger import fit_transformer, transform, feature_names, predict_export, evaluate


def load_population(conn, features_path, labels_path, view_prefix, split_filter=None):
    conn.execute(f"CREATE VIEW {view_prefix}_features AS SELECT * FROM read_parquet('{str(features_path)}')")
    conn.execute(f"CREATE VIEW {view_prefix}_labels AS SELECT * FROM read_parquet('{str(labels_path)}')")
    for name in ('features', 'labels'):
        table = f'{view_prefix}_{name}'
        if conn.execute(f'SELECT count(*)-count(DISTINCT (loan_id,reporting_month)) FROM {table}').fetchone()[0]:
            raise ValueError(f'Duplicate keys in {table}')
    for a, b in [('features', 'labels'), ('labels', 'features')]:
        if conn.execute(f'SELECT count(*) FROM {view_prefix}_{a} ANTI JOIN {view_prefix}_{b} USING(loan_id,reporting_month)').fetchone()[0]:
            raise ValueError(f'Unmatched label join in {view_prefix}')
    where = f"WHERE f.development_split='{split_filter}'" if split_filter else ''
    sql = (f"SELECT f.loan_id,f.borrower_fico,f.ltv,f.dti,f.original_term,"
           f"coalesce(cast(f.delinquency_months AS VARCHAR),'missing')||'|'||coalesce(f.modification_status,'unknown_not_reported') benchmark_group,"
           f"f.occupancy,f.purpose,l.outcome_12m "
           f"FROM {view_prefix}_features f JOIN {view_prefix}_labels l USING(loan_id,reporting_month) {where} ORDER BY f.loan_id")
    rows = conn.execute(sql).fetchall()
    known = [r for r in rows if r[-1] in CLASSES]
    numeric = np.array([[float(v) if v is not None else np.nan for v in r[1:5]] for r in known])
    categorical = np.array([r[5:-1] for r in known], dtype=str)
    y = np.array([CLASSES.index(r[-1]) for r in known])
    coverage = {'total': len(rows), 'known': len(known), 'unresolved': len(rows) - len(known)}
    return numeric, categorical, y, coverage, rows


def run(root):
    root = Path(root).resolve()
    start = time.perf_counter()
    cfg_path = root / 'configs/redevelopment_model.json'
    cfg = json.loads(cfg_path.read_text())
    out = root / 'artifacts/runs/redevelopment_model' / uuid.uuid4().hex
    out.mkdir(parents=True)
    (out / 'protocol.json').write_text(json.dumps(cfg, indent=2) + '\n')
    conn = duckdb.connect()
    conn.execute("SET memory_limit='2GB'")

    print('Loading 2010Q1 development-split rows (training) and full 2011Q1 (development-validation)', flush=True)
    dn, dc, dy, dev_coverage, _ = load_population(conn, root / cfg['training_features'], root / cfg['training_labels'], 'dev2010', split_filter='development')
    vn, vc, vy, val_coverage, val_rows = load_population(conn, root / cfg['development_validation_features'], root / cfg['development_validation_labels'], 'dev2011')
    if set(dy) != {0, 1, 2} or set(vy) != {0, 1, 2}:
        raise ValueError('Insufficient class support in one of the populations')

    seasoning = {
        '2010Q1_development': {'missing_fico': float(np.isnan(dn[:, 0]).mean()), 'missing_ltv': float(np.isnan(dn[:, 1]).mean()),
                                'missing_dti': float(np.isnan(dn[:, 2]).mean()), 'missing_term': float(np.isnan(dn[:, 3]).mean()),
                                'class_frequencies': {CLASSES[k]: int((dy == k).sum()) for k in range(3)}, 'n': len(dy)},
        '2011Q1_development_validation': {'missing_fico': float(np.isnan(vn[:, 0]).mean()), 'missing_ltv': float(np.isnan(vn[:, 1]).mean()),
                                           'missing_dti': float(np.isnan(vn[:, 2]).mean()), 'missing_term': float(np.isnan(vn[:, 3]).mean()),
                                           'class_frequencies': {CLASSES[k]: int((vy == k).sum()) for k in range(3)}, 'n': len(vy)},
        'note': 'Both snapshots are 12-month conditional outcomes; 2011Q1 is one calendar year later than 2010Q1 (Jan 2012 vs Jan 2011 snapshot), a known population/seasoning difference, not a defect.',
    }

    print('Fitting preprocessing on 2010Q1 development rows only', flush=True)
    state = fit_transformer(dn, dc, cfg['numeric_features'], cfg['categorical_features'])
    dx = transform(dn, dc, state)
    vx = transform(vn, vc, state)

    results, models, predictions = {}, {}, {}
    hist = [{'group_key': g, 'outcome': CLASSES[k], 'n': n} for (g, k), n in Counter(zip(dc[:, 0], dy)).items()]
    for alpha in [None] + cfg['benchmark_smoothing']:
        name = 'constant' if alpha is None else f'benchmark_{alpha}'
        model = fit(hist, alpha)
        probs = np.asarray([predict(model, g) for g in vc[:, 0]])
        models[name], predictions[name], results[name] = model, probs, evaluate(vy, probs)

    print('Fitting the fixed regularization grid on development rows; selecting by 2011Q1 log loss', flush=True)
    for strength in cfg['regularization_C']:
        model = LogisticRegression(C=strength, solver=cfg['solver'], max_iter=cfg['max_iterations'], tol=1e-7, random_state=cfg['seed'])
        with warnings.catch_warnings(), threadpool_limits(limits=2):
            warnings.simplefilter('error', ConvergenceWarning)
            model.fit(dx, dy)
        if list(model.classes_) != [0, 1, 2]:
            raise ValueError('Class ordering changed')
        name = f'logistic_{strength}'
        p = model.predict_proba(vx)
        export = {'classes': CLASSES, 'coefficients': model.coef_.tolist(), 'intercepts': model.intercept_.tolist(),
                  'feature_names': feature_names(state), 'preprocessing': state, 'iterations': model.n_iter_.tolist()}
        if np.max(np.abs(p - predict_export(vx, export))) > 1e-10:
            raise ValueError('Export parity failure')
        models[name], predictions[name], results[name] = export, p, evaluate(vy, p)

    selected = min(results, key=lambda k: (results[k]['log_loss'], k))
    best_logistic = min([k for k in results if k.startswith('logistic')], key=lambda k: results[k]['log_loss'])
    best_benchmark = min([k for k in results if not k.startswith('logistic')], key=lambda k: results[k]['log_loss'])

    diff = -np.log(np.clip(predictions[best_logistic][np.arange(len(vy)), vy], 1e-15, 1)) + np.log(np.clip(predictions[best_benchmark][np.arange(len(vy)), vy], 1e-15, 1))
    rng = np.random.default_rng(cfg['seed'])
    boot = [float(diff[rng.integers(0, len(diff), len(diff))].mean()) for _ in range(cfg['bootstrap_repeats'])]

    segments = []
    for group in sorted(set(vc[:, 0])):
        mask = vc[:, 0] == group
        segments.append({'group': group, 'metrics': evaluate(vy[mask], predictions[selected][mask]), 'support_warning': int((vy[mask] == 0).sum()) < 20})

    for name, model in models.items():
        (out / (name + '.json')).write_text(json.dumps(model, indent=2) + '\n')

    result = {
        'status': 'pass_for_development_selection',
        'selected': selected, 'best_logistic': best_logistic, 'best_benchmark': best_benchmark,
        'is_unchanged_from_original_challenger': best_logistic == 'logistic_1.0',
        'metrics': results, 'coverage': {'2010Q1_development_training': dev_coverage, '2011Q1_development_validation': val_coverage},
        'seasoning_and_population_differences': seasoning, 'segments': segments,
        'paired_log_loss_difference_logistic_vs_benchmark': {
            'mean': float(diff.mean()), 'interval95': np.quantile(boot, [.025, .975]).tolist(),
            'note': 'Fixed predictions, paired loan bootstrap on 2011Q1; ignores fitting/selection uncertainty.',
        },
        'input_sha256': {
            'training_features': fingerprint(root / cfg['training_features']), 'training_labels': fingerprint(root / cfg['training_labels']),
            'development_validation_features': fingerprint(root / cfg['development_validation_features']),
            'development_validation_labels': fingerprint(root / cfg['development_validation_labels']),
        },
        'protocol_sha256': fingerprint(cfg_path), 'implementation_sha256': fingerprint(__file__),
        'elapsed_seconds': time.perf_counter() - start,
        'limitations': [
            'Development-validation selection on 2011Q1 is not a fresh held-out test; 2011Q1 was previously used once as an external test (result immutable) and is now explicitly repurposed for development per the redevelopment plan.',
            'Conditional complete-case target; unresolved outcomes excluded from fitting/scoring with coverage reported.',
            'No calibration performed here; 2012Q1 and 2013Q1 not read by this step.',
            'Selecting the same regularization strength as before would reproduce, not validate, the original challenger; a different selection would be a genuinely new candidate requiring its own scrutiny.',
        ],
    }
    conn.close()
    (out / 'redevelopment_model_result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(json.dumps({'status': result['status'], 'selected': selected, 'result': str(out / 'redevelopment_model_result.json')}), flush=True)
    return result, out


if __name__ == '__main__':
    run(Path(__file__).resolve().parents[2])
