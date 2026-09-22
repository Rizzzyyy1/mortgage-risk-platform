# Project Status

## Current status — reviewer handoff and presentation, 2026-09-22

This milestone is presentation and handoff, not further model development. The research build was already complete within its stated scope (see the correction entry immediately below); this milestone packages it for a reviewer.

**What was produced:**
- **[Reviewer presentation](https://claude.ai/artifact/DtfvvZiAmzV8GdToQU5jFJ)** (`https://claude.ai/artifact/DtfvvZiAmzV8GdToQU5jFJ`): an 8-slide deck built entirely from figures already verified in `docs/final_report.md`/`docs/project_status.md` — business question and intended use; the four-cohort chronological design; pipeline architecture and reproducibility controls; the three model versions (historical benchmark, original challenger, redeveloped candidate) with AUC explained as discrimination, not accuracy; the aggregate-vs-segment calibration finding with exact O/E, 95% CIs and band relationships; the workout/exposure/retrospective-loss evidence; the seven-row acceptance matrix; and reproduction instructions plus future work. No new figures were computed; every number was cross-checked against the source documents before publishing. Private; not yet shared.
- **README.md**: new "For reviewers: start here" section linking the presentation, final report, historical dashboard (with its private-artifact caveat restated), `docs/professional_review.md`, and the synthetic-demo instructions.
- **`docs/professional_review.md`**: the "Five-minute reviewer walkthrough" section extended into explicit where-to-start / what-to-demonstrate / which-results-to-explain / which-limitations-to-disclose / how-to-run-the-synthetic-demo subsections, with an explicit restatement that the historical dashboard requires private artifacts not bundled in this package and shows only the original frozen benchmark.

**Reviewer-experience check:** the historical dashboard's Model view already states it shows a single smoothed risk-table benchmark "selected on validation data; evaluated once on separate, later loans" — it was not silently replaced with the redeveloped/calibrated candidate, and the walkthrough above now says so explicitly for a reviewer who has not read every document.

**Handoff hygiene (not a comprehensive security audit):** inspected `.gitignore` and the untracked file listing. `data/raw/` (44 GB of vendor CSVs), `artifacts/runs/` (5.7 GB of run outputs), `.venv/`, `.venv_audit_20260919_193000/`, `build/`, `*.duckdb`/`*.sqlite*`, and `.env`/`.env.*` (except `.env.example`, which contains no secrets) are all correctly excluded — verified with `git check-ignore -v` on each path and confirmed none of them appear in `git status --short`. `data/demo/`, `notebooks/` and `reports/` are intentionally un-ignored but currently empty. The proposed source-control scope is exactly the 16 untracked top-level entries already listed by `git status --short` (`.env.example`, `.gitignore`, `AGENTS.md`, `PROJECT_PLAN.md`, `README.md`, `app/`, `configs/`, `docs/`, `pyproject.toml`, `requirements-build.lock`, `requirements.in`, `requirements.lock`, `scripts/`, `sql/`, `src/`, `tests/`) — no private data, credentials, local-environment files or generated databases among them. No files were staged, committed, published, deployed or redistributed.

**Verification performed:** no executable code changed this milestone, so the test suite was not rerun (still 184 passing, per the correction entry below); the presentation build itself validated its own HTML-subset content at publish time with no reported errors, and every figure on every slide was cross-checked against the source documents listed above before publishing.

**Final research-delivery status:** complete. **Remaining delivery blocker:** none for this milestone's scope — the one substantive open item is the human reviewer decision on the qualified/pending segment-calibration finding, which is a review action, not an engineering or documentation blocker. **Further statistical redevelopment (segment-specific remediation, a new held-out cohort, predictive LGD, actual-portfolio lifetime loss) is a separate, new project**, out of scope for this completed research-handoff milestone, and would require a freshly reserved final-test cohort since 2013Q1 is now a used, disclosed result.

## Historical status — factual correction: reversed risk direction and overclaimed CI separation, 2026-09-22

The bounded acceptance-review milestone immediately below (now retitled "historical, corrected") contained two prose errors in its hand-written narrative. The underlying evidence (saved run artifacts, JSON, Parquet) was never wrong; only the English description of it was. No refit, recalibration, threshold change or reopened model selection was performed to produce this correction — it is documentation-only, plus one targeted, low-risk code addition described below.

**Errors found and corrected:**
1. **Reversed risk direction.** `docs/final_report.md`'s "Consequence for intended use" paragraph said the model would *understate* risk for the current/unmodified and high-FICO segments and *overstate* it for the delinquent/low-FICO segments. O/E = observed/expected: O/E below 1 (current/unmodified 0.736, FICO 720+ 0.628) means the model predicted *more* defaults than occurred — it **overstated** risk. O/E above 1 (two-month-delinquent 1.414, FICO<660 1.299) means it predicted *fewer* defaults than occurred — it **understated** risk. The sentence had both halves backwards; corrected.
2. **Overclaimed confidence-interval separation.** Several passages (`README.md`, `docs/final_report.md`, `docs/professional_review.md`, `docs/project_status.md`, `docs/redevelopment_plan.md`) stated or implied that all four material segments' 95% bootstrap intervals lie "entirely outside" the [0.8, 1.25] reference band. Checked against the exact saved intervals: only the two overprediction segments (current/unmodified [0.675, 0.797]; FICO 720+ [0.561, 0.694]) lie entirely outside the band (entirely below 0.8). The two underprediction segments' intervals — two-month-delinquent [1.217, 1.598] and FICO<660 [1.104, 1.507] — have point estimates above the 1.25 ceiling but lower bounds *inside* the band (1.217 and 1.104, both below 1.25), so they overlap the band rather than lying entirely outside it. Overlap does not establish acceptable calibration; it means the evidence does not demonstrate separation from the band with the same 95% confidence as the two overprediction segments. Corrected everywhere it appeared.

**Verification performed:** re-read `artifacts/runs/segment_acceptance_review/9b9453a2d995423393cdebb418b8cb42/segment_acceptance_review_result.json` directly and recomputed each interval's relationship to [0.8, 1.25] by hand before touching any document. To prevent this specific class of error recurring, added two small, pure, tested classification functions to `src/mortgage_risk/segment_acceptance_review.py` — `oe_direction` (over/underprediction from O/E) and `ci_vs_band` (entirely_below / entirely_above / entirely_within / overlaps_floor / overlaps_ceiling / spans_band) — so future narrative is generated from a checked classification rather than by hand. Re-ran the module (deterministic, same seed, same saved predictions/labels — not a refit) to attach these fields to a new evidence run; the prior run directory is untouched. Added 13 new tests covering O/E below/equal/above 1 and every CI-vs-band boundary case (`tests/test_segment_acceptance_review.py`, 16 tests total). Full suite: **184 tests passed** (up from 171). `sh scripts/check_release.sh` rerun clean.

**Files corrected:** `README.md`, `docs/final_report.md`, `docs/professional_review.md`, `docs/project_status.md` (this file), `docs/redevelopment_plan.md`, `docs/validation_audit.md`, `docs/data_dictionary.md`. The prior "Current status" entry below is retitled to "historical, corrected" and its inaccurate sentence is annotated in place rather than silently rewritten, per the project's evidence-preservation rule; the immutable JSON run artifacts it references were never inaccurate.

**Verdicts (unchanged in substance, now stated precisely and without directional errors):**
- Engineering verification: **passed.**
- Aggregate quantitative gates: **passed** (all six, on the untouched 2013Q1 cohort).
- Segment calibration: **material concerns remain** — current/unmodified (99.8% of loans) and FICO 720+ (87% of loans) overstate risk with 95% CIs entirely below the 0.8 floor; two-month-delinquent and FICO<660 understate risk, with point estimates above 1.25 whose CIs overlap the band.
- Overall model acceptance: **qualified/pending** a reviewer decision — not an unconditional pass, and not a rejection.
- Research package: **deliverable, with limitations disclosed.** Completing this delivery is not the same claim as approving the model.
- Production probability-based use (pricing, provisioning, lending): **unsupported.**
- Predictive LGD and actual-portfolio lifetime loss: **not validated** — untouched by this milestone, remains a separate, complete, uncoupled retrospective-loss track.

**Final research-delivery status:** complete for this scope. No model promotion, new cohort acquisition, commit, publication or deployment was performed. This milestone stops here.

## Historical status, corrected — bounded acceptance review and research-project wrap-up, 2026-09-22

**Correction note:** the segment-concern bullet below originally said the two-month-delinquent interval was "entirely above the 1.25 ceiling." It is not — its 95% CI is [1.217, 1.598], which overlaps the band (1.217 < 1.25). See the correction entry above for the precise, code-verified classification of every segment. The bullet is left otherwise as originally written, for an accurate record of what was said and when.

Read AGENTS.md, the frozen redevelopment/evaluation protocols and the three redevelopment run artifacts (model selection, calibration, final evaluation) before this milestone. No refit, recalibration, threshold change or feature selection was performed against the final-test result; this milestone is read-only verification and documentation.

- **Verified the acceptance claim.** "All six quantitative gates passed" is a true, narrow claim (`artifacts/runs/redevelopment_final_evaluation/21a27da4febc4ebdbeba08698e5b18f1/final_evaluation_result.json`: `all_quantitative_gates_pass: true`). It is not the same claim as segment acceptability or overall intended-use acceptance. The frozen criteria (`docs/external_evaluation.md`, `docs/calibration_remediation.md`) already state a passing aggregate cannot override material segment deterioration — this milestone quantified whether that deterioration is material rather than leaving it as a qualitative caveat.
- **Quantified the segment concern** (`src/mortgage_risk/segment_acceptance_review.py`, new): a paired bootstrap over the already-saved 2013Q1 predictions and labels, rejoined only to recover segment labels, with every point estimate cross-checked to exactly match the frozen `final_evaluation_result.json` before any interval was computed (no refit, no recalibration, no new scoring). Result: **current/unmodified (656,937 of 658,447 loans, 99.8% of the population)** O/E 0.736, 95% CI **[0.675, 0.797]**, entirely below the 0.8 floor; **FICO 720+ (573,236 loans, 87%)** O/E 0.628, CI **[0.561, 0.694]**; two-month-delinquent (144 loans, 87 defaults) O/E 1.414, CI [1.217, 1.598], entirely above the 1.25 ceiling; FICO<660 (9,359 loans, 140 defaults) O/E 1.299, CI [1.104, 1.507]. **This is well-supported systematic error in the segments holding the large majority of the loan population, not sparse noise** — no new acceptance threshold was invented; the existing frozen [0.8,1.25] band is shown per segment for reference only. Evidence: `artifacts/runs/segment_acceptance_review/9b9453a2d995423393cdebb418b8cb42/segment_acceptance_review_result.json`.
- **Corrected evidence-role wording** across `docs/final_report.md`, `docs/professional_review.md` and `README.md`: 2011Q1 is development-validation (shaped model selection), 2012Q1 is calibration-fitting (fit the intercept offsets), 2013Q1 is the one final evaluation. These are loan-disjoint but not three independent tests of the final calibrated model — only 2013Q1 tests it. O/E 0.8139 is recorded as passing the frozen range while still indicating aggregate overprediction (expected defaults ~23% above observed), not as an exact calibration.
- **Overall model acceptance: qualified/pending review, not an unconditional pass.** Full acceptance matrix (Engineering / Aggregate model performance / Segment calibration / Retrospective loss measurement / Predictive LGD / Actual-portfolio lifetime loss / Production readiness) added to `docs/final_report.md`. Intended-use distinction made explicit: a ranking-only research use is materially less affected by this finding than any probability-based use (pricing, provisioning, lending), which the model does not support.
- 3 new tests (`tests/test_segment_acceptance_review.py`). **171 tests passed** (up from 168).
- No refit, recalibration, threshold change, model promotion, dashboard replacement, commit or publication. The 2013Q1 result remains preserved and used, not reset to untouched.
- Next: any segment-specific remediation is a new, separately-scoped project requiring development-only changes and a freshly reserved final-test cohort, since 2013Q1 cannot become an untouched test again. This milestone's own scope is complete.

## Historical status — 2012Q1/2013Q1 acquired; PD model refrozen, calibrated, evaluated once, 2026-09-22

- **2012Q1 (13.85 GB) and 2013Q1 (17.70 GB) verified, checksummed, copied and receipted** into `data/raw/fannie_mae_loan_performance/`; `configs/multi_cohort_redevelopment.json` updated with `source_present: true` and both SHA-256 checksums. The retrospective loss analysis (vendor-method reconciliation) is a separate, complete result and was untouched by this milestone.
- **Development-only model selection** (`redevelopment_model.py`): trained on the same 2010Q1 rows as before; selected among the same fixed candidate grid using the full 2011Q1 population (chronologically later, out-of-cohort) instead of a same-cohort split. **`logistic_1.0` selected again** — reproduces the original challenger's exact 2011Q1 metrics, confirming pipeline consistency rather than a different model by default.
- **Calibration on 2012Q1 only** (`redevelopment_calibration.py`): intercept offsets fit directly on 2012Q1 (911 defaults), accepted against a frozen 1e-6 tie threshold. **Selected: adjusted.** Aggregate O/E moved from 0.690 to ~1.0. **Honest segment finding: the dominant current/unmodified segment improved (O/E 0.625→0.933) but the small two-month-delinquent segment got worse (O/E 1.212→1.468)** — reported, not hidden, per the frozen protocol's ban on segment-specific fixes.
- **The one final evaluation, on 2013Q1** (`redevelopment_final_evaluation.py`): built features+labels together in one step that no earlier step reads, so outcome-blindness is structural. **All six frozen quantitative gates passed** (default support, unresolved fraction, paired log loss, Brier, AUC non-inferiority, and — the gate that failed before — calibration O/E 0.8139, within [0.8, 1.25] but close to its floor). **The same opposite-direction segment miscalibration reproduces on this independent cohort**: current/unmodified and high-FICO overpredicted, two-month-delinquent and low-FICO underpredicted.
- **Four separate verdicts** (full detail in `docs/redevelopment_plan.md`): (1) new-cohort engineering — pass; (2) discrimination/calibration — materially improved, not unconditionally fixed (segment issue persists); (3) final external acceptance — passed, within a stated narrow scope (2010-2013 vintage, primary conforming SF, aggregate ranking; not uniform-segment calibration); (4) LGD/lifetime-loss limitations — unchanged, no coupling attempted.
- 9 new tests (`test_multi_cohort_adapter.py`, `test_redevelopment_model.py`). **168 tests passed** (up from 159).
- No model promotion, no dashboard replacement, no commit, no publication. No retuning attempted against the 2013Q1 result.
- Evidence: `artifacts/runs/redevelopment_model/49235a3eec044f748f4fe4beb4f93c12/`, `artifacts/runs/redevelopment_calibration/66899de49fc84a8da3166d59214c2aa4/`, `artifacts/runs/redevelopment_final_evaluation/21a27da4febc4ebdbeba08698e5b18f1/`.
- Next: this milestone's scope is complete. Any further work (e.g., segment-specific remediation, a genuinely new held-out cohort, or LGD/lifetime-loss coupling) is a new, separately-authorized milestone, not a continuation of this one.

## Historical status — Official vendor R code retrieved; event semantics resolved, 2026-09-22

- Retrieved Fannie Mae's official R reference implementation (`LPPUB_StatFile_Production.R`) via a Wayback Machine snapshot of the current `capitalmarkets.fanniemae.com` "Code (Primary)" link (the live URL is Cloudflare-blocked from this environment; no authentication was required or attempted — a public, unauthenticated archive URL). Full provenance (URLs, dates, SHA-256 checksums) recorded in `docs/redevelopment_plan.md` and in the run evidence.
- **Credit-event trigger, traced exactly:** the vendor's own threshold is 180-day delinquency (not 90-day), or the same 4 disposition codes. Compared against all 2,108 `disposed_credit_exit` loans: the two triggers land on the same month for only **23 loans (1.1%)**; for the rest the vendor's trigger fires later (median 3 months, mean 5.76 months). **Confirms directly: matching exposure balances do not establish matching event definitions.**
- **Net Loss/Net Severity, traced exactly:** `LAST_UPB` (exposure) = balance at removal, falling back to current UPB, both at the terminal row — matches what this project already used. `LAST_RT` (rate) is the **most recent prior rate carried forward**, not the terminal-row rate — implementing this raised interest-cost coverage from 11.4% to **100%**. `INT_COST` includes a 35bp guaranty-fee deduction and a non-interest-bearing-UPB offset, both new. Principal Forgiveness is confirmed as an **additive** loss term.
- **A real bug was caught before reporting anything:** an off-by-one column error (this project's established raw-column convention is `c{position-1}`) read Original UPB instead of Current Interest Rate, producing "rates" like 98000% and a $594M "loss" on one loan. Caught on inspection (implausible on its face), traced to the exact raw string, fixed, and a permanent plausibility guard (reject `last_rt` outside 0-20%) was added so a recurrence fails the run rather than silently reporting nonsense.
- **Reassessed the complete-case restriction:** per the vendor's own zero-fill population-inclusion rule (applied only to the specific cost/proceeds/forgiveness fields, never to exposure), the eligible population widens from 1,880 to **all 2,108** `disposed_credit_exit` loans. The original 1,880-loan figure is preserved unchanged (re-verified present); the new 2,108-loan official-formula figure is a separately named variant: median net loss $31,120.74 vs. $22,824.20 original, with the formula correction alone (same 1,880 loans) accounting for a $6,487.83 median shift.
- **Corrected blocker inventory:** vendor-method retrospective loss measurement and descriptive disposed-subset severity are now well-evidenced; predictive LGD across the full default population and actual-portfolio lifetime expected loss remain blocked by selection bias, cured/unresolved workouts, exposure timing and independent validation — untouched by resolving the R-code questions, as anticipated.
- New module `src/mortgage_risk/vendor_official_loss_calculation.py`, 9 new synthetic tests (including a regression test for the caught bug). **159 tests passed** (up from 150).
- Evidence: `artifacts/runs/vendor_official_loss_calculation/4fe2070b858446aeaf9d96d923f4d750/`. Full narrative: `docs/redevelopment_plan.md`.
- Next: none of the remaining predictive-LGD/lifetime-loss blockers are resolvable from existing evidence; they require either new cohorts (2012Q1/2013Q1, still not local, separate user action) or a dedicated exposure/recovery-timing design for non-disposed episodes.

## Historical status — Vendor-method reconciliation and final-report correction, 2026-09-22

- **Fixed a reversed reporting error** in `docs/final_report.md`: verified against the saved external-evaluation JSON (`evaluation_result.json`), current/unmodified loans are **overpredicted** (608 observed vs. 869.06 expected, O/E 0.6996) and two-month-delinquent loans are **underpredicted** (101 observed vs. 77.61 expected, O/E 1.3015) — the report had these backwards. Searched all other docs for the same reversal; found none (`docs/calibration_remediation.md` already had it correct).
- **Reconciled the descriptive realized-loss profile against Fannie Mae's own official loss methodology** (Loan Performance Data Tutorial, Feb 2021, via a Wayback Machine snapshot since the live page is Cloudflare-blocked from this environment; FAQ fetched directly from Fannie Mae's S3-hosted PDF). Confirmed field-by-field against the local glossary's own CAS/CIRT/(SF) checkmark columns:
  - Field 46 (UPB at the Time of Removal, the vendor's own "Credit Event UPB") is SF-applicable and now extracted — matched 100% (1,880/1,880) of the realized-loss population.
  - Net Loss is officially defined as including delinquent interest, net of proceeds; the vendor's own pre-computed Net Gain/Loss, Delinquent Accrued Interest and Interest Bearing UPB fields are all confirmed **CRT-only (NA for SF)** — validating this project's component-based approach as necessary, not a shortcut.
  - Official FAQ: blanks in the nine cost/proceeds fields should be treated as zero (new, authoritative, field-specific guidance).
  - Fields 63/64 (modification non-interest-bearing UPB / principal forgiveness) and 80 (foreclosure write-off) are confirmed SF-applicable with no population-date restriction — correcting an earlier overstatement that this data was absent from the dataset rather than just excluded from the original 9-field extract.
  - The "populated is not proven final" caution is refined with a more precise, SF-specific basis (FAQ Q41/Q43: 90-day lag, ongoing updates for recent dispositions) rather than the CRT-deal-claims phrase previously cited, which turns out to be shared boilerplate also present on confirmed CRT-only fields.
- New module `src/mortgage_risk/vendor_method_reconciliation.py`, 9 new synthetic tests. A real join bug (loan-only match against a field that repeats monthly, up to 141 rows for one loan) was caught by its own duplicate-key assertion before any result was reported, then fixed with a resolution-month-matched join. **150 tests passed** (up from 141 before this milestone; up from 124 at the start of this session's Milestone 1).
- Five-way methodology breakdown: 6/9 items resolved (A), 1 derivable under a disclosed convention (C), 2 remain genuinely open pending the vendor's R code, which was not reachable from this environment (B, E) — a specific, bounded gap, not a generic "data insufficient" conclusion.
- Evidence: `artifacts/runs/vendor_method_reconciliation/b758ff00b5aa468da1b81d13e64626f8/`. Full narrative: `docs/redevelopment_plan.md`.
- **Decision:** the realized-loss profile remains a retrospective descriptive statistic for its supported (1,880-loan, 21.5% of all defaults) population — not strengthened into an accepted LGD model, since the "credit event" trigger definition itself is unverified against this project's own default-proxy definition pending the unreachable R code. Predictive LGD and actual-cohort lifetime loss remain blocked, now for a more specific reason.
- Next: none of the remaining gaps are resolvable without either the vendor R code (separate access attempt) or the 2012Q1/2013Q1 cohorts (user's separate action, still not local).

## Historical status — Milestones 1-3 complete: corrected workout classification, default-anchor exposure, descriptive realized-loss profile, 2026-09-22

- Re-verified state before continuing: 2012Q1/2013Q1 still not local, git still 0 commits, no active jobs.
- **Milestone 1 (correction):** `loss_workout_linkage.py` v2 follows every default trajectory to its last supportable resolution instead of stopping at the first redefault/gap (v1 limitation, see below). Disposition share corrected from v1's 18.6% to **24.1%** (2,108/8,750), now matching **exactly** the 2,108 loss-field loans (v1 matched only 1,628/2,108). 21 synthetic tests built from real hand-traced loan histories (gap continuation, repeated cure/redefault cycles, the frozen `ambiguous_same_month` rule). Evidence: `artifacts/runs/loss_workout_linkage/b2ebdeb7319a4a6486c84b4ad02414f1/`.
- **Milestone 2 (exposure):** `default_anchor_exposure.py` retains reported balance/masking/terminal status at the original anchor month only (never substituting original UPB, a terminal-month zero, or a prior balance without labeling it a proxy). 94.1% of all defaults and 93.1% of disposed episodes have directly usable anchor exposure; 492 episodes (5.6%) have no supported exposure evidence at all. 5 synthetic tests. Evidence: `artifacts/runs/default_anchor_exposure/62355abf161f4a9fbd86b0f6401beb36/`.
- **Milestone 3 (descriptive loss profile, NOT LGD):** Read the glossary PDF text directly for fields 54-62 (poppler installed locally for this). Every one of those fields is explicitly gated by "individual CRT deal claims and reporting timelines" — populated does not mean final. `realized_loss_profile.py` computes one undiscounted accounting identity for the 1,880-loan (21.5% of all defaults) complete-case, exposure-supported subset: median net loss **$22,824** (21.5% of exposure), 23.2% net gains and 3.2% loss-exceeds-exposure cases, neither clamped. Explicitly labeled descriptive, with blockers to promotion recorded in the run evidence. 5 synthetic tests. Evidence: `artifacts/runs/realized_loss_profile/f63257e5acb54101abb2a4d0cb30e8a4/`.
- **141 tests passed** (up from 124 at the start of this milestone). Full narrative: `docs/redevelopment_plan.md`.
- Selection bias confirmed, not resolved: this profile still covers only 21.5% of all default episodes and must never be treated as all-default severity. No model fitted, no calibration attempted, no commit.
- Next: final research-delivery milestone — reconcile documentation/presentation, produce one concise final report, run release checks. 2012Q1/2013Q1 acquisition remains the user's separate, independent action for the calibration track.

## Historical status — Workout classification corrected (v2); full trajectory to last resolution, 2026-09-22

- Re-verified state before continuing: 2012Q1/2013Q1 still not local, git still 0 commits, no active jobs, 131 tests passing before this milestone's changes.
- Independent review of the v1 default-to-workout linkage (previous entry below) found it stopped scanning too early: at the first redefault (`cured_then_redefault`) and at the first reporting gap (`gap_after_default`). Hand-tracing real loan histories confirmed both problems concretely: **loan SYNTH-A** (a synthetic label standing in for a real hand-traced 2010Q1 loan; the actual identifier and its full history are retained only in the private, gitignored `artifacts/runs/` audit evidence, not published here) cures, redefaults, crosses a gap, cures again, and only then reaches `other_exit` — v1 stopped at the first redefault and never saw it; **loans SYNTH-B/SYNTH-C** (same redaction convention) end their history with delinquency still climbing *and* a payoff code on the same row, which the project's own frozen `ambiguous_same_month` rule says must not be resolved by code priority — v1 would have silently called both "paid off."
- Corrected `src/mortgage_risk/loss_workout_linkage.py` (v2) follows every trajectory to its last supportable resolution, keeps the original anchor fixed (redefaults are events within one episode, never a new one), and preserves both the path (cure/redefault/ambiguous/gap counts, full transition list) and the final resolution, never overwriting one with the other.
- Result on the same 8,750-loan population: disposition share moves from v1's uncorrected 18.6% to a corrected **24.1%** (2,108 loans) — and now matches **exactly** the 2,108 loans with recorded loss fields, a perfect cross-check v1 missed (v1 only matched 1,628/2,108). Zero episodes end in an unexplained data dropout outside the two flagged ambiguous cases.
- Tests rewritten around the real hand-traced examples: 21 synthetic cases (was 14), covering gap continuation, repeated cure/redefault cycles, ambiguous same-month, and disposition priority. **131 tests passed** (up from 124). Two cohort-wide empirical checks are now recorded in the run evidence: zero rows follow any terminal code anywhere in the 323,174-loan cohort, and `zero_balance_effective_date` equals `reporting_month` on all 306,637 terminal rows with zero exceptions (the effective-date-vs-reporting-date question is answered, not open).
- v1's run directory and result are preserved unchanged; this is a new run, not an overwrite. Evidence: `artifacts/runs/loss_workout_linkage/b2ebdeb7319a4a6486c84b4ad02414f1/`. Narrative: `docs/redevelopment_plan.md`.
- Selection bias is confirmed, not resolved: 75.9% of default episodes still never reach disposition. No exposure, severity, LGD, or model work performed yet.
- Next: default-anchor exposure for the 2,108 `disposed_credit_exit` loans (Milestone 2), then decide whether a narrowly-labeled realized-loss analysis is defensible (Milestone 3).

## Historical status — Default-to-workout linkage reconciled, 2026-09-22

- Confirmed 2012Q1 and 2013Q1 are still not local (`data/raw/fannie_mae_loan_performance/` holds only the sample, 2010Q1 and 2011Q1); `configs/multi_cohort_redevelopment.json` still records `source_present: false` for both. No active ingestion job or database lock found; git index still has zero commits.
- Followed all 8,750 accepted-cohort Phase 2F default-proxy episodes through their full post-anchor trajectory (reused `event_rows.parquet`/`loan_outcomes.parquet`, no CSV rescan) and cross-tabbed against the 2,108 loss-field loans: 1,628 (18.6%) reach an actual disposition, 2,940 (33.6%) pay off/mature after defaulting, 2,747 (31.4%) cure then redefault, 1,061 (12.1%) cure with no redefault by data end, 319 (3.6%) other-exit, 39 (0.4%) remain open at data end, 16 (0.2%) hit a reporting gap. Every check passed: 0 duplicate/unmatched loan IDs, counts sum exactly to 8,750, all loss-field loans classified, 0 unsupported codes, and no case of a loan's data silently stopping before the panel-wide latest month with no explaining resolution or gap.
- This quantifies the previously-flagged disposed-loans-only selection bias precisely (81.4% of default episodes would be excluded) and shows loss fields can appear on loans that later cure/redefault, not only on completed dispositions — a real limitation for any future severity label, not a fix for one.
- New reusable module with synthetic hand-checkable tests: `src/mortgage_risk/loss_workout_linkage.py`, `tests/test_loss_workout_linkage.py` (14 cases). **124 tests passed** (up from 110). Runtime 4.775s.
- Evidence: `artifacts/runs/loss_workout_linkage/24126815af8448fe9b02b34f23ca7aa9/`; narrative and table: `docs/redevelopment_plan.md`.
- Still not done: default-anchor exposure (masking/deferral at the anchor month), any severity/LGD label, and any model fit. No data downloaded, no model fitted or promoted, no commit.
- Next: establish supported default-anchor exposure for at least the 1,628 `disposed_credit_exit` loans (masking/deferral status at the anchor month), before proposing any severity/LGD label. Vendor 2012Q1/2013Q1 acquisition remains a separate, independent blocker for calibration/final-test roles.

## Historical status — Redevelopment design and loss feasibility complete, 2026-09-22

- Frozen minimal chronological design: existing 2010Q1/2011Q1 development; 2012Q1 calibration; untouched 2013Q1 final evaluation. Prediction/outcome dates and changed reservation are explicit in `configs/multi_cohort_redevelopment.json`.
- Existing 2010Q1 loss-field scan found 2,108 unique loans; no selected-field conversion failures or unmatched cohort IDs. Monetary completeness does not establish economic finality.
- Plan and evidence: `docs/redevelopment_plan.md`; `artifacts/runs/loss_feasibility/30a0a02381af4b93807301fc6ef08d90/`.
- Calibration remains unresolved pending additional cohorts and new development; portfolio losses remain unestimated pending default/workout/exposure reconciliation.
- Required next input: vendor primary 2012Q1 and 2013Q1 files plus release/layout information. No new data downloaded, no model fitted or promoted. Existing loss-workout linkage can continue independently.

## Historical status — Clean research package verified, 2026-09-22

- New isolated Python 3.14/macOS ARM64 environment installed pinned expanded dependencies and built wheel non-editably.
- Tests copied outside repository: 109 passed, one vendor-data test skipped in 19.00s. Synthetic demo and dependency checks passed; import verified from installed site-packages.
- Wheel content inspection found only 29 Python-package/metadata members, no data files or databases. No complete security or cross-platform certification claimed.
- Git index remains empty; no commit, publication or deployment.
- Evidence: `artifacts/runs/clean_release/1efd8de3f336419eb7f94eeef6f6f0c4/verification_result.json`.
- Research package installation gate complete. External model acceptance and actual-cohort loss readiness remain unpassed.
- Next: user-facing research handoff using the verified package, review guide and explicit model limitations; further statistical redevelopment is a separate scope.

## Historical status — Research delivery review complete, 2026-09-22

- Consolidated model inventory, failed external gate, monitoring criteria/actions, reviewer responsibilities and strategic completion sequence in `professional_review.md`. Monitoring remains a specification, not a deployed service.
- README and audit now distinguish historical dashboard evidence from the later challenger failure; release guide explicitly qualifies stale clean-install evidence.
- Current-environment release check passed: dependency consistency, 110 tests in 4.08s, vendor-free synthetic demo.
- Evidence: `artifacts/runs/delivery_review/db5bb892dfd34359b088f246f9a1d345/verification_result.json`; synthetic outputs preserved alongside it.
- Model acceptance remains withheld and actual-cohort lifetime losses remain unsupported. No new models, data downloads or publication.
- Next: verify a clean installation of the expanded dependencies, then review source/distribution contents. Separate multi-vintage redevelopment from this finite delivery gate.

## Historical status — Calibration experiment complete; no remedy demonstrated, 2026-09-22

- Implemented five-fold development-only calibration, with preprocessing fitted inside folds and coherent three-class probability normalization.
- Improvement in internal log loss (9.34e-7) is below the frozen 1e-6 tie threshold; Brier slightly worsens. Retained unchanged candidate.
- 110 tests passed; export parity, original data fingerprints and fold count checks passed.
- External calibration failure remains unresolved. No model promoted, external rescore or additional download.
- Results: `docs/calibration_remediation.md`; run `artifacts/runs/calibration_remediation/6059d958cd634f14bc0882f861036b98/`.
- Next: prepare reviewer-facing limitations and monitoring evidence; broader modeling requires a separate multi-vintage development design.

## Historical status — Calibration review and experiment design complete, 2026-09-22

- Diagnosed opposite internal/external calibration directions and conflicting external segment errors; no causal explanation asserted.
- Froze a two-candidate development-only experiment with loan-grouped cross-fitting and coherent multinomial intercept adjustment. No model fitted in this milestone.
- Reserved 2012Q1 / January 2013–January 2014 evaluation by design only; no new download or outcome inspection.
- Prior failed external gate remains unchanged. No model promoted.
- Design: `docs/calibration_remediation.md`; machine-readable settings: `configs/calibration_remediation.json`.
- Next: execute the bounded development-only experiment; proceed to fresh evaluation only if warranted.

## Historical status — External evaluation complete; acceptance withheld, 2026-09-22

- New 2011Q1 adapter processed 36,545,962 records / 505,196 loans; 472,056 eligible snapshot loans, 88 unresolved outcomes.
- Frozen candidate AUC 0.868 versus 0.657 benchmark; better log loss and Brier, but calibration O/E 0.78685 fails frozen 0.8–1.25 gate. 890 defaults versus 1,131.10 expected.
- No promotion, refit, recalibration or dashboard substitution. Segment deterioration and vendor-release provenance remain limitations.
- 108 tests passed; persisted prediction metrics independently recomputed in SQL. Evaluation execution is complete; model acceptance is not.
- Report: `docs/external_evaluation_results.md`.
- Evidence: `artifacts/runs/external_evaluation/bb53b87c6a034af29614c2c5768b4b06/`.
- Next: design development-only calibration remediation and a fresh reserved evaluation before fitting a revised model.

## Historical status — External evaluation preparation, 2026-09-21

- Candidate, benchmark, development report and evaluation settings frozen by fingerprint.
- Reserved design: 2011Q1 primary cohort; January 2012 snapshot with outcomes through January 2013.
- **Waiting for reserved cohort:** only original 2010Q1 and sample files are present. No external evaluation or promotion performed.
- Readiness checks fail on changed frozen inputs and never treat file presence as analytical acceptance. Cohort adaptation and external scoring still require implementation after schema inspection.

Protocol: `docs/external_evaluation.md`

Evidence: `artifacts/runs/external_readiness/bcafae6405144438a5b06d5ff022b222/readiness_result.json`

Next: acquire the reserved 2011Q1 primary cohort and corresponding release/layout information.


## Historical status — Internal challenger comparison, 2026-09-21

- Completed training-only preprocessing and a three-candidate regularized multinomial comparison; benchmark refitted on the same development population.
- Selected logistic C=1 by internal log loss. AUC 0.862 versus 0.615 benchmark; log loss 0.40806 versus 0.41461; Brier 0.23659 versus 0.23824.
- 146 observed defaults versus 130.50 expected; calibration and sparse-segment limitations remain. Same-date internal performance is exploratory, not external acceptance.
- Original 2013/2015 evaluations and dashboard remain unchanged. No model promoted.
- L-BFGS nonconvergence was rejected; Newton-Cholesky converged in 8–9 iterations. 102 tests and dependency check passed.

Report: `docs/challenger_evaluation.md`

Evidence: `artifacts/runs/challenger/f94a630d661f4ea28f7a21c4a567c74c/challenger_result.json`

Next: freeze the candidate and arrange a separately reserved cohort/evaluation protocol. No new data acquired or publication performed.


## Historical status — Expanded feature preparation, 2026-09-21

- Prepared six additional candidate predictors from verified snapshot fields, joining only original January 2011 training loans. No held-out files or outcome labels accessed.
- Preserved all 220282 training records; duplicate-key and lost-record checks passed.
- Frozen deterministic loan-level development/internal-validation assignment before outcome use. This is same-date exploratory validation, not a fresh external test.
- Raw values and missing/invalid indicators retained; no clipping, imputation, scaling or model fitted.
- **98 tests passed in 2.63s.**

Evidence: `artifacts/runs/expanded_features/2d1fe0dacf2548e883b756f23fe1fb8b/feature_result.json`

Next: fit training-only preprocessing and a bounded interpretable challenger; evaluate internally against the benchmark on the same split. External acceptance still requires a separately reserved cohort.


## Historical status — Risk-factor assessment, 2026-09-21

- Completed an outcome-blind five-snapshot inventory: 654,564 records, 34.73 seconds, zero duplicate/missing keys and zero unmatched records against accepted ingestion.
- Documented 21 candidate fields and a bounded interpretable challenger proposal; no labels read or models fitted.
- Early FICO/LTV/DTI/term/occupancy/purpose coverage supports further feature preparation. Vendor history is entirely absent in early snapshots; score definitions change in 2025/2026.
- This is snapshot inventory acceptance, not full-population or final feature/model acceptance.
- Next: prepare training-only features and preregister internal selection; obtain a separately reserved cohort before external model acceptance. Existing held-out results remain frozen.

Specification: `docs/risk_factor_expansion.md`

Evidence: `artifacts/runs/risk_factor_assessment/00fd2e4a925d4d2fa284ceb1efd01a4e/assessment_result.json`


## Historical status — Professional research hardening, 2026-09-21

- Added fail-closed integrity checks across every dashboard report, validation report, schedule and sensitivity input. Manifest coverage, confined paths and fingerprints are checked; schedules must have consecutive months, matching horizons and finite nonnegative losses.
- **92 tests passed in 2.54 seconds.** Dependency check and vendor-free synthetic demo passed. New reporting build succeeded without re-ingestion or model fitting.
- New dashboard HTML is byte-identical to the user-accepted Phase 7 page; no new visual review is claimed.
- Added architecture diagram, model inventory, reviewer walkthrough, repeatable release-check script and prioritized controls/remediation assessment. SR 26-2 is the current design reference; no regulatory compliance is asserted.
- This closes bounded reporting-integrity and review-documentation gaps, not every industry/production concern. Independent challenge, multi-cohort validation, actual economic severity/exposure readiness, vulnerability assessment, generic historical orchestration and deployment controls remain open.

Evidence: `artifacts/runs/professional_review/81aa3684f31d416792bb2adbd4b3bfb2/review_result.json`

Dashboard: `artifacts/runs/phase7/1933f81c59cd4e3195fb1b8a040e7d4f/index.html`

Next: follow docs/professional_review.md remediation priorities. A first reviewed version-control snapshot is still pending; no commit or publication performed.


## Historical status — Phase 8 review release, 2026-09-21

- **PASS for reproducible vendor-free review.** A clean environment installed the package, passed dependency checks and ran the demo outside its source checkout without vendor data or saved artifacts.
- Clean suite: **83 passed, 1 explicit optional vendor integration skip**. Original workspace: **84 passed**, including the vendor integration. Missing vendor data is never substituted silently.
- Corrected the missing DuckDB pin; added pinned build tools and ignores for auxiliary environments/database journals.
- Deterministic synthetic demo reuses the existing competing-event/loss calculations and exports checksummed schedules/results. It is separate from the historical dashboard, with invented assumptions clearly labeled.
- README and release guide describe setup, data boundaries and the historical workflow's cohort-specific run references.
- Verified Python 3.14/macOS ARM64 only. No cross-platform, full historical rebuild, operational deployment or economic-loss readiness claim.
- No files are currently tracked in Git; ignore checks passed for protected data/environment/artifact paths. No commit or publication performed.

Evidence: `artifacts/runs/phase8/162fda1e4d854b779ae1d475f87e22f8/release_result.json`

Synthetic outputs: `artifacts/runs/phase8/162fda1e4d854b779ae1d475f87e22f8/synthetic_demo/`

Next: review the local deliverables; any repository publication or deployment requires separate authorization. Further economic-model development would need additional validated data and assumptions.


## Historical status — Phase 7 accepted, 2026-09-21

- Local standalone dashboard built with Portfolio, Model, Stress and Evidence views; saved aggregates only, no raw-data reload or model refit.
- Accepted report fingerprints, monthly category counts/balances and illustrative loss totals verified before generating the page.
- 82 tests passed in 2.46 seconds; final dashboard JavaScript syntax check passed. Four new tests cover reconciliation, changed evidence rejection, schedule discrepancies and removal of internal paths.
- Executive memo generated with explicit historical / predictive / hypothetical distinctions. Missing exposure remains unavailable, not imputed to zero.
- **Phase 7 accepted with user manual verification:** the user confirmed “they work” in response to the dashboard checklist. Automated browser access remains blocked; no screenshots or agent visual inspection are claimed. Manual acceptance is recorded separately in `user_acceptance.json` alongside the original verification evidence.
- Actual-cohort lifetime economic losses remain NOT READY; single-cohort statistical qualifications remain unchanged.

Dashboard: `artifacts/runs/phase7/c39af0a7a17c43d4b5b7785c5388531a/index.html`

Memo: `artifacts/runs/phase7/c39af0a7a17c43d4b5b7785c5388531a/executive_memo.md`

Evidence: `artifacts/runs/phase7/c39af0a7a17c43d4b5b7785c5388531a/verification_result.json`

Next: Phase 8 release packaging — reproducible setup, a synthetic demonstration and repository hygiene; no publication without authorization.


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


## Historical verified status — Phase 5, 2026-09-20

- **PASS for illustrative dynamic stress, recovery timing, sensitivity and exact attribution. Actual-cohort lifetime loss readiness remains unresolved.**
- Reused Phase 3's hypothetical $100,000 loan and frozen hazards. The baseline reproduces accepted undiscounted loss within 1e-8 dollars.
- Adverse intensity holds through month 24, declines linearly to zero by month 60, then stays at baseline. This differs intentionally from Phase 3's sustained full-term stress; its prior result is unchanged.
- Undiscounted expected loss: baseline **$103.65**, transient adverse **$276.46**. Timing-adjusted PV loss: **$99.81** and **$286.49**, using 4% annual discount and 6/18-month recovery lags.
- All 16 combinations of default, payoff/maturity, severity and recovery delay evaluated for exact Shapley allocation. Both loss-increase attributions reconcile within 1e-8 dollars. Delay contributes zero to undiscounted loss and about $17.74 to PV loss increase.
- 18 one-at-a-time sensitivity cases; configured default/payoff/LGD/term/recovery-lag direction checks passed. Recovery cashflows after loan maturity remain included.
- **73 tests passed in 2.76s**, including hand-calculated interactions, PV, scalar-path equivalence and end-to-end export. Full execution **0.043 seconds**. A fixture caught an export binding error before the full run; corrected.
- No model refit, actual exposure imputation, new data, dashboard, commit or publication. Frozen Phase 4 evaluation remains unchanged.

Report: `artifacts/runs/phase5/c4ba96b0e7f94dc88a33ab2c8db78d86/stress_report.md`

Evidence: `artifacts/runs/phase5/c4ba96b0e7f94dc88a33ab2c8db78d86/stress_result.json`

Next: Phase 6 consolidated validation and monitoring replay, with separate engineering, statistical and economic-readiness verdicts. Maintain explicit synthetic loss labeling.


## Historical verified status — Phase 4B, 2026-09-20

- **PASS for the first estimated benchmark and chronological evaluation; not a deployment or full loss-model approval.**
- Training-only constant and smoothed categorical three-outcome models; alpha 10/100/1000 compared on validation multiclass log loss. Selected `smoothed_10` saved before test loading. No test-driven refit or recalibration.
- Test: 15,694 loans, 77 defaults; AUC **0.6981**, approximate stratified fixed-score bootstrap 95% interval **0.6458–0.7501** (200 replicates).
- Test multiclass log loss **0.470649** vs constant **0.477640**; Brier **0.281066** vs **0.282054** (sum over three classes).
- Expected defaults 71.96 vs 77 observed; O/E **1.070**. Current/unmodified segment underpredicts (46 observed vs 36.51 expected); modified segment has only 7 test loans. No claim of uniform segment calibration.
- Censoring: 45 train and 1 validation outcomes excluded explicitly from conditional-outcome fitting/scoring; none in test. Unresolved outcomes retained and prevalence bounds reported. Unconditional missing-at-random assumptions remain unverified.
- **68 tests passed in 2.46s**; full fit/evaluation runtime **0.784 seconds**. No new dependencies, ingestion or additional data.
- Numeric design fields are not predictors in this first model. Single-cohort calendar/seasoning confounding, omitted credit attributes, combined payoff/maturity and unestimated severity remain limitations.

Report: `artifacts/runs/phase4b/59e0a87732b248b6b65060391077041f/model_report.md`

Evidence: `artifacts/runs/phase4b/59e0a87732b248b6b65060391077041f/model_result.json`

Next: Phase 5 bounded stress/loss refinement with explicit economic assumptions and sensitivity/attribution. Preserve this frozen model evaluation. Do not translate the conditional 12-month model directly into actual-cohort lifetime losses without a justified time/exposure/severity model.


## Historical verified status — Phase 4A, 2026-09-20

- **PASS: feature availability and chronological evaluation preparation. Phase 4 model estimation is not yet complete.**
- Frozen snapshots: January 2011 training, January 2013 validation, January 2015 test; each label horizon is 12 months and ends before the following split starts.
- MD5 first-character groups assign loans independently of outcomes: train 0–b, validation c–d, test e–f. Zero loan overlap; one snapshot per selected loan.
- Training 220,282, validation 23,400, test 15,694; 259,376 total. Future outcome labels are separate from the five explicitly allowed features.
- Features: current delinquency months, nonnegative reported age, positive original balance, eligible reported balance, and current reported modification status. Missing values remain missing; no imputation or fitted preprocessing.
- Censored/unresolved labels remain explicit (45 training, 1 validation). Test outcome counts are preflight completeness evidence, not model performance or a basis for tuning.
- **64 tests passed in 2.51s**; preparation runtime **1.263 seconds**. Tests verify split/horizon constraints and that changing future outcomes does not change exported features.
- No ingestion, additional data, or model fit. Phase 3 historical and synthetic benchmark distinctions remain in force.

Report: `artifacts/runs/phase4a/346469500fc34c66b760aeb21def6ffe/design_report.md`

Evidence: `artifacts/runs/phase4a/346469500fc34c66b760aeb21def6ffe/design_result.json`

Next: Phase 4B interpretable model comparison with training-only preprocessing, explicit censoring treatment, validation-only model selection, calibration and segment assessment, then one final test evaluation. Prefer a simple defensible model over adding a challenger by default. Single-cohort seasoning/calendar confounding and omitted FICO/LTV/DTI limit interpretation.


## Historical verified status — Phase 3, 2026-09-20

- **PASS for the bounded benchmark:** historical competing-risk curve plus explicitly hypothetical baseline/adverse loss demonstration. Actual-cohort loss readiness remains open.
- Historical input: 323,174 loans; 323,167 eligible at entry; 7 accounted-for entry exclusions. Exposure eligibility does not restrict risk denominators.
- Historical 12-month default-proxy cumulative incidence: **0.127509%**; payoff/maturity cumulative incidence: **9.470291%**.
- Risk-set removals reconcile; 12-month event counts match Phase 2F exactly. Probability maximum residual: 6.66e-16, tolerance 1e-12.
- Historical support: 194 months after entry; tail risk set 5,130. No unsupported historical tail extrapolation.
- Hypothetical $100,000, 4%, 120-month loan: baseline remaining-life expected loss $103.65; adverse $394.33. Assumed LGD 20%/35%; adverse multipliers default 2.0 and payoff/maturity 0.7. These are educational scenario values, not actual cohort losses.
- **62 tests passed in 2.34s**. Full run: **0.231 seconds**. Expected loss/recovery and final amortization/probability closure passed.
- No fitted feature model, additional data, dashboard, commit, or publication. Earlier artifacts are unchanged.

Report: `artifacts/runs/phase3/8e2217375a004a2b915b6e639f68b476/benchmark_report.md`

Machine evidence: `artifacts/runs/phase3/8e2217375a004a2b915b6e639f68b476/benchmark_result.json`

Method and assumptions: docs/methodology.md and configs/benchmark.json. The Aalen–Johansen method reference is linked in the methodology.

Next bounded phase: Phase 4 interpretable estimated models, starting with feature-availability and chronological evaluation design. Actual-cohort economic losses remain blocked by maturity/exposure and severity limitations; do not mistake the synthetic example for their resolution.


## Historical verified status — Phase 2F, 2026-09-20

- **PASS** for descriptive summaries and the documented observed-event proxy contract.
- Preserved 20,983,277 records, 323,174 loans, and 195 months.
- Zero monthly count/known-balance-count/balance differences against accepted ingestion; all four category dimensions reconcile, including eligible reported balances. Phase 2E eligibility category totals match exactly.
- One retrospective 12-month outcome per loan; follow-up gaps, unknowns, ambiguity, and entry-prevalent events remain explicit.
- **50 tests passed in 2.21s**, including end-to-end reporting and boundary fixtures. Successful full run: **7.269 seconds**. An earlier reporting-alias failure was corrected and is not acceptance evidence.
- Code 01 remains payoff **or maturity**, not verified pure prepayment. Default is a project 90+ delinquency/credit-exit proxy. No probabilities or losses were estimated.
- Source files and Phase 2D/2E artifacts unchanged. No additional quarters, dashboard, commits, or publication.

Evidence: `artifacts/runs/phase2f/64d49545a270488ca411e6a731e59465/descriptive_result.json`

Readable report: `artifacts/runs/phase2f/64d49545a270488ca411e6a731e59465/descriptive_report.md`

Next: Phase 3 transparent competing-risk benchmark using explicit at-risk denominators, censoring rules and payoff/maturity terminology; settle unsupported exposure/severity assumptions before any loss calculation. Read target_definitions.md for current rules; older status notes below are historical.


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

## Phase 0 — Runnable and reproducible foundation

This phase establishes the runnable foundation for the project: validated configuration, reproducible dependency management, the project-local execution entry point, and verification using the current environment.

### Current state
- Phase 0 is complete only after the foundation checks, dependency lock, CLI validation, and tests pass in the project-local environment and a separate clean environment.
- The project package remains installed in editable mode and imports successfully from the local source package.
- The project architecture remains aligned with AGENTS.md and PROJECT_PLAN.md.
- Analysis and modeling have not started.

### Relocation milestone
- Project was relocated from an iCloud-synced Documents path to a normal local project directory (path redacted for publication).
- The new project location is a normal local directory and is not a symlink into an iCloud-synced directory.
- The original source folder remains in place until the user verifies the new local copy and intentionally removes it to reclaim iCloud space.

### Implemented and verified
- Project folder exists at a normal local project directory (path redacted for publication).
- The project-local execution entry point was implemented via the installed package command: `mortgage-risk check --config configs/project.yaml`
- A minimal configuration file was added at configs/project.yaml and validated for required fields, schema version, path resolution, and invalid inputs
- A dependency lock workflow was implemented using `requirements.in` and `requirements.lock` with the current minimal runtime and test tooling
- Foundation tests covering valid config, invalid inputs, path resolution, successful execution, failed exit codes, and unique runs were added
- Generated run outputs are recorded under artifacts/runs/<unique-run-id>/ and remain separate from curated reports

### Verification evidence
- Editable installation: verified successfully using the project-local virtual environment
- Import check: verified successfully from src/mortgage_risk/__init__.py
- CLI foundation check: verified successfully with valid configuration
- Error handling: verified for invalid configuration and failed checks with nonzero exit codes
- Unique run records: verified without overwriting previous output directories
- Repository boundary: local Git repository remains scoped to this project folder only
- Ignore rules: verified for protected environment/data paths and for trackable docs/demo paths

### Remaining limitations
- Dependency locking is now implemented and verified for the current minimal dependency set; future dependency additions will require refreshes of the lock file
- No mortgage data, analytical calculations, model fitting, or dashboard work has been added, per the Phase 0 boundary
- Future analytical phases remain intentionally deferred until source access and field definitions are available

### Next bounded implementation milestone
Phase 1 — Source assessment and analytical definitions: assess source documentation and available files, define the population, observation grain, event definitions, time windows, exposure, and loss perspective, and record any blocker preventing real-data analysis.

### Status
Phase 0 passed after successful verification of the foundation setup, lockfile workflow, CLI, test coverage, and output recording. The next phase is Phase 1 — Source assessment and analytical definitions.

---

## Phase 1A — Source assessment and data inventory

### Current status
Phase 1A is substantively complete for the sample-inspection scope: the raw sample was physically verified, the official glossary and file-layout PDF was located and preserved, and the checked fields were matched to the official SF Loan Performance glossary. Full historical-data acquisition remains open and is explicitly separate from this sample-based inspection.

### Verified sample evidence
- File inspected and preserved: `data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv`
- Size: 192,742 bytes
- SHA-256: `c3f773e86e037986a966a35cdd39577a82fa5f7b9efd073d838b1417fea9b5b2`
- Encoding: UTF-8 with BOM / UTF-8-sig
- Delimiter: pipe (`|`)
- Header row: not present
- Record count: 757 non-empty rows
- Field count: 108 fields for every row
- Blank records: none
- Distinct loans: 8
- Reporting range: 2009-07-01 to 2020-06-01
- Duplicate loan-month keys: none
- Invalid reporting periods: none

### Verified public-source evidence
- Official product page reached and read: https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data
- Official glossary and file-layout document saved and retained at `data/raw/fannie_mae_loan_performance/crt-file-layout-and-glossary.pdf` and as a project-root copy at `crt-file-layout-and-glossary.pdf`
- The glossary confirms the following relevant field definitions:
  - Field 2: Loan Identifier
  - Field 3: Monthly Reporting Period, date format MMYYYY
  - Field 40: Current Loan Delinquency Status
  - Field 41: Loan Payment History
  - Field 42: Modification Flag
  - Field 44: Zero Balance Code
  - Field 12: Current Actual UPB
  - Field 10: Original UPB
  - Field 8/9: Original/Current Interest Rate
- The document itself identifies the file as the SF Loan Performance glossary and notes the “October 2020 Release” enhanced format for several fields.

### Important scope boundary
The glossary confirms the sample file is a historical SF Loan Performance dataset and verifies the checked field mapping for that layout. It does not prove that every historical 108-column file in every acquisition quarter is unchanged across all releases. The document’s version note and the sample’s 108-field structure are consistent, but full historical-package verification remains pending for the complete vendor release set.

### Phase 1B status
Phase 1B is partially complete and is now focused on analytical definitions and portfolio design. The sample inspection and vendor-backed field checks are sufficient to define the project’s measurement contract in principle, but the full historical-data package remains open and must be treated as a prerequisite for production-grade estimation.

### Phase 1B milestone objective
Define the project’s analytical contract before transformation or modeling: cohort design, event definitions, exposure logic, censoring rules, timing rules, and loss perspective for 12-month default probability, remaining-life expected loss, and scenario-conditioned losses.

### Implementation status
- Sample inspection code remains in [src/mortgage_risk/fannie_sample_inspect.py](src/mortgage_risk/fannie_sample_inspect.py)
- Focused tests for date parsing remain in [tests/test_fannie_sample_inspect.py](tests/test_fannie_sample_inspect.py)
- The vendor PDF is preserved and ignored by Git
- Phase 1B analytical documentation is in progress

### Remaining evidence gap
- Full historical acquisition data is not yet downloaded or verified locally
- The complete 108-field layout for every vendor package still requires package-level confirmation when the full historical dataset becomes available
- No model fitting, loss estimation, or dashboard implementation is included in this milestone

### Next bounded milestone
Proceed to Phase 1B analytical definitions and portfolio design, keeping all definitions explicit and provisional where the full data package is still missing.

---

## Phase 2A — Sample ingestion and monthly-data reconciliation

### Current status
Phase 2A is implemented and validated for the sample file. The pipeline reads the unchanged vendor sample, validates the required fields, materializes a typed monthly table in DuckDB, converts the same table to Parquet, and records reconciliation evidence including row counts, distinct loan counts, duplicate loan-month keys, date conversion checks, and monthly balance summaries.

### What the pipeline now does
- Reads the preserved source file at `data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv` with UTF-8 BOM handling.
- Parses the pipe-delimited, headerless file using the verified schema positions for the inspected fields.
- Preserves identifiers as text and stores source filename and record number for traceability.
- Converts the validated reporting month from MMYYYY into a proper month-start `DATE` value.
- Stores the typed subset of verified fields in DuckDB and writes the same validated table to Parquet.
- Fails clearly on unexpected field counts, invalid reporting periods, and malformed values instead of silently skipping or imputing rows.

### Verified sample counts
- Raw nonblank records: 757
- Parsed records: 757
- Output rows: 757
- Distinct loans: 8
- Distinct months: 132
- Duplicate loan-month keys: 0
- Date conversion failures: 0
- Required field validation: pass

### Reconciliation evidence
- Nonblank raw records match parsed rows.
- Distinct loan counts before and after ingestion remain consistent.
- Duplicate loan-month keys are not present in the sample.
- Monthly balance totals are computed from the validated current actual UPB values without forcing monthly values to match across months.
- Missing, zero, and invalid balance conditions are tracked separately.

### Generated output locations
- database: `artifacts/runs/sample_ingest/<unique-run-id>/sample_monthly.db`
- parquet: `artifacts/runs/sample_ingest/<unique-run-id>/sample_monthly.parquet`
- metadata: `artifacts/runs/sample_ingest/<unique-run-id>/sample_ingest_result.json`

### Verification evidence
- `./.venv/bin/python -m pytest -q tests/test_sample_ingestion.py` → 3 passed in 1.79s
- `mortgage-risk sample-ingest --input data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv` → successful run with generated output and validation status pass

### Known limitations
- This remains a sample-based ingestion milestone; the eight-loan sample is not treated as a historical portfolio or as a full market population.
- Official vendor field definitions beyond the inspected subset remain constrained by the project’s evidence rules.
- Full historical cohort acquisition is still outstanding and not claimed by this pipeline.

### Completion status
Phase 2A passed for the sample ingestion and reconciliation milestone. The next bounded milestone is to build a transparent, small monthly cohort reconciliation layer and first benchmark exposure checks using the validated monthly table, without moving into default probability estimation or lifetime loss modeling.
---

## Phase 2B — Monthly portfolio summaries and exposure checks

### Current status
Phase 2B is implemented and validated for the sample-based monthly summary layer. It reads the latest validated ingestion output and produces monthly portfolio summaries and exposure diagnostics without altering the source data or claiming portfolio representativeness beyond the observed vendor sample.

### What the new layer produces
- monthly observed loan counts by reporting month
- counts with known, missing, and zero current balance
- total and average known current balance by month
- category counts and totals by documented delinquency status, modification flag, and termination code
- diagnostic flags for negative balances, missing balances, balance increases, and monthly gaps
- reconciliation evidence comparing source totals from DuckDB against the persisted summary totals

### Illustrative monthly summary
For the vendor sample, the result is defined as the observed population for the sample only. For example, the first month in the validation evidence contains a single observed loan with a zero known balance, which is distinct from a missing balance and is explicitly reported as such.

### Diagnostic interpretation
- missing balance: a loan-month is observed but the current balance is absent in the source record; this is tracked separately from zero
- zero balance: a balance of exactly zero is known and valid in the source file at that month and is not treated as missing
- balance increase: a current balance that rises from the previous month is flagged for review and not silently corrected
- monthly gap: a loan missing an intervening month in the time series is flagged and not treated as a default or prepayment without event-code support

### Verification evidence
- `./.venv/bin/python -m pytest -q tests/test_foundation_cli.py tests/test_sample_ingestion.py tests/test_monthly_summary.py` → 12 passed in 1.56s
- `mortgage-risk monthly-summary` → executed successfully using the latest validated ingestion run and produced a unique monthly-summary artifact under `artifacts/runs/monthly_summary/`

### Generated artifact paths
- latest ingestion DB: `artifacts/runs/sample_ingest/<latest-run-id>/sample_monthly.db`
- latest ingestion Parquet: `artifacts/runs/sample_ingest/<latest-run-id>/sample_monthly.parquet`
- latest ingestion metadata: `artifacts/runs/sample_ingest/<latest-run-id>/sample_ingest_result.json`
- monthly summary output: `artifacts/runs/monthly_summary/<timestamp>/monthly_portfolio_summary.json`

### Remaining prerequisites before modeling
- full vendor historical-package access and inspection
- complete official schema verification for any additional fields beyond the inspected subset
- confirmed event and loss definitions for default, modification, and termination handling
- a documented historical cohort broader than the eight-loan sample

### Completion status
Phase 2B passed for the observed sample summary and exposure-diagnostics milestone. The project remains bounded to sample-based engineering and has not moved into model fitting, default-probability estimation, expected-loss estimation, or dashboard work.

---

## Phase 2 closeout — corrected reconciliation evidence and zero-balance limitation

### Verified run evidence
A new summary was generated against the existing verified ingestion run using explicit input-run selection:
- Input run: `fff6c8f729be4b37b1584bd34906f92e`
- Saved result: `artifacts/runs/monthly_summary/phase2_closeout_20260919_001/monthly_summary_20260919_214202/monthly_portfolio_summary.json`
- CLI execution: `./.venv/bin/mortgage-risk monthly-summary --input-run fff6c8f729be4b37b1584bd34906f92e --output-dir artifacts/runs/monthly_summary/phase2_closeout_20260919_001`
- Overall status: `pass`

### Representative consecutive-month bridge
From the saved result, one checked bridge pair is:
- prior month: 2010-01-01
- current month: 2010-02-01
- prior total known balance: 174218.51
- current total known balance: 1368764.98
- balance change, continuing known loans: 1194546.47
- newly observed known balance: 0.00
- missing-to-known balance: 0.00
- disappearing known balance: 0.00
- known-to-missing balance: 0.00
- bridge component total: 1194546.47
- residual: 0.00
- status: pass

### Reconciliation summary from the saved result
- checked month pairs: 131
- skipped month pairs: 0
- failed month pairs: 0
- maximum absolute residual across all checked pairs: 0.00
- reconciliation tolerance: 0.01
- rounding rule: all monetary bridge components and residuals are quantized to `0.01` before serialization; this is the effective precision used for both the bridge and the tolerance check
- overall reconciliation status: pass

### Zero-balance limitation retained
The official glossary uses field numbers, not the PDF page numbers, and the local glossary text confirms the field definitions without establishing zero balances as usable economic exposure:
- Field 12: `Current Actual UPB` — “The current actual outstanding unpaid principal balance of a mortgage loan…”
- Field 44: `Zero Balance Code` — “A code indicating the reason the loan's balance was reduced to zero or experienced…”

The sample therefore retains recorded zero balances as reported source values with a documented zero-balance reason field only when the sample records establish a populated code. The glossary does not validate those zeros as usable economic exposure for downstream portfolio exposure logic. In this project, zero-balance rows remain a limitation on interpretation and are not treated as validated economic exposure.

### Completion status
Sample-based engineering is complete for the verified ingestion and monthly reconciliation scope that this project has actually tested. Historical-data acquisition remains open and is explicitly retained as the next prerequisite for any broader portfolio conclusions or modeling work.

### Historical-data acquisition handoff
Use the verified official Fannie Mae product page and the Data Dynamics route to locate the historical Single-Family Loan Performance download options without expanding the sample pipeline.

Checklist:
1. Open the official product page: https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data
2. Follow the Data Dynamics access route from the product page and sign in if required.
3. In the Data Dynamics listing, identify the Single-Family Loan Performance download area and confirm the available package options.
4. Select one acquisition-quarter cohort only, along with its available monthly follow-up files, and record the package names and sizes without downloading the full archive set.
5. Save the package list and dates before any download; do not claim a quarter or file set that is not explicitly listed.
6. If the authenticated download list is unavailable to this environment, ask the user to provide either a screenshot of the Data Dynamics package list or the package names and sizes so the project can match the exact acquisition route and scope.

The specific screen needed is the authenticated Data Dynamics package or file-list page that shows the Single-Family Loan Performance options and the available package names and sizes for a single historical cohort. No downloads, no model work, and no expected-loss calculations are included in this handoff.

---

## Phase 2C — historical schema verification and bounded pilot

### File provenance and size
- Source file retained at `data/raw/fannie_mae_loan_performance/2010Q1.csv`.
- Corresponding original download retained locally, outside the project directory (path redacted for publication).
- SHA-256 checksum on the preserved project copy matches the original download exactly: `db167bad9a51ab7e3c9e867a24cfd1b5dd87a89bad4a42254b6c7fb9558ea95d`.
- `file` reports the preserved file as `CSV text` and there is no compressed archive or second copy in the project raw-data directory.
- The earlier 364.5 MB reading was not the preserved raw file under project control; the verified preserved file is 5.3 GB, and the evidence shows the exported CSV is a direct text copy rather than a compressed or partially downloaded artifact.

### Schema evidence
- The local official glossary and file-layout document is retained at `crt-file-layout-and-glossary.pdf` and also under `data/raw/fannie_mae_loan_performance/crt-file-layout-and-glossary.pdf`.
- The glossary defines the relevant field positions for the historical quarter:
  - Field 1: Reference Pool ID
  - Field 2: Loan Identifier
  - Field 3: Monthly Reporting Period
  - Field 12: Current Actual UPB
  - Field 44: Zero Balance Code
  - Fields 111-113: Origination Classic FICO®, Issuance Classic FICO®, Current Classic FICO®
- The real `2010Q1.csv` rows are 113 fields wide, and the raw export begins with a leading empty field before the first structured value. This is not a separate “index” field; it is a leading blank export slot caused by the CSV export format, while the glossary defines the actual 1-based field positions.
- The sample layout remains 108 columns and is still supported. The historical schema requires a separate explicit 113-column path, which is implemented in the project code and rejected clearly if another layout is encountered.

### Deterministic pilot selection and results
- Selection rule: choose the first 1,000 unique loan identifiers in sorted order from the raw file, independent of outcome, performance, or future censoring.
- Selected loan count: 1,000
- Retained monthly records for selected loans: 64,541
- Distinct loans retained: 1,000
- Distinct months retained: 195
- Min reporting month: 2010-01-01
- Max reporting month: 2026-03-01
- Duplicate loan-month keys: 0
- Overall pilot status: pass

### Output artifacts
- Historical ingest DB: `artifacts/runs/historical_ingest/fd292a12b4b8477daccb9328e5e32825/historical_monthly.db`
- Historical ingest Parquet: `artifacts/runs/historical_ingest/fd292a12b4b8477daccb9328e5e32825/historical_monthly.parquet`
- Historical ingest metadata: `artifacts/runs/historical_ingest/fd292a12b4b8477daccb9328e5e32825/historical_ingest_result.json`
- CLI evidence: `./.venv/bin/python -m mortgage_risk.cli historical-ingest --input data/raw/fannie_mae_loan_performance/2010Q1.csv --output-dir artifacts/runs/historical_ingest --max-loans 1000` returned `status: pass`.

### Validation status
- The new historical schema support is covered by focused tests in `tests/test_historical_ingest.py`.
- The existing sample ingestion and monthly summary tests still pass in the canonical project environment.
- This is a bounded pilot milestone only. It does not constitute full-quarter ingestion, portfolio modeling, expected-loss estimation, or dashboard work.

### Completion status
Phase 2C is complete for the bounded historical-schema verification and deterministic pilot milestone. The project remains within the evidence-first workflow and stops before broader quarter processing or model development.
