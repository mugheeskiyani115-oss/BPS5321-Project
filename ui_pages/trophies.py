"""Trophies: level, mission records, badges and the run history."""
import pandas as pd
import streamlit as st

from biotwin import game
from ui import components as C
from ui import state
from ui import theme as T


def body():
    C.hero("Trophy room", "Your planning record", "Stars compare each submission with the NSGA-II optimiser on the "
           "same model. Badges reward good planning habits.")
    C.player_strip()
    st.markdown("### Mission records")
    rows = []
    for m in game.MISSIONS.values():
        best = state.ss.best.get(m.id, {})
        rows.append({"Mission": f"{m.icon} {m.title}", "Stars": "★" * best.get("stars", 0) or "—",
                     "Best score": best.get("score", 0), "Unlocked": "yes" if game.unlocked(m.id, state.ss.best) else "no",
                     "Best layout": ", ".join(f"{c}@{s}" for s, c in best.get("layout", {}).items()) or "—",
                     "Credits sold": "yes" if best.get("credits") else "no" if best else "—"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown("### Badges")
    C.badge_grid(state.ss.badges)
    st.markdown("### Submission history")
    if state.ss.runs:
        hist = pd.DataFrame(state.ss.runs[::-1])
        st.dataframe(hist.round(1), hide_index=True, width="stretch",
                     column_config={"net_cost_sgd_t": st.column_config.NumberColumn("Net cost S$/t", format="%.0f"),
                                    "credits_t": st.column_config.NumberColumn("Credits t/yr", format="%.0f"),
                                    "haul_km": st.column_config.NumberColumn("Haul km", format="%.1f")})
        st.download_button("Download history (CSV)", hist.to_csv(index=False), "biotwin_quest_history.csv", "text/csv",
                           on_click="ignore")
    else:
        st.info("No submissions yet — head to Play.")
    st.caption(T.md("XP = half your best mission scores + 60 per badge. Levels: "
                    + ", ".join(f"{t} ({x:,} XP)" for x, t in game.LEVELS) + "."))


C.guard(body)
