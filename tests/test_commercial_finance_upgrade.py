import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from biotwin.commercial_finance import apply_financial_scenario
from biotwin.finance_audit import audit_financial_result


def fixture(grant=0, tax=0):
    rows = [{"year": 0, "calendar_year": 2026, "tonnes": 0, "biochar_sales_sgd": 0,
        "gate_fees_sgd": 0, "credit_sales_sgd": 0, "staff_sgd": 0,
        "maintenance_sgd": 0, "land_sgd": 0, "electricity_sgd": 0,
        "trucking_sgd": 0, "certification_sgd": 0, "capital_sgd": 1000,
        "cash_flow_sgd": -1000, "cumulative_sgd": -1000, "discounted_sgd": -1000}]
    for t in range(1, 4):
        rows.append({"year": t, "calendar_year": 2026+t, "tonnes": 10, "biochar_sales_sgd": 180,
        "gate_fees_sgd": 100, "credit_sales_sgd": 70, "staff_sgd": 50,
        "maintenance_sgd": 20, "land_sgd": 10, "electricity_sgd": 10,
        "trucking_sgd": 10, "certification_sgd": 0, "capital_sgd": 0,
        "cash_flow_sgd": 250, "cumulative_sgd": -1000+250*t, "discounted_sgd": 250/(1.08**t)})
    d=pd.DataFrame(rows)
    pv_t=sum(10/(1.08**t) for t in range(1,4))
    lc=(1000+sum(100/(1.08**t) for t in range(1,4)))/pv_t
    npv=-1000+sum(250/(1.08**t) for t in range(1,4))
    pf={"capex_sgd":1000,"analysis_years":3,"discount_rate":.08,"npv_sgd":npv,
        "levelised_cost_sgd_per_t":lc,"break_even_gate_fee_sgd_per_t":0,
        "year1_cash_flow_sgd":250,"year2_cash_flow_sgd":250,"final_cash_flow_sgd":250,
        "years":d,"irr":None,"payback_year":None}
    a=SimpleNamespace(capital_grant_fraction=grant,illustrative_tax_rate=tax,gate_fee_sgd_per_t=10)
    return pf, a


def audit(pf):
    return audit_financial_result({"years":pf["years"].to_dict(orient="records"),
      "metrics":{k:pf[k] for k in ["capex_sgd","discount_rate","npv_sgd","levelised_cost_sgd_per_t"]}})


def test_original_model_still_reconciles_and_grant_zero_keeps_npv():
    pf,a=fixture(); new=apply_financial_scenario(pf,{},a)
    assert new['npv_sgd']==pytest.approx(pf['npv_sgd']); assert audit(new)['status']=='reconciled'
    assert new['commercial']['annual_non_cash_depreciation_sgd'] == pytest.approx(1000/3)


def test_grant_only_reduces_year_zero_outflow_and_increases_npv_same_amount():
    pf,a=fixture(grant=.2); new=apply_financial_scenario(pf,{},a)
    assert new['years'].iloc[0]['cash_flow_sgd']==-800
    assert new['npv_sgd']==pytest.approx(pf['npv_sgd']+200)
    assert new['levelised_cost_sgd_per_t']==pytest.approx(pf['levelised_cost_sgd_per_t'])
    assert audit(new)['status']=='reconciled'


def test_tax_is_cash_outflow_and_depreciation_not_a_cash_outflow():
    pf,a=fixture(grant=.25,tax=.17); new=apply_financial_scenario(pf,{},a)
    assert new['years'].iloc[1]['illustrative_tax_sgd'] == pytest.approx((250-1000/3)*.17 if 250 > 1000/3 else 0)
    assert new['years'].iloc[1]['cash_flow_sgd']==250
    assert new['years'].iloc[0]['cash_flow_sgd']==-750
    assert audit(new)['status']=='reconciled'


def test_tax_with_profit_positive_and_grant_reconciles():
    pf,a=fixture(grant=.1,tax=.17)
    pf['years'].loc[1:,'biochar_sales_sgd'] += 200
    pf['years'].loc[1:,'cash_flow_sgd'] += 200
    pf['years']['cumulative_sgd']=pf['years']['cash_flow_sgd'].cumsum()
    pf['npv_sgd'] += sum(200/(1.08**t) for t in range(1,4))
    new=apply_financial_scenario(pf,{},a)
    assert new['years'].iloc[1]['illustrative_tax_sgd'] > 0
    assert new['years'].iloc[1]['depreciation_non_cash_sgd'] > 0
    assert audit(new)['status']=='reconciled'


def test_wrong_original_cash_flow_is_rejected():
    pf,a=fixture(); pf['years'].loc[1,'cash_flow_sgd']=999
    with pytest.raises(ValueError,match='do not reconcile'):
        apply_financial_scenario(pf,{},a)
