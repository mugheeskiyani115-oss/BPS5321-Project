# BioTwin Singapore | Commercial finance scenarios, November 2026

**This update is for the existing FastAPI/JavaScript `BPS5321-Project-ui-changes` website**, not for the older Streamlit `app.py` application. It does not clone or modify GitHub.

## Windows: install and open

1. Stop BioTwin in its terminal (`Ctrl+C`). Make a copy of your existing project folder first.
2. Extract this ZIP **directly inside the folder containing `serve.py`**, selecting merge (not creating a second nested project folder). It adds `UPDATE_COMMERCIAL_AND_RUN.bat`, `COMMERCIAL_UPGRADE_README.md`, and `_commercial_patch/`.
3. Double click `UPDATE_COMMERCIAL_AND_RUN.bat`.
4. Open `http://localhost:8000`, then go to **Evaluate > Business inputs > Commercial sensitivity**. Choose a scenario, optionally change staffing, grant or taxes, then **Get results**.
5. To relaunch later, use the original `serve.py` command or `py serve.py`. Installer only needs to be run once.

Manual command, if Windows blocks `.bat`:

```cmd
py _commercial_patch\install_into_existing_project.py .
py -m pip install -r requirements.txt
py -m pytest -q tests\test_commercial_finance_upgrade.py
py serve.py
```

### What was changed

- `biotwin/pathway.py`: *optional* staffing override, grant share and simple tax sensitivity, all defaulting to the original values (0 scenario modifications).
- `biotwin/evaluate.py`: editable commercial assumptions and wrapper around the existing `pro_forma`. **Biochar, gate fee and carbon credits already existed and are not added twice.**
- `biotwin/commercial_finance.py`: grants are year-zero inflows; simplified cash taxes depend on positive operating profit after assumed straight-line depreciation. Depreciation is NOT a second cash cost and CAPEX is NOT amortized away in NPV.
- `biotwin/finance_audit.py`: rejects incoherent cash flow, NPV, cumulative cash flow or gross levelised cost. Also accepts a hypothetical grant and cash tax in their correct years.
- `api/server.py`: publishes audited financial summaries and source status for grant/tax/crew assumptions.
- `web/js/views/evaluate.js`: commercial presets (existing research baseline, construction product S$300/t with potential credits S$230/tCO2e, speculative premium S$1,000/t), staffing options, grant fraction and simple tax sensitivity.
- `web/js/views/results.js`: visible product, credit and gate-fee revenues; gross investment, hypothetical grant, cash taxes and noncash depreciation, NPV.
- Existing `biotwin/reporting.py` **if present**: finance table explicitly shows other net cash movements and refuses mathematically contradictory PDF reports. Existing 3D map capture and six-sector functionality are preserved.

## What it deliberately does NOT do

- It does **not** assume the quoted S$300/t construction biochar price has an offtake contract, or that S$1,000/t premium material will sell at industrial scale.
- It does **not** assume the plant qualifies for carbon credits, or replace the audited registry credit quantity with a blanket 2.9 tCO2e/t-biochar factor. Puro credits concern independently verified **net removals**; avoidance and gross storage are separate.
- It does **not** multiply the existing 0.165 t biochar / wet tonne figure by a separate dry-mass factor. That figure is **already expressed on a wet feedstock basis**; adding dry-mass conversion again would change the model basis.
- It does **not** treat NEA or EnterpriseSG grants as guaranteed. No grant is included unless the user explicitly selects a hypothetical percentage. Suitability and grant accounting require independent checks.
- It does **not** turn accounting depreciation into a reduction in the actual capital outlay. The 17% tax mode is a simplified instructional scenario (no losses carried forward and straight-line assumed depreciation), **not** a claim about Singapore tax capital allowances, deductibility or grant tax treatment.
- It does **not** automatically adjust plant output to unverified monthly woody/leafy changes. If the separate seasonal visual upgrade is installed, its assumption-only output remains separate.
- It does **not** retune NSGA-II objective weights to maximize NPV. Facility auto-selection and any existing NSGA-II search continue using the project's original cost/carbon/haul objectives; the new financing assumptions affect the subsequent project finance evaluation.
- It does **not** guarantee positive NPV. An uneconomic configuration must remain negative under its chosen assumptions.

## Official references for due diligence

- NEA 3R Fund: https://www.nea.gov.sg/programmes-grants/grants-and-awards/3r-fund
- EnterpriseSG Enterprise Development Grant: https://www.enterprisesg.gov.sg/financial-support/enterprise-development-grant/
- Puro.earth certification: https://puro.earth/cdr-infrastructure/carbon-credit-certification/
- Puro.earth methodology: https://puro.earth/methodologies/biochar/

All prices in the illustrative interface are SG dollars unless marked otherwise. Existing model foreign exchange inputs convert revenue presets into the current internal USD/EUR price fields. The preset S$230 per verified credit is a **price assumption**, not an issuance assurance or a current live market quote.

## Backups / troubleshooting

On successful install, previous versions of changed files are copied into `.biotwin_backups/YYYYMMDD_HHMMSS/`. That folder is ignored by Git. The installer checks anchors and Python syntax before writing changes. If it refuses an unexpected local code version, your files remain unchanged; share the exact error message.

The PDF export is retained **if it was already present in the existing project**. This commercial package does not install a missing PDF integration from scratch.
