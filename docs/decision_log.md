# Decision Log

## Purpose

This file records the consequential choices made during the project’s design phase. It is intended to preserve the rationale for important business and analytical decisions without turning the project into a broad architecture rewrite.

## Decision 1: Separate historical cohort design from current portfolio reporting

Date: current milestone

Decision: The project will maintain two distinct populations: a historical development cohort and a reporting portfolio.

Rationale:

- A historical dataset with complete follow-up is required to analyze default and prepayment paths.
- A current reporting portfolio is defined by current eligibility, not by historical event development.
- Collapsing the two populations would bias default and prepayment estimates and would misstate the target definition.

Impact:

- Portfolio reporting and model development can be evaluated separately.
- Target definitions remain coherent across time windows and loss perspectives.

## Decision 2: Use the loan-month as the operating grain

Date: current milestone

Decision: All risk metrics will be based on a monthly loan-level panel.

Rationale:

- Mortgage performance is naturally observed monthly. 
- Monthly panels align with delinquency, exposure, and survival logic.
- The monthly grain fits the Fannie Mae reporting structure and the project intention to model default, prepayment, and exposure over time.

Impact:

- Event definitions are easier to audit.
- Risk metrics can be aggregated across the portfolio without losing time dimension.

## Decision 3: Treat default and prepayment as competing risks, not independent outcomes

Date: current milestone

Decision: The project will model default and prepayment as competing events in the historical panel.

Rationale:

- A loan can only have one primary event in a period under a coherent logic.
- Default and prepayment are not additive in the same way that probability and severity are separate.
- This avoids double-counting and supports a cleaner survival process.

Impact:

- The benchmark remains interpretable.
- Loss and scenario analysis are less likely to overstate portfolio risk.

## Decision 4: Keep 12-month default, remaining-life expected loss, and scenario loss distinct

Date: current milestone

Decision: The project will maintain separate output definitions for 12-month default risk, expected lifetime loss, and scenario-conditioned loss.

Rationale:

- These metrics answer different business questions.
- Combining them would obscure the risk perspective and create confusing benchmark outputs.
- It is consistent with the project charter and the analytical commitments in the plan.

Impact:

- Reporting and model review remain disciplined.
- Benchmark outputs are easier to reconcile and explain.

## Decision 5: Treat the local sample as verified physical evidence and the vendor glossary as the authoritative check for the inspected fields

Date: current milestone

Decision: The project will keep sample validation separate from official full-source verification.

Rationale:

- The sample proved the panel structure and monthly pattern.
- The official glossary and file-layout document were used to validate the inspected field mappings.
- The full historical package remains a separate access and verification step.

Impact:

- The project is evidence-based without overstating certainty.
- Field claims are explicit about what is verified and what remains provisional.

## Decision 6: Do not advance to model fitting until the cohort and metric definitions are locked

Date: current milestone

Decision: The project pauses before final model fitting and broad stress simulations.

Rationale:

- The project has a bounded execution order by design.
- The current milestone is to settle definitions and portfolio design.
- This preserves the evidence chain and prevents an unsupported jump into analytics.

Impact:

- The project remains within scope.
- It keeps a clear handoff between source assessment and analytical modeling.

## Phase 3 — 2026-09-20

Phase 3 uses a nonparametric competing-risk benchmark and an explicitly hypothetical loss track because validated real remaining maturity and severity are unavailable. This preserves an end-to-end testable calculation without imputing masked balances or calling code01 pure prepayment. It adds no modeling dependencies and uses a versioned JSON configuration. Future models must compare against this baseline.

## Phase 4B — 2026-09-20

Phase 4B selected a dependency-free smoothed multinomial risk table as the first interpretable fitted model. It uses current delinquency and modification state; numeric features remain unused until justified. Validation selected alpha=10 over 100/1000 and the constant reference. Final-test results improve ranking and proper scores, with segment and censoring limits preserved. No gratuitous challenger or test-driven tuning was added.

## Risk-factor inventory decision — 2026-09-21

Prioritize legacy origination borrower FICO, LTV, DTI, term, occupancy and purpose for an interpretable challenger design, subject to model-risk-set validation. Do not combine legacy and December-2025 replacement score definitions. Early vendor history is absent; derive history only from prior monthly records. Preserve the exposed 2015 test and require a separately reserved cohort for external challenger acceptance. No model fitted. See risk_factor_expansion.md for evidence and evaluation boundaries.

## Internal challenger decision — 2026-09-21

Logistic C=1 selected for exploratory continuation by preregistered internal log loss, not promoted. Refit smoothed benchmark used identical development records. Optimization failure triggered a numerical solver change only; no validation-driven feature/grid expansion. Calibration and sparse groups remain concerns; preserve a separately reserved cohort for external evaluation. See challenger_evaluation.md.

## Reserved-cohort evaluation protocol — 2026-09-21

Frozen 2011Q1 primary cohort / January 2012 snapshot / January 2013 horizon before data access. Candidate and benchmark remain fixed. Review thresholds are project judgments, not regulatory standards; external-cohort evaluation cannot trigger refitting or threshold adjustment. Readiness is pending source acquisition. See external_evaluation.md.


## 2026-09-22 — Withhold challenger acceptance after external evaluation

Frozen 2011Q1 evaluation improved ranking and aggregate scoring but failed the preregistered calibration gate (O/E 0.78685, minimum 0.8). Preserve thresholds, models, predictions and prior dashboard. No tuning or promotion on this external cohort. Segment deterioration requires investigation; future remediation needs separate development and fresh evaluation. See external_evaluation_results.md and its verification artifact.


## 2026-09-22 — Retain unchanged candidate after bounded calibration experiment

Development-only cross-fitted intercept adjustment improved internal log loss by only 9.34e-7, below the preregistered 1e-6 tie threshold, and slightly worsened Brier. Retain unchanged model and stop calibration search as planned. No external acceptance claim, model promotion or new download. Report this negative result and plan multi-vintage redevelopment separately from research-platform delivery. Evidence: calibration_remediation/6059d958cd634f14bc0882f861036b98.
