# Reproducible review

## Supported and verified environment

The expanded dependencies were verified on 2026-09-22 in a new Python 3.14/macOS ARM64 virtual environment without system-site packages. The built wheel was installed non-editably and tested outside the source tree: 109 tests passed, one vendor-data test skipped, dependency checks and the synthetic demo passed. Other Python/platform combinations have not been release-tested. Runtime/test dependencies are pinned in requirements.lock; packaging tools in requirements-build.lock. These are version pins, not a cross-platform hash lock. Install from a trusted package index.

From the repository root:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -r requirements-build.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation .
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
.venv/bin/python -m mortgage_risk.demo --output artifacts/runs/synthetic-demo-001
```

Use a new output directory for every demo. Existing output directories are deliberately rejected. The demo also works outside the repository after package installation. It writes reproducible JSON schedules, results, a checksum manifest and an explanation. No Fannie Mae data, saved run, external service, credentials or browser is used. It exercises the existing competing-event and loss engines with invented inputs; it does not reproduce empirical model training or the historical dashboard.

The vendor integration test skips explicitly when the sample is absent. All synthetic tests still run. In the original workspace, the vendor test continues to run against the local sample. Test counts and skips must be reported separately.

## Historical-data workflow

The current four-view dashboard presents saved historical aggregates and requires the accepted local artifact chain. It is not included in the vendor-free demo. The dashboard can be opened from its generated index.html without a server. Its controls were manually confirmed by the user; automated visual inspection remains unavailable.

For an authorized local historical workflow:

1. Acquire the relevant primary acquisition/performance quarter and matching official glossary independently under the vendor access conditions. Keep these in ignored data/raw/fannie_mae_loan_performance/. Do not rename a different schema to pretend it matches.
2. Inspect the layout before using historical-ingest. Start with a small pilot; use its explicit --input and --output-dir options. Full ingestion is a separate deliberate action. Preserve source checksum and schema evidence.
3. Establish exposure eligibility, validate supplemental keys and join counts, reconcile monthly balances, and preserve exclusions before descriptive or modeling work.
4. Run the documented descriptive, benchmark, model-design, estimated-model, stress and consolidated-validation modules in dependency order. The configs name exact accepted run IDs. The exposure/descriptive modules also retain cohort-specific run references. They must be deliberately rebound and revalidated for a new cohort; this release does not claim a portable one-command historical rebuild.
5. Generate the dashboard only after consolidated validation passes, using its report fingerprints. Never copy the historical acceptance verdict onto new inputs.

See docs/target_definitions.md, docs/methodology.md and docs/project_status.md for mathematical definitions, limitations and exact local evidence. No additional acquisition, historical rerun, refit or publication was performed for this release.

## Repository hygiene and limitations

Raw/intermediate/processed data, run artifacts, environments, databases and journals are ignored. Synthetic fixtures and source code remain reviewable. Git ignore rules do not remove previously tracked files: verify the index before any future commit. No commit or publication is part of this milestone. Do not distribute vendor files or historical artifacts merely because the demo is vendor-free.

Actual-cohort lifetime loss remains unsupported. Severity assumptions and illustrative stress are not estimates of that cohort's loss, and the conditional model is a single-cohort benchmark. Release engineering completion does not remove these qualifications.

## Repeatable review check

Run `sh scripts/check_release.sh` from the root. It checks installed dependencies, runs all tests (with the explicit vendor-data skip when appropriate), and creates a fresh synthetic demo. Dashboard inputs are pinned by configs/dashboard_integrity.json; a changed or missing required artifact stops the build. Review and validate changed inputs before deliberately replacing that receipt. See professional_review.md for remaining production and model-risk gaps.


## Latest clean release evidence — 2026-09-22

Evidence: `artifacts/runs/clean_release/1efd8de3f336419eb7f94eeef6f6f0c4/verification_result.json`. The wheel inventory contains 29 package/metadata members, with no CSV, Parquet, database, PDF or .env files. This is a package-content check, not a comprehensive security certification. The Git index contains no tracked files; 89 nonignored files remain untracked. Nothing was staged, committed or published. Historical configs and private artifacts are not bundled in the wheel.
