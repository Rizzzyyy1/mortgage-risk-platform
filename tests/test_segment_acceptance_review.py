import json
import duckdb
import pytest
from mortgage_risk.segment_acceptance_review import run, oe_direction, ci_vs_band


def write_parquet(conn, rows, columns, path):
    conn.execute(f"CREATE TABLE t({','.join(c + ' VARCHAR' for c in columns)})")
    for row in rows:
        conn.execute(f"INSERT INTO t VALUES ({','.join('?' for _ in row)})", list(row))
    conn.execute(f"COPY t TO '{path}' (FORMAT PARQUET)")
    conn.execute('DROP TABLE t')


def build_fixture(tmp_path):
    conn = duckdb.connect()
    write_parquet(conn, [
        ('L1', '0.9', '0.05', '0.05', '0.1', '0.05', '0.85'),
        ('L2', '0.05', '0.9', '0.05', '0.1', '0.05', '0.85'),
        ('L3', '0.05', '0.9', '0.05', '0.1', '0.05', '0.85'),
        ('L4', '0.05', '0.9', '0.05', '0.1', '0.05', '0.85'),
    ], ['loan_id', 'candidate_default', 'candidate_payoff', 'candidate_event_free', 'benchmark_default', 'benchmark_payoff', 'benchmark_event_free'],
        tmp_path / 'predictions.parquet')
    write_parquet(conn, [
        ('L1', '0', '700', '80', 'P', 'C'),
        ('L2', '0', '700', '80', 'P', 'C'),
        ('L3', '2', '600', '80', 'P', 'C'),
        ('L4', '2', '600', '80', 'P', 'C'),
    ], ['loan_id', 'delinquency_months', 'borrower_fico', 'ltv', 'occupancy', 'purpose'], tmp_path / 'features.parquet')
    write_parquet(conn, [
        ('L1', 'default_proxy'),
        ('L2', 'observed_event_free_12m'),
        ('L3', 'default_proxy'),
        ('L4', 'default_proxy'),
    ], ['loan_id', 'outcome_12m'], tmp_path / 'labels.parquet')
    conn.close()
    from mortgage_risk.artifact_integrity import fingerprint
    frozen = {
        'status': 'evaluated_not_promoted',
        'features_sha256': fingerprint(tmp_path / 'features.parquet'),
        'labels_sha256': fingerprint(tmp_path / 'labels.parquet'),
        'coverage': {'total': 4, 'known': 4, 'unresolved': 0},
        'segments': [
            {'field': 'delinquency', 'value': '0|N', 'candidate': {'loans': 2, 'defaults': 1, 'expected_defaults': 0.95}},
            {'field': 'delinquency', 'value': '2|N', 'candidate': {'loans': 2, 'defaults': 2, 'expected_defaults': 0.1}},
        ],
    }
    (tmp_path / 'final_evaluation_result.json').write_text(json.dumps(frozen))
    return tmp_path


def test_run_reproduces_frozen_point_estimates_and_adds_bootstrap_intervals(tmp_path):
    fixture = build_fixture(tmp_path)
    result, out = run(tmp_path, eval_dir=fixture, features_path=fixture / 'features.parquet', labels_path=fixture / 'labels.parquet', reps=50)
    by_key = {(s['field'], s['value']): s for s in result['segments']}
    current = by_key[('delinquency', '0|N')]
    assert current['n'] == 2 and current['observed'] == 1 and current['observed_expected'] == pytest.approx(1 / 0.95, rel=1e-3)
    delinquent = by_key[('delinquency', '2|N')]
    assert delinquent['n'] == 2 and delinquent['observed'] == 2 and delinquent['observed_expected'] == pytest.approx(2 / 0.1, rel=1e-3)
    assert delinquent['within_frozen_aggregate_band_0.8_1.25'] is False
    assert 'oe_ci95' in current and len(current['oe_ci95']) == 2
    assert (out / 'segment_acceptance_review_result.json').exists()


def test_run_raises_if_supplied_features_do_not_match_the_frozen_hash(tmp_path):
    fixture = build_fixture(tmp_path)
    other = tmp_path / 'other_features.parquet'
    conn = duckdb.connect()
    write_parquet(conn, [('L1', '0', '700', '80', 'P', 'C')], ['loan_id', 'delinquency_months', 'borrower_fico', 'ltv', 'occupancy', 'purpose'], other)
    conn.close()
    with pytest.raises(ValueError, match='do not match the frozen'):
        run(tmp_path, eval_dir=fixture, features_path=other, labels_path=fixture / 'labels.parquet', reps=10)


def test_run_raises_if_recomputed_point_estimate_diverges_from_frozen_record(tmp_path):
    fixture = build_fixture(tmp_path)
    frozen = json.loads((fixture / 'final_evaluation_result.json').read_text())
    frozen['segments'][0]['candidate']['defaults'] = 999
    (fixture / 'final_evaluation_result.json').write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match='diverges from frozen record'):
        run(tmp_path, eval_dir=fixture, features_path=fixture / 'features.parquet', labels_path=fixture / 'labels.parquet', reps=10)


def test_run_labels_overprediction_and_underprediction_segments_correctly(tmp_path):
    # L1 (delinquency 0|N): predicted default probability 0.9, observed default -> O/E = 1/0.9 > 1 -> underprediction.
    # L3+L4 (delinquency 2|N): predicted 0.05 each, both observed default -> O/E = 2/0.1 > 1 -> underprediction.
    # Add an overpredicted group by inverting predictions in a second fixture instead of reusing build_fixture's numbers directly.
    fixture = build_fixture(tmp_path)
    result, _ = run(tmp_path, eval_dir=fixture, features_path=fixture / 'features.parquet', labels_path=fixture / 'labels.parquet', reps=50)
    by_key = {(s['field'], s['value']): s for s in result['segments']}
    # delinquency 0|N: 1 observed default vs 0.95 expected -> O/E > 1 -> underprediction (model predicted fewer defaults than happened)
    assert by_key[('delinquency', '0|N')]['oe_direction'] == 'underprediction'
    # delinquency 2|N: 2 observed defaults vs 0.1 expected -> O/E >> 1 -> underprediction
    assert by_key[('delinquency', '2|N')]['oe_direction'] == 'underprediction'


@pytest.mark.parametrize('oe,expected', [(0.5, 'overprediction'), (1.0, 'exact'), (1.5, 'underprediction'), (None, None)])
def test_oe_direction_boundary_cases(oe, expected):
    assert oe_direction(oe) == expected


@pytest.mark.parametrize('ci,expected', [
    ((0.675, 0.797), 'entirely_below'),   # both bounds below the floor
    ((1.217, 1.598), 'overlaps_ceiling'),  # lower bound inside the band, upper bound above the ceiling
    ((1.30, 1.60), 'entirely_above'),      # both bounds above the ceiling
    ((0.90, 1.10), 'entirely_within'),     # both bounds inside the band
    ((0.70, 0.90), 'overlaps_floor'),      # lower bound below the floor, upper bound inside the band
    ((0.70, 1.30), 'spans_band'),          # spans across the entire band on both sides
    (None, None),
])
def test_ci_vs_band_boundary_cases(ci, expected):
    assert ci_vs_band(ci) == expected


def test_ci_vs_band_exact_boundary_values_are_treated_as_inside():
    # A bound exactly equal to the floor/ceiling counts as inside the band, not outside it.
    assert ci_vs_band((0.8, 1.25)) == 'entirely_within'
