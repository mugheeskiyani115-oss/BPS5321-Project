"""NSGA-II (Deb et al., 2002) over candidate sites x plant sizes, with an exhaustive check for small cases.

Decision variables: one integer gene per candidate site; 0 = closed, k = open with the k-th size class.
Objectives (all minimised internally):
  1. annual net cost, S$/yr                    (capex annuity + opex + haul + dMRV - revenue)
  2. -net climate benefit vs current use, tCO2e/yr
  3. mean haul distance, km per tonne
Constraint: processed tonnes >= target throughput; violation = shortfall in tonnes (Deb's constrained domination:
feasible beats infeasible; between infeasible solutions the smaller shortfall wins).

Ten sites x six sizes is 7^10 ~ 2.8e8 configurations, so exhaustive enumeration is impossible at full size;
`exhaustive()` exists to verify NSGA-II recovers the true Pareto front on reduced instances (see tests).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

import numpy as np
import pandas as pd

from .network import Network, evaluate

OBJECTIVES = ("net_cost_sgd", "net_climate_t", "mean_haul_km")
SENSE = np.array([1.0, -1.0, 1.0])          # +1 minimise, -1 maximise


@dataclass
class Problem:
    net: Network
    levels: tuple[str, ...]                  # size classes allowed (gene k -> levels[k-1])
    max_open: int | None = None
    max_capex_sgd: float | None = None       # capital budget (game missions)
    cache: dict = field(default_factory=dict)

    @property
    def n_genes(self) -> int:
        return len(self.net.sites)

    def decode(self, g: np.ndarray) -> dict[str, str]:
        return {self.net.sites.site_id.iat[i]: self.levels[v - 1] for i, v in enumerate(g) if v > 0}

    def evaluate(self, g: np.ndarray) -> tuple[np.ndarray, float]:
        key = tuple(int(x) for x in g)
        if key not in self.cache:
            r = evaluate(self.net, self.decode(np.array(key)))
            f = np.array([r[o] for o in OBJECTIVES]) * SENSE
            cv = r["shortfall_t"]
            if self.max_open is not None and r["n_sites"] > self.max_open:
                cv += 1e6 * (r["n_sites"] - self.max_open)
            if self.max_capex_sgd is not None and r["capex_total_sgd"] > self.max_capex_sgd:
                cv += (r["capex_total_sgd"] - self.max_capex_sgd) / 100   # S$100 of overspend ~ 1 t of shortfall
            self.cache[key] = (f, cv, r)
        f, cv, _ = self.cache[key]
        return f, cv


def _dominates(fa, ca, fb, cb) -> bool:
    if ca < cb:
        return True
    if ca > cb:
        return False
    return bool(np.all(fa <= fb) and np.any(fa < fb))


def non_dominated_sort(F: np.ndarray, CV: np.ndarray) -> list[list[int]]:
    n = len(F)
    S = [[] for _ in range(n)]
    count = np.zeros(n, int)
    fronts = [[]]
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if _dominates(F[p], CV[p], F[q], CV[q]):
                S[p].append(q)
            elif _dominates(F[q], CV[q], F[p], CV[p]):
                count[p] += 1
        if count[p] == 0:
            fronts[0].append(p)
    i = 0
    while fronts[i]:
        nxt = []
        for p in fronts[i]:
            for q in S[p]:
                count[q] -= 1
                if count[q] == 0:
                    nxt.append(q)
        i += 1
        fronts.append(nxt)
    return fronts[:-1]


def crowding(F: np.ndarray) -> np.ndarray:
    n, m = F.shape
    d = np.zeros(n)
    if n <= 2:
        return np.full(n, np.inf)
    for j in range(m):
        o = np.argsort(F[:, j])
        span = F[o[-1], j] - F[o[0], j]
        d[o[0]] = d[o[-1]] = np.inf
        if span > 0:
            d[o[1:-1]] += (F[o[2:], j] - F[o[:-2], j]) / span
    return d


def _rank_and_crowd(F, CV):
    rank = np.empty(len(F), int)
    crowd = np.empty(len(F))
    for r, fr in enumerate(non_dominated_sort(F, CV)):
        rank[fr] = r
        crowd[fr] = crowding(F[fr])
    return rank, crowd


def nsga2(problem: Problem, pop_size: int = 60, generations: int = 60, p_cross: float = 0.9,
          p_open_init: float = 0.25, seed: int = 0, progress=None) -> dict:
    rng = np.random.default_rng(seed)
    n, L = problem.n_genes, len(problem.levels)

    # Initial population: random sparse layouts + every "one plant at one site" layout that meets the target.
    pop = []
    single = [k + 1 for k, c in enumerate(problem.levels)
              if problem.net.plants.loc[c, "capacity_tpd"] * 365 * problem.net.plants.loc[c, "availability"]
              >= problem.net.a.target_t]
    if single:
        for i in range(n):
            g = np.zeros(n, int)
            g[i] = single[0]
            pop.append(g)
    while len(pop) < pop_size:
        g = np.where(rng.random(n) < p_open_init, rng.integers(1, L + 1, n), 0)
        pop.append(g)
    pop = np.array(pop[:pop_size])

    def eval_all(P):
        res = [problem.evaluate(g) for g in P]
        return np.array([r[0] for r in res]), np.array([r[1] for r in res])

    F, CV = eval_all(pop)
    history = []
    for gen in range(generations):
        rank, crowd = _rank_and_crowd(F, CV)
        # binary tournament
        def pick():
            i, j = rng.integers(0, len(pop), 2)
            if rank[i] != rank[j]:
                return i if rank[i] < rank[j] else j
            return i if crowd[i] >= crowd[j] else j
        kids = []
        while len(kids) < pop_size:
            a_, b_ = pop[pick()].copy(), pop[pick()].copy()
            if rng.random() < p_cross:                       # uniform crossover
                mask = rng.random(n) < 0.5
                a_[mask], b_[mask] = b_[mask], a_[mask].copy()
            for c in (a_, b_):                               # mutation: close a site or change its size
                m = rng.random(n) < 1.0 / n
                c[m] = np.where(rng.random(m.sum()) < 0.5, 0, rng.integers(1, L + 1, m.sum()))
                kids.append(c)
        kids = np.array(kids[:pop_size])
        Fk, CVk = eval_all(kids)
        allP, allF, allCV = np.vstack([pop, kids]), np.vstack([F, Fk]), np.concatenate([CV, CVk])
        # de-duplicate genotypes so the front isn't filled with copies
        _, uniq = np.unique(allP, axis=0, return_index=True)
        uniq = np.sort(uniq)
        allP, allF, allCV = allP[uniq], allF[uniq], allCV[uniq]
        fronts = non_dominated_sort(allF, allCV)
        chosen = []
        for fr in fronts:
            if len(chosen) + len(fr) <= pop_size:
                chosen.extend(fr)
            else:
                cd = crowding(allF[fr])
                chosen.extend(np.array(fr)[np.argsort(-cd)][: pop_size - len(chosen)])
                break
        chosen = np.array(chosen)
        pop, F, CV = allP[chosen], allF[chosen], allCV[chosen]
        feas = CV == 0
        history.append({"generation": gen + 1, "evaluations": len(problem.cache),
                        "feasible_share": float(feas.mean()),
                        "best_net_cost_sgd": float(F[feas, 0].min()) if feas.any() else np.nan,
                        "best_net_climate_t": float(-F[feas, 1].min()) if feas.any() else np.nan})
        if progress:
            progress((gen + 1) / generations)

    return {"front": pareto_table(problem, pop), "history": pd.DataFrame(history),
            "evaluations": len(problem.cache)}


def pareto_table(problem: Problem, genomes) -> pd.DataFrame:
    """Feasible, non-dominated, de-duplicated solutions as a table (one row per configuration)."""
    rows = {}
    for g in genomes:
        key = tuple(int(x) for x in g)
        f, cv = problem.evaluate(np.array(key))
        if cv == 0:
            rows[key] = (f, problem.cache[key][2])
    if not rows:
        return pd.DataFrame()
    keys = list(rows)
    F = np.array([rows[k][0] for k in keys])
    keep = pareto_mask(F)
    out = []
    for k, ok in zip(keys, keep):
        if not ok:
            continue
        r = rows[k][1]
        out.append({"configuration": label(problem, r["config"]), "n_sites": r["n_sites"],
                    "capacity_t": r["capacity_t"], "net_cost_sgd": r["net_cost_sgd"],
                    "net_cost_sgd_per_t": r["net_cost_sgd_per_t"], "net_climate_t": r["net_climate_t"],
                    "registry_credit_t": r["registry_credit_t"], "mean_haul_km": r["mean_haul_km"],
                    "capex_total_sgd": r["capex_total_sgd"], "genome": "".join(map(str, k)),
                    "config": r["config"]})
    return pd.DataFrame(out).sort_values("net_cost_sgd").reset_index(drop=True)


def pareto_mask(F: np.ndarray) -> np.ndarray:
    n = len(F)
    keep = np.ones(n, bool)
    for i in range(n):
        dom = np.all(F <= F[i], axis=1) & np.any(F < F[i], axis=1)
        keep[i] = not dom.any()
    return keep


def label(problem: Problem, config: dict[str, str]) -> str:
    names = problem.net.sites.set_index("site_id").name
    return " + ".join(f"{c} @ {names[s]}" for s, c in config.items())


def exhaustive(problem: Problem) -> pd.DataFrame:
    """Evaluate every configuration (only for small instances) and return the true Pareto front."""
    n, L = problem.n_genes, len(problem.levels)
    if (L + 1) ** n > 200_000:
        raise ValueError(f"{(L + 1) ** n:,} configurations is too many to enumerate")
    return pareto_table(problem, [np.array(g) for g in product(range(L + 1), repeat=n)])
