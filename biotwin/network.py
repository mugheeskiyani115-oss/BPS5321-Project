"""Supply network: road distances and times, LP allocation of feedstock to hubs, full evaluation of a layout.

A layout maps candidate site ids to plant size classes, e.g. {"S08": "C20", "S06": "S10"}.
Origins are the 55 planning areas; each supplies allocated tonnes x woody share x collectable share.
Haul cost per tonne comes from truck-day costing on OSRM road times; the LP minimises total haul cost subject to
origin supply and plant capacity while processing min(target, capacity, supply). A shortfall against the target is
reported as a constraint violation, never hidden.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linprog

from . import pathway as pw
from .data import Bundle


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.minimum(1, a)))


@dataclass
class Network:
    origins: pd.DataFrame        # planning_area, lat, lon, allocated_t, supply_t
    sites: pd.DataFrame          # site_id, name, region, latitude, longitude, rent
    dist_km: np.ndarray          # origins x sites, road km
    drive_min: np.ndarray        # origins x sites, OSRM drive minutes (car, free flow)
    haul_sgd_t: np.ndarray       # origins x sites, S$ per tonne
    road_share: float
    plants: pd.DataFrame
    a: pw.Assumptions

    @property
    def total_supply_t(self) -> float:
        return float(self.origins.supply_t.sum())


def build_network(b: Bundle, a: pw.Assumptions, allocated_t: np.ndarray | None = None,
                  extra_sites: pd.DataFrame | None = None) -> Network:
    areas = b.areas
    if allocated_t is None:
        allocated_t = areas.estimated_t.to_numpy(float) * a.national_t / areas.estimated_t.sum()
    allocated_t = np.asarray(allocated_t, float)
    if len(allocated_t) != len(areas) or (allocated_t < 0).any():
        raise ValueError("allocated tonnes must be one non-negative value per planning area")
    origins = pd.DataFrame({"planning_area": areas.planning_area, "region": areas.region,
                            "lat": areas.route_lat, "lon": areas.route_lon,
                            "display_lat": areas.latitude, "display_lon": areas.longitude,
                            "allocated_t": allocated_t,
                            "supply_t": allocated_t * a.woody_share * a.collectable_share})
    sites = b.sites.copy()
    if extra_sites is not None and len(extra_sites):
        extra = extra_sites.copy()
        if "rent_sgd_m2_yr_with_gst" not in extra:
            extra["rent_sgd_m2_yr_with_gst"] = float(np.median(b.sites.rent_sgd_m2_yr_with_gst))
        sites = pd.concat([sites, extra], ignore_index=True)
        if sites.site_id.duplicated().any():
            raise ValueError("custom site ids must be unique")

    straight = haversine_km(origins.lat.to_numpy()[:, None], origins.lon.to_numpy()[:, None],
                            sites.latitude.to_numpy()[None, :], sites.longitude.to_numpy()[None, :])
    dist = straight * a.road_factor_fallback
    is_road = np.zeros_like(dist, bool)
    minutes = np.full_like(dist, np.nan)
    speed_kmh = 52.8
    if b.roads is not None and len(b.roads):
        road = b.roads[b.roads.method.str.startswith("OSRM")] if "method" in b.roads else b.roads
        if "duration_min" in road and road.duration_min.gt(0).any():
            ok = road[road.duration_min > 0]
            speed_kmh = float(np.median(ok.road_km / (ok.duration_min / 60)))
        o_idx = {p: i for i, p in enumerate(origins.planning_area)}
        s_idx = {s: j for j, s in enumerate(sites.site_id)}
        for r in road.itertuples():
            i, j = o_idx.get(r.origin), s_idx.get(r.destination)
            if i is not None and j is not None:
                dist[i, j] = r.road_km
                minutes[i, j] = getattr(r, "duration_min", np.nan)
                is_road[i, j] = True
    minutes = np.where(np.isfinite(minutes) & (minutes > 0), minutes, dist / speed_kmh * 60)
    return Network(origins=origins, sites=sites.reset_index(drop=True), dist_km=dist, drive_min=minutes,
                   haul_sgd_t=pw.haul_cost_sgd_per_t(minutes, a), road_share=float(is_road.mean()),
                   plants=b.plants, a=a)


def _allocate_lp(cost: np.ndarray, supply: np.ndarray, caps: np.ndarray, total: float) -> np.ndarray:
    n, k = cost.shape
    rows_o = sparse.kron(sparse.eye(n), np.ones((1, k)))
    rows_s = sparse.kron(np.ones((1, n)), sparse.eye(k))
    A_ub = sparse.vstack([rows_o, rows_s]).tocsr()
    res = linprog(cost.ravel(), A_ub=A_ub, b_ub=np.concatenate([supply, caps]),
                  A_eq=sparse.csr_matrix(np.ones((1, n * k))), b_eq=[total], bounds=(0, None), method="highs")
    if not res.success:
        raise RuntimeError(f"Allocation LP failed: {res.message}")
    return res.x.reshape(n, k)


COST_KEYS = ["capex_annual_sgd", "labour_sgd", "maintenance_sgd", "land_sgd", "electricity_sgd", "haul_cost_sgd",
             "cert_sgd"]


def evaluate(net: Network, config: dict[str, str], with_flows: bool = False) -> dict:
    a = net.a
    open_sites = [(s, c) for s, c in config.items() if c]
    sid = {s: j for j, s in enumerate(net.sites.site_id)}
    unknown = [s for s, _ in open_sites if s not in sid]
    bad_class = [c for _, c in open_sites if c not in net.plants.index]
    if unknown or bad_class:
        raise ValueError(f"Unknown site ids {unknown} or plant classes {bad_class}")
    supply = net.origins.supply_t.to_numpy(float)
    if not open_sites:
        return _empty_result(a)

    idx = [sid[s] for s, _ in open_sites]
    plants = [net.plants.loc[c] for _, c in open_sites]
    rents = net.sites.rent_sgd_m2_yr_with_gst.iloc[idx].to_numpy(float)
    caps = np.array([pw.annual_capacity_t(p) for p in plants])
    processed = float(min(a.target_t, caps.sum(), supply.sum()))
    flow = (_allocate_lp(net.haul_sgd_t[:, idx], supply, caps, processed) if processed > 0
            else np.zeros((len(supply), len(idx))))
    site_t = flow.sum(axis=0)
    tkm = float((flow * net.dist_km[:, idx]).sum())
    haul_cost = float((flow * net.haul_sgd_t[:, idx]).sum())

    stored = processed * a.biochar_yield * a.stable_co2_per_t_biochar
    process = sum(t * pw.carbon_per_wet_t(a, p["carbon_class"])["process_emissions"] for t, p in zip(site_t, plants))
    haul_em = tkm * a.haul_ef_kg_per_tkm / 1000
    credit = stored - process - haul_em
    baseline = processed * a.baseline_avoided

    capex_annual = sum(pw.annual_capex_sgd(p, a) for p in plants)
    labour = sum(pw.labour_sgd_yr(p, a) for p in plants)
    maint = sum(pw.maintenance_sgd_yr(p, a) for p in plants)
    land = sum(pw.land_sgd_yr(p, a, r) for p, r in zip(plants, rents))
    elec = processed * pw.variable_sgd_per_t(a)
    cert = len(plants) * pw.cert_fixed_sgd_yr(a) if a.credits_enabled else 0.0
    product = processed * pw.product_revenue_sgd_per_t(a)
    credit_rev = max(credit, 0) * pw.credit_margin_sgd(a) if a.credits_enabled else 0.0
    cost = capex_annual + labour + maint + land + elec + haul_cost + cert
    revenue = product + credit_rev
    shortfall = max(a.target_t - processed, 0.0)

    per_site = pd.DataFrame({
        "site_id": [s for s, _ in open_sites], "name": net.sites.name.iloc[idx].to_numpy(),
        "size_class": [c for _, c in open_sites], "plant": [p["label"] for p in plants],
        "capacity_t": caps, "throughput_t": site_t, "utilisation": np.divide(site_t, caps, where=caps > 0),
        "capex_sgd": [pw.capex_sgd(p, a) for p in plants], "staff_fte": [pw.staff_fte(p, a) for p in plants],
        "land_rent_sgd_m2": rents,
        "latitude": net.sites.latitude.iloc[idx].to_numpy(), "longitude": net.sites.longitude.iloc[idx].to_numpy(),
    })
    out = {
        "config": dict(open_sites), "n_sites": len(open_sites), "processed_t": processed, "target_t": a.target_t,
        "shortfall_t": shortfall, "feasible": shortfall < 1e-6, "capacity_t": float(caps.sum()),
        "tonne_km": tkm, "mean_haul_km": tkm / processed if processed else 0.0,
        "biochar_t": processed * a.biochar_yield, "stored_co2_t": stored, "process_emissions_t": process,
        "haul_emissions_t": haul_em, "registry_credit_t": credit, "baseline_avoided_t": baseline,
        "net_climate_t": credit - baseline, "capex_total_sgd": float(per_site.capex_sgd.sum()),
        "capex_annual_sgd": capex_annual, "labour_sgd": labour, "maintenance_sgd": maint, "land_sgd": land,
        "electricity_sgd": elec, "haul_cost_sgd": haul_cost, "cert_sgd": cert, "staff_fte": float(per_site.staff_fte.sum()),
        "product_revenue_sgd": product, "credit_revenue_sgd": credit_rev, "cost_sgd": cost, "revenue_sgd": revenue,
        "net_cost_sgd": cost - revenue, "net_cost_sgd_per_t": (cost - revenue) / processed if processed else np.nan,
        "break_even_gate_fee_sgd_per_t": ((cost - revenue) / processed + a.gate_fee_sgd_per_t) if processed else np.nan,
        "per_site": per_site,
    }
    if with_flows:
        rows = [{"origin": net.origins.planning_area.iat[i], "site_id": open_sites[j][0], "tonnes": flow[i, j],
                 "road_km": net.dist_km[i, idx[j]], "haul_sgd_t": net.haul_sgd_t[i, idx[j]],
                 "o_lat": net.origins.display_lat.iat[i], "o_lon": net.origins.display_lon.iat[i],
                 "s_lat": per_site.latitude.iat[j], "s_lon": per_site.longitude.iat[j]}
                for i, j in zip(*np.nonzero(flow > 1e-3))]
        out["flows"] = pd.DataFrame(rows)
    return out


def _empty_result(a: pw.Assumptions) -> dict:
    zero = {k: 0.0 for k in ["processed_t", "capacity_t", "tonne_km", "mean_haul_km", "biochar_t", "stored_co2_t",
                             "process_emissions_t", "haul_emissions_t", "registry_credit_t", "baseline_avoided_t",
                             "net_climate_t", "capex_total_sgd", "staff_fte", "product_revenue_sgd",
                             "credit_revenue_sgd", "cost_sgd", "revenue_sgd", "net_cost_sgd", *COST_KEYS]}
    return {**zero, "config": {}, "n_sites": 0, "target_t": a.target_t, "shortfall_t": a.target_t, "feasible": False,
            "net_cost_sgd_per_t": np.nan, "break_even_gate_fee_sgd_per_t": np.nan,
            "per_site": pd.DataFrame(), "flows": pd.DataFrame()}


def smallest_single_plant(net: Network) -> str | None:
    caps = net.plants.apply(pw.annual_capacity_t, axis=1).sort_values()
    ok = caps[caps >= net.a.target_t]
    return ok.index[0] if len(ok) else None
