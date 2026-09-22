# AGENTS.md

This project follows the parent workspace instructions and the agreed architectural baseline in PROJECT_PLAN.md. The working rule is to keep the work bounded, inspect existing work before editing, and stop at the milestone boundary once verification is complete.

## Purpose
- Build a professional, reproducible portfolio project demonstrating mortgage data engineering, portfolio analytics, credit modeling, expected loss, stress testing, and clear business communication.
- Keep the work educational and CECL-inspired rather than claiming regulatory compliance or validation beyond the project’s own evidence.

## Architecture
- Follow PROJECT_PLAN.md as the agreed baseline and add modules only as phases require them.
- Use Python, SQL, DuckDB, and Parquet initially; add one dashboard later only when the analysis is ready.
- Add dependencies only for a current requirement and prefer the smallest working implementation.
- Keep reusable calculations in src/mortgage_risk/ and the SQL layer. Notebooks explain and investigate; the dashboard presents validated outputs.
- Avoid duplicated analytical logic across notebook calculations, dashboard code, and package functions.

## Workflow
- Inspect existing work before changing it.
- Complete each requested milestone autonomously, including debugging, verification, and documentation.
- Preserve working components and do not rebuild the project at the start of each task.
- Within the milestone authorized for this task, proceed with routine project edits, local tests, debugging, and documentation without asking conversational permission repeatedly.
- Respect required system approval dialogs and security controls. Project instructions do not override security restrictions.
- Reduce avoidable approval requests by using the project-local environment and workspace, avoiding unnecessary dependency reinstalls or upgrades, creating uniquely named temporary test environments instead of deleting a fixed directory before each run, and keeping installation, cleanup, and verification commands separate so any approval request has a clear scope.
- Request only the permissions needed for the specific action.
- When approval is required, explain the action, why it is necessary, and what triggered the request.
- Stop at the milestone boundary and leave the next phase clearly documented.
- Ask only when missing information materially changes analytical meaning, scope, access requirements, or an irreversible action. Make routine reversible implementation decisions independently and document consequential choices.

## Data integrity
- Never modify raw inputs or synced reference material.
- Verify source documentation and actual fields before making claims or modeling assumptions.
- Document provenance, schemas, exclusions, joins, transformations, and reconciliation evidence.
- Never silently discard observations or hide gaps in source coverage.
- Keep restricted data and secrets out of Git and clearly distinguish synthetic demo inputs from real data and empirical findings.

## Analytical integrity
- Define the portfolio population, reporting date, eligible exposures, default, prepayment, censoring, modifications, recoveries, and loss perspective before modeling.
- Keep 12-month default probability, remaining-life expected loss, and scenario losses distinct.
- Use coherent monthly default and prepayment competing-event logic. Align survival, exposure, severity, and recovery assumptions without double-counting.
- Use prediction-time information and chronological evaluation. Fit preprocessing on training data only. Evaluate calibration and segment performance alongside discrimination.
- Introduce complex models only after establishing a transparent benchmark.
- Describe the methodology as educational and CECL-inspired. Do not claim regulatory compliance or independent validation of developer self-review.

## Reproducibility
- Use a validated configuration, documented execution stages, and an explicit project environment.
- Record run configuration, reporting date, code/data/model/scenario versions, metrics, logs, and reconciliation evidence.
- Never silently substitute synthetic inputs when real data is missing.

## Efficiency
- Develop on a small cohort before scaling. Inspect schemas and targeted samples before loading large datasets.
- Use meaningful tests for calculations and failure cases. Avoid repeated expensive runs unless changes or unresolved concerns justify them.
- Keep documentation proportional. Do not create redundant reports or planning files.

## Completion
- A milestone is complete only when its acceptance checks pass.
- Distinguish implemented, tested, blocked, and planned work.
- End each milestone with changes, verification results, limitations, completion status, and one copy-ready next instruction.
- Keep run outputs in artifacts/runs/ and curated reports separate from generated output.

## Delivery priorities
- Prioritize fast completion with defensible mathematical reasoning, readable code, reproducible pipelines and polished reviewer-facing outputs.
- Work in substantive bounded milestones, including implementation, targeted tests, fixes and concise documentation; avoid unnecessary approval handoffs within authorized scope.
- Reuse accepted artifacts and preserve stable interfaces. Avoid redundant audits, duplicate reports, premature abstractions and unnecessary dependencies.
- Keep progress and final updates concise. Spend tokens on resolving material uncertainty and validating behavior; never hide limitations or weaken acceptance checks to appear finished.
