# SYNTH-A/B/C/D/E below are synthetic labels standing in for real 2010Q1 loans that were
# hand-traced during development to motivate specific test cases (see docs/redevelopment_plan.md).
# The actual vendor loan identifiers and their full histories are retained only in the private,
# gitignored artifacts/runs/ audit evidence, never published; every row fixture in this file is
# fabricated synthetic data, not a copy of any vendor record.
from datetime import date
import pytest
from mortgage_risk.loss_workout_linkage import classify_episode

PANEL_MAX = date(2026, 3, 1)


def row(month, dq, code, event=None):
    return {'reporting_month': date(2020, month, 1) if month <= 12 else date(2021, month - 12, 1),
            'delinquency_status': dq, 'zero_balance_code': code, 'candidate_event': event}


def test_immediate_disposition_at_anchor():
    rows = [row(1, '05', '09', 'default_proxy')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'disposed_credit_exit'
    assert result['resolution_month'] == date(2020, 1, 1)
    assert result['cure_count'] == 0 and result['redefault_count'] == 0


def test_delayed_disposition_after_further_delinquency():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '04', None), row(3, '05', '03')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'disposed_credit_exit'
    assert result['resolution_month'] == date(2020, 3, 1)


def test_payoff_after_default():
    rows = [row(1, '04', None, 'default_proxy'), row(2, '05', None), row(3, None, '01')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'payoff_or_maturity_after_default'
    assert result['resolution_month'] == date(2020, 3, 1)


def test_other_exit_after_default_is_a_stop_but_left_unresolved_as_to_loss():
    rows = [row(1, '03', None, 'default_proxy'), row(2, None, '06')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'other_exit_after_default'
    assert result['resolution_month'] == date(2020, 2, 1)


def test_unsupported_code_after_default_is_flagged_not_silently_dropped():
    rows = [row(1, '03', None, 'default_proxy'), row(2, None, 'ZZ')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'unsupported_code_after_default'


# --- Gaps are a continuity flag, not a stopping condition (real cohort pattern: loan
# SYNTH-D hits a gap, keeps defaulting, and only resolves three months later). ---

def test_gap_does_not_stop_the_scan_loan_resolves_after_the_gap():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '04', None),
            row(6, '18', None, 'gap_censor'), row(7, '19', None), row(8, None, '06')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'other_exit_after_default'
    assert result['resolution_month'] == date(2020, 8, 1)
    assert result['had_gap'] is True


def test_gap_row_still_evaluated_for_its_own_terminal_code():
    # loan SYNTH-E: the gap row itself carries a disposition code and unknown delinquency.
    rows = [row(1, '03', None, 'default_proxy'), row(2, 'XX', '03', 'gap_censor')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'disposed_credit_exit'
    assert result['had_gap'] is True


def test_unresolved_with_no_gap_and_data_stops_is_incomplete_followup_not_gap():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '04', None)]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'still_delinquent_incomplete_followup'
    assert result['had_gap'] is False


# --- Cure / redefault cycles are followed to the true final resolution, not stopped at the
# first redefault (real cohort pattern: loan SYNTH-A cures, redefaults, hits a gap,
# cures again, and only then reaches other_exit). ---

def test_cured_no_redefault_at_data_end():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '01', None), row(3, '00', None)]
    result = classify_episode(rows, date(2020, 3, 1))
    assert result['category'] == 'cured_no_redefault_at_data_end'
    assert result['resolution_month'] is None
    assert result['cure_count'] == 1 and result['redefault_count'] == 0


def test_cured_no_redefault_incomplete_followup_when_data_stops_early():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '01', None)]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'cured_no_redefault_incomplete_followup'


def test_single_redefault_still_not_terminal_continues_to_true_resolution():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '01', None), row(3, '00', None), row(4, '03', None)]
    result = classify_episode(rows, PANEL_MAX)
    # unlike v1, a redefault with no further data is 'still_delinquent', not a standalone
    # 'cured_then_redefault' terminal bucket; the path preserves that a redefault occurred.
    assert result['category'] == 'still_delinquent_incomplete_followup'
    assert result['cure_count'] == 1 and result['redefault_count'] == 1
    assert any(p['kind'] == 'redefault' for p in result['path'])


def test_two_cure_cycles_a_gap_and_a_terminal_other_exit_all_followed_to_the_end():
    # a compressed version of the real loan SYNTH-A trajectory.
    rows = [
        row(1, '03', None, 'default_proxy'),   # anchor, delinquent
        row(2, '00', None),                     # cure 1
        row(3, '03', None),                     # redefault 1
        row(7, '20', None, 'gap_censor'),        # gap, still delinquent
        row(8, '00', None),                     # cure 2
        row(9, None, '16'),                      # terminal other-exit
    ]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'other_exit_after_default'
    assert result['cure_count'] == 2 and result['redefault_count'] == 1
    assert result['had_gap'] is True
    kinds = [p['kind'] for p in result['path']]
    assert kinds == ['cure', 'redefault', 'gap', 'cure', 'other_exit_after_default']


def test_cure_then_redefault_then_disposition_resolves_as_disposition():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '00', None), row(3, '03', None), row(4, '05', '09')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'disposed_credit_exit'
    assert result['cure_count'] == 1 and result['redefault_count'] == 1


def test_still_delinquent_at_data_end():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '05', None)]
    result = classify_episode(rows, date(2020, 2, 1))
    assert result['category'] == 'still_delinquent_at_data_end'


def test_unknown_status_unresolved_split_by_data_end():
    rows_at_end = [row(1, 'XX', None, 'default_proxy')]
    rows_early = [row(1, 'XX', None, 'default_proxy')]
    assert classify_episode(rows_at_end, date(2020, 1, 1))['category'] == 'unknown_status_at_data_end'
    assert classify_episode(rows_early, PANEL_MAX)['category'] == 'unknown_status_incomplete_followup'


def test_empty_rows_raise_instead_of_silently_returning():
    with pytest.raises(ValueError):
        classify_episode([], PANEL_MAX)


# --- Ambiguous same-month conflicts (payoff/other-exit code with delinquency>=3 in the same
# row) are never resolved by code priority; they are their own state. Both real cohort examples
# (loans SYNTH-B and SYNTH-C) show climbing delinquency with a payoff code on the very
# last available row. ---

def test_ambiguous_same_month_is_not_resolved_as_payoff():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '04', None), row(3, '05', None),
            row(4, '06', None), row(5, '07', '01', 'ambiguous_same_month')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'ambiguous_unresolved_incomplete_followup'
    assert result['resolution_month'] is None


def test_ambiguous_same_month_at_data_end_is_distinguished_from_incomplete_followup():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '09', '01', 'ambiguous_same_month')]
    result = classify_episode(rows, date(2020, 2, 1))
    assert result['category'] == 'ambiguous_unresolved_at_data_end'


def test_ambiguous_same_month_can_still_be_resolved_by_a_later_clean_row():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '05', '06', 'ambiguous_same_month'), row(3, None, '09')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'disposed_credit_exit'
    assert result['ambiguous_count'] == 1


def test_ambiguous_same_month_followed_by_clean_cure_is_not_treated_as_redefault_later():
    rows = [row(1, '03', None, 'default_proxy'), row(2, '05', '06', 'ambiguous_same_month'),
            row(3, '00', None), row(4, '03', None)]
    result = classify_episode(rows, PANEL_MAX)
    # cure at month 3 is the first real cure (ambiguous never counted as cured or delinquent for
    # redefault-counting purposes), so month 4's return to delinquency is a genuine redefault.
    assert result['cure_count'] == 1
    assert result['redefault_count'] == 1


def test_disposition_always_wins_even_with_unknown_delinquency_and_no_ambiguous_flag():
    # disposition codes are never flagged ambiguous by the frozen event contract, regardless of
    # delinquency, matching loan SYNTH-E's real gap+disposition row.
    rows = [row(1, '03', None, 'default_proxy'), row(2, 'XX', '03')]
    result = classify_episode(rows, PANEL_MAX)
    assert result['category'] == 'disposed_credit_exit'
