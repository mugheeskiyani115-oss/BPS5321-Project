#!/usr/bin/env python3
"""Rebuild the open datasets BioTwin uses, without Colab or Google Drive.

    python -I pipeline/build_data.py all        # every step, in dependency order
    python -I pipeline/build_data.py roads      # a single step

Raw downloads are cached in data/raw/ (git-ignored). Processed outputs go to data/.
Each output is logged with its source URL and retrieval date in data/pipeline_provenance.json.

Steps
-----
geo        URA MP2019 subzones -> 55 planning areas + 5 regions; NParks nature reserves
trees      NParks Trees.sg (community copy) -> tree count and biomass proxy per planning area
landcover  ESA WorldCover 2021 (10 m) -> green / managed-green / grass area per planning area
allocate   Allocate NEA's 2025 national total across planning areas (same method as the EDA notebook)
sites      URA MP2019 land use "BUSINESS 2" (industrial) parcels -> candidate hub sites
facilities OpenStreetMap / Nominatim -> existing waste-to-energy and related facilities
roads      OSRM (OpenStreetMap road network) -> road distance origin x destination matrix
fx         European Central Bank reference rates -> USD/EUR to SGD
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA, RAW, GEO, PARAMS = ROOT / "data", ROOT / "data" / "raw", ROOT / "data" / "geo", ROOT / "data" / "params"
PROV_FILE = DATA / "pipeline_provenance.json"
SVY21 = "EPSG:3414"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "BioTwin-academic-pipeline/1.0 (horticultural waste research)"

REFERENCE_YEAR = 2025
NATIONAL_T = 232_000          # NEA Annex A, Table 1, CY2025 horticultural waste generated ('000 t = 232)
N_WEIGHT_SAMPLES, SEED = 2000, 42
WOOD_DENSITY = 0.60           # g/cm3: constant multiplier, does not change any planning area's share
GIRTH_MIDPOINT_M = {"XS": 0.25, "S": 0.8, "M": 1.3, "L": 1.9}   # L (>1.5 m) open-ended: 1.9 m is an assumption
UNMANAGED_AREAS = ["CENTRAL WATER CATCHMENT", "WESTERN WATER CATCHMENT", "NORTH-EASTERN ISLANDS", "WESTERN ISLANDS"]
ISLAND_AREAS = ["NORTH-EASTERN ISLANDS", "WESTERN ISLANDS", "SOUTHERN ISLANDS"]

DATAGOV = "https://api-open.data.gov.sg/v1/public/api/datasets/{}"
DS_SUBZONES = "d_8594ae9ff96d0c708bc2af633048edfb"     # URA MP2019 subzone boundary (no sea)
DS_RESERVES = "d_dfd037f5064cb2e2b2e358ceeccb4af7"     # NParks nature reserves gazette
DS_LANDUSE = "d_90d86daa5bfaa371668b84fa5f01424f"      # URA MP2019 land use layer
TREES_URL = "https://raw.githubusercontent.com/cheeaun/sgtreesdata/main/data/trees.csv"
SPECIES_URL = "https://raw.githubusercontent.com/cheeaun/sgtreesdata/main/data/species.json"
WC_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N00E102_Map.tif"
SG_BBOX = (103.55, 1.15, 104.10, 1.48)
OSRM_URL = "https://router.project-osrm.org/table/v1/driving/"
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


# --------------------------------------------------------------------------- helpers
def record(key: str, **info) -> None:
    prov = json.loads(PROV_FILE.read_text()) if PROV_FILE.exists() else {}
    prov[key] = {**info, "retrieved": dt.date.today().isoformat()}
    PROV_FILE.write_text(json.dumps(prov, indent=1, ensure_ascii=False))


def cached_download(url: str, dest: Path, params=None, timeout=300) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    r = SESSION.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return dest


def datagov_download(dataset_id: str, dest: Path, max_polls: int = 10) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = None
    for attempt in range(max_polls):
        r = SESSION.get(DATAGOV.format(dataset_id) + "/poll-download", timeout=30)
        url = ((r.json() if r.ok else {}).get("data") or {}).get("url")
        if url:
            break
        if attempt == 0:
            SESSION.get(DATAGOV.format(dataset_id) + "/initiate-download", timeout=30)
        time.sleep(3)
    if not url:
        raise RuntimeError(f"data.gov.sg returned no download URL for {dataset_id}")
    return cached_download(url, dest, timeout=900)


def _attr(row, keys, html_key):
    for k in keys:
        if k in row and pd.notna(row[k]):
            return str(row[k]).strip().upper()
    m = re.search(html_key + r"\s*</th>\s*<td>\s*([^<]+?)\s*</td>", str(row.get("Description", "")), flags=re.I)
    return m.group(1).strip().upper() if m else None


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.minimum(1, a)))


def load_pa():
    import geopandas as gpd
    return gpd.read_file(GEO / "planning_areas_full.gpkg")


# --------------------------------------------------------------------------- steps
def step_geo():
    import geopandas as gpd
    sz = gpd.read_file(datagov_download(DS_SUBZONES, RAW / "mp2019_subzones.geojson"))
    sz["planning_area"] = sz.apply(lambda r: _attr(r, ["PLN_AREA_N", "pln_area_n"], "PLN_AREA_N"), axis=1)
    sz["region"] = sz.apply(lambda r: _attr(r, ["REGION_N", "region_n"], "REGION_N"), axis=1)
    sz["subzone"] = sz.apply(lambda r: _attr(r, ["SUBZONE_N", "subzone_n"], "SUBZONE_N"), axis=1)
    sz = sz.set_crs(4326, allow_override=sz.crs is None).to_crs(SVY21)
    sz["geometry"] = sz.geometry.buffer(0)
    sz[["subzone", "planning_area", "region", "geometry"]].to_file(GEO / "subzones_full.gpkg", driver="GPKG")

    pa = sz.dissolve("planning_area", aggfunc={"region": "first"}).reset_index()
    pa["region"] = pa.region.str.replace(" REGION", "", regex=False).str.title()
    pa["area_km2"] = pa.area / 1e6
    try:
        nr = gpd.read_file(datagov_download(DS_RESERVES, RAW / "nature_reserves.geojson")).to_crs(SVY21)
        nr["geometry"] = nr.geometry.buffer(0)
        inter = gpd.overlay(pa[["planning_area", "geometry"]], nr[["geometry"]], how="intersection", keep_geom_type=True)
        pa = pa.merge(inter.dissolve("planning_area").area.div(1e6).rename("reserve_km2"),
                      left_on="planning_area", right_index=True, how="left").fillna({"reserve_km2": 0})
        nr[["geometry"]].to_file(GEO / "nature_reserves.gpkg", driver="GPKG")
        record("nature_reserves", source=f"NParks Nature Reserves Gazette, data.gov.sg {DS_RESERVES}")
    except Exception as exc:  # optional layer
        pa["reserve_km2"] = 0.0
        print(f"  nature reserves unavailable: {exc}")
    pa = pa.sort_values("planning_area").reset_index(drop=True)
    pa.to_file(GEO / "planning_areas_full.gpkg", driver="GPKG")

    # Light WGS84 copy for the app's 3D map (simplified ~20 m; display only).
    light = pa[["planning_area", "region", "area_km2", "geometry"]].copy()
    light["geometry"] = light.geometry.simplify(20, preserve_topology=True)
    light.to_crs(4326).to_file(GEO / "planning_areas.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
    record("planning_areas", source=f"URA Master Plan 2019 subzone boundary (no sea), data.gov.sg {DS_SUBZONES}",
           note="Subzones dissolved to planning areas; REGION_N gives the five URA regions",
           n_planning_areas=len(pa))
    print(f"  {len(pa)} planning areas, {pa.area_km2.sum():,.0f} km2; regions: {pa.region.value_counts().to_dict()}")


def step_trees():
    import geopandas as gpd
    pa = load_pa()
    trees = pd.read_csv(cached_download(TREES_URL, RAW / "trees.csv"))
    trees["girth_m"] = trees.girth_size.map(GIRTH_MIDPOINT_M)
    trees["height_m"] = (trees.height_est.where(trees.height_est >= 3) - 1.5).clip(lower=1.5)
    trees["girth_m"] = trees.girth_m.fillna(trees.girth_m.median())
    trees["height_m"] = trees.height_m.fillna(trees.groupby("girth_m").height_m.transform("median"))
    d_cm = trees.girth_m * 100 / np.pi
    trees["agb_kg"] = 0.0673 * (WOOD_DENSITY * d_cm ** 2 * trees.height_m) ** 0.976   # Chave et al. (2014) Eq. 4 form
    tg = gpd.GeoDataFrame(trees[["agb_kg"]], geometry=gpd.points_from_xy(trees.lng, trees.lat), crs=4326).to_crs(SVY21)
    tg = gpd.sjoin(tg, pa[["planning_area", "geometry"]], how="inner", predicate="within")
    stats = tg.groupby("planning_area").agg(n_trees=("agb_kg", "size"), agb_t=("agb_kg", lambda s: s.sum() / 1e3))
    stats.to_csv(DATA / "processed_tree_stats.csv")
    record("trees", source="NParks Trees.sg via github.com/cheeaun/sgtreesdata (community copy, Oct 2021; (c) NParks)",
           url=TREES_URL, n_trees_loaded=int(len(trees)), n_trees_matched=int(len(tg)),
           allometry="AGB = 0.0673 (rho D^2 H)^0.976, Chave et al. 2014; girth-class midpoints; relative index only")
    print(f"  {len(trees):,} trees loaded, {len(tg):,} matched to planning areas")


def step_landcover():
    import geopandas as gpd
    import rasterio
    from rasterio import features
    from rasterio.windows import Window, from_bounds
    pa = load_pa()
    local = RAW / "worldcover_sg_2021.tif"
    if not local.exists():
        with rasterio.Env(GDAL_HTTP_TIMEOUT="120", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
            with rasterio.open("/vsicurl/" + WC_URL) as src:
                w = from_bounds(*SG_BBOX, transform=src.transform)
                w = Window(int(w.col_off), int(w.row_off), int(math.ceil(w.width)), int(math.ceil(w.height)))
                arr, tr = src.read(1, window=w), src.window_transform(w)
                prof = {"driver": "GTiff", "dtype": arr.dtype, "count": 1, "crs": src.crs, "transform": tr,
                        "height": arr.shape[0], "width": arr.shape[1], "compress": "deflate", "nodata": 0}
        with rasterio.open(local, "w", **prof) as dst:
            dst.write(arr, 1)
    with rasterio.open(local) as src:
        lc, tr, crs = src.read(1), src.transform, src.crs
    zones = features.rasterize(((g, i + 1) for i, g in enumerate(pa.to_crs(crs).geometry)),
                               out_shape=lc.shape, transform=tr, fill=0, dtype="int32")
    in_res = np.zeros(lc.shape, bool)
    if (GEO / "nature_reserves.gpkg").exists():
        nr = gpd.read_file(GEO / "nature_reserves.gpkg").to_crs(crs)
        in_res = features.rasterize(((g, 1) for g in nr.geometry), out_shape=lc.shape, transform=tr,
                                    fill=0, dtype="uint8").astype(bool)
    valid = (zones > 0) & (lc > 0)
    nz = len(pa) + 1
    total = np.maximum(np.bincount(zones[valid], minlength=nz).astype(float), 1)
    green = np.isin(lc, [10, 20, 30, 90, 95]) & valid
    out = pd.DataFrame({
        "planning_area": pa.planning_area,
        "tree_pct": 100 * (np.bincount(zones[valid & (lc == 10)], minlength=nz) / total)[1:],
        "built_pct": 100 * (np.bincount(zones[valid & (lc == 50)], minlength=nz) / total)[1:],
        "green_pct": 100 * (np.bincount(zones[green], minlength=nz) / total)[1:],
        "green_managed_pct": 100 * (np.bincount(zones[green & ~in_res], minlength=nz) / total)[1:],
        "grass_pct": 100 * (np.bincount(zones[valid & (lc == 30)], minlength=nz) / total)[1:],
    })
    for c in ["green", "green_managed", "grass"]:
        out[f"{c}_km2"] = out[f"{c}_pct"] / 100 * pa.area_km2.to_numpy()
    out.to_csv(DATA / "processed_landcover_stats.csv", index=False)
    record("landcover", source="ESA WorldCover 2021 v200, 10 m, tile N00E102 (CC BY 4.0)", url=WC_URL,
           note="Green = tree, shrub, grass, herbaceous wetland, mangrove; managed = outside gazetted nature reserves")
    print(f"  national tree cover {100 * (lc[valid] == 10).mean():.1f}%, green {100 * green.sum() / valid.sum():.1f}%")


def step_allocate():
    from scipy import stats as sstats
    pa = load_pa()
    tree = pd.read_csv(DATA / "processed_tree_stats.csv")
    df = pa.drop(columns="geometry").merge(tree, on="planning_area", how="left")
    lc_file = DATA / "processed_landcover_stats.csv"
    proxies = {"agb_t": "s_biomass", "n_trees": "s_tree_count"}
    if lc_file.exists():
        df = df.merge(pd.read_csv(lc_file), on="planning_area", how="left")
        proxies["green_managed_km2"] = "s_managed_green"
    df[list(proxies)] = df[list(proxies)].fillna(0)
    X = df[list(proxies)].copy()
    if "green_managed_km2" in X:
        X.loc[df.planning_area.isin(UNMANAGED_AREAS), "green_managed_km2"] = 0   # catchments / islands: not pruned
    S = X.to_numpy(float) / X.to_numpy(float).sum(axis=0)
    for j, col in enumerate(proxies.values()):
        df[col] = S[:, j]
    w0 = np.full(S.shape[1], 1 / S.shape[1])
    df["estimated_t"] = S @ w0 * NATIONAL_T
    W = np.random.default_rng(SEED).dirichlet(np.ones(S.shape[1]), size=N_WEIGHT_SAMPLES)
    sims = (S @ W.T) * NATIONAL_T
    df["p05_t"], df["p95_t"] = np.percentile(sims, 5, axis=1), np.percentile(sims, 95, axis=1)
    rho = np.array([sstats.spearmanr(df.estimated_t, sims[:, k])[0] for k in range(N_WEIGHT_SAMPLES)])

    import geopandas as gpd
    cent = gpd.GeoSeries(pa.geometry.centroid, crs=SVY21).to_crs(4326)
    rep = gpd.GeoSeries(pa.geometry.representative_point(), crs=SVY21).to_crs(4326)
    df["latitude"], df["longitude"] = cent.y.round(5).to_numpy(), cent.x.round(5).to_numpy()
    df["route_lat"], df["route_lon"] = rep.y.round(5).to_numpy(), rep.x.round(5).to_numpy()
    df["is_island"] = df.planning_area.isin(ISLAND_AREAS)
    df["share_pct"] = 100 * df.estimated_t / NATIONAL_T
    df["estimate_status"] = f"{REFERENCE_YEAR} national total allocated by proxies; not observed"
    keep = ["planning_area", "region", "area_km2", "estimated_t", "p05_t", "p95_t", "share_pct", "latitude", "longitude",
            "route_lat", "route_lon", "is_island", "n_trees", "agb_t"] + \
           [c for c in ["green_managed_km2", "grass_km2", "tree_pct", "built_pct"] if c in df] + \
           list(proxies.values()) + ["estimate_status"]
    out = df[keep].sort_values("estimated_t", ascending=False)
    out.to_csv(DATA / "planning_area_estimates.csv", index=False)

    reg = out.groupby("region").agg(estimated_t=("estimated_t", "sum"), recorded_trees=("n_trees", "sum"))
    idx = {r: (df.region == r).to_numpy() for r in reg.index}
    reg["p05_t"] = [np.percentile(sims[idx[r]].sum(axis=0), 5) for r in reg.index]
    reg["p95_t"] = [np.percentile(sims[idx[r]].sum(axis=0), 95) for r in reg.index]
    reg["share_pct"] = 100 * reg.estimated_t / NATIONAL_T
    reg.round(0).sort_values("estimated_t", ascending=False).to_csv(DATA / "region_estimates_rebuilt.csv")
    record("planning_area_estimates", method="equal-weight mix of proxy shares; Dirichlet(1) weight sensitivity",
           proxies=list(proxies), national_t=NATIONAL_T, n_weight_samples=N_WEIGHT_SAMPLES,
           median_rank_spearman=round(float(np.median(rho)), 3), status="proxy allocation, NOT observed regional waste")
    print(f"  mass balance {out.estimated_t.sum():,.0f} t; median rank rho {np.median(rho):.3f}")
    print(reg.round(-2).to_string())


def step_sites(top_n: int = 10, min_spacing_km: float = 4.0):
    """Candidate hubs = largest contiguous URA 'BUSINESS 2' (industrial) clusters, spread across regions.

    These are areas ZONED for industry in MP2019, not vacant or available parcels.
    """
    import geopandas as gpd
    path = datagov_download(DS_LANDUSE, RAW / "mp2019_landuse.geojson")
    lu = gpd.read_file(path)
    if "LU_DESC" not in lu.columns:
        lu["LU_DESC"] = lu.apply(lambda r: _attr(r, ["LU_DESC"], "LU_DESC"), axis=1)
    lu = lu.set_crs(4326, allow_override=lu.crs is None).to_crs(SVY21)
    b2 = lu[lu.LU_DESC.astype(str).str.upper().eq("BUSINESS 2")].copy()
    b2["geometry"] = b2.geometry.buffer(0)
    clusters = gpd.GeoDataFrame(geometry=list(b2.geometry.buffer(40).union_all().geoms), crs=SVY21)
    clusters["geometry"] = clusters.geometry.buffer(-40)
    clusters = clusters[~clusters.geometry.is_empty]
    clusters["b2_ha"] = clusters.area / 1e4
    sz = gpd.read_file(GEO / "subzones_full.gpkg")
    pts = clusters.copy()
    pts["geometry"] = clusters.geometry.representative_point()
    pts = gpd.sjoin(pts, sz[["subzone", "planning_area", "region", "geometry"]], how="left", predicate="within")
    pts = pts[~pts.planning_area.isin(ISLAND_AREAS)].dropna(subset=["planning_area"])
    pts["region"] = pts.region.str.replace(" REGION", "", regex=False).str.title()
    pts = pts.sort_values("b2_ha", ascending=False)

    chosen = []
    def far_enough(p):
        return all(p.geometry.distance(c.geometry) / 1000 >= min_spacing_km for c in chosen)
    for region in pts.region.unique():                         # 1. largest cluster in each region
        for _, p in pts[pts.region == region].iterrows():
            if far_enough(p):
                chosen.append(p); break
    for _, p in pts.iterrows():                                # 2. fill with next largest, spaced apart
        if len(chosen) >= top_n:
            break
        if far_enough(p) and not any(p.name == c.name for c in chosen):
            chosen.append(p)
    sel = gpd.GeoDataFrame(chosen, crs=SVY21).to_crs(4326)
    out = pd.DataFrame({
        "site_id": [f"S{i + 1:02d}" for i in range(len(sel))],
        "name": [f"{s.title()} ({p.title()})" if s != p else s.title() for s, p in zip(sel.subzone, sel.planning_area)],
        "subzone": sel.subzone.str.title(), "planning_area": sel.planning_area, "region": sel.region,
        "b2_cluster_ha": sel.b2_ha.round(1),
        "latitude": sel.geometry.y.round(5), "longitude": sel.geometry.x.round(5),
        "site_status": "MP2019 Business 2 zoning; parcel availability, tenancy and permits NOT checked",
    }).sort_values(["region", "b2_cluster_ha"], ascending=[True, False]).reset_index(drop=True)
    out["site_id"] = [f"S{i + 1:02d}" for i in range(len(out))]
    out.to_csv(DATA / "candidate_sites.csv", index=False)
    record("candidate_sites", source=f"URA Master Plan 2019 Land Use layer, data.gov.sg {DS_LANDUSE}",
           rule=f"Contiguous BUSINESS 2 clusters (40 m merge); largest per region, then next largest >= "
                f"{min_spacing_km} km apart; islands excluded; top {top_n}",
           caveat="Zoning only; not vacant land, not approved sites")
    print(out[["site_id", "name", "region", "b2_cluster_ha"]].to_string(index=False))


FACILITY_QUERIES = [
    # (query, facility_type, role)
    ("Senoko Waste-to-Energy Plant", "waste-to-energy plant", "current fate: incineration with energy recovery"),
    ("Keppel Seghers Tuas Waste-to-Energy Plant", "waste-to-energy plant", "current fate: incineration with energy recovery"),
    ("TuasOne Waste-to-Energy Plant", "waste-to-energy plant", "current fate: incineration with energy recovery"),
    ("Tuas South Incineration Plant", "waste-to-energy plant", "current fate: incineration with energy recovery"),
    ("Tuas Nexus", "integrated waste & water facility", "context: IWMF under construction"),
    ("Gee Hoe Seng", "recycler / biochar seller", "context: local retail biochar supplier"),
    ("Gardens by the Bay", "biomass boiler (park trimmings)",
     "current fate: burns ~70% of its horticultural waste plus trimmings from other parks (CLC)"),
]


def step_facilities():
    rows = []
    for q, ftype, role in FACILITY_QUERIES:
        r = SESSION.get(NOMINATIM_URL, params={"q": q, "countrycodes": "sg", "format": "jsonv2", "limit": 1}, timeout=30)
        time.sleep(1.1)   # Nominatim usage policy: max 1 request / second
        hits = r.json() if r.ok else []
        if not hits:
            print(f"  not found in OSM: {q}")
            continue
        h = hits[0]
        rows.append({"name": h.get("name") or q, "query": q, "facility_type": ftype, "role": role,
                     "latitude": round(float(h["lat"]), 5), "longitude": round(float(h["lon"]), 5),
                     "osm_ref": f"{h['osm_type']}/{h['osm_id']}", "osm_display_name": h.get("display_name", "")})
    out = pd.DataFrame(rows)
    out.to_csv(DATA / "facilities.csv", index=False)
    record("facilities", source="OpenStreetMap via Nominatim (ODbL)", queries=[q for q, *_ in FACILITY_QUERIES],
           found=len(out), caveat="Names geocoded from OSM; biomass power plants not identified by name in OSM")
    print(out[["name", "facility_type", "osm_ref"]].to_string(index=False))


def step_roads(fallback_factor: float = 1.35):
    est = pd.read_csv(DATA / "planning_area_estimates.csv")
    sites = pd.read_csv(DATA / "candidate_sites.csv")
    fac = pd.read_csv(DATA / "facilities.csv") if (DATA / "facilities.csv").exists() else pd.DataFrame()
    origins = est[["planning_area", "route_lat", "route_lon", "is_island"]].rename(
        columns={"planning_area": "origin", "route_lat": "lat", "route_lon": "lon"})
    dests = pd.concat([sites[["site_id", "latitude", "longitude"]].rename(columns={"site_id": "destination"}),
                       fac[["name", "latitude", "longitude"]].rename(columns={"name": "destination"}) if len(fac) else None])
    dests = dests.rename(columns={"latitude": "lat", "longitude": "lon"}).reset_index(drop=True)
    coords = ";".join(f"{r.lon:.5f},{r.lat:.5f}" for r in pd.concat([origins, dests]).itertuples())
    n_o, n_d = len(origins), len(dests)
    params = {"sources": ";".join(map(str, range(n_o))), "destinations": ";".join(map(str, range(n_o, n_o + n_d))),
              "annotations": "distance,duration"}
    r = SESSION.get(OSRM_URL + coords, params=params, timeout=120)
    r.raise_for_status()
    js = r.json()
    if js.get("code") != "Ok":
        raise RuntimeError(f"OSRM error: {js.get('code')} {js.get('message')}")
    D, T = np.array(js["distances"], dtype=float), np.array(js["durations"], dtype=float)
    snap_o = [s.get("distance", np.nan) for s in js["sources"]]
    rows = []
    for i, o in origins.iterrows():
        for j, d in dests.iterrows():
            hv = float(haversine_km(o.lat, o.lon, d.lat, d.lon))
            ok = np.isfinite(D[i, j]) and not o.is_island and snap_o[i] < 2000
            rows.append({"origin": o.origin, "destination": d.destination,
                         "road_km": round(D[i, j] / 1000, 3) if ok else round(hv * fallback_factor, 3),
                         "duration_min": round(T[i, j] / 60, 1) if ok else np.nan,
                         "straight_km": round(hv, 3), "origin_snap_m": round(snap_o[i], 0),
                         "method": "OSRM road network" if ok else f"straight line x {fallback_factor} (island / unsnapped)"})
    out = pd.DataFrame(rows)
    out.to_csv(DATA / "road_distances.csv", index=False)
    ratio = (out.road_km / out.straight_km.where(out.straight_km > 1)).describe()
    record("road_distances", source="OSRM table service on OpenStreetMap roads (router.project-osrm.org; ODbL data)",
           origins="planning-area representative points (inside polygon), not collection depots",
           n_pairs=len(out), fallback=f"straight line x {fallback_factor} for islands or points >2 km from a road",
           median_road_to_straight_ratio=round(float(ratio["50%"]), 3))
    print(f"  {len(out)} pairs; road/straight-line ratio median {ratio['50%']:.2f} (IQR {ratio['25%']:.2f}-{ratio['75%']:.2f})")
    print(out.method.value_counts().to_string())


def step_fx():
    r = SESSION.get(ECB_URL, timeout=30)
    r.raise_for_status()
    day = re.search(r"time='([\d-]+)'", r.text).group(1)
    rate = {c: float(v) for c, v in re.findall(r"currency='([A-Z]{3})' rate='([\d.]+)'", r.text)}
    out = pd.DataFrame([{"date": day, "eur_usd": rate["USD"], "eur_sgd": rate["SGD"], "eur_gbp": rate["GBP"],
                         "usd_sgd": round(rate["SGD"] / rate["USD"], 4), "gbp_sgd": round(rate["SGD"] / rate["GBP"], 4),
                         "source": "ECB euro foreign exchange reference rates"}])
    PARAMS.mkdir(parents=True, exist_ok=True)
    out.to_csv(PARAMS / "fx.csv", index=False)
    record("fx", source="European Central Bank reference rates", url=ECB_URL, date=day)
    print(out.to_string(index=False))


def step_routes(sleep_s: float = 1.05):
    """Road geometry (OSRM route service, simplified) for every planning area -> candidate site pair, for the map's
    truck animation. ~550 requests at <= 1 per second (OSRM demo-server etiquette); resumable."""
    est = pd.read_csv(DATA / "planning_area_estimates.csv")
    sites = pd.read_csv(DATA / "candidate_sites.csv")
    out_file = DATA / "routes.json"
    routes = json.loads(out_file.read_text()) if out_file.exists() else {}
    todo = [(o, s) for o in est.itertuples() for s in sites.itertuples()
            if f"{o.planning_area}|{s.site_id}" not in routes]
    print(f"  {len(routes)} cached, {len(todo)} to fetch")
    for k, (o, s) in enumerate(todo):
        key = f"{o.planning_area}|{s.site_id}"
        url = (f"https://router.project-osrm.org/route/v1/driving/{o.route_lon:.5f},{o.route_lat:.5f};"
               f"{s.longitude:.5f},{s.latitude:.5f}")
        try:
            r = SESSION.get(url, params={"overview": "simplified", "geometries": "geojson"}, timeout=30)
            js = r.json() if r.ok else {}
            if js.get("code") == "Ok":
                coords = js["routes"][0]["geometry"]["coordinates"]
                routes[key] = [[round(x, 5), round(y, 5)] for x, y in coords]
            else:
                routes[key] = None   # e.g. islands: no road route
        except requests.RequestException:
            pass                     # retried on the next run
        if k % 25 == 0:
            out_file.write_text(json.dumps(routes, separators=(",", ":")))
        time.sleep(sleep_s)
    out_file.write_text(json.dumps(routes, separators=(",", ":")))
    record("routes", source="OSRM route service on OpenStreetMap roads (router.project-osrm.org; ODbL data)",
           n_pairs=len(routes), with_geometry=sum(v is not None for v in routes.values()),
           note="Simplified geometry, used only to animate trucks on the map")
    print(f"  {sum(v is not None for v in routes.values())} routes with geometry")


STEPS = {"geo": step_geo, "trees": step_trees, "landcover": step_landcover, "allocate": step_allocate,
         "sites": step_sites, "facilities": step_facilities, "roads": step_roads, "fx": step_fx, "routes": step_routes}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["all", *STEPS])
    args = ap.parse_args()
    for d in (RAW, GEO, PARAMS):
        d.mkdir(parents=True, exist_ok=True)
    for name in (STEPS if args.step == "all" else [args.step]):
        print(f"[{name}]")
        STEPS[name]()
