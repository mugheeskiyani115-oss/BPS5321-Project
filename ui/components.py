"""Reusable UI pieces: error guard, hero, mission cards, badges, objective checklist, notifications."""
from __future__ import annotations

import traceback

import streamlit as st

from biotwin import game
from biotwin.data import DataMissing

from . import state, theme as T


def guard(fn, *args, **kwargs):
    """Run a page body; show a readable error instead of crashing the app."""
    try:
        return fn(*args, **kwargs)
    except (ValueError, RuntimeError, KeyError, DataMissing) as exc:
        st.error(f"Something in this view could not be computed: {exc}")
    except Exception as exc:  # last-resort safety net
        st.error(f"Unexpected error: {type(exc).__name__}: {exc}")
        with st.expander("Technical details"):
            st.code(traceback.format_exc())


def hero(kicker: str, title: str, text: str) -> None:
    st.markdown(f"<div class='bt-hero'><div class='bt-kicker'>{kicker}</div><h1>{title}</h1><p>{text}</p></div>",
                unsafe_allow_html=True)


def player_strip() -> None:
    lv = game.level_for(state.xp())
    c = st.columns([2.2, 1, 1, 1])
    with c[0]:
        nxt = f"{lv['next_at'] - lv['xp']:,} XP to next level" if lv["next_at"] else "Max level"
        st.markdown(f"**Level {lv['level']} · {lv['title']}** <span class='bt-muted'>({lv['xp']:,} XP · {nxt})</span>",
                    unsafe_allow_html=True)
        st.progress(min(max(lv["progress"], 0.0), 1.0))
    total_stars = sum(v.get("stars", 0) for v in state.ss.best.values())
    c[1].metric("Stars", f"{total_stars} / {3 * len(game.MISSIONS)}")
    c[2].metric("Badges", f"{len(state.ss.badges)} / {len(game.BADGES)}")
    c[3].metric("Missions cleared", f"{sum(1 for v in state.ss.best.values() if v.get('stars', 0) >= 1)} / "
                                    f"{len(game.MISSIONS)}")


def mission_card(m: game.Mission, best: dict, is_unlocked: bool, key: str) -> bool:
    b = best.get(m.id, {})
    locked = "" if is_unlocked else " locked"
    lock_txt = "" if is_unlocked else f"🔒 Clear {game.MISSIONS[m.unlock_after].title} to unlock"
    st.markdown(
        f"<div class='bt-card{locked}'><h4>{m.icon} {m.title}</h4><p class='sub'>{m.tagline}</p>"
        f"{T.stars(b.get('stars', 0))}<br/><span class='bt-pill'>{m.target_t:,.0f} t/yr</span>"
        f"<span class='bt-pill'>S&#36;{m.budget_sgd / 1e6:,.0f}M budget</span>"
        f"<span class='bt-pill'>best {b.get('score', 0):,}</span><p class='bt-muted'>{lock_txt}</p></div>",
        unsafe_allow_html=True)
    return st.button("Play" if is_unlocked else "Locked", key=key, disabled=not is_unlocked, width="stretch",
                     type="primary" if is_unlocked and not b else "secondary")


def badge_grid(earned: set[str], cols: int = 6) -> None:
    items = list(game.BADGES.items())
    for i in range(0, len(items), cols):
        row = st.columns(cols)
        for col, (bid, (ico, name, desc)) in zip(row, items[i:i + cols]):
            cls = "" if bid in earned else " locked"
            col.markdown(f"<div class='bt-badge{cls}'><div class='ico'>{ico}</div><div class='nm'>{name}</div>"
                         f"<div class='ds'>{desc}</div></div>", unsafe_allow_html=True)


def checklist(checks: list) -> None:
    html = ""
    for label, ok, detail in checks:
        mark = "✅" if ok else "⬜"
        html += f"<div class='bt-check'>{mark} {T.h(label)}<span class='d'>{T.h(detail)}</span></div>"
    st.markdown(html, unsafe_allow_html=True)


def flush_badge_toasts() -> None:
    for bid in state.ss.new_badges:
        ico, name, _ = game.BADGES[bid]
        st.toast(f"Badge unlocked: {name}", icon=ico)
    state.ss.new_badges = []
