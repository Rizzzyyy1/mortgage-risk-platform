# Reserved 2011Q1 external evaluation

Evaluation completed; challenger acceptance failed calibration. No model was promoted or recalibrated. The original dashboard and accepted earlier artifacts remain unchanged.

## Data and verification

The user-provided 2011Q1 file contains 36,545,962 records and 505,196 loans. The adapter found no original-cohort identifier overlap or duplicate loan-month keys. Required predictor checks and observed nonblank event-code checks passed. Features were frozen before full follow-up labels were constructed. January 2012 eligibility produced 472,056 loans; 471,968 have resolved 12-month outcomes and 88 remain censored (0.019%). There were 890 default-proxy events.

Fifteen loans first appear in July 2012, outside the nominal acquisition quarter; they cannot enter the January 2012 snapshot. Their late first appearance remains unexplained. Filename and user download route support cohort attribution, but the exact vendor release has not been independently authenticated. This is a targeted modeling adapter, not a repeat of the full balance/exposure audit.

108 tests passed in 3.70 seconds. Separate SQL recomputation from saved predictions and labels reproduced counts, expected defaults, log loss and Brier within 1e-7. All 472,056 predictions are unique, match label IDs and have finite probabilities in [0,1] summing to one. Numeric inference of exported identifiers caused no mismatch here; preserve text identifiers in future exports.

## Frozen-model results

| Measure | Candidate | Benchmark |
|---|---:|---:|
| Default AUC | 0.86808 | 0.65738 |
| Multiclass log loss | 0.51035 | 0.51503 |
| Multiclass Brier | 0.31903 | 0.32101 |
| Expected defaults | 1,131.10 | 1,379.12 |
| Observed/expected defaults | 0.78685 | 0.64534 |

The candidate improves ranking and aggregate prediction scores. Paired 95% log-loss difference interval: [-0.005014, -0.004380]; Brier: [-0.002125, -0.001834]; AUC: [0.196947, 0.225197]. These loan bootstrap intervals condition on the frozen models and one cohort, excluding training and macroeconomic uncertainty.

Five of six preregistered quantitative gates pass. Calibration fails the unchanged 0.8–1.25 observed/expected range. The diagnostic intercept/slope calculation succeeded; its status `pass` means numerical estimation succeeded, not that calibration acceptance passed. Its intercept is 0.23427 and slope 1.10296; fixed-slope intercept is -0.26061. None was applied to predictions. Reliability decile tables are saved in JSON; a reliability plot has not been generated.

## Material segment limitations

Current, unmodified loans have 608 observed versus 869.06 expected defaults (O/E 0.700). Two-month delinquent loans have 101 versus 77.61 (O/E 1.301), and worse log loss/Brier than the benchmark. Investment-property loans also have worse log loss/Brier despite better ranking. Second-home results have only 19 defaults and are flagged insufficient. These differences argue against treating a single global calibration correction as an established remedy.

FICO increased by about 0.142 development standard deviations and DTI declined by 0.186; there were no unseen categorical levels. Mean-shift checks are not a complete drift or representativeness assessment. The target remains a conditional 12-month default proxy with competing payoff/maturity, not lifetime expected loss or regulatory PD.

## Decision and next step

Engineering execution and persisted-score checks passed. Challenger external acceptance did not pass; vendor-release provenance also remains a limitation. Retain both frozen models and this external result as evidence, with neither declared production-ready. Do not tune thresholds or recalibrate on this cohort and describe the result as independent validation.

Next: prepare a bounded calibration-remediation design using development data, with a newly reserved evaluation design before any revised model is fitted. Investigate the opposite-direction current/delinquent segment errors and calendar/cohort shift first. No additional download or model fitting is authorized by this report itself.

## Reproduction and artifacts

Adapter: `python -m mortgage_risk.external_cohort`; evaluator: `python -m mortgage_risk.external_evaluate --cohort artifacts/runs/external_cohort/520d427266944462a622978247670345` (creates a new run; do not rerun merely to read results).

- Cohort: `artifacts/runs/external_cohort/520d427266944462a622978247670345/`
- Evaluation: `artifacts/runs/external_evaluation/bb53b87c6a034af29614c2c5768b4b06/`
- Evaluation files: `evaluation_result.json`, `predictions.parquet`, `verification_result.json`.
- Source receipt: `data/raw/fannie_mae_loan_performance/2011Q1.csv.receipt.json`.

Adapter runtime: 91.03 seconds; scoring/evaluation including 1,000 paired bootstrap repetitions: 26.52 seconds. Models, preprocessing and evaluation configuration remained frozen.
