"""Load BioTwin's data files once, with explicit errors when something is missing."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
REBUILD_HINT = "Rebuild it with:  python -I pipeline/build_data.py all"
TAGS = {"notebook", "web", "derived", "assumption", "pdf"}


class DataMissing(FileNotFoundError):
    """A required data file is absent."""


def _csv(rel: str, required: tuple[str, ...] = (), optional: bool = False) -> pd.DataFrame | None:
    path = DATA / rel
    if not path.exists():
        if optional:
            return None
        raise DataMissing(f"data/{rel} not found. {REBUILD_HINT}")
    df = pd.read_csv(path)
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f"data/{rel} is missing columns: {sorted(missing)}")
    return df


@dataclass(frozen=True)
class Bundle:
    areas: pd.DataFrame          # 55 planning areas: estimates, proxies, coordinates, PWC sector
    sites: pd.DataFrame          # candidate hub sites with JTC land rent
    facilities: pd.DataFrame     # existing facilities (OSM)
    roads: pd.DataFrame | None   # origin x destination road distances and times (OSRM)
    params: pd.DataFrame         # parameter register, indexed by key
    plants: pd.DataFrame         # plant size classes, indexed by size_class
    benchmarks: pd.DataFrame     # opex benchmarks used to justify the cost basis
    carbon_path: pd.DataFrame    # CORC price path (EUR)
    fx: dict                     # usd_sgd, eur_sgd, gbp_sgd, date
    national: pd.DataFrame       # national series 2000-2025
    pwc: pd.DataFrame            # planning area -> PWC sector (approximate)
    geojson: dict | None         # planning-area polygons for the 3D map
    provenance: dict
    fingerprint: str             # hash of every model input, to detect stale precomputed results

    def p(self, key: str) -> float:
        if key not in self.params.index:
            raise KeyError(f"parameter '{key}' not in data/params/parameters.csv")
        return float(self.params.at[key, "value"])


def _fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        if p.exists():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


@lru_cache(maxsize=1)
def load_bundle() -> Bundle:
    areas = _csv("planning_area_estimates.csv",
                 ("planning_area", "region", "estimated_t", "p05_t", "p95_t", "latitude", "longitude"))
    if areas["estimated_t"].isna().any() or (areas["estimated_t"] < 0).any():
        raise ValueError("planning_area_estimates.csv: estimated_t must be present and non-negative")
    if areas["planning_area"].duplicated().any():
        raise ValueError("planning_area_estimates.csv: duplicate planning areas")
    for c, src in (("route_lat", "latitude"), ("route_lon", "longitude")):
        if c not in areas:
            areas[c] = areas[src]
    if "is_island" not in areas:
        areas["is_island"] = False
    pwc = _csv("pwc_sector_map.csv", ("planning_area", "pwc_sector"))
    areas = areas.merge(pwc[["planning_area", "pwc_sector"]], on="planning_area", how="left")

    sites = _csv("candidate_sites.csv", ("site_id", "name", "region", "latitude", "longitude"))
    if sites["site_id"].duplicated().any():
        raise ValueError("candidate_sites.csv: duplicate site_id")
    rents = _csv("params/site_land_rents.csv", ("site_id", "rent_sgd_m2_yr_with_gst"))
    sites = sites.merge(rents[["site_id", "jtc_estate", "rent_sgd_m2_yr_with_gst", "match"]], on="site_id", how="left")
    if sites.rent_sgd_m2_yr_with_gst.isna().any():
        raise ValueError(f"No JTC land rent for sites {list(sites.site_id[sites.rent_sgd_m2_yr_with_gst.isna()])}")

    facilities = _csv("facilities.csv", ("name", "latitude", "longitude"), optional=True)
    roads = _csv("road_distances.csv", ("origin", "destination", "road_km"), optional=True)
    params = _csv("params/parameters.csv", ("key", "value", "unit", "tag", "source")).set_index("key")
    bad = set(params.tag) - TAGS
    if bad:
        raise ValueError(f"parameters.csv: unknown tags {bad}")
    plants = _csv("params/plant_options.csv", ("size_class", "capacity_tpd", "carbon_class", "turnkey_usd_low",
                                                "turnkey_usd_high", "availability", "workers_per_shift")).set_index("size_class")
    benchmarks = _csv("params/opex_benchmarks.csv", ("benchmark", "technology", "usd_per_t_low", "usd_per_t_high"))
    carbon_path = _csv("params/carbon_price_path.csv", ("year", "low_eur", "base_eur", "high_eur"))
    fx_df = _csv("params/fx.csv", ("usd_sgd", "eur_sgd"), optional=True)
    fx = (fx_df.iloc[0].to_dict() if fx_df is not None else
          {"usd_sgd": 1.2881, "eur_sgd": 1.4236, "gbp_sgd": 1.7037, "date": "2026-11-13 (embedded fallback)"})
    fx.setdefault("gbp_sgd", 1.7037)
    national = _csv("national_waste_series.csv", ("year", "horti_generated_t"))

    gj_path = DATA / "geo" / "planning_areas.geojson"
    geojson = json.loads(gj_path.read_text()) if gj_path.exists() else None
    prov = {}
    for name in ("provenance.json", "pipeline_provenance.json"):
        f = DATA / name
        if f.exists():
            prov[name] = json.loads(f.read_text(encoding="utf8"))
    inputs = [DATA / "planning_area_estimates.csv", DATA / "candidate_sites.csv", DATA / "road_distances.csv",
              *sorted(f for f in (DATA / "params").glob("*.csv") if f.name != "pdf_claim_checks.csv")]
    return Bundle(areas=areas, sites=sites, facilities=facilities if facilities is not None else pd.DataFrame(),
                  roads=roads, params=params, plants=plants, benchmarks=benchmarks, carbon_path=carbon_path, fx=fx,
                  national=national, pwc=pwc, geojson=geojson, provenance=prov, fingerprint=_fingerprint(inputs))
