# BPS5231 interim feedback — disposition

| Feedback | Correction made | Evidence / limitation |
|---|---|---|
| Narrow research to Singapore feedstock and one conversion | Scope now Singapore + pyrolysis-to-biochar only | Revised writeup sections 1 and 5, deck slides 4 and 10 |
| Biomass stock is not waste generated | Model regional tonnes explicitly labelled proxy allocation | Revised EDA cell 30, writeup section 3, Streamlit Feedstock tab |
| Validate regional tonnages vs independent collections | Real-data upload with WAPE and ranking; blank template | App Validation tab; **records not supplied so no empirical validation claimed** |
| Robust proxy rank does not demonstrate actual waste | Sensitivity intervals and median rho 0.967 shown as weight sensitivity only | EDA revisions, slide 7 |
| R2=0.364 is not monthly waste prediction | Exact target and GroupKFold explained; no claims of global transfer | EDA section 5, slide 8 |
| Weather cannot prove maintenance schedules cause fluctuations | Corrected causal language | EDA interpretation cell 19, slide 9 |
| Stored carbon, net climate and credit eligibility conflated | Separate tCO2 stored, tCO2e net, *assumed issued credits* (default zero) and carbon tax | App Carbon tab, writeup section 5, slide 10 |
| Show arithmetic supporting pyrolysis case | S$92 revenue minus S$310 cost equals S$−218/t; 0.372 gross less 0.277 total debit equals 0.095 net | Code default scenario reconciliation unit test; app, slides 10–11 |
| Separate EDA from future optimization and app | EDA notebook revised, functioning Streamlit and LP / exact enumeration built | App and code tests; **NSGA-II remains future work** |
| Let users select candidate sites and compare centralized vs decentralized | Interactive map selection and multiselect backup; equal 9,000 t/y comparator and cost / carbon tradeoffs | App Site comparison tab, slides 12–14; site locations are illustrative |
| REopt example for inputs to outputs | Input → configure → calculate → compare → interpret economic outputs | App and slide 12; different underlying technology model |

## Additional analytical correction

The source notebook's `SCENARIO_WINDOW=10` accidentally cut at `END_YEAR=2026`, thereby extracting **2017–2025 (9 observations)**. The revised code uses `horti.generated.loc[:REFERENCE_YEAR].dropna().tail(SCENARIO_WINDOW)`, giving 2016–2025, with P10 ≈ 231k t, median ≈ 317k t, P90 ≈ 412k t from the embedded national series. The amended cell's stale saved output has been cleared. Rerun with accessible source data before final academic submission.

## Academic honesty / delivery boundary

- Existing notebook results are retained from the user's submission; the whole EDA **has not been rerun** in this offline package because its external geospatial source files were not provided.
- Core Python functions passed six automated tests; the Streamlit UI was syntax checked and its app code generated but **not browser tested** in this runtime because Streamlit is not installed here.
- There is no public deployment URL, no actual permit-approved hub list, no independent collection dataset, no verified process emissions inventory and no issued credit claim.
- `region_feedstock_2025.csv` contains results reconstructed from the uploaded notebook's regional summary, adjusted to sum to NEA's 232,000 t national headline. `p05_t` and `p95_t` remain rounded saved weight sensitivity bounds.
