# BioTwin Quest — Singapore horticultural waste → biochar

**Research question:** where, and at what scale, should Singapore process woody horticultural waste into biochar,
and what are the cost, transport and net-carbon trade-offs?

BioTwin Quest is a game-style decision-support app built on a tested planning model. Players choose sites and plant
sizes on a 3D OpenStreetMap of Singapore and are scored against an NSGA-II optimiser. Every number they are scored on
comes from the model; budgets and star thresholds are the only game rules.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH= streamlit run app.py                                            # http://localhost:8501
PYTHONPATH= PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests      # 38 tests incl. headless app runs
```

(`PYTHONPATH=` clears a ROS path that some machines load and that breaks Python packages.)

Rebuild data (needs internet): `pip install -r requirements-pipeline.txt`, then
`python -I pipeline/build_data.py all` and `python -I pipeline/build_game_refs.py`.

## Pages

| Page | What it does |
|---|---|
| 🏠 Mission hub | Level and XP, five missions (unlock in order), badges |
| 🎮 Play | 3D map: click an empty industrial plot, build one of six plant sizes, watch cost / credits / haul update, submit for stars. The Decade mission simulates 2026–2035 |
| 🏆 Trophies | Mission records, badge cabinet, submission history (CSV) |
| 🔬 Lab | The analysis without game rules: feedstock map, supply forecast + 10-year credit outlook, itemised plant economics, free NSGA-II run, validation upload |
| 📚 Sources | Every parameter with its tag and link; JTC rent per site; research-PDF claim checks; datasets |

Missions: 🌱 First Spark (2,000 t/yr, lowest cost) → 🏙️ City Loop (9,000 t/yr, lowest cost) → 🌍 Carbon Captain
(most credits) → 🤖 Beat the AI (not dominated on cost, carbon and haul) → 📅 Decade Run (ten stochastic years).

## Model (one basis, no toggles)

- **Carbon — Notebook 2:** 0.165 t biochar, 0.372 tCO2e stored, 0.234 registry credit, −0.009 net vs current use per
  wet tonne; small kilns ≈ 0.12.
- **Plant cost — itemised Singapore:** vendor turnkey capex (pyrolysisplant.com) + crews to cover operating hours at MOM
  2025 median wages + 17% CPF (Employment Act 44-h week) + SP Group electricity (US DOE grinding energy) + maintenance
  8% of capex/yr (Trollip et al. 2025) + JTC posted land rent at each site. Chosen because generic vendor opex
  (US$30–90/t) leaves out Singapore wages and land, and the research PDF's Singapore range has no source; the itemised
  model lands inside that range for continuous plants (US$179/t at 20 t/day).
- **Haulage:** truck-day costing (S$800/day tipper with operator; EPA bulk density for branches) on OSRM road times →
  median S$22/t, in line with the handoff's ~S$20/t. Emissions: DESNZ 2025 rigid HGV factor.
- **Credits:** Senken CORC index (€120.67, June 2026) and price paths; Puro.earth fees per credit + annual verification.
- **Gate-fee benchmark:** NEA incineration fee S$89.60/t incl. GST (S$82.20 excl.).
- **Supply:** NEA national series; projection method chosen by backtest; 55 planning areas by proxy allocation.

Parameter tags (`data/params/parameters.csv`): 20 web, 4 Notebook 2, 4 derived, 13 assumptions, 1 research-PDF
fallback (seasonal woody swing, no web source found).

## Code

| Path | Role |
|---|---|
| `biotwin/` | Model: `data`, `pathway` (carbon + itemised costs), `network` (roads, LP, layout evaluation), `optimise` (NSGA-II), `forecast`, `outlook` (10-year credits), `validation`, `game` (missions, scoring, badges, decade simulation) |
| `ui/`, `ui_pages/`, `app.py` | Streamlit UI (dark theme, pydeck 3D maps on OpenFreeMap) |
| `pipeline/` | `build_data.py` (open data), `build_game_refs.py` (optimiser references, fingerprinted) |
| `data/` | Inputs and parameters with provenance |
| `biotwin_core.py`, `tests/test_core.py` | Interim-case model kept for its original tests |

## Key findings

- Labour dominates Singapore running costs, so a single 50 t/day plant is cheapest for 9,000 t/yr (≈S$354/t net cost);
  small batch kilns cost S$790–860/t at resident wages.
- Biochar roughly ties with today's biomass-power fate on carbon (Notebook 2: −0.009 tCO2e/t).
- Credits help but do not close the gap: break-even credit price ≈ €1,070/tCO2e for the cheapest layout vs a 2040
  high path of €215 (10-year PV −S$21.4M without credits, −S$18.8M with them).
- Real road distances are 1.38× straight-line; the trend in national supply is weak and not robust.

## Still needed

Independent tonnage records (NEA WRMS / NParks / town councils / collectors), a Singapore operating-cost or plant
quote, a biochar buyer quote, the Notebook 2 country profile (to replace derived values), and NEA's position on
small-kiln emissions.
