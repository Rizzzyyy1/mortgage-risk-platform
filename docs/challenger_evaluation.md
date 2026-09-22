# Expanded-risk challenger: internal evaluation

**Verdict: promising exploratory challenger; not externally validated or promoted.**

Only original January 2011 training-assigned loans were used. The existing 2013 validation and 2015 test were not accessed. The outcome definition remains conditional on an observed 12-month default, payoff/maturity or event-free outcome.

## Design

Four numeric predictors (legacy borrower FICO, original LTV, DTI and term), plus categorical delinquency/modification group, occupancy and purpose. Development-only median imputation and standardization; numeric missing indicators and explicit unseen-category indicators. No class reweighting, oversampling, probability recalibration or history backfilling. No causal interpretation of coefficients.

The model uses multinomial softmax probabilities with L2 regularization. C = 0.01, 0.1, 1.0 was fixed before fitting; smaller C means stronger regularization. Each benchmark was refitted on identical known-outcome development loans. Lowest internal-validation multiclass log loss selects the candidate.

The initial L-BFGS attempt stopped at its iteration limit and was rejected. Newton-Cholesky converged in 8–9 iterations with unchanged features, grid and splits. JSON coefficient/preprocessing export reproduced library probabilities within 1e-10. Solver choice reference: https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html

## Population

Development: 179,186 total; 179,152 known outcomes and 34 unresolved. Internal validation: 41,096 total; 41,085 known outcomes and 11 unresolved. No unresolved record was relabeled event-free. Censoring prevalence bounds remain in the result JSON.

| Metric | Refit smoothed benchmark | Selected logistic C=1 |
|---|---:|---:|
| Default AUC | 0.615006 | 0.862052 |
| Multiclass log loss | 0.414615 | 0.408056 |
| Multiclass Brier | 0.238238 | 0.236587 |
| Expected defaults | 127.336147 | 130.501926 |
| Observed/expected defaults | 1.146572 | 1.118757 |

Observed defaults: 146. Paired log-loss difference (challenger minus benchmark): -0.00656; fixed-prediction 95% bootstrap interval [-0.00775, -0.00547]. The same validation data selected the candidate, so this interval excludes selection/fitting uncertainty and is not confirmatory.

## Material remaining concerns

- Overall expected defaults (130.50) remain below observed defaults (146). Current/unmodified loans have 112 observed versus 92.76 expected, an O/E ratio of 1.207.
- The two-month-delinquent segment has only 13 loans and nine defaults; its discrimination estimate is unstable and does not justify a segment claim.
- Same-date, same-vintage internal validation cannot establish temporal or cross-cohort robustness. Original training outcomes also informed earlier development; this is not a newly untouched test.
- Current-vintage source revisions and the conditional complete-case target remain limitations.
- No recalibration on this selected validation set and no extension to portfolio lifetime losses or production decisions.

## Next acceptance gate

Freeze this candidate and its transformations. Acquire/identify a separately reserved cohort under the appropriate data access conditions, validate schema and score semantics, and define an out-of-time evaluation protocol before opening its outcomes. If additional calibration development is needed, use separate development evidence and preserve the new final evaluation set.

## Verification and artifacts

102 tests passed; dependency check passed. The converged comparison took 4.84 seconds. Models/preprocessing are JSON; validation predictions are Parquet. Detailed inputs, protocol and hashes are saved alongside the result. No pickle loading is required.

Run: `artifacts/runs/challenger/f94a630d661f4ea28f7a21c4a567c74c`

Dependencies now include pinned scikit-learn and numerical packages. Python metadata minimum raised to 3.11 to match scikit-learn; the tested environment remains Python 3.14/macOS ARM64. Earlier clean-install evidence predates this dependency expansion and is not a new clean-install certification.
