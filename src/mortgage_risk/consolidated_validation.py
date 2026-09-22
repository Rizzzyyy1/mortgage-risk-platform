"""Phase6 saved-evidence validation and offline monitoring replay; no refitting."""
import json,math,hashlib,time,uuid,itertools
from pathlib import Path
from decimal import Decimal,localcontext
import duckdb


def psi(reference,current,pseudocount=.5):
    if not reference or len(reference)!=len(current) or min(reference+current)<0 or sum(reference)<=0 or sum(current)<=0 or pseudocount<=0:raise ValueError('Invalid PSI populations')
    a=sum(reference)+pseudocount*len(reference);b=sum(current)+pseudocount*len(current)
    return sum(((y+pseudocount)/b-(x+pseudocount)/a)*math.log(((y+pseudocount)/b)/((x+pseudocount)/a)) for x,y in zip(reference,current))


def calibration_status(loans,expected,observed,cfg):
    if loans<cfg['minimum_segment_loans'] or expected<cfg['minimum_expected_defaults']:return 'insufficient_support'
    ratio=observed/expected
    if ratio<cfg['oe_critical_low'] or ratio>cfg['oe_critical_high']:return 'critical'
    if ratio<cfg['oe_warning_low'] or ratio>cfg['oe_warning_high']:return 'warning'
    return 'within_judgmental_band'


def validate_curve(curve):
    prev=None
    for row in curve:
        n=row['at_risk'];d=row['defaults'];p=row['payoff_or_maturity'];c=row['censored']
        if n<=0 or min(d,p,c)<0 or d+p+c>n:raise ValueError('Invalid risk counts')
        if prev and n!=prev['at_risk']-prev['defaults']-prev['payoff_or_maturity']-prev['censored']:raise ValueError('Risk bridge mismatch')
        s0=prev['survival'] if prev else 1.;d0=prev['default_cif'] if prev else 0.;p0=prev['payoff_or_maturity_cif'] if prev else 0.
        expected=[s0*(1-(d+p)/n),d0+s0*d/n,p0+s0*p/n]
        actual=[row['survival'],row['default_cif'],row['payoff_or_maturity_cif']]
        if max(abs(a-b) for a,b in zip(actual,expected))>1e-12:raise ValueError('Probability recursion mismatch')
        prev=row
    if prev and prev['at_risk']!=prev['defaults']+prev['payoff_or_maturity']+prev['censored']:raise ValueError('Unclosed risk population')
    return len(curve)


def permutation_attribution(coalitions,metric):
    with localcontext() as ctx:
        ctx.prec=32;values=[Decimal(0)]*4
        for order in itertools.permutations(range(4)):
            mask=0
            for i in order:
                nxt=mask|(1<<i);values[i]+=Decimal(coalitions[str(nxt)][metric])-Decimal(coalitions[str(mask)][metric]);mask=nxt
        return [x/24 for x in values]


def prediction_metrics(c):
    row=c.execute("""SELECT count(*) n,count(*) FILTER(WHERE outcome='default_proxy') d,
      sum(p_default) expected,
      -avg(ln(CASE outcome WHEN 'default_proxy' THEN p_default WHEN 'payoff_or_maturity' THEN p_payoff_maturity ELSE p_event_free END)) logloss,
      avg(pow(p_default-cast(outcome='default_proxy' AS INTEGER),2)+pow(p_payoff_maturity-cast(outcome='payoff_or_maturity' AS INTEGER),2)+pow(p_event_free-cast(outcome='observed_event_free_12m' AS INTEGER),2)) brier
      FROM predictions WHERE outcome IN ('default_proxy','payoff_or_maturity','observed_event_free_12m')""").fetchone()
    auc=c.execute("""WITH bins AS(SELECT p_default,count(*) FILTER(WHERE outcome='default_proxy') d,count(*) FILTER(WHERE outcome!='default_proxy') n FROM predictions WHERE outcome IN ('default_proxy','payoff_or_maturity','observed_event_free_12m') GROUP BY 1), ranks AS(SELECT *,coalesce(sum(n) OVER(ORDER BY p_default ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) below FROM bins)
      SELECT sum(d*(below+n/2.0))/nullif(sum(d)*sum(n),0) FROM ranks""").fetchone()[0]
    return dict(loans=row[0],defaults=row[1],expected_defaults=row[2],multiclass_log_loss=row[3],multiclass_brier=row[4],default_auc=auc)


def run(root,config):
    root=Path(root).resolve();cfg=json.loads(Path(config).read_text());start=time.perf_counter();reports={};manifest={}
    for name,rel in cfg['reports'].items():
        path=root/rel;reports[name]=json.loads(path.read_text());manifest[name]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        status=reports[name].get('status',reports[name].get('engineering_status'))
        if status!='pass':raise ValueError(f'Unaccepted input {name}')
    a,e,f,b,design,model,stress=[reports[k] for k in ['acceptance','eligibility','descriptive','benchmark','design','model','stress']]
    if e['output_records']!=f['counts']['records'] or f['counts']['loans']!=b['total_loans'] or b['eligible_entry_loans']+b['entry_excluded']!=b['total_loans']:raise ValueError('Population lineage mismatch')
    if a['bridge_failures'] or e['monthly_reconciliation_differences'] or f['input_monthly_differences'] or f['category_reconciliation_differences']:raise ValueError('Earlier reconciliation failure')
    for actual,wanted in [(f['input_run'],Path(manifest['eligibility']['path']).parent),(b['input_run'],Path(manifest['descriptive']['path']).parent),(model['input_run'],Path(manifest['design']['path']).parent),(stress['input_run'],Path(manifest['benchmark']['path']).parent)]:
        if Path(actual).resolve()!=wanted.resolve():raise ValueError('Run lineage mismatch')
    out=root/'artifacts/runs/phase6'/uuid.uuid4().hex;out.mkdir(parents=True)
    benchmark_dir=Path(manifest['benchmark']['path']).parent;model_dir=Path(manifest['model']['path']).parent;stress_dir=Path(manifest['stress']['path']).parent
    print('Checking saved risk curves, model predictions, labels and scenario arithmetic',flush=True)
    curve=json.loads((benchmark_dir/'historical_curve.json').read_text());curve_count=validate_curve(curve)
    c=duckdb.connect()
    def view(name,path):
        escaped=str(path).replace("'","''")
        c.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{escaped}')")
    view('predictions',model_dir/'test_predictions.parquet')
    view('labels',Path(manifest['design']['path']).parent/'test_labels.parquet')
    invalid=c.execute('SELECT count(*) FROM predictions WHERE p_default IS NULL OR p_payoff_maturity IS NULL OR p_event_free IS NULL OR NOT isfinite(p_default) OR NOT isfinite(p_payoff_maturity) OR NOT isfinite(p_event_free) OR p_default<=0 OR p_payoff_maturity<=0 OR p_event_free<=0 OR abs(p_default+p_payoff_maturity+p_event_free-1)>1e-12').fetchone()[0]
    if invalid:raise ValueError('Invalid predictions')
    if c.execute('SELECT count(*) FROM predictions').fetchone()[0]!=model['censoring_sensitivity']['test']['total']:raise ValueError('Prediction count mismatch')
    mismatch=c.execute('SELECT count(*) FROM predictions p FULL JOIN labels l USING(loan_id,reporting_month) WHERE p.outcome IS DISTINCT FROM l.outcome_12m').fetchone()[0]
    if mismatch:raise ValueError('Saved labels mismatch')
    if c.execute('SELECT count(*)-count(distinct loan_id) FROM predictions').fetchone()[0]:raise ValueError('Prediction duplicates')
    independent=prediction_metrics(c);saved=model['test_metrics'][model['selected_model']]
    differences={k:abs(v-saved[k]) for k,v in independent.items()}
    if any(v>1e-9 for v in differences.values()):raise ValueError('Independent model metrics mismatch')
    selected=json.loads((model_dir/'selected_model.json').read_text());selection=json.loads((model_dir/'selection.json').read_text())
    expected_selection=min(model['validation_metrics'],key=lambda name:(model['validation_metrics'][name]['multiclass_log_loss'],name))
    if selection['selected']!=expected_selection or model['selected_model']!=expected_selection:raise ValueError('Selection mismatch')
    pred_groups=c.execute('SELECT DISTINCT group_key,p_default,p_payoff_maturity,p_event_free FROM predictions').fetchall()
    if any(max(abs(x-y) for x,y in zip(row[1:],selected['groups'].get(row[0],selected['prior'])))>1e-12 for row in pred_groups):raise ValueError('Predictions differ from frozen model')
    c.close()
    attribution_residuals={}
    drivers=['default','payoff_maturity','severity','recovery_delay']
    for metric,contributions in stress['shapley_attribution'].items():
        independent_values=permutation_attribution(stress['coalitions'],metric)
        residual=max(abs(v-Decimal(contributions[d])) for d,v in zip(drivers,independent_values))
        if residual>Decimal('0.00000001'):raise ValueError('Independent attribution mismatch')
        attribution_residuals[metric]=str(residual)
    money_checks={}
    for scenario in ['baseline','adverse']:
        schedule=json.loads((stress_dir/(scenario+'_schedule.json')).read_text());lag=stress[scenario]['recovery_lag_months']
        with localcontext() as ctx:
            ctx.prec=32;growth=1+Decimal(str(stress['config']['annual_discount_rate']))
            undisc=sum(Decimal(x['expected_defaulted_balance'])-Decimal(x['assumed_recovery']) for x in schedule)
            pv=sum(Decimal(x['expected_defaulted_balance'])/growth**(Decimal(x['month'])/12)-Decimal(x['assumed_recovery'])/growth**(Decimal(x['month']+lag)/12) for x in schedule)
            residual=max(abs(undisc-Decimal(stress[scenario]['remaining_life_expected_loss'])),abs(pv-Decimal(stress[scenario]['timing_adjusted_pv_loss'])))
            if residual>Decimal('0.00000001'):raise ValueError('Independent loss mismatch')
            money_checks[scenario]=str(residual)
    print('Replaying judgmental monitoring rules without retraining or recalibration',flush=True)
    thresholds=cfg['monitoring'];groups=model['feature_group_shift'];reference=[x['train'] for x in groups];monitor=[]
    for split in ['train','validation','test']:
        shift=psi(reference,[x[split] for x in groups]);censor=model['censoring_sensitivity'][split]
        metric=None if split=='train' else (model['validation_metrics'][model['selected_model']] if split=='validation' else saved)
        monitor.append(dict(split=split,psi=shift,population_status='critical' if shift>=thresholds['psi_critical'] else 'warning' if shift>=thresholds['psi_warning'] else 'within_judgmental_band',
          unresolved_fraction=censor['censored_or_unresolved']/censor['total'],
          unresolved_status='warning' if censor['censored_or_unresolved']/censor['total']>thresholds['unresolved_warning'] else 'within_judgmental_band',
          calibration_status='training_reference_not_evaluated' if metric is None else calibration_status(metric['loans'],metric['expected_defaults'],metric['defaults'],thresholds)))
    segment_monitor=[dict(group_key=s['group_key'],status=calibration_status(s['loans'],s['expected_defaults'],s['defaults'],thresholds),loans=s['loans'],observed=s['defaults'],expected=s['expected_defaults']) for s in model['test_segments']]
    result=dict(phase='6',status='pass',engineering_verdict='pass',statistical_verdict='qualified_single_cohort_conditional_benchmark',economic_verdict='actual_cohort_loss_not_ready',
      input_manifest=manifest,historical_intervals_checked=curve_count,independent_metric_differences=differences,
      independent_attribution_residuals=attribution_residuals,independent_monetary_residuals=money_checks,
      monitoring_replay=monitor,segment_monitoring=segment_monitor,config=cfg,elapsed_seconds=round(time.perf_counter()-start,3),
      implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),config_sha256=hashlib.sha256(Path(config).read_bytes()).hexdigest(),output_directory=str(out),
      limitations=['Developer-conducted independent calculation checks, not external independent validation.',
      'Monitoring thresholds are retrospective project judgments selected after prior results were visible; they are not backtested operational thresholds or regulatory standards.',
      'Only three historical split snapshots are replayed. This is not a live monitor, fresh-data backtest or new test evaluation.',
      'Single cohort, 77 test defaults, conditional censor treatment and sparse modified segments limit statistical conclusions.',
      'Actual exposure/maturity, severity and macro transmission remain unresolved; losses remain explicitly hypothetical.'])
    (out/'validation_result.json').write_text(json.dumps(result,indent=2));(out/'monitoring_replay.json').write_text(json.dumps(monitor,indent=2))
    lines=['# Phase 6 validation and monitoring','', '**Engineering:** pass. **Statistical:** qualified benchmark. **Actual-cohort economic losses:** not ready.','',
      'Saved held-out probabilities, labels, metrics and validation-only selection were reconciled without fitting. Risk recursions and stress monetary calculations were checked independently; attribution was checked using all 24 driver orderings.','','## Monitoring replay','','| Snapshot | Population PSI | Population flag | Calibration flag |','|---|---:|---|---|']
    lines += [f"| {x['split']} | {x['psi']:.5f} | {x['population_status']} | {x['calibration_status']} |" for x in monitor]
    lines += ['','## Segment actions','','| Group | Status | Action |','|---|---|---|']
    lines += [f"| {x['group_key'].replace('|',' / ')} | {x['status']} | "+('Investigate under/overprediction on fresh validation data; do not tune on this test.' if x['status'] in ['warning','critical'] else 'Collect more outcomes before a segment conclusion.' if x['status']=='insufficient_support' else 'Continue observation; band membership does not prove calibration.')+' |' for x in segment_monitor]
    lines += ['','## Limitations','']+['- '+x for x in result['limitations']]
    (out/'validation_report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':'pass','result':str(out/'validation_result.json')}),flush=True);return result

if __name__=='__main__':run(Path(__file__).resolve().parents[2],'configs/consolidated_validation.json')
