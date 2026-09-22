# Release readiness — publication-hardening milestone

Concise evidence record for the publication-hardening milestone (sanitization,
overlap-check fix, frozen-input enforcement, portable handoff, licensing/CI,
release-candidate verification). This is a packaging/release-process
verification, separate from and does not change the model acceptance
verdict recorded in `docs/final_report.md` (qualified/pending segment
review).

## 1. Licensing and metadata

- `LICENSE` (MIT, copyright Rizwan Ahmmed) scopes coverage to original
  source/docs and explicitly excludes third-party material.
- `THIRD_PARTY_NOTICES.md` (new) documents: Fannie Mae vendor data (not
  redistributed; `data/raw/` gitignored), Fannie Mae's official R
  methodology (read for reconciliation, never vendored or executed), and
  every third-party Python dependency with its license identifier, each
  verified against the actually-installed package metadata (`pip show`),
  not assumed from memory.
- `pyproject.toml` now declares `authors = [{name = "Rizwan Ahmmed"}]`,
  `license = "MIT"` (SPDX expression), and `license-files = ["LICENSE",
  "THIRD_PARTY_NOTICES.md"]` (PEP 639), plus standard trove classifiers.
  `[build-system] requires` raised to `setuptools>=77` (needed for PEP 639
  license-file support; the pinned build tool, setuptools 84.0.0 in
  `requirements-build.lock`, already satisfies this).
- **Verified in a real build**: both the built wheel
  (`mortgage_risk_platform-0.1.0-py3-none-any.whl`) and sdist
  (`mortgage_risk_platform-0.1.0.tar.gz`) contain `LICENSE` and
  `THIRD_PARTY_NOTICES.md` (wheel: under
  `*.dist-info/licenses/`; sdist: at the package root). The wheel's
  `METADATA` shows `License-Expression: MIT`, `Author: Rizwan Ahmmed`, and
  two `License-File` entries.

## 2. GitHub Actions CI

- Added `.github/workflows/ci.yml`: triggers on push/PR/manual dispatch,
  `permissions: contents: read` only, no secrets or vendor credentials.
  Steps: install pinned deps (`requirements.lock` +
  `requirements-build.lock`), build/install the package non-editably,
  `pip check`, run the test suite, run the synthetic demo — all using only
  public PyPI packages and the repository's own synthetic fixtures.
- Runner/Python pin (`macos-14`, Python 3.14) matches this project's
  verified baseline stated in `README.md`.
- YAML validated by parsing it with `PyYAML` locally; every step's command
  was independently exercised (see §3) with matching results.
- **Not yet run by GitHub at the time this report was written.** This
  repository had no remote configured yet, so no push or pull request had
  triggered this workflow. Nothing here was described as "CI passing" —
  only as locally verified, equivalent steps.
- **Update (post-publication):** the repository has since been published
  to `https://github.com/Rizzzyyy1/mortgage-risk-platform`, and this
  workflow [passed on GitHub for commit
  `846ace9`](https://github.com/Rizzzyyy1/mortgage-risk-platform/actions/runs/35771122605).
  That confirms this specific run, not a standing guarantee that every
  later commit passes — check the repository's Actions tab for the
  current commit's status. `docs/professional_review.md`'s
  dependency-assurance row reflects this update.

## 3. Release-candidate verification (evidence)

All commands below were run today (2026-09-22) against the current working
tree (commit `ba49540b7918a8357e6c3bf86f88f5570ad810ae` plus the
uncommitted changes listed by `git status`, none of which were committed).

| Check | Result |
|---|---|
| Full test suite, dev checkout (`.venv`, vendor sample present) | `203 passed` |
| Fresh build (`python -m build`) | sdist + wheel built cleanly; both contain `LICENSE` and `THIRD_PARTY_NOTICES.md` (verified by extracting and listing each archive) |
| Fresh venv, wheel installed non-editably (`pip install --no-deps <wheel>`), outside the checkout | `import mortgage_risk` resolves to the venv's `site-packages/mortgage_risk/__init__.py`, not to `src/` |
| `pip check`, fresh venv | No broken requirements |
| Test suite, run from a directory outside the checkout (only `tests/` and `configs/` copied out; no `src/`, no `.git`, no `data/`), private vendor data genuinely absent | `202 passed, 1 skipped` — the one skip is the optional vendor-sample integration test (`tests/test_sample_ingestion.py:31`, "local vendor sample is absent"), the expected and correct outcome without private data |
| Synthetic demo, fresh venv, outside the checkout | `{"status": "pass", "data_status": "SYNTHETIC ONLY — no vendor data or fitted estimates", ...}`; produced `demo_result.json`, `manifest.json`, schedules and a README in the output directory |
| Console entry point (`mortgage-risk`), fresh venv | Installed and runs (`--help` lists subcommands) |
| README's literal "Run without private data" command sequence, separate fresh venv | Reproduced exactly as documented: clean install, `pip check` clean, `203 passed` (vendor sample present in this checkout, so no skip here), demo status `pass` |
| Relative-link check, README + all `docs/*.md` (21 files) | All relative links resolve |

The 203-vs-202 difference above is expected and not a discrepancy: the dev
checkout has a local vendor sample on disk (so that one optional test
runs), while the outside-checkout run has no `data/` directory at all (so
it correctly skips). Both are consistent with "private data absent"
producing exactly one documented skip and nothing else.

## Remaining user decision

None required to close this milestone — the only open licensing question
(who is the copyright holder) was already answered and applied. No other
blocking decision remains for this release-hardening milestone.

## Boundary statement

This is research software, not an approved production credit or
lifetime-loss model. Overall model acceptance remains qualified/pending a
human reviewer's intended-use decision (`docs/final_report.md`). Nothing
in this milestone changes that verdict, evaluates the model further, or
constitutes promotion, deployment or publication — this repository has
not been pushed or made public.
