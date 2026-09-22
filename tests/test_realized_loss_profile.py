import duckdb
from mortgage_risk.realized_loss_profile import NET_LOSS_SQL, COST_FIELDS, PROCEEDS_FIELDS, ALL_LOSS_FIELDS


def make_row_table(rows):
    c = duckdb.connect()
    columns = ['anchor_current_actual_upb'] + list(ALL_LOSS_FIELDS)
    c.execute(f"CREATE TABLE t({','.join(col + ' DECIMAL(18,2)' for col in columns)})")
    for row in rows:
        c.execute(f"INSERT INTO t VALUES ({','.join(str(row[col]) for col in columns)})")
    return c


def test_net_loss_formula_matches_hand_calculation():
    row = {
        'anchor_current_actual_upb': 100000,
        'foreclosure_costs': 2000, 'preservation_repair': 1500, 'asset_recovery_costs': 500,
        'holding_expenses_credits': 300, 'taxes': 700,
        'net_sales_proceeds': 80000, 'credit_enhancement_proceeds': 0,
        'repurchase_makewhole': 0, 'other_foreclosure_proceeds': 0,
    }
    c = make_row_table([row])
    result = c.execute(f'SELECT ({NET_LOSS_SQL}) FROM t').fetchone()[0]
    # 100000 + (2000+1500+500+300+700) - (80000+0+0+0) = 100000+5000-80000 = 25000
    assert result == 25000


def test_net_loss_can_be_negative_net_gain_and_is_not_clamped():
    row = {
        'anchor_current_actual_upb': 50000,
        'foreclosure_costs': 1000, 'preservation_repair': 0, 'asset_recovery_costs': 0,
        'holding_expenses_credits': 0, 'taxes': 0,
        'net_sales_proceeds': 60000, 'credit_enhancement_proceeds': 0,
        'repurchase_makewhole': 0, 'other_foreclosure_proceeds': 0,
    }
    c = make_row_table([row])
    result = c.execute(f'SELECT ({NET_LOSS_SQL}) FROM t').fetchone()[0]
    # 50000 + 1000 - 60000 = -9000, a net gain; must remain negative, not floored at zero.
    assert result == -9000


def test_net_loss_can_exceed_exposure_and_is_not_clamped():
    row = {
        'anchor_current_actual_upb': 20000,
        'foreclosure_costs': 5000, 'preservation_repair': 8000, 'asset_recovery_costs': 3000,
        'holding_expenses_credits': 2000, 'taxes': 1000,
        'net_sales_proceeds': 5000, 'credit_enhancement_proceeds': 0,
        'repurchase_makewhole': 0, 'other_foreclosure_proceeds': 0,
    }
    c = make_row_table([row])
    result = c.execute(f'SELECT ({NET_LOSS_SQL}) FROM t').fetchone()[0]
    # 20000 + 19000 - 5000 = 34000, which is more than the 20000 exposure; not capped at exposure.
    assert result == 34000
    assert result > row['anchor_current_actual_upb']


def test_negative_holding_expenses_credits_is_a_real_net_credit_not_an_error():
    # glossary field 57 explicitly combines expenses and credits (e.g. rental income, refunds),
    # so a negative value is a legitimate net credit and reduces net_loss, not a clamped value.
    row = {
        'anchor_current_actual_upb': 100000,
        'foreclosure_costs': 1000, 'preservation_repair': 0, 'asset_recovery_costs': 0,
        'holding_expenses_credits': -4000, 'taxes': 0,
        'net_sales_proceeds': 90000, 'credit_enhancement_proceeds': 0,
        'repurchase_makewhole': 0, 'other_foreclosure_proceeds': 0,
    }
    c = make_row_table([row])
    result = c.execute(f'SELECT ({NET_LOSS_SQL}) FROM t').fetchone()[0]
    # 100000 + (1000-4000) - 90000 = 7000
    assert result == 7000


def test_field_groups_are_disjoint_and_cover_all_nine_selected_fields():
    assert set(COST_FIELDS) & set(PROCEEDS_FIELDS) == set()
    assert len(COST_FIELDS) == 5 and len(PROCEEDS_FIELDS) == 4
    assert set(ALL_LOSS_FIELDS) == set(COST_FIELDS) | set(PROCEEDS_FIELDS)
