# Project Charter

## Purpose

This project is a bounded, evidence-based mortgage-risk platform designed to demonstrate mortgage data engineering, portfolio analytics, credit risk modeling, expected-loss estimation, and scenario stress testing. The work is educational and CECL-inspired, not a regulatory or validated production model.

## Mission

Build a reproducible project that:

- validates source material and data provenance,
- defines a credible loan-level monthly mortgage panel,
- produces transparent benchmark metrics,
- separates model-development cohorts from reporting portfolios,
- and communicates uncertainty and assumptions clearly.

## Scope boundary

This document defines the project contract for Phases 1B onward. It does not authorize broad data acquisition, production deployment, or unsupported estimation claims.

In scope:

- source assessment and evidence-based field validation,
- monthly mortgage performance panel design,
- benchmark credit risk metrics,
- expected-loss and scenario analytics,
- transparent assumptions and decision logging,
- documented reporting and review outputs.

Out of scope for this milestone:

- claiming regulatory compliance,
- using unverified production data as a final source,
- broad or unsupported model complexity,
- dashboard or app features before the analytical foundation is stable,
- large-scale implementation beyond the agreed small cohort and benchmark path.

## Project question

How should the platform define mortgage default risk, exposure, loss, and scenario sensitivity in a disciplined and explainable way using the Fannie Mae loan-performance structure and a small, evidence-based cohort?

## Success criteria

The project will be considered successful when it can show:

1. a clear population definition and reporting date,
2. a coherent set of event definitions and timing rules,
3. a transparent exposure and severity framework,
4. a reproducible benchmark for 12-month default risk,
5. distinct remaining-life expected loss and scenario-loss outputs,
6. visible assumptions, limitations, and evidence lineage.

## Governance principles

- Keep raw vendor files unchanged.
- Distinguish historical cohort design from current portfolio reporting.
- Treat default and prepayment as competing events where appropriate.
- Use monthly observation arrays to maintain operational consistency.
- Preserve the difference between prediction-time information and outcome realization.
- Document any provisional definition when vendor data is still incomplete or a data package is not yet fully inspected.

## Core population model

The project will maintain two separate populations:

- Historical development cohort: a defined acquisition-quarter or comparable historical sample used for model development and event analysis.
- Reporting portfolio: the set of loans eligible at a specified reporting date for current-period monitoring or scoring.

These populations must not be collapsed into one measurement. A historical training cohort is not a current portfolio snapshot, and a current portfolio snapshot is not a development cohort.

## Reporting date and observation grain

- Observation grain: loan-month.
- Reporting date: an explicit month-end or month-start calendar date chosen for each analysis run.
- Each loan-month record carries the loan’s static information and the monthly dynamic state that is known at that reporting date.
- The monthly observation structure is required for time-to-event logic, exposure tracking, and competing events.

## Decision boundary

The platform will proceed with the analytical contract defined in this charter and the supporting definition documents. It will not begin broad model fitting until the data package and schema are verified against the official vendor source and the small cohort is reconciled.
