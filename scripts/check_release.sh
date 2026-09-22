#!/bin/sh
# Run from repository root after following docs/release_guide.md.
set -eu
PYTHON=${PYTHON:-.venv/bin/python}
"$PYTHON" -m pip check
"$PYTHON" -m pytest -q
review_dir=$(mktemp -d "${TMPDIR:-/tmp}/mortgage-review.XXXXXX")
"$PYTHON" -m mortgage_risk.demo --output "$review_dir/demo"
printf 'Synthetic review evidence: %s\n' "$review_dir/demo"
