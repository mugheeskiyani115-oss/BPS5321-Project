"""Run without Streamlit: python run_example.py"""
from pathlib import Path
from biotwin_core import *

root=Path(__file__).resolve().parent
region=load_region_data(str(root/'data'/'region_feedstock_2025.csv'))
origins,description=load_optional_planning_areas(str(root/'data'/'planning_area_estimates.csv'),region)
conf=Scenario()
options,all_plans=enumerate_plans(origins,region,conf)
central=min((p for p in all_plans if p['n_hubs']==1),key=lambda p:p['cost_sgd'])
three=solve_plan(origins,region,['Central','West','East'],conf)
print('Input:',description, '| national total',region.estimated_t.sum(),'t')
for label,p in [('Best one-hub case',central),('Three-hub example',three)]:
    print(f"{label}: {p['sites']} | {p['annual_t']:,.0f} t/y | avg haul {p['avg_haul_km']:.2f} km | "
          f"cost S${p['cost_sgd']:,.0f} | net climate {p['net_climate_benefit_t']:.1f} tCO2e/y")
options.to_csv(root/'data'/'EXAMPLE_31_hub_combinations.csv',index=False)
print('Scenario CSV exported')
