"""Per-wet-tonne carbon ledger and itemised Singapore plant economics for pyrolysis to biochar.

Carbon (Notebook 2 values; three quantities kept separate):
  stored carbon        = biochar yield x stable CO2 per tonne of biochar
  registry credit      = stored - process emissions - haul emissions
  net vs current use   = registry credit - emissions already avoided by today's fate (biomass power / WtE)

Plant cost (one basis, itemised from Singapore data; see data/params/parameters.csv):
  capex annuity   = turnkey capex (vendor, mid-range) x (1 + pre-processing uplift) x capital recovery factor
  labour          = crews to cover operating hours (MOM wages + employer CPF, Employment Act 44 h week)
  maintenance     = share of capex per year (Trollip et al. 2025)
  land            = site area x JTC posted land rent at that site
  electricity     = kWh per tonne (US DOE FCIC) x SP Group tariff        (the only per-tonne running cost)
Why this basis: generic vendor opex (US$30-90/t) leaves out Singapore wages and land; the research PDF's Singapore
range has no source. The itemised estimate uses sourced Singapore inputs and lands inside the PDF range for
continuous plants, which is a useful cross-check (see cost_basis_check()).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .data import Bundle

GST = 1.09


@dataclass(frozen=True)
class Assumptions:
    # feedstock
    woody_share: float = 0.70
    collectable_share: float = 0.25
    target_t: float = 9000.0
    national_t: float = 232_000.0
    # carbon (Notebook 2)
    biochar_yield: float = 0.165
    stable_co2_per_t_biochar: float = 2.2545
    process_emissions: float = 0.134
    small_kiln_extra: float = 0.114
    baseline_avoided: float = 0.243
    haul_ef_kg_per_tkm: float = 0.19748
    # product & credits
    biochar_price_usd: float = 100.0
    gate_fee_sgd_per_t: float = 0.0
    credits_enabled: bool = False
    credit_price_eur: float = 120.67
    puro_fee_eur_per_corc: float = 8.48
    puro_annual_fee_eur: float = 1400.0
    verification_gbp_per_year: float = 7500.0
    validation_gbp_once: float = 13000.0
    # finance & FX
    discount_rate: float = 0.08
    life_years: int = 15
    preprocessing_uplift: float = 0.20
    usd_sgd: float = 1.2881
    eur_sgd: float = 1.4236
    gbp_sgd: float = 1.7037
    # labour & O&M
    operator_wage: float = 4168.0
    worker_wage: float = 2692.0
    supervisor_wage: float = 4312.0
    employer_cpf: float = 0.17
    normal_hours: float = 44.0
    leave_allowance: float = 1.07
    labour_exponent: float = 0.25
    capital_grant_fraction: float = 0.0  # 0-50%; illustrative grant, NOT awarded
    illustrative_tax_rate: float = 0.0  # 0 or a modelled income-tax sensitivity
    continuous_crew_per_shift: float = 0.0  # 0 uses existing size-scaled model; >0 is scenario assumption
    seasonal_woody_amplitude: float = 0.0  # sensitivity only, not measured monthly tonnes
    woody_share_uncertainty_sd: float = 0.05  # hypothetical standard deviation of composition draws
    electricity_kwh_per_t: float = 60.0
    electricity_price: float = 0.2859
    maintenance_share: float = 0.08
    site_fixed_area_m2: float = 300.0
    storage_days: float = 7.0
    stack_height_m: float = 3.0
    access_allowance: float = 1.5
    feed_bulk_density: float = 0.2076
    # haulage
    tipper_day_rate: float = 800.0
    truck_body_m3: float = 20.0
    truck_hours: float = 8.0
    handling_h: float = 0.5
    truck_time_factor: float = 1.3
    road_factor_fallback: float = 1.35

    def __post_init__(self):
        checks = {
            "woody_share": 0 < self.woody_share <= 1, "collectable_share": 0 < self.collectable_share <= 1,
            "target_t": self.target_t > 0, "national_t": self.national_t > 0,
            "biochar_yield": 0 < self.biochar_yield < 1, "discount_rate": 0 <= self.discount_rate < 1,
            "life_years": self.life_years >= 1, "fx": min(self.usd_sgd, self.eur_sgd, self.gbp_sgd) > 0,
            "gate_fee": self.gate_fee_sgd_per_t >= 0, "truck": self.truck_hours > self.handling_h > 0,
            "capital_grant_fraction": 0 <= self.capital_grant_fraction <= 0.5,
            "illustrative_tax_rate": 0 <= self.illustrative_tax_rate <= 0.25,
            "continuous_crew_per_shift": 0 <= self.continuous_crew_per_shift <= 12,
            "seasonal_woody_amplitude": 0 <= self.seasonal_woody_amplitude <= 0.2,
            "woody_share_uncertainty_sd": 0 <= self.woody_share_uncertainty_sd <= 0.15,
        }
        bad = [k for k, ok in checks.items() if not ok]
        if bad:
            raise ValueError(f"Out-of-range assumptions: {', '.join(bad)}")

    def key(self) -> tuple:
        return tuple(sorted(asdict(self).items()))

    @property
    def payload_t(self) -> float:
        return self.truck_body_m3 * self.feed_bulk_density


PARAM_MAP = {
    "woody_share": "woody_share", "collectable_share": "collectable_share", "national_t": "national_waste_2025_t",
    "biochar_yield": "biochar_yield_t_per_wet_t", "stable_co2_per_t_biochar": "stable_co2_per_t_biochar",
    "process_emissions": "process_emissions_industrial", "small_kiln_extra": "small_kiln_extra_emissions",
    "baseline_avoided": "baseline_avoided", "haul_ef_kg_per_tkm": "haul_ef_kg_per_tkm",
    "biochar_price_usd": "biochar_price_usd", "credit_price_eur": "corc_spot_eur",
    "puro_fee_eur_per_corc": "puro_fee_eur_per_corc", "puro_annual_fee_eur": "puro_annual_fee_eur",
    "verification_gbp_per_year": "verification_gbp_per_year", "validation_gbp_once": "validation_gbp_once",
    "discount_rate": "discount_rate", "life_years": "plant_life_years", "preprocessing_uplift": "preprocessing_capex_uplift",
    "operator_wage": "operator_wage_sgd_month", "worker_wage": "worker_wage_sgd_month",
    "supervisor_wage": "supervisor_wage_sgd_month", "employer_cpf": "employer_cpf_rate",
    "normal_hours": "normal_hours_per_week", "leave_allowance": "leave_allowance",
    "labour_exponent": "labour_scaling_exponent", "electricity_kwh_per_t": "electricity_kwh_per_t",
    "electricity_price": "electricity_price_sgd_kwh", "maintenance_share": "maintenance_share_capex",
    "site_fixed_area_m2": "site_fixed_area_m2", "storage_days": "storage_days", "stack_height_m": "stack_height_m",
    "access_allowance": "access_allowance", "feed_bulk_density": "feed_bulk_density_t_m3",
    "tipper_day_rate": "tipper_day_rate_sgd", "truck_body_m3": "truck_body_m3", "truck_hours": "truck_hours_per_day",
    "handling_h": "truck_handling_h_per_trip", "truck_time_factor": "truck_time_factor",
    "road_factor_fallback": "road_factor_fallback",
}


def default_assumptions(b: Bundle, **overrides) -> Assumptions:
    """Every default from the parameter register and the ECB exchange rates; no alternative bases."""
    base = {field: b.p(key) for field, key in PARAM_MAP.items()}
    base["life_years"] = int(base["life_years"])
    base.update(usd_sgd=float(b.fx["usd_sgd"]), eur_sgd=float(b.fx["eur_sgd"]), gbp_sgd=float(b.fx["gbp_sgd"]))
    base.update(overrides)
    return Assumptions(**base)


# ----------------------------------------------------------------------------- carbon
def carbon_per_wet_t(a: Assumptions, carbon_class: str = "industrial", haul_tkm_per_t: float = 0.0) -> dict:
    stored = a.biochar_yield * a.stable_co2_per_t_biochar
    process = a.process_emissions + (a.small_kiln_extra if carbon_class == "small" else 0.0)
    haul = haul_tkm_per_t * a.haul_ef_kg_per_tkm / 1000
    credit = stored - process - haul
    return {"biochar_t": a.biochar_yield, "stored_co2": stored, "process_emissions": process,
            "haul_emissions": haul, "registry_credit": credit, "baseline_avoided": a.baseline_avoided,
            "net_vs_current_use": credit - a.baseline_avoided}


# ----------------------------------------------------------------------------- plant economics
def crf(rate: float, years: int) -> float:
    if rate <= 0:
        return 1 / years
    g = (1 + rate) ** years
    return rate * g / (g - 1)


def annual_capacity_t(plant: pd.Series) -> float:
    return float(plant["capacity_tpd"]) * 365 * float(plant["availability"])


def capex_sgd(plant: pd.Series, a: Assumptions) -> float:
    turnkey = (float(plant["turnkey_usd_low"]) + float(plant["turnkey_usd_high"])) / 2
    return turnkey * (1 + a.preprocessing_uplift) * a.usd_sgd


def annual_capex_sgd(plant: pd.Series, a: Assumptions) -> float:
    return capex_sgd(plant, a) * crf(a.discount_rate, a.life_years)


def workers_per_shift(plant: pd.Series, a: Assumptions) -> float:
    # Technology-specific assumption, not a validated supplier crew roster.
    technology = str(plant.get("technology", "")).lower()
    if a.continuous_crew_per_shift > 0 and "continuous" in technology:
        return a.continuous_crew_per_shift
    w = float(plant["workers_per_shift"])
    if str(plant.get("labour_scaling", "rule")) == "linear":
        return w
    return w * (float(plant["capacity_tpd"]) / 10) ** a.labour_exponent


def staff_fte(plant: pd.Series, a: Assumptions) -> float:
    staffed_hours = 168 * float(plant["availability"])
    return workers_per_shift(plant, a) * staffed_hours / a.normal_hours * a.leave_allowance


def labour_sgd_yr(plant: pd.Series, a: Assumptions) -> float:
    w = workers_per_shift(plant, a)
    crew_wage = (a.operator_wage + max(w - 1, 0) * a.worker_wage) / max(w, 1)
    sup = a.supervisor_wage * 12 * (1 + a.employer_cpf) if int(plant.get("has_supervisor", 0)) else 0.0
    return staff_fte(plant, a) * crew_wage * 12 * (1 + a.employer_cpf) + sup


def land_area_m2(plant: pd.Series, a: Assumptions) -> float:
    storage = a.storage_days * float(plant["capacity_tpd"]) / a.feed_bulk_density / a.stack_height_m
    return a.site_fixed_area_m2 + storage * a.access_allowance


def land_sgd_yr(plant: pd.Series, a: Assumptions, rent_with_gst: float) -> float:
    return land_area_m2(plant, a) * rent_with_gst / GST


def maintenance_sgd_yr(plant: pd.Series, a: Assumptions) -> float:
    return capex_sgd(plant, a) * a.maintenance_share


def fixed_om_sgd_yr(plant: pd.Series, a: Assumptions, rent_with_gst: float) -> float:
    return labour_sgd_yr(plant, a) + maintenance_sgd_yr(plant, a) + land_sgd_yr(plant, a, rent_with_gst)


def variable_sgd_per_t(a: Assumptions) -> float:
    return a.electricity_kwh_per_t * a.electricity_price


def product_revenue_sgd_per_t(a: Assumptions) -> float:
    return a.biochar_yield * a.biochar_price_usd * a.usd_sgd + a.gate_fee_sgd_per_t


def credit_margin_sgd(a: Assumptions) -> float:
    """Revenue per credit sold after the registry's per-credit fee."""
    return (a.credit_price_eur - a.puro_fee_eur_per_corc) * a.eur_sgd


def cert_fixed_sgd_yr(a: Assumptions) -> float:
    """Per certified plant: registry annual fee + annual verification + validation spread over plant life."""
    return (a.puro_annual_fee_eur * a.eur_sgd + a.verification_gbp_per_year * a.gbp_sgd
            + a.validation_gbp_once * a.gbp_sgd * crf(a.discount_rate, a.life_years))


def haul_cost_sgd_per_t(drive_min: np.ndarray | float, a: Assumptions) -> np.ndarray:
    """Truck-day costing: day rate / (payload x trips per day); a trip = out + back + handling."""
    trip_h = 2 * np.asarray(drive_min, float) / 60 * a.truck_time_factor + a.handling_h
    trips = np.maximum(a.truck_hours / trip_h, 1e-6)
    return a.tipper_day_rate / (a.payload_t * trips)


def plant_cost_table(b: Bundle, a: Assumptions, rent_with_gst: float | None = None,
                     utilisation: float = 1.0) -> pd.DataFrame:
    """Itemised cost per wet tonne for one plant of each size at `utilisation` of capacity."""
    rent = float(np.median(b.sites.rent_sgd_m2_yr_with_gst)) if rent_with_gst is None else rent_with_gst
    rows = []
    for sc, p in b.plants.iterrows():
        t = annual_capacity_t(p) * utilisation
        c = carbon_per_wet_t(a, p["carbon_class"])
        items = {"capex": annual_capex_sgd(p, a), "labour": labour_sgd_yr(p, a), "maintenance": maintenance_sgd_yr(p, a),
                 "land": land_sgd_yr(p, a, rent)}
        per_t = {f"{k}_sgd_per_t": v / t for k, v in items.items()}
        per_t["electricity_sgd_per_t"] = variable_sgd_per_t(a)
        cost = sum(per_t.values())
        rev = product_revenue_sgd_per_t(a)
        if a.credits_enabled:
            rev += max(c["registry_credit"], 0) * credit_margin_sgd(a) - cert_fixed_sgd_yr(a) / t
        rows.append({"size_class": sc, "label": p["label"], "technology": p["technology"],
                     "capacity_tpd": p["capacity_tpd"], "annual_t": t, "capex_sgd": capex_sgd(p, a),
                     "staff_fte": staff_fte(p, a), "land_m2": land_area_m2(p, a), **per_t,
                     "opex_sgd_per_t": cost - per_t["capex_sgd_per_t"], "cost_sgd_per_t": cost,
                     "revenue_sgd_per_t": rev, "margin_sgd_per_t": rev - cost,
                     "registry_credit_t_per_t": c["registry_credit"],
                     "break_even_gate_fee_sgd_per_t": max(cost - (rev - a.gate_fee_sgd_per_t), 0.0)})
    return pd.DataFrame(rows)


def cost_basis_check(b: Bundle, a: Assumptions) -> pd.DataFrame:
    """Itemised Singapore opex (US$/t, excl. capex) next to the vendor and research-PDF ranges."""
    t = plant_cost_table(b, a)
    rows = []
    for r in t.itertuples():
        cont = "continuous" in r.technology or r.technology == "semi-continuous"
        bench = b.benchmarks.set_index(["benchmark", "technology"])
        v = bench.loc[("Vendor generic", "continuous" if cont else "batch")]
        s = bench.loc[("Research PDF Singapore", "continuous" if cont else "batch (high fixed carbon)")]
        rows.append({"Plant": r.label, "This model (US$/t)": r.opex_sgd_per_t / a.usd_sgd,
                     "Vendor generic (US$/t)": f"{v.usd_per_t_low:.0f}-{v.usd_per_t_high:.0f}",
                     "Research PDF Singapore (US$/t)": f"{s.usd_per_t_low:.0f}-{s.usd_per_t_high:.0f}",
                     "Labour share of opex": r.labour_sgd_per_t / r.opex_sgd_per_t})
    return pd.DataFrame(rows)


def break_evens(b: Bundle, a: Assumptions, size_class: str, rent_with_gst: float | None = None) -> dict:
    """Each alone: gate fee, biochar price or credit price that brings one full plant's margin to zero."""
    row = plant_cost_table(b, a.__class__(**{**asdict(a), "credits_enabled": False}), rent_with_gst) \
        .set_index("size_class").loc[size_class]
    p = b.plants.loc[size_class]
    t = annual_capacity_t(p)
    cost = row.cost_sgd_per_t
    product = a.biochar_yield * a.biochar_price_usd * a.usd_sgd
    credit_t = carbon_per_wet_t(a, p["carbon_class"])["registry_credit"]
    gap = cost - product - a.gate_fee_sgd_per_t
    credit_be = ((gap + cert_fixed_sgd_yr(a) / t) / (credit_t * a.eur_sgd) + a.puro_fee_eur_per_corc
                 if credit_t > 0 else np.inf)
    return {"cost_sgd_per_t": cost, "gate_fee_sgd_per_t": max(cost - product, 0.0),
            "biochar_usd_per_t": max((cost - a.gate_fee_sgd_per_t) / (a.biochar_yield * a.usd_sgd), 0.0),
            "credit_eur_per_tco2e": max(credit_be, 0.0)}
