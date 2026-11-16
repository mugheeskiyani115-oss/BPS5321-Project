"""BioTwin Quest — plan Singapore's horticultural-waste-to-biochar network as a game, on a real model.

Run:  streamlit run app.py
Pages: Mission hub · Play · Trophies · Lab (analysis) · Sources.
"""
import streamlit as st

from ui import components as C
from ui import state, theme

st.set_page_config(page_title="BioTwin Quest", page_icon="🌿", layout="wide", initial_sidebar_state="collapsed")
theme.inject()
state.init()

PAGES = [
    st.Page("ui_pages/hub.py", title="Mission hub", icon="🏠", url_path="hub", default=True),
    st.Page("ui_pages/play.py", title="Play", icon="🎮", url_path="play"),
    st.Page("ui_pages/trophies.py", title="Trophies", icon="🏆", url_path="trophies"),
    st.Page("ui_pages/lab.py", title="Lab", icon="🔬", url_path="lab"),
    st.Page("ui_pages/sources.py", title="Sources", icon="📚", url_path="sources"),
]
nav = st.navigation(PAGES, position="top")
C.flush_badge_toasts()
nav.run()
