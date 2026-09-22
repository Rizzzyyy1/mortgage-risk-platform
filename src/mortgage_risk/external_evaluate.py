"""Score a reserved cohort once with frozen models; report, never auto-promote."""
import argparse,csv,json,time,uuid
from pathlib import Path
import duckdb
import numpy as np
from scipy.optimize import minimize,brentq
from scipy.special import expit
from threadpoolctl import threadpool_limits
from mortgage_risk.external_readiness import check
from mortgage_risk.artifact_integrity import fingerprint
from mortgage_risk.challenger import transform,predict_export,evaluate
from mortgage_risk.estimated_models import CLASSES,predict


def calibration_diagnostics(y,p):
    y=np.asarray(y,dtype=float);z=np.log(np.clip(p,1e-12,1-1e-12)/(1-np.clip(p,1e-12,1-1e-12)))
    if y.sum()==0 or y.sum()==len(y):return {'status':'insufficient_class_support'}
    def objective(theta):
        score=theta[0]+theta[1]*z
        residual=expit(score)-y
        return float(np.mean(np.logaddexp(0,score)-y*score)),np.array([residual.mean(),np.mean(residual*z)])
    result=minimize(objective,[0.,1.],jac=True,method='BFGS',options={'gtol':1e-7})
    return {'status':'pass' if result.success else 'optimization_warning','intercept':float(result.x[0]),'slope':float(result.x[1]),'intercept_slope_fixed_one':float(brentq(lambda a:np.mean(expit(z+a))-y.mean(),-50,50)),'note':'Diagnostic only; not applied to model predictions.'}


def auc_bins(y,scores):
    _,bins=np.unique(scores,return_inverse=True)
    return np.asarray(y)==0,bins,int(bins.max())+1


def weighted_auc(prepared,weights):
    positive,bins,n=prepared
    a=np.bincount(bins,weights=weights*positive,minlength=n)
    b=np.bincount(bins,weights=weights*(~positive),minlength=n)
    if a.sum()==0 or b.sum()==0:return float('nan')
    return float(np.sum(a*(np.cumsum(b)-.5*b))/(a.sum()*b.sum()))


def comparison_gates(cfg,metrics,unresolved,total,interval):
    a,b=metrics['candidate'],metrics['benchmark']
    return {'default_support':a['defaults']>=cfg['minimum_observed_defaults'],
            'unresolved_fraction':unresolved/total<=cfg['maximum_unresolved_fraction'],
            'paired_log_loss':interval['log_loss'][1]<cfg['paired_log_loss_ci_upper_must_be_below'],
            'brier':a['multiclass_brier']<=b['multiclass_brier'],
            'auc_noninferiority':a['default_auc'] is not None and b['default_auc'] is not None and a['default_auc']>=b['default_auc']-cfg['maximum_auc_degradation'],
            'calibration':a['observed_expected'] is not None and cfg['calibration_oe_range'][0]<=a['observed_expected']<=cfg['calibration_oe_range'][1]}


def run(root,cohort):
    root=Path(root).resolve();cohort=Path(cohort).resolve();start=time.perf_counter();check(root)
    cfg=json.loads((root/'configs/external_evaluation.json').read_text());receipt=json.loads((cohort/'cohort_result.json').read_text())
    if receipt['status']!='pass_for_reserved_cohort_adapter':raise ValueError('Unaccepted adapter')
    frozen=receipt['feature_freeze']
    if fingerprint(cohort/'features.parquet')!=frozen['feature_sha256'] or fingerprint(root/'configs/external_evaluation.json')!=frozen['protocol_sha256']:raise ValueError('Frozen feature or protocol changed')
    candidate=json.loads((root/cfg['candidate']).read_text());benchmark=json.loads((root/cfg['benchmark']).read_text());state=candidate['preprocessing']
    if candidate['classes']!=CLASSES or benchmark['classes']!=CLASSES:raise ValueError('Class ordering mismatch')
    out=root/'artifacts/runs/external_evaluation'/uuid.uuid4().hex;out.mkdir(parents=True)
    c=duckdb.connect();c.read_parquet(str(cohort/'features.parquet')).create_view('features');c.read_parquet(str(cohort/'labels.parquet')).create_view('labels')
    for table in ['features','labels']:
        if c.execute(f'SELECT count(*)-count(DISTINCT (loan_id,reporting_month)) FROM {table}').fetchone()[0]:raise ValueError('Duplicate keys')
    for a,b in [('features','labels'),('labels','features')]:
        if c.execute(f'SELECT count(*) FROM {a} ANTI JOIN {b} USING(loan_id,reporting_month)').fetchone()[0]:raise ValueError('Unmatched labels')
    total=c.execute('SELECT count(*) FROM features').fetchone()[0]
    if total>2000000:raise ValueError('Snapshot exceeds bounded in-memory scoring design')
    c.execute("CREATE VIEW scoring AS SELECT f.*,coalesce(cast(delinquency_months AS VARCHAR),'missing')||'|'||coalesce(modification_status,'unknown_not_reported') benchmark_group FROM features f")
    names=state['numeric_names'];cats=state['category_names']
    raw=c.execute('SELECT loan_id,'+','.join(names+cats)+' FROM scoring ORDER BY loan_id').fetchall()
    numeric=np.array([[float(v) if v is not None else np.nan for v in r[1:1+len(names)]] for r in raw]);categorical=np.array([r[1+len(names):] for r in raw],dtype=str)
    print('Scoring all eligible loans using frozen coefficients and transformations',flush=True)
    with threadpool_limits(limits=2):p=predict_export(transform(numeric,categorical,state),candidate)
    q=np.asarray([predict(benchmark,g) for g in categorical[:,0]])
    # Persist every prediction before associating labels.
    with (out/'predictions.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['loan_id','candidate_default','candidate_payoff','candidate_event_free','benchmark_default','benchmark_payoff','benchmark_event_free']);writer.writerows((r[0],*a,*b) for r,a,b in zip(raw,p,q))
    c.read_csv(str(out/'predictions.csv'),header=True,all_varchar=False).create_view('saved_predictions')
    c.execute('COPY saved_predictions TO ? (FORMAT PARQUET)',[str(out/'predictions.parquet')])
    labels=c.execute('SELECT loan_id,outcome_12m FROM labels ORDER BY loan_id').fetchall()
    if [r[0] for r in raw]!=[r[0] for r in labels]:raise ValueError('Scoring order mismatch')
    mask=np.array([r[1] in CLASSES for r in labels]);y=np.array([CLASSES.index(r[1]) for r in labels if r[1] in CLASSES]);ap=p[mask];bp=q[mask]
    metrics={'candidate':evaluate(y,ap),'benchmark':evaluate(y,bp)}
    diagnostic=calibration_diagnostics(y==0,ap[:,0])
    loss_diff=-np.log(np.clip(ap[np.arange(len(y)),y],1e-15,1))+np.log(np.clip(bp[np.arange(len(y)),y],1e-15,1))
    brier_diff=np.sum((ap-np.eye(3)[y])**2,axis=1)-np.sum((bp-np.eye(3)[y])**2,axis=1)
    aa,bb=auc_bins(y,ap[:,0]),auc_bins(y,bp[:,0]);rng=np.random.default_rng(cfg['seed']);samples=[]
    print('Computing fixed paired bootstrap comparisons; no selection or recalibration',flush=True)
    with threadpool_limits(limits=2):
        for _ in range(cfg['bootstrap_repeats']):
            w=np.bincount(rng.integers(0,len(y),len(y)),minlength=len(y))
            samples.append([float(w@loss_diff/len(y)),float(w@brier_diff/len(y)),weighted_auc(aa,w)-weighted_auc(bb,w)])
    intervals={name:np.nanquantile(np.asarray(samples)[:,i],[.025,.975]).tolist() for i,name in enumerate(['log_loss','brier','auc'])}
    segments=[]
    groups={'delinquency':categorical[mask,0], 'occupancy':categorical[mask,1],'purpose':categorical[mask,2],
            'fico_band':np.array(['missing' if np.isnan(v) else '<660' if v<660 else '660-719' if v<720 else '720+' for v in numeric[mask,0]]),
            'ltv_band':np.array(['missing' if np.isnan(v) else '<=80' if v<=80 else '>80' for v in numeric[mask,1]])}
    for field,values in groups.items():
        for value in sorted(set(values)):
            m=values==value
            segments.append({'field':field,'value':value,'candidate':evaluate(y[m],ap[m]),'benchmark':evaluate(y[m],bp[m]),'insufficient_support':int((y[m]==0).sum())<20 or int(m.sum())<100})
    drift={'numeric':{name:{'missing_fraction':float(np.isnan(numeric[:,i]).mean()),'observed_mean':float(np.nanmean(numeric[:,i])),'development_imputed_mean':state['means'][i],'mean_shift_in_development_sd':float((np.nanmean(numeric[:,i])-state['means'][i])/state['scales'][i])} for i,name in enumerate(names)},'unseen_categories':{name:int((~np.isin(categorical[:,i],state['categories'][i])).sum()) for i,name in enumerate(cats)},'note':'All eligible external covariates; development reference uses frozen known-outcome preprocessing. Mean-shift diagnostic, not PSI.'}
    unresolved=total-len(y);gates=comparison_gates(cfg,metrics,unresolved,total,intervals)
    result={'status':'evaluated_not_promoted','quantitative_gates':gates,'all_quantitative_gates_pass':all(gates.values()),'metrics':metrics,'calibration_diagnostics':diagnostic,'paired_difference_intervals95':intervals,'coverage':{'total':total,'known':len(y),'unresolved':unresolved,'default_rate_bounds':[int((y==0).sum())/total,(int((y==0).sum())+unresolved)/total]},'segments':segments,'drift':drift,'protocol_sha256':fingerprint(root/'configs/external_evaluation.json'),'candidate_sha256':fingerprint(root/cfg['candidate']),'benchmark_sha256':fingerprint(root/cfg['benchmark']),'features_sha256':fingerprint(cohort/'features.parquet'),'labels_sha256':fingerprint(cohort/'labels.parquet'),'implementation_sha256':fingerprint(__file__),'elapsed_seconds':time.perf_counter()-start,'model_promoted':False,'limitations':['Reserved acquisition cohort only; no broad cycle or production claim.','Conditional complete-case outcome; censoring bounds reported.','Calibration fit is diagnostic only and never applied to predictions.','Bootstrap conditional on frozen models; does not include development/model-selection uncertainty.','Segment support and deterioration require review even if quantitative gates pass.']}
    (out/'evaluation_result.json').write_text(json.dumps(result,indent=2)+'\n');c.close();print(out,flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cohort',required=True);args=p.parse_args();run(Path(__file__).resolve().parents[2],args.cohort)
