"""BioTwin Singapore web server: JSON API over the `biotwin` model + the static JavaScript front end.

Run:  python -m uvicorn api.server:app --port 8000      (then open http://localhost:8000)

Endpoints
  GET  /api/meta       regions, sites, plants, facilities, planning areas, input defaults
  GET  /api/geo        planning-area polygons (GeoJSON) for the 3D map
  POST /api/evaluate   run one scenario -> outputs, pro forma, business as usual, findings, comparisons, flows
  GET  /api/evidence   parameter register, waste-data check
  POST /api/validate   compare uploaded independent tonnages with the estimates
"""
from __future__ import annotations

import io
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from biotwin import evaluate as E
from biotwin import forecast as fc
from biotwin import pathway as pw
from biotwin import validation as vd
from biotwin.data import DATA, load_bundle

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

app = FastAPI(title="BioTwin Singapore", version="1.0")
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ----------------------------------------------------------------------------- helpers
def clean(x):
    """Make numpy / pandas values JSON-safe (NaN and inf become null)."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, pd.DataFrame):
        return [clean(r) for r in x.to_dict(orient="records")]
    if isinstance(x, pd.Series):
        return clean(x.to_dict())
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        v = float(x)
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.ndarray):
        return clean(x.tolist())
    return x


@lru_cache(maxsize=1)
def bundle():
    return load_bundle()


@lru_cache(maxsize=1)
def routes() -> dict:
    f = DATA / "routes.json"
    return json.loads(f.read_text()) if f.exists() else {}


# ----------------------------------------------------------------------------- metadata
@lru_cache(maxsize=1)
def _meta() -> dict:
    b = bundle()
    a = pw.default_assumptions(b)
    costs = pw.plant_cost_table(b, a).set_index("size_class")
    supply = b.areas.estimated_t.to_numpy() * a.woody_share * a.collectable_share
    reg = b.params
    adv = {}
    for f, (label, unit, lo, hi, step) in E.ADVANCED.items():
        key = {"credit_price_eur": "corc_spot_eur", "life_years": "plant_life_years"}.get(f, f)
        adv[f] = {"label": label, "unit": unit, "min": lo, "max": hi, "step": step, "default": getattr(a, f),
                  "source": reg.at[key, "source"] if key in reg.index else ""}
    s = fc.national_series(b)
    return clean({
        "regions": list(E.REGIONS),
        "sites": b.sites[["site_id", "name", "region", "latitude", "longitude", "rent_sgd_m2_yr_with_gst",
                          "jtc_estate"]].rename(columns={"rent_sgd_m2_yr_with_gst": "rent"}),
        "plants": [{"size_class": sc, "label": p["label"], "capacity_tpd": p["capacity_tpd"],
                    "technology": p["technology"], "carbon_class": p["carbon_class"],
                    "annual_t": costs.at[sc, "annual_t"], "capex_sgd": costs.at[sc, "capex_sgd"],
                    "staff": costs.at[sc, "staff_fte"], "cost_sgd_per_t": costs.at[sc, "cost_sgd_per_t"]}
                   for sc, p in b.plants.iterrows()],
        "facilities": b.facilities[["name", "facility_type", "latitude", "longitude"]] if len(b.facilities) else [],
        "areas": pd.DataFrame({"planning_area": b.areas.planning_area, "region": b.areas.region,
                               "lat": b.areas.latitude, "lon": b.areas.longitude, "woody_available_t": supply,
                               "estimated_t": b.areas.estimated_t}),
        "advanced": adv,
        "gate_fee_cap_sgd": b.p("gate_fee_cap_sgd"),
        "national": {"waste_2025_t": b.p("national_waste_2025_t"), "woody_share": a.woody_share,
                     "collectable_share": a.collectable_share,
                     "series": [{"year": int(y), "t": float(v)} for y, v in s.items()]},
        "fx": b.fx, "fingerprint": b.fingerprint,
    })


@app.get("/api/meta")
def meta():
    return JSONResponse(_meta(), headers={"Cache-Control": "max-age=300"})


@app.get("/api/geo")
def geo():
    b = bundle()
    if b.geojson is None:
        raise HTTPException(404, "planning-area polygons not available")
    return JSONResponse(b.geojson, headers={"Cache-Control": "max-age=3600"})


# ----------------------------------------------------------------------------- evaluation
class EvalRequest(BaseModel):
    region: str = "All"
    sites: list[str] = Field(default_factory=list, max_length=10)
    size: str | None = None
    gate_fee: float = Field(0.0, ge=0, le=500)
    sell_credits: bool = False
    advanced: dict[str, float] = Field(default_factory=dict)


def _scenario(req: EvalRequest) -> E.Scenario:
    b = bundle()
    if req.region not in ("All", *E.REGIONS):
        raise HTTPException(400, f"Unknown region '{req.region}'")
    known = set(b.sites.site_id)
    bad = [s for s in req.sites if s not in known]
    if bad:
        raise HTTPException(400, f"Unknown site(s): {bad}")
    if req.size is not None and req.size not in b.plants.index:
        raise HTTPException(400, f"Unknown plant size '{req.size}'")
    adv = []
    for f, v in req.advanced.items():
        if f not in E.ADVANCED:
            raise HTTPException(400, f"Unknown advanced input '{f}'")
        _, _, lo, hi, _ = E.ADVANCED[f]
        if not (lo <= v <= hi):
            raise HTTPException(400, f"{E.ADVANCED[f][0]} must be between {lo} and {hi}")
        adv.append((f, int(v) if f == "life_years" else float(v)))
    return E.Scenario(sites=tuple(dict.fromkeys(req.sites)), size_class=req.size, region=req.region,
                      gate_fee_sgd_per_t=req.gate_fee, sell_credits=req.sell_credits, advanced=tuple(sorted(adv)))


@lru_cache(maxsize=64)
def _run(sc: E.Scenario) -> dict:
    b = bundle()
    res = E.run(b, sc)
    ev, pf, bau = res["eval"], res["pro_forma"], res["bau"]
    names = b.sites.set_index("site_id")
    per_site = ev["per_site"].set_index("site_id")
    rt = routes()
    flows = []
    for f in ev["flows"].itertuples():
        path = rt.get(f"{f.origin}|{f.site_id}")
        flows.append({"origin": f.origin, "site_id": f.site_id, "tonnes": f.tonnes, "road_km": f.road_km,
                      "haul_sgd_t": f.haul_sgd_t, "from": [f.o_lon, f.o_lat], "to": [f.s_lon, f.s_lat],
                      "path": path})
    t = ev["processed_t"] or 1.0
    levelised = {"Capital (yearly)": ev["capex_annual_sgd"], "Staff": ev["labour_sgd"],
                 "Maintenance": ev["maintenance_sgd"], "Land": ev["land_sgd"], "Electricity": ev["electricity_sgd"],
                 "Trucking": ev["haul_cost_sgd"], "Certification": ev["cert_sgd"]}
    income = {"Biochar sales": ev["biochar_t"] * res["assumptions"]["biochar_price_usd"] * res["assumptions"]["usd_sgd"],
              "Gate fees": ev["processed_t"] * sc.gate_fee_sgd_per_t, "Credit sales": ev["credit_revenue_sgd"]}
    a = res["assumptions"]
    reg = b.params
    used = []
    for f, key in [("woody_share", "woody_share"), ("collectable_share", "collectable_share"),
                   ("biochar_price_usd", "biochar_price_usd"), ("credit_price_eur", "corc_spot_eur"),
                   ("discount_rate", "discount_rate"), ("life_years", "plant_life_years"),
                   ("operator_wage", "operator_wage_sgd_month"), ("electricity_price", "electricity_price_sgd_kwh"),
                   ("haul_ef_kg_per_tkm", "haul_ef_kg_per_tkm"), ("baseline_avoided", "baseline_avoided")]:
        used.append({"input": key, "value": a[f], "default": reg.at[key, "value"], "unit": reg.at[key, "unit"],
                     "source": reg.at[key, "source"], "tag": reg.at[key, "tag"]})
    for key in ["inflation_2027", "inflation_long_run", "wage_growth", "ramp_up_year1"]:
        used.append({"input": key, "value": reg.at[key, "value"], "default": reg.at[key, "value"],
                     "unit": reg.at[key, "unit"], "source": reg.at[key, "source"], "tag": reg.at[key, "tag"]})
    return clean({
        "scenario": {"region": sc.region, "sites": list(sc.sites), "size": sc.size_class,
                     "gate_fee": sc.gate_fee_sgd_per_t, "sell_credits": sc.sell_credits,
                     "advanced": dict(sc.advanced)},
        "layout": [{"site_id": s, "name": names.name[s], "region": names.region[s], "size_class": c,
                    "label": b.plants.loc[c, "label"], "lat": names.latitude[s], "lon": names.longitude[s],
                    "capacity_t": per_site.capacity_t[s], "throughput_t": per_site.throughput_t[s],
                    "staff": per_site.staff_fte[s], "rent": names.rent_sgd_m2_yr_with_gst[s]}
                   for s, c in res["layout"].items()],
        "metrics": {"processed_t": ev["processed_t"], "biochar_t": ev["biochar_t"], "shortfall_t": ev["shortfall_t"],
                    "capex_sgd": pf["capex_sgd"], "npv_sgd": pf["npv_sgd"], "payback_year": pf["payback_year"],
                    "irr": pf["irr"], "levelised_cost_sgd_per_t": pf["levelised_cost_sgd_per_t"],
                    "break_even_gate_fee_sgd_per_t": pf["break_even_gate_fee_sgd_per_t"],
                    "year1_cash_flow_sgd": pf["year1_cash_flow_sgd"], "year2_cash_flow_sgd": pf["year2_cash_flow_sgd"],
                    "final_cash_flow_sgd": pf["final_cash_flow_sgd"], "stored_co2_t": ev["stored_co2_t"],
                    "credits_t": ev["registry_credit_t"], "net_climate_t": ev["registry_credit_t"] - bau["avoided_t"],
                    "mean_haul_km": ev["mean_haul_km"], "staff": ev["staff_fte"],
                    "net_cost_sgd_per_t": ev["net_cost_sgd_per_t"], "supply_available_t": res["supply_t"],
                    "analysis_years": pf["analysis_years"], "discount_rate": pf["discount_rate"]},
        "bau": bau, "years": pf["years"], "drivers": pf["drivers"],
        "cost_per_t": {k: v / t for k, v in levelised.items() if v},
        "income_per_t": {k: v / t for k, v in income.items() if v},
        "findings": res["findings"], "sites_compare": res["sites"], "sizes_compare": res["sizes"],
        "flows": flows, "assumptions": used, "gate_fee_cap_sgd": b.p("gate_fee_cap_sgd"),
    })


@app.post("/api/evaluate")
def evaluate(req: EvalRequest):
    sc = _scenario(req)
    try:
        return JSONResponse(_run(sc))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


# ----------------------------------------------------------------------------- evidence & validation
@lru_cache(maxsize=1)
def _evidence() -> dict:
    b = bundle()
    return clean({
        "parameters": b.params.reset_index()[["key", "value", "low", "high", "unit", "tag", "source", "url", "note"]],
        "waste_data_check": pd.read_csv(DATA / "params" / "waste_data_check.csv"),
        "plants": b.plants.reset_index(),
        "estimates": {u: vd.estimates_by(b.areas, b.areas.estimated_t, u) for u in vd.UNITS},
        "units": vd.UNITS,
    })


@app.get("/api/evidence")
def evidence():
    return JSONResponse(_evidence(), headers={"Cache-Control": "max-age=300"})


@app.post("/api/validate")
async def validate(unit: str = Form(...), file: UploadFile = File(...)):
    if unit not in vd.UNITS:
        raise HTTPException(400, f"unit must be one of {list(vd.UNITS)}")
    raw = await file.read()
    if len(raw) > 1_000_000:
        raise HTTPException(413, "File too large (max 1 MB)")
    try:
        obs = pd.read_csv(io.BytesIO(raw))
        b = bundle()
        res = vd.compare(vd.estimates_by(b.areas, b.areas.estimated_t, unit), obs, unit)
    except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return JSONResponse(clean(res))


@app.get("/api/health")
def health():
    return {"ok": True, "fingerprint": bundle().fingerprint, "routes": len(routes())}


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
