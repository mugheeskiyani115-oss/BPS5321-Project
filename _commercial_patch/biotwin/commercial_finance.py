"""Optional commercial finance scenarios built on BioTwin's original cashflow model.

Physical biochar revenue, gate fees and conditional credit revenue are ALREADY
calculated by the core model. This module does not add them again. It adds only
an OPTIONAL grant at financial close and an OPTIONAL simplified income tax
scenario. Depreciation is noncash and never replaces initial CAPEX.

This is for feasibility sensitivity, not investment, tax, grant or credit advice.
"""
from __future__ import annotations

from dataclasses import asdict
from math import isfinite

import numpy as np
import pandas as pd


REVENUE = ("biochar_sales_sgd", "gate_fees_sgd", "credit_sales_sgd")
OPEX = ("staff_sgd", "maintenance_sgd", "land_sgd", "electricity_sgd", "trucking_sgd", "certification_sgd")


def _fin(value: float, name: str) -> float:
    n = float(value)
    if not isfinite(n):
        raise ValueError(f"Non-finite {name}")
    return n


def _irr(flows: np.ndarray) -> float | None:
    flows = np.asarray(flows, dtype=float)
    if not len(flows) or flows[0] >= 0 or flows.sum() <= 0:
        return None
    def npv(rate):
        return float(np.sum(flows / (1 + rate) ** np.arange(len(flows))))
    lo, hi = -0.99, 1.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(110):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return float((lo + hi) / 2)


def apply_financial_scenario(pf: dict, ev: dict, a, b=None) -> dict:
    """Apply conditional grant and simple tax to an ORIGINAL validated pro forma.

    - Original cash revenues remain exactly as calculated by BioTwin.
    - Year 0 includes the full capital purchase AND any hypothetical awarded grant.
    - Tax applies to positive operating profit after illustrative straight-line
      depreciation; losses have no carryforward in this simplified sensitivity.
    - Reported levelised project cost uses GROSS capital expenditure and cash
      OPEX; it intentionally excludes grants and taxes to preserve comparison.
    """
    grant_share = _fin(getattr(a, "capital_grant_fraction", 0.0), "grant fraction")
    tax_rate = _fin(getattr(a, "illustrative_tax_rate", 0.0), "illustrative tax rate")
    if not (0 <= grant_share <= 0.5 and 0 <= tax_rate <= 0.25):
        raise ValueError("Grant/tax scenario out of range")
    out = pf.copy()
    y = pf["years"].copy(deep=True)
    if len(y) < 2 or list(y.year) != list(range(len(y))):
        raise ValueError("Invalid cashflow years")
    gross_capex = _fin(pf["capex_sgd"], "CAPEX")
    years = int(pf["analysis_years"])
    if len(y) != years + 1 or years < 1:
        raise ValueError("Cashflow and project life disagree")
    revenue = y[list(REVENUE)].astype(float).sum(axis=1).to_numpy()
    operating = y[list(OPEX)].astype(float).sum(axis=1).to_numpy()
    capital = y["capital_sgd"].astype(float).to_numpy()
    cf_before = revenue - operating - capital
    if not np.allclose(cf_before, y.cash_flow_sgd.to_numpy(float), rtol=1e-9, atol=0.10):
        raise ValueError("Original year-by-year cash flows do not reconcile; changes were not applied")
    if abs(capital[0] - gross_capex) > 0.10 or np.any(np.abs(capital[1:]) > 0.10):
        raise ValueError("Unexpected capital schedule; review grant treatment")
    grant = gross_capex * grant_share
    grant_series = np.zeros(len(y))
    grant_series[0] = grant
    depreciation = np.zeros(len(y))
    depreciation[1:] = gross_capex / years  # NONCASH illustration, NOT Singapore tax allowance advice
    taxable_profit = np.maximum(revenue - operating - depreciation, 0.0)
    tax_paid = taxable_profit * tax_rate
    tax_paid[0] = 0.0
    cf_new = cf_before + grant_series - tax_paid
    cumulative = np.cumsum(cf_new)
    disc = (1 + float(pf["discount_rate"])) ** np.arange(len(y))
    npv_new = float(np.sum(cf_new / disc))
    y["grant_sgd"] = grant_series
    y["depreciation_non_cash_sgd"] = depreciation
    y["illustrative_tax_sgd"] = tax_paid
    y["taxable_profit_sgd"] = taxable_profit
    y["cash_flow_sgd"] = cf_new
    y["cumulative_sgd"] = cumulative
    y["discounted_sgd"] = cf_new / disc
    payback = next((int(i) for i in range(1, len(y)) if cumulative[i] >= 0), None)
    out.update({"years": y, "npv_sgd": npv_new, "irr": _irr(cf_new), "payback_year": payback,
                "year1_cash_flow_sgd": float(cf_new[1]),
                "year2_cash_flow_sgd": float(cf_new[min(2, years)]),
                "final_cash_flow_sgd": float(cf_new[-1])})
    # Commercial break-even includes the actual project tax and grant assumptions;
    # price escalation reuses the model's original sequence.
    if b is not None:
        from .evaluate import escalation  # called after evaluate module is loaded
        idx = escalation(b, years).price_index.to_numpy(float)
    else:
        # Only for unit fixtures without a Bundle, not the production app.
        idx = np.ones(years)
    original_gate = float(getattr(a, "gate_fee_sgd_per_t", 0.0))
    cash_rev_nogate = revenue[1:] - y["gate_fees_sgd"].to_numpy(float)[1:]
    ops = operating[1:]
    tons = y["tonnes"].to_numpy(float)[1:]
    if not np.all(np.isfinite(idx)) or np.any(tons < 0):
        raise ValueError("Invalid gate fee price escalation or throughput")
    def npv_given_gate(g):
        rev = cash_rev_nogate + tons * g * idx
        taxable = np.maximum(rev - ops - depreciation[1:], 0.0)
        cash = rev - ops - taxable * tax_rate
        return -gross_capex + grant + float(np.sum(cash / disc[1:]))
    if npv_given_gate(0) >= 0:
        break_even = 0.0
    else:
        lo, hi = 0.0, max(500.0, original_gate, float(pf.get("break_even_gate_fee_sgd_per_t", 0)))
        for _ in range(30):
            if npv_given_gate(hi) >= 0:
                break
            hi *= 2
        else:
            raise ValueError("No gate fee break-even bracket found")
        for _ in range(80):
            mid = (lo + hi) / 2
            if npv_given_gate(mid) >= 0:
                hi = mid
            else:
                lo = mid
        break_even = hi
    out["break_even_gate_fee_sgd_per_t"] = float(break_even)
    out["commercial"] = {
        "gross_capex_sgd": gross_capex, "illustrative_grant_fraction": grant_share,
        "illustrative_grant_sgd": grant, "net_initial_cash_outlay_sgd": gross_capex - grant,
        "illustrative_tax_rate": tax_rate,
        "total_illustrative_cash_taxes_sgd": float(tax_paid.sum()),
        "annual_non_cash_depreciation_sgd": gross_capex / years,
        "baseline_project_npv_sgd": float(pf["npv_sgd"]),
        "after_scenario_npv_sgd": npv_new,
        "modelled_biochar_revenue_year2_sgd": float(y.iloc[min(2, years)].biochar_sales_sgd),
        "modelled_credit_revenue_year2_sgd": float(y.iloc[min(2, years)].credit_sales_sgd),
        "modelled_gate_fee_revenue_year2_sgd": float(y.iloc[min(2, years)].gate_fees_sgd),
        "calculation_note": "Original gross CAPEX remains in year zero; only a hypothetical grant is received in year zero. Depreciation is noncash and affects only illustrative tax; eligibility and tax treatment must be verified.",
        "credit_note": "Registry credit volume follows the existing LCA ledger, not 2.9 gross tCO2e per tonne of biochar. No issued credits or buyer contract is assumed.",
        "price_note": "Construction-grade biochar prices are unverified market scenarios; offtake and material specification are required.",
    }
    return out
