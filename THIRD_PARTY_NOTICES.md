# Third-Party Notices

`LICENSE` (MIT) covers only the original source code, tests, SQL, scripts,
configuration and documentation authored in this repository (`src/`,
`tests/`, `sql/`, `scripts/`, `app/`, `configs/`, `docs/`, `README.md` and
related project files). It does not cover, and grants no rights to, the
third-party material described below. This file lists what that material
is, how this project uses it, and what is (and is not) redistributed in
this repository.

## Vendor data: Fannie Mae Single-Family Loan Performance Data

This project's analysis is built on Fannie Mae's publicly available
Single-Family Loan Performance dataset, obtained directly from Fannie Mae
under Fannie Mae's own data-access terms.

- **Not redistributed.** No vendor loan-performance data files are tracked
  in this repository. `data/raw/` is excluded via `.gitignore`, and no
  vendor CSV, Parquet or database file derived from it is committed. A
  clean checkout of this repository does not include any Fannie Mae data.
- **Field layout / glossary document.** `crt-file-layout-and-glossary.pdf`,
  Fannie Mae's own file-layout and glossary reference, is used locally to
  interpret raw column positions. It is explicitly excluded via
  `.gitignore` (both by name and by pattern) and is never committed or
  distributed by this repository.
- **Terms of use.** Any local use of the vendor dataset is governed
  entirely by Fannie Mae's own data-access terms, not by this repository's
  MIT license. Reproducing this project's real-data workflow requires
  independently obtaining the dataset from Fannie Mae and agreeing to
  those terms; see `docs/release_guide.md`.

## Vendor methodology: Fannie Mae's official R reference code

The realized-loss/workout reconciliation (`docs/redevelopment_plan.md`,
`docs/data_dictionary.md`) describes retrieving and reading Fannie Mae's
own official R reference implementation (`LPPUB_StatFile_Production.R`
and related files, retrieved via a public, unauthenticated Wayback Machine
snapshot of Fannie Mae's product page) in order to check this project's
own descriptive loss calculation against the vendor's published formula.

- **Not redistributed and not executed.** None of that R code is included,
  copied, translated or executed anywhere in this repository. This
  project's own Python implementation (`src/mortgage_risk/`) was written
  independently and checked against the vendor's plain-English methodology
  and formula as documentation, not by importing, running or transcribing
  the vendor's code.
- No license terms for that R code were reviewed or accepted as part of
  this project, because the code itself is not used, included or
  distributed here — only its publicly documented methodology was read for
  reconciliation purposes, with full provenance (URLs, retrieval dates,
  SHA-256 checksums) recorded in `docs/redevelopment_plan.md`.

## Third-party Python packages

This project depends on third-party, separately licensed open-source
Python packages, installed via `pip` from PyPI and pinned in
`requirements.lock` / `requirements-build.lock`. They are not vendored or
redistributed as source in this repository; each is covered by its own
upstream license, obtained by the end user through their own package
installation, and none of them is Fannie Mae material. Licenses below were
read directly from each installed package's own metadata
(`pip show` / installed distribution metadata), not assumed:

| Package | Role | Upstream license (from installed package metadata) |
|---|---|---|
| duckdb | Analytical SQL engine | MIT |
| PyYAML | Configuration parsing | MIT |
| scikit-learn | Modeling (benchmark/challenger) | BSD-3-Clause |
| numpy | Numerical arrays (scikit-learn dependency) | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (mixed; BSD-3-Clause for numpy's own code) |
| scipy | Numerical routines (scikit-learn dependency) | BSD |
| joblib | Parallel/caching utilities (scikit-learn dependency) | BSD-3-Clause |
| threadpoolctl | Thread-pool control (scikit-learn dependency) | BSD-3-Clause |
| cloudpickle | Serialization (scikit-learn dependency) | BSD-3-Clause |
| narwhals | DataFrame compatibility layer (scikit-learn dependency) | MIT |
| pytest | Test runner (development/test only) | MIT |
| iniconfig | pytest dependency (development/test only) | MIT |
| packaging | pytest dependency (development/test only) | Apache-2.0 OR BSD-2-Clause (dual-licensed) |
| pluggy | pytest dependency (development/test only) | MIT |
| pygments | pytest dependency (development/test only) | BSD-2-Clause |
| setuptools | Build backend (build-time only) | MIT |
| wheel | Build backend (build-time only) | MIT |

This table records what this project actually depends on and each
package's own published license identifier at the time of writing; it is
not a substitute for each package's own license text, which ships with
the package itself when installed and is not reproduced here. No license
terms have been altered, and no claim is made that MIT (this project's
own license) extends to any of these packages.

## No other embedded third-party material

The hand-authored reviewer presentation (`docs/reviewer_presentation.html`)
and local dashboard template (`app/dashboard.html`) were checked and
contain no embedded third-party fonts, scripts, stylesheets or other
copyrighted assets loaded from a CDN or vendored inline; both are original
work covered by `LICENSE`.

If you believe this file omits or misstates a third-party dependency or
attribution, open an issue rather than relying on this file alone as a
legal clearance record — it is a good-faith, project-authored notice, not
independent legal review.
