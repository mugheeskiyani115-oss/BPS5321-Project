"""Ten-year outlook: national supply, woody feedstock, carbon-credit potential and credit-price scenarios.

Conventions (state them wherever these numbers are shown):
* Supply follows `forecast.project` (method chosen by backtest; flat unless the linear-trend method is picked).
* Credit potential = woody tonnes x registry credit per wet tonne for INDUSTRIAL pyrolysis: an UPPER BOUND that
  assumes all woody waste is pyrolysed and every tonne is certified. Eligibility is not established.
* Credit prices = Senken (Aug 2026) low / base / high biochar paths (nominal EUR), linearly interpolated between the
  published years 2026, 2030, 2035, 2040.
* Credit income is net of the Puro.earth per-credit fee and each plant's fixed certification cost.
* Plant costs, biochar price and FX are held flat (handoff convention); credit prices are nominal. Treat the
  discounted totals as indicative, not a valuation.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from . import forecast as fc
from . import network as nw
from . import pathway as pw
from .data import Bundle

CASES = ("low", "base", "high")


def credit_price_path(b: Bundle, years) -> pd.DataFrame:
    p = b.carbon_path.sort_values("year")
    years = np.asarray(years, float)
    if years.max() > p.year.max():
        raise ValueError(f"Credit price path only runs to {int(p.year.max())}")
    out = pd.DataFrame({"year": years.astype(int)})
    for c in CASES:
        out[f"{c}_eur"] = np.interp(years, p.year, p[f"{c}_eur"])
    return out


def supply_outlook(b: Bundle, a: pw.Assumptions, method: str = "naive_last", start: int = 2026, n_years: int = 10,
                   haul_km_per_t: float = 0.0, backtest_points: pd.DataFrame | None = None) -> pd.DataFrame:
    s = fc.national_series(b)
    proj = fc.project(s, method, to_year=start + n_years - 1, backtest_points=backtest_points)
    df = proj[proj.year >= start].rename(columns={"point_t": "central_t"})[["year", "p10_t", "central_t", "p90_t"]]
    credit = pw.carbon_per_wet_t(a, "industrial", haul_tkm_per_t=haul_km_per_t)["registry_credit"]
    for k in ("p10", "central", "p90"):
        df[f"woody_{k}_t"] = df[f"{k}_t"] * a.woody_share
        df[f"credit_potential_{k}_t"] = df[f"woody_{k}_t"] * credit
    df["collectable_woody_t"] = df.central_t * a.woody_share * a.collectable_share
    df = df.merge(credit_price_path(b, df.year), on="year")
    df["potential_value_base_sgd"] = df.credit_potential_central_t * (df.base_eur - a.puro_fee_eur_per_corc) * a.eur_sgd
    return df.reset_index(drop=True)


def plant_outlook(b: Bundle, a: pw.Assumptions, config: dict[str, str], supply: pd.DataFrame,
                  area_shares: np.ndarray, extra_sites: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """Year-by-year result of one hub configuration, without credits and with credits at each price case.

    Result = revenue - cost (capex as an annuity), S$/yr. Positive is a surplus.
    """
    if not config:
        raise ValueError("Choose at least one plant in Sites & network first")
    a0 = replace(a, credits_enabled=False)
    shares = np.asarray(area_shares, float) / np.sum(area_shares)
    rows = []
    for y in supply.itertuples():
        ay = replace(a0, national_t=float(y.central_t))
        r = nw.evaluate(nw.build_network(b, ay, shares * ay.national_t, extra_sites), config)
        credits = max(r["registry_credit_t"], 0.0)
        cert = r["n_sites"] * pw.cert_fixed_sgd_yr(a)
        row = {"year": y.year, "processed_t": r["processed_t"], "shortfall_t": r["shortfall_t"],
               "registry_credit_t": credits, "net_vs_current_t": r["net_climate_t"],
               "result_no_credits_sgd": -r["net_cost_sgd"], "cert_cost_sgd": cert,
               "break_even_credit_eur": ((r["net_cost_sgd"] + cert) / (credits * a.eur_sgd) + a.puro_fee_eur_per_corc
                                         if credits > 0 else np.inf)}
        for c in CASES:
            price = getattr(y, f"{c}_eur")
            row[f"credit_revenue_{c}_sgd"] = credits * (price - a.puro_fee_eur_per_corc) * a.eur_sgd - cert
            row[f"result_{c}_sgd"] = row["result_no_credits_sgd"] + row[f"credit_revenue_{c}_sgd"]
        rows.append(row)
    df = pd.DataFrame(rows)
    disc = (1 + a.discount_rate) ** -np.arange(1, len(df) + 1)
    pv = {k: float((df[f"result_{k}_sgd"] * disc).sum()) for k in ("no_credits", *CASES)}
    return df, pv
