# Final report — research-project handoff, 2026-09-22

This is the single concise handoff document for this project. It summarizes what is done, what is qualified, what is blocked, and how to reproduce it. It does not replace the detailed evidence documents it links to, and it does not assert production model acceptance.

## Business question

Can historical Fannie Mae Single-Family loan performance data support (a) an interpretable 12-month conditional default-risk model, (b) a transparent illustrative lifetime-loss/stress framework, and (c) a defensible, quantified account of what actually happens after a loan defaults (workout, exposure, realized loss) — while being explicit about what remains unvalidated at each step? This is a research/demonstration platform, not an underwriting, pricing, provisioning or regulatory-capital system.

## Data and population

- **Sources:** the official Fannie Mae SF Loan Performance sample (108 fields), and two full acquisition-quarter historical files, 2010Q1 (5.71 GB, 20,983,277 records, 323,174 loans, 195 months, Jan 2010–Mar 2026) and 2011Q1 (9.99 GB, 36,545,962 records, 505,196 loans), both SHA-256 checksummed at ingestion. A vendor glossary/file-layout PDF (dated 2026-09-10) is the field-definition source.
- **2012Q1 and 2013Q1 are not local** as of this report. They are needed for the calibration and final-test roles of the redevelopment design (`configs/multi_cohort_redevelopment.json`) and remain the user's separate action via their authenticated vendor account.
- **Development cohort:** 2010Q1, entered January 2011, 12-month outcome window. **External/frozen cohort:** 2011Q1, entered January 2012, outcome window through January 2013.

## Methods

- **Ingestion and reconciliation:** bulk DuckDB/Parquet ingestion; 194 consecutive-month balance bridges, zero failures (`docs/methodology.md`, Phase 2D).
- **Exposure eligibility:** conservative masking policy (ages 1–5 masked, 0/6 unresolved, 7+ potentially unmasked); reported balance never treated as usable exposure without passing this check (`target_definitions.md`, Phase 2E).
- **Event/outcome contract:** default proxy = first 90+ day delinquency or credit-related exit (02/03/09/15); payoff/maturity = exit 01; other exits and unresolved states censor. One first-stop event per loan (`target_definitions.md`, Phase 2F).
- **Benchmark and challenger models:** a transparent smoothed-categorical benchmark (Phase 4B) and a regularized multinomial challenger (FICO/LTV/DTI/term/delinquency/occupancy/purpose) compared internally and then evaluated on the frozen 2011Q1 cohort.
- **Loss-workout track (this session):** a full post-default trajectory classifier, default-anchor exposure quantification, and a descriptive realized-loss profile — a separate track from the PD model, built entirely from already-accepted evidence (no new ingestion).

## Engineering evidence

- 184 tests passing in the current environment (`docs/validation_audit.md`); a prior clean Python 3.14/macOS ARM64 install (no system site-packages) passed 109 tests with one intentional vendor-data skip, and a vendor-free synthetic demo ran outside the source tree.
- Wheel content check (this session, rebuilt for a distributable-contents inspection): 32 members, all Python package code and metadata — no CSV/Parquet/database/PDF/.env files bundled.
- No commits, no publication, no deployment. Git index remains empty (0 commits).

## Model findings: original failure, then redevelopment (2010-2011Q1 → 2012Q1 → 2013Q1)

**Original challenger, immutable historical record:**
- Development-only comparison (same-date, exploratory): AUC 0.862 vs. 0.615 benchmark; better log loss and Brier.
- Frozen external evaluation (2011Q1, 472,056 eligible loans, 890 defaults): AUC 0.868 vs. 0.657 benchmark, better log loss/Brier — **but calibration O/E 0.787 failed the preregistered 0.8–1.25 gate**, with opposite-direction segment errors (current/unmodified overpredicted, two-month-delinquent underpredicted) that no single correction factor could fix.
- A development-only intercept-calibration experiment (cross-fitted within 2010Q1 alone) improved log loss by only 9.34e-7, below the 1e-6 tie threshold — no meaningful remedy. This result and the failed evaluation above remain on record unchanged.

**Redevelopment with 2012Q1/2013Q1, newly acquired.** The three cohorts below are loan-disjoint but play three different, non-interchangeable evidential roles — they are not three independent tests of the final calibrated model:
- **2011Q1 — development-validation only.** Trained on the same 2010Q1 rows, selected among the same candidate grid using the full 2011Q1 population as an out-of-cohort validation set: **the same `logistic_1.0` model was selected again**, exactly reproducing its original 2011Q1 metrics. 2011Q1 shaped model selection; it is not a test of the final artifact.
- **2012Q1 — calibration-fitting only** (911 defaults, intercept offsets against a frozen 1e-6 tie threshold): **accepted.** Aggregate O/E moved from 0.690 to ~1.0, but the dominant current/unmodified segment improved (O/E 0.625→0.933) while the small two-month-delinquent segment got *worse* (O/E 1.212→1.468) — reported honestly, not corrected further, per the frozen no-segment-specific-adjustment rule. 2012Q1's outcomes were used to fit the model; it is not a test of it either.
- **2013Q1 — the one final evaluation** (836 defaults, no retuning), the only genuinely untouched cohort for this frozen model: **all six preregistered quantitative gates passed**, including aggregate calibration (O/E **0.8139**, within [0.8, 1.25] but close to its floor). **The same opposite-direction segment pattern found on 2011Q1 and 2012Q1 reproduces here** — current/unmodified and high-FICO loans overpredicted, two-month-delinquent and low-FICO loans underpredicted. Seeing the pattern recur across all three cohorts' different roles is evidence the pattern is structural rather than one cohort's noise; it is not three independent validations of the model, and it does not extend this result to other vintages or economic regimes.
- **Segment review, quantified with bootstrap uncertainty (2026-09-22, this milestone):** see "Segment calibration review" below — the deviation is not sparse noise; it is tight and well-powered in the two largest population strata.
- **Scope of what this supports:** aggregate 12-month default-proxy risk-ranking for 2010–2013 primary-conforming acquisition vintages resembling this development lineage. It does **not** support a claim of uniform segment calibration, validity for other vintages/economic regimes, or any severity/loss coupling. **No model has been promoted**; the historical dashboard still shows only the original benchmark and illustrative stress chain. Full detail: `docs/redevelopment_plan.md`.

## Segment calibration review, quantified and corrected (2026-09-22)

**Correction note (2026-09-22):** an earlier version of this section, and of the equivalent passages in `docs/professional_review.md`, `docs/project_status.md`, `docs/redevelopment_plan.md` and `README.md`, (1) stated that the model would "understate risk for current/unmodified, high-FICO loans and overstate risk for delinquent/low-FICO loans" — this had the direction backwards, and (2) described the two-month-delinquent and FICO<660 intervals as lying "entirely above the ceiling" or "entirely outside" the [0.8,1.25] reference band, when their 95% intervals actually overlap it. Both are corrected below. This correction is wording-only: no prediction, metric, gate result or run artifact was changed. The immutable run evidence was always correct; only the hand-written narrative was wrong.

O/E is observed defaults divided by expected defaults. **O/E below 1 means the model predicted more defaults than occurred — it overpredicted, i.e. overstated, risk for that segment. O/E above 1 means the model predicted fewer defaults than occurred — it underpredicted, i.e. understated, risk.**

The passing aggregate gate on 2013Q1 does not by itself establish overall model acceptance: the frozen criteria (`docs/external_evaluation.md`, `docs/calibration_remediation.md`) state that "a passing aggregate cannot override material segment deterioration" and that "material segment degradation prevents promotion even if aggregate gates pass." Neither document specifies a formal, quantitative segment-level gate, so the [0.8, 1.25] band below is shown as a **diagnostic reference** (the same band already frozen for the aggregate gate), not a retroactively-applied pass/fail rule. This milestone quantifies the deterioration with a paired bootstrap over the already-saved 2013Q1 predictions and labels (`src/mortgage_risk/segment_acceptance_review.py`; no refit, no recalibration, no new scoring — every point estimate was cross-checked to match the frozen `final_evaluation_result.json` exactly before any interval was computed). Each interval is an independent per-segment 95% interval, not adjusted for multiple comparisons and not a simultaneous guarantee across every segment reported.

Delinquency status and FICO band are two different, overlapping partitions of the **same** 658,447-loan population — their percentages below each sum to 100% *within their own partition* and must not be added across partitions (e.g. "99.8% + 87%" is not a claim about 186.8% of the book; these are two different ways of cutting the same population):

| Segment | Loans | % of this partition | O/E | Direction | 95% bootstrap CI | Point est. outside [0.8,1.25]? | CI vs. band |
|---|---|---|---|---|---|---|---|
| Current/unmodified (delinquency 0) | 656,937 | 99.8% | 0.736 | overprediction | [0.675, 0.797] | Yes | **entirely_below** — interval lies wholly under the 0.8 floor |
| One-month delinquent | 1,366 | 0.2% | 0.996 | overprediction (trivial) | [0.849, 1.155] | No | entirely_within |
| Two-month delinquent | 144 | 0.02% | 1.414 | underprediction | [1.217, 1.598] | Yes | **overlaps_ceiling** — lower bound (1.217) sits inside the band, below 1.25 |
| FICO 720+ | 573,236 | 87.0% | 0.628 | overprediction | [0.561, 0.694] | Yes | **entirely_below** — interval lies wholly under the 0.8 floor |
| FICO 660-719 | 75,522 | 11.5% | 0.968 | overprediction (trivial) | [0.877, 1.067] | No | entirely_within |
| FICO <660 | 9,359 | 1.4% | 1.299 | underprediction | [1.104, 1.507] | Yes | **overlaps_ceiling** — lower bound (1.104) sits inside the band, below 1.25 |

**Only the two overprediction segments (current/unmodified, FICO 720+) have intervals that lie entirely outside the reference band, which is what supports a claim of separation at 95% confidence.** Both cover the large majority of the population by loan count (99.8% and 87% of their respective partitions) with tight intervals — a large sample size, not noise, is producing the precision. The two underprediction segments (two-month-delinquent, FICO<660) have point estimates above the 1.25 ceiling with enough defaults (87 and 140, both above the project's own 20-default insufficient-support threshold) to be a genuine finding, not sparse evidence — but their 95% intervals' lower bounds sit just inside the band, so the evidence does not establish separation from the band with the same confidence as the overprediction segments. This distinction is reported, not glossed over. Evidence: `artifacts/runs/segment_acceptance_review/d1971a46201f4a9a9db4f31a16c0bd24/segment_acceptance_review_result.json` (16 tests in `tests/test_segment_acceptance_review.py`, including boundary-case tests for the direction and band-relationship classifications used to build this table).

**Consequence for intended use.** For a ranking-only research use (ordering loans by relative risk, not reading off calibrated probabilities), this is a materially smaller concern — AUC discrimination (0.875) is strong and stable across the cohorts evaluated so far, though this reflects the model's overall AUC and is not a claim that ranking is equally strong within every individual segment (segment-level AUC has not been examined in this milestone), nor a claim of validity for other vintages. For any probability-based use — pricing, loss provisioning, capital allocation or lending decisions that would read the model's output as a calibrated default probability — this segment pattern means the model would systematically **overstate** risk for a current/unmodified, high-FICO loan (the majority of the book by loan count) and systematically **understate** risk for a delinquent or low-FICO loan, in ways an aggregate O/E of 0.81 does not disclose on its own. The model is not accepted for probability-based use.

## Acceptance matrix (2026-09-22)

| Area | Status | Basis |
|---|---|---|
| Engineering verification | **Passed** | New-cohort ingestion, checksums, loan-ID disjointness and adapter/join checks all passed for 2012Q1 and 2013Q1; 184 tests passing |
| Aggregate quantitative gates | **Passed** (all six preregistered gates) | 2013Q1, untouched: AUC 0.875 vs. 0.639 benchmark; aggregate O/E 0.814, inside [0.8, 1.25] but close to its floor; Brier and paired log-loss both favor the candidate |
| Segment calibration | **Material concerns remain** | Current/unmodified (99.8% of loans) and FICO 720+ (87% of loans) both overpredict risk, with 95% CIs entirely below the 0.8 floor; two-month-delinquent and FICO<660 both underpredict risk, with point estimates above 1.25 whose CIs overlap it — see table above. No formal segment-level gate was pre-specified; this is a diagnostic finding, not a failed formal test |
| Overall model acceptance | **Qualified/pending** | Aggregate gates passed, but the frozen criteria say a passing aggregate cannot override material segment deterioration, and a reviewer decision on that finding has not been made |
| Research package | **Deliverable, with limitations disclosed** | This report, the acceptance matrix and the quantified segment review together are the deliverable; research-delivery completion is not the same claim as model approval |
| Production probability-based use | **Unsupported** | Segment pattern above means calibrated-probability reads would be systematically wrong for the majority of the book in one direction and for delinquent/low-FICO loans in the other |
| Predictive LGD / actual-portfolio lifetime loss | **Not validated** | No severity model, no hazard-path or recovery-timing coupling; the retrospective loss measurement below remains a separate, complete, uncoupled track |

**Overall model acceptance: qualified, pending a reviewer decision on the segment finding above — not an unconditional pass.** The six preregistered aggregate gates did pass, and that is a real, evaluated-once result; but the frozen criteria this project set for itself explicitly say a passing aggregate cannot override material segment deterioration, and that deterioration is present, well-supported, and directionally opposite between the segments containing the vast majority of the loan population and the smaller delinquent/low-FICO segments. **Completing this research delivery is not the same thing as approving the model** — the package is ready for reviewer evaluation; the model itself is not approved for any use beyond the ranking-only research scope stated above.

## Workout, exposure and loss-methodology findings (separate track from the PD model above)

- **Default-to-workout linkage (corrected, v2):** of 8,750 accepted-cohort default episodes, followed to their last supportable resolution: 24.1% reach an actual disposition (exactly matching the 2,108 loans with recorded loss fields — a strong internal cross-check), 47.1% pay off/mature after defaulting, 19.6% cure with no redefault observed, 7.7% exit some other way (ultimate loss genuinely unresolved by this dataset), 1.4% remain open, and 0.02% end on an unresolved same-month data conflict. An earlier version of this analysis (v1, preserved for provenance) undercounted disposition at 18.6% by stopping at the first redefault or reporting gap; v2 corrected this after hand-tracing real loan histories.
- **Default-anchor exposure:** 94.1% of all default episodes (93.1% of disposed episodes) have a directly usable reported balance at the original default month; 5.6% have no supported exposure evidence at all. A terminal-month zero balance is never used as anchor exposure; a same-vintage prior balance is offered only as a separately labeled, explicitly aged proxy.
- **Realized-loss profile:** for the 1,880-loan subset with both complete loss-field accounting and supported exposure (21.5% of all default episodes), the undiscounted net loss is median $22,824 (21.5% of exposure), with 23.2% net gains and 3.2% loss-exceeds-exposure cases, neither clamped.
- **Reconciled against Fannie Mae's own official loss methodology**, then **retrieved and traced the actual official R code** (`LPPUB_StatFile_Production.R`, via a Wayback Machine snapshot of the current product page — no authentication required or bypassed). Confirmed the vendor's own pre-computed net-loss/severity/accrued-interest fields are CRT-only; implemented the exact official Net Loss formula, including a rate carry-forward fix that raised interest-cost coverage from 11.4% to 100%, a 35bp guaranty-fee deduction, and confirmation that Principal Forgiveness is an additive loss term. Confirmed the vendor's own credit-event trigger is a **180-day** delinquency threshold, not this project's 90-day default-proxy anchor — the two agree on the same month for only 1.1% of loans, directly confirming that matching exposure balances do not establish matching event definitions. Applying the vendor's own zero-fill population rule (never to exposure) widens the eligible population from 1,880 to all 2,108 disposed loans, preserved as a separately named variant alongside the unchanged original figure. A real off-by-one column bug was caught (implausible 98000%-rate values) before being reported, fixed, and guarded against recurrence. See `docs/redevelopment_plan.md`.

## Supported versus unsupported claims

**Supported by current evidence:**
- Engineering reconciliation (ingestion, balances, event contract) is verified and reproducible across all four acquisition-quarter cohorts (2010Q1, 2011Q1, 2012Q1, 2013Q1).
- The redevelopment model (same predictors/training population as the original challenger, calibration offsets fit on 2012Q1) improves discrimination over the benchmark and **passed all six preregistered aggregate quantitative gates, including calibration, on the untouched 2013Q1 cohort** — a genuine, evaluated-once result, not a promise.
- That pass holds in aggregate only, and is now quantified rather than described qualitatively: the same opposite-direction segment miscalibration found on 2011Q1 (development-validation) and 2012Q1 (calibration-fitting) reproduces on 2013Q1 (final evaluation), with the current/unmodified segment (99.8% of loans) and FICO 720+ segment (87% of loans) overpredicting risk with 95% intervals entirely below the 0.8 floor, and the two-month-delinquent and FICO<660 segments underpredicting risk with point estimates above 1.25 whose intervals overlap it — see "Segment calibration review" above. **Overall model acceptance is qualified/pending a reviewer decision on this finding, not an unconditional pass.**
- The 24.1% default-to-disposition rate, 94.1% exposure-availability rate, and the realized-loss/vendor-official figures (for their specific, non-representative disposed-loan subsets) are internally reconciled, cross-checked against Fannie Mae's own retrieved R code, and reproducible from existing accepted data.

**Not supported, and not claimed:**
- No approved production PD model. The passing 2013Q1 aggregate evaluation is real but does not by itself establish acceptance — manual review of the segment finding above, uniform-segment calibration evidence, and a broader vintage/economic-cycle test (2011Q1/2012Q1/2013Q1 are loan-disjoint but not three independent tests of the final model) are still absent. No cross-cohort calibration beyond the frozen 2012Q1 fit described above.
- No LGD or severity model. The realized-loss figures above are explicitly descriptive, for a reason now traced to the vendor's own code, not just inferred from prose: the vendor's own "credit event" (180-day delinquency threshold) is a different event than this project's default-proxy anchor (90-day), agreeing on the same month for only 1.1% of disposed loans — so even a byte-exact loss formula does not by itself validate this project's own event definition. Forgiveness (field 64) is SF-applicable and confirmed an additive loss term in the official formula; it was checked directly and is zero for all 2,108 disposed loans in this specific cohort. Foregone interest now uses the vendor's own rate-carry-forward logic (100% coverage, up from 11.4%), with a 35bp guaranty-fee deduction the earlier approximation lacked.
- No actual-cohort lifetime portfolio loss estimate. No validated monthly hazard path. No macro/scenario transmission model — the Phase 5 stress figures remain an explicitly hypothetical $100,000-loan illustration, not measured portfolio economics.
- No regulatory compliance or independent institutional validation is claimed (SR 26-2 is a design reference only).

## Reproduction instructions

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -r requirements-build.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation .
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
.venv/bin/python -m mortgage_risk.demo --output artifacts/runs/synthetic-demo-001
```

This reproduces the vendor-free engineering/test evidence. Reproducing the vendor-data results (ingestion, models, workout linkage, redevelopment) requires the private 2010Q1/2011Q1/2012Q1/2013Q1 files in `data/raw/fannie_mae_loan_performance/` and re-running the specific module referenced by each artifact directory in `docs/project_status.md`/`docs/redevelopment_plan.md`; most modules are run as `python -m mortgage_risk.<module>` and pin their own accepted-input run directories rather than accepting arbitrary arguments.

## Remaining work

- **2012Q1 and 2013Q1 are now acquired and used** (development-validation and final-test roles, `configs/multi_cohort_redevelopment.json`); this line is retained to show the prior blocker is resolved, not still open.
- **Segment-specific miscalibration, now quantified with bootstrap uncertainty** (current/unmodified and high-FICO overpredict risk, 95% CIs entirely below the 0.8 floor; two-month-delinquent and low-FICO underpredict risk, point estimates above the 1.25 ceiling but 95% CIs overlapping it) is unresolved and reproduces across 2011Q1, 2012Q1 and 2013Q1's different evidential roles. No segment-specific fix was attempted; the frozen protocol explicitly excluded that. **Treat any further segment-model redevelopment as a separate, new project**, requiring development-only changes and a freshly reserved final-test cohort — 2013Q1 is now a used, disclosed result and cannot become an untouched test again.
- **Severity/LGD model:** the retrospective loss analysis is reconciled against the official vendor formula, but the vendor's own "credit event" (180-day) differs from this project's PD default-proxy anchor (90-day), so the two are not coupled and a predictive LGD model remains unbuilt.
- **Actual-cohort lifetime loss:** blocked on the severity model above plus a validated monthly hazard path (the 12-month classifier must not be converted directly into one) plus recovery-timing and exposure-path evidence for the 75.9% of default episodes that never reach disposition.

## Defensible intended-use statement and delivery status (2026-09-22)

**Intended use this evidence supports:** aggregate 12-month default-proxy risk **ranking** (not calibrated probability output) on 2010-2013 primary-conforming acquisition-vintage loans resembling this development/calibration lineage, for research and reviewer demonstration only. It does not support pricing, provisioning, capital or lending decisions, uniform-segment calibration claims, other-vintage or other-economic-regime validity, or any severity/LGD/lifetime-loss coupling.

**Is research delivery complete?** Yes, for this milestone's scope: the redevelopment model was frozen, calibrated once, evaluated once on an untouched cohort, and the resulting segment concern was quantified with uncertainty rather than left as a qualitative caveat. Reviewer-facing documentation (this report, the acceptance matrix, `docs/professional_review.md`) reflects that quantified finding.

**Is overall model acceptance qualified or pending?** **Qualified/pending.** The six preregistered aggregate gates passed on 2013Q1 — a real result — but the frozen criteria this project set for itself say a passing aggregate cannot override material segment deterioration, and that deterioration is both real (reproduces across all three cohorts' different roles) and well-supported (tight bootstrap intervals in the segments holding the large majority of the loan population). A human reviewer decision on whether the model is acceptable for its stated ranking-only research use, given this disclosed limitation, has not been made by this milestone and is the genuinely necessary next step before any further use — not a promise that more data or another redevelopment cycle would resolve it.

## Document map

| Topic | Document |
|---|---|
| Reviewer presentation (8 slides) | [claude.ai/artifact/DtfvvZiAmzV8GdToQU5jFJ](https://claude.ai/artifact/DtfvvZiAmzV8GdToQU5jFJ) |
| Milestone-by-milestone status | `docs/project_status.md` |
| Loss/workout/exposure evidence chain | `docs/redevelopment_plan.md` |
| Field mappings and output schemas | `docs/data_dictionary.md` |
| Model inventory, controls, reviewer walkthrough | `docs/professional_review.md` |
| Test/reproducibility record | `docs/validation_audit.md` |
| Event/target definitions | `docs/target_definitions.md` |
| Setup and release limitations | `docs/release_guide.md` |
