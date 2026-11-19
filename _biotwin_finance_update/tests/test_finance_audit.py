"""No site data or Internet required: integrity tests for evaluated financial outputs."""
import copy
import math
import pathlib
import sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from biotwin.finance_audit import audit_financial_result, seasonal_composition


def sample():
    # The same variable structure as the FastAPI /api/evaluate result.
    years=[]; cumul=0
    for i in range(4):
        revenue=0 if i==0 else 1_000_000+100_000*(i-1)
        opex=0 if i==0 else 900_000+25_000*(i-1)
        capex=2_000_000 if i==0 else 0
        cash=revenue-opex-capex
        cumul+=cash
        row={"year":i,"calendar_year":2026+i,"tonnes":0 if i==0 else 10000,
            "biochar_sales_sgd":revenue,"gate_fees_sgd":0,"credit_sales_sgd":0,
            "staff_sgd":opex,"maintenance_sgd":0,"land_sgd":0,"electricity_sgd":0,
            "trucking_sgd":0,"certification_sgd":0,"capital_sgd":capex,
            "cash_flow_sgd":cash,"cumulative_sgd":cumul}
        years.append(row)
    rate=.08
    npv=sum(y["cash_flow_sgd"]/(1+rate)**i for i,y in enumerate(years))
    pv_costs=sum(y["staff_sgd"]/(1+rate)**i for i,y in enumerate(years) if i)
    pv_t=sum(y["tonnes"]/(1+rate)**i for i,y in enumerate(years) if i)
    return {"years":years,"metrics":{"discount_rate":rate,"capex_sgd":2_000_000,
          "npv_sgd":npv,"levelised_cost_sgd_per_t":(2_000_000+pv_costs)/pv_t}}


def test_accounting_valid():
    z=audit_financial_result(sample())
    assert z["status"]=="reconciled"
    assert z["max_annual_gap_sgd"]==0
    assert z["year2"]["revenue_sgd"]==1_100_000
    assert z["year2"]["cash_opex_sgd"]==925_000
    assert z["year2"]["cash_flow_sgd"]==175_000


def test_cashflow_contradiction_rejected():
    r=sample();r["years"][1]["cash_flow_sgd"]=-200_000
    with pytest.raises(ValueError,match="cashflow mismatch"):
        audit_financial_result(r)


def test_wrong_npv_rejected():
    r=sample();r["metrics"]["npv_sgd"]+=500_000
    with pytest.raises(ValueError,match="NPV does not reconcile"):
        audit_financial_result(r)


def test_wrong_levelised_cost_rejected():
    r=sample();r["metrics"]["levelised_cost_sgd_per_t"]+=50
    with pytest.raises(ValueError,match="Levelised lifecycle cost"):
        audit_financial_result(r)


def test_annual_vs_monthly_composition():
    s=seasonal_composition(.75,.1125,232000,.25)
    assert all(math.isclose(m["woody_share"],.6375,abs_tol=1e-7) for m in s["months"] if m["monsoon"])
    assert all(math.isclose(m["woody_share"],.7875,abs_tol=1e-7) for m in s["months"] if not m["monsoon"])
    assert math.isclose(sum(m["woody_share"] for m in s["months"])/12,.75,abs_tol=1e-7)
    assert s["changes_annual_finance"] is False


def test_monthly_overflow_rejected():
    with pytest.raises(ValueError):
        seasonal_composition(.99,.2,232000,.25)
