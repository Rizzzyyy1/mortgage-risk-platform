"""Phase4B: interpretable smoothed categorical multinomial benchmark."""
import json,math,hashlib,time,uuid,random
from collections import Counter,defaultdict
from pathlib import Path
import duckdb
CLASSES=['default_proxy','payoff_or_maturity','observed_event_free_12m']


def fit(hist,alpha=None):
    counts=[0,0,0];groups={}
    for row in hist:
        if row['outcome'] not in CLASSES:continue
        k=CLASSES.index(row['outcome']);n=row['n'];counts[k]+=n
        groups.setdefault(row['group_key'],[0,0,0])[k]+=n
    total=sum(counts)
    if not total or (alpha is not None and (not math.isfinite(alpha) or alpha<=0)):raise ValueError('Invalid fit data or smoothing')
    prior=[(n+.5)/(total+1.5) for n in counts]
    probabilities={} if alpha is None else {g:[(n+alpha*p)/(sum(ns)+alpha) for n,p in zip(ns,prior)] for g,ns in groups.items()}
    return dict(kind='constant' if alpha is None else 'smoothed_risk_table',alpha=alpha,classes=CLASSES,prior=prior,groups=probabilities,training_known_count=total)


def predict(model,key):
    return model['groups'].get(key,model['prior'])


def metrics(rows):
    # Rows are grouped counts at exact predicted probabilities, never millions of Python records.
    n=sum(x['n'] for x in rows)
    if n==0:raise ValueError('No evaluable outcomes')
    logloss=brier=expected=0.;observed=0;curve=defaultdict(lambda:[0,0])
    for row in rows:
        probs=row['probs'];k=CLASSES.index(row['outcome']);count=row['n']
        if any(not math.isfinite(p) or p<=0 or p>=1 for p in probs) or abs(sum(probs)-1)>1e-12:raise ValueError('Invalid predicted probabilities')
        logloss-=count*math.log(probs[k]);brier+=count*sum((p-(j==k))**2 for j,p in enumerate(probs))
        expected+=count*probs[0];observed+=count*(k==0)
        curve[probs[0]][0]+=count*(k==0);curve[probs[0]][1]+=count*(k!=0)
    neg=n-observed;below=u=0.
    calibration=[]
    for score,(pos,negative) in sorted(curve.items()):
        u+=pos*(below+.5*negative);below+=negative
        calibration.append(dict(predicted_default=score,observed_default=pos/(pos+negative),loans=pos+negative,defaults=pos))
    return dict(loans=n,defaults=observed,multiclass_log_loss=logloss/n,multiclass_brier=brier/n,
      default_auc=u/(observed*neg) if observed and neg else None,expected_defaults=expected,
      observed_expected_default_ratio=observed/expected,calibration=calibration)


def auc_bootstrap(rows,repeats=200,seed=2026):
    rng=random.Random(seed);bins=defaultdict(lambda:[0,0])
    for r in rows:bins[r['probs'][0]][r['outcome']!='default_proxy']+=r['n']
    scores=sorted(bins);pos=[bins[s][0] for s in scores];neg=[bins[s][1] for s in scores];np=sum(pos);nn=sum(neg)
    if not np or not nn:return None
    values=[]
    for _ in range(repeats):
        a=Counter(rng.choices(range(len(scores)),weights=pos,k=np));b=Counter(rng.choices(range(len(scores)),weights=neg,k=nn));below=u=0
        for j in range(len(scores)):u+=a[j]*(below+.5*b[j]);below+=b[j]
        values.append(u/(np*nn))
    values.sort()
    return dict(lower=values[int(.025*(repeats-1))],upper=values[int(.975*(repeats-1))],repeats=repeats,seed=seed,method='stratified fixed-score percentile bootstrap; conditional on observed class counts, no model refitting')


def run(root,config):
    root=Path(root).resolve();cfg=json.loads(Path(config).read_text());start=time.perf_counter();inp=root/cfg['input_run']
    design=json.loads((inp/'design_result.json').read_text())
    if design['status']!='pass':raise ValueError('Unaccepted feature design')
    out=root/'artifacts/runs/phase4b'/uuid.uuid4().hex;out.mkdir(parents=True)
    c=duckdb.connect(str(out/'model_checks.db'));c.execute("SET memory_limit='1GB'")
    def lit(p):return str(p).replace("'","''")
    def query(sql):
        cur=c.execute(sql);names=[x[0] for x in cur.description];return [dict(zip(names,row)) for row in cur.fetchall()]
    def load(split):
        c.execute(f"CREATE VIEW {split}_features AS SELECT * FROM read_parquet('{lit(inp/(split+'_features.parquet'))}')")
        c.execute(f"CREATE VIEW {split}_labels AS SELECT * FROM read_parquet('{lit(inp/(split+'_labels.parquet'))}')")
        nf=c.execute(f'SELECT count(*) FROM {split}_features').fetchone()[0];nl=c.execute(f'SELECT count(*) FROM {split}_labels').fetchone()[0]
        for suffix in ('features','labels'):
            if c.execute(f'SELECT count(*)-count(distinct loan_id) FROM {split}_{suffix}').fetchone()[0]:raise ValueError('Duplicate input keys')
        c.execute(f"CREATE VIEW {split}_joined AS SELECT f.loan_id,f.reporting_month,coalesce(cast(f.delinquency_months AS VARCHAR),'missing')||'|'||coalesce(f.modification_status,'unknown_not_reported') group_key,l.outcome_12m outcome FROM {split}_features f JOIN {split}_labels l USING(loan_id,reporting_month)")
        if nf!=nl or c.execute(f'SELECT count(*) FROM {split}_joined').fetchone()[0]!=nf:raise ValueError('Feature/label join mismatch')
        return query(f'SELECT group_key,outcome,count(*) n FROM {split}_joined GROUP BY 1,2 ORDER BY 1,2')
    def evaluated(hist,model):
        return [dict(probs=predict(model,x['group_key']),outcome=x['outcome'],n=x['n']) for x in hist if x['outcome'] in CLASSES]
    print('Fitting training-only frequency models and selecting on validation log loss',flush=True)
    training=load('train');validation=load('validation')
    models={'constant':fit(training)}
    for a in cfg['smoothing_strengths']:models[f'smoothed_{a}']=fit(training,a)
    validation_metrics={name:metrics(evaluated(validation,m)) for name,m in models.items()}
    selected=min(models,key=lambda name:(validation_metrics[name]['multiclass_log_loss'],name))
    # Selection is frozen on disk before test labels or predictions are loaded.
    (out/'selection.json').write_text(json.dumps(dict(primary_metric='validation multiclass log loss',selected=selected,validation_metrics=validation_metrics),indent=2))
    (out/'selected_model.json').write_text(json.dumps(models[selected],indent=2))
    print('Selected model frozen; evaluating test once alongside the constant reference',flush=True)
    test=load('test');test_metrics={}
    for name in dict.fromkeys([selected,'constant']):
        rows=evaluated(test,models[name]);test_metrics[name]=metrics(rows);test_metrics[name]['default_auc_interval']=auc_bootstrap(rows,cfg['bootstrap_repeats'],cfg['seed'])
    censoring={}
    for split,hist in [('train',training),('validation',validation),('test',test)]:
        n=sum(x['n'] for x in hist);d=sum(x['n'] for x in hist if x['outcome']=='default_proxy');u=sum(x['n'] for x in hist if x['outcome'] not in CLASSES)
        censoring[split]=dict(total=n,known=n-u,censored_or_unresolved=u,default_rate_lower=d/n,default_rate_upper=(d+u)/n)
    segments=[]
    for group in sorted({x['group_key'] for x in test}):
        h=[x for x in test if x['group_key']==group and x['outcome'] in CLASSES]
        if h:segments.append(dict(group_key=group,**metrics(evaluated(h,models[selected]))))
    # Save predictions separately from model features. All rows, including unresolved, are retained.
    c.execute('CREATE TABLE probabilities(group_key VARCHAR,p_default DOUBLE,p_payoff_maturity DOUBLE,p_event_free DOUBLE)')
    keys=sorted({x['group_key'] for x in test});c.executemany('INSERT INTO probabilities VALUES (?,?,?,?)',[(key,*predict(models[selected],key)) for key in keys])
    c.execute(f"COPY (SELECT j.*,p.* EXCLUDE(group_key) FROM test_joined j JOIN probabilities p USING(group_key)) TO '{lit(out/'test_predictions.parquet')}' (FORMAT PARQUET)")
    shift=[dict(group_key=g,train=sum(x['n'] for x in training if x['group_key']==g),validation=sum(x['n'] for x in validation if x['group_key']==g),test=sum(x['n'] for x in test if x['group_key']==g)) for g in sorted({x['group_key'] for x in training+validation+test})]
    result=dict(phase='4B',status='pass',input_run=str(inp),selected_model=selected,validation_metrics=validation_metrics,test_metrics=test_metrics,
      censoring_sensitivity=censoring,test_segments=segments,feature_group_shift=shift,config=cfg,
      predictors=['delinquency_months','modification_status'],unused_design_features=['loan_age_months','original_balance','eligible_reported_balance'],
      elapsed_seconds=round(time.perf_counter()-start,3),implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      config_sha256=hashlib.sha256(Path(config).read_bytes()).hexdigest(),output_directory=str(out),
      limitations=['Complete-case conditional-outcome benchmark: unresolved outcomes excluded explicitly from fitting/scoring, never relabeled; prevalence sensitivity bounds reported. Missing-at-random is not established.',
      'One acquisition vintage; calendar/seasoning and observed population shifts remain. Test is a later snapshot of different loans, not a new origination vintage.',
      'No macro covariates, true prepayment separation, estimated severity or actual-cohort loss model. Numeric features unused in this initial categorical benchmark.',
      'No threshold or recalibration tuned on test. Calibration may fail even with useful ranking; do not equate an engineering pass with deployment readiness.'])
    c.close();(out/'model_result.json').write_text(json.dumps(result,indent=2))
    (out/'all_training_models.json').write_text(json.dumps(models,indent=2))
    lines=['# Phase 4B estimated benchmark','',f'Selected on validation multiclass log loss: **{selected}**. Selection saved before test loading.','','| Test model | Default AUC | Multiclass log loss | Brier (sum across 3 classes) | Observed / expected defaults |','|---|---:|---:|---:|---:|']
    lines += [f"| {name} | {m['default_auc']:.4f} | {m['multiclass_log_loss']:.6f} | {m['multiclass_brier']:.6f} | {m['observed_expected_default_ratio']:.3f} |" for name,m in test_metrics.items()]
    lines += ['','An observed/expected ratio of 1 means aggregate calibration; materially different values indicate under/overprediction. Selection does not certify calibration.','','## Limitations','']+['- '+x for x in result['limitations']]
    (out/'model_report.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'status':'pass','selected':selected,'result':str(out/'model_result.json')}),flush=True)
    return result

if __name__=='__main__':run(Path(__file__).resolve().parents[2],'configs/estimated_models.json')
