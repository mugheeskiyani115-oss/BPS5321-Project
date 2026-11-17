"""Tests for the biotwin model, the game engine and every app page (headless)."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from biotwin import forecast as fc
from biotwin import network as nw
from biotwin import optimise as op
from biotwin import outlook as ol
from biotwin import pathway as pw
from biotwin import evaluate as E
from biotwin import recommend
from biotwin import validation as vd
from biotwin.data import load_bundle

ROOT = Path(__file__).resolve().parents[1]
B = load_bundle()
A = pw.default_assumptions(B, target_t=9000)
NET = nw.build_network(B, A)


# ------------------------------------------------------------------ data & provenance
def test_planning_areas_mass_balance_and_notebook_regions():
    assert len(B.areas) == 55
    assert B.areas.estimated_t.sum() == pytest.approx(232_000)
    reg = B.areas.groupby("region").estimated_t.sum().round(-2)
    assert reg.to_dict() == {"Central": 72100, "East": 42800, "North": 36900, "North-East": 31900, "West": 48400}


def test_roads_sectors_and_road_ratio():
    assert B.areas.pwc_sector.notna().all() and B.areas.pwc_sector.nunique() == 6
    routed = B.roads[B.roads.method.str.startswith("OSRM")]
    assert (routed.road_km / routed.straight_km)[routed.straight_km > 1].median() == pytest.approx(1.38, abs=0.05)


def test_every_parameter_is_tagged_and_web_values_are_linked():
    assert B.params.tag.isin({"notebook", "web", "derived", "assumption", "pdf"}).all()
    web = B.params[B.params.tag == "web"]
    assert web.url.notna().all() and web.url.str.startswith("http").all()
    assert {"notebook", "web", "pdf"} <= set(B.params.tag)


def test_site_land_rents_match_jtc_schedule():
    r = B.sites.set_index("site_id").rent_sgd_m2_yr_with_gst
    assert r["S08"] == pytest.approx(13.41) and r["S01"] == pytest.approx(82.61) and r.notna().all()


# ------------------------------------------------------------------ carbon (Notebook 2, single basis)
def test_notebook2_worked_example_reconciles():
    haul_km = 0.004 / (A.haul_ef_kg_per_tkm / 1000)
    c = pw.carbon_per_wet_t(A, "industrial", haul_tkm_per_t=haul_km)
    assert c["stored_co2"] == pytest.approx(0.372, abs=1e-4)
    assert c["registry_credit"] == pytest.approx(0.234, abs=1e-4)
    assert c["net_vs_current_use"] == pytest.approx(-0.009, abs=1e-4)
    assert pw.carbon_per_wet_t(A, "small", haul_tkm_per_t=haul_km)["registry_credit"] == pytest.approx(0.12, abs=1e-3)
    assert not hasattr(pw, "CARBON_PRESETS")          # no alternative carbon basis any more


# ------------------------------------------------------------------ itemised Singapore costs
def test_labour_model_follows_mom_wages_and_hours():
    p = B.plants.loc["C20"]
    workers = 6 * 2 ** 0.25
    fte = workers * 168 * 0.86 / 44 * 1.07
    assert pw.staff_fte(p, A) == pytest.approx(fte)
    crew = (4168 + (workers - 1) * 2692) / workers
    assert pw.labour_sgd_yr(p, A) == pytest.approx(fte * crew * 12 * 1.17 + 4312 * 12 * 1.17)
    assert pw.workers_per_shift(B.plants.loc["K2"], A) == 3.0      # manual batch kilns scale linearly


def test_continuous_opex_inside_pdf_singapore_range_and_above_vendor():
    chk = pw.cost_basis_check(B, A).set_index("Plant")
    us = chk["This model (US$/t)"]
    assert 150 <= us["20 t/day continuous"] <= 250           # cross-check against the PDF's Singapore range
    assert (us > 60).all()                                    # every size above the generic vendor ceiling


def test_haul_cost_from_truck_day_rate():
    c15 = float(pw.haul_cost_sgd_per_t(15, A))
    trips = 8 / (2 * 15 / 60 * 1.3 + 0.5)
    assert c15 == pytest.approx(800 / (20 * 0.2076 * trips))
    assert float(pw.haul_cost_sgd_per_t(30, A)) > c15
    assert 15 <= np.median(NET.haul_sgd_t.min(axis=1)) <= 30      # handoff estimated ~S$20/t


def test_land_rent_changes_cost_by_site():
    kallang, tuas = nw.evaluate(NET, {"S01": "C50"}), nw.evaluate(NET, {"S08": "C50"})
    area = pw.land_area_m2(B.plants.loc["C50"], A)
    assert kallang["land_sgd"] == pytest.approx(area * 82.61 / 1.09)
    assert tuas["land_sgd"] == pytest.approx(area * 13.41 / 1.09)


def test_crf_and_break_even_gate_fee():
    assert pw.crf(0.08, 15) == pytest.approx(0.116830, abs=1e-6)
    be = pw.break_evens(B, A, "S10")
    row = pw.plant_cost_table(B, replace(A, gate_fee_sgd_per_t=be["gate_fee_sgd_per_t"])).set_index("size_class").loc["S10"]
    assert row.margin_sgd_per_t == pytest.approx(0, abs=1e-6)


def test_credit_revenue_net_of_registry_fee():
    assert pw.credit_margin_sgd(A) == pytest.approx((120.67 - 8.48) * A.eur_sgd)
    assert pw.cert_fixed_sgd_yr(A) == pytest.approx(1400 * A.eur_sgd + 7500 * A.gbp_sgd
                                                    + 13000 * A.gbp_sgd * pw.crf(0.08, 15))


def test_assumption_validation():
    with pytest.raises(ValueError):
        replace(A, woody_share=1.5)
    with pytest.raises(ValueError):
        replace(A, gate_fee_sgd_per_t=-1)


# ------------------------------------------------------------------ network
def test_lp_respects_supply_capacity_and_target():
    r = nw.evaluate(NET, {"S08": "C20", "S06": "S10", "S01": "K2"}, with_flows=True)
    assert r["feasible"] and r["processed_t"] == pytest.approx(9000)
    f = r["flows"]
    assert f.tonnes.sum() == pytest.approx(9000, rel=1e-6)
    caps = r["per_site"].set_index("site_id").capacity_t
    by_site = f.groupby("site_id").tonnes.sum()
    assert (by_site <= caps[by_site.index] + 1e-6).all()
    sup = NET.origins.set_index("planning_area").supply_t
    by_o = f.groupby("origin").tonnes.sum()
    assert (by_o <= sup[by_o.index] + 1e-6).all()
    assert r["haul_cost_sgd"] == pytest.approx((f.tonnes * f.haul_sgd_t).sum(), rel=1e-6)


def test_shortfall_is_reported_not_hidden():
    r = nw.evaluate(NET, {"S01": "K2"})
    assert not r["feasible"] and r["shortfall_t"] == pytest.approx(9000 - r["capacity_t"], rel=1e-6)
    with pytest.raises(ValueError):
        nw.evaluate(NET, {"NOPE": "C20"})


def test_small_kilns_lose_credit():
    big = nw.evaluate(NET, {"S01": "C50"})
    kilns = nw.evaluate(NET, {s: "B5" for s in NET.sites.site_id})
    assert kilns["registry_credit_t"] < big["registry_credit_t"]


# ------------------------------------------------------------------ optimiser
def test_nsga2_recovers_exhaustive_front_on_reduced_instance():
    small = replace(NET, sites=NET.sites.iloc[[0, 3, 5, 7]].reset_index(drop=True), dist_km=NET.dist_km[:, [0, 3, 5, 7]],
                    drive_min=NET.drive_min[:, [0, 3, 5, 7]], haul_sgd_t=NET.haul_sgd_t[:, [0, 3, 5, 7]])
    levels = ("B5", "S10", "C20")
    truth = op.exhaustive(op.Problem(small, levels))
    found = op.nsga2(op.Problem(small, levels), pop_size=40, generations=40, seed=3)["front"]
    key = lambda df: {tuple(np.round(r, 3)) for r in df[["net_cost_sgd", "net_climate_t", "mean_haul_km"]].to_numpy()}
    assert len(truth) > 1 and key(truth) <= key(found)


def test_nsga2_respects_capital_budget():
    res = op.nsga2(op.Problem(NET, tuple(B.plants.index), max_open=6, max_capex_sgd=5e6), pop_size=30,
                   generations=15, seed=0)
    assert len(res["front"]) and (res["front"].capex_total_sgd <= 5e6 + 1).all()


# ------------------------------------------------------------------ forecast & outlook
S = fc.national_series(B)


def test_trend_test_and_projection():
    t = fc.trend_test(S)
    assert t["mann_kendall_p"] == pytest.approx(0.073, abs=0.001) and t["ols_p"] == pytest.approx(0.049, abs=0.001)
    p = fc.project(S, "median_last5")
    assert p.point_t.iloc[0] == pytest.approx(256_000) and (p.p10_t <= p.point_t).all()


def test_credit_outlook_and_break_even():
    haul = 0.004 / (A.haul_ef_kg_per_tkm / 1000)
    so = ol.supply_outlook(B, A, "naive_last", haul_km_per_t=haul)
    assert so.credit_potential_central_t.iloc[0] == pytest.approx(232_000 * 0.70 * 0.234, rel=1e-3)
    assert ol.credit_price_path(B, [2028]).base_eur.iloc[0] == pytest.approx(133)
    po, pv = ol.plant_outlook(B, A, {"S09": "C50"}, so, B.areas.estimated_t.to_numpy())
    y = po.iloc[0]
    rev = y.registry_credit_t * (y.break_even_credit_eur - A.puro_fee_eur_per_corc) * A.eur_sgd - y.cert_cost_sgd
    assert y.result_no_credits_sgd + rev == pytest.approx(0, abs=1e-3)
    assert pv["high"] >= pv["base"] >= pv["low"] >= pv["no_credits"]


def test_validation_requires_sourced_records():
    est = vd.estimates_by(B.areas, B.areas.estimated_t, "pwc_sector")
    with pytest.raises(ValueError):
        vd.compare(est, vd.template(B.areas, "pwc_sector"), "pwc_sector")
    r = vd.compare(est, est.assign(year=2025, source="op", observed_t=est.estimated_t * 1.1), "pwc_sector")
    assert r["wape"] == pytest.approx(0.1 / 1.1, rel=1e-6)


# ------------------------------------------------------------------ recommendations
RECS = recommend.load(B)


def test_precomputed_recommendations_match_current_inputs():
    assert RECS is not None, "run: python -I pipeline/build_recommendations.py"
    assert set(RECS) == {float(t) for t in recommend.TARGETS}
    for t, r in RECS.items():
        assert r["options"] and r["cheapest"]["net_cost_sgd"] == min(o["net_cost_sgd"] for o in r["options"])


def test_recommended_options_are_feasible_and_non_dominated():
    r = RECS[9000.0]
    F = np.array([[o["net_cost_sgd"], o["net_climate_t"], o["mean_haul_km"]] for o in r["options"]]) * op.SENSE
    assert op.pareto_mask(F).all()
    ev = nw.evaluate(NET, r["cheapest"]["layout"])
    assert ev["feasible"] and ev["net_cost_sgd"] == pytest.approx(r["cheapest"]["net_cost_sgd"], rel=1e-9)


def test_compare_places_a_layout_against_the_options():
    r = RECS[9000.0]
    best = recommend.compare(nw.evaluate(NET, r["cheapest"]["layout"]), r)
    assert best["comparable"] and best["cost_gap_pct"] == pytest.approx(0, abs=1e-9) and best["on_frontier"]
    worse = recommend.compare(nw.evaluate(NET, {s: "B5" for s in NET.sites.site_id}), r)
    assert worse["cost_gap_pct"] > 0 and not worse["on_frontier"]
    assert not recommend.compare(nw.evaluate(NET, {"S01": "K2"}), r)["comparable"]


def test_balanced_option_and_description():
    r = RECS[9000.0]
    assert recommend.balanced(r) in r["options"]
    assert recommend.describe({"S01": "C20", "S02": "S10", "S03": "S10"},
                              {"C20": "20 t/day", "S10": "10 t/day"}) == "1 × 20 t/day + 2 × 10 t/day"


def test_waste_data_check_is_documented():
    chk = pd.read_csv(ROOT / "data" / "params" / "waste_data_check.csv")
    assert {"source", "granularity", "verdict", "url"} <= set(chk.columns) and len(chk) >= 8
    assert "Gardens by the Bay" in set(B.facilities["query"].fillna(""))


# ------------------------------------------------------------------ scenario evaluation
def test_evaluation_of_a_chosen_plant():
    r = E.run(B, E.Scenario(sites=("S09",), size_class="C50"))
    ev, pf, bau = r["eval"], r["pro_forma"], r["bau"]
    assert r["layout"] == {"S09": "C50"} and ev["processed_t"] == pytest.approx(pw.annual_capacity_t(B.plants.loc["C50"]))
    y = pf["years"]
    assert len(y) == 16 and y.cash_flow_sgd.iloc[0] == pytest.approx(-pf["capex_sgd"])
    disc = (1 + pf["discount_rate"]) ** -y.year
    assert pf["npv_sgd"] == pytest.approx(float((y.cash_flow_sgd * disc).sum()))
    r2 = E.run(B, E.Scenario(sites=("S09",), size_class="C50", gate_fee_sgd_per_t=pf["break_even_gate_fee_sgd_per_t"]))
    assert r2["pro_forma"]["npv_sgd"] == pytest.approx(0, abs=1)
    assert bau["avoided_t"] == pytest.approx(ev["processed_t"] * A.baseline_avoided)
    assert bau["mean_haul_km"] > 0 and [f["title"] for f in r["findings"]][0] == "Expected output"
    assert len(r["sites"]) == 10 and r["sites"].net_cost_sgd_per_t.is_monotonic_increasing


def test_cash_flows_change_every_year_for_stated_reasons():
    r = E.run(B, E.Scenario(sites=("S09",), size_class="C50", sell_credits=True))
    y = r["pro_forma"]["years"].set_index("year")
    ev = r["eval"]
    assert y.utilisation[1] == pytest.approx(B.p("ramp_up_year1")) and y.utilisation[2] == 1.0       # ramp-up
    assert y.staff_sgd[3] / y.staff_sgd[2] == pytest.approx(1 + B.p("wage_growth"))                     # MOM wages
    assert y.maintenance_sgd[3] / y.maintenance_sgd[2] == pytest.approx(1 + B.p("inflation_long_run"))  # MAS
    assert y.maintenance_sgd[1] == pytest.approx(ev["maintenance_sgd"] * (1 + B.p("inflation_2027")))
    assert y.credit_price_eur[15] > y.credit_price_eur[1]                                              # Senken path
    assert y.cash_flow_sgd.iloc[1:].nunique() == 15                                                    # no two years equal


def test_tool_picks_the_cheapest_plot_and_size_in_a_region():
    r = E.run(B, E.Scenario(region="West"))
    (site, size), = r["layout"].items()
    assert B.sites.set_index("site_id").region[site] == "West"
    for s in E.region_sites(B, "West"):
        for c in B.plants.index:
            ev, _ = E._eval_layout(B, E.Scenario(region="West"), {s: c})
            assert ev["net_cost_sgd_per_t"] >= r["eval"]["net_cost_sgd_per_t"] - 1e-6


def test_decentralised_layout_and_advanced_inputs():
    r = E.run(B, E.Scenario(sites=("S03", "S05", "S06"), size_class="S10", sell_credits=True,
                            advanced=(("woody_share", 0.6),)))
    assert len(r["layout"]) == 3 and r["assumptions"]["woody_share"] == 0.6
    assert r["eval"]["credit_revenue_sgd"] > 0 and r["eval"]["cert_sgd"] == pytest.approx(3 * pw.cert_fixed_sgd_yr(
        pw.default_assumptions(B)))
    assert E.irr(100, 10, 5) is None and E.irr(100, 30, 5) == pytest.approx(0.1524, abs=1e-3)
    with pytest.raises(ValueError):
        E.run(B, E.Scenario(region="Nowhere"))


