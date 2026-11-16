"""Lab: the analysis behind the game (feedstock, forecast & credits outlook, plant economics, optimiser, validation)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from biotwin import forecast as fc
from biotwin import network as nw
from biotwin import optimise as op
from biotwin import outlook as ol
from biotwin import pathway as pw
from biotwin import validation as vd
from ui import components as C
from ui import data as D
from ui import maps as M
from ui import state
from ui import theme as T

ss = state.ss


def feedstock(b, a):
    st.markdown("#### Where is the woody feedstock?")
    st.write("Planning-area columns show estimated woody, collectable tonnes per year: NEA's 2025 national total "
             "allocated by tree biomass, tree count and managed green area, × woody share (Notebook 2: "
             f"{a.woody_share:.0%}) × collectable share ({a.collectable_share:.0%}). **Proxy allocation — not "
             "measured regional waste.**")
    with st.expander("Sensitivity: proxy weights"):
        weights = {c: st.slider(lbl, 0.0, 1.0, 1.0, 0.1, key=f"lab_w_{c}") for c, lbl in fc.PROXY_COLUMNS.items()
                   if c in b.areas.columns}
    alloc = fc.allocate(b.areas, weights, a.national_t)
    woody = alloc * a.woody_share * a.collectable_share
    net = nw.build_network(b, a, alloc)
    M.deck([M.area_layer(b, woody, "t/yr woody & collectable"),
            *M.site_layers(net, {}, {}, facilities=b.facilities)], key="lab_map", height=540)
    tbl = b.areas[["planning_area", "region", "pwc_sector"]].assign(allocated_t=alloc, woody_collectable_t=woody)
    c1, c2 = st.columns(2)
    c1.dataframe(tbl.groupby("region")[["allocated_t", "woody_collectable_t"]].sum().round(-2)
                 .sort_values("allocated_t", ascending=False), width="stretch")
    c2.dataframe(tbl.groupby("pwc_sector")[["allocated_t", "woody_collectable_t"]].sum().round(-2)
                 .sort_values("allocated_t", ascending=False), width="stretch")
    st.caption("PWC sectors read from NEA's schematic map (7 Oct 2025); 21 of 55 planning areas sit near a boundary.")


def forecast(b, a):
    s, summary, pts = D.backtest()
    method = summary.index[0]
    p = fc.project(s, method, backtest_points=pts)
    st.markdown("#### National supply: history, backtest and projection")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(p.year) + list(p.year[::-1]), y=list(p.p90_t) + list(p.p10_t[::-1]), fill="toself",
                             fillcolor="rgba(57,135,229,0.18)", line=dict(width=0), name="80% band (backtest errors)",
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines+markers", name="NEA, generated",
                             line=dict(color=T.BLUE, width=2), marker=dict(size=8),
                             hovertemplate="%{x}: %{y:,.0f} t<extra></extra>"))
    fig.add_trace(go.Scatter(x=p.year, y=p.point_t, mode="lines", name=f"Projection: {fc.METHODS[method]}",
                             line=dict(color=T.BLUE, width=2, dash="dash"), hovertemplate="%{x}: %{y:,.0f} t<extra></extra>"))
    st.plotly_chart(T.style(fig, 380, yaxis_title="Tonnes per year", hovermode="x unified"), width="stretch")
    c1, c2 = st.columns([1.2, 1])
    c1.dataframe(summary[["description", "mape_pct", "mae_t"]].rename(columns={"description": "Method",
                 "mape_pct": "MAPE %", "mae_t": "MAE t"}).round(1), hide_index=True, width="stretch")
    t1, t2 = fc.trend_test(s), fc.trend_test(s, exclude_years=(2018,))
    c2.dataframe(pd.DataFrame({"": ["Slope t/yr", "OLS p", "Mann-Kendall p"],
                               "2016–2025": [f"{t1['slope_t_per_year']:,.0f}", f"{t1['ols_p']:.3f}", f"{t1['mann_kendall_p']:.3f}"],
                               "excl. 2018": [f"{t2['slope_t_per_year']:,.0f}", f"{t2['ols_p']:.3f}", f"{t2['mann_kendall_p']:.3f}"]}),
                 hide_index=True, width="stretch")
    st.caption("One national figure per year exists, so the method is picked by backtest and the projection stays flat: "
               "evidence of decline is weak and not robust (OLS p≈0.05, Mann-Kendall p≈0.07).")

    st.markdown("#### 10-year carbon-credit outlook (9,000 t/yr reference layout)")
    so = ol.supply_outlook(b, a, method, haul_km_per_t=0.004 / (a.haul_ef_kg_per_tkm / 1000), backtest_points=pts)
    refs = D.references(b.fingerprint)
    layout = refs["city_loop"]["best_cost_layout"]
    po, pv = ol.plant_outlook(b, a, layout, so, b.areas.estimated_t.to_numpy())
    k = st.columns(4)
    k[0].metric("National credit potential", f"{so.credit_potential_central_t.iloc[-1]:,.0f} t/yr",
                "upper bound: all woody waste", delta_color="off", delta_arrow="off")
    k[1].metric("Layout credits", f"{po.registry_credit_t.iloc[0]:,.0f} t/yr")
    k[2].metric("Break-even credit price", f"€{po.break_even_credit_eur.iloc[0]:,.0f}",
                f"Senken 2035 high €{so.high_eur.iloc[-1]:,.0f}", delta_color="off", delta_arrow="off")
    k[3].metric("10-yr PV, base credits", T.money(pv["base"]), f"no credits {T.money(pv['no_credits'])}", delta_color="off", delta_arrow="off")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=list(so.year) + list(so.year[::-1]), y=list(so.high_eur) + list(so.low_eur[::-1]),
                              fill="toself", fillcolor="rgba(57,135,229,0.18)", line=dict(width=0), name="Senken low–high",
                              hoverinfo="skip"))
    fig2.add_trace(go.Scatter(x=so.year, y=so.base_eur, mode="lines+markers", name="Senken base",
                              line=dict(color=T.BLUE, width=2), marker=dict(size=8)))
    fig2.add_trace(go.Scatter(x=po.year, y=po.break_even_credit_eur, mode="lines", name="Break-even for the layout",
                              line=dict(color=T.ORANGE, width=2, dash="dash")))
    st.plotly_chart(T.style(fig2, 300, yaxis_title="EUR per tCO2e", yaxis_rangemode="tozero"), width="stretch")
    st.caption(T.md(f"Layout: {', '.join(f'{c}@{s}' for s, c in layout.items())} (the AI's cheapest for 9,000 t/yr). "
                    "Credit income is net of the Puro.earth per-credit fee and annual verification. Costs held flat; "
                    "credit prices nominal."))


def economics(b, a):
    st.markdown("#### Plant economics (itemised, Singapore)")
    st.write("One cost basis: vendor turnkey capex plus an itemised Singapore running cost — MOM wages + CPF for the "
             "crews the plant's hours need, SP Group electricity, maintenance at 8% of capex a year, and JTC land rent. "
             "Shown at the median candidate-site rent and full utilisation.")
    t = pw.plant_cost_table(b, a)
    fig = go.Figure()
    parts = [("capex_sgd_per_t", "Capital", T.BLUE), ("labour_sgd_per_t", "Labour", T.ORANGE),
             ("maintenance_sgd_per_t", "Maintenance", T.AQUA)]
    for col, name, colr in parts:
        fig.add_trace(go.Bar(x=t.label, y=t[col], name=name, marker=dict(color=colr, line=dict(color=T.SURFACE, width=2)),
                             hovertemplate="%{x}: S$%{y:,.0f}/t<extra>" + name + "</extra>"))
    other = t.land_sgd_per_t + t.electricity_sgd_per_t
    fig.add_trace(go.Bar(x=t.label, y=other, name="Land + electricity", marker=dict(color=T.MUTED, line=dict(color=T.SURFACE, width=2)),
                         hovertemplate="%{x}: S$%{y:,.0f}/t<extra>Land + electricity</extra>"))
    st.plotly_chart(T.style(fig, 360, barmode="stack", yaxis_title="S$ per wet tonne", bargap=0.35), width="stretch")
    st.dataframe(t[["label", "annual_t", "staff_fte", "land_m2", "capex_sgd", "cost_sgd_per_t", "margin_sgd_per_t",
                    "break_even_gate_fee_sgd_per_t"]].rename(columns={"label": "Plant", "annual_t": "t/yr",
                    "staff_fte": "Staff FTE", "land_m2": "Land m²", "capex_sgd": "Capex S$", "cost_sgd_per_t": "Cost S$/t",
                    "margin_sgd_per_t": "Margin S$/t", "break_even_gate_fee_sgd_per_t": "Break-even gate fee S$/t"}).round(0),
                 hide_index=True, width="stretch")
    st.markdown("**Why this cost basis?** Running cost (excl. capital), US$ per wet tonne:")
    st.dataframe(pw.cost_basis_check(b, a).round(2), hide_index=True, width="stretch",
                 column_config={"Labour share of opex": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.0f%%")})
    st.caption(T.md("Generic vendor opex leaves out Singapore wages and land. The research PDF's Singapore range has no "
                    "source, but the itemised model lands inside it for continuous plants. Small batch kilns are "
                    "labour-bound at resident wages (MOM data covers residents; foreign-worker crews would cost less). "
                    f"Incineration costs generators {T.money(b.p('gate_fee_cap_sgd'))}/t (NEA, excl. GST)."))


def optimiser(b, a):
    st.markdown("#### Free optimiser run (NSGA-II)")
    with st.form("lab_nsga"):
        c = st.columns(4)
        target = c[0].number_input("Target t/yr", 1000, 60000, 9000, 500)
        pop = c[1].number_input("Population", 20, 150, 50, 10)
        gens = c[2].number_input("Generations", 10, 150, 40, 10)
        seed = c[3].number_input("Seed", 0, 9999, 1)
        run = st.form_submit_button("Run", type="primary")
    if run:
        with st.spinner("Searching…"):
            a2 = pw.default_assumptions(b, target_t=float(target))
            res = op.nsga2(op.Problem(nw.build_network(b, a2), tuple(b.plants.index), max_open=6),
                           pop_size=int(pop), generations=int(gens), seed=int(seed))
        ss["lab_front"] = res["front"]
    front = ss.get("lab_front")
    if front is None or front.empty:
        st.info("Press Run to map the trade-offs between net cost, net climate benefit and haul distance.")
        return
    fig = go.Figure(go.Scatter(x=front.net_cost_sgd_per_t, y=front.net_climate_t, mode="markers",
                               marker=dict(size=11, color=front.mean_haul_km, colorscale=[[0, T.SEQ[7]], [1, T.SEQ[1]]],
                                           showscale=True, colorbar=dict(title="Haul km"), line=dict(color=T.SURFACE, width=2)),
                               customdata=front.configuration,
                               hovertemplate="%{customdata}<br>S$%{x:,.0f}/t · %{y:+,.0f} tCO2e/yr<extra></extra>"))
    st.plotly_chart(T.style(fig, 420, xaxis_title="Net cost, S$ per wet tonne",
                            yaxis_title="Net climate vs current use, tCO2e/yr"), width="stretch")
    st.dataframe(front[["configuration", "n_sites", "net_cost_sgd_per_t", "net_climate_t", "registry_credit_t",
                        "mean_haul_km", "capex_total_sgd"]].round(1), hide_index=True, width="stretch")


def validation(b, a):
    st.markdown("#### Independent validation — pending real records")
    unit = st.radio("Compare by", list(vd.UNITS), format_func=vd.UNITS.get, horizontal=True)
    est = vd.estimates_by(b.areas, b.areas.estimated_t, unit)
    st.dataframe(est.round(-2), hide_index=True, width="stretch")
    st.download_button("Download blank template", vd.template(b.areas, unit).to_csv(index=False),
                       f"validation_template_{unit}.csv", "text/csv", on_click="ignore")
    up = st.file_uploader("Upload completed CSV (independent 2025 records only)", type=["csv"])
    if up is None:
        st.warning("No independent records uploaded: regional accuracy has **not** been measured.")
        return
    try:
        res = vd.compare(est, pd.read_csv(up), unit)
    except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        st.error(f"Cannot use this file: {exc}")
        return
    k = st.columns(3)
    k[0].metric("WAPE", f"{100 * res['wape']:.1f}%")
    k[1].metric("Rank ρ", "n/a" if np.isnan(res["rank_spearman"]) else f"{res['rank_spearman']:.2f}")
    k[2].metric("Share error", f"{res['share_mae_pp']:.1f} pp")
    st.dataframe(res["table"].round(2), hide_index=True, width="stretch")


def body():
    b = D.bundle_or_stop()
    state.visit("forecaster")
    a = pw.default_assumptions(b, target_t=9000)
    C.hero("Lab", "The analysis behind the game", "Same model, no game rules: feedstock estimates, supply forecast, "
           "carbon-credit outlook, plant economics, a free optimiser run and validation.")
    tabs = st.tabs(["🗺️ Feedstock", "📈 Forecast & credits", "⚗️ Plant economics", "🎯 Optimiser", "✅ Validation"])
    for tab, fn in zip(tabs, [feedstock, forecast, economics, optimiser, validation]):
        with tab:
            C.guard(fn, b, a)


C.guard(body)
