"""Run with: streamlit run app.py

BioTwin | Singapore horticultural waste and *illustrative* biochar planning.
This is a working academic demonstration, NOT a verified operational digital twin.
"""
from pathlib import Path
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from biotwin_core import (Scenario, enumerate_plans, load_optional_planning_areas,
                          load_region_data, solve_plan, validate_operator_data)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
REGIONS = load_region_data(str(DATA / 'region_feedstock_2025.csv'))
ORIGINS, DATA_LEVEL = load_optional_planning_areas(str(DATA / 'planning_area_estimates.csv'), REGIONS)
PROVENANCE = json.loads((DATA / 'provenance.json').read_text(encoding='utf8'))

st.set_page_config(page_title='BioTwin | Singapore pilot', page_icon='🌿', layout='wide')
st.markdown('''<style>
.block-container {padding-top: 1.1rem; max-width: 1300px;}
.hero {background: linear-gradient(110deg,#13353b,#236257); color: white; padding:25px 30px; border-radius:14px; margin-bottom:18px;}
.hero h1 {color:white; margin:0; font-size:2.1rem}
.hero p {color:#ddf5eb; margin:8px 0 0;}
small,.caption{color:#567067}
[data-testid="stMetricValue"] {font-size:1.75rem}
</style>''', unsafe_allow_html=True)
st.markdown('''<div class="hero"><h1>BioTwin Singapore</h1>
<p>Where could horticultural residues be collected and converted to biochar — and what would it cost?</p>
</div>''', unsafe_allow_html=True)
st.warning('**Research prototype, not an investment or carbon credit claim.** Regional waste values are proxy allocations of a real national total. Hub markers are illustrative; road routing, operator validation, permits and registry certification remain outstanding.', icon='🔎')

with st.sidebar:
    st.header('Scenario inputs')
    st.caption('All editable figures below are assumptions unless explicitly sourced. Defaults explore an illustrative 30 t/day biochar programme.')
    tpd = st.slider('Total capacity (wet tonnes/day)', 5, 70, 30, 5)
    days = st.slider('Operating days/year', 200, 365, 300, 5)
    accessible = st.slider('Potentially collectable share of regional proxy (%)', 2, 100, 10, 1)
    with st.expander('Transport assumptions'):
        road_mult = st.slider('Great-circle to road-distance factor', 1.00, 2.25, 1.35, 0.05)
        local_leg = st.slider('Local collection distance allowance (km)', 0, 20, 5)
        t_cost = st.number_input('Transport cost (S$/tonne-km)', 0.0, 3.0, 0.30, step=0.05)
        t_ef = st.number_input('Transport emissions (kg CO2e/tonne-km)', 0.0, 2.0, 0.12, step=0.02)
    with st.expander('Carbon model (illustrative decomposition)'):
        stored = st.number_input('Gross stored carbon (tCO2/wet tonne)', 0.0, 1.5, 0.372, step=0.01)
        p_em = st.number_input('Processing emissions (tCO2e/wet tonne)', 0.0, 1.5, 0.100, step=0.01)
        op_debit = st.number_input('Existing biomass-energy opportunity debit (tCO2e/wet tonne)', 0.0, 1.5, 0.177, step=0.01)
        st.caption('The latter two default values are an illustrative split of 0.277, inferred from the earlier 0.372 gross vs 0.095 net example. Not a measured inventory.')
    with st.expander('Project economics (illustrative)'):
        plant_cost = st.number_input('Processing cost (S$/wet tonne)', 0.0, 1500.0, 310.0, step=10.0)
        product_sales = st.number_input('Product / other revenue (S$/wet tonne)', 0.0, 1200.0, 92.0, step=10.0)
        site_cost = st.number_input('Additional fixed overhead per hub (S$/year)', 0.0, 1_000_000.0, 50_000.0, step=10_000.0)
        gate_fee = st.number_input('Gate fee (S$/wet tonne)', 0.0, 800.0, 0.0, step=10.0)
    with st.expander('Unverified carbon credit sensitivity ONLY'):
        credit_eligible = st.checkbox('Explore hypothetical credit eligibility', value=False)
        credit_qty = st.number_input('Assumed *issued* credits (tCO2e/wet tonne)', 0.0, 1.0, 0.0, step=0.05,
                                      disabled=not credit_eligible)
        credit_price = st.number_input('Hypothetical credit sales price (S$/credit)', 0.0, 1000.0, 0.0, step=20.0,
                                        disabled=not credit_eligible)
        st.caption('Carbon storage, net climate benefit and issued credits are THREE different quantities. Singapore carbon tax S$45/t is not a credit sale price.')

CFG = Scenario(throughput_t_per_day=float(tpd), operating_days=int(days),
               accessible_fraction=accessible/100, road_distance_multiplier=road_mult,
               first_last_mile_km=float(local_leg), transport_cost_sgd_per_tkm=t_cost,
               transport_emissions_kgco2e_per_tkm=t_ef,
               processing_cost_sgd_per_t=plant_cost,
               additional_hub_cost_sgd_per_year=site_cost,
               product_revenue_sgd_per_t=product_sales,
               gate_fee_sgd_per_t=gate_fee, stored_co2_t_per_wet_t=stored,
               process_emission_t_per_wet_t=p_em,
               baseline_opportunity_debit_t_per_wet_t=op_debit,
               assume_credit_eligible=credit_eligible,
               assumed_issued_credit_t_per_wet_t=credit_qty,
               credit_price_sgd_per_tco2e=credit_price)

national_total = REGIONS.estimated_t.sum()
met = st.columns(4)
met[0].metric('2025 national waste reported', f'{national_total:,.0f} t')
met[1].metric('Regional allocation basis', '5 regions', 'estimated, not measured', delta_color='off')
met[2].metric('Planned pilot annual throughput', f'{CFG.annual_t:,.0f} t')
met[3].metric('2025 independent regional validation', 'Not available')

explore, compare, accounting, validation, methods = st.tabs([
    '01  Feedstock map', '02  Site comparison', '03  Carbon and economics',
    '04  Validation', '05  Evidence and methods'])

with explore:
    st.subheader('National statistics anchored to spatial proxies')
    st.write('The 2025 national total is reported by NEA. The five regional shares below are estimates derived from 2021 managed-tree and land-cover proxies. **No regional 2025 waste measurements have been supplied.**')
    left, right = st.columns([1.2, 1])
    with left:
        mapfig = px.scatter_map(REGIONS, lat='latitude', lon='longitude', size='estimated_t',
                                  color='estimated_t', hover_name='region',
                                  hover_data={'share_pct':':.1f','estimated_t':':,.0f','latitude':False,'longitude':False},
                                  color_continuous_scale='Tealgrn', zoom=9.3, height=455,
                                  map_style='open-street-map',
                                  size_max=55, center={'lat':1.355,'lon':103.817})
        mapfig.update_layout(margin=dict(l=0,r=0,t=10,b=0),
                             coloraxis_colorbar_title='Proxy tonnes')
        st.plotly_chart(mapfig, width='stretch')
        st.caption('Region anchor coordinates are approximate display points, not actual regional polygon centroids.')
    with right:
        g = REGIONS.sort_values('estimated_t')
        fig = go.Figure()
        fig.add_trace(go.Bar(y=g.region, x=g.estimated_t, orientation='h', marker_color='#188a75', name='Equal-weight allocation'))
        for _,r in g.iterrows():
            fig.add_shape(type='line',x0=r.p05_t,x1=r.p95_t,y0=r.region,y1=r.region,
                          line={'width':4,'color':'#e69b3c'})
        fig.update_layout(title='2025 estimated waste by region',xaxis_title='Wet tonnes/year',
                          yaxis_title='',height=430,margin=dict(l=10,r=10,b=20,t=50),showlegend=False)
        st.plotly_chart(fig, width='stretch')
        st.caption('Orange segments: 5th–95th percentile variation across proxy weight choices, NOT observed error or 90% prediction intervals.')
    st.dataframe(REGIONS[['region','estimated_t','share_pct','p05_t','p95_t','recorded_trees']].rename(columns={
        'region':'Region','estimated_t':'Estimated waste (t/yr)','share_pct':'Share (%)',
        'p05_t':'Sensitivity low (t)','p95_t':'Sensitivity high (t)','recorded_trees':'2021 inventoried trees'}),
        hide_index=True,width='stretch')
    st.info('Original notebook: median spatial ranking Spearman ρ = 0.967 under 2,000 changes to proxy weights. This measures **internal ranking stability**, not agreement with real collections.')
    st.caption(f'Origin granularity used in route analysis: {DATA_LEVEL}. To use 55 planning areas, rerun the revised EDA notebook and copy the exported `planning_area_estimates.csv` to the app data folder.')

with compare:
    st.subheader('Select candidate hub anchors and compare configurations')
    st.write('The map points represent **illustrative regional anchors** only. Select points directly on the map, or use the region selector. The models allocate exactly the same annual feedstock throughput across the chosen hubs.')
    def _map_selection_callback():
        # Streamlit runs the callback before rebuilding the widgets. Each region
        # is drawn as a separate one-point Plotly trace, so curve_number maps
        # to a region label. The selector is an accessible fallback.
        event = st.session_state.get('candidate_map', {})
        selection = event.get('selection', {}) if hasattr(event, 'get') else {}
        points = selection.get('points', []) if hasattr(selection, 'get') else []
        clicked = sorted({REGIONS.region.iloc[int(pt['curve_number'])]
                          for pt in points if 'curve_number' in pt and
                          0 <= int(pt['curve_number']) < len(REGIONS)})
        if clicked:
            st.session_state['selected_hubs'] = clicked
    chosen = st.multiselect('Candidate regions to host illustrative processing hubs',
                            options=REGIONS.region.tolist(),default=['Central','West','East'],
                            key='selected_hubs')
    st.caption('Map: click a marker or use the selection tools for multiple markers. The region selector above also works if your browser does not support map selection.')
    hfig = go.Figure()
    for r in REGIONS.itertuples():
        active = r.region in chosen
        hfig.add_trace(go.Scattermap(lat=[r.latitude],lon=[r.longitude],
                           mode='markers+text',text=[r.region],textposition='top center',name=r.region,
                           marker={'size':25 if active else 15,'color':'#126b50' if active else '#9daeb0'},
                           hovertemplate=f'<b>{r.region}</b><br>Illustrative anchor, not a permit-approved site<extra></extra>'))
    hfig.update_layout(map={'style':'open-street-map','zoom':9.5,'center':{'lat':1.355,'lon':103.816}},
                       height=390,margin={'l':0,'r':0,'t':0,'b':0},showlegend=False)
    st.plotly_chart(hfig,width='stretch',key='candidate_map',
                    on_select=_map_selection_callback,
                    selection_mode=['points','box','lasso'])
    if not chosen:
        st.warning('Choose at least one candidate hub region.')
    else:
        try:
            candidate = solve_plan(ORIGINS, REGIONS, chosen, CFG)
            all_opts, plans = enumerate_plans(ORIGINS, REGIONS, CFG)
            central_cases = [p for p in plans if p['n_hubs']==1]
            central = min(central_cases, key=lambda p: p['cost_sgd'])
            st.caption(f'Comparison baseline: least-cost single hub among the same five illustrative anchors ({central["sites"][0]}). Equal total throughput in both scenarios: {CFG.annual_t:,.0f} t/year.')
            comparison = pd.DataFrame([
                {'Scenario':f'One hub: {central["sites"][0]}','Hub count':1,
                 'Mean approx haul (km)':central['avg_haul_km'],
                 'Annual transport cost (S$)':central['transport_cost_sgd'],
                 'Total annual cost (S$)':central['cost_sgd'],
                 'Net climate benefit (tCO2e/yr)':central['net_climate_benefit_t'],
                 'Annual margin (S$)':central['margin_sgd']},
                {'Scenario':'Selected hubs: '+', '.join(candidate['sites']),
                 'Hub count':candidate['n_hubs'],
                 'Mean approx haul (km)':candidate['avg_haul_km'],
                 'Annual transport cost (S$)':candidate['transport_cost_sgd'],
                 'Total annual cost (S$)':candidate['cost_sgd'],
                 'Net climate benefit (tCO2e/yr)':candidate['net_climate_benefit_t'],
                 'Annual margin (S$)':candidate['margin_sgd']},
            ])
            st.dataframe(comparison,hide_index=True,width='stretch')
            dcost = candidate['cost_sgd']-central['cost_sgd']
            dcarbon = candidate['net_climate_benefit_t']-central['net_climate_benefit_t']
            cols=st.columns(3)
            cols[0].metric('Change in annual total cost',f'S${dcost:,.0f}')
            cols[1].metric('Change in net climate benefit',f'{dcarbon:+,.1f} tCO2e')
            cols[2].metric('Change in mean approximate haul',f'{candidate["avg_haul_km"]-central["avg_haul_km"]:+.1f} km')
            st.subheader('All feasible hub combinations: exact candidate enumeration')
            pf = px.scatter(all_opts, x='cost_sgd',y='net_climate_t',color='pareto',symbol='n_hubs',
                            hover_name='sites',hover_data=['n_hubs','mean_haul_km','margin_sgd'],
                            color_discrete_map={True:'#147f61',False:'#adbcb7'},
                            labels={'cost_sgd':'Annual cost (S$)','net_climate_t':'Illustrative net benefit (tCO2e/yr)',
                                    'pareto':'Pareto efficient','n_hubs':'Number of hubs'})
            pf.update_layout(height=425,margin=dict(t=20,l=10,r=15,b=20))
            st.plotly_chart(pf,width='stretch')
            st.caption('Green = not dominated in annual cost and net climate benefit among 31 enumerated combinations. This is **exhaustive small-set screening**, not NSGA-II or a certified facility siting optimization.')
            with st.expander('Inspect actual tonne assignments for your selected hubs'):
                st.dataframe(candidate['flows'],hide_index=True,width='stretch')
                st.download_button('Download allocation CSV',candidate['flows'].to_csv(index=False),
                                   'biotwin_selected_allocation.csv','text/csv')
            st.download_button('Download all scenario combinations CSV',all_opts.to_csv(index=False),
                               'biotwin_illustrative_site_options.csv','text/csv')
        except (ValueError,RuntimeError) as exc:
            st.error(f'Infeasible assumptions: {exc}. Increase the accessible share or lower throughput.')

with accounting:
    st.subheader('Three distinct carbon concepts')
    st.latex(r'\mathrm{Net\ benefit} = \mathrm{Stored\ carbon} - \mathrm{Processing\ emissions} - \mathrm{Baseline\ opportunity\ debit} - \mathrm{Extra\ transport}')
    st.write('Carbon credits are a separate certificate quantity that requires approved methodology, additionality, monitoring, records and independent verification. They are **not** automatically equal to either stored carbon or net climate benefit.')
    try:
        ref = solve_plan(ORIGINS,REGIONS,['Central'],CFG)
        c = st.columns(4)
        c[0].metric('Gross stored carbon', f'{ref["gross_stored_co2_t"]:,.0f} tCO2')
        c[1].metric('Net climate benefit vs baseline', f'{ref["net_climate_benefit_t"]:,.0f} tCO2e')
        c[2].metric('Assumed issued credits', f'{ref["assumed_credit_issued_t"]:,.0f} tCO2e')
        c[3].metric('Gate fee to break even', f'S${ref["break_even_gate_sgd_per_t"]:,.0f}/t')
        components = pd.DataFrame({
            'Category':['Durable storage','Processing emissions','Existing energy benefit foregone','Extra transport'],
            'tCO2e':[ref['gross_stored_co2_t'], -ref['process_emissions_t'],
                     -ref['baseline_opportunity_debit_t'],-ref['transport_emissions_t']]})
        fig=px.bar(components,x='Category',y='tCO2e',color='tCO2e',color_continuous_scale='RdYlGn',
                   title='Illustrative annual carbon ledger, one Central anchor')
        fig.update_layout(showlegend=False,coloraxis_showscale=False)
        st.plotly_chart(fig,width='stretch')
        st.write('**Worked example reported in the interim submission:** S$92/t revenue against S$310/t cost gives S$−218/t margin, BEFORE any newly modelled transport, site overhead or gate revenue. These values are assumptions, not local vendor quotations.')
        st.info('The 2026–2027 Singapore carbon tax is S$45/tCO2e for covered emitters; it is not used as a biochar credit sales price. This tool defaults to zero issued credits and zero credit revenue.')
    except ValueError as exc:
        st.error(str(exc))

with validation:
    st.subheader('Independent operational validation — pending')
    st.write('The reviewer correctly distinguishes *sensitivity to chosen proxy weights* from *evidence of actual regional horticultural waste*. An external operator or collection dataset is needed to estimate regional errors.')
    st.download_button('Download operator record template', (DATA / 'operator_validation_TEMPLATE.csv').read_text(),
                       'operator_validation_TEMPLATE.csv','text/csv')
    upload = st.file_uploader('Upload REAL 2025 region level observed waste records as CSV', type=['csv'])
    if upload is None:
        st.warning('No independent records provided. **Regional prediction accuracy has NOT been calculated.** Do not interpret the 5–95% weight sensitivity intervals as measured accuracy.')
    else:
        try:
            actual = pd.read_csv(upload)
            val = validate_operator_data(REGIONS,actual)
            st.metric('Weighted absolute percentage error (observed matched regions)',f'{100*val["wape"]:.1f}%')
            st.metric('Regions with comparable 2025 records',f'{val["compared"]}/{len(REGIONS)}')
            if pd.notna(val['rank_spearman']):
                st.metric('Measured vs estimated ranking Spearman ρ',f'{val["rank_spearman"]:.3f}')
            st.dataframe(val['comparison'][['region','estimated_t','observed_t','error_t','source']],
                         hide_index=True,width='stretch')
            st.caption('Comparability must be assessed manually: collection boundaries, tree vs other horticultural wastes, time period and double counting can bias error metrics.')
        except (ValueError,pd.errors.ParserError) as exc:
            st.error(f'Cannot validate submitted records: {exc}')
    st.markdown('**Minimum next evidence:** operator or town council waste collection records, actual collection depot locations, local haul contracts, plant quotations, moisture / biochar yields, baseline waste fates, and carbon methodology eligibility.')
    st.markdown('**Model score already measured (but for a different target):** Random Forest R² = 0.364 and MAE = 0.997 in log(1 + managed-tree biomass proxy) for held-out planning-area groups. These are NOT monthly waste prediction scores.')

with methods:
    st.subheader('Evidence, assumptions and implementation status')
    evidence = [
        ('NEA national horticultural total','Reported, 2025, 232,000 t'),
        ('Managed-tree and land-cover spatial allocation','Implemented in original EDA; proxy only'),
        ('Proxy weights: 2,000 sampled alternatives','Completed sensitivity analysis; no operational validation'),
        ('Satellite random forest','Exploratory regression of managed-tree biomass proxy; limited R²'),
        ('Interactive regional map and site selection','Implemented as demonstrator with approximate map anchors'),
        ('Fixed-throughput hub allocation LP','Implemented, approximate transport distances; no road routing'),
        ('Small candidate combination Pareto plot','Implemented as exhaustive enumeration; no NSGA-II'),
        ('Biochar climate and financial calculation','Implemented as editable, explicitly illustrative inputs'),
        ('Carbon credit issuance and dMRV','NOT implemented; no registry certification'),
        ('True planning-area map','Only when original EDA is rerun and optional CSV is exported'),
        ('Facility permits, quotations and operator validation','NOT implemented'),
        ('Worldwide applicability / monthly waste forecasts','Not supported by demonstrated research')]
    st.dataframe(pd.DataFrame(evidence,columns=['Component','Evidence / status']),hide_index=True,width='stretch')
    st.markdown('**Sources and references:**')
    st.markdown('''
    * [NEA, Waste Statistics and Overall Recycling (2025)](https://www.nea.gov.sg/our-services/waste-management/waste-statistics-and-overall-recycling)
    * [NCCS, Singapore carbon tax](https://www.nccs.gov.sg/singapores-climate-action/mitigation-efforts/carbontax/)
    * [EMA, Singapore Energy Statistics](https://www.ema.gov.sg/resources/singapore-energy-statistics/chapter2)
    * [Puro.earth, current biochar methodology](https://puro.earth/methodologies/biochar/)
    * [REopt tool — interface inspiration, not equivalent technology model](https://reopt.nlr.gov/tool/)
    * [URA Master Plan](https://data.gov.sg/) and [ESA WorldCover 2021](https://esa-worldcover.org/), as referenced in the submitted notebook.
    ''')
    st.json(PROVENANCE,expanded=False)
    st.caption('This demonstration does not ingest live public databases at runtime. Reproducibility depends on rerunning the archived EDA notebook to regenerate its detailed inputs.')
