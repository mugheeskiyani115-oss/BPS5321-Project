# BioTwin Singapore: sustainability report visual style

This package updates **only** `biotwin/reporting.py` in the existing FastAPI + JavaScript BioTwin project. It does **not** replace the app or modify engineering, carbon, feedstock, financial or optimization formulas.

## What changes

- Keeps the nine-page report structure used in the current BioTwin export.
- Uses an original sustainability/advisory design informed by the supplied *Temasek Sustainability Report 2025*: purple headings, clean spacing, subtle section rails, multi-colour KPI accents and charts.
- Uses Times New Roman when that font is available on Windows. A compatible serif fallback is used where it is unavailable. No font files are included.
- Preserves the **actual 3D map screenshot in full colour**; exports still require a real map capture from BioTwin Results (no substitute drawing in production).
- Colours levelised cost bars, the cumulative cash-flow curve, the carbon ledger and the six-sector allocation chart.
- Keeps financial integrity: the cash-flow table includes revenue, operating expenses and other net cash movements for the initial CAPEX, hypothetical grants and taxes. If the optional `finance_audit.py` is installed, the report validates the actual financial schedule before export.
- The source status of the six-sector figures stays explicit: synthetic sector share estimates, not independently measured operator waste quantities.

## Install on Windows

1. Open the existing **BPS5321-Project-ui-changes** folder. It must contain `serve.py`, `api`, `biotwin`, `web` and `data`.
2. Extract the ZIP. Move the extracted `BioTwin_Temasek_Report_Style` **folder** inside the project folder, next to `serve.py`.
3. Open `BioTwin_Temasek_Report_Style` and double-click `APPLY_STYLE.bat`.
4. The script backs up `biotwin/reporting.py` and replaces **only that file**. No fragile search-and-replace code patching.
5. Restart the website by using your normal `RUN_BIOTWIN.bat` or `py serve.py` command.
6. Run a real evaluation, adjust the 3D map perspective, then choose **Export PDF report**.

The sample PDF is a **design fixture using illustrative data**. Its map is an intentionally labelled demonstration graphic. Actual PDF exports embed the current browser map image and actual evaluated values.

## Manual installation alternative

Copy `BioTwin_Temasek_Report_Style/reporting.py` into the project's existing `biotwin` folder and replace `reporting.py`. Restart BioTwin.

## Compatibility / safeguards

- This is for the **FastAPI/JavaScript** project launched with `serve.py`, not the old Streamlit project launched with `app.py`.
- Existing screenshot capture remains in the website and must already be working. This update changes **rendering style only**.
- The PDF output is a static document; the website remains the interactive 3D map.
- Two site profiles are displayed on the site geography page when a scenario contains many locations; the full site list remains on the configuration page to preserve nine pages.
- Keep the earlier project code and all data files unchanged. Changes can be pushed to GitHub manually after review.
