# Phase 3 benchmark methodology

## Purpose and evidence boundary

The historical output is a retrospective nonparametric competing-risk benchmark for the accepted 2010Q1 cohort. The loss output is an explicitly hypothetical amortizing-loan demonstration. It is not actual-cohort economic exposure, estimated LGD, a validated forecast, or regulatory-compliant expected credit loss.

Inputs are fixed in configs/benchmark.json to the accepted Phase 2F run. No CSV scan, feature fitting, data expansion, or exposure imputation is performed. Code and config checksums are recorded with every run.

## Historical risk sets and joint probabilities

Time is elapsed calendar months after first observation, not loan age. The seven entry-ineligible loans remain accounted for outside the risk set. No exposure-eligibility filter is applied. Episode outcomes follow target_definitions.md; unknown/ambiguous/unsupported states censor before the unknown interval, gaps after the last valid interval, and other exits/observation end after that interval. Same-month censor/event ordering is a project convention.

At month t, n is the number still observable and event-free before the interval, d is defaults, p is combined payoff/maturity, and c is end-of-interval censoring. Check n(next) = n - d - p - c. Zero-duration censors leave before month 1. Censoring changes later denominators; it is not a competing probability state.

Use hD=d/n and hP=p/n; marginal event probabilities are prior survival times each hazard. Update survival by multiplying by (1-hD-hP), and accumulate the two event probabilities separately. Survival plus both cumulative incidences must equal one. The implementation uses a 1e-12 probability tolerance. The historical curve stops at observed support; it is not extrapolated beyond it.

This is the elementary competing-risk form of the Aalen–Johansen estimator. Method reference: [Therneau, Crowson and Atkinson, Multi-state models and competing risks, sections 2.1–2.2](https://cran.r-project.org/web/packages/survival/vignettes/compete.pdf). Interpreting the curve beyond observed cases requires a noninformative-censoring assumption that this project has not established. No confidence intervals or out-of-time validation are claimed.

## Illustrative exposure and loss projection

The first 12 months' event counts divided by their total observed risk-months provide two constant monthly demonstration hazards. These pooled rates differ from the age-varying historical curve and its 12-month cumulative incidence. Applying them to a hypothetical remaining term is an explicit transport/extrapolation assumption, not a fitted remaining-life model.

The example has $100,000 opening balance, 4% annual coupon, and 120 monthly payments. Conditional surviving balance follows the fixed-rate annuity schedule. The baseline uses the pooled hazards and 20% LGD. The single adverse example doubles default hazard, multiplies payoff/maturity hazard by 0.7, and uses 35% LGD. These are configurable judgmental values, not estimated severities or macroeconomic stress transmission.

Defaults/payoff proxies act on beginning-of-month balances before scheduled payment. Survival is applied once in marginal default probability. Each month's undiscounted expected loss equals that marginal default probability times conditional opening balance times LGD. Assumed recovery equals expected defaulted balance times (1-LGD). Decimal arithmetic is used for the payment and monetary calculations; loss equals expected defaulted balance minus assumed recoveries within 1e-8 dollars. Display rounding happens only in the report.

Probability remaining after events at the last payment matures explicitly. Conditional balance and survival both close to zero. The proxy early-exit hazard already combines vendor payoff and maturity; it is not represented as pure prepayment. The example reports 12-month default probability separately from remaining-life default probability and remaining-life expected loss. No recovery timing, discounting, or actual-cohort loss estimate is implied.

## Verification and next boundary

Tests cover hand-calculated competing hazards and censoring, invalid risk sets, immediate censoring, unknown/gap timing, an exact two-month zero-coupon loss calculation, amortization, single survival weighting, zero defaults, adverse direction, invalid assumptions, and the complete runner. All 62 project tests passed in 2.34s.

The full run reconciles the 12-month event counts back to Phase 2F, all episode removals, probability mass, maturity closure, and monetary losses/recoveries. The statistical and economic limitations remain even when engineering checks pass.

Phase 4 must establish prediction-time features, chronological training/evaluation and calibration before any predictive model claim. Actual cohort loss estimates additionally need verified remaining maturity/exposure and defensible severity/recovery inputs. Preserve this simple benchmark for comparison.

## Phase 4A fixed landmark design

The as-of observation is the end of the named reporting month (stored with a first-of-month period key). Outcomes cover the next 12 reporting months. Frozen dates are 2011-01 / 2013-01 / 2015-01; no outcome-informed date optimization occurred. Disjoint loan groups use the first MD5 hex character of loan_id: 0–b/c–d/e–f. This provides approximate 75%/12.5%/12.5% allocation before snapshot availability and risk exclusions, not equal split populations.

Only loans observed at the assigned landmark, initially eligible for the Phase 2F episode, currently 00–02 delinquent and with no analytical stop observed by that landmark are included. A future stop is used only for labels. In particular, a later-discovered gap must not retrospectively remove an otherwise eligible snapshot. Source-reported balance zeros and exposure eligibility do not define the event risk set.

Predictor allowlist: delinquency_months, loan_age_months (negative becomes missing), original_balance (nonpositive becomes missing), eligible_reported_balance (Phase 2E usable value, no imputation), modification_status (reported status, including explicit unknown). Loan ID and reporting month are join/audit keys, not predictors. Original balance is the vendor-reported value, not a replacement for masked current balance.

Future stop dates, exit codes, last observation dates, horizon outcomes and follow-up length are excluded from exported features. Labels are exported separately. Known default/payoff inside the window resolves that class; unknown/other exits/gaps lead to explicit censoring; complete observed event-free windows form the third known outcome. No censored case is labeled non-default. Feature transformations and imputation, if later justified, must fit on training only. Validation chooses the model; test is for final evaluation, with no refit based on test results.

Only one acquisition quarter is available. Age and calendar regime shift together, and future model validation must report train-support/feature-shift diagnostics; performance cannot be described as cross-vintage validation. FICO/LTV/DTI and contractual maturity are absent from the retained feature set. A revised vendor release does not establish point-in-time source availability. Model-ready design does not resolve these limitations or establish predictive skill.

## Phase 4B interpretable estimated model

Model target: the three resolved 12-month outcomes (default proxy, payoff/maturity, observed event-free), conditional on outcome resolution. The unresolved observations remain saved but are explicitly excluded from fitting/scoring: 45/220,282 training, 1/23,400 validation, 0/15,694 test. The model does not establish unconditional probabilities under informative censoring. Sensitivity bounds report observed defaults / all rows through (observed defaults + unresolved) / all rows; these bound prevalence, not individual predictions or discrimination bias.

Predictors are current delinquency (0/1/2) crossed with reported modification status. It is a smoothed categorical multinomial risk table, not logistic regression. No numeric preprocessing, imputation or severity fitting occurs. Loan age/balances are deliberately unused in this first benchmark; adding them requires training-support and stability checks, especially given calendar/seasoning shifts.

For class k, the training prior is pi_k=(n_k+0.5)/(N+1.5). For observed group g, probability is (n_gk+alpha*pi_k)/(n_g+alpha). Positive probabilities sum to one. Unseen groups fall back to the training prior. The constant reference predicts that prior for every row. The 0.5 pseudocount is fixed; alpha in {10,100,1000} is chosen solely on validation multiclass log loss, with the constant model also eligible. Selected alpha=10. Model JSON and selection evidence are written before test loading. No additional test-informed hyperparameter search was performed.

Metrics: mean three-class log loss; Brier as the sum of squared errors across the three probabilities; default AUC with half credit for tied scores; aggregate observed/expected defaults; exact-score calibration groups and delinquency/modification segments. AUC interval uses a seeded 200-replicate stratified percentile bootstrap of fixed predictions, conditional on class counts; it does not include model-fitting uncertainty, economic-regime uncertainty or between-vintage variation. Small segments are descriptive only.

The selected model improves final-test log loss, Brier and ranking over the constant reference. Aggregate O/E near one does not prove calibration across groups: current/unmodified defaults are underpredicted, and the modified test group contains only seven loans. There is no test-based recalibration or decision threshold. Performance is qualified evidence for this cohort/split, not proof of production suitability.

The implementation uses grouped SQL counts and a small reusable Python estimator, with no added model dependencies. All 68 tests pass, including exact smoothing, unseen-group fallback, probability validation, hand-computed Brier/log loss/AUC, censor handling, bootstrap and end-to-end selection. Selected parameters and test predictions are persisted for later comparison without reopening model selection.

## Phase 5 stress and recovery refinement

The reusable projector now accepts either scalar hazards/severity or explicit monthly paths; constant-path equivalence is tested and prior baseline values reconcile. Phase 5 uses only the accepted hypothetical loan and frozen Phase 3 pooled hazards. Phase 4's conditional 12-month predictions are not converted into lifetime hazards.

Adverse intensity is 1 through month 24, (60-t)/36 in months 25–59, and 0 from month 60. Default hazard multiplier is 1+intensity, payoff/maturity multiplier is 1-0.3*intensity, and assumed LGD is 0.20+0.15*intensity. These are judgmental transient paths, not macro-calibrated forecasts. The earlier sustained-stress scenario remains a separate accepted result, so its higher expected loss is not a discrepancy.

Recovery delay is six months baseline and eighteen adverse. Annual effective discount rate is 4%; monthly factor q=(1.04)^(1/12). Timing-adjusted PV loss sums expected defaulted opening balance divided by q^t minus assumed recovery divided by q^(t+lag). Undiscounted loss remains defaulted balance minus recovery, independent of lag. Recoveries after contractual maturity are included. LGD here excludes delay and represents the undiscounted non-recovery fraction, preventing double-counting recovery timing. No recovery costs, calibrated recovery distribution, or regulatory accounting interpretation is asserted.

Exact Shapley attribution evaluates all 16 combinations of four drivers. Each marginal contribution is averaged over every possible driver ordering, allocating interactions symmetrically. Contributions reconcile to adverse-minus-baseline separately for undiscounted and PV losses within 1e-8 dollars; presentation rounding may differ by a cent. This is scenario attribution, not causal identification.

The sensitivity grid changes one input at a time around baseline: default multiplier 0.5/1/2, payoff multiplier 0.5/1/1.5, LGD 0.10/0.20/0.35, term 60/120/180 months, discount 0/4%/8%, and recovery lag 0/6/18 months. Direction checks apply to these assumptions, not universal monotonicity claims for arbitrary economic models. No probability distributions or confidence levels are assigned to the sensitivity range.

Full default/payoff/maturity probability closure, annuity closure and loss/recovery reconciliation run inside every projection. Tests additionally prove zero-discount timing equivalence, delayed-recovery PV direction, recovery-tail inclusion, stress boundaries and hand-calculated interaction allocations.

## Phase 6 consolidated verification and monitoring replay

The runner reads the seven accepted milestone reports and fingerprints them; it checks linked run identities and population totals. It reads saved test predictions and original labels without refitting, checks the probabilities against the frozen model, verifies validation-only selection, and recomputes proper scores/AUC in SQL. Floating summation differences are accepted only within 1e-9. Historical risk-set counts and joint probability recursion are checked directly. Stress cashflows are discounted with direct annual-factor powers, while the original used a monthly factor. Driver contributions are recomputed over all 24 permutations, independently of the original subset-weight formula; the monetary tolerance is 1e-8 dollars. These are independent calculations performed by the developer, not an independent external audit.

Monitoring replay uses only the existing 2011/2013/2015 split snapshots. Population Stability Index (PSI) compares delinquency/modification group proportions with the training reference, adding 0.5 to each aligned group count before normalization. PSI=sum((current-reference)*log(current/reference)). Different loans, seasoning and calendar periods limit causal interpretation. Population flags use 0.10 warning / 0.25 critical. Calibration O/E warning bounds are 0.80–1.25 and critical bounds 0.67–1.50; groups require at least 100 loans and 20 expected defaults for a flag. Otherwise report insufficient support. Unresolved-label fraction above 1% warns.

All thresholds are retrospective project judgments selected with prior results visible, not pre-registered or empirically calibrated alert thresholds. No alarm frequency or false-positive rate is estimated. Training is a population reference, not a held-out calibration evaluation. Validation and test use saved scores; no threshold optimizes or changes their predictions.

Actions: investigate current/unmodified underprediction using fresh validation evidence; preserve the frozen test. Collect further outcomes for sparse groups rather than interpreting a zero-event small cell as safe. If data-quality/probability checks fail, stop downstream report acceptance; if population/calibration flags fire, investigate source changes and uncertainty before separately authorizing retraining. This is a documented offline replay and action plan, not a scheduled live monitoring service.
