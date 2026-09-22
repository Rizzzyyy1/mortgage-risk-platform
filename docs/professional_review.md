# Professional review and use boundaries

## Intended use and model inventory

This is a local mortgage-risk research platform. The permitted use is analytical demonstration and reviewer evaluation. It is not approved for underwriting, pricing, provisioning, regulatory capital or automated customer decisions. Those uses require new evidence and organizational controls, not a renamed dashboard.

| Component | Method and use | Principal limitation |
|---|---|---|
| Monthly descriptive layer | Reconciled loan-month counts and eligible reported balances | Single acquisition cohort; masking and unresolved balances remain explicit |
| Historical event benchmark | Competing-event cumulative incidence and risk-set accounting | Payoff includes maturity; censoring assumptions and source revisions matter |
| Conditional 12-month benchmark | Smoothed three-class categorical probabilities; validation selects smoothing | Conditional complete-case target; only 77 held-out defaults; uneven segment calibration |
| Illustrative lifetime loss | Amortization, competing hazards, assumed severity and recovery timing | Hypothetical loan; no estimated cohort LGD or validated macro transmission |
| Expanded multinomial challenger (original, immutable) | FICO/LTV/DTI/term plus delinquency, occupancy and purpose | Later-cohort (2011Q1) AUC improves but calibration acceptance failed (O/E 0.787); not promoted. Superseded for calibration purposes by the redevelopment row below, which reuses this same trained model. |
| Development-only calibration experiment (original, immutable) | Five-fold out-of-fold intercept adjustment, cross-fitted within 2010Q1 | No meaningful internal improvement (9.34e-7 < 1e-6 tie threshold); unchanged model retained |
| PD redevelopment: development-validation (2011Q1) → calibration-fitting (2012Q1) → final evaluation (2013Q1) | Same training population/predictors as the original challenger; development-only chronological selection using 2011Q1; intercept calibration fit on 2012Q1 alone; one evaluation on untouched 2013Q1 — three loan-disjoint cohorts in three different, non-interchangeable roles, not three independent tests of the final model | All six preregistered aggregate quantitative gates passed on 2013Q1 (O/E 0.8139, within [0.8,1.25] but close to its floor) — but a bootstrap-quantified segment review found the same opposite-direction miscalibration: current/unmodified (99.8% of loans) and FICO 720+ (87% of loans) overstate risk with 95% CIs entirely below the 0.8 floor; two-month-delinquent and FICO<660 understate risk, with point estimates above 1.25 whose CIs overlap the band. **Overall acceptance: qualified/pending review, not an unconditional pass.** Supports ranking-only research use for 2010-2013 primary-conforming vintages; not promoted; not accepted for any probability-based use. |
| Monitoring replay | PSI and observed/expected counts on saved snapshots | Retrospective judgmental thresholds; not live alerts |
| Default-to-workout linkage (v2) | Follows every 2010Q1 default episode to its last supportable resolution; cross-checked against loss-field loans | 24.1% of default episodes reach disposition; the other 75.9% (payoff-after-default, cure, other-exit, still-open) are excluded from any disposed-only severity sample |
| Default-anchor exposure | Reported balance/masking/terminal status at the original default anchor, reused unchanged from exposure_eligibility | 5.6% of default episodes have no supported exposure evidence at all; a prior-balance proxy is separately labeled, never substituted |
| Realized-loss profile | Descriptive, undiscounted accounting identity; original 1,880-loan complete-case figure preserved, plus a separately named 2,108-loan official-formula variant implementing Fannie Mae's own retrieved and traced R code (`LPPUB_StatFile_Production.R`) | Explicitly not LGD: the vendor's own credit-event trigger (180-day) is confirmed different from this project's default-proxy anchor (90-day), agreeing on the same month for only 1.1% of loans — a byte-exact loss formula does not by itself validate this project's event definition; still covers only the 24.1% of default episodes that reach disposition |

The mathematical and statistical definitions remain in methodology.md and target_definitions.md. The project developer maintains these components; an independent validator and production owner have not been appointed. User interface acceptance is not independent model validation.

## Control assessment and remediation

| Concern | Implemented evidence/control | Remaining work and acceptance condition |
|---|---|---|
| Data quality | Count/balance/key reconciliation; raw values and exclusions retained | New cohorts must pass equivalent schema and cohort checks before use |
| Reporting integrity | Dashboard checks all required report, validation, schedule and sensitivity fingerprints before reading results; missing coverage or changed inputs stop the build | Hashes detect accidental changes, not malicious replacement of both data and receipt; independent attestation and access control are absent |
| Change control | Unique run outputs; accepted historical runs preserved; meaningful regression tests and repeatable release-check script | No reviewed Git history yet; first commit requires deliberate review of the index and distributable files |
| Leakage and model selection | Chronological, loan-disjoint partitions and validation-only selection | Revised vendor history is not true point-in-time data; no retuning on the held-out test |
| Statistical validity | Calibration, discrimination, segment support and uncertainty reported | Multiple cohorts and fresh validation required before broader generalization; examine current/unmodified calibration without reusing test for selection |
| Economic validity | Reported balance distinct from usable exposure; scenario assumptions explicit | Resolve masking boundaries and establish supported severity/recovery/macro models before actual-cohort lifetime loss use |
| Independent challenge | Developer implementation checks with distinct calculation paths | Objective external model review required before material business use; no independent certification is claimed |
| Security and privacy | Local execution, aggregate dashboard, excluded raw/run data, no external dashboard dependencies | Authentication, authorization, retention policy, audit log integrity and threat assessment required if deployed |
| Operations | Reproducible synthetic demo; fail-closed reporting inputs | Historical run references remain cohort-specific; backup/restore drill, performance budget and scheduled-job recovery remain unimplemented |
| Dependency assurance | Pinned runtime/test/build versions and clean installation check; a vendor-data-free GitHub Actions workflow (`.github/workflows/ci.yml`, minimal `contents: read` permission, no credentials) is included and its steps have been run locally in a fresh environment | The workflow has not yet been executed by GitHub itself — this repository has no remote configured yet, so no hosted CI run exists. Local step-by-step verification is not equivalent to a hosted run and should not be described as "CI passing" until GitHub has actually run it. Vulnerability review, supply-chain hashes and cross-platform coverage remain open; version pins alone are not a security assessment |

For a data/model defect: retain the affected run, stop its promotion, record scope and impacted downstream outputs, correct on a new run, then rerun affected validation and reporting gates. Rollback means selecting an intact previously accepted run, never overwriting it. A failed integrity check must be investigated; do not regenerate the receipt merely to silence the failure. New receipts require documented review of changed inputs and downstream acceptance.

## Review reference

Design reference: [Federal Reserve SR 26-2, Revised Guidance on Model Risk Management, April 17, 2026](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm), which supersedes SR 11-7. This project adopts proportionate attention to intended use, limitations, testing and objective challenge; this is not a compliance opinion or an institutional validation program. Applicability to a regulated institution must be assessed separately.

## Five-minute reviewer walkthrough

**Where to start:** the README's "For reviewers: start here" section, then the [reviewer presentation](reviewer_presentation.html) (`docs/reviewer_presentation.html`, 8 slides, standalone offline HTML) for a nontechnical overview, then `docs/final_report.md` for the full narrative and acceptance matrix. Read the verified scope and limitations before looking at any performance metric in isolation.

**What to demonstrate, in order:**
1. In the historical dashboard's Portfolio view, compare early and late months; explain why missing/masked balances cannot be treated as usable exposure.
2. In Model, compare the selected benchmark to the constant model. Note that the dashboard shows **only the original, frozen historical benchmark** — it does not display either the original challenger or the redeveloped/calibrated candidate, both of which live only in the documentation and evidence artifacts referenced below.
3. In Stress, distinguish 12-month default probability, undiscounted lifetime loss and timing-adjusted PV. Explain that the loan and severity/scenario assumptions are illustrative, not measured.
4. In Evidence, inspect run identity, validation qualifications and the separation of engineering acceptance from economic readiness.

**Which results to explain:** the redeveloped/calibrated PD candidate's aggregate result (all six preregistered gates passed on the untouched 2013Q1 cohort, AUC 0.875 vs. 0.639 benchmark, O/E 0.814 within [0.8, 1.25]) — framed as discrimination, not percentage accuracy — alongside the separate, complete retrospective loss-workout and vendor-reconciled-loss evidence (24.1% default-to-disposition rate; median $22,824 net loss on the 1,880-loan complete-case subset).

**Which limitations to disclose, every time these results are shown:** (a) overall model acceptance is **qualified/pending review**, not an unconditional pass — the same aggregate O/E improvement coexists with a well-supported, opposite-direction segment-calibration finding (current/unmodified and FICO 720+ overstate risk with 95% CIs entirely below the 0.8 floor; two-month-delinquent and FICO<660 understate risk, with point estimates above 1.25 whose CIs overlap it); (b) this supports ranking-only research use, not any probability-based use (pricing, provisioning, lending); (c) predictive LGD and actual-portfolio lifetime loss are not validated and remain a separate, uncoupled track, because the vendor's own 180-day credit-event trigger and this project's 90-day default-proxy anchor agree on the same month for only 1.1% of loans.

**How to run the synthetic demonstration without vendor data**, from a clean checkout:
```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -r requirements-build.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation .
.venv/bin/python -m pytest -q
.venv/bin/python -m mortgage_risk.demo --output artifacts/runs/synthetic-demo-001
```
Or simply `sh scripts/check_release.sh` for all of the above plus the dependency check in one pass. Compare the checksummed outputs; the demo uses invented inputs and the existing risk/loss engines, and its result is explicitly labeled `SYNTHETIC ONLY`.

**Private historical artifacts are required for the historical dashboard and are not bundled** in this distributable package: `.venv/bin/python -m mortgage_risk.dashboard` only works in the original workspace, where the private vendor-derived accepted-report artifacts already exist. A clean checkout has no such artifacts; use the synthetic demo there instead, and do not claim it recreates the historical dashboard.


## Current model decision — 2026-09-22 (updated: acceptance qualified, pending segment review)

**Original challenger (immutable historical record):** external acceptance was withheld. On 471,968 resolved outcomes from 2011Q1, AUC 0.86808 versus 0.65738 benchmark and better aggregate log loss/Brier, but 890 defaults were observed versus 1,131.10 expected: O/E 0.78685 failed the preregistered 0.8–1.25 criterion. A development-only calibration experiment (cross-fitted within 2010Q1) made no material improvement (9.34e-7 < 1e-6 tie threshold). This result stands unchanged.

**Redevelopment, evaluated once, in three non-interchangeable roles:** 2012Q1 and 2013Q1 were acquired, verified and checksummed. 2011Q1 served only as a development-validation cohort for a chronological out-of-cohort model-selection comparison (the identical `logistic_1.0` model resulted). 2012Q1 served only to fit intercept calibration offsets, accepted against its frozen tie threshold. 2013Q1 was the one genuinely untouched final evaluation — these are loan-disjoint cohorts, not three independent tests of the final model; only 2013Q1 tests it. It **passed all six preregistered aggregate quantitative gates**, including calibration (O/E 0.8139, inside [0.8, 1.25] but close to its floor, meaning expected defaults still ran about 23% above observed). This is a real, evaluated-once result, not a promise, and it does not retroactively validate the original failed run.

**This does not clear the model for business use, and the aggregate pass alone does not establish overall acceptance.** A bootstrap-quantified segment review (`docs/final_report.md`) found the same opposite-direction miscalibration on 2013Q1 that appeared on 2011Q1 and 2012Q1, and quantified it: the current/unmodified segment (99.8% of loans) and FICO 720+ segment (87% of loans) both overstate risk (O/E < 1), with 95% intervals entirely below the 0.8 floor; the two-month-delinquent and FICO<660 segments both understate risk (O/E > 1), with point estimates above the 1.25 ceiling whose 95% intervals' lower bounds sit just inside the band, so — unlike the first two segments — the evidence does not establish separation from the band with the same 95% confidence. This is well-supported systematic error in the segments holding the large majority of the loan population, not sparse noise, and the frozen criteria this project set for itself say a passing aggregate cannot override it, even though no formal segment-level gate was pre-specified. **Overall acceptance is therefore qualified/pending a reviewer decision, not an unconditional pass.** No segment-specific fix was attempted (the frozen protocol excluded it); any such remediation is a new, separately-scoped project with a freshly reserved final-test cohort, since 2013Q1 cannot become untouched again. The supported scope is aggregate 12-month default-proxy **ranking**, as evidenced on the cohorts actually evaluated — not a claim that ranking is equally strong within every segment or that it generalizes to other vintages or economic regimes — on 2010–2013 primary-conforming acquisition vintages, for research use only; it does not support probability-based use (pricing, provisioning, lending). Neither model is approved for business decisions. Delivering this research package is not the same claim as approving the model for use. The historical dashboard continues to show the original benchmark and illustrative stress chain; it does not display either challenger result.

**Correction note (2026-09-22):** an earlier version of this section described all four segments' intervals as "entirely outside" the reference band; only the two overprediction segments' intervals actually lie entirely outside it. Corrected here; see `docs/project_status.md` for the full correction record.

Evidence: `external_evaluation_results.md`, `calibration_remediation.md` (original, immutable), `docs/redevelopment_plan.md` (redevelopment, with the four separate verdicts) and `docs/final_report.md` (acceptance matrix and quantified segment review, this milestone). Tests and distinct SQL recomputation are developer checks, not organizationally independent validation.

## Monitoring specification and response

This is a proposed operating specification, not a deployed alert service. Apply it to each new approved batch and review matured 12-month outcomes monthly when available. Before outcomes mature, report data quality and score distributions only; never call unavailable labels zero defaults. No organizational owner has been appointed: a future operator must assign data, model-review and escalation responsibilities before operational use.

| Check | Decision rule | Response |
|---|---|---|
| Source/schema/lineage | Missing provenance, incompatible fields, changed frozen hashes, duplicate keys or join multiplication | Quarantine batch; stop scoring/promotion; investigate without replacing receipts to hide changes |
| Feature availability | Missing/invalid/unseen rates and definition changes against development reference | Publish counts and shift distributions; require review for unsupported values. No universal numeric drift threshold has been validated |
| Outcome support | Fewer than 100 default events or unresolved fraction above 1% | Insufficient evidence for acceptance; retain censoring bounds and defer approval |
| Aggregate calibration | O/E outside 0.8–1.25 on the specified resolved target | Fail acceptance; preserve run and investigate. Existing failure remains open |
| Comparative performance | Paired log-loss 95% upper difference >=0; Brier worse; or AUC degradation >0.02 versus frozen comparator | Fail the corresponding frozen gate; do not optimize thresholds after viewing outcomes |
| Segments | Report counts, defaults, expected defaults, O/E and scoring metrics; fewer than 20 defaults or 100 loans is descriptive insufficient support | Investigate deterioration even when aggregate gates pass; do not fit sparse segment corrections automatically |
| Economic inputs | Unresolved masking, unsupported severity/recovery or macro transmission | Block actual-cohort lifetime-loss claims; keep illustrative scenarios labeled |

These thresholds are project judgments, not regulatory standards or calibrated alarm probabilities. Loan-bootstrap intervals condition on the frozen model and observed cohort; repeated monitoring and common macroeconomic dependence require additional statistical design. Mean shifts and PSI cannot prove model validity or explain causation.

Record batch ID, source/model/config hashes, reporting and outcome cutoff dates, coverage, checks, findings, reviewer decision and impacted outputs. Preserve a failed run; use a new version for remediation. Never silently substitute a different model. No automatic retraining, promotion or production rollback is implemented.

## Strategic completion sequence

1. Finish the research delivery: current evidence index, visible failed calibration gate, reproducible synthetic demonstration, dependency/test check and explicit dashboard version boundary. The default-to-workout linkage, default-anchor exposure and descriptive realized-loss profile (see model inventory above and redevelopment_plan.md) are now part of this delivery; they remain a separate, descriptive evidence track from the PD/calibration model and are not shown on the historical dashboard.
2. Verify the expanded dependency set in a clean environment, then review the distributable source/index. The clean expanded-environment check now passed on Python 3.14/macOS ARM64 (109 tests, one intentional vendor skip); cross-platform verification remains open. Publication requires a separate authorized action.
3. Further modeling as a distinct redevelopment is now complete for this scope: 2012Q1/2013Q1 were acquired, the chronological development/calibration/final-test roles were frozen and followed, the one final evaluation passed its aggregate quantitative gates, and the resulting segment-calibration limitation was quantified with bootstrap uncertainty and given an explicit qualified/pending overall-acceptance status rather than left as a passing headline (see the model inventory and "Current model decision" above). Any further modeling work (segment-specific remediation, a new held-out cohort, or a different model family) is a new, separately-scoped milestone requiring a freshly reserved final-test cohort, not a continuation of this one.
4. Operational deployment and actual-cohort loss estimation remain separate, uncompleted objectives requiring independent review, economic evidence and operational controls.


## Clean package handoff

The expanded-dependency clean-install gate passed on 2026-09-22; see release_guide.md for exact evidence and limits. No files were committed or published. The finite local research package is ready for reviewer handoff, while the failed model gate and unsupported actual-cohort lifetime loss remain prominent restrictions.
