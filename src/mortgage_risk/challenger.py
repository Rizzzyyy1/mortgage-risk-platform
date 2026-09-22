"""Regularized multinomial challenger using original training loans only."""
import json
import time
import uuid
import warnings
from pathlib import Path
from collections import Counter
import duckdb
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import roc_auc_score
from threadpoolctl import threadpool_limits
from mortgage_risk.artifact_integrity import fingerprint
from mortgage_risk.estimated_models import CLASSES, fit, predict


def fit_transformer(numeric, categorical, numeric_names, category_names):
    if not np.isfinite(numeric[~np.isnan(numeric)]).all():raise ValueError('Nonfinite features')
    if np.isnan(numeric).all(axis=0).any():raise ValueError('All-missing development feature')
    medians=np.nanmedian(numeric,axis=0)
    filled=np.where(np.isnan(numeric),medians,numeric)
    means=filled.mean(axis=0);scales=filled.std(axis=0);scales=np.where(scales==0,1,scales)
    categories=[sorted(set(categorical[:,i])) for i in range(categorical.shape[1])]
    return {'medians':medians.tolist(),'means':means.tolist(),'scales':scales.tolist(),
            'categories':categories,'numeric_names':numeric_names,'category_names':category_names}


def transform(numeric,categorical,state):
    missing=np.isnan(numeric)
    values=(np.where(missing,state['medians'],numeric)-state['means'])/state['scales']
    cols=[values,missing.astype(float)]
    for i,levels in enumerate(state['categories']):
        cols += [(categorical[:,i,None]==np.asarray(levels)[None,:]).astype(float),
                 (~np.isin(categorical[:,i],levels)).astype(float)[:,None]]
    x=np.concatenate(cols,axis=1)
    if not np.isfinite(x).all():raise ValueError('Nonfinite transformed features')
    return x


def feature_names(state):
    return state['numeric_names']+[x+'_missing' for x in state['numeric_names']]+[
        name+'='+level for name,levels in zip(state['category_names'],state['categories']) for level in levels+['UNSEEN']]


def predict_export(x,model):
    scores=x@np.asarray(model['coefficients']).T+model['intercepts']
    scores-=scores.max(axis=1,keepdims=True);e=np.exp(scores)
    return e/e.sum(axis=1,keepdims=True)


def evaluate(y,p):
    if p.shape!=(len(y),3) or not np.isfinite(p).all() or (p<0).any() or not np.allclose(p.sum(axis=1),1,atol=1e-12):raise ValueError('Invalid probabilities')
    losses=-np.log(np.clip(p[np.arange(len(y)),y],1e-15,1))
    binary=(y==0);expected=float(p[:,0].sum());observed=int(binary.sum())
    calibration=[]
    # Equal-sized score groups are descriptive only; no calibration is fitted here.
    for indices in np.array_split(np.argsort(p[:,0],kind='stable'),10):
        if len(indices):calibration.append({'loans':len(indices),'predicted':float(p[indices,0].mean()),'observed':float(binary[indices].mean())})
    return {'loans':len(y),'defaults':observed,'log_loss':float(losses.mean()),
            'multiclass_brier':float(np.mean(np.sum((p-np.eye(3)[y])**2,axis=1))),
            'default_auc':float(roc_auc_score(binary,p[:,0])) if 0<observed<len(y) else None,
            'expected_defaults':expected,'observed_expected':observed/expected if expected else None,
            'calibration_deciles':calibration}


def load_data(c,features,labels):
    c.read_parquet(str(features)).create_view('features');c.read_parquet(str(labels)).create_view('labels')
    for table in ['features','labels']:
        if c.execute(f'SELECT count(*)-count(DISTINCT (loan_id,reporting_month)) FROM {table}').fetchone()[0]:raise ValueError('Duplicate input keys')
        if c.execute(f'SELECT count(*) FROM {table} WHERE loan_id IS NULL OR reporting_month IS NULL').fetchone()[0]:raise ValueError('Missing keys')
    for a,b in [('features','labels'),('labels','features')]:
        if c.execute(f'SELECT count(*) FROM {a} ANTI JOIN {b} USING(loan_id,reporting_month)').fetchone()[0]:raise ValueError('Unmatched label join')
    if c.execute("SELECT count(*) FROM features WHERE reporting_month!=DATE '2011-01-01' OR substr(md5(loan_id),1,1) NOT IN ('0','1','2','3','4','5','6','7','8','9','a','b') OR development_split!=CASE WHEN substr(md5('expanded-v1:'||loan_id),1,1) IN ('0','1','2') THEN 'internal_validation' ELSE 'development' END").fetchone()[0]:raise ValueError('Unauthorized training population or changed split')
    c.execute("CREATE TABLE joined AS SELECT f.*,l.outcome_12m,coalesce(cast(f.delinquency_months AS VARCHAR),'missing')||'|'||coalesce(f.modification_status,'unknown_not_reported') benchmark_group FROM features f JOIN labels l USING(loan_id,reporting_month)")


def run(root,config):
    root=Path(root).resolve();cfg=json.loads(Path(config).read_text());start=time.perf_counter()
    out=root/'artifacts/runs/challenger'/uuid.uuid4().hex;out.mkdir(parents=True)
    # Freeze protocol on disk before reading labels or validation outcomes.
    (out/'protocol.json').write_text(json.dumps(cfg,indent=2)+'\n')
    c=duckdb.connect();c.execute("SET memory_limit='1GB'")
    load_data(c,root/cfg['features'],root/cfg['labels'])
    totals=c.execute('SELECT development_split,outcome_12m,count(*) FROM joined GROUP BY 1,2 ORDER BY 1,2').fetchall()
    data={};coverage={}
    names=cfg['numeric_features'];cats=cfg['categorical_features']
    for split in ['development','internal_validation']:
        raw=c.execute('SELECT loan_id,'+','.join(names+cats)+',outcome_12m FROM joined WHERE development_split=? ORDER BY loan_id',[split]).fetchall()
        known=[r for r in raw if r[-1] in CLASSES];unknown=len(raw)-len(known)
        coverage[split]={'total':len(raw),'known':len(known),'unresolved':unknown,'default_rate_bounds':[sum(r[-1]=='default_proxy' for r in known)/len(raw),(sum(r[-1]=='default_proxy' for r in known)+unknown)/len(raw)]}
        numeric=np.array([[float(v) if v is not None else np.nan for v in r[1:1+len(names)]] for r in known])
        categorical=np.array([r[1+len(names):-1] for r in known],dtype=str)
        y=np.array([CLASSES.index(r[-1]) for r in known]);ids=[r[0] for r in known]
        if set(y)!={0,1,2}:raise ValueError('Insufficient class support')
        data[split]=(numeric,categorical,y,ids)
    dn,dc,dy,_=data['development'];vn,vc,vy,vids=data['internal_validation']
    state=fit_transformer(dn,dc,names,cats);dx=transform(dn,dc,state);vx=transform(vn,vc,state)
    results={};models={};predictions={}
    hist=[{'group_key':g,'outcome':CLASSES[k],'n':n} for (g,k),n in Counter(zip(dc[:,0],dy)).items()]
    for alpha in [None]+cfg['benchmark_smoothing']:
        name='constant' if alpha is None else f'benchmark_{alpha}';model=fit(hist,alpha)
        probs=np.asarray([predict(model,g) for g in vc[:,0]])
        models[name]=model;predictions[name]=probs;results[name]=evaluate(vy,probs)
    print('Fitting three fixed regularization candidates on development rows only',flush=True)
    for strength in cfg['regularization_C']:
        model=LogisticRegression(C=strength,solver=cfg['solver'],max_iter=cfg['max_iterations'],tol=1e-7,random_state=cfg['seed'])
        with warnings.catch_warnings(),threadpool_limits(limits=2):
            warnings.simplefilter('error',ConvergenceWarning);model.fit(dx,dy)
        if list(model.classes_)!=[0,1,2]:raise ValueError('Class ordering changed')
        name=f'logistic_{strength}';p=model.predict_proba(vx)
        export={'classes':CLASSES,'coefficients':model.coef_.tolist(),'intercepts':model.intercept_.tolist(),'feature_names':feature_names(state),'preprocessing':state,'iterations':model.n_iter_.tolist()}
        if np.max(np.abs(p-predict_export(vx,export)))>1e-10:raise ValueError('Export parity failure')
        models[name]=export;predictions[name]=p;results[name]=evaluate(vy,p)
    selected=min(results,key=lambda k:(results[k]['log_loss'],k))
    best_logistic=min([k for k in results if k.startswith('logistic')],key=lambda k:results[k]['log_loss'])
    best_benchmark=min([k for k in results if not k.startswith('logistic')],key=lambda k:results[k]['log_loss'])
    diff=-np.log(np.clip(predictions[best_logistic][np.arange(len(vy)),vy],1e-15,1))+np.log(np.clip(predictions[best_benchmark][np.arange(len(vy)),vy],1e-15,1))
    rng=np.random.default_rng(cfg['seed']);boot=[float(diff[rng.integers(0,len(diff),len(diff))].mean()) for _ in range(cfg['bootstrap_repeats'])]
    segments=[]
    for group in sorted(set(vc[:,0])):
        mask=vc[:,0]==group
        segments.append({'group':group,'metrics':evaluate(vy[mask],predictions[selected][mask]),'support_warning':int((vy[mask]==0).sum())<20})
    prediction_path=out/'internal_predictions.parquet'
    c.execute('CREATE TABLE predictions(loan_id VARCHAR,outcome INTEGER,p_default DOUBLE,p_payoff DOUBLE,p_event_free DOUBLE)')
    # Small bounded validation output: use CSV then DuckDB bulk COPY, never row inserts.
    import csv
    with (out/'internal_predictions.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['loan_id','outcome','p_default','p_payoff','p_event_free'])
        writer.writerows((loan,int(y),*p) for loan,y,p in zip(vids,vy,predictions[selected]))
    c.execute('COPY predictions FROM ? (HEADER, DELIMITER \',\')',[str(out/'internal_predictions.csv')]);c.execute('COPY predictions TO ? (FORMAT PARQUET)',[str(prediction_path)])
    for name,model in models.items():(out/(name+'.json')).write_text(json.dumps(model,indent=2)+'\n')
    result={'status':'pass_for_exploratory_internal_comparison','selected_internal':selected,'best_logistic':best_logistic,'best_benchmark':best_benchmark,'metrics':results,'coverage':coverage,'segments':segments,'paired_log_loss_difference':{'mean':float(diff.mean()),'interval95':np.quantile(boot,[.025,.975]).tolist(),'note':'Fixed predictions, paired loan bootstrap; ignores model-fitting and selection uncertainty. Same validation used for selection; not confirmatory.'},'input_sha256':{k:fingerprint(root/cfg[k]) for k in ['features','labels']},'config_sha256':fingerprint(config),'implementation_sha256':fingerprint(__file__),'elapsed_seconds':time.perf_counter()-start,'limitations':['Original test and 2013 validation untouched.','Internal same-date selected-model performance is exploratory and optimistically selected.','Conditional complete-case target; unresolved outcomes excluded with bounds reported.','No externally validated model promotion, lifetime-loss coupling or dashboard replacement.']}
    (out/'challenger_result.json').write_text(json.dumps(result,indent=2)+'\n');c.close();print(out,flush=True);return result

if __name__=='__main__':run(Path(__file__).resolve().parents[2],'configs/challenger.json')
