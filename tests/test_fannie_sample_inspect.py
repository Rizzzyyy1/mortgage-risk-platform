from datetime import date

from mortgage_risk import fannie_sample_inspect


def make_row(loan_id: str, reporting_period: str) -> list[str]:
    return ["", loan_id, reporting_period] + [""] * (108 - 3)


def test_parse_reporting_period_handles_year_boundary_and_invalids():
    assert fannie_sample_inspect.parse_reporting_period("122010") == (date(2010, 12, 1), None)
    assert fannie_sample_inspect.parse_reporting_period("012011") == (date(2011, 1, 1), None)
    assert fannie_sample_inspect.parse_reporting_period("201013") == (None, "invalid_reporting_period")
    assert fannie_sample_inspect.parse_reporting_period("") == (None, "missing_reporting_period")


def test_summarize_distinguishes_valid_and_invalid_periods(tmp_path):
    path = tmp_path / "sample.csv"
    rows = [
        make_row("L-1", "122010"),
        make_row("L-1", "012011"),
        make_row("L-2", "012011"),
        make_row("L-3", "201013"),
        make_row("L-3", "201013"),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write("|".join(row) + "\r\n")

    summary = fannie_sample_inspect.summarize(path)

    assert summary["record_count"] == 5
    assert summary["distinct_loan_count"] == 3
    assert summary["earliest_reporting_period_iso"] == "2010-12-01"
    assert summary["latest_reporting_period_iso"] == "2011-01-01"
    assert summary["distinct_month_count"] == 2
    assert summary["invalid_reporting_period_count"] == 2
    assert summary["duplicate_loan_month_keys"] == 1
    assert summary["conflicting_duplicate_loan_month_keys"] == 0
