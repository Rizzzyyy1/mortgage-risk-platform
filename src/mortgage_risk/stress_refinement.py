"""Phase5 illustrative dynamic stress, recovery timing and exact driver attribution."""
import json,hashlib,time,uuid,math
from decimal import Decimal,localcontext
from pathlib import Path
import duckdb
from mortgage_risk.benchmark import project_example
DRIVERS=['default','payoff_maturity','severity','recovery_delay']


def stress_weights(months,hold,fade_end):
    if not 0<hold<fade_end<=months:raise ValueError('Invalid stress timing')
    return [1. if t<=hold else max(0.,(fade_end-t)/(fade_end-hold)) for t in range(1,months+1)]


def present_value(schedule,annual_discount,lag):
    if not math.isfinite(annual_discount) or annual_discount<0 or not isinstance(lag,int) or lag<0:raise ValueError('Invalid recovery timing')
    with localcontext() as ctx:
        ctx.prec=32
        q=(1+Decimal(str(annual_discount)))**(Decimal(1)/12)
        d=r=tail=Decimal(0)
        for row in schedule:
            t=row['month'];defaulted=Decimal(row['expected_defaulted_balance']);recovered=Decimal(row['assumed_recovery'])
            d+=defaulted/q**t;r+=recovered/q**(t+lag)
            if t+lag>len(schedule):tail+=recovered
        return dict(pv_defaulted_balance=str(d),pv_recoveries=str(r),timing_adjusted_pv_loss=str(d-r),undiscounted_recovery_beyond_loan_horizon=str(tail))


def shapley(values,n=4):
    if set(values)!=set(range(2**n)):raise ValueError('All coalitions required')
    with localcontext() as ctx:
        ctx.prec=32;result=[]
        for i in range(n):
            total=Decimal(0)
            for mask in range(2**n):
                if mask&(1<<i):continue
                k=mask.bit_count();weight=Decimal(math.factorial(k)*math.factorial(n-k-1))/math.factorial(n)
                total+=weight*(Decimal(values[mask|(1<<i)])-Decimal(values[mask]))
            result.append(total)
        if abs(sum(result)-(Decimal(values[2**n-1])-Decimal(values[0])))>Decimal('0.00000001'):raise ValueError('Attribution does not reconcile')
        return result


def run(root,config):
    root=Path(root).resolve();cfg=json.loads(Path(config).read_text());start=time.perf_counter();inp=root/cfg['benchmark_run']
    prior=json.loads((inp/'benchmark_result.json').read_text())
    if prior['status']!='pass':raise ValueError('Unaccepted benchmark')
    out=root/'artifacts/runs/phase5'/uuid.uuid4().hex;out.mkdir(parents=True)
    loan=prior['hypothetical_loan'];n=loan['remaining_months'];hd=prior['pooled_first12']['default_hazard'];hp=prior['pooled_first12']['payoff_or_maturity_hazard']
    base_lgd=prior['illustrative_scenarios']['baseline']['assumptions']['lgd'];shock=cfg['adverse'];w=stress_weights(n,cfg['hold_months'],cfg['fade_end_month'])
    paths=dict(default=[hd*(1+x*(shock['default_multiplier']-1)) for x in w],
      payoff_maturity=[hp*(1+x*(shock['payoff_multiplier']-1)) for x in w],severity=[base_lgd+x*(shock['lgd']-base_lgd) for x in w])
    coalitions={};schedules={}
    print('Projecting baseline and transient stress; attributing all four interacting drivers',flush=True)
    for mask in range(16):
        p=project_example(loan['opening_balance'],loan['annual_coupon'],n,paths['default'] if mask&1 else hd,paths['payoff_maturity'] if mask&2 else hp,paths['severity'] if mask&4 else base_lgd)
        lag=shock['recovery_lag_months'] if mask&8 else cfg['baseline_recovery_lag_months']
        pv=present_value(p['schedule'],cfg['annual_discount_rate'],lag)
        if mask in (0,15):schedules['baseline' if mask==0 else 'adverse']=p['schedule']
        p.pop('schedule');coalitions[mask]=dict(active_drivers=[d for i,d in enumerate(DRIVERS) if mask&(1<<i)],recovery_lag_months=lag,**p,**pv)
    baseline_residual=abs(Decimal(coalitions[0]['remaining_life_expected_loss'])-Decimal(prior['illustrative_scenarios']['baseline']['remaining_life_expected_loss']))
    if baseline_residual>Decimal('0.00000001'):raise ValueError('Baseline changed from Phase3')
    attrib={metric:shapley({k:v[metric] for k,v in coalitions.items()}) for metric in ['remaining_life_expected_loss','timing_adjusted_pv_loss']}
    sensitivity=[]
    for driver,values in cfg['sensitivity'].items():
        for value in values:
            d=hd*(value if driver=='default_multiplier' else 1);p=hp*(value if driver=='payoff_multiplier' else 1);l=value if driver=='lgd' else base_lgd
            term=value if driver=='remaining_months' else n
            result=project_example(loan['opening_balance'],loan['annual_coupon'],term,d,p,l)
            pv=present_value(result['schedule'],value if driver=='annual_discount_rate' else cfg['annual_discount_rate'],value if driver=='recovery_lag_months' else cfg['baseline_recovery_lag_months'])
            sensitivity.append(dict(driver=driver,value=value,remaining_life_expected_loss=result['remaining_life_expected_loss'],**pv))
    # Direction checks concern these frozen hypothetical assumptions, not universal economic claims.
    for driver,metric,direction in [('default_multiplier','remaining_life_expected_loss',1),('payoff_multiplier','remaining_life_expected_loss',-1),('lgd','remaining_life_expected_loss',1),('remaining_months','remaining_life_expected_loss',1),('recovery_lag_months','timing_adjusted_pv_loss',1)]:
        rows=sorted((x for x in sensitivity if x['driver']==driver),key=lambda x:x['value'])
        if any(direction*(Decimal(b[metric])-Decimal(a[metric]))<Decimal('-0.00000001') for a,b in zip(rows,rows[1:])):raise ValueError('Sensitivity direction check failed')
    c=duckdb.connect()
    def persist(name,obj):
        path=out/(name+'.json');path.write_text(json.dumps(obj,indent=2,default=str))
        target=str(out/(name+'.parquet')).replace("'","''")
        c.execute(f"COPY (SELECT * FROM read_json_auto(?)) TO '{target}' (FORMAT PARQUET)",[str(path)])
    for name,rows in schedules.items():persist(name+'_schedule',rows)
    persist('sensitivity',sensitivity);c.close()
    result=dict(phase='5',status='pass',input_run=str(inp),config=cfg,baseline=coalitions[0],adverse=coalitions[15],
      shapley_attribution={key:{driver:str(v) for driver,v in zip(DRIVERS,values)} for key,values in attrib.items()},
      baseline_reproduction_residual=str(baseline_residual),coalitions=coalitions,paths=paths,elapsed_seconds=round(time.perf_counter()-start,3),
      implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),projection_sha256=hashlib.sha256(Path(project_example.__code__.co_filename).read_bytes()).hexdigest(),
      config_sha256=hashlib.sha256(Path(config).read_bytes()).hexdigest(),output_directory=str(out),
      limitations=['Entire loss analysis is hypothetical; no actual-cohort lifetime loss or macro-calibrated stress claim.',
      'Phase4 conditional 12-month model is not converted to monthly hazards or lifetime losses.',
      'LGD means undiscounted non-recovery fraction here, excluding delay; timing-adjusted PV loss is separate from undiscounted expected loss.',
      'Recovery cashflows beyond contractual loan maturity are included. No recovery operating costs or stochastic timing distribution.',
      'Shapley allocation divides nonlinear interactions symmetrically; it is accounting attribution, not causal identification.'])
    (out/'stress_result.json').write_text(json.dumps(result,indent=2,default=str))
    lines=['# Phase 5 illustrative stress refinement','', 'Hypothetical $100,000 loan; no actual-cohort loss estimate. Stress holds for 24 months and returns to baseline by month 60.','','| Measure | Baseline | Transient adverse |','|---|---:|---:|']
    for key,label in [('remaining_life_expected_loss','Undiscounted expected loss'),('timing_adjusted_pv_loss','Timing-adjusted PV loss')]:
        lines.append(f"| {label} | ${Decimal(coalitions[0][key]):,.2f} | ${Decimal(coalitions[15][key]):,.2f} |")
    lines+=['','## Exact four-driver attribution','','| Driver | Undiscounted loss increase | PV loss increase |','|---|---:|---:|']
    lines += [f"| {d} | ${attrib['remaining_life_expected_loss'][i]:,.2f} | ${attrib['timing_adjusted_pv_loss'][i]:,.2f} |" for i,d in enumerate(DRIVERS)]
    lines+=['','Driver contributions reconcile before display rounding. All 16 baseline/adverse driver combinations are evaluated.','','## Limitations','']+['- '+x for x in result['limitations']]
    (out/'stress_report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':'pass','result':str(out/'stress_result.json'),'seconds':result['elapsed_seconds']}),flush=True);return result

if __name__=='__main__':run(Path(__file__).resolve().parents[2],'configs/stress_refinement.json')
