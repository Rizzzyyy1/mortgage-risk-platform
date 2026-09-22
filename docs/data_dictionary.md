# Data dictionary (provisional)

## Purpose

This document is intentionally a working placeholder, not a validated vendor schema. It records the kinds of information the project will need to confirm once the official Fannie Mae source files and product documentation are available through Data Dynamics.

The sample and 2010Q1 historical file are now local and selected fields have been checked against the glossary. Entries explicitly labeled provisional remain unvalidated; the current Phase 2E mapping and derived fields are documented below.

## Status legend

- Verified in official public documentation: the existence of the product, Data Dynamics as the access platform, registration and terms requirements, quarterly acquisition/performance organization, sample file, FAQ, tutorial, and glossary/file-layout references.
- Supported only by general mortgage-domain conventions: conceptual categories that may resemble mortgage data but are not yet vendor-verified.
- Awaiting source verification: the exact field names, file layouts, code tables, and delivery package details for the downloaded dataset.

## Verified public-source facts

The following items are directly supported by the official product documentation and the Data Dynamics access page:

| Topic | Verified fact | Source |
|---|---|---|
| Product name | Fannie Mae Single-Family Loan Performance Data | https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data |
| Access platform | Data Dynamics is the official access platform | https://capitalmarkets.fanniemae.com/tools-applications/data-dynamics |
| Registration requirement | Users must register and create a username and password | official product page |
| Terms requirement | Users must accept the applicable terms and conditions | official product page |
| Data organization | Acquisition and performance data are organized by acquisition quarter with monthly performance history | official product page |
| Primary dataset | Static origination data plus dynamic performance history through the previous quarter | official product page |
| HARP dataset | HARP dataset is included and includes mapping support | official product page |
| Supporting docs | FAQ, sample file, tutorial, glossary and file layout, and R code are available | official product page |

## Verified local sample observations

These facts are supported by the local sample file itself and are not inferred from a guessed schema.

| Observation | Verified fact | Evidence status |
|---|---|---|
| File origin | The sample file is the official sample distributed by Fannie Mae for the Single-Family Loan Performance product | Verified by product page and file location |
| File format | The file uses pipe-delimited rows and a fixed 108-column layout | Verified by file inspection |
| Header row | There is no data header row in the sample file | Verified by first-row content |
| Sample grain | Each row is a monthly loan-period record for a single loan | Verified by repeated loan identifier with month changes |
| Loan identifier | Field 2 in the official glossary is Loan Identifier | Verified by official glossary |
| Reporting period | Field 3 in the official glossary is Monthly Reporting Period and uses MMYYYY | Verified by official glossary |
| Distinct loans | 8 distinct loan IDs appear in the sample | Verified by row counts |
| Distinct months | 132 distinct monthly periods appear and parse as dates without fallback guessing | Verified by parsed monthly dates |
| Duplicate keys | No duplicate loan-month keys were detected | Verified by row-level key analysis |

## Official field mapping validated against the glossary

The following field positions were checked against the downloaded vendor glossary and therefore have greater evidentiary weight than the earlier provisional assumptions.

| Field position | Official name | Meaning | Verification status |
|---|---|---|---|
| 2 | Loan Identifier | Unique mortgage loan identifier | Verified against official glossary |
| 3 | Monthly Reporting Period | Month and year of servicer cut-off period; MMYYYY | Verified against official glossary |
| 8 | Original Interest Rate | Original note rate | Verified against official glossary |
| 9 | Current Interest Rate | Current effective interest rate | Verified against official glossary |
| 10 | Original UPB | Original unpaid principal balance | Verified against official glossary |
| 12 | Current Actual UPB | Current actual unpaid principal balance | Verified against official glossary |
| 40 | Current Loan Delinquency Status | Delinquency bucket or status in months | Verified against official glossary |
| 41 | Loan Payment History | Recent 24-month payment history code string | Verified against official glossary |
| 42 | Modification Flag | Whether the loan has been modified | Verified against official glossary |
| 44 | Zero Balance Code | Reason for balance reaching zero | Verified against official glossary |

## Candidate schema categories only

The following categories are examples of the information the project will need to confirm after download; they are not verified field names or official data definitions.

| Category | Example concept | Verification status |
|---|---|---|
| loan identity | unique mortgage identifier, acquisition identifier, HARP mapping key | Awaiting source verification |
| origination data | origination date, original term, original balance, note rate | Supported only by general mortgage-domain conventions |
| property / collateral | property type, occupancy, loan purpose, insurance status | Supported only by general mortgage-domain conventions |
| time dimension | acquisition quarter, reporting month, loan age | Supported only by general mortgage-domain conventions |
| balance and exposure | current UPB, scheduled principal, scheduled interest, remaining term | Supported only by general mortgage-domain conventions |
| delinquency and defaults | delinquency bucket, default status, modification or workout status | Awaiting source verification |
| prepayment and exits | payoff status, prepayment event, liquidation status, REO state | Awaiting source verification |
| loss and recovery | charge-off, recovery, loss amount, servicing outcomes | Awaiting source verification |
| derived project metrics | event month, survival month, exposure at risk, scenario loss | Project-defined placeholders only |

## Candidate field names to be verified later

These are not official dataset fields; they are placeholders used only for planning and must be replaced after vendor validation.

| Placeholder field | Meaning | Status |
|---|---|---|
| loan_id | loan-level identifier used to track the same mortgage across time | Candidate only |
| acquisition_quarter | quarter in which the loan was acquired | Candidate only |
| reporting_month | monthly observation date in the performance history | Candidate only |
| delinquency_status | reported delinquency or default status | Candidate only |
| prepayment_flag | event indicating repayment outside scheduled amortization | Candidate only |
| default_flag | event indicating default or severe delinquency | Candidate only |
| modification_flag | active modification or workout indicator | Candidate only |
| liquidation_status | final exit status such as payoff or REO | Candidate only |
| charge_off_amount | realized loss or charge-off amount | Candidate only |
| recovery_amount | recovered amount after a loss event | Candidate only |

## Project-defined derived fields

These fields are expected to be created in the project’s transformation layer, not sourced directly from the vendor schema.

| Derived field | Purpose | Status |
|---|---|---|
| historical cohort flag | marks a model-development cohort | Project-defined placeholder |
| event month | date of default or other event | Project-defined placeholder |
| exposure at risk | balance at risk in a month | Project-defined placeholder |
| survival month | time to event or censoring | Project-defined placeholder |
| 12-month default probability | benchmark probability measure | Project-defined placeholder |
| scenario loss | scenario-adjusted portfolio loss | Project-defined placeholder |

## Validation requirement before any modeling

Before any modeling or transformation logic is treated as real, the project must verify against the downloaded official files and documentation:
- the exact field names,
- the exact file names and archive structure,
- the data contract for each acquisition-quarter package or combined file,
- the data types and null handling,
- the meaning of delinquency and default codes,
- the monthly reporting conventions,
- the join keys across acquisition and performance files,
- any vendor restrictions on redistribution or reuse.

## Current availability and remaining gaps — 2026-09-22

The 2010Q1 and 2011Q1 files and official glossary are local. Earlier placeholder descriptions are historical planning material; they do not override verified mappings below or in risk_factor_expansion.md. Core ingestion and selected predictor fields have been checked. Loss fields 52–62 have a verified glossary mapping, a corrected default-to-workout linkage, quantified default-anchor exposure, and a descriptive (not LGD) realized-loss profile — see "Loss/workout/exposure field mapping" below and redevelopment_plan.md for the full evidence chain and remaining blockers. Additional calibration/final cohorts 2012Q1 and 2013Q1 are not local.

## Phase 2E supplemental and derived fields

One-based source fields: 2 loan identifier; 3 reporting month; 14 note/origination date; 15 first-payment date; 16 signed loan age; 45 zero-balance effective date. Source dates are MMYYYY, parsed only with six digits and valid calendar values. All supplemental raw strings are retained, with loan/month/source-record-number keys matched exactly to accepted ingestion. Source record number is a one-based row ordinal, not a vendor field.

| Derived field | Meaning |
|---|---|
| masking_status | masked, unmasked, unresolved under documented project policy |
| terminal_record_status | terminal, not_observed_terminal, unresolved using observed codes/effective dates |
| exposure_eligibility_reason | mutually exclusive reason; terminal exclusions precede masking and balance exclusions |
| exposure_eligible | true only for supported positive reported exposure |
| usable_reported_exposure | original reported DECIMAL balance if eligible, otherwise NULL |
| reported_modification_status | Y/N or unknown_not_reported; raw flag retained separately |
| previously_observed_modification_status | most recent prior Y/N, strictly preceding observation; NULL when none |
| last_observed_terminal_month | most recent valid terminal-code month available at or before observation |

See target_definitions.md for the conservative masking boundary, date plausibility rules, and economic limitations. Negative loan ages are preserved and unresolved for eligibility. Loan counts across eligibility categories overlap across months and must not be added as distinct cohort totals.

## Phase 2F — 2026-09-20

Phase 2F outputs: monthly.parquet (month counts and balances); categories.parquet (month/dimension/category totals for eligibility, delinquency, modification, exit code); event_rows.parquet (all observed rows with as-of candidate_event and candidate_time); loan_outcomes.parquet (one row per loan, entry, first stop, follow-up and outcome_12m); monthly_first_stops.parquet (first-stop counts with entry-prevalent counts). Gap candidate_time is the previous observed month; other candidates use the reporting month. Outcome labels use future follow-up intentionally and must not be prediction features. See target_definitions.md for the event contract.

## Phase 3 — 2026-09-20

Phase 3 episodes.parquet contains eligible loan episodes and inclusive observed duration (unknown intervals excluded). historical_curve.parquet records elapsed month, risk count, event/censor counts, two hazards, survival and cumulative incidences. baseline_schedule.parquet and adverse_schedule.parquet contain the hypothetical conditional balances, marginal event probabilities, assumed recovery and expected loss. Monetary schedule values are serialized decimal strings to preserve precision; historical curve probabilities are doubles. Detailed semantics: methodology.md.

## Phase 4A — 2026-09-20

Phase 4A exports train/validation/test_features.parquet with loan_id, reporting_month and the five allowlisted predictors; corresponding *_labels.parquet holds keys, horizon_month and outcome_12m. Missing numeric predictors remain NULL. See methodology.md for as-of semantics and selection rules.

## Phase 4B — 2026-09-20

Phase 4B selected_model.json contains classes, training prior, group probabilities, alpha and known training count. selection.json freezes validation-only selection. test_predictions.parquet retains loan key/month/group, raw retrospective outcome and three probabilities. model_result.json stores validation/test metrics, exact-score calibration, segments, censor bounds and group distributions. This is a conditional 12-month model, not monthly hazard or severity.

## Phase 5 — 2026-09-20

Phase 5 stress_result.json holds baseline/adverse metrics, 16 coalition values, monthly driver paths and Shapley contributions for undiscounted and PV losses. sensitivity.parquet contains one-at-a-time driver/value outputs. baseline_schedule.parquet and adverse_schedule.parquet contain hypothetical conditional exposure and marginal event/loss data. PV recovery-tail amount includes recoveries beyond contractual maturity.

## Phase 6 — 2026-09-21

Phase 6 validation_result.json records fingerprinted input reports, separate engineering/statistical/economic verdicts, independent metric/monetary/attribution residuals, population and segment flags. monitoring_replay.json contains three historical snapshot checks; training calibration is intentionally not evaluated. No live monitoring data is created.

## Loss/workout/exposure field mapping — 2026-09-22

This is the canonical mapping for the loss, workout and default-anchor-exposure fields; other documents (redevelopment_plan.md, project_status.md) refer back to it rather than repeating field definitions.

### Glossary fields 52–62 (Single-Family applicable; local glossary pp. 5–6, dated 2026-09-10)

| Position | Field | Glossary definition (verbatim key phrase) |
|---|---|---|
| 52 | Foreclosure Date | Foreclosure-related date field |
| 53 | Disposition Date | "The date on which Fannie Mae's interest in a property ends through either the transfer of the property to a third party or the satisfaction of the mortgage obligation" |
| 54 | Foreclosure Costs | Title/valuation/utility-maintenance costs and bankruptcy/foreclosure legal costs |
| 55 | Property Preservation and Repair Costs | Maintenance and repair costs securing/preserving the property |
| 56 | Asset Recovery Costs | Relocation assistance, deed-in-lieu fee, eviction costs |
| 57 | Miscellaneous Holding Expenses and Credits | HOA dues, insurance premiums/refunds, rental income, title insurance — **combines expenses and credits, so a negative value is a legitimate net credit, not an error** |
| 58 | Associated Taxes for Holding Property | Property tax payments during the holding period |
| 59 | Net Sales Proceeds | "Total cash received from the sale of the property **net of any applicable selling expenses, such as fees and commissions**, ... as currently reported on the HUD-1 or other settlement statement" |
| 60 | Credit Enhancement Proceeds | MI claims, recourse/indemnification payments |
| 61 | Repurchase Make Whole Proceeds | Amounts received under representation/warranty repurchase arrangements |
| 62 | Other Foreclosure Proceeds | Non-sale proceeds, e.g. redemption proceeds from the mortgagor |

**Every one of fields 54–62 carries the identical glossary caveat: "This field will be populated after the disclosed disposition date of the mortgage loan or the subject property, as applicable, based on individual CRT deal claims and reporting timelines."** A populated value is therefore not proven final or non-revisable; see realized_loss_profile.py's blockers. Fields 63–64 (modification non-interest-bearing UPB, principal forgiveness) and 75–76 (CRT-only modification-loss amounts) are separate fields not used by any current output; 75–76 must not be assumed applicable to Single-Family data.

### loss_feasibility output — `artifacts/runs/loss_feasibility/30a0a02381af4b93807301fc6ef08d90/loss_fields.parquet`

One row per loan with any of fields 52–62 populated (2,108 loans; verified exactly one row per loan, so no repeated/cumulative-disclosure risk). Columns: `loan_id`, `reporting_month_raw` (MMYYYY string), `exit_code`, and the nine raw-string monetary/date fields named after their glossary meaning (`foreclosure_date`, `disposition_date`, `foreclosure_costs`, `preservation_repair`, `asset_recovery_costs`, `holding_expenses_credits`, `taxes`, `net_sales_proceeds`, `credit_enhancement_proceeds`, `repurchase_makewhole`, `other_foreclosure_proceeds`). Values are raw strings; downstream consumers `try_cast` to `DECIMAL(18,2)`/date themselves rather than trusting a pre-typed column.

### loss_workout_linkage v2 output — `artifacts/runs/loss_workout_linkage/b2ebdeb7319a4a6486c84b4ad02414f1/workout_episodes.parquet`

One row per Phase 2F default-proxy episode (8,750 loans). Columns: `loan_id`, `anchor_month` (the original, never-moved Phase 2F first_stop month), `category` (final resolution: `disposed_credit_exit`, `payoff_or_maturity_after_default`, `other_exit_after_default`, `cured_no_redefault_{at_data_end|incomplete_followup}`, `still_delinquent_{at_data_end|incomplete_followup}`, `ambiguous_unresolved_{at_data_end|incomplete_followup}`, `unknown_status_{at_data_end|incomplete_followup}`, or `unsupported_code_after_default`), `resolution_month` (non-NULL only for a terminal code), `cure_count`, `redefault_count`, `ambiguous_count`, `had_gap` (continuity-break flag, never a stopping condition), `path_json` (ordered transition list: kind + month), `has_loss_fields` (loan_id present in loss_fields.parquet). v1 (`artifacts/runs/loss_workout_linkage/24126815af8448fe9b02b34f23ca7aa9/`) used a simpler, since-corrected schema without path tracking; it is preserved for provenance only and superseded by v2.

### default_anchor_exposure output — `artifacts/runs/default_anchor_exposure/62355abf161f4a9fbd86b0f6401beb36/anchor_exposure.parquet`

One row per default episode (8,750 loans), exposure evaluated **only at the original anchor month**. Columns: `loan_id`, `anchor_month`, `workout_category`, `resolution_month`, `has_loss_fields`, `anchor_current_actual_upb` (raw reported balance, unsubstituted), `anchor_masking_status`/`anchor_terminal_record_status`/`anchor_exposure_eligibility_reason` (reused unchanged from exposure_eligibility.parquet), `anchor_exposure_classification` (the reused reason, except `terminal_same_month` when the anchor row is itself the disposition row), `prior_supported_balance`/`prior_supported_balance_month`/`prior_supported_balance_age_months` (a separately named, explicitly aged proxy — the most recent eligible balance at or before the anchor — never substituted for anchor exposure itself).

### realized_loss_profile output — `artifacts/runs/realized_loss_profile/f63257e5acb54101abb2a4d0cb30e8a4/analysis_population.parquet`

One row per loan in the complete-case, exposure-supported `disposed_credit_exit` subset (1,880 loans). Columns: `loan_id`, `anchor_month`, `resolution_month`, `anchor_current_actual_upb`, `anchor_exposure_classification`, the nine typed loss fields, `net_loss` (the accounting identity, undiscounted, unclamped). **This is a descriptive profile, not an LGD or severity model** — see redevelopment_plan.md's Milestone 3 section for the full blocker list before any promotion.

### Official vendor loss-methodology fields (verified 2026-09-22, not previously extracted)

Read directly from the local combined CRT/SF glossary's own CAS/CIRT/Single-Family(SF) checkmark columns — applicability is verified per field, not inferred from any shared boilerplate note. Cross-referenced against Fannie Mae's own Loan Performance Data Tutorial (Feb 2021) and SF Loan Performance FAQ (2017).

| Position | Field | SF-applicable? | Notes |
|---|---|---|---|
| 9 | Current Interest Rate | Yes | Used for the project's own foregone-interest approximation; empirically blank on ~89% of terminal (removal) rows specifically, though populated on ~88% of rows overall — a real reporting pattern, not a conversion failure. |
| 46 | UPB at the Time of Removal | Yes | The vendor's own credit-event exposure concept, distinct from this project's default-anchor UPB. Populated "as a loan hits a Zero Balance Code, or is otherwise liquidated" — matched 100% (1,880/1,880) of the realized-loss-profile population when joined to the exact resolution month. |
| 51 | Last Paid Installment Date | Yes | Populated for zero-balance codes 02/03/09/15 specifically, "to allow users to calculate accrued interest" (FAQ Q51). Matched 1,879/1,880 of the population. |
| 63 | Modification-Related Non-Interest Bearing UPB | Yes | No population-date restriction. Nonzero at least once for 25/1,880 of the population (aggregated across each loan's full history, not just its terminal row). |
| 64 | Principal Forgiveness Amount | Yes | No population-date restriction. Nonzero for 0/1,880 of the population, though the field is nonblank for 2,969 loans across the full 2010Q1 cohort. |
| 80 | Foreclosure Principal Write-off Amount | Yes | Nonzero at the terminal row for 0/1,880 of the population. |
| 106/107 | Alternative Delinquency Resolution / Count | Yes, but only **populated starting with the July 2020 activity period** | A real, checkable population-timing limit for a cohort whose defaults mostly precede July 2020 — not evidence that the underlying data is absent from the dataset. |
| 108 | Total Deferral Amount | Yes, same July 2020 restriction | Nonzero at least once for 9/1,880 of the population. |
| 77/78 | Current/Cumulative Credit Event Net Gain or Loss | **No — CRT-only** | The vendor's own pre-computed net-loss convenience fields are unavailable for SF; a comparable figure must be built from components, which `realized_loss_profile.py` already does. |
| 85 | Delinquent Accrued Interest | **No — CRT-only** | Confirmed unavailable for SF; the project computes its own labeled approximation instead (`estimated_foregone_interest`), using fields 9/46/51, which are SF-applicable. |
| 110 | Interest Bearing UPB | **No — CRT-only** | Its formula note ("*if Current Actual UPB has been reduced to zero due to a loss, the UPB at the Time of Removal is used") independently corroborates using field 46 as the exposure-at-credit-event concept. |

### vendor_method_reconciliation output — `artifacts/runs/vendor_method_reconciliation/b758ff00b5aa468da1b81d13e64626f8/comparison.parquet`

One row per loan in the realized-loss-profile population (1,880 loans; joins are month-matched to each loan's own `resolution_month`, never loan-only-matched, to avoid fan-out against fields that repeat across many months). Adds `upb_at_removal`, `last_paid_installment_date`, `foreclosure_principal_writeoff`, `current_interest_rate` (terminal-row values), `max_modification_nib_upb`/`ever_modification_nib_upb_nonzero`, `max_principal_forgiveness_amount`/`ever_principal_forgiveness_nonzero`, `max_total_deferral_amount`/`ever_total_deferral_amount_nonzero` (aggregated across each loan's full history), `estimated_foregone_interest` (this project's own labeled approximation), and three named net-loss variants: `project_net_loss_conservative`, `faq_zero_filled_net_loss`, `vendor_anchored_net_loss`. See redevelopment_plan.md for the full methodology-comparison table and result interpretation.

### Official R code, retrieved and traced (2026-09-22)

Fannie Mae's `LPPUB_StatFile_Production.R` (retrieved via Wayback Machine snapshot of the current product page's "Code (Primary)" link; see redevelopment_plan.md for full provenance/checksums) defines the vendor's own credit-event trigger and Net Loss/Net Severity formula in R. Field-name mapping confirmed directly from the script's own column header list and rename statements:

| R variable | Source glossary field | Position |
|---|---|---|
| `FCC_COST` | Foreclosure Costs | 54 |
| `PP_COST` | Property Preservation and Repair Costs | 55 |
| `AR_COST` | Asset Recovery Costs | 56 |
| `IE_COST` | Miscellaneous Holding Expenses and Credits | 57 |
| `TAX_COST` | Associated Taxes for Holding Property | 58 |
| `NS_PROCS` | Net Sales Proceeds | 59 |
| `CE_PROCS` | Credit Enhancement Proceeds | 60 |
| `RMW_PROCS` | Repurchase Make Whole Proceeds | 61 |
| `O_PROCS` | Other Foreclosure Proceeds | 62 |
| `non_int_upb` | Modification-Related Non-Interest Bearing UPB | 63 |
| `PFG_COST`/`prin_forg_upb` | Principal Forgiveness Amount | 64 |
| `zb_upb` (source column `LAST_UPB`) | UPB at the Time of Removal | 46 |
| `LPI_DTE` | Last Paid Installment Date | 51 |
| `LAST_RT` | Current Interest Rate (most recent prior populated value, carried forward — not the terminal-row value) | 9 |

**Credit-event trigger:** `zero_balance_code IN ('02','03','09','15') OR (delinquency_status >= 6 AND < 999)` — a 180-day threshold, distinct from this project's 90-day default-proxy anchor. **`FCE_UPB = zb_upb + act_upb`** at that trigger row with no null-coalescing (frequently undefined when the trigger is the delinquency threshold, since `zb_upb` is not yet populated before a disposition) — a different quantity from `LAST_UPB` (see below), which is what Net Loss actually uses.

**`LAST_UPB`** (exposure basis for Net Loss): at the loan's terminal row, `COALESCE(zb_upb, act_upb)`.

**`INT_COST`** (foregone/delinquent interest): `months(LPI_DTE, LastDate) × ((LAST_RT/100 − 0.0035)/12) × (LAST_UPB − non_int_upb)`. The 0.35-percentage-point deduction is a guaranty/servicing-fee carve-out.

**`NET_LOSS = LAST_UPB + FCC_COST + PP_COST + AR_COST + IE_COST + TAX_COST + PFG_COST + INT_COST − NS_PROCS − CE_PROCS − RMW_PROCS − O_PROCS`**, computed only when `COMPLT_FLG==1` (Disposition Date populated and the loan's terminal status is one of the four disposition codes — an exact match to this project's `disposed_credit_exit` population). Every cost/proceeds/forgiveness/interest term, but never `LAST_UPB` itself, defaults to zero when missing. **`NET_SEV = NET_LOSS / LAST_UPB`.**

### PD redevelopment outputs (2012Q1/2013Q1 acquired, 2026-09-22)

`multi_cohort_adapter.py` generalizes `external_cohort.py` (unchanged, immutable) to an arbitrary source/snapshot/outcome-end date. Each cohort build produces `features.parquet` (loan_id, reporting_month, delinquency_months, modification_status, borrower_fico/ltv/dti/original_term/occupancy/purpose with `_raw`/`_quality` companions — same schema as the original 2011Q1 `external_cohort` output) and, only when explicitly requested, `labels.parquet` (loan_id, reporting_month, outcome_12m). The two are separable calls so a cohort's labels can be withheld past its features being built — how 2013Q1's outcome-blindness was enforced structurally.

- `artifacts/runs/redevelopment_model/49235a3eec044f748f4fe4beb4f93c12/`: development-only model selection. `logistic_1.0.json`/`benchmark_10.json` etc. (same export schema as `challenger.py`'s outputs); `redevelopment_model_result.json` holds coverage, seasoning/missingness comparison between 2010Q1 and 2011Q1, and selection metrics.
- `artifacts/runs/redevelopment_calibration/66899de49fc84a8da3166d59214c2aa4/`: `frozen_evaluation_model.json` (the candidate actually used for the final evaluation — either the unchanged development-selected model or, here, the intercept-adjusted one) and `redevelopment_calibration_result.json` (coverage, offsets, segment-level before/after O/E).
- `artifacts/runs/redevelopment_final_evaluation/21a27da4febc4ebdbeba08698e5b18f1/`: `final_evaluation_result.json` (same schema as the original `external_evaluate.py` output: quantitative_gates, metrics, calibration_diagnostics, paired_difference_intervals95, segments, drift) and `predictions.parquet`.
- `artifacts/runs/loan_id_registry/2011Q1_loan_ids.parquet`: distinct loan_id list for the full 2011Q1 cohort (505,196 rows), built once for all-cohort disjointness checks since only the snapshot-eligible subset existed before.
- `artifacts/runs/segment_acceptance_review/d1971a46201f4a9a9db4f31a16c0bd24/segment_acceptance_review_result.json` (2026-09-22, `segment_acceptance_review.py`; supersedes the earlier `9b9453a2d995423393cdebb418b8cb42` run, preserved unchanged, which lacked the two classification fields added below): read-only quantification of the 2013Q1 segment finding — rejoins the saved `predictions.parquet` from the final-evaluation run above with the frozen cohort's `features.parquet` (hash-verified against the record in `final_evaluation_result.json`) purely to recover segment labels, cross-checks every point estimate against the frozen record, then reports a 95% paired bootstrap interval per segment. No refit, no recalibration, no new scoring, no new acceptance threshold. Fields per segment: `field`, `value`, `n`, `observed`, `expected`, `observed_expected`, `oe_ci95`, `within_frozen_aggregate_band_0.8_1.25`, `oe_direction` (`overprediction`/`underprediction`/`exact`, from `observed_expected` relative to 1 — added so risk-direction wording is generated from a checked value, after a prior milestone's hand-written narrative reversed it in one place), `ci_vs_band_0.8_1.25` (`entirely_below`/`entirely_above`/`entirely_within`/`overlaps_floor`/`overlaps_ceiling`/`spans_band` — added after a prior milestone's narrative overstated how many segments' intervals lay entirely outside the band), `insufficient_support`.

See `docs/redevelopment_plan.md` and `docs/final_report.md` for the full narrative, the four separate verdicts, the acceptance matrix, and why the segment-level miscalibration is not resolved despite the aggregate gate passing.

### vendor_official_loss_calculation output — `artifacts/runs/vendor_official_loss_calculation/4fe2070b858446aeaf9d96d923f4d750/official.parquet`

One row per `disposed_credit_exit` loan (2,108 loans — the full population, not complete-case). Columns: `loan_id`, `anchor_month`, `resolution_month`, `last_upb`, `upb_at_removal`, `current_actual_upb_at_resolution`, `last_paid_installment_date`, `last_rt` (carry-forward rate), `non_int_upb`, `pfg_cost`, the nine cost/proceeds fields, `int_cost`, `official_net_loss`, `official_net_severity`. A companion `rate_history.parquet` holds `current_interest_rate` for every month of every disposed loan (one narrow, bounded CSV scan, reused for the carry-forward window function — not a full re-ingestion). This is the vendor's own official formula, byte-traced from their R code; it is still a retrospective descriptive statistic, not a predictive LGD model — see redevelopment_plan.md for the corrected four-row blocker inventory.
