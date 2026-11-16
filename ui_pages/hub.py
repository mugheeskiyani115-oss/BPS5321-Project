"""Mission hub: player progress, mission select, badges."""
import streamlit as st

from biotwin import game
from ui import components as C
from ui import data as D
from ui import state


def body():
    b = D.bundle_or_stop()
    C.hero("BioTwin Quest · Singapore",
           "Turn the island's tree trimmings into carbon-storing biochar",
           "You run a new biochar venture. Pick sites on a 3D map of Singapore, choose plant sizes, and beat the "
           "optimiser on cost, carbon and haul distance. Every number comes from NEA, MOM, JTC, SP Group, "
           "OpenStreetMap, published research and the team's Notebook 2 — see Sources.")
    C.player_strip()
    st.markdown("### Missions")
    missions = list(game.MISSIONS.values())
    cols = st.columns(len(missions))
    for col, m in zip(cols, missions):
        with col:
            if C.mission_card(m, state.ss.best, game.unlocked(m.id, state.ss.best), key=f"play_{m.id}"):
                state.ss.mission = m.id
                st.switch_page("ui_pages/play.py")

    st.markdown("### How the game works")
    c = st.columns(4)
    steps = [("1 · Pick a site", "Ten real industrial-zoned plots (URA Master Plan 2019). Each has its own JTC "
                                 "land rent and road distances to every planning area."),
             ("2 · Build a plant", "From a 2 t/day batch kiln to a 100 t/day continuous line. Costs use MOM wages, "
                                   "SP Group power prices and vendor plant prices."),
             ("3 · Watch the numbers", "Feedstock is routed over real roads by a linear program. Cost, credits and "
                                       "haul update instantly."),
             ("4 · Submit & score", "Stars compare you with the NSGA-II optimiser. Badges reward good planning.")]
    for col, (t, d) in zip(c, steps):
        col.markdown(f"<div class='bt-card'><h4>{t}</h4><p class='sub'>{d}</p></div>", unsafe_allow_html=True)

    st.markdown("### Badges")
    C.badge_grid(state.ss.badges)
    with st.expander("Settings"):
        st.caption("Progress is kept for this browser session only.")
        if st.button("Reset all progress"):
            state.reset_all()
            st.rerun()
    st.caption(f"Model inputs fingerprint {b.fingerprint} · FX: ECB {b.fx['date']}")


C.guard(body)
