"""Sources: every parameter with its tag and link, the research-PDF checks, datasets and provenance."""
import pandas as pd
import streamlit as st

from biotwin.data import DATA
from ui import components as C
from ui import data as D
from ui import state

TAG_HELP = {"web": "found on the web (official or published source)", "notebook": "team Notebook 2",
            "derived": "computed from other values with a stated formula", "assumption": "modelling assumption",
            "pdf": "research PDF fallback (no web source found)"}


def body():
    b = D.bundle_or_stop()
    state.visit("data_detective")
    C.hero("Sources", "Where every number comes from", "Web sources first; the team's Notebook 2 for carbon and "
           "feedstock values; the research PDF only where nothing better was found.")
    reg = b.params.reset_index()
    counts = reg.tag.value_counts()
    cols = st.columns(len(TAG_HELP))
    for col, (tag, help_) in zip(cols, TAG_HELP.items()):
        col.metric(tag, int(counts.get(tag, 0)), help_, delta_color="off", delta_arrow="off")
    tags = st.multiselect("Filter by tag", sorted(reg.tag.unique()), default=sorted(reg.tag.unique()))
    st.dataframe(reg[reg.tag.isin(tags)][["key", "value", "low", "high", "unit", "tag", "source", "url", "note"]],
                 hide_index=True, width="stretch",
                 column_config={"url": st.column_config.LinkColumn("Link", display_text="open")})
    st.markdown("#### Plant sizes")
    st.dataframe(b.plants.reset_index(), hide_index=True, width="stretch")
    st.markdown("#### Land rent at each candidate site (JTC posted rates from 1 Jul 2026)")
    st.dataframe(b.sites[["site_id", "name", "region", "jtc_estate", "rent_sgd_m2_yr_with_gst", "match"]],
                 hide_index=True, width="stretch")
    st.markdown("#### Research PDF claims, checked against their links")
    st.dataframe(pd.read_csv(DATA / "params" / "pdf_claim_checks.csv"), hide_index=True, width="stretch")
    st.markdown("#### Open datasets")
    st.markdown("""
| Layer | Source |
|---|---|
| National waste 2000–2025 | NEA / SingStat (data.gov.sg); 2024–25 checked against NEA Annex A |
| Planning areas & regions | URA Master Plan 2019 subzones |
| Managed trees (695,912 matched) | NParks Trees.sg community copy (Oct 2021) |
| Land cover | ESA WorldCover 2021, 10 m |
| Candidate sites | URA Master Plan 2019 land use, *Business 2* clusters |
| Existing facilities | OpenStreetMap via Nominatim |
| Road distances & times | OSRM on OpenStreetMap |
| Exchange rates | European Central Bank reference rates |
""")
    st.code("python -I pipeline/build_data.py all      # rebuild open datasets\n"
            "python -I pipeline/build_game_refs.py     # recompute the optimiser references", language="bash")
    with st.expander("Provenance records"):
        st.json(b.provenance, expanded=False)


C.guard(body)
