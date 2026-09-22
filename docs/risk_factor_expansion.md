# Risk-factor expansion specification

## Scope and evidence

This milestone inventories candidate risk factors without reading outcome labels or fitting a model. The supplemental scan retains five snapshots: January 2011, January 2013, January 2015, December 2025 and March 2026. Profiles cover all observed snapshot loans, not the final model-eligible risk set. Late snapshots diagnose disclosure changes only; they must not supply historical predictors.

Source: local official glossary dated 2026-09-10, pages 1–4 and 11. Field numbers below are one-based. The source file has 113 columns; glossary field 114 is unavailable. Existing ingestion and accepted model artifacts are unchanged. Row keys are reconciled in both directions to accepted ingestion; source metadata stability is checked. No new whole-file content checksum or point-in-time source certification is claimed.

## Proposed factor selection

| Factor | Field(s) | Economic rationale | Initial decision and timing rule |
|---|---|---|---|
| Delinquency and modification | 40,42 | Current payment stress and restructuring | Retain benchmark features; use only snapshot observations |
| Original borrower credit score | 24 | Origination credit quality | Priority candidate; preserve unknowns and legacy definition; cannot use later replacement values |
| Original LTV | 20 | Initial collateral leverage | Priority candidate; vendor can suppress values above 97% for primary loans or unknown values, so missingness is informative; not current LTV |
| DTI | 23 | Origination repayment burden | Priority candidate; blanks may reflect disclosure rules; source does not state a complete numerical permissible range here |
| Original term | 13 | Contract length and amortization | Priority candidate; use original term, not retrospectively changed maturity |
| Occupancy | 30 | Investment versus owner-occupied risk | Priority candidate; U is reported unknown, distinct from an absent value |
| Loan purpose | 27 | Purchase and refinancing selection | Priority candidate; U is unspecified refinance, not automatically invalid |
| Loan age | 16 | Seasoning | Candidate with existing age-quality rules; nearly constant within vintage/time can confound age and calendar effects |
| Origination rate | 8 | Contract characteristics | Secondary candidate; not a rate-incentive measure without time-aligned market rates |
| CLTV | 21 | Subordinate leverage | Secondary; assess overlap with LTV and inconsistencies; do not use both mechanically |
| Property type / units | 28,29 | Collateral type and concentration | Secondary; retain sparse groups for reporting, group only using training evidence |
| Borrower count / first-time buyer | 22,26 | Household and acquisition characteristics | Secondary; unknown category and limited interpretation kept explicit |
| Origination channel | 4 | Acquisition selection and underwriting channel | Secondary; avoid causal claims |
| State / MSA | 31,32 | Geographic concentration | Reporting first; MSA 00000 is nondesignated, not missing; definitions can change; fine geography can overfit and act as a proxy |
| Mortgage insurance percentage | 34 | Potential loss mitigation | Defer from first PD challenger; coverage percentage is not actual recovery or LGD |
| Current rate | 9 | Current contract terms | Defer first challenger; contemporaneous modifications and reporting availability require separate treatment |
| Payment history | 41 | Prior arrears/cures | Derive trailing history from retained monthly panel using dates <= snapshot; require contiguous history and explicit unknowns. Do not directly parse pre-April-2020 vendor history without validating its legacy convention |
| New origination FICO | 111 | Lowest representative borrower score | Exclude from 2011/2013/2015 predictors: populated from December 2025 and not identical to legacy primary/co-borrower definitions |
| Current/issuance FICO | 112,113 | Recent scores | Exclude: glossary marks not applicable to SF loan-performance product |
| VantageScore | 114 | Alternative credit score | Absent from this 113-column file; no substitution |
| Macroeconomic conditions | External | Housing, unemployment, refinancing incentives | Separate future work; no external series acquired; require release lags and historical vintages |

## Modeling proposal

Keep the frozen smoothed categorical benchmark. The smallest challenger should be regularized multinomial logistic regression for the same three conditional 12-month outcomes, starting with existing predictors plus origination borrower FICO, LTV, DTI, term and occupancy/purpose. This is a candidate design, not a fitted or approved model. Add history features only after coverage/leakage tests. Avoid automatic all-variable expansion or outcome-driven feature screening.

Fit scaling, imputation, category grouping and regularization only on development data. Treat unknowns explicitly; retain missing indicators where justified. Do not median-impute on the full dataset, create false current collateral values or convert unresolved outcomes into event-free observations. Report conditional selection/censoring sensitivity separately from apparent complete-case performance. Freeze feature definitions before reading new evaluation labels.

## Evaluation contract

The existing 2015 held-out results have already been inspected and remain archived; they cannot become a fresh test for repeated challenger selection. The 2013 validation evidence is also previously exposed. No fresh evaluation population is declared available merely by renaming a split.

Development can use only original training-assigned loans, with a preregistered loan-disjoint internal split and trailing-feature construction restricted to snapshot time. Use this for implementation and exploratory challenger selection; record that the source vintage and original modeling decisions are already known. Freeze the final pipeline and comparison before evaluating an independently reserved acquisition cohort with a complete 12-month outcome window. That cohort is not acquired in this milestone, so external acceptance remains blocked by data availability.

Assess multiclass log loss/Brier, default discrimination with uncertainty, calibration intercept/slope or reliability plots, observed/expected defaults, censoring coverage, segment support, stability and runtime. Use paired loan-level bootstrap comparisons where appropriate; do not declare improvement from AUC alone. Predeclare acceptable calibration and minimum-event criteria using development evidence and business use before the final evaluation. Retain the benchmark if added complexity does not demonstrate a defensible improvement.

## Acceptance boundary

Completing this inventory permits a bounded feature-preparation/design milestone, not production use or automatic model promotion. Candidate eligibility remains conditional on model-risk-set profiling, complete numerical/categorical validation and point-in-time availability. Original accepted reports remain immutable.

## Measured snapshot evidence

Scan retained 654,564 records in 34.73 seconds. Duplicate/missing keys: zero. Source-to-base and base-to-source unmatched keys: zero. No conversion failures or unsupported codes in the implemented checks.

| Factor | Jan 2011 missing / records | Jan 2013 missing / records | Jan 2015 missing / records |
|---|---:|---:|---:|
| borrower_fico | 291 / 296,126 | 219 / 194,963 | 159 / 129,809 |
| ltv | 0 / 296,126 | 0 / 194,963 | 0 / 129,809 |
| cltv | 12 / 296,126 | 10 / 194,963 | 5 / 129,809 |
| dti | 2,453 / 296,126 | 1,590 / 194,963 | 1,078 / 129,809 |
| original_term | 0 / 296,126 | 0 / 194,963 | 0 / 129,809 |
| occupancy | 0 / 296,126 | 0 / 194,963 | 0 / 129,809 |
| purpose | 0 / 296,126 | 0 / 194,963 | 0 / 129,809 |
| payment_history | 296,126 / 296,126 | 194,963 / 194,963 | 129,809 / 129,809 |

Legacy FICO is entirely blank in March 2026; replacement origination FICO is entirely blank in the three early snapshots. Vendor payment history is entirely blank in those early snapshots. Use earlier monthly observations to construct history and never backfill from the late disclosure.

Evidence: `artifacts/runs/risk_factor_assessment/00fd2e4a925d4d2fa284ceb1efd01a4e/assessment_result.json`. Detailed supplemental snapshots: `artifacts/runs/risk_factor_assessment/00fd2e4a925d4d2fa284ceb1efd01a4e/snapshot_factors.parquet`. These ignored artifacts contain vendor data and are not public demo fixtures.

## Frozen feature-preparation result

Prepared 220282 original training observations. Split counts: [{"development_split": "development", "records": 179186}, {"development_split": "internal_validation", "records": 41096}]. Rule: first hex digit of MD5("expanded-v1:" + loan_id) in 0/1/2 assigns internal validation; others development. Assignment precedes label access. Missing numeric values stay null; malformed/out-of-range values retain raw text and an invalid flag. Purpose/occupancy reported U remains distinct from missing. No preprocessing fitted. Evidence: `artifacts/runs/expanded_features/2d1fe0dacf2548e883b756f23fe1fb8b/feature_result.json`. Future preprocessing must learn solely on development rows; original 2013/2015 evaluations are not fresh acceptance sets.
