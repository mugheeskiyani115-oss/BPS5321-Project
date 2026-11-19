"""Financial integrity and transparent seasonality for BioTwin Singapore.

No values are calibrated to produce a positive NPV. This module checks the
actual evaluated model output, and raises an error if numbers disagree.
Seasonal composition is an assumption-driven comparison, not observed
monthly waste, and does not silently alter annual facility dispatch.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

import numpy as np

CASH_REVENUE = ("biochar_sales_sgd", "gate_fees_sgd", "credit_sales_sgd")
CASH_OPEX = ("staff_sgd", "maintenance_sgd", "land_sgd", "electricity_sgd",
             "trucking_sgd", "certification_sgd")


def _number(row: dict, key: str) -> float:
    value = row.get(key, 0.0)
    if value is None:
        raise ValueError(f"Missing financial amount {key}")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"Invalid financial amount {key}")
    return number


def audit_financial_result(result: dict, tol: float = 0.10) -> dict[str, Any]:
    """Validate yearly cashflows, NPV and levelised lifecycle cost.

    Construction is a year-zero outflow. The subsequent yearly cash flows
    use cash OPEX only, not annualised capital, to avoid double counting.
    """
    years = result.get("years") or []
    metrics = result.get("metrics") or {}
    if len(years) < 2:
        raise ValueError("Financial report needs construction year and operating years")
    discount = _number(metrics, "discount_rate")
    capex = _number(metrics, "capex_sgd")
    if not 0 <= discount < 1 or capex < 0:
        raise ValueError("Out-of-range financial inputs")
    observed_cum = 0.0
    observed_npv = 0.0
    discounted_opex = 0.0
    discounted_t = 0.0
    max_gap = 0.0
    by_year = []
    for idx, year in enumerate(years):
        if int(year.get("year", idx)) != idx:
            raise ValueError("Financial schedule years must begin at 0 and increase consecutively")
        revenue = sum(_number(year, k) for k in CASH_REVENUE)
        opex = sum(_number(year, k) for k in CASH_OPEX)
        capital = _number(year, "capital_sgd")
        grant = _number(year, "grant_sgd")
        cash_tax = _number(year, "illustrative_tax_sgd")
        depreciation = _number(year, "depreciation_non_cash_sgd")
        if grant < -tol or cash_tax < -tol or depreciation < -tol:
            raise ValueError("Invalid grant, cash tax or depreciation")
        if idx > 0 and grant > tol:
            raise ValueError("Unexpected recurring grant; grant is modelled only in year zero")
        if idx == 0 and (cash_tax > tol or depreciation > tol):
            raise ValueError("Construction year cannot report depreciation or cash taxes")
        expected_cf = revenue - opex - capital + grant - cash_tax
        actual_cf = _number(year, "cash_flow_sgd")
        gap = abs(expected_cf - actual_cf)
        max_gap = max(max_gap, gap)
        if gap > tol + 1e-9 * abs(expected_cf):
            raise ValueError(f"Financial cashflow mismatch in year {idx}: {gap:,.2f} SGD")
        if idx == 0 and abs(capital - capex) > tol + 1e-9 * capex:
            raise ValueError("Year-zero CAPEX and reported investment differ")
        if idx > 0 and abs(capital) > tol:
            raise ValueError("Unexpected additional capital expenditure; update model if reinvestment is intended")
        if idx == 0 and (abs(revenue) > tol or abs(opex) > tol):
            raise ValueError("Construction year incorrectly reports operating revenue or cost")
        observed_cum += actual_cf
        reported_cumulative = _number(year, "cumulative_sgd")
        if abs(observed_cum - reported_cumulative) > tol + 1e-9 * abs(observed_cum):
            raise ValueError(f"Cumulative cash flow does not reconcile at year {idx}")
        factor = (1 + discount) ** idx
        observed_npv += actual_cf / factor
        if idx > 0:
            discounted_opex += opex / factor
            discounted_t += _number(year, "tonnes") / factor
        by_year.append({"calendar_year": year.get("calendar_year"), "revenue_sgd": revenue,
                        "cash_opex_sgd": opex, "capital_sgd": capital, "grant_sgd": grant, "cash_tax_sgd": cash_tax,
                        "non_cash_depreciation_sgd": depreciation, "cash_flow_sgd": actual_cf})
    npv_gap = abs(observed_npv - _number(metrics, "npv_sgd"))
    if npv_gap > tol + 1e-9 * abs(observed_npv):
        raise ValueError(f"NPV does not reconcile to yearly cash flows ({npv_gap:,.2f} SGD)")
    if discounted_t <= 0:
        raise ValueError("No discounted processed tonnage in financial evaluation")
    levelised = (capex + discounted_opex) / discounted_t
    cost_gap = abs(levelised - _number(metrics, "levelised_cost_sgd_per_t"))
    if cost_gap > 0.01:
        raise ValueError(f"Levelised lifecycle cost does not reconcile ({cost_gap:.3f} SGD/t)")
    return {"status": "reconciled", "max_annual_gap_sgd": round(max_gap, 6),
            "npv_gap_sgd": round(npv_gap, 6), "levelised_cost_gap_sgd_per_t": round(cost_gap, 6),
            "cost_definition": "discounted CAPEX plus discounted cash OPEX divided by discounted processed tonnes",
            "year2": by_year[2] if len(by_year) > 2 else by_year[1],
            "yearly": by_year}


def seasonal_composition(woody_mean: float, amplitude: float, national_t: float,
                         collectable_share: float, uncertainty_sd: float = 0.05) -> dict[str, Any]:
    """Assumption-driven monthly *composition*, not monthly observed generation.

    Nov/Dec/Jan woody fraction = annual mean - amplitude, other months =
    annual mean + amplitude/3. This conserves annual mean given equal months.
    No annual economic effect is inferred without storage and seasonal capacity
    dispatch model; this is a transparency/supply-risk sensitivity visualization.
    """
    if not (0 < woody_mean <= 1 and 0 <= amplitude <= .2 and 0 < collectable_share <= 1
            and 0 <= uncertainty_sd <= .15):
        raise ValueError("Out-of-range seasonal composition assumptions")
    monsoon = {11, 12, 1}
    dry_value = woody_mean + amplitude / 3
    wet_value = woody_mean - amplitude
    if wet_value < 0 or dry_value > 1:
        raise ValueError("Seasonal composition exceeds 0 to 100%")
    rng = np.random.default_rng(42)
    sampled_mean = np.clip(rng.normal(woody_mean, uncertainty_sd, size=500), 0.01, 0.99)
    rows = []
    for month in range(1, 13):
        share = wet_value if month in monsoon else dry_value
        sampled_month_share = np.clip(sampled_mean + (-amplitude if month in monsoon else amplitude / 3), 0, 1)
        sampled_month_available = national_t / 12 * collectable_share * sampled_month_share
        rows.append({"month": month, "monsoon": month in monsoon, "woody_share": round(share, 6),
                     "available_woody_t": round(national_t / 12 * share * collectable_share, 3),
                     "p10_woody_available_t": round(float(np.quantile(sampled_month_available, .10)), 3),
                     "p90_woody_available_t": round(float(np.quantile(sampled_month_available, .90)), 3)})
    return {"status": "assumption_sensitivity_not_measured", "mean_woody_share": woody_mean,
            "amplitude": amplitude, "uncertainty_sd": uncertainty_sd,
            "monte_carlo_draws": 500, "monte_carlo_seed": 42,
            "monthly_waste_basis": "flat national annual tonnage / 12 (assumed)",
            "changes_annual_finance": False, "months": rows,
            "interpretation": "500 hypothetical composition draws produce P10/P90 supply ranges. Neither these intervals nor the seasonal pattern are observed; annual project finance is not silently changed."}
