"""BioTwin Quest: game rules on top of the planning model.

Game rules (budgets, star thresholds, XP) are design choices and are labelled as such in the UI. Every number the
player is scored on (costs, credits, haul, supply) comes from the model and its sourced parameters. Random "events"
in the decade run are draws from the model's own uncertainty ranges (forecast backtest errors, the woody-share
range, Senken's low-high credit-price band); nothing else is invented.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from . import forecast as fc
from . import network as nw
from . import optimise as op
from . import outlook as ol
from . import pathway as pw
from .data import DATA, Bundle

REFS_FILE = DATA / "game" / "mission_refs.json"


@dataclass(frozen=True)
class Mission:
    id: str
    icon: str
    title: str
    tagline: str
    brief: str
    objective: str            # cost | credits | pareto | decade
    target_t: float
    budget_sgd: float
    unlock_after: str | None


MISSIONS: dict[str, Mission] = {m.id: m for m in [
    Mission("first_spark", "🌱", "First Spark", "Your first plant",
            "Get a pilot running: process 2,000 wet tonnes of woody waste a year for the lowest net cost per tonne. "
            "Click a candidate site on the map, then build a plant.",
            "cost", 2_000, 4_000_000, None),
    Mission("city_loop", "🏙️", "City Loop", "Scale up for the whole island",
            "Process 9,000 t/yr — the team's reference throughput — at the lowest net cost per tonne. One big plant or "
            "several small ones? Labour, haulage and land rent all pull in different directions.",
            "cost", 9_000, 15_000_000, "first_spark"),
    Mission("carbon_captain", "🌍", "Carbon Captain", "Squeeze out every credit",
            "Process 9,000 t/yr and earn the most registry carbon credits. Small kilns lose about half the credit per "
            "tonne; long hauls burn diesel.",
            "credits", 9_000, 15_000_000, "city_loop"),
    Mission("beat_the_ai", "🤖", "Beat the AI", "Out-plan the optimiser",
            "The NSGA-II optimiser has mapped the best trade-offs between cost, carbon and haul distance. Build a "
            "layout it cannot beat on all three at once.",
            "pareto", 9_000, 15_000_000, "carbon_captain"),
    Mission("decade", "📅", "Decade Run", "Survive 2026–2035",
            "Run your 9,000 t/yr layout through ten simulated years: supply swings, leafy monsoon years and moving "
            "credit prices. Decide whether certifying and selling credits pays.",
            "decade", 9_000, 15_000_000, "beat_the_ai"),
]}

STAR_RULES = {   # game-design thresholds, shown to the player
    "cost": (1.05, 1.01), "credits": (0.97, 0.995), "pareto": (0.03, 0.0), "decade": (1.05, 1.01),
}

BADGES = {
    "groundbreaker": ("🏗️", "Groundbreaker", "Build your first plant"),
    "short_haul": ("🛣️", "Short Haul", "Finish a feasible layout with a mean haul under 6 km"),
    "heavy_industry": ("🏭", "Heavy Industry", "Run a 50 or 100 t/day continuous plant"),
    "kiln_collective": ("🔥", "Kiln Collective", "Run four or more small kilns at once"),
    "certified": ("📜", "Certified", "Sell credits and come out ahead after registry fees"),
    "monsoon_ready": ("🌧️", "Monsoon Ready", "Keep supply above demand in every month of the leafy season"),
    "ai_slayer": ("🤖", "AI Slayer", "Submit a layout the optimiser does not dominate"),
    "perfectionist": ("⭐", "Perfectionist", "Earn three stars in any mission"),
    "lean_build": ("💰", "Lean Build", "Earn a star using at most 60% of the budget"),
    "decade_survivor": ("📅", "Decade Survivor", "Complete a decade run with supply met every year"),
    "forecaster": ("📈", "Forecaster", "Open the supply forecast in the Lab"),
    "data_detective": ("🔎", "Data Detective", "Check the sources behind the numbers"),
}

LEVELS = [(0, "Sapling"), (300, "Arborist"), (800, "Kiln Keeper"), (1500, "Carbon Engineer"), (2500, "Biochar Baron"),
          (4000, "Climate Architect")]


# ----------------------------------------------------------------------------- model glue
def mission_assumptions(b: Bundle, m: Mission, sell_credits: bool = False, **over) -> pw.Assumptions:
    return pw.default_assumptions(b, target_t=m.target_t, credits_enabled=sell_credits, **over)


def evaluate_layout(b: Bundle, m: Mission, layout: dict[str, str], sell_credits: bool = False,
                    net: nw.Network | None = None, with_flows: bool = False) -> dict:
    a = mission_assumptions(b, m, sell_credits)
    net = net if net is not None else nw.build_network(b, a)
    ev = nw.evaluate(net, layout, with_flows=with_flows)
    ev["budget_sgd"] = m.budget_sgd
    ev["within_budget"] = ev["capex_total_sgd"] <= m.budget_sgd + 1e-6
    ev["valid"] = bool(ev["feasible"] and ev["within_budget"])
    return ev


def monthly_supply_ok(b: Bundle, m: Mission) -> bool:
    a = mission_assumptions(b, m)
    mc = fc.monthly_composition(a.woody_share, b.p("seasonal_woody_amplitude"))
    monthly = a.national_t / 12 * mc.woody_share * a.collectable_share
    return bool((monthly >= m.target_t / 12).all())


# ----------------------------------------------------------------------------- references (the "AI")
def compute_reference(b: Bundle, m: Mission, seeds=(1, 2), pop: int = 60, gens: int = 60) -> dict:
    """NSGA-II reference for a mission: cheapest layout, most credits, and the trade-off front."""
    a = mission_assumptions(b, m)
    net = nw.build_network(b, a)
    fronts = []
    for s in seeds:
        prob = op.Problem(net, tuple(b.plants.index), max_open=6, max_capex_sgd=m.budget_sgd)
        fronts.append(op.nsga2(prob, pop_size=pop, generations=gens, seed=s)["front"])
    f = pd.concat(fronts, ignore_index=True)
    f = f.drop_duplicates("genome")
    F = f[["net_cost_sgd", "net_climate_t", "mean_haul_km"]].to_numpy() * op.SENSE
    f = f[op.pareto_mask(F)].reset_index(drop=True)
    cheap = f.loc[f.net_cost_sgd_per_t.idxmin()]
    green = f.loc[f.registry_credit_t.idxmax()]
    # registry credit is not an NSGA objective; make sure the all-industrial, short-haul options are considered
    best_credit = float(green.registry_credit_t)
    best_credit_cfg = dict(green.config)
    for sc in [c for c in b.plants.index if b.plants.loc[c, "carbon_class"] == "industrial"]:
        for s in net.sites.site_id:
            r = nw.evaluate(net, {s: sc})
            if r["feasible"] and r["capex_total_sgd"] <= m.budget_sgd and r["registry_credit_t"] > best_credit:
                best_credit, best_credit_cfg = r["registry_credit_t"], {s: sc}
    return {
        "mission": m.id, "fingerprint": b.fingerprint, "target_t": m.target_t, "budget_sgd": m.budget_sgd,
        "best_cost_sgd_t": float(cheap.net_cost_sgd_per_t), "best_cost_layout": dict(cheap.config),
        "best_credit_t": best_credit, "best_credit_layout": best_credit_cfg,
        "front": f[["net_cost_sgd", "net_climate_t", "mean_haul_km"]].to_numpy().tolist(),
        "front_layouts": [dict(c) for c in f.config],
    }


def load_references(b: Bundle) -> dict | None:
    if not REFS_FILE.exists():
        return None
    refs = json.loads(REFS_FILE.read_text())
    if refs.get("fingerprint") != b.fingerprint:
        return None
    missions = refs.get("missions", {})
    for mid, m in MISSIONS.items():
        r = missions.get(mid)
        if r is None or r.get("target_t") != m.target_t or r.get("budget_sgd") != m.budget_sgd:
            return None
    return missions


def save_references(b: Bundle, refs: dict) -> Path:
    REFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REFS_FILE.write_text(json.dumps({"fingerprint": b.fingerprint, "missions": refs}, indent=1))
    return REFS_FILE


# ----------------------------------------------------------------------------- scoring
def pareto_gap(ev: dict, front: list[list[float]]) -> tuple[float, bool]:
    """Normalised distance from the layout to the AI front, and whether any front point dominates it."""
    F = np.asarray(front, float) * op.SENSE
    p = np.array([ev["net_cost_sgd"], ev["net_climate_t"], ev["mean_haul_km"]]) * op.SENSE
    span = np.maximum(F.max(axis=0) - F.min(axis=0), 1e-9)
    dominated = bool(np.any(np.all(F <= p + 1e-9, axis=1) & np.any(F < p - 1e-9, axis=1)))
    gap = np.maximum(p - F, 0) / span                 # how far each front point is better, per objective
    return float(np.min(np.linalg.norm(gap, axis=1))), dominated


def score(m: Mission, ev: dict, ref: dict, decade: dict | None = None) -> dict:
    checks = [("Meets the throughput target", ev["feasible"], f"{ev['processed_t']:,.0f} / {m.target_t:,.0f} t/yr"),
              ("Stays within the capital budget", ev["within_budget"],
               f"S${ev['capex_total_sgd'] / 1e6:,.2f}M / S${m.budget_sgd / 1e6:,.1f}M")]
    two, three = STAR_RULES[m.objective]
    value, s = 0.0, 0
    if m.objective == "cost":
        best, mine = ref["best_cost_sgd_t"], ev["net_cost_sgd_per_t"]
        ratio = mine / best if ev["valid"] else np.inf
        value = 1000 * min(best / mine, 1.0) if ev["valid"] else 0
        checks += [(f"Net cost within {100 * (two - 1):.0f}% of the AI's best (S${best:,.0f}/t)", ratio <= two,
                    f"S${mine:,.0f}/t" if ev["processed_t"] else "—"),
                   (f"Net cost within {100 * (three - 1):.0f}% of the AI's best", ratio <= three, "")]
    elif m.objective == "credits":
        best, mine = ref["best_credit_t"], ev["registry_credit_t"]
        ratio = mine / best if ev["valid"] and best > 0 else 0
        value = 1000 * min(ratio, 1.0)
        checks += [(f"At least {100 * two:.0f}% of the AI's best credits ({best:,.0f} tCO2e/yr)", ratio >= two,
                    f"{mine:,.0f} tCO2e/yr"),
                   (f"At least {100 * three:.1f}% of the AI's best credits", ratio >= three, "")]
    elif m.objective == "pareto":
        gap, dominated = pareto_gap(ev, ref["front"]) if ev["valid"] else (np.inf, True)
        value = 1000 * max(0.0, 1 - gap) if ev["valid"] else 0
        checks += [(f"Within {100 * two:.0f}% of the AI's trade-off front", gap <= two,
                    "on the front" if gap == 0 else f"gap {100 * gap:.1f}%" if np.isfinite(gap) else "—"),
                   ("Not beaten by the AI on all three objectives", ev["valid"] and not dominated, "")]
    elif m.objective == "decade":
        if decade is None:
            checks += [("Run the decade", False, "press ▶ Run the decade"), ("Beat the AI's decade result", False, "")]
        else:
            mine, refl = decade["pv_loss_sgd"], decade["ref_pv_loss_sgd"]
            ratio = mine / refl if refl > 0 else (1.0 if mine <= 0 else np.inf)
            value = 1000 * min(refl / mine, 1.0) if mine > 0 else 1000
            checks += [("Supply met in all ten years", decade["years_short"] == 0,
                        f"{10 - decade['years_short']}/10 years"),
                       (f"Ten-year loss within {100 * (three - 1):.0f}% of the AI layout on the same years",
                        ratio <= three, f"S${mine / 1e6:,.1f}M vs S${refl / 1e6:,.1f}M")]
    base = ev["valid"] and (m.objective != "decade" or decade is not None)
    if base:
        s = 1 + int(checks[2][1]) + int(checks[2][1] and checks[3][1])
    return {"score": int(round(value)) if base else 0, "stars": s if base else 0, "checks": checks}


def earned_badges(m: Mission, ev: dict, result: dict, sell_credits: bool, b: Bundle, ref: dict,
                  decade: dict | None = None) -> set[str]:
    got = set()
    sizes = list(ev["config"].values())
    if sizes:
        got.add("groundbreaker")
    if ev["valid"] and ev["mean_haul_km"] < 6:
        got.add("short_haul")
    if any(s in ("C50", "C100") for s in sizes):
        got.add("heavy_industry")
    if sum(b.plants.loc[s, "carbon_class"] == "small" for s in sizes) >= 4:
        got.add("kiln_collective")
    if sell_credits and ev["valid"] and ev["credit_revenue_sgd"] > ev["cert_sgd"]:
        got.add("certified")
    if ev["valid"] and monthly_supply_ok(b, m):
        got.add("monsoon_ready")
    if ev["valid"] and ref.get("front"):
        if not pareto_gap(ev, ref["front"])[1]:
            got.add("ai_slayer")
    if result["stars"] == 3:
        got.add("perfectionist")
    if result["stars"] >= 1 and ev["capex_total_sgd"] <= 0.6 * m.budget_sgd:
        got.add("lean_build")
    if decade is not None and decade["years_short"] == 0:
        got.add("decade_survivor")
    return got


def level_for(xp: float) -> dict:
    idx = max(i for i, (t, _) in enumerate(LEVELS) if xp >= t)
    lo = LEVELS[idx][0]
    hi = LEVELS[idx + 1][0] if idx + 1 < len(LEVELS) else None
    return {"level": idx + 1, "title": LEVELS[idx][1], "xp": xp, "next_at": hi,
            "progress": 1.0 if hi is None else (xp - lo) / (hi - lo)}


def total_xp(best: dict, badges: set) -> int:
    return int(sum(v["score"] for v in best.values()) // 2 + 60 * len(badges))


def unlocked(mission_id: str, best: dict) -> bool:
    req = MISSIONS[mission_id].unlock_after
    return req is None or best.get(req, {}).get("stars", 0) >= 1


# ----------------------------------------------------------------------------- decade simulation
def simulate_decade(b: Bundle, m: Mission, layout: dict[str, str], sell_credits: bool, seed: int,
                    start: int = 2026, n_years: int = 10) -> pd.DataFrame:
    """Ten stochastic years. Draws: national supply = projection x (1 + a backtest error of the naive method);
    woody share uniform within +/- the seasonal amplitude; credit price uniform within Senken's low-high band."""
    rng = np.random.default_rng(seed)
    s = fc.national_series(b)
    _, pts = fc.backtest(s)
    rel = (pts[pts.method == "naive_last"].eval("actual_t / predicted_t - 1")).to_numpy(float)
    base = fc.project(s, "naive_last", to_year=start + n_years - 1, backtest_points=pts)
    prices = ol.credit_price_path(b, base.year)
    amp = b.p("seasonal_woody_amplitude")
    a0 = mission_assumptions(b, m, sell_credits)
    shares = b.areas.estimated_t.to_numpy(float) / b.areas.estimated_t.sum()
    rows = []
    for i, y in enumerate(base.itertuples()):
        e = float(rng.choice(rel))
        woody = float(np.clip(a0.woody_share + rng.uniform(-amp, amp), 0.05, 0.95))
        pr = prices.iloc[i]
        price = float(rng.uniform(pr.low_eur, pr.high_eur)) if pr.high_eur > pr.low_eur else float(pr.base_eur)
        a = replace(a0, national_t=max(y.point_t * (1 + e), 1.0), woody_share=woody, credit_price_eur=price)
        r = nw.evaluate(nw.build_network(b, a, shares * a.national_t), layout)
        events = []
        if e >= 0.10:
            events.append(f"📈 Bumper year: supply {100 * e:+.0f}%")
        elif e <= -0.10:
            events.append(f"📉 Lean year: supply {100 * e:+.0f}%")
        if woody < a0.woody_share - amp / 2:
            events.append(f"🍂 Leafy year: woody share {100 * woody:.0f}%")
        elif woody > a0.woody_share + amp / 2:
            events.append(f"🪵 Woody year: {100 * woody:.0f}%")
        if r["shortfall_t"] > 0:
            events.append(f"⚠️ Short {r['shortfall_t']:,.0f} t")
        rows.append({"year": int(y.year), "national_t": a.national_t, "woody_share": woody, "credit_price_eur": price,
                     "processed_t": r["processed_t"], "shortfall_t": r["shortfall_t"],
                     "registry_credit_t": r["registry_credit_t"], "net_climate_t": r["net_climate_t"],
                     "result_sgd": -r["net_cost_sgd"], "events": " · ".join(events) or "Steady year"})
    df = pd.DataFrame(rows)
    df["cumulative_sgd"] = df.result_sgd.cumsum()
    return df


def decade_summary(b: Bundle, df: pd.DataFrame) -> dict:
    r = b.p("discount_rate")
    disc = (1 + r) ** -np.arange(1, len(df) + 1)
    pv = float((df.result_sgd * disc).sum())
    return {"pv_result_sgd": pv, "pv_loss_sgd": -pv, "years_short": int((df.shortfall_t > 1e-6).sum()),
            "credits_t": float(df.registry_credit_t.sum()), "tonnes": float(df.processed_t.sum())}


def decade_with_reference(b: Bundle, m: Mission, layout: dict[str, str], sell_credits: bool, ref: dict,
                          seed: int) -> tuple[pd.DataFrame, dict]:
    mine = simulate_decade(b, m, layout, sell_credits, seed)
    summ = decade_summary(b, mine)
    ref_pv = max(decade_summary(b, simulate_decade(b, m, ref["best_cost_layout"], sc, seed))["pv_result_sgd"]
                 for sc in (False, True))
    summ["ref_pv_loss_sgd"] = -ref_pv
    summ["seed"] = seed
    return mine, summ
