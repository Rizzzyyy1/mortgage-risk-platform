# Mortgage Risk Platform — Agreed Project Plan

## User intent

Build this project collaboratively as an outstanding, detailed, structured,
clean professional portfolio project for credit risk, risk analytics, and
financial data science applications. Preserve this structure as the baseline
and improve it when implementation needs justify changes. Do not introduce
complexity merely to expand the tool stack.

## Workspace boundaries

- Follow the root AGENTS.md. Synced files under sources/ are read-only references.
- Place implementation in mortgage-risk-platform/ when implementation begins.
- This plan records the agreed design; it does not mean implementation has begun.

## Agreed structure

```text
mortgage-risk-platform/
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── .vscode/
│   ├── settings.json
│   └── extensions.json
├── configs/
│   ├── data.yaml
│   ├── portfolio.yaml
│   ├── models.yaml
│   └── scenarios.yaml
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   └── demo/
├── sql/
│   ├── staging/
│   ├── quality/
│   ├── transformations/
│   └── analytics/
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_portfolio_analysis.ipynb
│   ├── 03_default_prepayment.ipynb
│   ├── 04_loss_severity.ipynb
│   └── 05_stress_analysis.ipynb
├── src/
│   └── mortgage_risk/
│       ├── __init__.py
│       ├── ingestion/
│       ├── data_quality/
│       ├── features/
│       ├── portfolio/
│       ├── models/
│       ├── losses/
│       ├── scenarios/
│       ├── validation/
│       ├── monitoring/
│       └── pipeline.py
├── app/
│   ├── main.py
│   ├── pages/
│   └── components/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
│   ├── project_charter.md
│   ├── data_dictionary.md
│   ├── target_definitions.md
│   ├── methodology.md
│   ├── assumptions_register.md
│   ├── decision_log.md
│   └── limitations.md
├── reports/
│   ├── figures/
│   ├── portfolio_analysis/
│   ├── model_validation/
│   └── executive_memos/
├── artifacts/
│   └── runs/
└── .github/
    └── workflows/
        └── checks.yml
```

## Refinements to apply as we build

- Add versioned schemas and source manifests for data contracts, provenance,
  source release dates, coverage, and checksums. Keep large/restricted data out
  of Git. Never overwrite raw inputs.
- Validate configuration and use a dependency lockfile once the package manager
  is chosen. Keep secrets out of code and configuration committed to Git.
- Provide one documented execution entry point with explicit pipeline stages.
  Notebooks and the dashboard should call reusable package logic, not duplicate
  transformations or financial calculations.
- Save each run with its configuration, code/data/model/scenario versions,
  reporting date, metrics, logs, and reconciliation evidence.
- Distinguish generated run outputs from curated reports intended for reviewers.
- Use small synthetic fixtures for meaningful automated tests and a public demo.
- Create directories and modules when needed rather than scaffolding empty layers.
- Record consequential architecture changes and their rationale in the decision log.

## Analytical commitments

- Intended primary source: Fannie Mae loan performance data, subject to source
  assessment and access. Initial stack: Python, SQL, DuckDB, Parquet, one dashboard.
- Define portfolio population, reporting date, default, loss perspective,
  recoveries, censoring, modifications, and eligible exposures before modeling.
- Keep 12-month default risk, remaining-life expected loss, and scenario losses
  distinct while sharing a coherent monthly modeling foundation.
- Model default and prepayment as competing events; align loss severity with the
  chosen default definition and avoid double-counting prepayment effects.
- Use chronological evaluation, prediction-time feature availability, calibration,
  segment analysis, and transparent assumptions about future economic conditions.
- Include a CECL-inspired educational methodology; do not claim regulatory
  compliance, production certification, or independent validation of self-review.
- Make stress transmission, uncertainty, limitations, and result lineage visible.

## Delivery order and completion gates

1. Data and portfolio: definitions settled; counts and balances reconcile.
2. Models: coherent probabilities; reproducible chronological evaluation and calibration.
3. Lifetime loss and stress: hand-checkable examples pass; losses reconcile and
   economic sensitivities can be explained.
4. Review and presentation: validation, monitoring replay, dashboard, executive
   memo, and reproducible reviewer instructions.

Start with a small end-to-end cohort, benchmark, scenario, and loss table before
expanding scale. Emphasize defensible decisions and evidence over feature count.
