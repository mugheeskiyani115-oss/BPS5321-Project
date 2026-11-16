"""Dark game theme: palette (dark-mode steps of the validated reference palette), CSS and chart styling."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

# categorical (dark steps) - fixed order, max three on any map
BLUE, ORANGE, AQUA = "#3987e5", "#d95926", "#199e70"
INK, INK2, MUTED = "#f0efec", "#c3c2b7", "#898781"
GRID, AXIS, SURFACE, PLANE = "#2c2c2a", "#383835", "#1a1a19", "#0d0d0d"
GOOD, WARNING, CRITICAL = "#0ca30c", "#fab219", "#d03b3b"
STAR = "#e8b931"
# sequential blue for the dark surface: low magnitude recedes (dark), high magnitude is bright
SEQ = ["#104281", "#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#86b6ef", "#b7d3f6"]
BASEMAP = "https://tiles.openfreemap.org/styles/dark"
ATTRIBUTION = "Map data © OpenStreetMap contributors · tiles © OpenFreeMap · roads via OSRM"

CSS = """
<style>
.block-container {padding-top: 3.4rem; max-width: 1380px;}
h1, h2, h3 {letter-spacing: -0.01em;}
.bt-hero {background: radial-gradient(1200px 300px at 10% 0%, #1f4d3f 0%, #10231d 55%, #0d0d0d 100%);
  border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 26px 30px; margin-bottom: 18px;}
.bt-hero h1 {margin: 0; font-size: 2.2rem; color: #f0efec;}
.bt-hero p {margin: 6px 0 0; color: #c3c2b7; font-size: 1.02rem;}
.bt-kicker {text-transform: uppercase; letter-spacing: .14em; font-size: .72rem; color: #1baf7a; font-weight: 700;}
.bt-card {background: #1a1a19; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 16px 18px;
  height: 100%;}
.bt-card.locked {opacity: .45;}
.bt-card h4 {margin: 0 0 4px; font-size: 1.08rem; color: #f0efec;}
.bt-card .sub {color: #c3c2b7; font-size: .88rem; margin: 0 0 10px;}
.bt-stars {color: #e8b931; font-size: 1.15rem; letter-spacing: 2px;}
.bt-stars .off {color: #383835;}
.bt-pill {display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .75rem; font-weight: 600;
  background: rgba(255,255,255,0.06); color: #c3c2b7; margin-right: 6px;}
.bt-pill.good {background: rgba(12,163,12,.16); color: #5fd35f;}
.bt-pill.warn {background: rgba(250,178,25,.16); color: #fab219;}
.bt-badge {background: #1a1a19; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px;
  text-align: center; height: 100%;}
.bt-badge .ico {font-size: 1.8rem;}
.bt-badge .nm {font-weight: 700; color: #f0efec; font-size: .9rem; margin-top: 4px;}
.bt-badge .ds {color: #898781; font-size: .76rem;}
.bt-badge.locked {filter: grayscale(1); opacity: .35;}
.bt-check {padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: .93rem;}
.bt-check .d {color: #898781; font-size: .82rem; margin-left: 6px;}
.bt-year {background: #1a1a19; border-radius: 10px; padding: 10px; border: 1px solid rgba(255,255,255,0.08);
  font-size: .78rem; min-height: 112px;}
.bt-year b {font-size: .95rem; color: #f0efec;}
.bt-muted {color: #898781; font-size: .85rem;}
[data-testid="stMetricValue"] {font-size: 1.55rem;}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def md(text: str) -> str:
    """Escape '$' so markdown does not render S$/US$ amounts as LaTeX."""
    return str(text).replace("$", "\\$")


def h(text: str) -> str:
    """Make '$' safe inside raw HTML blocks (markdown escapes are not consumed there)."""
    return str(text).replace("$", "&#36;")


def rgb(hex_: str, alpha: int = 255) -> list[int]:
    h = hex_.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def ramp(v: float, vmax: float, alpha: int = 225) -> list[int]:
    x = 0.0 if vmax <= 0 else min(max(v / vmax, 0.0), 1.0) * (len(SEQ) - 1)
    i = min(int(x), len(SEQ) - 2)
    a, b = np.array(rgb(SEQ[i])[:3]), np.array(rgb(SEQ[i + 1])[:3])
    return [int(c) for c in a + (b - a) * (x - i)] + [alpha]


def stars(n: int, of: int = 3) -> str:
    return f"<span class='bt-stars'>{'★' * n}<span class='off'>{'★' * (of - n)}</span></span>"


def style(fig: go.Figure, height: int = 360, **kw) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=36, b=10), template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=INK2),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), hoverlabel=dict(namelength=-1),
                      **kw)
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS)
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS)
    return fig


def money(x: float, unit: str = "") -> str:
    """S$ with M/k scaling and a real minus sign."""
    if x is None or not np.isfinite(x):
        return "—"
    sign = "−" if x < 0 else ""
    v = abs(x)
    s = f"{v / 1e6:,.2f}M" if v >= 1e6 else f"{v / 1e3:,.0f}k" if v >= 1e4 else f"{v:,.0f}"
    return f"{sign}S${s}{unit}"
