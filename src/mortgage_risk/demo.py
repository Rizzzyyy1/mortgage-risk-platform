"""Deterministic, vendor-free demonstration of the existing risk calculations."""
import argparse
import hashlib
import json
from pathlib import Path
from mortgage_risk.benchmark import life_table, project_example


def build_demo(output):
    """Use invented episodes and assumptions; never load historical artifacts."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    histogram = [
        {'duration': 1, 'event_kind': 'default_proxy', 'loans': 1},
        {'duration': 1, 'event_kind': 'payoff_or_maturity', 'loans': 2},
        {'duration': 12, 'event_kind': 'censored', 'loans': 7},
    ]
    curve, initial_censors = life_table(histogram, 10)
    scenarios = {}
    for name, default, payoff, lgd in [('baseline', .001, .01, .2), ('adverse', .002, .007, .35)]:
        result = project_example(100000, .04, 120, default, payoff, lgd)
        schedule = result.pop('schedule')
        (output / f'{name}_schedule.json').write_text(json.dumps(schedule, indent=2)+'\n')
        scenarios[name] = result
    result = {
        'status': 'pass', 'data_status': 'SYNTHETIC ONLY — no vendor data or fitted estimates',
        'invented_loan_count': 10, 'initial_censors': initial_censors,
        'assumptions': {'opening_balance': 100000, 'annual_coupon': .04, 'term_months': 120,
                        'baseline': {'monthly_default': .001, 'monthly_payoff': .01, 'lgd': .2},
                        'adverse': {'monthly_default': .002, 'monthly_payoff': .007, 'lgd': .35}},
        'curve': curve, 'scenarios': scenarios,
        'limitations': ['Invented inputs; not an empirical model or estimate of actual portfolio loss.',
                        'Censoring is distinct from competing events. Payoff includes maturity.'],
    }
    (output/'demo_result.json').write_text(json.dumps(result, indent=2)+'\n')
    (output/'README.md').write_text(
        '# Synthetic demonstration\n\nAll inputs are invented; no private artifacts are required.\n\n'
        'Ten invented loans: one defaults and two pay off in month 1; seven censor in month 12. '
        'Thus the month-12 cumulative incidences are 10% default and 20% payoff, with 70% survival.\n\n'
        'The separate $100,000 hypothetical loan uses assumed hazards, 4% coupon, 120 months and '
        '20%/35% severity. It demonstrates the existing loss engine, not a fit to these ten loans.\n')
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory; existing outputs are never overwritten')
    args = parser.parse_args()
    result = build_demo(args.output)
    print(json.dumps({'status': result['status'], 'data_status': result['data_status'], 'output': str(args.output.resolve())}))


if __name__ == '__main__':
    main()
