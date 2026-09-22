# Correctness and reproducibility record

## Current evidence — 2026-09-22 (updated: factual correction to segment-review wording)

Developer verification, not independent institutional model validation. Full current-environment suite last passed **184 tests** (110 model/dashboard-track tests plus 74 new tests across the default-to-workout linkage, default-anchor exposure, realized-loss-profile, vendor-method-reconciliation, vendor-official-loss-calculation, multi-cohort-adapter, redevelopment-model and segment-acceptance-review modules: 21 + 5 + 5 + 9 + 9 + 5 + 4 + 16). External stored predictions independently recomputed in SQL agree with recorded metrics; the **original** challenger's calibration acceptance failed on 2011Q1 (immutable). A **redeveloped** model, with calibration offsets fit on 2012Q1, passed all six preregistered aggregate quantitative gates on the untouched 2013Q1 cohort. A bootstrap-quantified segment review (`segment_acceptance_review.py`, reusing the saved 2013Q1 predictions with no refit) found the same segment-level miscalibration pattern — current/unmodified (99.8% of loans) and FICO 720+ (87% of loans) overstate risk with 95% confidence intervals entirely below the 0.8 floor; two-month-delinquent and FICO<660 understate risk, with point estimates above 1.25 whose CIs overlap it — **overall model acceptance is qualified/pending review, not an unconditional pass.** A prior version of this narrative reversed the risk-direction wording and overstated how many segments' intervals lay entirely outside the band; both are corrected here and throughout the active documentation (`docs/project_status.md` has the full correction record). Engineering verification does not resolve model or economic limitations.

Separately: the PD-calibration redevelopment (2012Q1/2013Q1 newly acquired) reused the original challenger's training population and predictor set unchanged, selected the same `logistic_1.0` model via a development-only chronological comparison on 2011Q1, fit intercept calibration on 2012Q1 alone (accepted against a frozen 1e-6 tie threshold), and evaluated once on 2013Q1 with no retuning. Full detail, the four separate verdicts (engineering / discrimination-calibration / final acceptance / LGD-lifetime-loss limitations), the quantified segment review and the acceptance matrix: `docs/redevelopment_plan.md` and `docs/final_report.md`.

Separately from the PD/calibration track: a corrected default-to-workout linkage (`loss_workout_linkage.py` v2) follows every default episode to its last supportable resolution — 24.1% of the 8,750 accepted-cohort default episodes reach disposition, exactly matching the 2,108 loans with recorded loss fields. Default-anchor exposure is quantified for 94.1% of episodes (`default_anchor_exposure.py`), and a labeled descriptive (not LGD) realized-loss profile covers the 1,880-loan complete-case subset (`realized_loss_profile.py`), now reconciled against Fannie Mae's own official loss methodology (`vendor_method_reconciliation.py`): six of nine methodology items resolved, one derivable under a disclosed convention, two genuinely open pending the vendor's own R code. None of this is a severity/LGD model or an actual-cohort loss estimate; see `redevelopment_plan.md` for the full evidence chain and the specific blockers to promotion.

Current results: `external_evaluation_results.md`, `calibration_remediation.md`, `redevelopment_plan.md`; reviewer decision and monitoring specification: `professional_review.md`. Older counts below describe historical runs, not current acceptance.

## Historical verified status — Phase 6, 2026-09-21

- **Engineering: PASS. Statistical: qualified single-cohort conditional benchmark. Actual-cohort economic losses: NOT READY.**
- Consolidated seven accepted milestone reports with SHA-256 manifests and checked run linkage/population consistency. No ingestion, model fitting, recalibration or new held-out evaluation.
- Independently recalculated saved test AUC, log loss, Brier and expected defaults in SQL; maximum metric difference 2.99e-11, tolerance 1e-9.
- Verified 194 historical risk-set/probability recursions. Recalculated loss/PV cashflows directly and attribution through all 24 driver permutations rather than the original subset-weight calculation; monetary/attribution residuals below 1e-8 dollars.
- Offline monitoring replay covers training, validation and test snapshots only. PSI: 0, 0.00310, 0.00639. No live monitor or operational backtest is claimed.
- Current/unmodified segment (0 / N) triggers a judgmental calibration warning; modified-current (0 / Y) and two-month delinquent (2 / N) groups have insufficient support under the monitoring rules.
- **78 tests passed in 2.66s** before a report-format-only correction. Final corrected-report validation run passed in **0.044 seconds**. No numerical behavior changed in that correction.
- Thresholds were chosen after earlier results were visible. They are retrospective project judgments, not regulatory limits or validated alarm rules.

Report: `artifacts/runs/phase6/6c871180c0cc4afeb49b3fe755337725/validation_report.md`

Evidence: `artifacts/runs/phase6/6c871180c0cc4afeb49b3fe755337725/validation_result.json`

Next: Phase 7 dashboard and executive communication, using saved accepted aggregates with explicit historical/model/illustrative labels. Do not present synthetic losses as actual portfolio economics or hide qualification flags.



## Historical verified status — Phase 2D, 2026-09-20

This section supersedes stale current-status statements in the historical milestone notes below.

- Full-quarter engineering acceptance: **PASS**, for the retained 15-column dataset and checks specified here.
- Vendor codes: **nonblank domains PASS; blank modification semantics NEED REVIEW**.
- Economic exposure: **NOT READY**; reported balances must not be treated as unmasked economic exposure.
- Completed input run: `7a30ef59b2e74c518133ddf5923c92c9`. No raw re-ingestion or interrupted-job restart was performed.
- Verified 20,983,277 rows, 323,174 loans, 195 months (2010-01 through 2026-03), zero duplicate loan-month keys, zero missing required keys/dates.
- Database and Parquet column names/types, monthly record counts, missing-balance counts, and current-balance totals agree.
- Original/current retained raw balance strings: zero conversion errors and zero raw-to-typed differences. Reporting dates also agree with their raw strings.
- Existing independent raw audit: zero monthly count/balance differences across 195 months. Provenance limitation: that audit lacks its own embedded source checksum; linkage relies on prior project evidence. No new source-file hash was claimed.
- Category totals reconcile for each month and category dimension.
- 194 consecutive-month bridges, zero failures, maximum residual 0.00, tolerance 0.01. SQL DECIMAL arithmetic precedes cent formatting. Bridge missing-entry/exit behavior is regression-tested.
- Diagnostics: 331,406 balance-increase flags across 314,356 loans; 33 monthly-gap flags across 28 loans. Flags can overlap; they are not event labels. Detailed data is Parquet, JSON preview is capped at 100.
- Zero unsupported nonblank delinquency/modification/termination codes. CAS-only 97/98 termination codes are excluded from SF rules.
- 306,417 blank modification flags all coincide with populated termination codes. This establishes an observed association, not a vendor-documented permission to impute N. No blank delinquency values observed.
- Important correction: glossary PDF page 1, field 12 explicitly states first-six-month UPB masking. Earlier claims that the glossary contains no masking convention are superseded. The retained dataset lacks loan age/origination date needed to identify the affected rows precisely. PDF page 4 supports fields 40/42/44; both pages were visually inspected.
- Tests: **27 passed in 2.03s**, current environment. No new clean-environment reproduction is claimed.
- Acceptance execution: **74.799 seconds**. Two prior attempts failed on SQL aliases in the new runner and are not acceptance evidence; both were corrected.

Evidence:
- Acceptance: `artifacts/runs/phase2d_acceptance/0906ff5ce1dd458dba3a892f8ec375c3/acceptance_result.json`
- Full summary: `artifacts/runs/phase2d_acceptance/0906ff5ce1dd458dba3a892f8ec375c3/monthly_summary_20260920_151123_7fc98f87/monthly_portfolio_summary.json`
- Detailed diagnostics: `artifacts/runs/phase2d_acceptance/0906ff5ce1dd458dba3a892f8ec375c3/monthly_summary_20260920_151123_7fc98f87/diagnostics.parquet`

Implementation changes: SQL bridge aggregation; bounded diagnostic Parquet and preview; nonexclusive diagnostic flags; rejection of ambiguous monthly-table selection; real historical code counters; reusable `python -m mortgage_risk.phase2d_acceptance` runner. The runner is intentionally scoped to this fixed acceptance case, not a general pipeline interface.

Next bounded step: define and verify exposure eligibility using the documented masking rule and investigate terminal modification blanks before any model/loss claims. Preserve reported raw values. No models, losses, dashboard, commits, or publication were added.

## Historical milestone records (retained for provenance)

## Verification status summary

- Existing tests passed: yes
- Independent raw-data comparison: yes, completed and saved
- Clean-environment reproduction: yes, completed and saved
- Unresolved analytical limitations: yes, retained and documented

## Existing tests passed

Command run in the project-local environment:
- `./.venv/bin/python -m pytest -q`

Result:
- 17 passed in 1.81s

Artifact:
- [artifacts/runs/clean_env_repro/pytest_clean_env.txt](../artifacts/runs/clean_env_repro/pytest_clean_env.txt)

## Independent raw-data comparison (completed)

Check performed:
- direct reading of the unchanged source file at [data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv](../data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv)
- no imports from the project parsing or aggregation functions
- Decimal-based monthly total calculations using the validated source field mapping for current actual UPB
- comparison against the saved production monthly output at [artifacts/runs/sample_ingest/fff6c8f729be4b37b1584bd34906f92e/sample_monthly.db](../artifacts/runs/sample_ingest/fff6c8f729be4b37b1584bd34906f92e/sample_monthly.db)

Artifact:
- [artifacts/runs/independent_raw_compare/20260920T003000Z/raw_comparison.json](../artifacts/runs/independent_raw_compare/20260920T003000Z/raw_comparison.json)

Actual result:
- overall_status: pass
- raw_record_count: 757
- distinct_loan_count: 8
- distinct_month_count: 132
- duplicate_loan_month_keys: 0
- zero_balance_count: 53
- missing_balance_count: 0
- month_total_differences: 0

Interpretation:
- the raw CSV and the production sample database agree on all monthly total values at cent precision for the verified sample scope
- there are no raw-data mismatches in the month totals used by the pipeline

## Clean-environment reproduction (completed)

Temporary environment created using the documented lock workflow:
- .venv_audit_20260919_193000

Commands executed in that environment:
- `python -m pip install -r requirements.lock`
- `python -m pip install -e .`
- `python -m pytest -q`
- `mortgage-risk sample-ingest --input data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv --output-dir artifacts/runs/clean_env_repro/sample_ingest`
- `mortgage-risk monthly-summary --db artifacts/runs/clean_env_repro/sample_ingest/96f65e57c31c45f2ba8314b4801f2c52/sample_monthly.db --output-dir artifacts/runs/clean_env_repro/monthly_summary`

Result summary:
- pytest: 17 passed in 2.20s
- sample ingest: pass
  - artifact: [artifacts/runs/clean_env_repro/sample_ingest/96f65e57c31c45f2ba8314b4801f2c52/sample_ingest_result.json](../artifacts/runs/clean_env_repro/sample_ingest/96f65e57c31c45f2ba8314b4801f2c52/sample_ingest_result.json)
- monthly summary: pass
  - artifact: [artifacts/runs/clean_env_repro/monthly_summary/monthly_summary_20260920_001641/monthly_portfolio_summary.json](../artifacts/runs/clean_env_repro/monthly_summary/monthly_summary_20260920_001641/monthly_portfolio_summary.json)

## Actual comparison differences

There were no month-level differences between the independent raw CSV calculation and the saved production monthly totals.

The only explicit source-level distinction still retained is:
- zero balances are observed raw-source balances and remain distinct from missing balances
- no claim is made that every zero balance represents valid economic exposure or a fully usable balance for downstream analytics

## Unresolved analytical limitations

- zero-balance rows are source-observed values, not validated usable exposure
- no historical cohort beyond the sample has been acquired or validated
- no default, prepayment, expected-loss, scenario, or model work is claimed in this phase
- the project remains bounded to the sample and a historical-data pilot only after the official cohort is inspected and validated

## Historical-data pilot readiness

The sample pipeline is ready for a tightly scoped historical-data pilot only if the incoming historical files are inspected against the official schema and the same reconciliation rules are applied before any broader analytical claims are made.

This does not constitute full-dataset scalability, a validated market portfolio, or a proven economic exposure model.

## Phase 2E implementation verification — 2026-09-20

## Historical verified status — Phase 2E, 2026-09-20

This section supersedes current-status claims below; earlier sections are retained as milestone evidence.

- Eligibility engineering: **PASS**. Preserved 20,983,277 records; exact ordinal/loan/month joins have no missing keys, duplicates, or unmatched records. All 195 monthly counts and reported-balance totals reconcile with zero differences.
- Masking interpretation: **PARTIALLY UNRESOLVED**. Six-month source rule verified; numeric boundary not claimed settled. See target definitions for conservative policy and exclusions.
- Vendor modification blanks: **SEMANTICS UNRESOLVED**, preserved. All 306,417 blanks are terminal; preceding observed status is N for 304,604, Y for 1,807, and unavailable for 6. This association does not authorize imputation.
- Descriptive readiness: **QUALIFIED**, for eligible reported exposure with exclusions. Full-cohort economic exposure and modeling readiness are not established.
- No invalid numeric-age or date conversions in the final supplement. 32,160 negative ages remain signed and unresolved, not mislabeled conversion failures.
- Tests: **40 passed in 2.09s**. Final supplemental-reuse run: **37.577 seconds** (excludes the earlier CSV scan).

- eligible_positive_reported_balance: 17,703,222 records
- masked_early_life: 1,504,715 records
- masking_or_age_unresolved: 1,437,002 records
- terminal_record: 306,637 records
- unmasked_zero_unexplained: 31,701 records

Evidence: `artifacts/runs/exposure_eligibility/7b7177c3473345d091dd1cd19d24799e/eligibility_result.json`

Detailed eligibility: `artifacts/runs/exposure_eligibility/7b7177c3473345d091dd1cd19d24799e/exposure_eligibility.parquet`

Validated supplement: `artifacts/runs/exposure_eligibility/7b7177c3473345d091dd1cd19d24799e/supplement_validated.parquet`

One CSV scan produced the original supplement. Its first parsing attempt failed the join guard; saved raw date strings were reparsed without rescanning. An intermediate successful run was superseded to retain signed negative ages correctly. Prior runs remain unchanged. The source checksum is inherited from accepted ingestion, not freshly recomputed. Phase 2D database, Parquet, and acceptance outputs were not modified.

Next bounded milestone: descriptive portfolio analysis using this eligibility layer, with exclusions and unresolved zeros visible; establish precise event thresholds and observation-window rules before the first benchmark. No models, losses, dashboard, new quarters, commits, or publication were added.


This is implementation verification, not an independent external audit.

## Phase 2F — 2026-09-20

Phase 2F developer verification passed: 50 tests in 2.21s, zero category and input monthly reconciliation differences, all loans assigned one retrospective outcome. Evidence: artifacts/runs/phase2f/64d49545a270488ca411e6a731e59465/descriptive_result.json. The first execution failed on a SQL alias; corrected runner passed a new end-to-end fixture and the full run. This is not independent external model validation.

## Phase 3 — 2026-09-20

Phase 3 developer verification: 62 tests passed in 2.34s. Full run 0.231 seconds; event-count differences zero; max probability residual 6.661338147750939e-16; risk-set and monetary closure pass. Report: artifacts/runs/phase3/8e2217375a004a2b915b6e639f68b476/benchmark_report.md. Historical probability estimates rely on censoring assumptions; synthetic loss arithmetic is not validation of actual economic predictions.

## Phase 4A — 2026-09-20

Phase 4A developer verification: 64 tests passed in 2.51s, preparation 1.263 seconds; zero selected-loan duplication or overlap, non-overlapping label windows, future-label mutation leaves exported features unchanged. No predictive performance measured. Evidence: artifacts/runs/phase4a/346469500fc34c66b760aeb21def6ffe/design_result.json.

## Phase 4B — 2026-09-20

Phase 4B developer verification: 68 tests in 2.46s; runtime 0.784s. Selection saved before test loading; test AUC 0.6981, fixed-score interval 0.6458–0.7501, O/E 1.070. Proper scores improve on the constant reference. Qualification: only 77 test defaults, single vintage, conditional complete-case target and nonuniform segment calibration. Evidence: artifacts/runs/phase4b/59e0a87732b248b6b65060391077041f/model_result.json.

## Phase 5 — 2026-09-20

Phase 5 developer verification: 73 tests passed in 2.76s. Baseline reproduced; all probability/cashflow and attribution closures passed; 18 sensitivity cases and configured direction checks passed. Full run 0.043 seconds. This verifies hypothetical calculations, not actual-cohort forecast accuracy. Evidence: artifacts/runs/phase5/c4ba96b0e7f94dc88a33ab2c8db78d86/stress_result.json.

## Phase 7 presentation verification — 2026-09-21

82 tests passed (2.46 seconds); final JavaScript syntax passed. Dashboard generation reconciles accepted aggregate categories and loss totals and rejects modified report fingerprints. Browser verification was blocked by an unavailable admin-policy check; visual and interaction acceptance remains pending. No earlier numerical acceptance is superseded. Evidence: `artifacts/runs/phase7/c39af0a7a17c43d4b5b7785c5388531a/verification_result.json`.

### Phase 7 manual acceptance follow-up

The user confirmed “they work” after receiving the dashboard interaction and layout checklist. Phase 7 is accepted using that user-reported manual verification alongside the existing 82 passing tests. No screenshot review or automated browser pass is claimed. Original verification evidence is preserved; the separate acceptance receipt is `artifacts/runs/phase7/c39af0a7a17c43d4b5b7785c5388531a/user_acceptance.json`.

## Phase 8 release verification

Clean non-editable installation and dependency check passed. The vendor-free test run passed 83 tests and explicitly skipped one optional vendor integration; the original workspace passed all 84. The deterministic demo ran outside the source checkout without private artifacts. Ignore checks passed; no files were tracked. Evidence: `artifacts/runs/phase8/162fda1e4d854b779ae1d475f87e22f8/release_result.json`. This validates the synthetic review workflow, not portability of the cohort-specific historical rebuild.

## Professional research hardening

92 tests passed in 2.54s. Input integrity and semantic failure cases added; accepted numerical results preserved. The new dashboard HTML matches the manually accepted output byte for byte. Hash receipts detect changes, not source authenticity. Evidence: `artifacts/runs/professional_review/81aa3684f31d416792bb2adbd4b3bfb2/review_result.json`. Independent validation and production readiness remain unclaimed.
