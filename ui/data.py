"""Cached access to the model: bundle, optimiser references and networks."""
from __future__ import annotations

import streamlit as st

from biotwin import forecast as fc
from biotwin import game
from biotwin import network as nw
from biotwin.data import DataMissing, load_bundle


@st.cache_resource(show_spinner=False)
def bundle():
    return load_bundle()


def bundle_or_stop():
    try:
        return bundle()
    except (DataMissing, ValueError) as exc:
        st.error(f"**Data not ready.** {exc}")
        st.stop()


@st.cache_resource(show_spinner="The AI is mapping the best layouts for each mission (first run only, ~1 min)…")
def references(fingerprint: str) -> dict:
    b = bundle()
    refs = game.load_references(b)
    if refs is None:   # parameters changed since the precomputed file: recompute and save
        refs = {mid: game.compute_reference(b, m, seeds=(1,), pop=50, gens=45) for mid, m in game.MISSIONS.items()}
        try:
            game.save_references(b, refs)
        except OSError:
            pass       # read-only hosting: keep the in-memory copy
    return refs


@st.cache_resource(show_spinner=False, max_entries=16)
def network(mission_id: str, sell_credits: bool):
    b = bundle()
    return nw.build_network(b, game.mission_assumptions(b, game.MISSIONS[mission_id], sell_credits))


@st.cache_data(show_spinner=False)
def backtest():
    s = fc.national_series(bundle())
    summary, pts = fc.backtest(s)
    return s, summary, pts
