"""Transparent cohort competing-risk benchmark and explicitly hypothetical loss example."""
import argparse
import hashlib
import json
import math
import time
import uuid
from decimal import Decimal, localcontext
from pathlib import Path
from datetime import datetime, timezone
import duckdb


def episode_sql():
    return """SELECT loan_id,entry_month,first_stop,
      CASE WHEN first_stop IN ('default_proxy','payoff_or_maturity') THEN first_stop ELSE 'censored' END event_kind,
      date_diff('month',entry_month,coalesce(stop_month,last_month))
        - CASE WHEN first_stop IN ('unknown_status','unsupported_code','ambiguous_same_month') THEN 1 ELSE 0 END duration
      FROM outcomes WHERE at_risk_at_entry"""


def life_table(histogram, entries):
    grouped={}
    for row in histogram:
        t,n=int(row['duration']),int(row['loans']);kind=row['event_kind']
        if t<0 or n<0 or kind not in ('default_proxy','payoff_or_maturity','censored') or (t==0 and kind!='censored'):
            raise ValueError('Invalid episode histogram')
        cell=grouped.setdefault(t,dict(default_proxy=0,payoff_or_maturity=0,censored=0));cell[kind]+=n
    if sum(sum(v.values()) for v in grouped.values())!=entries:raise ValueError('Episode population mismatch')
    initial_censors=grouped.get(0,{}).get('censored',0)
    risk=entries-initial_censors;s=1.0;fd=fp=0.0;result=[]
    for t in range(1,max(grouped,default=0)+1):
        cell=grouped.get(t,dict(default_proxy=0,payoff_or_maturity=0,censored=0));d=cell['default_proxy'];p=cell['payoff_or_maturity'];c=cell['censored']
        if risk<=0 or d+p+c>risk:raise ValueError('Risk-set accounting failed')
        hd=d/risk;hp=p/risk;md=s*hd;mp=s*hp;fd+=md;fp+=mp;s-=md+mp
        residual=abs(s+fd+fp-1)
        if residual>1e-12 or min(s,fd,fp)<-1e-12:raise ValueError('Probability reconciliation failed')
        result.append(dict(month=t,at_risk=risk,defaults=d,payoff_or_maturity=p,censored=c,
          monthly_default_hazard=hd,monthly_payoff_or_maturity_hazard=hp,survival=s,default_cif=fd,payoff_or_maturity_cif=fp,probability_residual=residual))
        risk-=d+p+c
    if risk!=0:raise ValueError('Episodes do not close')
    return result,initial_censors


def project_example(opening_balance,annual_coupon,term_months,hd,hp,lgd):
    def path(value):
        values=list(value) if isinstance(value,(list,tuple)) else [value]*term_months
        if len(values)!=term_months:raise ValueError('Monthly path length mismatch')
        return [float(x) for x in values]
    if not isinstance(term_months,int) or term_months<1:raise ValueError('Invalid term')
    defaults,payoffs,severities=path(hd),path(hp),path(lgd)
    if not all(math.isfinite(x) for x in [float(opening_balance),float(annual_coupon)]+defaults+payoffs+severities) or float(opening_balance)<=0 or not 0<=float(annual_coupon)<=1:
        raise ValueError('Invalid illustrative assumptions')
    if any(d<0 or p<0 or d+p>1 or not 0<=l<=1 for d,p,l in zip(defaults,payoffs,severities)):
        raise ValueError('Invalid monthly probabilities or severity')
    with localcontext() as ctx:
        ctx.prec=32
        b=Decimal(str(opening_balance));rate=Decimal(str(annual_coupon))/12
        payment=b/term_months if rate==0 else b*rate/(1-(1+rate)**(-term_months))
        s=1.;fd=fp=fm=0.;loss=ead=recovery=Decimal(0);schedule=[];pd12=0.
        for t in range(1,term_months+1):
            hd,hp=defaults[t-1],payoffs[t-1];severity=Decimal(str(severities[t-1]))
            begin=b;interest=b*rate;principal=min(b,payment-interest)
            if principal<0:raise ValueError('Negative amortization is not supported')
            b=Decimal(0) if t==term_months else b-principal
            md=s*hd;mp=s*hp;remaining=s-md-mp;mm=remaining if t==term_months else 0.;s=remaining-mm
            fd+=md;fp+=mp;fm+=mm
            defaulted=Decimal(str(md))*begin;recovered=defaulted*(1-severity);monthly_loss=defaulted*severity
            ead+=defaulted;recovery+=recovered;loss+=monthly_loss
            if t<=12:pd12=fd
            residual=abs(s+fd+fp+fm-1)
            if residual>1e-12:raise ValueError('Illustrative probabilities do not sum to one')
            schedule.append(dict(month=t,conditional_opening_balance=str(begin),conditional_closing_balance=str(b),
              survival=s,default_cif=fd,payoff_or_maturity_proxy_cif=fp,contractual_maturity_cif=fm,
              marginal_default=md,marginal_payoff_or_maturity_proxy=mp,marginal_contractual_maturity=mm,
              expected_defaulted_balance=str(defaulted),assumed_recovery=str(recovered),expected_loss=str(monthly_loss),probability_residual=residual))
        residual=abs(ead-recovery-loss)
        if residual>Decimal('0.00000001') or b!=0 or abs(s)>1e-12:raise ValueError('Illustrative cash/loss closure failed')
        return dict(default_probability_12m=pd12,remaining_life_default_probability=fd,
          remaining_life_expected_loss=str(loss),expected_defaulted_balance=str(ead),assumed_recoveries=str(recovery),
          monetary_residual=str(residual),scheduled_payment=str(payment),schedule=schedule)


def run(root,config_path):
    root=Path(root).resolve();config_path=Path(config_path);cfg=json.loads(config_path.read_text());start=time.perf_counter()
    inp=root/cfg['input_run'];prior=json.loads((inp/'descriptive_result.json').read_text())
    if prior['status']!='pass':raise ValueError('Phase2F must pass')
    out=root/'artifacts/runs/phase3'/uuid.uuid4().hex;out.mkdir(parents=True)
    c=duckdb.connect(str(out/'benchmark.db'));c.execute("SET memory_limit='1GB'");c.execute('SET threads=2')
    def lit(p):return str(p).replace("'","''")
    def query(sql):
        cur=c.execute(sql);names=[x[0] for x in cur.description];return [dict(zip(names,r)) for r in cur.fetchall()]
    c.execute(f"CREATE VIEW outcomes AS SELECT * FROM read_parquet('{lit(inp/'loan_outcomes.parquet')}')")
    if c.execute('SELECT count(*)-count(distinct loan_id) FROM outcomes').fetchone()[0]:raise ValueError('Duplicate outcome keys')
    c.execute('CREATE TABLE episodes AS '+episode_sql())
    count=c.execute('SELECT count(*) FROM episodes').fetchone()[0]
    total=c.execute('SELECT count(*) FROM outcomes').fetchone()[0]
    if total!=prior['counts']['loans']:raise ValueError('Input loan total mismatch')
    hist=query('SELECT duration,event_kind,count(*) loans FROM episodes GROUP BY 1,2 ORDER BY 1,2')
    print('Reconciling historical risk sets and competing-risk probabilities',flush=True)
    curve,c0=life_table(hist,count)
    if len(curve)<12:raise ValueError('Insufficient support for 12-month benchmark')
    pooled=curve[:12];riskmonths=sum(x['at_risk'] for x in pooled)
    hd=sum(x['defaults'] for x in pooled)/riskmonths;hp=sum(x['payoff_or_maturity'] for x in pooled)/riskmonths
    expected={x['outcome_12m']:x['loans'] for x in prior['outcomes_12m']}
    event_checks={key:sum(x[col] for x in pooled)-expected.get(key,0) for key,col in [('default_proxy','defaults'),('payoff_or_maturity','payoff_or_maturity')]}
    if any(event_checks.values()):raise ValueError('12-month event counts disagree with Phase2F')
    print('Projecting the labeled hypothetical baseline and one adverse scenario',flush=True)
    example=cfg['hypothetical_loan'];scenarios={}
    for name,assumptions in cfg['scenarios'].items():
        projected=project_example(example['opening_balance'],example['annual_coupon'],example['remaining_months'],hd*assumptions['default_hazard_multiplier'],hp*assumptions['payoff_hazard_multiplier'],assumptions['lgd'])
        schedule=projected.pop('schedule');(out/(name+'_schedule.json')).write_text(json.dumps(schedule,indent=2))
        c.execute(f"COPY (SELECT * FROM read_json_auto('{lit(out/(name+'_schedule.json'))}')) TO '{lit(out/(name+'_schedule.parquet'))}' (FORMAT PARQUET)")
        scenarios[name]=dict(assumptions=assumptions,monthly_default_hazard=hd*assumptions['default_hazard_multiplier'],monthly_payoff_or_maturity_hazard=hp*assumptions['payoff_hazard_multiplier'],**projected)
    if set(scenarios)!={'baseline','adverse'}:raise ValueError('Exactly baseline and adverse scenarios required')
    loss_delta=Decimal(scenarios['adverse']['remaining_life_expected_loss'])-Decimal(scenarios['baseline']['remaining_life_expected_loss'])
    if loss_delta<0:raise ValueError('Configured adverse example unexpectedly reduces loss')
    (out/'historical_curve.json').write_text(json.dumps(curve,indent=2))
    c.execute(f"COPY (SELECT * FROM read_json_auto('{lit(out/'historical_curve.json')}')) TO '{lit(out/'historical_curve.parquet')}' (FORMAT PARQUET)")
    c.execute(f"COPY episodes TO '{lit(out/'episodes.parquet')}' (FORMAT PARQUET)")
    result=dict(phase='3',status='pass',input_run=str(inp),event_contract='phase2f-v1',
      total_loans=total,eligible_entry_loans=count,entry_excluded=total-count,censored_before_first_interval=c0,
      historical_12m=curve[11],historical_support_months=len(curve),historical_tail_at_risk=curve[-1]['at_risk'],
      historical_max_probability_residual=max(x['probability_residual'] for x in curve),event_count_differences=event_checks,
      pooled_first12=dict(default_hazard=hd,payoff_or_maturity_hazard=hp,observed_risk_months=riskmonths),
      hypothetical_loan=example,illustrative_scenarios=scenarios,illustrative_adverse_incremental_loss=str(loss_delta),
      assumptions=cfg['assumptions'],config=cfg,elapsed_seconds=round(time.perf_counter()-start,3),timestamp_utc=datetime.now(timezone.utc).isoformat(),
      implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
      source_checksum_inherited=prior['source_checksum_inherited'],method_reference='https://cran.r-project.org/web/packages/survival/vignettes/compete.pdf',output_directory=str(out))
    c.close();(out/'benchmark_result.json').write_text(json.dumps(result,indent=2))
    lines=['# Phase 3 benchmark','',f'Historical input: `{inp}`','',f'Entry risk population: {count:,}; excluded at entry: {total-count:,}.',
      f"Historical 12-month default-proxy cumulative incidence: {curve[11]['default_cif']:.6%}.",
      f"Historical 12-month payoff-or-maturity cumulative incidence: {curve[11]['payoff_or_maturity_cif']:.6%}.",'',
      '## Hypothetical loss example — not actual cohort losses','',f"Opening balance ${example['opening_balance']:,}; remaining term {example['remaining_months']} months; coupon {example['annual_coupon']:.1%}.",'',
      '| Scenario | 12-month default probability | Remaining-life expected loss |','|---|---:|---:|']
    lines += [f"| {name} | {v['default_probability_12m']:.6%} | ${Decimal(v['remaining_life_expected_loss']):,.2f} |" for name,v in scenarios.items()]
    lines += ['',f'Illustrative adverse incremental loss: ${loss_delta:,.2f}.','', '## Assumptions and limits','']+['- '+x for x in cfg['assumptions']]
    lines += ['', 'Probabilities, risk-set counts, scheduled balance closure, and loss/recovery arithmetic passed reconciliation. The empirical curve is retrospective; the illustrative constant-rate projection is not a validated forecast.']
    (out/'benchmark_report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':'pass','result':str(out/'benchmark_result.json'),'seconds':result['elapsed_seconds']}),flush=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',default='configs/benchmark.json');a=parser.parse_args()
    run(Path(__file__).resolve().parents[2],a.config)
