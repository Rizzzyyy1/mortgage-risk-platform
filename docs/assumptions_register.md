# Assumptions Register

## Purpose

This register captures the assumptions that must remain visible throughout the project so that the analytical design stays explainable and reviewable.

## A. Source and schema assumptions

### A1. Official source documentation is required before final schema claims
Assumption: the project will not treat any field name as final unless it is supported by the official vendor glossary or downloaded package.

Status: active and enforced.

### A2. Sample inspection supports physical format validation, not full-source certification
Assumption: the local sample proves the file layout, row structure, and monthly panel pattern, but not the full vendor package behavior across all acquisitions.

Status: active.

### A3. Data package availability is still a gating dependency
Assumption: the full Fannie Mae package or equivalent approved dataset remains the required historical source before production-grade model estimation.

Status: active and provisional pending vendor access.

## B. Cohort and population assumptions

### B1. Historical cohort and reporting portfolio are distinct
Assumption: model-development data and current portfolio reporting are separate populations.

Status: adopted.

### B2. A loan-month is the primary observation unit
Assumption: monthly loan-level state is the operating unit for risk estimation and exposure tracking.

Status: adopted.

### B3. The initial cohort will be modest and bounded
Assumption: the platform starts with one acquisition period or small development cohort instead of a broad production-scale portfolio.

Status: adopted.

## C. Event and timing assumptions

### C1. Default and prepayment are competing events
Assumption: a loan cannot be treated as both defaulted and prepaid in the same month unless a defined ordering rule explicitly allows it.

Status: adopted.

### C2. Event timing uses the monthly reporting period
Assumption: loan state changes are anchored to the reporting month, not to an unknown daily event date.

Status: adopted.

### C3. Censoring is explicit
Assumption: loans with no event within the observation window are not treated as non-events without clear censoring logic.

Status: adopted.

### C4. Modification and workout states are tracked separately
Assumption: modifications may affect exposure and default probability but do not disappear from the loan history.

Status: adopted.

## D. Exposure and loss assumptions

### D1. Exposure is defined at the loan-month level
Assumption: the project measures monthly exposure using the current unpaid principal balance or a coherent projected balance path, depending on the chosen benchmark.

Status: adopted.

### D2. Severity is conditional on default
Assumption: loss severity is estimated after default is identified and aligned with the chosen default definition.

Status: adopted.

### D3. Expected loss is distinct from scenario loss
Assumption: baseline expected loss and stress scenario loss are separate estimates that should not be merged without explicit labeling.

Status: adopted.

## E. Model-development assumptions

### E1. Transparent benchmark before complexity
Assumption: the project will start with a clear benchmark and only add complexity when evidence supports it.

Status: adopted.

### E2. Chronological evaluation is required
Assumption: the project will preserve time ordering and avoid leakage from future information into past predictions.

Status: adopted.

### E3. Calibration and segment review are required
Assumption: performance must be evaluated for both calibration and segmentation, not just discrimination.

Status: adopted.

## F. Communication assumptions

### F1. Educational framing remains in place
Assumption: the project is educational and CECL-inspired, not a regulator-certified or independently validated production model.

Status: adopted.

### F2. Uncertainty is reported visibly
Assumption: assumptions, data gaps, and evaluation limits are part of the project evidence and must remain visible in reporting.

Status: adopted.

## Phase 2E assumptions — 2026-09-20

The numerical six-month masking endpoints remain unresolved. Ages 0/6 and negative ages are excluded pending clarification; ages 1–5 are conservatively masked. The +/-1 note-month/age plausibility tolerance is a project screen, not a vendor equation. Terminal blanks remain unknown despite preceding Y/N observations. Positive eligible reported balance supports qualified descriptive analysis only, not full economic exposure or regulatory compliance. See target_definitions.md for the authoritative implementation policy and project_status.md for observed counts.

## Phase 2F — 2026-09-20

Phase 2F adopts 90+ delinquency or exit 02/03/09/15 as a project default proxy. Code01 is payoff/maturity, not pure prepayment. First unknown/gap/ambiguous/other-exit observations end follow-up conservatively. Entry is first observed month, not origination, and existing default/exit/unknown at entry is excluded from retrospective risk labels. These assumptions do not establish independent censoring or regulatory validity. See target_definitions.md.

## Phase 3 — 2026-09-20

Phase 3 assumes noninformative censoring for the historical curve without claiming it is empirically established. The hypothetical loan uses pooled first-12-month constant hazards, a $100,000 balance, 4% coupon, 120-month remaining term, baseline/adverse LGD 20%/35%, and stress multipliers 2.0 default/0.7 payoff-maturity. These are judgmental demonstration assumptions, not measured economic paths, calibrated stress or actual-cohort losses. Full details: methodology.md and configs/benchmark.json.

## Phase 4A — 2026-09-20

Phase 4A freezes disjoint loan groups at fixed 2011/2013/2015 landmarks. It assumes current-row inputs can support a historical prediction exercise, subject to vendor-revision limits. Single-cohort seasoning/calendar confounding and omitted credit attributes constrain conclusions. Censored labels must receive explicit treatment before fitting; no silent complete-case estimation.

## Phase 4B — 2026-09-20

Phase 4B explicitly estimates resolved-outcome conditional probabilities by delinquency/modification group. Unresolved training/validation rows are excluded with counts and prevalence bounds, not converted to zero. Noninformative missingness is not established. Training-only positive priors and validation-selected smoothing stabilize sparse groups; unseen groups fall back to the prior. No test refit. See methodology.md for equations and calibration limits.

## Phase 5 — 2026-09-20

Phase 5 specifies a 24-month stress plateau fading by month 60, 6/18-month recovery lags and 4% effective discount. All are hypothetical; LGD is undiscounted non-recovery severity. Actual cohort maturity/exposure, macro transmission and severity estimation remain open. See methodology.md and configs/stress_refinement.json.

## Phase 6 — 2026-09-21

Phase 6 PSI and O/E monitoring bands are post-hoc project judgments, sample-gated and not regulatory/operationally validated. Three split snapshots cannot establish robust drift or alarm performance. Independent calculation agreement verifies implementation, not actual economic forecast readiness. See methodology.md.
