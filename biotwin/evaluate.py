"""Evaluate one scenario: build plant(s) at chosen site(s) and report outputs, economics, carbon and findings.

Structure follows a REopt-style evaluation:
  inputs (region, sites, plant size, business inputs, advanced inputs with defaults)
  -> two cases: Business as usual (woody waste keeps going to biomass power / waste-to-energy) and Your plant
  -> economics over the analysis period (capital cost, yearly cash flow, NPV, payback, IRR, break-even gate fee)
  -> numbered findings generated from the numbers, plus site and size comparisons.
Cash flows are flat in real terms (no escalation), as in Notebook 2; all money is S$.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

import numpy as np
import pandas as pd

from . import network as nw
from . import pathway as pw
from .data import Bundle

REGIONS = ("Central", "East", "North", "North-East", "West")
ADVANCED = {   # editable advanced inputs: (Assumptions field, label, unit, min, max, step)
    "woody_share": ("Woody share of horticultural waste", "fraction", 0.5, 0.9, 0.05),
    "collectable_share": ("Share of woody waste a new plant can win", "fraction", 0.05, 1.0, 0.05),
    "biochar_price_usd": ("Biochar sale price", "US$/t biochar", 0.0, 1500.0, 10.0),
    "credit_price_eur": ("Carbon credit price", "€/t CO₂e", 0.0, 400.0, 5.0),
    "discount_rate": ("Discount rate", "per year", 0.0, 0.15, 0.01),
    "life_years": ("Analysis period (plant life)", "years", 5, 25, 1),
}


@dataclass(frozen=True)
class Scenario:
    sites: tuple[str, ...] = ()            # empty -> tool picks the best site in `region`
    size_class: str | None = None          # None -> tool picks the cheapest size for the site(s)
    region: str = "All"
    gate_fee_sgd_per_t: float = 0.0
    sell_credits: bool = False
    advanced: tuple = ()                   # ((field, value), ...) overrides of defaults
    name: str = ""

    def overrides(self) -> dict:
        return dict(self.advanced)


def assumptions(b: Bundle, sc: Scenario, target_t: float = 1.0) -> pw.Assumptions:
    over = sc.overrides()
    if "life_years" in over:
        over["life_years"] = int(over["life_years"])
    return pw.default_assumptions(b, target_t=target_t, gate_fee_sgd_per_t=sc.gate_fee_sgd_per_t,
                                  credits_enabled=sc.sell_credits, **over)


def region_sites(b: Bundle, region: str) -> list[str]:
    s = b.sites if region == "All" else b.sites[b.sites.region == region]
    return list(s.site_id)


def _capacity(b: Bundle, layout: dict) -> float:
    return float(sum(pw.annual_capacity_t(b.plants.loc[c]) for c in layout.values()))


def _eval_layout(b: Bundle, sc: Scenario, layout: dict, with_flows: bool = False) -> tuple[dict, nw.Network]:
    a = assumptions(b, sc, target_t=_capacity(b, layout))
    net = nw.build_network(b, a)
    return nw.evaluate(net, layout, with_flows=with_flows), net


def resolve(b: Bundle, sc: Scenario) -> dict[str, str]:
    """Turn 'let the tool choose' into a concrete layout (cheapest net cost per tonne at full load)."""
    sizes = [sc.size_class] if sc.size_class else list(b.plants.index)
    sites = list(sc.sites) if sc.sites else region_sites(b, sc.region)
    if not sites:
        raise ValueError(f"No candidate sites in region {sc.region}")
    if sc.sites:                                   # user's sites, same size at each
        best, best_cost = None, np.inf
        for size in sizes:
            ev, _ = _eval_layout(b, sc, {s: size for s in sites})
            if ev["processed_t"] > 0 and ev["net_cost_sgd_per_t"] < best_cost:
                best, best_cost = {s: size for s in sites}, ev["net_cost_sgd_per_t"]
        return best
    best, best_cost = None, np.inf                 # tool picks one site (and size)
    for size in sizes:
        for s in sites:
            ev, _ = _eval_layout(b, sc, {s: size})
            if ev["processed_t"] > 0 and ev["net_cost_sgd_per_t"] < best_cost:
                best, best_cost = {s: size}, ev["net_cost_sgd_per_t"]
    return best


# ----------------------------------------------------------------------------- finance
def annuity_factor(r: float, n: int) -> float:
    return n if r <= 0 else (1 - (1 + r) ** -n) / r


def irr_series(flows: np.ndarray) -> float | None:
    """Internal rate of return of a cash-flow series (year 0 first); None when it never turns positive."""
    flows = np.asarray(flows, float)
    if flows.sum() <= 0 or flows[0] >= 0:
        return None
    npv = lambda r: float(np.sum(flows / (1 + r) ** np.arange(len(flows))))
    lo, hi = -0.99, 1.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if npv(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


def irr(capex: float, cf: float, n: int) -> float | None:
    """IRR for a flat cash flow (kept for comparison and tests)."""
    return irr_series(np.concatenate([[-capex], np.full(n, cf)])) if cf > 0 and capex > 0 else None


def escalation(b: Bundle, n: int) -> pd.DataFrame:
    """Year-by-year indices: MAS inflation forecasts for prices, MOM-based wage growth, ramp-up, credit-price path."""
    from . import outlook as ol
    start = int(b.p("build_year"))
    known = {2026: b.p("inflation_2026"), 2027: b.p("inflation_2027")}
    years = np.arange(start + 1, start + n + 1)
    infl = np.array([known.get(int(y), b.p("inflation_long_run")) for y in years])
    path = b.carbon_path.sort_values("year")
    credit = np.interp(np.minimum(years, path.year.max()), path.year, path.base_eur)
    return pd.DataFrame({"year": np.arange(1, n + 1), "calendar_year": years, "inflation": infl,
                         "price_index": np.cumprod(1 + infl),
                         "wage_index": (1 + b.p("wage_growth")) ** np.arange(1, n + 1),
                         "utilisation": np.where(np.arange(1, n + 1) == 1, b.p("ramp_up_year1"), 1.0),
                         "credit_price_path_eur": credit, "credit_path_2026_eur": float(path.base_eur.iloc[0])})


def pro_forma(ev: dict, a: pw.Assumptions, b: Bundle | None = None) -> dict:
    """Nominal year-by-year cash flows. Year 0 = build. Each later year differs because of:
    first-year ramp-up, wages growing faster than prices (MOM), prices/power/land/trucking/gate fee following MAS
    inflation forecasts, and (if sold) credits following Senken's base price path."""
    from .data import load_bundle
    b = b or load_bundle()
    n, r = int(a.life_years), a.discount_rate
    esc = escalation(b, n)
    capex, t = ev["capex_total_sgd"], ev["processed_t"]
    u, p, w = esc.utilisation.to_numpy(), esc.price_index.to_numpy(), esc.wage_index.to_numpy()
    tonnes = t * u
    biochar = tonnes * a.biochar_yield * a.biochar_price_usd * a.usd_sgd * p
    gate = tonnes * a.gate_fee_sgd_per_t * p
    credit_per_t = ev["registry_credit_t"] / t if t else 0.0
    if a.credits_enabled and t:
        price = esc.credit_price_path_eur.to_numpy() * (a.credit_price_eur / esc.credit_path_2026_eur.iloc[0])
        credits = np.maximum(credit_per_t, 0) * tonnes * (price - a.puro_fee_eur_per_corc) * a.eur_sgd
        cert = np.full(n, ev["cert_sgd"]) * p
    else:
        price, credits, cert = esc.credit_price_path_eur.to_numpy(), np.zeros(n), np.zeros(n)
    staff = ev["labour_sgd"] * w
    maintenance = ev["maintenance_sgd"] * p
    land = ev["land_sgd"] * p
    electricity = ev["electricity_sgd"] * u * p
    trucking = ev["haul_cost_sgd"] * u * p
    revenue = biochar + gate + credits
    costs = staff + maintenance + land + electricity + trucking + cert
    cf = revenue - costs
    disc = (1 + r) ** -np.arange(1, n + 1)
    npv = -capex + float(np.sum(cf * disc))
    flows = np.concatenate([[-capex], cf])
    cum = np.cumsum(flows)
    payback = next((int(k) for k in range(1, n + 1) if cum[k] >= 0), None)
    gate_pv = float(np.sum(tonnes * p * disc))
    lcot = (capex + float(np.sum(costs * disc))) / float(np.sum(tonnes * disc)) if t else np.nan
    years = pd.DataFrame({
        "year": np.arange(0, n + 1), "calendar_year": np.concatenate([[esc.calendar_year.iloc[0] - 1], esc.calendar_year]),
        "utilisation": np.concatenate([[0.0], u]), "tonnes": np.concatenate([[0.0], tonnes]),
        "biochar_sales_sgd": np.concatenate([[0.0], biochar]), "gate_fees_sgd": np.concatenate([[0.0], gate]),
        "credit_sales_sgd": np.concatenate([[0.0], credits]), "credit_price_eur": np.concatenate([[price[0]], price]),
        "capital_sgd": np.concatenate([[capex], np.zeros(n)]), "staff_sgd": np.concatenate([[0.0], staff]),
        "maintenance_sgd": np.concatenate([[0.0], maintenance]), "land_sgd": np.concatenate([[0.0], land]),
        "electricity_sgd": np.concatenate([[0.0], electricity]), "trucking_sgd": np.concatenate([[0.0], trucking]),
        "certification_sgd": np.concatenate([[0.0], cert]), "cash_flow_sgd": flows, "cumulative_sgd": cum,
        "discounted_sgd": flows * np.concatenate([[1.0], disc])})
    return {"capex_sgd": capex, "npv_sgd": npv, "payback_year": payback, "irr": irr_series(flows),
            "analysis_years": n, "discount_rate": r, "levelised_cost_sgd_per_t": lcot,
            "break_even_gate_fee_sgd_per_t": max(a.gate_fee_sgd_per_t - npv / gate_pv, 0.0) if gate_pv else np.nan,
            "year1_cash_flow_sgd": float(cf[0]), "year2_cash_flow_sgd": float(cf[min(1, n - 1)]),
            "final_cash_flow_sgd": float(cf[-1]), "years": years,
            "drivers": {"ramp_up_year1": float(u[0]), "wage_growth": b.p("wage_growth"),
                        "inflation_2027": b.p("inflation_2027"), "inflation_long_run": b.p("inflation_long_run"),
                        "credit_price_first_eur": float(price[0]), "credit_price_last_eur": float(price[-1]),
                        "first_year": int(esc.calendar_year.iloc[0]), "last_year": int(esc.calendar_year.iloc[-1])}}


# ----------------------------------------------------------------------------- business as usual
def business_as_usual(b: Bundle, net: nw.Network, ev: dict, a: pw.Assumptions) -> dict:
    """Today's fate of the same tonnes: trucked to the nearest existing waste-to-energy / biomass facility and burned
    for power. Biomass power plants are not mapped in OSM, so mapped WtE plants and Gardens by the Bay stand in."""
    t = ev["processed_t"]
    fac = b.facilities[~b.facilities.name.str.contains("Nexus", case=False)] if len(b.facilities) else b.facilities
    km = 0.0
    if t and b.roads is not None and len(fac) and len(ev.get("flows", [])):
        r = b.roads[b.roads.destination.isin(set(fac.name))]
        nearest = r.groupby("origin").road_km.min()
        f = ev["flows"]
        km = float((f.tonnes * f.origin.map(nearest).fillna(f.road_km)).sum())
    return {"processed_t": t, "tonne_km": km, "mean_haul_km": km / t if t else 0.0,
            "avoided_t": t * a.baseline_avoided, "biochar_t": 0.0, "staff_fte": 0.0,
            "destination": "Biomass power / waste-to-energy (burned)"}


# ----------------------------------------------------------------------------- comparisons
def site_comparison(b: Bundle, sc: Scenario, size: str) -> pd.DataFrame:
    rows = []
    for s in b.sites.itertuples():
        ev, _ = _eval_layout(b, sc, {s.site_id: size})
        rows.append({"site_id": s.site_id, "name": s.name, "region": s.region,
                     "rent_sgd_m2": s.rent_sgd_m2_yr_with_gst, "net_cost_sgd_per_t": ev["net_cost_sgd_per_t"],
                     "mean_haul_km": ev["mean_haul_km"], "credit_t": ev["registry_credit_t"]})
    return pd.DataFrame(rows).sort_values("net_cost_sgd_per_t").reset_index(drop=True)


def size_comparison(b: Bundle, sc: Scenario, sites: list[str]) -> pd.DataFrame:
    rows = []
    for size, p in b.plants.iterrows():
        ev, _ = _eval_layout(b, sc, {s: size for s in sites})
        if ev["processed_t"] <= 0:
            continue
        rows.append({"size_class": size, "label": p["label"], "processed_t": ev["processed_t"],
                     "net_cost_sgd_per_t": ev["net_cost_sgd_per_t"], "capex_sgd": ev["capex_total_sgd"],
                     "staff_fte": ev["staff_fte"], "credit_t": ev["registry_credit_t"]})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- findings
def _m(x: float) -> str:
    """S$ amount for prose: '−S$28.7 million', 'S$574,281'."""
    sign, v = ("−" if x < 0 else ""), abs(x)
    return f"{sign}S${v / 1e6:,.1f} million" if v >= 1e6 else f"{sign}S${v:,.0f}"


def _n(x: float) -> str:
    return f"{x:+,.0f}".replace("-", "−")


def findings(b: Bundle, sc: Scenario, ev: dict, pf: dict, bau: dict, sites_df: pd.DataFrame, sizes_df: pd.DataFrame,
             a: pw.Assumptions, layout: dict, net: nw.Network) -> list[dict]:
    t = ev["processed_t"]
    out = []
    woody_avail = net.total_supply_t
    out.append({"title": "Expected output",
                "text": f"Processes {t:,.0f} t of woody waste a year into {ev['biochar_t']:,.0f} t of biochar — "
                        f"{100 * t / woody_avail:.0f}% of the woody waste a new operator could realistically win "
                        f"({woody_avail:,.0f} t)." + ("" if ev["feasible"] else
                        f" Supply is {ev['shortfall_t']:,.0f} t short of the plant's capacity.")})
    f = ev["flows"].sort_values("tonnes", ascending=False)
    cum = f.sort_values("road_km").assign(c=lambda d: d.tonnes.cumsum() / d.tonnes.sum())
    k80 = float(cum.road_km[cum.c >= 0.8].iloc[0]) if len(cum) else 0.0
    top = ", ".join(f"{o.title()} ({v:,.0f} t)" for o, v in f.groupby("origin").tonnes.sum()
                    .sort_values(ascending=False).head(3).items())
    out.append({"title": "Where the waste comes from",
                "text": f"Draws on {f.origin.nunique()} planning areas; 80% of tonnes travel under {k80:.0f} km. "
                        f"Largest suppliers: {top}. Average trip {ev['mean_haul_km']:.1f} km, trucking "
                        f"S${ev['haul_cost_sgd'] / t:,.0f} per tonne."})
    items = {"staff": ev["labour_sgd"], "capital": ev["capex_annual_sgd"], "maintenance": ev["maintenance_sgd"],
             "trucking": ev["haul_cost_sgd"], "land": ev["land_sgd"], "electricity": ev["electricity_sgd"]}
    tot = sum(items.values())
    drivers = sorted(items.items(), key=lambda kv: -kv[1])[:2]
    out.append({"title": "What drives the cost",
                "text": f"Levelised cost S${pf['levelised_cost_sgd_per_t']:,.0f} per tonne. Biggest items: "
                        + " and ".join(f"{k} ({100 * v / tot:.0f}%)" for k, v in drivers)
                        + f". {ev['staff_fte']:.0f} staff at MOM 2025 wages."})
    d = pf["drivers"]
    trend = ("widens" if pf["final_cash_flow_sgd"] < pf["year2_cash_flow_sgd"] else "narrows")
    if pf["payback_year"]:
        econ = f"It pays back in year {pf['payback_year']}."
    else:
        econ = (f"Year 1 (at {100 * d['ramp_up_year1']:.0f}% output) is {_m(pf['year1_cash_flow_sgd'])}; year 2 is "
                f"{_m(pf['year2_cash_flow_sgd'])}, and the gap {trend} to {_m(pf['final_cash_flow_sgd'])} by "
                f"{d['last_year']} as staff costs rise {100 * d['wage_growth']:.1f}% a year against "
                f"{100 * d['inflation_long_run']:.0f}% price inflation. It never pays back.")
    out.append({"title": f"Economics over {pf['analysis_years']} years",
                "text": f"Capital cost {_m(pf['capex_sgd'])}. {econ} Net present value at "
                        f"{100 * pf['discount_rate']:.0f}%: {_m(pf['npv_sgd'])}."})
    cap = b.p("gate_fee_cap_sgd")
    gap = pf["break_even_gate_fee_sgd_per_t"] - cap
    out.append({"title": "Is it viable?",
                "text": (f"Breaks even with a gate fee of S${pf['break_even_gate_fee_sgd_per_t']:,.0f} per tonne. "
                         f"Incineration costs waste owners S${cap:,.2f} (NEA, excl. GST), so "
                         + (f"the plant needs about S${gap:,.0f} per tonne more than owners pay today."
                            if gap > 0 else "the plant can compete with incineration on price."))})
    net_c = ev["registry_credit_t"] - bau["avoided_t"]
    out.append({"title": "Carbon",
                "text": f"Stores {ev['stored_co2_t']:,.0f} t CO₂e a year; a registry could issue about "
                        f"{ev['registry_credit_t']:,.0f} t of credits. Burning the same waste for power already "
                        f"avoids {bau['avoided_t']:,.0f} t, so the change versus today is {_n(net_c)} t CO₂e a year."})
    if len(layout) == 1:
        sid, size = next(iter(layout.items()))
        rank = int(sites_df.index[sites_df.site_id == sid][0]) + 1
        best = sites_df.iloc[0]
        mine = sites_df[sites_df.site_id == sid].iloc[0]
        rent_rank = int(b.sites.rent_sgd_m2_yr_with_gst.rank(method="min")[b.sites.site_id == sid].iloc[0])
        site_txt = (f"Ranks #{rank} of {len(sites_df)} candidate plots for a {b.plants.loc[size, 'label']}."
                    + ("" if rank == 1 else f" The cheapest is {best['name']} at S${best.net_cost_sgd_per_t:,.0f}/t "
                       f"({100 * (mine.net_cost_sgd_per_t / best.net_cost_sgd_per_t - 1):.1f}% less).")
                    + f" Land here is S${mine.rent_sgd_m2:,.2f}/m² a year ({rent_rank}"
                      f"{'st' if rent_rank == 1 else 'nd' if rent_rank == 2 else 'rd' if rent_rank == 3 else 'th'}"
                      " cheapest of 10).")
        out.append({"title": "How this site compares", "text": site_txt})
    if len(sizes_df):
        bs = sizes_df.loc[sizes_df.net_cost_sgd_per_t.idxmin()]
        mine_size = next(iter(layout.values()))
        mine_row = sizes_df[sizes_df.size_class == mine_size]
        if len(mine_row):
            diff = 100 * (mine_row.net_cost_sgd_per_t.iloc[0] / bs.net_cost_sgd_per_t - 1)
            where = "this site" if len(layout) == 1 else f"these {len(layout)} sites"
            limited = (f" ({bs.processed_t:,.0f} t/yr — limited by available supply)"
                       if bs.processed_t < _capacity(b, {s: bs.size_class for s in layout}) - 1 else "")
            out.append({"title": "Plant size",
                        "text": (f"At {where}, {bs.label} gives the lowest net cost: S${bs.net_cost_sgd_per_t:,.0f} per "
                                 f"tonne after income{limited}."
                                 + ("" if mine_size == bs.size_class else
                                    f" Your choice costs {diff:+.0f}% more per tonne.")
                                 + " Bigger plants spread staff costs over more tonnes.")})
    a_cred = replace(a, credits_enabled=True)
    margin = max(ev["registry_credit_t"], 0) * pw.credit_margin_sgd(a_cred) - len(layout) * pw.cert_fixed_sgd_yr(a_cred)
    out.append({"title": "Carbon credits",
                "text": (f"{'Selling credits adds' if sc.sell_credits else 'If sold, credits would add'} about {_m(margin)} a year "
                         f"after registry and verification fees at €{a.credit_price_eur:,.0f}/t. Eligibility is not "
                         "established.")})
    out.append({"title": "Data caveat",
                "text": "Waste by area is estimated from tree and greenery data: no public dataset breaks the "
                        "national total down. NParks and NEA hold the records needed to confirm it."})
    return out


# ----------------------------------------------------------------------------- run
def run(b: Bundle, sc: Scenario) -> dict:
    layout = resolve(b, sc)
    if not layout:
        raise ValueError("No feasible plant for these choices")
    ev, net = _eval_layout(b, sc, layout, with_flows=True)
    a = net.a
    pf = pro_forma(ev, a, b)
    bau = business_as_usual(b, net, ev, a)
    size = next(iter(layout.values()))
    sites_df = site_comparison(b, sc, size)
    sizes_df = size_comparison(b, sc, list(layout))
    return {"scenario": asdict(sc), "layout": layout, "eval": ev, "pro_forma": pf, "bau": bau,
            "sites": sites_df, "sizes": sizes_df, "assumptions": asdict(a), "supply_t": net.total_supply_t,
            "findings": findings(b, sc, ev, pf, bau, sites_df, sizes_df, a, layout, net)}


def summary_row(res: dict, b: Bundle) -> dict:
    ev, pf = res["eval"], res["pro_forma"]
    lay = res["layout"]
    return {"Plant": " + ".join(f"{b.plants.loc[c, 'label']} at {b.sites.set_index('site_id').name[s]}"
                                for s, c in lay.items()),
            "Waste processed (t/yr)": ev["processed_t"], "Biochar (t/yr)": ev["biochar_t"],
            "Capital cost (S$)": pf["capex_sgd"], "Year-2 cash flow (S$)": pf["year2_cash_flow_sgd"],
            "NPV (S$)": pf["npv_sgd"], "Levelised cost (S$/t)": pf["levelised_cost_sgd_per_t"],
            "Break-even gate fee (S$/t)": pf["break_even_gate_fee_sgd_per_t"],
            "Credits (t CO₂e/yr)": ev["registry_credit_t"],
            "Climate vs today (t CO₂e/yr)": ev["registry_credit_t"] - res["bau"]["avoided_t"],
            "Average trucking (km)": ev["mean_haul_km"], "Staff": ev["staff_fte"]}
