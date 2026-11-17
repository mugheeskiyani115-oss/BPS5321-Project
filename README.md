# BioTwin Singapore — planning tool for horticultural waste → biochar

**Research question:** where, and at what scale, should Singapore process woody horticultural waste into biochar,
and what are the cost, transport and net-carbon trade-offs?

A REopt-style evaluation tool on a tested planning model. You choose a region and plot(s), choose a plant and set
business inputs. You then get the expected output, a 15-year pro forma (capital cost, year-by-year cash flow, NPV,
payback, IRR and break-even gate fee), business as usual vs your plant, numbered findings, and how every other plot
and plant size compares.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH= python serve.py                                                  # http://localhost:8000
PYTHONPATH= PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests       # 46 tests (model + API)
```

Use `python serve.py --port 9000` to run on another port. `PYTHONPATH=` clears a ROS path that some machines load and
that breaks Python packages. The front end is plain JavaScript modules with vendored libraries, so there is no
Node or build step and no internet is needed at run time except for basemap tiles.

To rebuild the data (needs internet), run `pip install -r requirements-pipeline.txt`, then
`python -I pipeline/build_data.py all` and `python -I pipeline/build_recommendations.py`. Run the second command
again after any change to `data/params/parameters.csv`.

## Pages

| Page | What it does |
|---|---|
| Home | What the tool does and how an evaluation works, with headline national numbers |
| Evaluate | **1 Location:** pick a region (the map flies there). Let the tool pick the cheapest plot, or click plots on the map or in the list; several plots make a decentralised network. **2 Plant:** pick a size, or let the tool size it. **3 Business inputs:** gate fee slider marked at the incineration fee, sell credits, and advanced inputs with defaults and a reset. Then **Get results**. |
| Results | Map with trucks driving real road routes to the plant, key metrics, process flow, business as usual vs your plant, findings, year-by-year cash flow (each year or cumulative, plus a table), comparisons (cost per tonne, other plots, plant sizes), assumptions, and Save / Download CSV / Edit inputs |
| Saved | Saved evaluations side by side, with charts and CSV export (stored in the browser) |
| Evidence | Waste-data check, every parameter with its tag and source link, validation upload, research-PDF checks |

### Animations

- **Page changes:** cross-fades using the View Transitions API.
- **Scrolling:** sections fade in as they come into view.
- **Numbers:** count up to their values.
- **Controls:** the segmented controls and tabs slide, the switch springs, and the slider fill follows the thumb.
- **Map:** flies to each region; plot columns rise and change colour; selected plots pulse; after a run, trucks drive
  the cached OSRM road routes to the plant.
- **Charts:** bars appear in sequence and lines draw in.
- **Process flow:** an animated SVG.

Everything respects the operating system's reduced-motion setting. If WebGL is not available, the map shows a
fallback message instead.

## Architecture

| Path | Role |
|---|---|
| `biotwin/` | Model: `data` (loads and fingerprints inputs), `pathway` (carbon and itemised costs), `network` (road matrix, LP allocation, layout evaluation), `evaluate` (scenario → layout, pro forma, business as usual, findings, comparisons), `optimise` (NSGA-II), `recommend`, `forecast`, `outlook` (10-year credits), `validation` |
| `api/server.py`, `serve.py` | FastAPI: `GET /api/meta`, `/api/geo`, `/api/evidence`, `/api/health`; `POST /api/evaluate`, `/api/validate`; serves `web/` |
| `web/` | Front end: `js/app.js` (router), `js/views/*` (pages), `js/map.js` (MapLibre + deck.gl on a CARTO dark OSM basemap), `js/charts.js` (ECharts), `js/ui.js`, `js/store.js`, `css/app.css`; `vendor/` holds MapLibre 4.7.1, deck.gl 9.0.38 and ECharts 5.5.1 |
| `pipeline/` | `build_data.py` (steps: geo, trees, landcover, allocate, sites, facilities, roads, fx, routes) and `build_recommendations.py` |
| `data/` | Inputs, `params/parameters.csv` (every parameter with a tag and source), `routes.json` (road geometry for truck animation) |
| `biotwin_core.py`, `tests/test_core.py` | Interim-case model, kept for its original tests |

## Model (one basis, no toggles)

- **Carbon (Notebook 2):** per wet tonne, 0.165 t biochar, 0.372 tCO2e stored, 0.234 registry credit, and −0.009 net
  against current use. Small kilns give about 0.12.
- **Plant cost (itemised Singapore):** the components are
  - vendor turnkey capex;
  - crews to cover operating hours, at MOM 2025 median wages plus 17% CPF, on the Employment Act 44-hour week;
  - SP Group electricity;
  - maintenance at 8% of capex a year;
  - JTC posted land rent at each site.

  This basis was chosen over generic vendor opex (US$30–90/t) because that figure leaves out Singapore wages and land.
- **Haulage:** a truck-day cost (S$800 a day for a tipper with operator) applied to OSRM road times.
- **Credits:** Senken CORC index and price path, minus Puro.earth fees per credit and annual verification.
- **Gate-fee benchmark:** the NEA incineration fee of S$82.20/t excluding GST.

### Why the cash flow changes every year

Notebook 2 held prices, wages, supply and credits flat, so every year after the first was identical. The pro forma
now builds in 2026 and runs from 2027, in nominal dollars:

| Driver | Value | Source |
|---|---|---|
| Year-1 output | 75% of capacity, then 100% | Assumption, informed by commercial plant ramp-ups |
| Staff costs | +3.5% a year | Derived from MOM 2025 nominal wage growth (+4.9%) |
| Other prices (gate fee, biochar, maintenance, land, power, trucking) | +1.75% (2026), +2.0% (2027), +2.0% long run | MAS core inflation forecast; long run is an assumption |
| Carbon credit price | Senken base path, scaled to the price you enter | Web |

The parameter register in `data/params/parameters.csv` has 48 parameters: 22 from published sources, 4 from
Notebook 2, 5 calculated, 16 assumptions and 1 research-PDF fallback.

## Key findings (cheapest plant: 50 t/day at the cheapest plot, about 15,700 t/yr)

| Case | NPV, 15 years | Payback |
|---|---|---|
| No gate fee, no credits | −S$33.0M | none |
| Gate fee at the incineration rate (S$82.20/t) | −S$20.6M | none |
| Incineration gate fee plus credits | −S$14.3M | none |
| S$200/t gate fee plus credits | +S$3.3M | year 7 |

- The plant costs S$8.5M to build and about S$276 per tonne over its life.
- It breaks even at a gate fee of S$220/t, or S$178/t if credits are sold.
- Labour dominates Singapore running costs, so one larger plant beats several small kilns.
- On carbon, biochar roughly ties with today's biomass-power fate (Notebook 2: −0.009 tCO2e/t).
- The gap widens over time because staff costs rise faster than prices.
- Real road distances are 1.38× straight-line.

## Waste data (checked 17 Nov 2026)

No public dataset breaks horticultural waste down below the national total. Sources checked: data.gov.sg, NEA, NParks,
town-council tenders and research (see `data/params/waste_data_check.csv`). NParks tracks volumes from its landscape
contractors and NEA holds collector returns in WRMS; both need a formal data request.

## Still needed

- Independent tonnage records (NParks contractor reports, NEA WRMS, town councils or collectors).
- A Singapore operating-cost or plant quote.
- A biochar buyer quote.
- The Notebook 2 country profile, to replace derived values.
- NEA's position on small-kiln emissions.
