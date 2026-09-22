# Target Definitions and Portfolio Design

## 1. Objective

This document defines the measurable targets and the analytical design for the mortgage-risk platform. The aim is to keep the measurement logic explicit and coherent before building transformations or predictive models.

## 2. Populations

### Historical development cohort

The historical cohort is the set of loans used to develop, calibrate, and evaluate risk metrics. It should:

- represent a defined acquisition period or other bounded historical segment,
- include the full available monthly performance history for each loan,
- retain loans that experience default, prepayment, modification, or other exits,
- and preserve the monthly panel needed for chronological evaluation.

### Reporting portfolio

The reporting portfolio is a separate snapshot of loans eligible as of a chosen reporting date. It is used for:

- current portfolio measurement,
- exposure totals,
- scenario-based reporting,
- current-risk summaries.

The reporting portfolio is not the same as the historical development cohort and should not be substituted for it.

## 3. Loan-month observation

Each observation represents one loan in one month. The record must include:

- loan identifier,
- reporting month,
- origination and portfolio attributes,
- current unpaid principal balance,
- delinquency state,
- performance status or exit status,
- any modification or workout flags,
- exposure at risk for the month.

This grain is the base unit for default risk, prepayment logic, and loss estimation.

## 4. Outcome definitions

### Default event

A default event is a loan-level outcome indicating that the mortgage has failed to perform according to the project’s chosen default definition.

The operational Phase 2F default proxy is first observed delinquency of three or more months or exit code 02/03/09/15, subject to the ambiguity and censoring rules below. This is a project definition supported by vendor fields, not a vendor-defined universal default standard.

Important guardrail:

- default is not simply a delinquency bucket label without event timing,
- the chosen default rule must be consistent with the monthly reporting period,
- and the default definition must be aligned with the loss-severity assumptions.

### Prepayment event

A prepayment event occurs when the loan exits due to scheduled or unscheduled payoff before the mortgage’s maturity, excluding ordinary amortization. This is a competing event relative to default in the historical cohort.

### Censoring

A loan-month is censored when the observation ends without a default event, or when the loan exits the cohort for reasons outside the defined event set. Censoring must be tracked because it affects event probability and survival interpretation.

### Modification / workout states

Modification or workout states are not treated as ordinary performance continuation. They may alter the default risk and balance path, but they should be encoded explicitly so they do not silently distort the default or prepayment timeline.

## 5. Time windows

### 12-month default measure

The 12-month default probability is defined as the probability that a loan defaults within the next 12 months from a prediction date, conditional on the information available at that prediction time.

This measure:

- uses loan information known at the prediction date,
- excludes future information,
- should be estimated using a coherent monthly panel and look-forward window,
- and must not be conflated with the lifetime expected loss estimate.

### Remaining-life expected loss

Remaining-life expected loss estimates the expected loss over the remaining life of the loan or cohort, conditional on the chosen default and severity assumptions.

This measure includes:

- default probability over future months,
- exposure at risk across the remaining life,
- severity assumptions conditional on default,
- timing of expected cashflows and recoveries.

### Scenario loss

Scenario loss is the expected loss under a specified macro scenario or stress path. It should reflect the project’s chosen adverse environment, not a general default baseline.

Scenario loss is distinct from both:

- the 12-month default probability, and
- the remaining-life expected loss under the baseline assumptions.

## 6. Exposure, severity, and loss perspective

### Exposure at risk

Exposure at risk is the balance exposed to loss during a period, generally measured with the current unpaid principal balance or the relevant projected balance adjusted for scheduled amortization and current state.

### Severity

Loss severity is the percentage of exposure lost conditional on default. It depends on the chosen default definition, loss timing, recovery assumptions, and any workout or modification outcomes.

### Loss perspective

The project will maintain a clear loss perspective:

- default risk is a probability measure,
- loss severity is the conditional loss given default,
- expected loss is the product of probability, exposure, and severity,
- scenario loss modifies the baseline path through assumptions about macro or housing conditions.

## 7. Event ordering and competing risks

The monthly framework will respect the following logic:

1. determine the loan’s state at the start of the month,
2. update performance and delinquency information within the month,
3. identify whether a default event or prepayment event occurs first,
4. assign a single event outcome where the event logic requires one mutually exclusive status,
5. carry forward the loan status to the next month under the selected censoring and exit logic.

This matters because default and prepayment are competing events. A loan that prepays cannot be treated as a defaulted loan in the same period without a clear event-ordering rule.

## 8. Data-quality and analysis guardrails

The project will avoid:

- using a single current month of data as a substitute for the historical cohort,
- selecting only surviving loans when building the historical event dataset,
- treating field names as official without source validation,
- mixing portfolio-snapshot reporting with cohort-development metrics,
- or double-counting prepayment and default in a single loss estimate.

## 9. Baseline benchmark design

The initial benchmark will be deliberately transparent:

- use one modest, documented cohort,
- apply a simple, clearly explained default logic,
- produce monthly survival or event metrics,
- estimate 12-month default and remaining-life loss under a baseline severity assumption,
- then compare to one adverse scenario with visible stress assumptions.

This design supports hand-checking and reproducibility before any complexity is added.

## Phase 2E — Reported-exposure eligibility (2026-09-20)

Source: `data/raw/fannie_mae_loan_performance/crt-file-layout-and-glossary.pdf`, dated 2026-09-10, page 1 fields 3/12/14/15/16 and page 4 fields 42/44/45. Current Actual UPB is masked for the first six months of loan life. The document does not explicitly settle the numeric endpoints of that interval. Loan Age uses the first full interest-accrual month, whereas Origination Date is the note date; they are not assumed identical.

Project policy, not a vendor-certified boundary or regulatory standard:

- Ages 1–5 are classified masked as the overlap of the candidate 0–5 and 1–6 conventions. Ages 0 and 6 remain unresolved pending vendor clarification or a definitive boundary example. Ages 7+ can be unmasked under the plausibility checks below. A zero balance alone never establishes masking.
- Missing age/origination/first-payment dates, negative ages, origin after reporting month, first payment before origin, or an absolute difference greater than one month between note-date month difference and reported age remain unresolved. The one-month tolerance is a deliberately conservative project screening choice, not a vendor equation; exceptions are not automatically source errors. Loan age is never calculated from the first observation.
- A valid termination code observed at or before the reporting month establishes terminal status for that observation and subsequent observations. Unsupported codes, malformed/future effective dates, or an effective date without supporting observed termination remain unresolved. Terminal status denotes dataset exit, not necessarily default or prepayment.
- Only positive, present reported balances on unmasked, nonterminal observations qualify as usable reported exposure. Unmasked zeros are retained and excluded as unexplained; they are not imputed. Terminal, masked, missing, negative, and unresolved observations remain in the population. The usable value is NULL for exclusions, never a fabricated zero or original balance.
- Eligibility reasons are mutually exclusive with terminal status evaluated before masking and balance availability. Masking status is retained separately, so a terminal record may also have unresolved age. Reported balances and source strings remain unchanged.
- Blank modification flags remain unknown/not-reported, never N. `previously_observed_modification_status` is the last Y/N strictly before the observation, with no look-ahead. It is a derived historical observation, not a replacement vendor flag. Monthly as-of windows prevent future-row leakage; this does not assert that a revised vendor release was historically available in real time.

Descriptive analysis may use the eligible subset with exclusion counts displayed. It must not present its total as full-cohort economic exposure. Do not filter the historical population to exposure-eligible rows when subsequently constructing events or censoring; that could bias risk estimates. Event thresholds and outcome horizons still need an explicit benchmark contract before model work.

## Phase 2F — Descriptive event contract v1 (2026-09-20)

This section makes the earlier conceptual event definitions operational for the first observed cohort episode. Source: local `crt-file-layout-and-glossary.pdf`, page 4, fields 40–45, dated 2026-09-10. The glossary supplies code meanings; the threshold, event grouping, and censoring below are project analytical choices, not vendor or regulatory default standards.

| Rule | Operational definition |
|---|---|
| Default proxy | First observed numeric delinquency 03–99 (three or more months delinquent), or credit-related exit 02 (third-party sale), 03 (short sale), 09 (deed-in-lieu/REO disposition), or 15 (nonperforming note sale) |
| Payoff or maturity | Code 01. The glossary combines prepaid and matured; true early prepayment is unresolved without verified maturity information. Do not label every 01 as prepayment. |
| Other exit | Codes 06 repurchase, 16 reperforming note sale, 96 non-credit removal; censor rather than presume default or prepayment |
| Same-month ambiguity | Delinquency 03–99 plus exit 01/06/16/96: stop as ambiguous; no guessed within-month ordering. Credit-related exits remain default proxies even when delinquency is XX. |
| Unknown or unsupported | Unknown/blank/non-numeric delinquency without a resolving valid exit, or unsupported nonblank exit code: unresolved stop; never a known non-event |
| Reporting gap | If adjacent observed months differ by more than one month, censor at the last prior observed month before considering the later record's event. No re-entry or assumed event-free gap. |
| First stop | Earliest observed event, unknown state, ambiguous tie, other exit or gap ends the analytical episode. Later raw records remain available for descriptive profiles, but cannot produce a second first event. |
| Entry | First observed month, not origination. Only observed delinquency 00–02 with no stop at entry enters the retrospective 12-month risk set. Default/exit/unknown at entry is reported separately as ineligible/prevalent. Prior unobserved history remains unknown. |
| Horizon | Twelve calendar months after entry: outcome window is (entry, entry + 12 months], including the endpoint. Labels are loan-level retrospective outcomes, not predictors or fitted probabilities. |
| Follow-up | A known first default/payoff inside the window resolves that outcome. Other exits, ambiguity, or unknown states through the endpoint remain censored/unresolved. A gap after a fully observed endpoint does not invalidate the preceding 12 months. Otherwise 13 consecutive observed monthly records including entry are needed for an event-free label. Short records without a resolving event are incomplete, not zero-default labels. |

The risk population uses all observed loans independently of exposure eligibility. Balance zeros, changes, or disappearance alone never establish an event. Cohort membership is historical and survival-biased filtering is prohibited. Raw delinquency-state counts include repeated observations and are prevalence counts, not first-event incidence. Monthly first-stop counts distinguish entry-prevalent cases. No event rate is calculated here: censoring-aware risk sets and the competing-risk estimator are a Phase 3 requirement.

As-of candidate classification uses only current and preceding rows. Future follow-up is used only in explicitly retrospective outcome tables; those outcomes and first-stop dates must not become prediction features. A revised vendor release is not evidence of historically available data vintages.

True prepayment separation, full economic exposure, boundary masking semantics, and terminal modification blanks remain unresolved. A benchmark may explicitly use the combined payoff/maturity competing outcome, but must not present it as validated pure prepayment.

## Phase 3 — 2026-09-20

Phase 3 implements the historical joint-survival/default/payoff-maturity curve under the Phase 2F proxy contract. Its 12-month cumulative incidence is distinct from the constant-rate hypothetical loan projection. Remaining-life loss is currently limited to that explicitly synthetic amortizing example. See methodology.md for censor timing, risk sets, event ordering, and loss timing.
