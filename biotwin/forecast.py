"""Prediction tools: national supply projection, spatial allocation and seasonal feedstock composition.

What the data can and cannot support
-----------------------------------
* NEA publishes ONE national horticultural-waste figure per year (26 points, 2000-2025). There is no
  monthly or regional series, so no model here forecasts monthly or regional waste from observations.
* The national projection is therefore chosen by a rolling-origin BACKTEST of simple methods on the
  real series; the method with measured skill (lowest error) is reported together with its error.
* The spatial split is a proxy allocation (tree biomass, tree count, managed green area) of the national
  value, with Dirichlet weight sensitivity; it is not validated against collections.
* Seasonal woody/leafy composition follows the research PDF's suggested stochastic treatment
  (mean woody share +/- amplitude, leafier in the Nov-Jan NE monsoon). It is an assumption-driven
  scenario generator, not a fitted model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .data import Bundle


# ----------------------------------------------------------------------------- national series
def national_series(b: Bundle) -> pd.Series:
    s = b.national.set_index("year")["horti_generated_t"].astype(float).dropna()
    return s.sort_index()


def trend_test(s: pd.Series, window: int = 10, exclude_years: tuple[int, ...] = ()) -> dict:
    """OLS slope test and the rank-based Mann-Kendall test (Kendall's tau vs time) on the last `window` years.

    The handoff's p = 0.073 is the Mann-Kendall result for 2016-2025; OLS on the same years gives p ~ 0.049.
    Report both: the 'no trend' reading is not robust to the test or window.
    """
    w = s.tail(window).drop(index=[y for y in exclude_years if y in s.tail(window).index])
    x, y = w.index.to_numpy(float), w.to_numpy(float)
    r = stats.linregress(x, y)
    kt = stats.kendalltau(x, y)
    return {"years": f"{int(w.index.min())}-{int(w.index.max())}", "n": len(w), "excluded": list(exclude_years),
            "slope_t_per_year": float(r.slope), "ols_p": float(r.pvalue), "r2": float(r.rvalue ** 2),
            "mann_kendall_tau": float(kt.statistic), "mann_kendall_p": float(kt.pvalue),
            "robust_trend": bool(r.pvalue < 0.05 and kt.pvalue < 0.05)}


def _predict(hist: pd.Series, method: str) -> float:
    v = hist.to_numpy(float)
    if method == "naive_last":
        return v[-1]
    if method == "mean_last5":
        return v[-5:].mean()
    if method == "median_last5":
        return float(np.median(v[-5:]))
    if method == "median_last10":
        return float(np.median(v[-10:]))
    if method == "linear_trend10":
        x = hist.index.to_numpy(float)[-10:]
        r = stats.linregress(x, v[-10:])
        return r.intercept + r.slope * (x[-1] + 1)
    raise ValueError(f"unknown method {method}")


METHODS = {
    "naive_last": "Last observed year",
    "mean_last5": "Mean of last 5 years",
    "median_last5": "Median of last 5 years (handoff approach)",
    "median_last10": "Median of last 10 years",
    "linear_trend10": "Linear trend on last 10 years",
}


def backtest(s: pd.Series, first_test_year: int = 2011, horizon: int = 1) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rolling-origin evaluation: for each test year t, fit on years <= t - horizon, predict t."""
    preds = []
    for t in s.index[s.index >= first_test_year]:
        hist = s.loc[: t - horizon]
        if len(hist) < 10:
            continue
        for m in METHODS:
            yhat = _predict(hist, m)
            preds.append({"year": int(t), "method": m, "predicted_t": yhat, "actual_t": s.loc[t]})
        w = hist.tail(10)
        lo, hi = np.percentile(w, [10, 90])
        preds.append({"year": int(t), "method": "_interval", "predicted_t": np.nan, "actual_t": s.loc[t],
                      "lo": lo, "hi": hi})
    p = pd.DataFrame(preds)
    pts = p[p.method != "_interval"].copy()
    pts["abs_err"] = (pts.predicted_t - pts.actual_t).abs()
    pts["ape"] = pts.abs_err / pts.actual_t
    summary = pts.groupby("method").agg(n_years=("year", "size"), mae_t=("abs_err", "mean"),
                                        mape_pct=("ape", lambda x: 100 * x.mean()),
                                        median_ape_pct=("ape", lambda x: 100 * x.median()))
    summary["description"] = summary.index.map(METHODS)
    iv = p[p.method == "_interval"]
    coverage = float(((iv.actual_t >= iv.lo) & (iv.actual_t <= iv.hi)).mean()) if len(iv) else np.nan
    summary.attrs["p10_p90_coverage"] = coverage
    return summary.sort_values("mape_pct"), pts


def project(s: pd.Series, method: str = "naive_last", to_year: int = 2045,
            backtest_points: pd.DataFrame | None = None) -> pd.DataFrame:
    """Point projection from `method`, with an 80% band from that method's own backtest errors.

    Band = point x (1 + 10th / 90th percentile of the signed relative one-year-ahead errors), so it reflects
    how wrong the method has actually been on this series. It is held constant over the horizon: there is no
    evidence for how error grows with lead time, so treat later years as no better than this.
    """
    if method not in METHODS:
        raise ValueError(f"unknown method {method}")
    years = np.arange(int(s.index.max()) + 1, to_year + 1)
    if method == "linear_trend10":
        x = s.index.to_numpy(float)[-10:]
        r = stats.linregress(x, s.to_numpy(float)[-10:])
        point = np.maximum(r.intercept + r.slope * years, 0)
    else:
        point = np.full(len(years), _predict(s, method))
    if backtest_points is None:
        _, backtest_points = backtest(s)
    e = backtest_points[backtest_points.method == method]
    rel = (e.actual_t / e.predicted_t - 1).to_numpy(float)
    lo, hi = np.percentile(rel, [10, 90]) if len(rel) else (0.0, 0.0)
    return pd.DataFrame({"year": years, "point_t": point, "p10_t": point * (1 + lo), "p90_t": point * (1 + hi),
                         "method": method})


def recent_range(s: pd.Series, k: int = 5) -> dict:
    w = s.tail(k)
    return {"years": f"{int(w.index.min())}-{int(w.index.max())}", "median_t": float(w.median()),
            "min_t": float(w.min()), "max_t": float(w.max())}


# ----------------------------------------------------------------------------- spatial allocation
PROXY_COLUMNS = {"s_biomass": "Tree biomass proxy", "s_tree_count": "Managed tree count",
                 "s_managed_green": "Managed green area (land cover)"}


def available_proxies(areas: pd.DataFrame) -> list[str]:
    return [c for c in PROXY_COLUMNS if c in areas.columns]


def allocate(areas: pd.DataFrame, weights: dict[str, float] | None, national_t: float) -> np.ndarray:
    """Planning-area tonnes = national total x weighted mix of each proxy's national share."""
    cols = available_proxies(areas)
    if not cols:   # older 5-region / 55-area files without per-proxy shares
        share = areas["estimated_t"].to_numpy(float)
        return share / share.sum() * national_t
    w = np.array([max(float((weights or {}).get(c, 1.0)), 0.0) for c in cols])
    if w.sum() <= 0:
        raise ValueError("At least one proxy weight must be positive")
    S = areas[cols].to_numpy(float)
    return S @ (w / w.sum()) * national_t


def weight_sensitivity(areas: pd.DataFrame, national_t: float, n: int = 2000, seed: int = 42) -> pd.DataFrame:
    cols = available_proxies(areas)
    S = areas[cols].to_numpy(float)
    W = np.random.default_rng(seed).dirichlet(np.ones(len(cols)), size=n)
    sims = S @ W.T * national_t
    base = allocate(areas, None, national_t)
    rho = np.array([stats.spearmanr(base, sims[:, k])[0] for k in range(n)])
    return pd.DataFrame({"planning_area": areas.planning_area, "p05_t": np.percentile(sims, 5, axis=1),
                         "p95_t": np.percentile(sims, 95, axis=1)}).assign(median_rank_rho=float(np.median(rho)))


# ----------------------------------------------------------------------------- seasonal composition
MONSOON_MONTHS = (11, 12, 1)


def monthly_composition(woody_mean: float, amplitude: float) -> pd.DataFrame:
    """Woody share lower by `amplitude` in Nov-Jan, higher in other months; annual mean preserved.

    Monthly TONNAGE is shown flat (annual / 12) because no monthly data exists.
    """
    monsoon = np.isin(np.arange(1, 13), MONSOON_MONTHS)
    up = amplitude * monsoon.sum() / (~monsoon).sum()
    if amplitude < 0 or woody_mean - amplitude < 0 or woody_mean + up > 1:
        raise ValueError("Seasonal amplitude too large for the chosen woody share")
    woody = np.where(monsoon, woody_mean - amplitude, woody_mean + up).clip(0, 1)
    return pd.DataFrame({"month": np.arange(1, 13), "woody_share": woody, "leafy_share": 1 - woody,
                         "monsoon": monsoon})


def woody_share_draws(woody_mean: float, sd: float, n: int, seed: int = 7) -> np.ndarray:
    """Stochastic woody share for uncertainty runs (truncated normal on [0.05, 0.95])."""
    rng = np.random.default_rng(seed)
    return np.clip(rng.normal(woody_mean, sd, size=n), 0.05, 0.95)
