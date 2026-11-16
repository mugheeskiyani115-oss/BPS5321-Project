"""Compare proxy estimates with INDEPENDENT records, by URA region or PWC sector.

Never fill a template with model values: that makes validation circular. PWC sector records would cover
residential (mainly landed-home garden) waste only; NParks and town-council contractors' tonnages sit outside
the PWC system, so coverage must be checked before reading the error metrics.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

UNITS = {"region": "URA region", "pwc_sector": "PWC sector (approximate mapping)"}


def estimates_by(areas: pd.DataFrame, allocated_t: np.ndarray, unit: str) -> pd.DataFrame:
    if unit not in UNITS:
        raise ValueError(f"unit must be one of {list(UNITS)}")
    d = areas[[unit]].assign(estimated_t=np.asarray(allocated_t, float))
    return d.groupby(unit, as_index=False).estimated_t.sum()


def template(areas: pd.DataFrame, unit: str, year: int = 2025) -> pd.DataFrame:
    return pd.DataFrame({unit: sorted(areas[unit].dropna().unique()), "year": year, "observed_t": np.nan,
                         "source": "", "record_type": "independent collection / operator / contractor record",
                         "coverage_note": "which waste streams and premises are included"})


def compare(estimates: pd.DataFrame, observed: pd.DataFrame, unit: str, year: int = 2025) -> dict:
    need = {unit, "observed_t", "year", "source"}
    if not need.issubset(observed.columns):
        raise ValueError(f"Validation CSV needs columns: {sorted(need)}")
    d = observed.copy()
    d = d[pd.to_numeric(d.year, errors="coerce").eq(year)]
    d["observed_t"] = pd.to_numeric(d.observed_t, errors="coerce")
    d = d.dropna(subset=["observed_t"])
    d = d[d.source.astype(str).str.strip().ne("") & d.source.notna() & (d.observed_t >= 0)]
    if not len(d):
        raise ValueError(f"No usable {year} rows: each needs a non-negative observed_t and a named source")
    if d[unit].duplicated().any():
        raise ValueError(f"One row per {UNITS[unit]} please; duplicates: {sorted(d[unit][d[unit].duplicated()])}")
    j = estimates.merge(d[[unit, "observed_t", "source"]], on=unit, how="inner")
    if not len(j) or j.observed_t.sum() <= 0:
        raise ValueError("No uploaded rows match the model's units (check spelling)")
    j["error_t"] = j.estimated_t - j.observed_t
    j["error_pct"] = 100 * j.error_t / j.observed_t.replace(0, np.nan)
    wape = float(j.error_t.abs().sum() / j.observed_t.sum())
    rho = j[["estimated_t", "observed_t"]].corr(method="spearman").iloc[0, 1] if len(j) >= 3 else np.nan
    # Shares remove the scale difference when records cover only part of the stream.
    j["est_share"] = j.estimated_t / j.estimated_t.sum()
    j["obs_share"] = j.observed_t / j.observed_t.sum()
    share_mae = float((j.est_share - j.obs_share).abs().mean())
    return {"compared": len(j), "coverage": len(j) / len(estimates), "wape": wape, "rank_spearman": float(rho),
            "share_mae_pp": 100 * share_mae, "table": j}
