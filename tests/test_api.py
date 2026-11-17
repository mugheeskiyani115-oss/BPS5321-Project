"""API and static front-end tests (no browser needed)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server import app

ROOT = Path(__file__).resolve().parents[1]
c = TestClient(app)


def test_static_front_end_is_served():
    r = c.get("/")
    assert r.status_code == 200 and "BioTwin" in r.text and "js/app.js" in r.text
    for f in ["js/app.js", "js/map.js", "js/charts.js", "js/views/evaluate.js", "js/views/results.js", "css/app.css",
              "vendor/maplibre-gl.js", "vendor/deck.gl.min.js", "vendor/echarts.min.js"]:
        assert c.get(f"/{f}").status_code == 200, f


def test_meta_and_geo():
    m = c.get("/api/meta").json()
    assert set(m["regions"]) == {"Central", "East", "North", "North-East", "West"}
    assert len(m["sites"]) == 10 and len(m["plants"]) == 6 and len(m["areas"]) == 55
    assert {"woody_share", "discount_rate", "life_years"} <= set(m["advanced"])
    g = c.get("/api/geo").json()
    assert g["type"] == "FeatureCollection" and len(g["features"]) == 55


def test_evaluate_returns_everything_the_results_page_needs():
    r = c.post("/api/evaluate", json={"region": "West", "size": "C50"})
    assert r.status_code == 200
    j = r.json()
    for k in ["scenario", "layout", "metrics", "bau", "years", "drivers", "findings", "sites_compare", "sizes_compare",
              "flows", "assumptions", "cost_per_t"]:
        assert k in j, k
    assert j["layout"][0]["region"] == "West" and len(j["years"]) == 16
    assert all(f["path"] is None or len(f["path"]) >= 2 for f in j["flows"])
    assert sum(f["path"] is not None for f in j["flows"]) >= 0.9 * len(j["flows"])   # road geometry for trucks


def test_manual_sites_credits_and_advanced_inputs():
    j = c.post("/api/evaluate", json={"sites": ["S02", "S03"], "size": "S10", "sell_credits": True, "gate_fee": 50,
                                      "advanced": {"woody_share": 0.6, "life_years": 20}}).json()
    assert {l["site_id"] for l in j["layout"]} == {"S02", "S03"} and len(j["years"]) == 21
    assert j["scenario"]["advanced"] == {"life_years": 20, "woody_share": 0.6}
    assert any(y["credit_sales_sgd"] > 0 for y in j["years"])


@pytest.mark.parametrize("body,code", [({"region": "Mars"}, 400), ({"sites": ["S99"]}, 400), ({"size": "XL"}, 400),
                                       ({"gate_fee": -5}, 422), ({"advanced": {"woody_share": 2}}, 400),
                                       ({"advanced": {"magic": 1}}, 400)])
def test_bad_inputs_are_rejected_clearly(body, code):
    r = c.post("/api/evaluate", json=body)
    assert r.status_code == code and r.json()["detail"]


def test_evidence_and_validation_upload():
    e = c.get("/api/evidence").json()
    assert len(e["parameters"]) > 40 and len(e["waste_data_check"]) >= 8
    est = e["estimates"]["region"]
    csv = "region,year,observed_t,source\n" + "\n".join(f"{r['region']},2025,{r['estimated_t'] * 1.1},op" for r in est)
    r = c.post("/api/validate", data={"unit": "region"}, files={"file": ("obs.csv", csv, "text/csv")})
    assert r.status_code == 200 and r.json()["wape"] == pytest.approx(0.1 / 1.1, rel=1e-6)
    bad = c.post("/api/validate", data={"unit": "region"}, files={"file": ("x.csv", "a,b\n1,2", "text/csv")})
    assert bad.status_code == 422
