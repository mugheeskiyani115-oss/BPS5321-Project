"""BioTwin: transparent illustrative planning calculations.

Purpose: screen five **illustrative regional hub anchors** against regional feedstock
PROXY estimates. No operator validation, actual candidate site approval, road
network, carbon certification, or verified engineering quotations is implied.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import asin, cos, radians, sin, sqrt
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import linprog


@dataclass(frozen=True)
class Scenario:
    throughput_t_per_day: float = 30.0
    operating_days: int = 300
    accessible_fraction: float = 0.10  # assumption: fraction of spatial waste proxy actually collectable
    road_distance_multiplier: float = 1.35  # assumption, NOT routing on the road network
    first_last_mile_km: float = 5.0  # assumption, region centroid misses local collection routes
    transport_cost_sgd_per_tkm: float = 0.30  # illustrative, not a haulier quote
    transport_emissions_kgco2e_per_tkm: float = 0.12  # illustrative, not a fleet inventory
    processing_cost_sgd_per_t: float = 310.0  # original interim worked-case headline
    additional_hub_cost_sgd_per_year: float = 50_000.0  # incremental siting overhead assumption
    product_revenue_sgd_per_t: float = 92.0  # original interim worked-case total revenue
    gate_fee_sgd_per_t: float = 0.0
    stored_co2_t_per_wet_t: float = 0.372  # original pyrolysis worked case
    process_emission_t_per_wet_t: float = 0.100  # EXAMPLE split of unverified 0.277 debit
    baseline_opportunity_debit_t_per_wet_t: float = 0.177  # EXAMPLE split, not observed
    assume_credit_eligible: bool = False
    assumed_issued_credit_t_per_wet_t: float = 0.0  # assumed, never inferred from storage or benefit
    credit_price_sgd_per_tco2e: float = 0.0

    @property
    def annual_t(self) -> float:
        return self.throughput_t_per_day * self.operating_days


def haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Great-circle centroid distance; does not represent Singapore road distances."""
    dlat, dlon = radians(lat_b - lat_a), radians(lon_b - lon_a)
    a = sin(dlat / 2)**2 + cos(radians(lat_a))*cos(radians(lat_b))*sin(dlon / 2)**2
    return 6371.0088 * 2 * asin(min(1, sqrt(a)))


def load_region_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {'region', 'estimated_t', 'latitude', 'longitude'}
    missing = required.difference(df)
    if missing:
        raise ValueError(f'Regional input missing: {sorted(missing)}')
    if df['region'].duplicated().any():
        raise ValueError('Region identifiers must be unique')
    if df['estimated_t'].isna().any() or (df['estimated_t'] < 0).any():
        raise ValueError('Feedstock must be nonnegative and present')
    if df[['latitude', 'longitude']].isna().any().any():
        raise ValueError('Location proxies are required')
    return df


def load_optional_planning_areas(path: str, region_default: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Use 55 planning areas if the *user* regenerated the spatial notebook export.

    If not present, return honest five-region approximation. A planning area file
    must include columns: planning_area, region, estimated_t, latitude, longitude.
    """
    from pathlib import Path
    if not Path(path).exists():
        return region_default.rename(columns={'region': 'origin_name'}).copy(), '5-region saved EDA aggregation'
    df = pd.read_csv(path)
    need = {'planning_area', 'region', 'estimated_t', 'latitude', 'longitude'}
    if not need.issubset(df.columns):
        raise ValueError(f'Planning area input must contain {sorted(need)}')
    df = df.rename(columns={'planning_area': 'origin_name'})
    if df['estimated_t'].isna().any() or (df['estimated_t'] < 0).any():
        raise ValueError('Planning area estimates must be nonnegative')
    return df, f'{len(df)} planning areas from notebook export'


def solve_plan(origins: pd.DataFrame, hubs: pd.DataFrame,
               selected_regions: Iterable[str], cfg: Scenario) -> dict:
    """Allocate one annual throughput across equal-capacity illustrative hub anchors.

    An LP minimizes tonne-km subject to regional availability and hub capacity.
    Unlike NSGA-II, this is a deterministic *single-objective* assignment used
    within exhaustive enumeration of the small candidate-site set.
    """
    chosen = tuple(sorted(set(selected_regions)))
    if not chosen:
        raise ValueError('Select at least one candidate hub anchor')
    if cfg.annual_t <= 0 or cfg.accessible_fraction <= 0:
        raise ValueError('Annual throughput and accessible fraction must be positive')
    h = hubs.set_index('region').loc[list(chosen)].reset_index()
    a = origins.reset_index(drop=True)
    supply = a['estimated_t'].to_numpy(float) * cfg.accessible_fraction
    if supply.sum() + 1e-5 < cfg.annual_t:
        raise ValueError('Assumed accessible tonnes cannot support selected throughput')
    n, m = len(a), len(h)
    # spatial approximation: centroid-to-anchor great-circle distance times an
    # assumed road uplift, PLUS a uniform first/last mile collection allowance
    dist = np.array([[cfg.first_last_mile_km + cfg.road_distance_multiplier * haversine_km(
        float(r.latitude), float(r.longitude), float(site.latitude), float(site.longitude))
        for site in h.itertuples()] for r in a.itertuples()])
    # hub throughput fixed to total/m: keeps central and distributed cases like for like.
    A_eq = np.zeros((m, n*m))
    for j in range(m):
        A_eq[j, np.arange(n)*m+j] = 1
    A_ub = np.zeros((n, n*m))
    for i in range(n):
        A_ub[i, i*m:(i+1)*m] = 1
    res = linprog(dist.ravel(), A_ub=A_ub, b_ub=supply,
                  A_eq=A_eq, b_eq=np.repeat(cfg.annual_t/m, m),
                  bounds=(0, None), method='highs')
    if not res.success:
        raise RuntimeError(f'Allocation optimizer failed: {res.message}')
    flow = res.x.reshape(n, m)
    annual_tkm = float((flow * dist).sum())
    annual_transport_cost = annual_tkm * cfg.transport_cost_sgd_per_tkm
    annual_transport_emissions_t = annual_tkm * cfg.transport_emissions_kgco2e_per_tkm / 1000
    processed = cfg.annual_t
    stored = processed * cfg.stored_co2_t_per_wet_t
    process = processed * cfg.process_emission_t_per_wet_t
    opportunity = processed * cfg.baseline_opportunity_debit_t_per_wet_t
    net_climate = stored - process - opportunity - annual_transport_emissions_t
    credits = (processed * cfg.assumed_issued_credit_t_per_wet_t if cfg.assume_credit_eligible else 0)
    sales = processed * cfg.product_revenue_sgd_per_t
    gate = processed * cfg.gate_fee_sgd_per_t
    credit_revenue = credits * cfg.credit_price_sgd_per_tco2e
    processing_cost = processed * cfg.processing_cost_sgd_per_t
    additional_hub_cost = len(chosen) * cfg.additional_hub_cost_sgd_per_year
    cost = processing_cost + additional_hub_cost + annual_transport_cost
    revenue = sales + gate + credit_revenue
    breakdown = pd.DataFrame([
        {'origin': a.loc[i, 'origin_name'] if 'origin_name' in a.columns else a.loc[i, 'region'],
         'hub': chosen[j], 'tonnes': round(float(flow[i, j]), 3),
         'approx_km': round(float(dist[i, j]), 2),
         'tonne_km': round(float(flow[i, j] * dist[i, j]), 2)}
        for i in range(n) for j in range(m) if flow[i, j] > 0.001
    ])
    return {
        'sites': chosen, 'n_hubs': m, 'annual_t': processed,
        'tonne_km': annual_tkm, 'avg_haul_km': annual_tkm/processed,
        'transport_cost_sgd': annual_transport_cost,
        'transport_emissions_t': annual_transport_emissions_t,
        'gross_stored_co2_t': stored, 'process_emissions_t': process,
        'baseline_opportunity_debit_t': opportunity,
        'net_climate_benefit_t': net_climate,
        'assumed_credit_issued_t': credits,
        'carbon_credit_revenue_sgd': credit_revenue,
        'revenue_sgd': revenue, 'cost_sgd': cost,
        'margin_sgd': revenue-cost,
        'margin_sgd_per_t': (revenue-cost)/processed,
        'break_even_gate_sgd_per_t': (cost - sales - credit_revenue)/processed,
        'flows': breakdown,
    }


def enumerate_plans(origins: pd.DataFrame, hubs: pd.DataFrame, cfg: Scenario,
                    max_hubs: int | None = None) -> tuple[pd.DataFrame, list[dict]]:
    """Complete enumeration of 2^5-1 small site subsets; explicitly NOT NSGA-II."""
    options = []
    available = list(hubs.region)
    for size in range(1, min(max_hubs or len(available), len(available)) + 1):
        for selected in combinations(available, size):
            options.append(solve_plan(origins, hubs, selected, cfg))
    # A plan is Pareto efficient when no other has both <= cost and >= benefit
    # with one strict improvement; cost here is cash cost, excluding revenue.
    tab = pd.DataFrame([{'sites': ', '.join(p['sites']), 'n_hubs': p['n_hubs'],
                         'cost_sgd': p['cost_sgd'], 'margin_sgd': p['margin_sgd'],
                         'net_climate_t': p['net_climate_benefit_t'],
                         'mean_haul_km': p['avg_haul_km']} for p in options])
    is_pareto = []
    for i, r in tab.iterrows():
        dominates = ((tab.cost_sgd <= r.cost_sgd + 1e-7) &
                     (tab.net_climate_t >= r.net_climate_t - 1e-7) &
                     ((tab.cost_sgd < r.cost_sgd - 1e-7) |
                      (tab.net_climate_t > r.net_climate_t + 1e-7)))
        is_pareto.append(not bool(dominates.any()))
    tab['pareto'] = is_pareto
    return tab.sort_values(['n_hubs', 'cost_sgd']).reset_index(drop=True), options


def validate_operator_data(regions: pd.DataFrame, observed: pd.DataFrame) -> dict:
    """Only *real uploaded records* can provide empirical feedstock validation.

    Do not compute a WAPE from the weight sensitivity bounds or tree proxy itself.
    """
    expected = {'region', 'observed_t', 'year', 'source'}
    if not expected.issubset(observed.columns):
        raise ValueError(f'Validation CSV requires: {sorted(expected)}')
    d = observed.copy()
    d = d.loc[pd.to_numeric(d.year, errors='coerce').eq(2025)].copy()
    d['observed_t'] = pd.to_numeric(d.observed_t, errors='coerce')
    d = d.dropna(subset=['observed_t', 'source'])
    d = d[d['source'].astype(str).str.strip().ne('')]
    d = d[d.observed_t >= 0]
    if not len(d) or d['region'].duplicated().any():
        raise ValueError('Provide one nonnegative independent observed record per region for 2025')
    joined = regions.merge(d[['region', 'observed_t', 'source']], on='region', how='inner')
    if not len(joined) or joined.observed_t.sum() <= 0:
        raise ValueError('No matching independent observed tonnage records')
    joined['error_t'] = joined.estimated_t - joined.observed_t
    wape = joined.error_t.abs().sum() / joined.observed_t.sum()
    rho = joined[['estimated_t', 'observed_t']].corr(method='spearman').iloc[0, 1] if len(joined) >= 3 else np.nan
    return {'compared': len(joined), 'coverage': len(joined) / len(regions),
            'wape': float(wape), 'rank_spearman': float(rho), 'comparison': joined}
