from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
from biotwin_core import Scenario, load_region_data, solve_plan, enumerate_plans, validate_operator_data

root = Path(__file__).resolve().parents[1]
regions = load_region_data(str(root / 'data/region_feedstock_2025.csv'))
origins = regions.rename(columns={'region':'origin_name'}).copy()


def test_national_mass_balance():
    assert regions.estimated_t.sum() == 232000
    assert regions.share_pct.sum() == pytest.approx(100)


def test_carbon_worked_case_reconciliation():
    cfg = Scenario(first_last_mile_km=0, road_distance_multiplier=0,
                   additional_hub_cost_sgd_per_year=0, transport_cost_sgd_per_tkm=0)
    p = solve_plan(origins, regions, ['Central'], cfg)
    assert p['annual_t'] == pytest.approx(9000)
    assert p['gross_stored_co2_t'] / p['annual_t'] == pytest.approx(0.372)
    assert p['net_climate_benefit_t'] / p['annual_t'] == pytest.approx(0.095)
    assert p['margin_sgd_per_t'] == pytest.approx(-218)
    assert p['assumed_credit_issued_t'] == 0
    assert p['break_even_gate_sgd_per_t'] == pytest.approx(218)


def test_flow_capacity_and_fair_throughput():
    cfg = Scenario()
    one = solve_plan(origins, regions, ['West'], cfg)
    three = solve_plan(origins, regions, ['Central', 'West','East'], cfg)
    for p in (one, three):
        assert p['flows'].tonnes.sum() == pytest.approx(cfg.annual_t, abs=.01)
        assert p['annual_t'] == cfg.annual_t
    assert three['flows'].groupby('hub').tonnes.sum().to_list() == pytest.approx([3000]*3, abs=.01)


def test_pareto_enumeration():
    tab, opts = enumerate_plans(origins, regions, Scenario())
    assert len(tab) == 31 == len(opts)
    assert tab.pareto.any()
    assert (tab.n_hubs >= 1).all()


def test_no_certification_claim_without_explicit_enable():
    cfg = Scenario(assumed_issued_credit_t_per_wet_t=.3, credit_price_sgd_per_tco2e=200)
    p = solve_plan(origins, regions, ['Central'], cfg)
    assert p['assumed_credit_issued_t'] == p['carbon_credit_revenue_sgd'] == 0


def test_actual_operator_data_required():
    empty = pd.DataFrame({'region':['Central'], 'year':[2025], 'observed_t':[float('nan')], 'source':['x']})
    with pytest.raises(ValueError): validate_operator_data(regions, empty)
    actual = pd.DataFrame({'region':['Central','West'], 'year':[2025,2025], 'observed_t':[70000,45000], 'source':['A','B']})
    result = validate_operator_data(regions, actual)
    assert result['compared'] == 2
    assert result['wape'] > 0
