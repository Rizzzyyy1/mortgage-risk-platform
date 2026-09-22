"""Bounded development-only, cross-fitted multinomial intercept experiment."""
import hashlib
import json
import time
import uuid
import warnings
from pathlib import Path

import duckdb
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from mortgage_risk.artifact_integrity import fingerprint
from mortgage_risk.challenger import evaluate, fit_transformer, load_data, predict_export, transform
from mortgage_risk.estimated_models import CLASSES


def adjust(probabilities, offsets):
    p = np.asarray(probabilities, dtype=float)
    a = np.asarray(offsets, dtype=float)
    if p.ndim != 2 or p.shape[1] != 3 or a.shape != (2,) or not np.isfinite(a).all():
        raise ValueError('Invalid calibration shape or offsets')
    if not np.isfinite(p).all() or (p <= 0).any() or not np.allclose(p.sum(axis=1), 1, atol=1e-12, rtol=0):
        raise ValueError('Expected strictly positive normalized probabilities')
    scores = np.log(p) + np.r_[a, 0.0]
    return np.exp(scores - logsumexp(scores, axis=1, keepdims=True))


def fit_offsets(p, y):
    y = np.asarray(y)
    if len(y) != len(p) or set(y) != {0, 1, 2}:
        raise ValueError('Three-class calibration support required')
    def objective(a):
        q = adjust(p, a)
        loss = -np.log(q[np.arange(len(y)), y]).mean()
        gradient = (q - np.eye(3)[y]).mean(axis=0)[:2]
        return loss, gradient
    result = minimize(objective, np.zeros(2), jac=True, method='BFGS', options={'gtol': 1e-9, 'maxiter': 300})
    if not result.success or not np.isfinite(result.fun):
        raise ValueError('Calibration did not converge: ' + str(result.message))
    return result.x


def fold_ids(ids, count=5):
    return np.array([int(hashlib.sha256(str(x).encode()).hexdigest(), 16) % count for x in ids])


def run(root):
    start = time.perf_counter()
    cfg_path = root / 'configs/calibration_remediation.json'
    cfg = json.loads(cfg_path.read_text())
    base_cfg = json.loads((root / 'configs/challenger.json').read_text())
    out = root / 'artifacts/runs/calibration_remediation' / uuid.uuid4().hex
    out.mkdir(parents=True)
    (out / 'protocol.json').write_text(json.dumps(cfg, indent=2) + '\n')
    con = duckdb.connect()
    load_data(con, root / cfg['development_features'], root / cfg['development_labels'])
    names, cats = base_cfg['numeric_features'], base_cfg['categorical_features']
    data, coverage = {}, {}
    for split in ['development', 'internal_validation']:
        rows = con.execute('SELECT loan_id,' + ','.join(names + cats) + ',outcome_12m FROM joined WHERE development_split=? ORDER BY loan_id', [split]).fetchall()
        known = [r for r in rows if r[-1] in CLASSES]
        coverage[split] = {'total': len(rows), 'known': len(known), 'unresolved': len(rows)-len(known)}
        data[split] = ([r[0] for r in known], np.array([[np.nan if v is None else float(v) for v in r[1:5]] for r in known]), np.array([r[5:-1] for r in known], dtype=str), np.array([CLASSES.index(r[-1]) for r in known]))
    ids, numeric, categorical, y = data['development']
    if len(set(ids)) != len(ids):
        raise ValueError('Expected one development snapshot per loan')
    folds = fold_ids(ids, cfg['crossfit_folds'])
    oof = np.full((len(y), 3), np.nan)
    fold_evidence = []
    for k in range(cfg['crossfit_folds']):
        train, hold = folds != k, folds == k
        state = fit_transformer(numeric[train], categorical[train], names, cats)
        model = LogisticRegression(C=1.0, solver='newton-cholesky', max_iter=1000, tol=1e-7, random_state=2026)
        with warnings.catch_warnings(), threadpool_limits(limits=2):
            warnings.simplefilter('error', ConvergenceWarning)
            model.fit(transform(numeric[train], categorical[train], state), y[train])
        if list(model.classes_) != [0, 1, 2]:
            raise ValueError('Fold class order changed')
        oof[hold] = model.predict_proba(transform(numeric[hold], categorical[hold], state))
        fold_evidence.append({'fold': k, 'fit_rows': int(train.sum()), 'held_rows': int(hold.sum()), 'iterations': model.n_iter_.tolist()})
    offsets = fit_offsets(oof, y)
    base_path = root / cfg['acceptance']['candidate']
    base = json.loads(base_path.read_text())
    vids, vn, vc, vy = data['internal_validation']
    p = predict_export(transform(vn, vc, base['preprocessing']), base)
    q = adjust(p, offsets)
    metrics = {'unchanged': evaluate(vy, p), 'adjusted': evaluate(vy, q)}
    selected = 'adjusted' if metrics['adjusted']['log_loss'] < metrics['unchanged']['log_loss'] - 1e-6 else 'unchanged'
    segments = [{'group': g, 'unchanged': evaluate(vy[vc[:, 0] == g], p[vc[:, 0] == g]), 'adjusted': evaluate(vy[vc[:, 0] == g], q[vc[:, 0] == g])} for g in sorted(set(vc[:, 0]))]
    export = dict(base)
    export['intercepts'] = (np.asarray(base['intercepts']) + np.r_[offsets, 0]).tolist()
    parity = float(np.max(np.abs(q-predict_export(transform(vn, vc, base['preprocessing']), export))))
    if parity > 1e-12:
        raise ValueError('Adjusted export parity failed')
    (out / 'adjusted_candidate.json').write_text(json.dumps(export, indent=2)+'\n')
    result = {'status': 'exploratory_experiment_complete', 'selected': selected, 'metrics': metrics, 'segments': segments, 'offsets': offsets.tolist(), 'coverage': coverage, 'folds': fold_evidence, 'export_max_difference': parity, 'oof_before': evaluate(y, oof), 'oof_after': evaluate(y, adjust(oof, offsets)), 'input_hashes': {str(path.relative_to(root)): fingerprint(path) for path in [cfg_path, base_path, root/cfg['development_features'], root/cfg['development_labels']]}, 'implementation_sha256': fingerprint(__file__), 'elapsed_seconds': time.perf_counter()-start, 'promoted': False, 'limitations': ['Internal validation previously used for model selection; exploratory only.', 'OOF calibration fit metrics are in-sample for offsets, not validation.', 'No external outcome file read. Prior external failure is unchanged.', 'New independent evaluation is required; no claim of corrected external calibration.']}
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    con.close()
    print(out, flush=True)


if __name__ == '__main__':
    run(Path(__file__).resolve().parents[2])
