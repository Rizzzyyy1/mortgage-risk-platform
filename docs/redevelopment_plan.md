# Multi-cohort redevelopment and loss feasibility

## Objective and present limits

Resolve two separate gates: transfer of default probabilities across cohorts, and defensible actual-cohort economic loss measurement. No guaranteed numerical fix is claimed. Existing engineering, model exports and failed evaluations remain immutable. The small intercept experiment already exhausted its bounded scope.

## Minimum additional acquisition

Two primary acquisition/performance files are needed: **2012Q1 and 2013Q1**, with matching release/layout information. Keep original filenames under data/raw/fannie_mae_loan_performance/. Inspect compressed and expanded sizes and available local disk before extraction. Do not use iCloud storage, silently substitute a sample, or download all vintages. Neither file is currently local. Acquisition requires the user's authenticated vendor route; no authentication bypass or terms acceptance is attempted.

| Role | Acquisition cohort | Prediction snapshot | Outcome horizon |
|---|---|---|---|
| Development | Existing 2010Q1 | Jan 2011 | Jan 2012 |
| Development | Existing 2011Q1 | Jan 2012 | Jan 2013 |
| Calibration | New 2012Q1 | Feb 2013 | Feb 2014 |
| Final test | New 2013Q1 | Mar 2014 | Mar 2015 |

Prior-role outcomes end before the next snapshot. One additional month of seasoning per successive role creates a known population difference, to be reported and checked. These adjacent vintages are a minimum transfer test, not broad cycle coverage. Source revisions remain a point-in-time limitation. The previous unaccessed 2012Q1 final-test reservation is explicitly superseded before acquisition; 2013Q1 is the new reserved final test. Inspected 2011Q1 outcomes may now inform development, but their original failed external result cannot be erased or recast as independent evidence for a revised model.

Freeze the machine-readable roles in configs/multi_cohort_redevelopment.json. Verify identifier disjointness across every cohort, schema/code validity, snapshot feature availability, censoring and outcome support before fitting. Development-only temporal comparison precedes calibration; the calibration cohort may fit probability adjustments but cannot choose an unrestricted feature search. Freeze all parameters before final outcomes. Retain original quantitative gates and explicit segment review. If event support is insufficient, stop acceptance rather than change gates after inspection.

## Loss-data feasibility and mathematical contract

Local glossary page 5, fields 52–62, identifies foreclosure/disposition dates, five expense categories and four proceeds categories applicable to Single-Family data. Page 6 distinguishes modification non-interest-bearing UPB (63), principal forgiveness (64), and CRT-only modification-loss amounts (75–76); do not assume CRT fields apply to Single-Family. Dates and accounting fields alone do not establish a fully observed economic loss.

First build a default-to-workout linkage using the existing first-default proxy. Include cured defaults, unresolved workouts, credit-related sales and missing disposition information. A disposed-property-only sample estimates loss conditional on disposition, not LGD conditional on every default. Preserve revised/repeated balances and identify the final available accounting observation once per loan; never sum repeated cumulative disclosures across months. Blanks remain unknown, not zero. Check costs/credits signs, recoveries after disposition and incomplete follow-up before setting any loss label.

Define a principal-and-expense perspective explicitly before estimation: outstanding supported principal at the chosen default anchor plus verified eligible costs minus verified proceeds. This is only a provisional accounting identity: missed interest, advances, forgiveness, deferred principal, sales treatment and recovery timing require source-specific reconciliation. Avoid double-counting net sale costs or adding forgiven principal already reflected in exposure. Do not clamp negative net loss or loss above principal without investigating; disclose conventions separately from raw outcomes.

LGD = defined net loss / valid positive exposure at the same default anchor. Masked/unresolved exposure prevents an exact ratio; coverage and selection bias must be reported. No original-balance substitution. Discounted loss additionally needs dated cashflows or an explicitly qualified timing approximation; a disposition date alone is not each recovery receipt date.

Portfolio expected loss requires sum over future months of survival to month start × default hazard × exposure conditional on default × severity conditional on default, with consistent payoff/maturity competition. The current 12-month complete-case classifier is not a validated monthly hazard path. Actual-portfolio lifetime loss therefore remains blocked even if a small realized-loss sample can be reconciled. Macro sensitivities remain scenarios until relationships have suitable time-series evidence.

## Efficient execution order and stop rules

1. Profile existing 2010Q1 loss fields once with bulk SQL; save narrow raw-string evidence and aggregate coverage. No model fitting or full-ingestion rebuild.
2. Obtain the two specified cohorts through the authorized route; verify disk capacity and release/layout before processing. Reuse bulk adapters but remove fixed-date assumptions with tested explicit parameters.
3. Complete bounded multi-cohort PD development/calibration, then one final evaluation. No silent second use of the final test after failure.
4. Link losses to all default episodes and reconcile a hand-checkable set of complete, cured and censored cases. Only then approve a severity label/model.
5. Validate exposure paths and monthly competing risks before coupling severity into actual-cohort losses. Keep the existing illustrative stress view separate throughout.

Acceptance evidence must distinguish engineering checks, statistical acceptance, realized-loss measurement and prospective lifetime-loss readiness. A missing-data or failed-model gate remains open until evidence resolves it; documentation alone is not a fix.

## Existing-data feasibility result

One 45.69-second narrow bulk scan of 2010Q1 retained 2,108 unique loans with foreclosure/disposition-related fields. 2,065 have disposition dates and 2,064 net sales proceeds. Each tested field had zero conversion failures; source size/mtime remained unchanged. 2004 loans have all nine selected monetary fields populated, which is a completeness screen, not proof of final economic settlement. All retained loan IDs match accepted cohort outcomes without duplicate keys. Detailed first-stop categories remain in linkage_checks.json; loss availability does not override original censoring/event rules.

Evidence: `artifacts/runs/loss_feasibility/30a0a02381af4b93807301fc6ef08d90/`. Includes raw-string narrow Parquet, coverage, linkage checks and the executed profiling script. No raw values imputed, LGD calculated or severity model fitted. The profile is insufficient to resolve outstanding workout bias, discount timing or masked default exposure.

## Default-to-workout linkage result v1 (step 4, 2026-09-22) — SUPERSEDED, see v2 below

This section is preserved for provenance. v1's classifier stopped scanning at the first redefault (`cured_then_redefault`) and at the first reporting gap (`gap_after_default`), which understated how many episodes actually reach disposition. v2 below corrects this by following each trajectory to its last supportable resolution; the 18.6% disposition figure quoted here is superseded by v2's 24.1%. v1's evidence and artifact directory are unchanged and immutable.

Every one of the 8,750 accepted-cohort default-proxy episodes (Phase 2F first_stop) was followed forward through its full observed post-anchor trajectory, reusing the accepted `event_rows.parquet`/`loan_outcomes.parquet` (no CSV rescan), and cross-tabbed against the 2,108 loans with recorded foreclosure/disposition loss fields:

| Category | Loans | Share | With loss fields |
|---|---|---|---|
| payoff_or_maturity_after_default | 2,940 | 33.6% | 0 |
| cured_then_redefault | 2,747 | 31.4% | 469 |
| disposed_credit_exit | 1,628 | 18.6% | 1,628 |
| cured_no_redefault_at_data_end | 1,061 | 12.1% | 0 |
| other_exit_after_default | 319 | 3.6% | 0 |
| still_delinquent_at_data_end | 39 | 0.4% | 0 |
| gap_after_default | 16 | 0.2% | 11 |

All checks passed: 0 duplicate/unmatched loan IDs, category counts sum exactly to the 8,750-loan population, all 2,108 loss-field loans are classified, and 0 unsupported zero-balance codes were found after default (consistent with the Phase 2D engineering invariant). No `cured_no_redefault_incomplete_followup`, `still_delinquent_incomplete_followup` or `unknown_status_unresolved` case occurred, i.e. no default episode's data stream quietly stops before the panel-wide latest month (2026-03) without an explaining resolution or gap flag — unlike the still-unexplained 2011Q1 late-first-appearance anomaly, this cohort shows no equivalent silent disappearance after default.

This quantifies the selection-bias concern already on record: only 1,628/8,750 (18.6%) of default episodes reach an actual disposition within their available follow-up, so a disposed-loans-only sample would omit 81.4% of default episodes, dominated by loans that pay off/mature after defaulting (33.6%, plausibly post-workout) or cure and later redefault (31.4%). The 469 `cured_then_redefault` loans and 11 `gap_after_default` loans that nonetheless carry loss fields show that foreclosure/disposition fields can be populated on a row that precedes an eventual cure-and-redefault or a reporting gap — i.e. these fields can reflect an in-process or later-reversed foreclosure action, not only a completed one. Classification deliberately stops at the first redefault row and does not chase the second episode's resolution; that second episode is unclassified by this pass, a scope limit, not evidence it is absent.

Evidence: `artifacts/runs/loss_workout_linkage/24126815af8448fe9b02b34f23ca7aa9/workout_linkage_result.json` and `workout_episodes.parquet` (per-loan category, anchor/resolution/cure months, has_loss_fields). Implementation: `src/mortgage_risk/loss_workout_linkage.py`; synthetic hand-checkable tests: `tests/test_loss_workout_linkage.py` (14 cases covering every category and the empty-input guard).

This still does not establish exposure at the default anchor, net loss amounts, LGD, or a severity label — those remain open per the mathematical contract above.

## Reference-method reconciliation against Fannie Mae's official methodology (2026-09-22)

Fannie Mae publishes its own official loss methodology: a *Loan Performance Data Tutorial* (Feb 2021, linked from the product page) that defines Credit Event Date/UPB, First 180 Date/UPB, Foregone Interest Cost, Net Loss and Net Severity, backed by official R reference code (`LPPUB_StatFile.R`, `LPPUB_StatFile_Production.R`, `LPPUB_StatSummary.R`), plus a *Single-Family Loan Performance Data FAQ* (2017). This reconciliation checks the project's descriptive realized-loss profile against that methodology field-by-field, using SF-applicable glossary fields not previously extracted.

**Access.** The tutorial page (`capitalmarkets.fanniemae.com/media/9066/display`) returns a Cloudflare bot challenge from this environment; a May 2025 Wayback Machine snapshot was used instead. The FAQ was fetched directly from Fannie Mae's own S3-hosted PDF. The R code's hosting domain (`loanperformancedata.fanniemae.com`) did not resolve from this environment (DNS failure — likely the legacy pre-Data-Dynamics portal). **The exact R formula was not independently executed; this reconciliation uses the tutorial's and FAQ's plain-English definitions, disclosed as such, not a byte-identical replication.**

**What the tutorial and FAQ established, verified field-by-field against the local glossary's own CAS/CIRT/(SF) checkmark columns (not inferred from any single boilerplate phrase):**

- **UPB at the Time of Removal (field 46)** is SF-applicable and is the vendor's own "Credit Event UPB" concept — the balance at the credit-event/removal date, distinct from this project's default-anchor UPB (the balance at the *first* 90+ day delinquency). Matched **100% (1,880/1,880)** of the realized-loss-profile population when joined to each loan's exact resolution month.
- **Net Loss** is officially defined as "the loss to Fannie Mae, **including delinquent interest**, net of any proceeds" — confirming the project's original component-based calculation was missing an interest term, exactly as flagged.
- **Net Severity** is officially "the net total loss to Fannie Mae, as a percentage of defaulted UPB... sometimes referred to as a 'loss given default' statistic" — i.e. Net Severity *is* the vendor's own LGD statistic.
- The vendor's own pre-computed convenience fields for these calculations — **Current/Cumulative Credit Event Net Gain or Loss (77/78), Delinquent Accrued Interest (85), and Interest Bearing UPB (110) — are all confirmed NA for Single-Family** (CAS/CIRT-only) in the glossary's own checkmarks. A comparable SF figure must be built from components; `realized_loss_profile.py` already does this, which this reconciliation validates as the necessary approach, not a shortcut.
- The official FAQ (Q42) states blanks in the nine cost/proceeds fields should be treated as zero — new, authoritative, field-specific guidance that qualifies this project's earlier general no-zero-fill stance for these specific fields. Applied as a separately named variant, not a silent change to the conservative figure (see below; for the current complete-case population the two are numerically identical, since there are no blanks left to fill by construction).
- **Fields 63 (Modification-Related Non-Interest Bearing UPB) and 64 (Principal Forgiveness Amount) are SF-applicable with no population-date restriction** — confirming these were never absent from the dataset, only excluded from the original nine-field extract. Field 80 (Foreclosure Principal Write-off Amount) is likewise SF-applicable. Fields 106-108 (Alternative Delinquency Resolution/count/Total Deferral Amount) are SF-applicable but the glossary states they are "populated starting with the July 2020 activity period" — a real, checkable limitation for a cohort whose defaults mostly precede that date, not an assumption of absence.
- The "populated is not proven final" caution from the earlier loss_feasibility/realized_loss_profile milestones is **refined, not withdrawn**: the official SF-Primary FAQ (Q41/Q43) gives a more directly applicable explanation than the CRT-deal-claims phrase this project previously leaned on — proceeds/expenses populate on a 90-day lag after Disposition Date and continue updating "in the same record" as activity occurs, especially for more recent dispositions. That CRT-deal-claims phrase also appears verbatim on the confirmed CRT-only fields 77/78/85, suggesting it is shared glossary boilerplate rather than proof that SF loss recognition depends on CRT reinsurance claims specifically.

**Field extraction.** One bounded, single-pass scan of 2010Q1.csv (31.5s, source stat unchanged) retained rows with any of fields 46/51/63/64/80/106/107/108 populated, joined to the accepted workout/exposure/loss-feasibility evidence with joins month-matched to each loan's own resolution month (a loan-only join was tried first and caught by its own duplicate-key assertion — one loan had up to 141 qualifying rows because Alternative Delinquency Resolution repeats monthly; fixed before any result was reported).

**Exposure denominator comparison (UPB at removal vs. this project's anchor UPB), n=1,880:** mean difference $8.54, **median difference $0.00**, range -$74,566 to +$115,332; 412 loans lower at removal (ordinary paydown during delinquency), 177 higher (capitalized arrears/advances). The two measure different things by design, not an error in either.

**Net-loss variants (USD, n=1,880):**

| Variant | Median | Definition |
|---|---|---|
| `project_conservative` | $22,824.20 | anchor UPB + 5 costs − 4 proceeds; blanks excluded from the population (original Milestone 3 figure) |
| `faq_zero_filled` | $22,824.20 | same, with official FAQ blank=zero convention; identical here because this population is already complete-case by construction — no blanks remain to fill |
| `vendor_anchored` | $23,688.68 | UPB **at removal** (not anchor) + this project's own `estimated_foregone_interest` (a simple, disclosed, non-compounding monthly approximation — NOT the vendor's CRT-only Delinquent Accrued Interest) + same zero-filled costs/proceeds |

`estimated_foregone_interest` is available for only 215/1,880 loans (11.4%): `current_interest_rate` is empirically blank on ~89% of terminal rows specifically (verified directly, not a conversion failure — it is populated on 88% of all rows generally, just not reliably on the removal row itself).

**Methodology comparison, five-way breakdown:**

| Item | Category | Summary |
|---|---|---|
| Credit-event definition and date | B | Concepts named/defined in the tutorial; exact R-code trigger logic not independently inspected (R code unreachable). |
| Exposure denominator and timing | **A** | Resolved — field 46 now extracted and compared. |
| First 90+ default vs. vendor event conventions | E | Tutorial defines a separate 180-day "First 180" milestone; whether "credit event" maps to a specific code, to First 180, or to something else is genuinely unclear without the R code. |
| Credit-event/removal UPB vs. first-default UPB | **A** | Resolved — see exposure denominator comparison above. |
| Interest calculation and required dates/rates | C | Vendor's own fields (85, 110) are CRT-only; derived a disclosed project approximation from SF-applicable fields 9/46/51 instead. |
| Expense and recovery categories | **A** | Already extracted and reconciled (fields 54-62). |
| Missing-value treatment | **A** | Resolved — official FAQ Q42 (blank=zero), applied as a named variant. |
| Forgiveness, non-interest-bearing UPB and deferrals | **A** | Resolved — fields 63/64/80/106-108 confirmed SF-applicable and extracted; not absent from the dataset, only from the original 9-field extract. |
| Observation cutoff, revisions, settlement completeness | **A** | Resolved and refined — FAQ Q41/Q43 give a more precise, SF-specific basis than the CRT-claims phrase this project previously cited. |

Six of nine items are now resolved (A); one is derivable under an explicit, disclosed convention (C); two remain genuinely open pending access to the R code (B, E) — a specific, bounded gap, not a generic "data insufficient" conclusion.

Evidence: `artifacts/runs/vendor_method_reconciliation/b758ff00b5aa468da1b81d13e64626f8/vendor_reconciliation_result.json` and `comparison.parquet`. Tests: `tests/test_vendor_method_reconciliation.py` (9 synthetic cases covering the foregone-interest formula, its null/implausible-date guards, and the vendor-anchored/FAQ-zero-filled loss arithmetic).

**Decision (item 5, superseded below): what can honestly be delivered.** The realized-loss profile is now reconciled against the official methodology and can be described, with equal confidence to before, as a *retrospective descriptive statistic for its supported population* — not strengthened into an accepted LGD model, because the "credit event" trigger definition itself (item E above) remains unverified against our own default-proxy definition, and the R code that would settle it was not reachable. Predictive LGD and actual-cohort lifetime loss remain blocked, now for a more specific, named reason than before.

## Official R code retrieved and event semantics resolved (2026-09-22, follow-on)

The R code was located and retrieved. Fannie Mae's current Single-Family Loan Performance product page ("Code (Primary)") links `https://capitalmarkets.fanniemae.com/media/document/zip/FNMA_SF_Loan_Performance_r_Primary.zip` — the current `capitalmarkets.fanniemae.com` domain, not the legacy `loanperformancedata.fanniemae.com` domain that failed to resolve last milestone. That URL is Cloudflare-blocked live from this environment, so a Wayback Machine snapshot was used (`http://web.archive.org/web/20250401064526/<that URL>`, which itself redirects, per its own archived headers, to `https://capitalmarkets.fanniemae.com/media/20936/display`, archived 2025-04-01T06:45:27Z, `content-type: application/zip`, `x-archive-orig-last-modified: 2024-08-02T13:56:53Z`). Retrieved 2026-09-22 from a public, unauthenticated Internet Archive URL — no access control was bypassed and no Data Dynamics authentication was required or attempted. Zip SHA-256 `00b6798d614ed6af75ed1e79e8908bbb0526f166d4367e4be0334af70ecd6418`; contains `LPPUB_Infile.R`, `LPPUB_StatFile.R`, `LPPUB_StatFile_Production.R` (the file inspected; SHA-256 `d6539dbdf3729879a97905d452bb2890b7b8035b2cdc00d8c035877f09a7fccc`), `LPPUB_StatSummary.R`. This is a historical archived copy (dated to the source data's own vintage), used for methodology interpretation, not asserted identical to whatever the live site currently serves.

**Credit-event trigger, traced exactly (line ~401 of `LPPUB_StatFile_Production.R`):** `zero_balance_code IN ('02','03','09','15') OR (delinquency_status >= 6 AND < 999)`. This is a genuinely different, **180-day** threshold — not this project's 90-day (`delinquency >= 3`) default-proxy anchor. Computed against the accepted `event_rows.parquet` for all 2,108 `disposed_credit_exit` loans: the two triggers land on the **same month for only 23 loans (1.1%)**; for the other 2,085 (98.9%) the vendor's trigger fires later, by a median of 3 months and mean of 5.76 months (up to 113 months in extreme cases). **This confirms the earlier caution directly: matching exposure balances do not establish matching event definitions** — they are different quantities that happen to often produce similar dollar figures because both are ultimately evaluated at the loan's terminal/disposition row, not at the trigger-date row.

**Exposure basis actually used in Net Loss (`LAST_UPB`, distinct from the vendor's own `FCE_UPB`):** at the loan's terminal row, `COALESCE(upb_at_removal, current_actual_upb)` — confirming field 46 as primary, current UPB as fallback, both read at the disposition row. (`FCE_UPB`, evaluated at the earlier trigger row, is frequently undefined by the vendor's own code when that row precedes any disposition, since it sums `zb_upb + act_upb` with no null-coalescing and `zb_upb` is not yet populated before a disposition — reported here, not used as an exposure basis.)

**Net Loss / Net Severity, traced exactly (lines ~554-571):**
- `COMPLT_FLG` (whether Net Loss is computed at all) requires a populated Disposition Date and `LAST_STAT` in `{F,S,N,T}`, which map 1:1 onto `zero_balance_code` 09/03/02/15 — an **exact match** to this project's `disposed_credit_exit` population; no independent judgment call was needed to align the two.
- `LAST_RT` is **not** the rate at the terminal row — it is the **most recent prior populated rate, carried forward**, because `current_interest_rate` is empirically blank on ~89% of terminal rows specifically (confirmed last milestone). This project's earlier `estimated_foregone_interest` used the terminal-row rate only (11.4% coverage); implementing the same carry-forward logic raised coverage to **100%** (2,108/2,108).
- `INT_COST = months(LastPaidInstallmentDate, LastDate) × ((LAST_RT/100 − 0.0035)/12) × (LAST_UPB − NON_INT_UPB)`. The **35-basis-point deduction** from the note rate (a guaranty/servicing-fee carve-out) and the **non-interest-bearing-UPB offset** were both absent from this project's earlier approximation.
- `NET_LOSS = LAST_UPB + FCC_COST + PP_COST + AR_COST + IE_COST + TAX_COST + PFG_COST + INT_COST − NS_PROCS − CE_PROCS − RMW_PROCS − O_PROCS`, with every cost/proceeds/forgiveness term (never `LAST_UPB` itself) zero-filled when missing, for every `COMPLT_FLG==1` loan — **not** restricted to complete-case. `PFG_COST` (Principal Forgiveness Amount, field 64) is confirmed as an **additive loss term**, resolving the earlier open question about its sign. `NET_SEV = NET_LOSS / LAST_UPB`, confirming Net Severity is a ratio to the same balance added into Net Loss, not a different exposure figure. `FORECLOSURE_PRINCIPAL_WRITE_OFF_AMOUNT` (field 80) is read but never used in this formula; `MODIR_COST`/`MODFB_COST` (modification-related costs) are tracked as separate metrics, not summed into Net Loss — this project's earlier formula was not missing a required term by omitting them.

**A real bug was caught before reporting anything:** the new rate-history extraction initially read raw column `c9` for Current Interest Rate; this project's established convention (a leading blank export column) requires `c{position-1}`, i.e. `c8`. The mistake produced "rates" like 98000% and a $594-million "loss" on a single loan — implausible on inspection, traced to the raw source string (`c9`='98000.00' is actually Original UPB; `c8`='6.250' is the real rate), and fixed. A permanent plausibility guard (reject any `last_rt` outside 0-20%) was added to the module so a recurrence fails the run rather than producing a silently wrong result.

**Vendor-official Net Loss, all 2,108 `disposed_credit_exit` loans (the zero-fill population, not complete-case):** mean **$40,876.51**, median **$31,120.74**, range −$163,444 to $370,002; 257 net gains (12.2%), 138 loss-exceeds-exposure (6.5%); mean Net Severity 40.4%, median 28.5% — both within typical published residential-mortgage severity ranges. For the 1,880 loans present in **both** the original complete-case figure and this wider population, the official formula alone (holding population fixed) raises the median by **$6,487.83** and the mean by **$10,558.04** — attributable to the now-materially-more-complete interest-cost term, not to population change.

| Population | n | Median net loss |
|---|---|---|
| Original (Milestone 3, complete-case + exposure-supported, **preserved unchanged**) | 1,880 | $22,824.20 |
| Official-formula (this milestone, all disposed, official zero-fill) | 2,108 | $31,120.74 |
| Official-formula restricted to the same 1,880 loans (isolates the formula effect) | 1,880 | $22,824.20 + $6,487.83 median shift |

Zero of 2,108 loans have nonzero Principal Forgiveness in this specific 2010Q1 disposed cohort — a real, checked finding, not an assumption of absence.

**Revision/as-of limitations carried forward:** 21 of 2,108 disposed loans (1.0%) have a resolution month within the last 12 months of available data, where the official FAQ's 90-day-lag/ongoing-update caution applies most. `PFG_COST`/`NON_INT_UPB` are read from the same resolution-month row as the other terminal fields; the R code's exact join chain for these two specific fields was not traced with full certainty (unlike the exactly-confirmed cost/proceeds/`LAST_UPB`/`LAST_RT`/`INT_COST` logic), so a small discrepancy from a live vendor figure remains possible for loans with nonzero forgiveness elsewhere in the cohort.

**Corrected blocker inventory — four distinct, separately-gated claims:**

| Claim | Status |
|---|---|
| Vendor-method retrospective loss measurement | Now implemented with the byte-verified official formula, for all 2,108 disposed loans |
| Descriptive disposed-subset severity (this project's own labeling) | Unchanged in kind, now cross-checked against (and moderately below) the official-formula figure |
| Predictive LGD across the full default population | **Still blocked** — selection bias (only 24.1% of default episodes ever reach disposition), cured/unresolved workouts, and the 180-day-vs-90-day event-definition gap all remain, independent of formula fidelity |
| Actual-portfolio lifetime expected loss | **Still blocked** — recovery timing, exposure paths for non-disposed episodes, macro transmission and independent model validation are untouched by this milestone |

Resolving the R-code questions materially improved the first two rows; it does not touch the last two, which the user's framing correctly anticipated.

Evidence: `artifacts/runs/vendor_official_loss_calculation/4fe2070b858446aeaf9d96d923f4d750/vendor_official_loss_result.json` and `official.parquet`, `rate_history.parquet`. Tests: `tests/test_vendor_official_loss_calculation.py` (9 synthetic cases: the exact Net Loss formula with and without zero-filling, exposure never zero-filled, the exact `INT_COST` formula with the 35bp deduction and non-interest-bearing offset, null-not-fabricated guards, the rate carry-forward window function, and the implausible-rate regression guard that caught the real bug above).

**Two reporting qualifications carry forward into the PD-calibration work below:** the retrieved `LPPUB_StatFile_Production.R` is a versioned historical reference (dated to its own August 2024 vintage via archived headers), not a live-verified current implementation, and every metric reported below is evaluated against these frozen thresholds directly -- falling within a metric's typical published range is never treated as independent validation of a calculation.

## PD calibration redevelopment: 2012Q1/2013Q1 acquired, model refrozen, calibrated, evaluated once (2026-09-22)

The user downloaded 2012Q1.csv (13.85 GB) and 2013Q1.csv (17.70 GB). Both were verified (113-column pipe-delimited, no header, identical layout to 2010Q1/2011Q1), checksummed at the source, copied into `data/raw/fannie_mae_loan_performance/`, and re-checksummed post-copy (byte-identical). Disk space was checked before copying (150 GB free against a 31.5 GB combined need). Receipts recorded at `data/raw/fannie_mae_loan_performance/2012Q1.csv.receipt.json` and `2013Q1.csv.receipt.json`; `configs/multi_cohort_redevelopment.json` updated with `source_present: true` and both checksums.

**This retrospective loss analysis (the R-code reconciliation above) is preserved as a separate, complete result and was not touched by this milestone.** The PD/calibration work below is an independent track using the SAME 2010Q1/2011Q1/2012Q1/2013Q1 cohorts for a different purpose (12-month default-proxy classification, not loss severity).

### Step 1 -- development-only model selection (`redevelopment_model.py`, `configs/redevelopment_model.json`)

The frozen protocol (written and committed to disk *before* fitting): train on the same 2010Q1 development-split rows already used by the original challenger (no change to training population or predictor set); select among the same fixed candidate grid (three L2 strengths, three benchmark smoothing values) using the **full 2011Q1 population** (472,056 loans, Jan 2012 snapshot) as a chronologically later, out-of-cohort development-validation set, replacing 2010Q1's own same-cohort internal_validation split. This is the smallest change that lets development-only selection use genuinely out-of-cohort evidence before ever touching 2012Q1 or 2013Q1. No nonlinear terms, interactions or feature search were introduced.

**Result: `logistic_1.0` was selected again** -- identical to the original frozen challenger. Its metrics on 2011Q1, recomputed independently through this new pipeline, exactly reproduce the original failed-external-evaluation numbers (AUC 0.868081, log loss 0.510349, O/E 0.786848), confirming internal consistency rather than producing a different model by construction. Seasoning/missingness differences between the two cohorts are modest (FICO/LTV/term missingness both under 0.1%; DTI missingness lower in 2011Q1 at 0.04% vs 0.85% in 2010Q1) and reported in full in the run evidence. Evidence: `artifacts/runs/redevelopment_model/49235a3eec044f748f4fe4beb4f93c12/`.

### Step 2 -- calibration on 2012Q1 only (`redevelopment_calibration.py`, `configs/redevelopment_calibration.json`)

Bounded comparison rule frozen *before* any 2012Q1 label was read: fit one pair of multinomial intercept offsets directly on 2012Q1's known outcomes (554,960 loans, 911 defaults -- not cross-fitted, since this cohort **is** the calibration set by design); accept only if multiclass log loss improves by more than a 1e-6 tie threshold, else keep the unchanged candidate. Loan-ID disjointness was checked against the full 2010Q1 (323,174 loans) and full 2011Q1 (505,196 loans, extracted via one bounded scan into `artifacts/runs/loan_id_registry/2011Q1_loan_ids.parquet` since only the snapshot-eligible subset existed before) -- zero overlap confirmed.

**Result: `adjusted` was selected.** Log loss improved from 0.3380 to 0.3298 (improvement 0.0082, far above the tie threshold); aggregate O/E moved from 0.690 (heavy overprediction) to 0.99999997 (essentially aggregate-exact, an expected property of intercept MLE, not evidence of segment-level fit). **Segment review, reported honestly rather than hidden behind the aggregate number: the largest segment (current/unmodified, 553,229 loans) improved from O/E 0.625 to 0.933, but the small two-month-delinquent segment (181 loans, 107 defaults) got *worse* -- O/E 1.212 unchanged to 1.468 adjusted.** A single global intercept shift cannot fix opposite-direction segment errors simultaneously; per the frozen protocol, no segment-specific adjustment was attempted. This is a calibration-set fit, not independent validation. Evidence: `artifacts/runs/redevelopment_calibration/66899de49fc84a8da3166d59214c2aa4/`.

### Step 3 -- the one final evaluation, on 2013Q1 (`redevelopment_final_evaluation.py`, `configs/redevelopment_final_evaluation.json`)

2013Q1 features and labels were built together in this single step, using the SAME adapter and outcome-through-March-2015 window -- by construction, no earlier step in this redevelopment reads 2013Q1 at all, so outcome-blindness is structural. All six of the original frozen quantitative gates (identical thresholds, carried forward unchanged from `configs/external_evaluation.json`) were applied exactly once, with no retuning:

| Gate | Result |
|---|---|
| Default support (>=100) | **Pass** -- 836 observed defaults |
| Unresolved fraction (<=1%) | **Pass** -- 741/659,188 (0.11%) |
| Paired log-loss 95% CI upper < 0 | **Pass** -- [-0.0193, -0.0187] |
| Brier <= benchmark | **Pass** -- 0.1113 vs. 0.1186 |
| AUC non-inferiority (within 0.02) | **Pass** -- 0.8748 vs. 0.6391 benchmark |
| Calibration O/E in [0.8, 1.25] | **Pass** -- **0.8139** |

**All six quantitative gates passed.** The calibration gate passed but close to its floor (0.8139 against a 0.80 minimum), not with wide margin. **Segment review shows the same opposite-direction pattern found on the calibration cohort, now reproduced on a genuinely untouched cohort:** current/unmodified overpredicted (O/E 0.736, 656,937 loans), two-month-delinquent underpredicted (O/E 1.414, 144 loans), FICO 720+ overpredicted (O/E 0.628, 573,236 loans), FICO <660 underpredicted (O/E 1.299, 9,359 loans). The aggregate gate passing does not mean these segments are individually well calibrated; a user of this model in the current/unmodified or high-FICO segment specifically should expect the model to overstate their default risk. Evidence: `artifacts/runs/redevelopment_final_evaluation/21a27da4febc4ebdbeba08698e5b18f1/final_evaluation_result.json` and `predictions.parquet`.

### Four separate verdicts

1. **New-cohort engineering: pass.** Both files verified, checksummed, disjoint, structurally identical to the established 113-column layout; all adapter/join/duplicate-key checks passed on all three new cohort builds (2012Q1 calibration, 2013Q1 final test, plus the 2011Q1 loan-ID registry).
2. **Revised model discrimination and calibration: materially improved, not unconditionally fixed.** Discrimination is strong and stable (AUC ~0.87-0.88 across every cohort checked). Aggregate calibration, which failed on 2011Q1 (O/E 0.787), now passes on 2013Q1 (O/E 0.814) after intercept calibration fit on 2012Q1 -- but the same segment-level opposite-direction miscalibration identified before calibration is still present after it, on an independent cohort.
3. **Final external acceptance: all six aggregate gates passed, but overall acceptance is qualified/pending, not an unconditional pass** (see the bounded acceptance-review addendum immediately below, which quantifies why). This supports use, with disclosed and now quantified segment caveats, for aggregate 12-month default-proxy risk-**ranking** on populations resembling this development/calibration lineage (2010-2013 acquisition vintages, primary conforming SF loans); it does not support claims of uniform calibration across FICO/delinquency segments, of validity for other vintages or economic regimes, of any severity/loss coupling, or of any probability-based use (pricing, provisioning, lending).
4. **Remaining LGD/lifetime-loss limitations: unchanged by this milestone.** The realized-loss profile and vendor-official loss calculation above remain a separate, complete result. This project's 90-day default-proxy PD target is kept distinct from the vendor-reference 180-day/credit-event trigger used in the loss reconciliation; nothing here couples the two, fits a severity model, or estimates actual-portfolio lifetime loss. No production promotion, dashboard replacement, commit or publication was performed.

Tests: `tests/test_multi_cohort_adapter.py` (5), `tests/test_redevelopment_model.py` (4) -- 168 tests passed overall (up from 159).

## Bounded acceptance review: segment finding quantified, overall acceptance qualified (2026-09-22, corrected 2026-09-22)

**Correction note:** this section originally said "all four intervals lie outside [0.8, 1.25]" and, in its "Consequence for intended use" paragraph, described the model as understating risk for the current/unmodified and high-FICO segments and overstating it for the delinquent and low-FICO segments. Both statements were checked against the exact saved intervals and found wrong; corrected below. See `docs/project_status.md` for the full correction record. No run artifact, prediction or metric changed -- only this prose.

The frozen criteria this project set for itself (`docs/external_evaluation.md`: "a passing aggregate cannot override material segment deterioration"; `docs/calibration_remediation.md`: "material segment degradation prevents promotion even if aggregate gates pass") already distinguished aggregate-gate passage from overall acceptance. Neither document specifies a formal, quantitative segment-level gate -- the [0.8,1.25] band below is a diagnostic reference (the same band already frozen for the aggregate gate), not a retroactively-applied pass/fail rule. This addendum makes the aggregate-versus-overall distinction explicit and quantifies it, without refitting, recalibrating, changing any threshold, or reusing 2013Q1 for anything beyond the evaluation already performed.

**Evidence-role correction.** 2011Q1, 2012Q1 and 2013Q1 are loan-disjoint but play three different, non-interchangeable roles: 2011Q1 is development-validation (it shaped model selection), 2012Q1 is calibration-fitting (its outcomes fit the intercept offsets), and 2013Q1 is the one final evaluation -- the only cohort that genuinely tests the frozen model. They are not three independent tests of it, and passing on 2013Q1 does not by itself establish broader economic-cycle or later-vintage validity. O/E 0.8139 is recorded as passing the frozen [0.8,1.25] range while still indicating aggregate overprediction: expected defaults ran about 23% above observed.

**Segment quantification** (`src/mortgage_risk/segment_acceptance_review.py`; 16 tests in `tests/test_segment_acceptance_review.py`, including boundary-case tests for the direction and band-relationship classifications used below): a paired bootstrap over the already-saved 2013Q1 `predictions.parquet`, rejoined only with the frozen cohort's `features.parquet` (SHA-256 verified equal to the hash already recorded in `final_evaluation_result.json`) to recover segment labels -- no refit, no recalibration, no new scoring. Every point estimate was cross-checked to exactly reproduce the frozen record before any interval was computed. Delinquency status and FICO band are two different, overlapping partitions of the same 658,447-loan population -- their percentages below must not be added across partitions.

| Segment | Loans | % of this partition | O/E | Direction | 95% bootstrap CI | CI vs. [0.8,1.25] band |
|---|---|---|---|---|---|---|
| Current/unmodified | 656,937 | 99.8% | 0.736 | overprediction (overstates risk) | [0.675, 0.797] | **entirely_below** the floor |
| Two-month delinquent | 144 | 0.02% | 1.414 | underprediction (understates risk) | [1.217, 1.598] | **overlaps_ceiling** -- lower bound 1.217 is inside the band |
| FICO 720+ | 573,236 | 87.0% | 0.628 | overprediction (overstates risk) | [0.561, 0.694] | **entirely_below** the floor |
| FICO <660 | 9,359 | 1.4% | 1.299 | underprediction (understates risk) | [1.104, 1.507] | **overlaps_ceiling** -- lower bound 1.104 is inside the band |

Only the two overprediction segments have intervals lying entirely outside the band, which is what supports separation at 95% confidence; the two largest -- current/unmodified and FICO 720+, each a different large majority of the same population -- have intervals that are both tight (hundreds of thousands of loans) and entirely below the floor. The two underprediction segments have well-supported point-estimate breaches (87 and 140 defaults, both above the project's 20-default insufficient-support threshold) but their intervals overlap the band, so the evidence does not establish the same separation for them. **This is well-supported systematic error, not sparse evidence, in both directions** -- distinguishing all four from the smaller, genuinely insufficient-support segments (e.g. `fico_band=missing`, 330 loans, 2 defaults, CI [0.0, 4.81]) that the frozen protocol already flags as descriptive-only. Each interval is a per-segment 95% interval, not a simultaneous guarantee across every segment reported.

**Consequence for intended use.** A ranking-only research use (ordering loans by relative risk, as evidenced on the cohorts actually evaluated) is materially less exposed to this finding than any probability-based use; AUC discrimination (0.875) is unaffected by intercept-level segment bias, though this does not itself establish equally strong ranking within every segment or generalization to other vintages. The model is not accepted for pricing, provisioning or lending use, where this pattern would mean systematically **overstating** risk for the majority current/unmodified, high-FICO book and **understating** it for delinquent or low-FICO loans.

**Verdict: overall model acceptance is qualified/pending a reviewer decision, not an unconditional pass**, even though all six aggregate gates passed. Full acceptance matrix: `docs/final_report.md`. Any segment-specific remediation is a new, separately-scoped project requiring development-only changes and a freshly reserved final-test cohort; 2013Q1 is now a used, disclosed result and cannot become an untouched test again. 184 tests passed overall (up from 168; 13 of the 16 new tests were added during the correction that fixed this section's wording -- see `docs/project_status.md`).

## Default-to-workout linkage result v2 — full trajectory, corrected (2026-09-22)

v1 above stopped classification at the first redefault or reporting gap. Two independent review findings from hand-tracing real loan histories motivated a correction before any severity work: (1) **loan SYNTH-A** (a synthetic label standing in for a real hand-traced 2010Q1 loan; the actual identifier and its full history are retained only in the private, gitignored `artifacts/runs/` audit evidence, not published here) cures, redefaults, crosses a reporting gap, cures a second time, and only then reaches an `other_exit` code five transitions after its first redefault — v1 stopped at the first redefault and never saw this; (2) **loans SYNTH-B and SYNTH-C** (same redaction convention) each end their available history with delinquency still climbing *and* a payoff code (01) on the same row — the project's own frozen `ambiguous_same_month` rule (target_definitions.md) says this must not be resolved by code priority, but v1's code-priority scan would have silently called both "paid off after default."

v2 (`src/mortgage_risk/loss_workout_linkage.py`) follows every trajectory to its last supportable resolution while keeping the single unit of analysis fixed at the original Phase 2F anchor (redefaults are events within one episode, never a new episode, and the anchor is never moved to a later redefault). It preserves both the path taken (`cure_count`, `redefault_count`, `ambiguous_count`, `had_gap`, and a full `path_json` transition list) and the final resolution:

| Category | Loans | Share | With loss fields | With ≥1 redefault | With a gap |
|---|---|---|---|---|---|
| payoff_or_maturity_after_default | 4,124 | 47.1% | 0 | 1,183 | 3 |
| cured_no_redefault_at_data_end | 1,716 | 19.6% | 0 | 655 | 0 |
| disposed_credit_exit | 2,108 | 24.1% | 2,108 | 470 | 19 |
| other_exit_after_default | 676 | 7.7% | 0 | 354 | 6 |
| still_delinquent_at_data_end | 124 | 1.4% | 0 | 85 | 0 |
| ambiguous_unresolved_incomplete_followup | 2 | 0.02% | 0 | 1 | 0 |

Two findings validate the correction. First, `disposed_credit_exit` now equals **exactly** the 2,108 loss-field loans, and every loss-field loan is classified `disposed_credit_exit` — a perfect match between the trajectory classifier and the independent accounting-field evidence, which v1 did not achieve (v1 had only 1,628/2,108 matching, leaving 480 loss-field loans misclassified as cured/gapped). Second, the two hand-traced ambiguous loans land exactly in the new `ambiguous_unresolved_incomplete_followup` category as designed, rather than being silently resolved as payoffs. Zero episodes fall into any `_incomplete_followup` variant of cured/still_delinquent/unknown_status — every non-terminal trajectory either reaches the panel-wide latest month (2026-03) or ends in one of the two flagged ambiguous cases; no default episode's data quietly disappears without an explained resolution or gap.

Two empirical checks (bulk SQL over accepted Parquet, recorded in the run result) back the design: zero rows exist anywhere in the 323,174-loan cohort after any terminal zero-balance code (so resolving at the first terminal code cannot miss a "later revision"), and `zero_balance_effective_date` equals `reporting_month` on all 306,637 terminal rows cohort-wide with zero exceptions (so there is no effective-date/reporting-date divergence to reconcile in this dataset — the "effective date versus reporting date" concern is answered, not open).

The corrected disposition share (24.1%, up from v1's uncorrected 18.6%) still means 75.9% of default episodes are excluded from a disposed-only sample — the selection-bias concern is confirmed, not resolved, by the correction. `other_exit_after_default` (7.7%) remains genuinely unresolved as to ultimate loss and stays in every denominator rather than being dropped or assumed.

Evidence: `artifacts/runs/loss_workout_linkage/b2ebdeb7319a4a6486c84b4ad02414f1/workout_linkage_result.json` and `workout_episodes.parquet` (loan_id, anchor_month, category, resolution_month, cure_count, redefault_count, ambiguous_count, had_gap, path_json, has_loss_fields). v1's run directory is untouched. Tests: `tests/test_loss_workout_linkage.py`, 21 synthetic hand-checkable cases built directly from the real hand-traced loan histories above (gap continuation, repeated cure/redefault cycles, ambiguous same-month, disposition priority, empty-input guard).

## Default-anchor exposure result (Milestone 2, 2026-09-22)

For every one of the 8,750 default episodes, `src/mortgage_risk/default_anchor_exposure.py` retains the raw reported balance, masking status, terminal status and exposure-eligibility reason at the **original default anchor month only** (never at resolution or any other month), reusing the accepted `exposure_eligibility.parquet` categories unchanged. It never substitutes original UPB, never treats masked/missing exposure as zero, never reclassifies unresolved masking ages 0/6, and never uses a terminal-month zero UPB as anchor exposure — a terminal-at-anchor row (the anchor month is itself the disposition row) is labeled `terminal_same_month` and kept separate. A separately named `prior_supported_balance` proxy (the most recent eligible reported balance at or before the anchor, with its exact age in months) is reported alongside, never merged into or presented as anchor exposure itself.

| Anchor classification | All 8,750 defaults | Disposed subset (2,108) |
|---|---|---|
| eligible_positive_reported_balance (directly usable) | 8,232 (94.1%) | 1,962 (93.1%) |
| masking_or_age_unresolved | 415 (4.7%) | 98 (4.6%) |
| masked_early_life | 74 (0.8%) | 24 (1.1%) |
| terminal_same_month (anchor is itself the disposition row) | 21 (0.2%) | 21 (1.0%) |
| unmasked_zero_unexplained | 8 (0.1%) | 3 (0.1%) |

94.1% of all default anchors and 93.1% of `disposed_credit_exit` anchors have a directly usable reported balance — no material differential selection bias in exposure availability between disposed and non-disposed episodes. Of the 518 loans without a directly usable anchor balance, only 26 have any earlier eligible balance to fall back on as a proxy (`terminal_same_month` loans typically do, at ~1 month's age; `masking_or_age_unresolved` loans typically do not). **492 of 8,750 default episodes (5.6%) have no supported exposure evidence at or before their anchor at all** — a real, quantified gap for any future severity work, not an estimate to paper over.

Checks passed: joined row count equals the population exactly, zero duplicate/unmatched keys, and zero cases of the proxy's month falling after the anchor (no look-ahead). Five manually traced sample loans (one per classification) are saved in the result for direct inspection, including a `terminal_same_month` loan whose anchor-row balance is a masking $0.00 disposition-month value while its 1-month-prior proxy is $223,571.70 — concretely demonstrating why the terminal balance is never used as anchor exposure.

Evidence: `artifacts/runs/default_anchor_exposure/62355abf161f4a9fbd86b0f6401beb36/default_anchor_exposure_result.json` and `anchor_exposure.parquet`. Tests: `tests/test_default_anchor_exposure.py` (5 synthetic cases covering the prior-balance window function, the terminal-same-month override, and non-substitution of masked/missing balances).

## Realized-loss profile result (Milestone 3, 2026-09-22) — descriptive only, not LGD

Before computing anything, the local glossary text for fields 54-62 was read directly (pdftotext, pages covering fields 52-62; poppler installed locally for this one inspection). Two findings determined the scope below. First, field 59 (Net Sales Proceeds) is defined as "total cash received from the sale of the property **net of any applicable selling expenses, such as fees and commissions**" — a narrow netting scope distinct from the pre-sale foreclosure/holding cost fields (54-58: title/valuation/utility/bankruptcy costs, preservation and repair, asset recovery/eviction, holding expenses and credits, holding-period taxes), so double-counting between those groups is unlikely though not proven impossible. Second, and more materially: **every one of fields 54-62 carries the identical caveat, "this field will be populated after the disclosed disposition date ... based on individual CRT deal claims and reporting timelines."** That ties population and completeness to a credit-risk-transfer reinsurance claims process, not to a confirmed final Single-Family settlement date — a populated value is not thereby proven final or non-revisable. This is new evidence, not previously read from the PDF text directly in this project.

Given that, `src/mortgage_risk/realized_loss_profile.py` computes exactly one **undiscounted nominal accounting identity** — `net_loss = anchor_current_actual_upb + (foreclosure_costs + preservation_repair + asset_recovery_costs + holding_expenses_credits + taxes) - (net_sales_proceeds + credit_enhancement_proceeds + repurchase_makewhole + other_foreclosure_proceeds)` — for the subset of `disposed_credit_exit` episodes where **both** the anchor exposure is directly usable **and** all nine loss fields are populated. No missing field is ever treated as zero; any loan failing either condition is excluded from the denominator, not imputed.

| Denominator step | Loans | Share of all 8,750 defaults |
|---|---|---|
| All disposed_credit_exit episodes | 2,108 | 24.1% |
| ...with directly usable anchor exposure | 1,962 | 22.4% |
| ...with all nine loss fields populated | 2,004 | 22.9% |
| **Analysis population (both conditions)** | **1,880** | **21.5%** |

Net loss distribution (undiscounted nominal USD, n=1,880): min **-$188,460.65**, p25 **$1,081.08**, median **$22,824.20**, mean **$28,111.51**, p75 **$47,135.30**, max **$242,044.22**. 436 loans (23.2%) show a net *gain* (proceeds exceeded principal plus costs) and 61 (3.2%) show loss exceeding exposure — neither is clamped, per the mathematical contract's explicit prohibition. The resulting ratio (net_loss / anchor exposure) has mean 28.3% and median 21.5%, reported only as `realized_loss_ratio_not_lgd` — a labeled description of this complete-case subset, never called LGD or severity, and never applied to the 75.9% of default episodes that never reach disposition or to the 8.2% of disposed episodes excluded from this population for incomplete accounting or unsupported exposure.

**This remains a descriptive profile, not an accepted severity/LGD model.** Blockers to promotion, recorded in the run evidence: (1) no confirmation that a populated field value is the final, non-revisable amount, given the CRT-claims-timeline caveat above; (2) missed interest, servicer advances, principal forgiveness and deferred principal are absent from every field inspected and from this identity; (3) the analysis population is 21.5% of all default episodes, not a representative severity sample; (4) no independent confirmation that fields 54-58 never overlap with field 59's netting beyond its stated "fees and commissions" scope.

Evidence: `artifacts/runs/realized_loss_profile/f63257e5acb54101abb2a4d0cb30e8a4/realized_loss_profile_result.json` and `analysis_population.parquet`. Tests: `tests/test_realized_loss_profile.py` (5 synthetic cases: hand-calculated identity, net-gain non-clamping, loss-exceeds-exposure non-clamping, the legitimate negative-holding-expense case, and field-group disjointness).

This closes the three efficiently executable milestones against the existing 2010Q1 cohort. Actual-cohort lifetime portfolio loss, a validated LGD model, and cross-cohort calibration remain blocked on the items in the mathematical contract above and on the still-unacquired 2012Q1/2013Q1 cohorts respectively.
