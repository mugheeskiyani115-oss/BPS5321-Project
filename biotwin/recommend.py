"""Recommended layouts: NSGA-II trade-off options for a few throughput levels.

Results are precomputed by `pipeline/build_recommendations.py` into data/recommendations.json and stamped with a
fingerprint of every model input; if inputs change, the app recomputes instead of showing stale answers.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import network as nw
from . import optimise as op
from . import pathway as pw
from .data import DATA, Bundle

TARGETS = (2_000, 5_000, 9_000, 15_000, 25_000)
FILE = DATA / "recommendations.json"
MAX_SITES = 6


def _summary(r: dict, labels: dict) -> dict:
    return {"layout": dict(r["config"]), "n_sites": r["n_sites"], "net_cost_sgd": r["net_cost_sgd"],
            "net_cost_sgd_per_t": r["net_cost_sgd_per_t"], "net_climate_t": r["net_climate_t"],
            "registry_credit_t": r["registry_credit_t"], "mean_haul_km": r["mean_haul_km"],
            "capex_total_sgd": r["capex_total_sgd"],
            "label": " + ".join(f"{labels[c]} at {s}" for s, c in r["config"].items())}


def compute(b: Bundle, target_t: float, seeds=(1, 2), pop: int = 60, gens: int = 60) -> dict:
    a = pw.default_assumptions(b, target_t=float(target_t))
    net = nw.build_network(b, a)
    labels = b.plants.label.to_dict()
    genomes = []
    for s in seeds:
        prob = op.Problem(net, tuple(b.plants.index), max_open=MAX_SITES)
        front = op.nsga2(prob, pop_size=pop, generations=gens, seed=s)["front"]
        genomes += [dict(c) for c in front.config]
    # the "most credits" option: also check every single industrial plant (credits are not an NSGA objective)
    for sc in b.plants.index[b.plants.carbon_class == "industrial"]:
        genomes += [{s: sc} for s in net.sites.site_id]
    evals, seen = [], set()
    for g in genomes:
        key = tuple(sorted(g.items()))
        if key in seen:
            continue
        seen.add(key)
        r = nw.evaluate(net, g)
        if r["feasible"]:
            evals.append(r)
    F = np.array([[r["net_cost_sgd"], r["net_climate_t"], r["mean_haul_km"]] for r in evals]) * op.SENSE
    options = [_summary(r, labels) for r, keep in zip(evals, op.pareto_mask(F)) if keep]
    options.sort(key=lambda o: o["net_cost_sgd"])
    feas = [_summary(r, labels) for r in evals]
    return {"target_t": float(target_t), "fingerprint": b.fingerprint,
            "cheapest": min(options, key=lambda o: o["net_cost_sgd"]),
            "most_credits": max(feas, key=lambda o: o["registry_credit_t"]),
            "shortest_haul": min(options, key=lambda o: o["mean_haul_km"]),
            "options": options}


def load(b: Bundle) -> dict[float, dict] | None:
    if not FILE.exists():
        return None
    data = json.loads(FILE.read_text())
    if data.get("fingerprint") != b.fingerprint:
        return None
    recs = {float(k): v for k, v in data.get("targets", {}).items()}
    return recs if all(float(t) in recs for t in TARGETS) else None


def save(b: Bundle, recs: dict) -> Path:
    FILE.write_text(json.dumps({"fingerprint": b.fingerprint, "targets": {str(k): v for k, v in recs.items()}},
                               indent=1))
    return FILE


def balanced(rec: dict) -> dict:
    """The option closest to the ideal point (normalised cost, climate and trucking all at their best)."""
    opts = pd.DataFrame(rec["options"])
    F = opts[["net_cost_sgd", "net_climate_t", "mean_haul_km"]].to_numpy() * op.SENSE
    span = np.maximum(F.max(axis=0) - F.min(axis=0), 1e-9)
    d = np.linalg.norm((F - F.min(axis=0)) / span, axis=1)
    return rec["options"][int(np.argmin(d))]


def describe(layout: dict, short: dict) -> str:
    """'1 × 50 t/day' or '1 × 20 t/day + 5 × 10 t/day' — compact, ordered by size."""
    counts = pd.Series(list(layout.values())).value_counts()
    order = sorted(counts.index, key=lambda c: -float("".join(ch for ch in c if ch.isdigit()) or 0))
    return " + ".join(f"{counts[c]} × {short[c]}" for c in order)


def compare(ev: dict, rec: dict) -> dict:
    """How a layout sits against the recommended options for the same throughput."""
    if not ev.get("feasible"):
        return {"comparable": False}
    opts = pd.DataFrame(rec["options"])
    F = opts[["net_cost_sgd", "net_climate_t", "mean_haul_km"]].to_numpy() * op.SENSE
    p = np.array([ev["net_cost_sgd"], ev["net_climate_t"], ev["mean_haul_km"]]) * op.SENSE
    dominated_by = np.all(F <= p + 1e-9, axis=1) & np.any(F < p - 1e-9, axis=1)
    cheapest = rec["cheapest"]
    return {"comparable": True,
            "cost_gap_pct": 100 * (ev["net_cost_sgd_per_t"] / cheapest["net_cost_sgd_per_t"] - 1),
            "credit_gap_t": ev["registry_credit_t"] - rec["most_credits"]["registry_credit_t"],
            "on_frontier": not bool(dominated_by.any()),
            "better_options": int(dominated_by.sum())}
