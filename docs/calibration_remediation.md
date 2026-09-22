# Calibration remediation design

## Finding and decision

The frozen candidate underpredicts defaults in original internal validation (146 observed / 130.50 expected; O/E 1.119), but overpredicts in the reserved cohort (890 / 1,131.10; O/E 0.787). Observed default frequency fell from 0.3554% to 0.1886%. The candidate already predicts a lower average risk for the later cohort, but not enough. These are conditional, different-population comparisons; they do not identify whether calendar conditions, cohort composition, censoring or model form caused the shift.

Current/unmodified external loans are overpredicted while two-month delinquent loans are underpredicted. Therefore a single global downward multiplier would worsen at least one material segment. No external fitted correction is accepted. A development-only correction may also move in the wrong direction externally; improvement is not promised.

## Bounded next experiment

Freeze the original feature set and C=1. Within the original development partition only, generate five loan-grouped out-of-fold predictions, fitting preprocessing and model inside each fold. Fit two multinomial intercept offsets to those OOF predictions, with event-free offset fixed at zero. Normalize all three probabilities together, retaining competing-event coherence. Do not independently rescale default probability or fit on in-sample predictions.

Compare only the unchanged model and this adjusted model on the existing original internal-validation partition. Select by multiclass log loss, retaining unchanged on a tie within 1e-6. That partition has already informed development; this is explicitly exploratory. Report default calibration, payoff calibration, Brier, discrimination and supported segments alongside selection. Reject numerical failure. Do not add segment calibrators, interactions, searches or threshold changes if this experiment fails.

The final base fit remains on the original development partition so its calibration and internal comparison have a consistent training scope. OOF-based calibration transferred to that final fit has estimation uncertainty; disclose it and require fresh external confirmation. This modest experiment tests whether development-only adjustment helps, not whether historical regime shift is solved.

## Fresh evaluation reservation

Reserve the 2012Q1 primary cohort, January 2013 snapshot and subsequent outcomes through January 2014. This is a design reservation, not a claim that files or outcomes were inspected. Validate vendor release/layout, chronological availability, source codes, feature compatibility, and no loan-ID overlap with either prior cohort before scoring. Preserve all 2011Q1 results; those outcomes cannot become a fresh independent test again.

Carry forward the original quantitative gates (100 defaults, unresolved <=1%, O/E 0.8–1.25, paired log-loss upper confidence limit <0, Brier no worse, AUC deterioration <=0.02). Keep the frozen original benchmark for continuity and compare the revised candidate with the unchanged candidate as well. Material segment degradation prevents promotion even if aggregate gates pass. Freeze fitted artifacts before opening fresh outcomes. No automatic download, production use or dashboard replacement.

## Evidence and completion

This milestone completed diagnosis and froze the bounded experiment; it did not fit a remedy or validate a revised model. Existing numerical results were reused without raw-data rescans. Configuration: `configs/calibration_remediation.json`. Review evidence: `artifacts/runs/calibration_review/8f1a25b45bc443e7adb7ae552a44e8fe`.

Next: implement and verify the two-candidate development-only experiment, then decide whether fresh external acquisition is warranted. If adjustment offers no credible benefit, retain the failed external result and document the model's restricted use rather than continue tuning indefinitely.


## Executed result — 2026-09-22

The five-fold experiment completed in 8.11 seconds. All folds converged in 8–9 iterations. Fold-specific preprocessing used fitting rows only. 179,152 known-outcome development loans produced out-of-fold probabilities; 34 unresolved development outcomes remained excluded and reported. Evaluation used 41,085 known-outcome internal-validation loans, with 11 unresolved reported separately.

| Metric | Unchanged | Adjusted |
|---|---:|---:|
| Multiclass log loss | 0.4080560884 | 0.4080551547 |
| Multiclass Brier | 0.2365873455 | 0.2365878210 |
| Default AUC | 0.862052 | 0.862052 |
| Expected defaults (146 observed) | 130.5019 | 130.8187 |
| Observed/expected | 1.118757 | 1.116049 |

The log-loss improvement is 0.0000009337, below the frozen 0.000001 tie threshold. The unchanged candidate is retained. Brier slightly deteriorates, and the adjustment raises default estimates; it does not establish a solution to the earlier external overprediction. No revised model was scored on external outcomes. The previous external calibration failure remains unresolved.

Default and payoff offsets were 0.00274385 and -0.00008273 relative to event-free. Exported adjusted coefficients reproduce adjusted probabilities within 2.23e-16. The adjusted JSON is an experimental artifact, not a selected or promoted model. Development source hashes match the original run, unchanged internal log loss reproduces, and held-fold counts reconcile. Full suite: 110 tests passed in 3.49 seconds. Initial test invocation encountered sandbox write restrictions; authorized rerun passed.

Evidence: `artifacts/runs/calibration_remediation/6059d958cd634f14bc0882f861036b98/result.json` and `verification_result.json`.

### Current next step

The bounded experiment is complete and its stop rule applies. Do not continue searching calibrators or download the reserved quarter automatically. Prioritize a reviewer-facing model limitation and monitoring report that presents the existing internal/external evidence, applicability restrictions, and conditions for future multi-vintage redevelopment. The project can be delivered as a reproducible research platform with a transparently failed model-acceptance gate; it cannot be described as a calibrated production mortgage-risk model. Any broader redevelopment needs a separate chronological multi-vintage design, with sufficient pre-evaluation history and an untouched final cohort.
