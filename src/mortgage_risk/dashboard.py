"""Build a self-contained local dashboard from accepted aggregate evidence only."""
import json,hashlib,uuid,time
from pathlib import Path
from decimal import Decimal
from mortgage_risk.artifact_integrity import verify_manifest


def load_payload(root,config):
    root=Path(root);cfg=json.loads(Path(config).read_text());paths=json.loads((root/'configs/consolidated_validation.json').read_text())['reports']
    stress_dir = str(Path(paths['stress']).parent)
    required = list(paths.values()) + [cfg['validation_report']] + [str(Path(stress_dir)/name) for name in ('baseline_schedule.json', 'adverse_schedule.json', 'sensitivity.json')]
    verify_manifest(root, root/cfg['integrity_manifest'], required)
    reports={k:json.loads((root/v).read_text()) for k,v in paths.items()}
    validation=json.loads((root/cfg['validation_report']).read_text())
    if validation['status']!='pass':raise ValueError('Validation not accepted')
    for k,v in reports.items():
        if v.get('status',v.get('engineering_status'))!='pass':raise ValueError(f'Unaccepted report {k}')
        if hashlib.sha256((root/paths[k]).read_bytes()).hexdigest()!=validation['input_manifest'][k]['sha256']:raise ValueError('Dashboard input differs from validated manifest')
    e,f,b,m,s= [reports[k] for k in ['eligibility','descriptive','benchmark','model','stress']]
    if sum(x['records'] for x in e['eligibility_counts'])!=f['counts']['records']:raise ValueError('Eligibility count mismatch')
    monthly={x['reporting_month']:x for x in f['monthly']}
    if len(monthly) != len(f['monthly']):raise ValueError('Duplicate reporting months')
    if set(monthly) != {x['reporting_month'] for x in e['monthly_summary']}:raise ValueError('Reporting month coverage mismatch')
    for month in monthly:
        groups=[x for x in e['monthly_summary'] if x['reporting_month']==month]
        if sum(x['records'] for x in groups)!=monthly[month]['records']:raise ValueError('Monthly categories mismatch')
        if sum(Decimal(x['reported_balance']) for x in groups)!=Decimal(monthly[month]['reported_balance']):raise ValueError('Monthly balance mismatch')
    sd=(root/paths['stress']).parent
    curves=[]
    totals={}
    for name in ['baseline','adverse']:
        schedule=json.loads((sd/(name+'_schedule.json')).read_text());total=Decimal(0);vals=[]
        for index, row in enumerate(schedule, start=1):
            if row.get('month') != index:raise ValueError('Nonconsecutive schedule months')
            loss=Decimal(row['expected_loss'])
            if not loss.is_finite() or loss < 0:raise ValueError('Invalid schedule loss')
            total+=loss;vals.append(float(total))
        if abs(total-Decimal(s[name]['remaining_life_expected_loss']))>Decimal('0.00000001'):raise ValueError('Stress display does not reconcile')
        totals[name]=vals
    if not totals['baseline'] or len(totals['baseline']) != len(totals['adverse']):raise ValueError('Schedule horizon mismatch')
    curves=[{'month':i+1,'baseline':x,'adverse':totals['adverse'][i]} for i,x in enumerate(totals['baseline'])]
    return dict(counts=f['counts'],monthly=f['monthly'],eligibility=e['monthly_summary'],historical_12m=b['historical_12m'],
      model=m,stress=s,sensitivity=json.loads((sd/'sensitivity.json').read_text()),loss_curve=curves,validation=validation,
      provenance=[dict(stage=k,run_id=Path(v).parent.name,report=Path(v).name,sha256=hashlib.sha256((root/v).read_bytes()).hexdigest()) for k,v in paths.items()])


def sanitize(payload):
    # The UI needs aggregate evidence, not local filesystem paths or large coalition details.
    p=dict(payload)
    for name in ['model','stress','validation']:
        p[name]={k:v for k,v in p[name].items() if k not in ['input_run','output_directory','input_manifest','coalitions','config']}
    return p


def run(root,config):
    root=Path(root).resolve();start=time.perf_counter();payload=sanitize(load_payload(root,config));out=root/'artifacts/runs/phase7'/uuid.uuid4().hex;out.mkdir(parents=True)
    template=(root/'app/dashboard.html').read_text()
    encoded=json.dumps(payload,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    if template.count('__DASHBOARD_DATA__')!=1:raise ValueError('Expected one payload placeholder')
    (out/'index.html').write_text(template.replace('__DASHBOARD_DATA__',encoded));(out/'dashboard_data.json').write_text(json.dumps(payload,indent=2))
    model=payload['model'];test=model['test_metrics'][model['selected_model']];stress=payload['stress']
    memo=f'''# Mortgage credit risk — executive brief

## Decision summary
The project demonstrates a reconciled mortgage data pipeline, an interpretable 12-month risk benchmark, and an explicitly illustrative stress/loss framework. Engineering validation passes; statistical evidence is qualified and actual-cohort lifetime loss estimates are not ready.

## Evidence
- Historical cohort: {payload['counts']['loans']:,} loans, {payload['counts']['records']:,} loan-month records, {payload['counts']['months']} reporting months.
- Held-out test: {test['loans']:,} loans, {test['defaults']} defaults; AUC {test['default_auc']:.4f}. Expected defaults {test['expected_defaults']:.2f}; observed/expected ratio {test['observed_expected_default_ratio']:.3f}.
- Model selection used validation only; calibration differs across segments. The current/unmodified segment warrants investigation, while sparse groups do not support strong conclusions.
- Hypothetical $100,000 loan: undiscounted baseline loss ${Decimal(stress['baseline']['remaining_life_expected_loss']):,.2f}, transient adverse ${Decimal(stress['adverse']['remaining_life_expected_loss']):,.2f}. These are not losses on the historical portfolio.

## Interpretation and next decisions
Only one acquisition cohort is available. Censoring, vendor revision history, exposure masking, maturity/prepayment separation and unestimated severity constrain interpretation. Preserve the held-out test; investigate calibration using fresh validation evidence. Do not replace missing balances or call illustrative losses regulatory or production estimates.

The local dashboard presents four views: historical portfolio, held-out model performance, hypothetical stress, and validation evidence. Its month controls filter saved aggregates; no model is fitted in the browser. Detailed provenance remains visible in the Evidence view.

Next delivery gate: reproducible clean setup, public synthetic demonstration, and repository hygiene. Publication is separate authorization.
'''
    (out/'executive_memo.md').write_text(memo)
    manifest=dict(phase='7',status='built_pending_browser_verification',output_directory=str(out),input_provenance=payload['provenance'],
      integrity_manifest_sha256=hashlib.sha256((root/json.loads(Path(config).read_text())['integrity_manifest']).read_bytes()).hexdigest(),
      html_sha256=hashlib.sha256((out/'index.html').read_bytes()).hexdigest(),template_sha256=hashlib.sha256((root/'app/dashboard.html').read_bytes()).hexdigest(),
      implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),elapsed_seconds=round(time.perf_counter()-start,3))
    (out/'dashboard_result.json').write_text(json.dumps(manifest,indent=2));print(str(out),flush=True);return manifest

if __name__=='__main__':run(Path(__file__).resolve().parents[2],'configs/dashboard.json')
