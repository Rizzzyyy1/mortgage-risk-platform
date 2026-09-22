# Mortgage Credit Risk & Stress Testing Platform

A reproducible research project connecting mortgage data engineering, competing-event analysis, an interpretable risk benchmark, illustrative stress testing and an evidence-led dashboard.

## For reviewers: start here

This is a research handoff, not a production system. **Overall model acceptance is qualified/pending review** — see the acceptance matrix in `docs/final_report.md`.

- **[Reviewer presentation](docs/reviewer_presentation.html)** — a standalone, offline HTML file (open directly in any browser, or print to PDF): business question, data/chronological design, architecture, model versions, calibration and segment findings, workout/loss evidence, the acceptance matrix, and reproduction instructions.
- **[Final report](docs/final_report.md)** — the single concise handoff document: findings, the acceptance matrix, supported/unsupported claims.
- **Historical dashboard** — `.venv/bin/python -m mortgage_risk.dashboard`, from the original workspace only; it requires private accepted-report artifacts not bundled in this package, and shows **only the original frozen benchmark**, never the redeveloped/calibrated candidate. See "Historical dashboard" below.
- **[Latest model evaluation and limitations](docs/professional_review.md)** — model inventory, control assessment, the five-minute reviewer walkthrough, and monitoring specification.
- **Synthetic demonstration** — runs without any vendor data; see "Run without private data" below.

## What is verified

- Historical engineering: 20,983,277 loan-month records, 323,174 loans and 195 reporting months reconciled.
- Chronological model evaluation and calibration/segment reporting, with single-cohort and censoring qualifications.
- Transparent hypothetical loss scenarios, sensitivity and reconciled driver attribution.
- A local four-view dashboard and executive memo; dashboard controls manually verified by the user.

Actual-cohort lifetime losses are **not ready**. Illustrative stress losses are not historical portfolio losses or regulatory estimates.

## Current model acceptance — qualified, pending segment review

The **original** expanded challenger improved risk ranking on the reserved 2011Q1 cohort but **failed calibration acceptance** (890 observed versus 1,131 expected defaults); a bounded development-only adjustment did not meaningfully improve it. That result is immutable. With 2012Q1/2013Q1 now acquired, the same model was **redeveloped**: 2011Q1 was used only for development-validation (out-of-cohort model selection), 2012Q1 only to fit intercept calibration, and 2013Q1 was the one genuinely untouched final evaluation — **all six preregistered aggregate quantitative gates passed** (AUC 0.875 vs. 0.639 benchmark, aggregate O/E 0.814 within [0.8, 1.25]). These three cohorts are loan-disjoint but are not three independent tests of the final calibrated model; only 2013Q1 tests it.

That aggregate pass does not resolve segment calibration. A bootstrap-quantified segment review (`docs/final_report.md`) found the same opposite-direction miscalibration on 2013Q1 that appeared on 2011Q1 and 2012Q1 — and it is not sparse noise: the current/unmodified segment (656,937 of 658,447 loans, 99.8% of the population) **overstates** risk (O/E < 1) with a 95% interval of **[0.675, 0.797]**, entirely below the 0.8 floor, and the FICO 720+ segment (87% of loans) overstates risk at **[0.561, 0.694]**. The two-month-delinquent and FICO<660 segments **understate** risk (O/E > 1), with point estimates above the 1.25 ceiling but 95% intervals whose lower bounds (1.217 and 1.104) sit just inside the band — so, unlike the first two segments, the evidence does not establish separation from the band with the same 95% confidence. **Overall model acceptance is therefore qualified/pending review, not an unconditional pass** — see the acceptance matrix in `docs/final_report.md`. No production model is approved. See [external results](docs/external_evaluation_results.md), [calibration experiment](docs/calibration_remediation.md), [the redevelopment evidence](docs/redevelopment_plan.md) and [monitoring and use boundaries](docs/professional_review.md). The dashboard retains the original historical benchmark.

## Loss-workout, exposure and vendor-reconciled loss evidence (separate from the PD model above)

Every 2010Q1 default episode has been followed to its last supportable resolution: **24.1%** reach an actual property disposition (exactly matching the loans with recorded loss fields), the rest pay off, cure, exit some other way, or remain open. Default-anchor exposure is quantified for 94.1% of episodes without ever substituting a missing/masked/terminal balance. A **descriptive, explicitly-not-LGD** realized-loss profile — now reconciled against Fannie Mae's own retrieved and traced official R code — covers the resulting loan subsets. See [redevelopment plan and evidence](docs/redevelopment_plan.md) for the full chain, including why the vendor's own "credit event" trigger differs from this project's PD default-proxy anchor and why this stays uncoupled from the PD model above.

## Run without private data

Verified baseline: Python 3.14, macOS ARM64. From this repository:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -r requirements-build.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation .
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
.venv/bin/python -m mortgage_risk.demo --output artifacts/runs/synthetic-demo-001
```

Choose a new output directory each time. The demo uses invented inputs and reuses the existing risk/loss engines. It produces JSON results, monthly schedules and checksums without vendor files. One optional integration test skips when the vendor sample is absent.

## Review the project

- [Final report — concise handoff summary](docs/final_report.md)
- [Setup, real-data workflow and release limitations](docs/release_guide.md)
- [Current acceptance evidence](docs/project_status.md)
- [Analytical definitions](docs/target_definitions.md)
- [Methodology](docs/methodology.md)
- [Validation record](docs/validation_audit.md)
- [Release readiness — packaging, licensing and CI evidence](docs/release_readiness.md)
- [Phase roadmap](docs/roadmap.md)

## Professional review

[Architecture and evidence flow](docs/architecture.md) · [Model inventory, controls, remaining risks and reviewer walkthrough](docs/professional_review.md)

Run `sh scripts/check_release.sh` for dependency checks, the test suite and a fresh synthetic demo. Reporting now fails closed if any fingerprinted dashboard input changes. Fingerprints are integrity checks, not independent certification. A vendor-data-free GitHub Actions workflow (`.github/workflows/ci.yml`) runs the same checks; [it passed on GitHub for commit `846ace9`](https://github.com/Rizzzyyy1/mortgage-risk-platform/actions/runs/35771122605) — a verified result for that specific commit, not a standing guarantee that every later commit passes. Check the [Actions tab](https://github.com/Rizzzyyy1/mortgage-risk-platform/actions) for the current commit's status.

## License

MIT for the original code and documentation in this repository — see [LICENSE](LICENSE). Third-party dependencies and vendor data/methodology are separately attributed and excluded from that grant — see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Architecture

Python handles orchestration and transparent calculations; DuckDB/SQL handles analytical aggregation; Parquet stores detailed outputs. Reusable logic is in src/mortgage_risk/, SQL in sql/, configurations in configs/, tests in tests/, and the local dashboard template in app/. Generated runs and vendor data remain ignored.

## Historical dashboard

In the original workspace, run `.venv/bin/python -m mortgage_risk.dashboard` from the repository root to build a new dashboard from the accepted reports specified by configs/dashboard.json and configs/consolidated_validation.json. Open its generated index.html locally. A clean checkout lacks those private historical artifacts; use the synthetic demo there. The historical pipeline retains explicit cohort/run references and is not a generic one-command rebuild.

No publication, deployment or regulatory certification is implied.

## Expanded-risk research challenger

An internally evaluated regularized multinomial challenger now supplements the frozen benchmark. See [evaluation and qualifications](docs/challenger_evaluation.md). It was evaluated on a later cohort and failed its calibration acceptance gate; it has not replaced the historical dashboard model. Run `.venv/bin/python -m mortgage_risk.challenger` only with the configured private development artifacts.
