"""Session state for the game: one place to create, validate, update and reset it."""
from __future__ import annotations

import time

import streamlit as st

from biotwin import game

VERSION = 3
ss = st.session_state


def init() -> None:
    if ss.get("_state_version") != VERSION:
        for k in list(ss.keys()):
            del ss[k]
        ss["_state_version"] = VERSION
    ss.setdefault("mission", "first_spark")
    ss.setdefault("layouts", {mid: {} for mid in game.MISSIONS})      # mission -> {site_id: size_class}
    ss.setdefault("sell_credits", {mid: False for mid in game.MISSIONS})
    ss.setdefault("best", {})                                         # mission -> {score, stars, layout, credits}
    ss.setdefault("badges", set())
    ss.setdefault("runs", [])                                         # history of submissions
    ss.setdefault("selected_site", None)
    ss.setdefault("last_result", {})                                  # mission -> last debrief
    ss.setdefault("decade", {})                                       # mission -> (df, summary)
    ss.setdefault("new_badges", [])
    # repair anything malformed (e.g. a mission added after the session started)
    for mid in game.MISSIONS:
        ss.layouts.setdefault(mid, {})
        ss.sell_credits.setdefault(mid, False)
    if ss.mission not in game.MISSIONS:
        ss.mission = "first_spark"


def layout(mid: str | None = None) -> dict:
    return ss.layouts[mid or ss.mission]


def set_plant(site_id: str, size_class: str | None, mid: str | None = None) -> None:
    lay = dict(layout(mid))
    if size_class:
        lay[site_id] = size_class
    else:
        lay.pop(site_id, None)
    ss.layouts[mid or ss.mission] = lay
    ss.last_result.pop(mid or ss.mission, None)
    ss.decade.pop(mid or ss.mission, None)


def clear_layout(mid: str | None = None) -> None:
    ss.layouts[mid or ss.mission] = {}
    ss.last_result.pop(mid or ss.mission, None)
    ss.decade.pop(mid or ss.mission, None)


def award(badges: set[str]) -> list[str]:
    new = sorted(set(badges) - ss.badges)
    ss.badges |= set(new)
    ss.new_badges = ss.new_badges + new
    return new


def visit(badge: str) -> None:
    award({badge})


def record(mid: str, result: dict, ev: dict, sell_credits: bool, badges: set[str]) -> dict:
    prev = ss.best.get(mid, {"score": 0, "stars": 0})
    improved = result["score"] > prev["score"] or result["stars"] > prev["stars"]
    if improved:
        ss.best[mid] = {"score": result["score"], "stars": max(result["stars"], prev["stars"]),
                        "layout": dict(ev["config"]), "credits": sell_credits}
    new = award(badges)
    ss.runs.append({"time": time.strftime("%H:%M:%S"), "mission": game.MISSIONS[mid].title, "score": result["score"],
                    "stars": result["stars"], "sites": ev["n_sites"], "net_cost_sgd_t": ev["net_cost_sgd_per_t"],
                    "credits_t": ev["registry_credit_t"], "haul_km": ev["mean_haul_km"],
                    "layout": ", ".join(f"{c}@{s}" for s, c in ev["config"].items())})
    debrief = {"result": result, "improved": improved, "new_badges": new, "previous": prev}
    ss.last_result[mid] = debrief
    return debrief


def xp() -> int:
    return game.total_xp(ss.best, ss.badges)


def reset_all() -> None:
    for k in list(ss.keys()):
        del ss[k]
    init()
