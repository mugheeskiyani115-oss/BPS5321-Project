"""Play: build a layout on the 3D map, watch the HUD, submit for stars (or run the decade)."""
import random

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from biotwin import game
from biotwin import pathway as pw
from ui import components as C
from ui import data as D
from ui import maps as M
from ui import state
from ui import theme as T

ss = state.ss


def _set_credits(mid: str) -> None:
    ss.sell_credits[mid] = bool(ss[f"credits_{mid}"])
    ss.last_result.pop(mid, None)
    ss.decade.pop(mid, None)


def _load_layout(mid: str, layout: dict) -> None:
    ss.layouts[mid] = dict(layout)
    ss.last_result.pop(mid, None)
    ss.decade.pop(mid, None)


def mission_header(b, unlocked_ids):
    top = st.columns([3.2, 1])
    with top[1]:
        choice = st.selectbox("Mission", unlocked_ids, index=unlocked_ids.index(ss.mission),
                              format_func=lambda k: f"{game.MISSIONS[k].icon} {game.MISSIONS[k].title}")
        if choice != ss.mission:
            ss.mission, ss.selected_site = choice, None
            st.rerun()
    m = game.MISSIONS[ss.mission]
    with top[0]:
        best = ss.best.get(m.id, {})
        st.markdown(f"<div class='bt-kicker'>Mission · best {best.get('score', 0):,} pts</div>"
                    f"<h2 style='margin:0 0 4px'>{m.icon} {m.title} {T.stars(best.get('stars', 0))}</h2>",
                    unsafe_allow_html=True)
        st.write(T.md(m.brief))
    return m


def hud(m, ev):
    h = st.columns(6)
    with h[0]:
        st.metric("Capital used", T.money(ev["capex_total_sgd"]), f"budget {T.money(m.budget_sgd)}", delta_color="off", delta_arrow="off")
        st.progress(min(ev["capex_total_sgd"] / m.budget_sgd, 1.0))
    with h[1]:
        st.metric("Throughput", f"{ev['processed_t']:,.0f} t/yr", f"target {m.target_t:,.0f}", delta_color="off", delta_arrow="off")
        st.progress(min(ev["processed_t"] / m.target_t, 1.0))
    h[2].metric("Net cost", T.money(ev["net_cost_sgd_per_t"], "/t") if ev["processed_t"] else "—",
                "revenue − cost, per wet tonne", delta_color="off", delta_arrow="off")
    h[3].metric("Registry credits", f"{ev['registry_credit_t']:,.0f} t/yr", "tCO2e", delta_color="off", delta_arrow="off")
    h[4].metric("Net vs current use", f"{ev['net_climate_t']:+,.0f} t/yr", "tCO2e vs biomass power", delta_color="off", delta_arrow="off")
    h[5].metric("Mean haul", f"{ev['mean_haul_km']:.1f} km", T.money(ev["haul_cost_sgd"], "/yr") + " trucking",
                delta_color="off", delta_arrow="off")
    if not ev["within_budget"]:
        st.warning("Over budget — demolish or downsize a plant.")
    elif ev["config"] and not ev["feasible"]:
        st.info(f"Capacity is {ev['shortfall_t']:,.0f} t/yr short of the target — build more or bigger.")


def build_panel(b, m, net, ev, lay, plant_cost_cache):
    site_ids = list(net.sites.site_id)
    names = net.sites.set_index("site_id").name.to_dict()
    cur = ss.selected_site if ss.selected_site in site_ids else None
    pick = st.selectbox("Site (or click a column on the map)", ["—"] + site_ids,
                        index=site_ids.index(cur) + 1 if cur else 0,
                        format_func=lambda s: "— choose a site —" if s == "—" else f"{s} · {names[s]}")
    ss.selected_site = None if pick == "—" else pick
    if not ss.selected_site:
        st.info("Grey columns are empty industrial plots. Click one on the map (or pick it above) to build.")
        return
    sid = ss.selected_site
    site = net.sites.set_index("site_id").loc[sid]
    current = lay.get(sid)
    rent = float(site.rent_sgd_m2_yr_with_gst)
    pill = (f"<span class='bt-pill good'>Running: {b.plants.loc[current, 'label']}</span>" if current
            else "<span class='bt-pill'>Empty plot</span>")
    st.markdown(f"<div class='bt-card'><h4>{sid} · {site['name']}</h4><p class='sub'>{site.region} · JTC "
                f"{site.jtc_estate}<br/>Land S&#36;{rent:,.2f}/m²/yr (posted, incl. GST)</p>{pill}</div>",
                unsafe_allow_html=True)
    if current:
        st.button("Demolish", key=f"demo_{m.id}_{sid}", on_click=state.set_plant, args=(sid, None), width="stretch")
    if rent not in plant_cost_cache:
        plant_cost_cache[rent] = pw.plant_cost_table(b, game.mission_assumptions(b, m), rent).set_index("size_class")
    costs = plant_cost_cache[rent]
    a = game.mission_assumptions(b, m)
    spent_elsewhere = ev["capex_total_sgd"] - (pw.capex_sgd(b.plants.loc[current], a) if current else 0)
    st.markdown("**Build here**")
    for sc, p in b.plants.iterrows():
        capex = pw.capex_sgd(p, a)
        over = spent_elsewhere + capex > m.budget_sgd + 1e-6
        row = costs.loc[sc]
        c1, c2 = st.columns([3.2, 1])
        c1.markdown(f"**{p['label']}** <span class='bt-muted'>· {row.annual_t:,.0f} t/yr · "
                    f"{T.h(T.money(capex))} · {row.staff_fte:.0f} staff · ~{T.h(T.money(row.cost_sgd_per_t))}/t at "
                    f"full load{' · small kiln: ~half credit' if p.carbon_class == 'small' else ''}</span>",
                    unsafe_allow_html=True)
        label = "Built" if current == sc else ("Swap" if current else "Build")
        c2.button(label, key=f"build_{m.id}_{sid}_{sc}", disabled=over or current == sc, width="stretch",
                  on_click=state.set_plant, args=(sid, sc), help="Over budget" if over else None)


def cost_breakdown(ev):
    if not ev["processed_t"]:
        return
    t = ev["processed_t"]
    items = {"Capital (annuity)": ev["capex_annual_sgd"], "Labour": ev["labour_sgd"], "Maintenance": ev["maintenance_sgd"],
             "Land": ev["land_sgd"], "Electricity": ev["electricity_sgd"], "Trucking": ev["haul_cost_sgd"],
             "Certification": ev["cert_sgd"]}
    items = {k: v / t for k, v in items.items() if v}
    rev = {"Biochar sales": ev["product_revenue_sgd"] / t, "Credit sales": ev["credit_revenue_sgd"] / t}
    rev = {k: v for k, v in rev.items() if v}
    fig = go.Figure()
    fig.add_trace(go.Bar(y=list(items), x=list(items.values()), orientation="h", name="Cost",
                         marker=dict(color=T.ORANGE, line=dict(color=T.SURFACE, width=2)),
                         hovertemplate="%{y}: S$%{x:,.0f}/t<extra></extra>"))
    fig.add_trace(go.Bar(y=list(rev), x=list(rev.values()), orientation="h", name="Revenue",
                         marker=dict(color=T.AQUA, line=dict(color=T.SURFACE, width=2)),
                         hovertemplate="%{y}: S$%{x:,.0f}/t<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(T.style(fig, 300, xaxis_title="S$ per wet tonne", bargap=0.3), width="stretch")


def decade_view(df, summ):
    st.markdown("#### Your decade, year by year")
    for half in (df.iloc[:5], df.iloc[5:]):
        cols = st.columns(5)
        for col, r in zip(cols, half.itertuples()):
            col.markdown(f"<div class='bt-year'><b>{r.year}</b><br/>{T.h(T.money(r.result_sgd))}<br/>"
                         f"<span class='bt-muted'>credit €{r.credit_price_eur:,.0f} · woody {100 * r.woody_share:.0f}%"
                         f"</span><br/>{r.events}</div>", unsafe_allow_html=True)
    fig = go.Figure(go.Scatter(x=df.year, y=df.cumulative_sgd, mode="lines+markers", line=dict(color=T.BLUE, width=2),
                               marker=dict(size=8), hovertemplate="%{x}: S$%{y:,.0f}<extra>cumulative</extra>"))
    st.plotly_chart(T.style(fig, 260, yaxis_title="Cumulative result, S$"), width="stretch")
    st.caption(f"Seed {summ['seed']}. Draws come from the model's own uncertainty: national supply × a one-year-ahead "
               "forecast error seen in NEA's 2011–2025 series, woody share ± the seasonal range, credit price "
               "within Senken's low–high band.")


def body():
    b = D.bundle_or_stop()
    if ss.pop("_celebrate", False):
        st.balloons()
    refs = D.references(b.fingerprint)
    unlocked_ids = [mid for mid in game.MISSIONS if game.unlocked(mid, ss.best)]
    if ss.mission not in unlocked_ids:
        ss.mission = unlocked_ids[0]
    m = mission_header(b, unlocked_ids)
    ref = refs[m.id]
    sell = ss.sell_credits[m.id]
    net = D.network(m.id, sell)
    lay = state.layout()
    ev = game.evaluate_layout(b, m, lay, sell, net=net, with_flows=True)
    hud(m, ev)

    left, right = st.columns([1.7, 1])
    with left:
        thr = dict(zip(ev["per_site"].site_id, ev["per_site"].throughput_t)) if len(ev["per_site"]) else {}
        layers = [M.area_layer(b, net.origins.supply_t.to_numpy(), "t/yr woody & collectable", opacity=0.5),
                  M.flow_layer(ev.get("flows")),
                  *M.site_layers(net, lay, b.plants.label.to_dict(), thr, ss.selected_site, b.facilities)]
        event = M.deck(layers, key=f"play_map_{m.id}", height=620, zoom=10.3, selectable=True)
        clicked = M.clicked_site(event)
        if clicked and clicked != ss.get(f"_last_click_{m.id}"):
            ss[f"_last_click_{m.id}"] = clicked
            ss.selected_site = clicked
        st.markdown(f"<span style='color:{T.ORANGE}'>■</span> your plants (height = throughput) &nbsp; "
                    f"<span style='color:{T.MUTED}'>■</span> empty plots &nbsp; "
                    f"<span style='color:{T.AQUA}'>■</span> existing waste-to-energy plants &nbsp; "
                    f"<span style='color:{T.SEQ[6]}'>■</span> woody feedstock (darker = less)",
                    unsafe_allow_html=True)
    with right:
        build_panel(b, m, net, ev, lay, ss.setdefault("_plant_cost_cache", {}))
        st.divider()
        st.toggle("Certify & sell carbon credits", value=sell, key=f"credits_{m.id}", on_change=_set_credits,
                  args=(m.id,), help="Puro.earth fee per credit plus annual verification per plant; credits sold at "
                                     "the June 2026 CORC index (decade: Senken price band).")
        st.button("Clear layout", on_click=state.clear_layout, width="stretch", disabled=not lay)

    st.divider()
    o1, o2 = st.columns([1.3, 1])
    decade = ss.decade.get(m.id)
    with o1:
        st.markdown("#### Objectives")
        preview = game.score(m, ev, ref, decade=decade[1] if decade else None)
        C.checklist(preview["checks"])
        st.caption("Budgets and star thresholds are game rules. Everything scored is computed by the model.")
    with o2:
        st.markdown("#### Score")
        st.markdown(f"<div style='font-size:2.6rem;font-weight:800;line-height:1'>{preview['score']:,} "
                    f"<span class='bt-muted'>pts</span></div>{T.stars(preview['stars'])}", unsafe_allow_html=True)
        if m.objective == "decade":
            go_ = st.button("▶ Run the decade", type="primary", disabled=not ev["valid"], width="stretch")
            if go_:
                seed = random.randint(1, 99_999)
                df, summ = game.decade_with_reference(b, m, lay, sell, ref, seed)
                ss.decade[m.id] = (df, summ)
                _submit(b, m, ev, ref, sell, summ)
                st.rerun()
        elif st.button("🏁 Submit layout", type="primary", disabled=not ev["config"], width="stretch"):
            _submit(b, m, ev, ref, sell, None)
            st.rerun()
        debrief = ss.last_result.get(m.id)
        if debrief:
            r = debrief["result"]
            msg = "New best!" if debrief["improved"] else f"Best stays {debrief['previous']['score']:,}"
            st.success(f"Submitted: {r['score']:,} pts, {r['stars']}★ — {msg}")
            if r["stars"] >= 1:
                with st.expander("👀 Reveal the AI's answer"):
                    ai = ref["best_credit_layout"] if m.objective == "credits" else ref["best_cost_layout"]
                    st.write(", ".join(f"{b.plants.loc[c, 'label']} @ {s} ({net.sites.set_index('site_id').name[s]})"
                                       for s, c in ai.items()))
                    st.caption(T.md(f"AI best: {T.money(ref['best_cost_sgd_t'])}/t · "
                                    f"{ref['best_credit_t']:,.0f} tCO2e/yr credits"))
                    st.button("Load the AI layout", on_click=_load_layout, args=(m.id, ai))

    if decade:
        decade_view(*decade)
    with st.expander("Where the money goes"):
        cost_breakdown(ev)
        if len(ev["per_site"]):
            st.dataframe(ev["per_site"].drop(columns=["latitude", "longitude"]).round(2), hide_index=True,
                         width="stretch")
        st.caption(T.md(f"Break-even gate fee: {T.money(ev['break_even_gate_fee_sgd_per_t'])}/t. What generators "
                        f"pay to incinerate today: {T.money(b.p('gate_fee_cap_sgd'))}/t (NEA, excl. GST)."))


def _submit(b, m, ev, ref, sell, decade_summary):
    result = game.score(m, ev, ref, decade=decade_summary)
    badges = game.earned_badges(m, ev, result, sell, b, ref, decade_summary)
    state.record(m.id, result, ev, sell, badges)
    if result["stars"] == 3:
        ss["_celebrate"] = True


C.guard(body)
