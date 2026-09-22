# Project Roadmap

## Delivery priorities — 2026-09-22

- Completed research components: historical ingestion/reconciliation, exposure qualification, descriptive analytics, benchmark, illustrative stress engine, historical dashboard, external challenger evaluation and bounded calibration experiment. Completion of an experiment does not mean its model passed.
- Current model gate: external calibration FAILED; remediation demonstrated no meaningful improvement. Actual-cohort lifetime loss NOT READY.
- Current delivery work: consolidate reviewer limitations/monitoring and verify the local release check.
- Next finite delivery gate: clean-environment verification after numerical dependency expansion, followed by source/distribution review.
- Optional separate redevelopment: chronological multi-vintage design and fresh final evaluation; no open-ended calibration search or automatic new downloads.
- Production controls, independent validation and real-cohort economic modeling remain outside the completed research scope.

The original phase definitions below are retained as scope references, not a claim that every acceptance criterion is passed.

## Phase 0 — Foundation

### Purpose
Finish configuration validation, the documented execution entry point, dependency locking, and environment reproducibility. Preserve the workspace initialization already completed.

### Prerequisites
- Verified project-local Python environment
- Working editable package installation
- Project root documentation and status files in place
- AGENTS.md and PROJECT_PLAN.md as the standing project baseline

### Bounded milestone
Establish the documented setup and smoke-check path in a clean environment using the current project-local package and environment.

### Deliverables
- Verified Python baseline and editable install
- Environment setup commands recorded in README.md
- Dependency lockfile task explicitly tracked as unresolved until implemented
- project_status.md updated to reflect the verified state

### Acceptance evidence
- Project-local environment works
- Package imports in editable mode
- README.md setup commands match the actual environment
- No project execution beyond setup and smoke validation

### Exclusions
- No mortgage data downloads
- No analytical modeling or scoring work
- No dashboard implementation

---

## Phase 1 — Source assessment and analytical definitions

### Purpose
Assess source documentation and available files. Define the population, observation grain, event definitions, time windows, exposure, and loss perspective.

### Prerequisites
- Project structure and environment are stable
- Source materials or documentation are available for assessment

### Bounded milestone
Verify field mappings, identify data gaps, and establish feasible analytical definitions for the portfolio and loss perspective.

### Deliverables
- Data source inventory and access status
- Initial schema and field mapping notes
- Explicit exclusions, event definitions, and missing data records
- Separate synthetic demonstration track if real data is unavailable

### Acceptance evidence
- Verified field mappings and source provenance
- Explicit data gaps documented
- Feasible population and loss definitions recorded
- No silent substitution of missing real data

### Exclusions
- No model fitting or stress simulation yet
- No broad production assumptions or regulatory claims

---

## Phase 2 — Monthly data and portfolio analytics

### Purpose
Implement ingestion, schemas, quality checks, transformations, monthly analytical data, and portfolio summaries.

### Prerequisites
- Phase 1 definitions and field mappings are settled
- Source files or synthetic inputs are available

### Bounded milestone
Create a small, reconciled cohort with verified keys, joins, dates, exclusions, counts, and balances.

### Deliverables
- Ingestion and schema validation code
- Quality checks and transformation scripts
- Monthly analytical dataset and portfolio summary outputs

### Acceptance evidence
- Keys, joins, dates, exclusions, counts, and balances reconcile for a small cohort
- Data provenance and assumptions are documented

### Exclusions
- No final default or loss models yet
- No large-scale production migration or broad dataset expansion

---

## Phase 3 — First end-to-end benchmark

### Purpose
Connect transparent monthly default/prepayment logic, exposure projection, severity assumptions, a baseline, and one adverse scenario.

### Prerequisites
- Phase 2 monthly analytics and portfolio summaries are in place
- Population and event definitions are fixed

### Bounded milestone
Produce a hand-checkable benchmark with separate 12-month default and lifetime/scenario loss outputs.

### Deliverables
- Default/prepayment logic with a transparent baseline
- Exposure projection and severity assumptions
- One adverse scenario and reconciled benchmark outputs

### Acceptance evidence
- Probabilities, survival, and losses reconcile
- Assumptions are visible and hand-checkable
- 12-month default and lifetime/scenario losses remain distinct

### Exclusions
- No complex challenger models yet
- No broad scenario matrix beyond the benchmark case

---

## Phase 4 — Estimated models

### Purpose
Develop interpretable default/prepayment and severity benchmarks where available data supports them. Add a challenger only when justified.

### Prerequisites
- Phase 3 end-to-end benchmark passes reconciliation checks
- Training and evaluation chronology is defined

### Bounded milestone
Fit and compare benchmark models using chronological evaluation with documented leakage checks.

### Deliverables
- Calibration and discrimination assessment
- Segment performance reporting
- Model selection rationale and limitations

### Acceptance evidence
- Reproducible chronological evaluation
- Leakage checks pass
- Calibration and segment assessment are documented
- Model improvements are justified by evidence

### Exclusions
- No fabricated model estimates
- No unsupported complexity beyond the justified benchmark/challenger logic

---

## Phase 5 — Lifetime loss and stress refinement

### Purpose
Improve economic paths, exposure dynamics, recoveries, sensitivity analysis, and loss-driver attribution.

### Prerequisites
- Phase 4 model evaluation is stable
- Benchmark and challenger outputs are available

### Bounded milestone
Refine the lifetime loss and stress framework so the key drivers and scenario effects are explainable.

### Deliverables
- Updated severity and recovery assumptions
- Portfolio and component loss analysis
- Sensitivity and attribution evidence

### Acceptance evidence
- Component and portfolio losses reconcile
- Scenario effects are explainable
- Uncertainty and limitations are documented

### Exclusions
- No unsupported regulatory or production certification claim

---

## Phase 6 — Validation and monitoring

### Purpose
Consolidate backtests, implementation checks, stability analysis, limitations, and monitoring replay where supported.

### Prerequisites
- Phase 5 loss and stress outputs are stable
- Modeling logic and assumptions are documented

### Bounded milestone
Create a validation package and monitoring plan supported by evidence.

### Deliverables
- Backtest and implementation checks
- Stability analysis and monitoring actions
- Limitations and governance notes

### Acceptance evidence
- Validation report is evidence-based
- Monitoring measures and response actions are clearly documented
- Judgmental thresholds are accurately labeled

### Exclusions
- No production deployment or governance certification beyond project-contained validation

---

## Phase 7 — Dashboard and executive communication

### Purpose
Build one dashboard covering portfolio risk, model performance, lifetime loss/stress, and validation/limitations. Create an executive memo and reviewer-friendly README.

### Prerequisites
- Phase 6 validation and monitoring outputs are in place
- Reporting date and provenance are clear

### Bounded milestone
Present validated outputs to stakeholders while clearly showing provenance, run identity, and demo/real-data status.

### Deliverables
- One dashboard with reconciled figures
- Executive memo and reviewer-facing summary
- Updated run and experiment metadata

### Acceptance evidence
- Displayed figures reconcile to saved outputs
- Reporting date, provenance, model version, and data status are visible
- Demo vs real-data status is labeled clearly

### Exclusions
- No deployment or publication tasks outside the project’s review workflow

---

## Phase 8 — Reproducible release

### Purpose
Verify a clean setup, fast synthetic demo, documented real-data workflow, automated checks, and repository hygiene.

### Prerequisites
- All analytical and review phases are complete
- Project reports and dashboard outputs are reconciled

### Bounded milestone
Prepare the project for reproducible review by another analyst without private data.

### Deliverables
- Clean setup guide and fast demo run
- Real-data workflow documentation
- Automated checks and repository hygiene evidence

### Acceptance evidence
- Another analyst can reproduce the demo without private data
- Private data remains excluded from Git and local workflow docs

### Exclusions
- Publication and deployment are separate, authorized tasks

---

## Cross-phase rule
Preserve a working end-to-end benchmark as later phases improve individual components.

When definitions or inputs change, identify affected downstream outputs and rerun the relevant checks.
