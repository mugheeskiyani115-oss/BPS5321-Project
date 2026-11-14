# BioTwin Singapore — interactive research prototype

**What it is:** a working Streamlit web app that explores Singapore's horticultural waste proxy allocation and **illustrative** pyrolysis/biochar siting, carbon, transport and economic scenarios.

**What it is not:** a verified digital twin, a production grade forecasting model, real road routing, a certified carbon accounting ledger, or a built NSGA-II engine. These were overclaimed in the interim presentation; the final deck and report now distinguish them.

## Quick start

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Your browser should open the app at `http://localhost:8501`. To share an actual URL, deploy the folder on **Streamlit Community Cloud** (or another Python web host); no hosted link has been created with this submission.

## Features that actually run

1. 2025 regional waste proxy map using 5 regions from the submitted notebook; the five displayed shares sum to 100% and regional allocations are normalized to NEA's reported 232,000 t national total.
2. Sensitivity bands (from 2,000 proxy weight draws) are labelled **weight sensitivity only**, not prediction accuracy.
3. Select one or more illustrative hub anchors directly on the interactive map (point, box or lasso selection), with an accessible region selector as fallback.
4. Linear programming allocates the same annual throughput to the selected hub capacities under assumed available feedstock, with approximate great-circle plus local routing distance.
5. Compare a one-hub scenario to a multi-hub scenario, including annual cost, haul burden, greenhouse gases and gate fee breakeven.
6. Exact enumeration of all 31 nonempty combinations of 5 candidate anchor regions; plot small-set Pareto efficient configurations. **No claim of NSGA-II**.
7. Separate gross carbon storage, illustrative net climate benefit and **assumed** issued credits (default zero).
8. Optional upload of genuinely independent 2025 regional operator data to compute WAPE and measured vs estimated ranking; without records, the app explicitly reports *not validated*.

## Data and key caveats

- `data/region_feedstock_2025.csv` uses *rounded shares and ranges* printed by the original notebook; its 55-area CSV and GIS layers were **not uploaded**. The regional headline is not independent validation.
- The map anchors are **illustrative representative positions**, not parcel coordinates or actual candidate sites. Existing locations, roads, permitted land, depot locations and land-use permissions are not checked.
- Plant capacity is split equally between selected anchors. Total throughput is held constant when comparing central and distributed options. Spatial availability is an assumed percentage of each proxy estimate.
- S$92/t and S$310/t are **reported worked-case assumptions** from the original submission, not vendor quotations. Additional annual overhead and route costs are scenario inputs.
- Gross storage = 0.372 tCO2/wet t, net before new transport = 0.095 tCO2e/wet t from the interim case. The app *illustratively decomposes* the difference into process 0.100 and foregone energy benefit 0.177; these numbers must be replaced with a complete process inventory.
- The 2026 Singapore carbon tax (S$45/tCO2e) is **not** a tradable carbon credit price. Carbon credit eligibility is not established; default revenue is zero.
- The Random Forest's R² = 0.364 is for **log managed-tree biomass proxy per grid cell**, not for monthly waste forecasting or evidence of international transfer.
- The original EDA notebook uses a Colab/Google Drive workflow and downloads external data. It has saved outputs, but the detailed raw files and second notebook mentioned in its introduction were not supplied. Therefore, rebuilding the full 55-area dataset from scratch cannot be verified with the uploads alone.

## Regenerate 55 planning area inputs

The revised EDA notebook contains an end cell to export an optional `planning_area_estimates.csv` (true coordinates from original URA geometries). Rerun it in a network-enabled environment with access to its input datasets, then copy the output into this folder's `data/`. The app uses those 55 supply origins automatically while retaining just five illustrative hub anchors.

## Independent data validation

Download `data/operator_validation_TEMPLATE.csv`. Fill `observed_t` with *actual* regional 2025 collection or operator records, including publisher. Upload the completed CSV in the app's Validation tab. Do not copy model values into this template; that would create circular validation.

## Reproducibility and tests

```bash
python -m pytest -q tests
```

Outputs can be exported as CSV from the app. Every calculation is deterministic for a chosen scenario. `biotwin_core.py` is separated from UI logic to permit independent tests and later substitution of verified road, waste and vendor datasets.

## Sources

- NEA Waste Statistics and Overall Recycling: https://www.nea.gov.sg/our-services/waste-management/waste-statistics-and-overall-recycling
- NCCS Carbon Tax: https://www.nccs.gov.sg/singapores-climate-action/mitigation-efforts/carbontax/
- EMA: https://www.ema.gov.sg/resources/singapore-energy-statistics/chapter2
- Puro.earth Biochar methodology: https://puro.earth/methodologies/biochar/
- REopt Web Tool (interface inspiration only): https://reopt.nlr.gov/tool/

Prepared for NUS BPS5231, 12 November 2026.
