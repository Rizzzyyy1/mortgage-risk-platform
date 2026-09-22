# Reserved-cohort evaluation protocol

## Status and intended question

Evaluation completed on 2026-09-22; calibration acceptance failed and no model was promoted. See external_evaluation_results.md. The frozen design and thresholds below remain unchanged. The readiness command alone is not analytical acceptance.

Question: does the frozen expanded-risk candidate improve the same conditional 12-month target on a later acquisition cohort, with acceptable calibration and stable reporting? The result will still not establish broad cross-cycle or production suitability.

## Frozen design

- Source: Fannie Mae primary acquisition/performance cohort 2011Q1, acquired through the authorized vendor route. Save the original file under data/raw/fannie_mae_loan_performance/2011Q1.csv. Do not rename another quarter to this name.
- Snapshot: January 2012. Outcome window: subsequent monthly observations through January 2013, following the existing event/censoring definitions. The choice approximately parallels the seasoning of the original 2010Q1/January-2011 development design; it does not perfectly control seasoning and calendar confounding.
- Population: all otherwise eligible snapshot loans with current delinquency 0–2, no earlier competing stop, and the same at-risk-entry/event contract. Quantify exclusions and unresolved follow-up; never relabel incomplete outcomes as event-free.
- Candidate: logistic C=1; benchmark: smoothed risk table alpha=10. Use saved development-only transformations and weights exactly. No external-cohort median, scaling, category fitting, hyperparameter search, retraining or recalibration.
- Preserve the original 2013/2015 evaluations and all prior accepted runs. Check reserved-cohort identifiers against all original-cohort loans, not only development rows. Quarantine unexpected overlap before evaluating labels.

## Required data gate before scoring

Verify product, cohort, release, checksum and glossary/layout against actual files. New vendor packages may have different column counts: do not force the prior 113-column parser on a changed layout. Reconcile records/keys and validate the required snapshot fields, code semantics, feature conversion and source timing. In particular, keep legacy primary-borrower FICO distinct from later lowest-borrower score disclosures. If the snapshot field is not genuinely available, report incompatibility rather than backfill from later records.

Build features using snapshot or earlier observations only. Freeze feature outputs and record missing/invalid/unseen category rates before joining outcomes. Score only after data-quality gates pass. Compare candidates on identical known-outcome records; retain and report the unresolved population and default-rate bounds separately. Record unavailable or out-of-range inputs without silently dropping loans.

## Preregistered review criteria

Machine-readable settings and their fingerprints are in configs/external_evaluation.json and configs/external_evaluation_integrity.json. These are project judgments chosen after internal results but before reserved-cohort access, not industry mandates or a statistical power calculation.

- Fewer than 100 observed defaults or more than 1% unresolved outcomes: insufficient evidence for acceptance; still report results.
- Primary paired loan-bootstrap log-loss difference (candidate minus benchmark): 95% upper bound below zero; 1,000 repetitions, seed 2026. No candidate selection on this evaluation.
- Multiclass Brier must not exceed the benchmark; default AUC degradation must not exceed 0.02. Report paired uncertainty rather than just point metrics.
- Overall observed/expected defaults must lie within 0.8–1.25; also report default calibration intercept/slope and reliability plots. A passing aggregate cannot override material segment deterioration.
- Segment results by delinquency, credit-score bands, LTV, occupancy and purpose require explicit sample/event counts. Unsupported segments are labeled insufficient, not passed. Investigate deviations; no threshold tuning after seeing results.
- Produce drift, missingness and unseen-category diagnostics, coefficient/preprocessing versions, source lineage, runtime and scoring parity evidence.

A failure triggers investigation or further development on separate data, not tuning on this cohort and calling the rerun independent. Retain the benchmark unless a documented review supports challenger acceptance. No automatic production or dashboard promotion.

## Next action

Preserve the failed external calibration result. Design remediation on development data and reserve fresh evaluation data before fitting any revised model; do not reuse this cohort as an untouched test. See external_evaluation_results.md for current evidence and limitations.
