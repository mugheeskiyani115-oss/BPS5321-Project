"""3D pydeck maps on an OpenStreetMap basemap (OpenFreeMap dark style)."""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from . import theme as T

TOOLTIP = {"html": "<b>{name_html}</b><br/>{val}",
           "style": {"backgroundColor": "#0d0d0d", "color": "#f0efec", "fontSize": "12px"}}


def area_layer(b, values: np.ndarray, unit: str = "t/yr", height_m: float = 1400, opacity: float = 0.85):
    if b.geojson is None:
        return None
    gj = copy.deepcopy(b.geojson)
    lut = dict(zip(b.areas.planning_area, values))
    vmax = max(float(np.max(values)), 1e-9)
    for f in gj["features"]:
        pa = f["properties"]["planning_area"]
        v = float(lut.get(pa, 0.0))
        f.update({"name_html": pa.title(), "val": f"{v:,.0f} {unit}", "elev": v / vmax * height_m,
                  "fill": T.ramp(v, vmax)})
    return pdk.Layer("GeoJsonLayer", gj, id="areas", extruded=True, wireframe=False, get_elevation="elev",
                     get_fill_color="fill", get_line_color=[255, 255, 255, 40], pickable=True, opacity=opacity)


def site_layers(net, layout: dict, plant_labels: dict, throughput: dict | None = None,
                selected: str | None = None, facilities: pd.DataFrame | None = None) -> list:
    sites = net.sites.copy()
    throughput = throughput or {}
    sites["built"] = sites.site_id.isin(layout)
    sites["t"] = sites.site_id.map(lambda s: throughput.get(s, 0.0))
    tmax = max(sites.t.max(), 1.0)
    sites["elev"] = np.where(sites.built, 1700 + sites.t / tmax * 2600, 1500)
    sites["color"] = [T.rgb(T.ORANGE) if b_ else T.rgb(T.MUTED, 210) for b_ in sites.built]
    sites["name_html"] = sites.site_id + " · " + sites.name
    sites["val"] = [f"{plant_labels.get(layout.get(s), '')} · {t:,.0f} t/yr" if b_ else
                    f"Empty plot · JTC rent S${r:,.2f}/m²/yr" for s, t, b_, r in
                    zip(sites.site_id, sites.t, sites.built, sites.rent_sgd_m2_yr_with_gst)]
    layers = [pdk.Layer("ColumnLayer", sites, id="sites", get_position=["longitude", "latitude"],
                        get_elevation="elev", radius=430, get_fill_color="color", extruded=True, pickable=True,
                        auto_highlight=True),
              pdk.Layer("TextLayer", sites, id="site_labels", get_position=["longitude", "latitude"],
                        get_text="site_id", get_size=13, get_color=T.rgb(T.INK), get_pixel_offset=[0, -20],
                        billboard=True)]
    if selected is not None and selected in set(sites.site_id):
        sel = sites[sites.site_id == selected].assign(z=1600)
        layers.append(pdk.Layer("ScatterplotLayer", sel, id="selected", get_position=["longitude", "latitude", "z"],
                                get_radius=900, stroked=True, filled=False, get_line_color=T.rgb(T.INK),
                                line_width_min_pixels=3))
    if facilities is not None and len(facilities):
        fac = facilities.assign(name_html=facilities.name, val=facilities.facility_type, elev=2000)
        layers.append(pdk.Layer("ColumnLayer", fac, id="facilities", get_position=["longitude", "latitude"],
                                get_elevation="elev", radius=250, get_fill_color=T.rgb(T.AQUA), extruded=True,
                                pickable=True))
    return layers


def flow_layer(flows: pd.DataFrame):
    if flows is None or not len(flows):
        return None
    fl = flows.assign(w=lambda d: 1 + 8 * d.tonnes / d.tonnes.max(),
                      name_html=lambda d: d.origin.str.title() + " → " + d.site_id,
                      val=lambda d: d.tonnes.map("{:,.0f} t/yr".format) + " · " + d.road_km.map("{:.1f} km".format)
                      + " · S$" + d.haul_sgd_t.map("{:.0f}/t".format))
    return pdk.Layer("ArcLayer", fl, id="flows", get_source_position=["o_lon", "o_lat"],
                     get_target_position=["s_lon", "s_lat"], get_width="w", get_source_color=T.rgb(T.BLUE, 200),
                     get_target_color=T.rgb(T.ORANGE, 230), get_height=0.35, pickable=True)


def deck(layers: list, *, key: str, height: int = 560, zoom: float = 10.45, pitch: int = 50,
         selectable: bool = False):
    view = pdk.ViewState(latitude=1.318, longitude=103.815, zoom=zoom, pitch=pitch, bearing=-10)
    d = pdk.Deck(layers=[l for l in layers if l is not None], initial_view_state=view, map_style=T.BASEMAP,
                 map_provider="carto", tooltip=TOOLTIP)
    if selectable:
        event = st.pydeck_chart(d, height=height, key=key, on_select="rerun", selection_mode="single-object")
    else:
        event = st.pydeck_chart(d, height=height, key=key)
    st.caption(T.ATTRIBUTION + " · drag to pan · right-drag to tilt")
    return event


def clicked_site(event) -> str | None:
    """Site id from a pydeck selection event, if the user clicked a site column."""
    try:
        objs = event.selection.objects.get("sites") or []
        return objs[0].get("site_id") if objs else None
    except AttributeError:
        return None
