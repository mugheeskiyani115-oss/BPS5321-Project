#!/usr/bin/env python3
"""Add PDF export and a six-sector *synthetic* feedstock scenario to BioTwin FastAPI + JS.

Run FROM YOUR REPOSITORY ROOT:
   py BioTwin_Consulting_Integration\\install_into_repo.py .

Targets the FastAPI/JavaScript version (serve.py, api/server.py, web/js/views/results.js).
Changes are idempotent; one-time backups are written beside edited files.
"""
from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent


def replace_once(s: str, before: str, after: str, label: str) -> str:
    if after in s:
        return s
    matches = s.count(before)
    if matches != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {matches}. Source version may have changed. No files were written.')
    return s.replace(before, after, 1)


def patch_evaluate(s: str) -> str:
    s=replace_once(s, '    region: str = "All"\n    gate_fee_sgd_per_t: float = 0.0',
      '    region: str = "All"\n    feedstock_basis: str = "vegetation_proxy"  # or six_sector_scenario (synthetic)\n    gate_fee_sgd_per_t: float = 0.0', 'evaluate Scenario')
    s=replace_once(s,'    net = nw.build_network(b, a)\n    return nw.evaluate(net, layout, with_flows=with_flows), net',
'''    from .sector_scenario import BASIS_SIX, allocate_to_planning_areas
    allocated_t = allocate_to_planning_areas(b.areas, a.national_t) if sc.feedstock_basis == BASIS_SIX else None
    net = nw.build_network(b, a, allocated_t=allocated_t)
    return nw.evaluate(net, layout, with_flows=with_flows), net''', 'evaluate spatial model')
    return s


def patch_api(s: str) -> str:
    s=replace_once(s,'from fastapi.responses import JSONResponse',
      'from fastapi.responses import JSONResponse, Response', 'report Response import')
    s=replace_once(s,'from biotwin import validation as vd\n',
      'from biotwin import validation as vd\nfrom biotwin import sector_scenario as sector\nfrom biotwin.reporting import make_report\n', 'report imports')
    s=replace_once(s,'    region: str = "All"\n    sites: list[str]',
      '    region: str = "All"\n    feedstock_basis: str = "vegetation_proxy"\n    sites: list[str]', 'API request schema')
    s=replace_once(s,'    if req.region not in ("All", *E.REGIONS):',
      '    if req.feedstock_basis not in sector.BASIS:\n        raise HTTPException(400, "Unknown feedstock basis")\n    if req.region not in ("All", *E.REGIONS):', 'API request validation')
    s=replace_once(s,'    return E.Scenario(sites=tuple(dict.fromkeys(req.sites)), size_class=req.size, region=req.region,',
      '    return E.Scenario(sites=tuple(dict.fromkeys(req.sites)), size_class=req.size, region=req.region,\n                      feedstock_basis=req.feedstock_basis,', 'API scenario construction')
    s=replace_once(s,'"scenario": {"region": sc.region, "sites": list(sc.sites), "size": sc.size_class,',
      '"scenario": {"region": sc.region, "sites": list(sc.sites), "size": sc.size_class,\n                     "feedstock_basis": sc.feedstock_basis,', 'API response scenario')
    s=replace_once(s,'# ----------------------------------------------------------------------------- evidence & validation',
'''# ----------------------------------------------------------------------------- downloadable consultant-style report
@app.post("/api/report")
def report(req: EvalRequest):
    sc = _scenario(req)
    try:
        result = _run(sc)  # exactly the same model and scenario as /api/evaluate
        pdf = make_report(result, sector_comparison=sector.comparison(bundle().areas))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="BioTwin_Scenario_Assessment.pdf"',
        "Cache-Control": "no-store",
    })

# ----------------------------------------------------------------------------- evidence & validation''', 'API PDF route')
    s=replace_once(s,'"areas": pd.DataFrame({"planning_area": b.areas.planning_area, "region": b.areas.region,',
      '"areas_six": pd.DataFrame({"planning_area": b.areas.planning_area, "region": b.areas.region,\n'
      '                                "woody_available_t": sector.allocate_to_planning_areas(b.areas, a.national_t) * a.woody_share * a.collectable_share}),\n'
      '        "areas": pd.DataFrame({"planning_area": b.areas.planning_area, "region": b.areas.region,',
      'Six-sector map metadata')
    s=replace_once(s,'"units": vd.UNITS,\n',
      '"units": vd.UNITS,\n        "pwc_scenario": {"status": "synthetic_unvalidated", "year": 2025,\n                         "national_observed_t": 232000, "rows": sector.comparison(b.areas)},\n', 'API six sector evidence')
    return s


def patch_store(s: str) -> str:
    s=replace_once(s,'inputs: { region: "All", mode: "auto",',
      'inputs: { region: "All", feedstock_basis: "vegetation_proxy", mode: "auto",', 'store defaults')
    s=replace_once(s,'    region: inputs.region,\n    sites:',
      '    region: inputs.region,\n    feedstock_basis: inputs.feedstock_basis || "vegetation_proxy",\n    sites:', 'store request')
    return s


def patch_api_js(s: str) -> str:
    s=replace_once(s, '  validate: (unit, file) => {',
'''  report: async (inputs) => {
    const res = await fetch("api/report", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(inputs),
    });
    if (!res.ok) {
      const details = await res.json().catch(() => ({}));
      throw new Error(typeof details.detail === "string" ? details.detail : `PDF report failed (HTTP ${res.status})`);
    }
    return res.blob();
  },
  validate: (unit, file) => {''', 'JS API report')
    return s


def patch_evaluate_js(s: str) -> str:
    s=replace_once(s,'          <div class="step-h"><span class="n done">3</span><h3>Business inputs</h3></div>',
'''          <div class="step-h"><span class="n done">3</span><h3>Business inputs</h3></div>
          <div class="field" style="margin:.6rem 0 1.1rem">
            <label for="feedstockBasis">Spatial feedstock allocation</label>
            <select id="feedstockBasis" class="btn" style="width:100%;text-align:left;padding:0 .8rem;margin-top:.4rem">
              <option value="vegetation_proxy">55 planning areas: vegetation-based estimates</option>
              <option value="six_sector_scenario">6 PWC sectors: synthetic Word-document scenario</option>
            </select>
            <p class="muted" style="font-size:.77rem;margin-top:.4rem">Both use the measured national total. Six-sector shares are assumptions, not collector records. This choice changes the model's waste allocation.</p>
          </div>''', 'Evaluate feedstock select')
    s=replace_once(s,'  const gate = $("gate");',
'''  const basisChoice = $("feedstockBasis");
  basisChoice.value = inp().feedstock_basis || "vegetation_proxy";
  basisChoice.addEventListener("change", () => {
    store.setInputs({ feedstock_basis: basisChoice.value });
    map.setSupply(basisChoice.value === "six_sector_scenario" ? meta.areas_six : meta.areas);
    refresh();
  });
  map.setSupply(inp().feedstock_basis === "six_sector_scenario" ? meta.areas_six : meta.areas);
  const gate = $("gate");''', 'Evaluate feedstock JS handler')
    s=replace_once(s, '    const areas = meta.areas.filter((a) => r === "All" || a.region === r);',
      '    const dataAreas = inp().feedstock_basis === "six_sector_scenario" ? meta.areas_six : meta.areas;\n    const areas = dataAreas.filter((a) => r === "All" || a.region === r);',
      'Evaluate scenario statistics')
    return s


def patch_map_js(s: str) -> str:
    s=replace_once(s, '    this.vmax = Math.max(...Object.values(this.supply));',
      '    this.vmax = Math.max(...Object.values(this.supply));\n    this.supplyVersion = 0;', 'Map update version')
    s=replace_once(s, '  setRegion(region, animate = true) {',
'''  setSupply(areas) {
    if (!Array.isArray(areas)) return;
    this.supply = Object.fromEntries(areas.map((a) => [a.planning_area, a.woody_available_t]));
    this.vmax = Math.max(1, ...Object.values(this.supply));
    this.supplyVersion += 1;
    this.render();
  }
  setRegion(region, animate = true) {''', 'Map setSupply method')
    s=replace_once(s, '    const key = `${region}|${r ? r.metrics.processed_t + r.layout.map((l) => l.site_id).join() : ""}`;',
      '    const key = `${region}|${this.supplyVersion}|${r ? r.metrics.processed_t + r.layout.map((l) => l.site_id).join() : ""}`;',
      'Map supply update trigger')
    return s


def patch_results_js(s: str) -> str:
    s=replace_once(s, 'import * as charts from "../charts.js";',
      'import * as charts from "../charts.js";\nimport { api } from "../api.js";', 'Results API import')
    s=replace_once(s,'    ...(Object.keys(sc.advanced || {}).length ?',
'''    sc.feedstock_basis === "six_sector_scenario" ? "Six-sector synthetic scenario" : "55-area vegetation proxy",
    ...(Object.keys(sc.advanced || {}).length ?''', 'Results scenario metadata')
    s=replace_once(s,'        <button class="btn primary" id="dl">Download</button>',
'''        <button class="btn" id="dl">Download CSV</button>
        <button class="btn primary" id="pdf">Export PDF report</button>''', 'Results PDF button')
    s=replace_once(s, '  $("dl").addEventListener("click", () => download("biotwin_evaluation.csv", toCsv(r, plants, where)));',
'''  $("dl").addEventListener("click", () => download("biotwin_evaluation.csv", toCsv(r, plants, where)));
  $("pdf").addEventListener("click", async () => {
    const button = $("pdf"); const oldLabel = button.textContent;
    button.disabled = true; button.textContent = "Preparing report...";
    try {
      const pdf = await api.report(sc);
      const url = URL.createObjectURL(pdf);
      const a = document.createElement("a");
      a.href = url; a.download = "BioTwin_Scenario_Assessment.pdf";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      toast("Consulting-style PDF report prepared");
    } catch (error) { toast(error.message, "err"); }
    finally { button.disabled = false; button.textContent = oldLabel; }
  });''', 'Results PDF download handler')
    return s


def patch_evidence_js(s: str) -> str:
    s=replace_once(s,'{ waste: waste, sources: sources, validation: validation }[v](data)',
      '{ waste: waste, sectors: sectors, sources: sources, validation: validation }[v](data)', 'Evidence tab mapping')
    s=replace_once(s, '[{ value: "waste", label: "Waste data" }, { value: "sources", label: "Sources" },',
      '[{ value: "waste", label: "Waste data" }, { value: "sectors", label: "Six-sector scenario" }, { value: "sources", label: "Sources" },', 'Evidence tab navigation')
    s=replace_once(s,'function sources(d) {',
'''function sectors(d) {
  const rows = d.pwc_scenario?.rows || [];
  const largest = Math.max(1, ...rows.map((r) => r.synthetic_t));
  return `<div class="reveal"><h2 class="title-m">Six Public Waste Collection sectors</h2>
    <p style="max-width:830px;margin:.7rem 0 1.1rem">The 2025 national total (232,000 tonnes) is an observed NEA statistic. The six sector weights below are <b>synthetic estimates from the group's Word document</b>, not actual operator collection records. Their national reconciliation proves only mass balance, not spatial accuracy. Use Evaluate to switch between the vegetation-proxy and synthetic sector allocation scenarios.</p>
    <div class="grid g2" style="margin-bottom:1rem">
      <div class="tile"><div class="k">Observed national waste</div><div class="v">232,000 t</div><div class="n">NEA 2025</div></div>
      <div class="tile"><div class="k">Sector measurement status</div><div class="v">Not validated</div><div class="n">No independent operator tonnage records supplied</div></div>
    </div>
    <div class="card" style="padding:1.3rem 1.4rem;margin-bottom:1.2rem">
      ${rows.map((r) => `<div style="display:grid;grid-template-columns:minmax(160px,1.5fr) 2fr 100px;gap:12px;align-items:center;margin:.7rem 0">
        <b>${esc(r.pwc_sector)}</b><div style="background:#27323b;height:12px;border-radius:8px"><div style="background:#16afa3;width:${(100*r.synthetic_t/largest).toFixed(1)}%;height:100%;border-radius:8px"></div></div>
        <span style="text-align:right">${fmt.int(r.synthetic_t)} t</span></div>`).join("")}
    </div>
    ${table(rows, [["pwc_sector", "PWC sector"], ["word_share_pct", "Assumed share", (v) => `${fmt.dec(v,1)}%`],
      ["synthetic_t", "Word proxy t", fmt.int], ["original_proxy_t", "Vegetation proxy t", fmt.int],
      ["difference_t", "Difference t", (v) => fmt.signed(v)]])}
    <p class="muted" style="margin-top:1rem">The document also assumes a 75% woody / 25% leafy split on a dry-mass basis. BioTwin's original woody-share input is not silently changed because the mass bases are unverified.</p></div>`;
}

function sources(d) {''', 'Evidence six-sector screen')
    return s


def install(root: Path) -> None:
    if not (root / 'serve.py').exists() or not (root / 'api/server.py').exists():
        raise RuntimeError('This is not the newer FastAPI BioTwin repository. Use the version containing serve.py, api/server.py and web/.')
    actions = {
        'biotwin/evaluate.py': patch_evaluate,
        'api/server.py': patch_api,
        'web/js/store.js': patch_store,
        'web/js/api.js': patch_api_js,
        'web/js/views/evaluate.js': patch_evaluate_js,
        'web/js/map.js': patch_map_js,
        'web/js/views/results.js': patch_results_js,
        'web/js/views/evidence.js': patch_evidence_js,
    }
    # Compute and syntax-check all modifications before writing any files.
    planned = {}
    for relative, func in actions.items():
        f = root / relative
        if not f.is_file():
            raise RuntimeError(f'Missing required project file {relative}')
        original = f.read_text(encoding='utf-8')
        updated = func(original)
        if relative.endswith('.py'):
            ast.parse(updated, filename=relative)
        planned[f] = (original, updated)
    req = root / 'requirements.txt'
    orig = req.read_text(encoding='utf-8')
    requirement = 'reportlab>=4.0,<5'
    planned[req] = (orig, orig if requirement in orig else orig.rstrip()+ '\n'+requirement+'\n')
    for path, (old, new) in planned.items():
        if old == new:
            continue
        backup = path.with_suffix(path.suffix + '.before-consulting-upgrade.bak')
        if not backup.exists():
            backup.write_text(old, encoding='utf-8')
        path.write_text(new, encoding='utf-8')
        print('UPDATED', path.relative_to(root))
    for relative in ('biotwin/reporting.py', 'biotwin/sector_scenario.py', 'data/pwc_scenario_2025.csv'):
        dest = root / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PACKAGE / relative, dest)
        print('INSTALLED', relative)
    ignore = root / '.gitignore'
    if ignore.is_file():
        current = ignore.read_text(encoding='utf-8')
        rule = '*.before-consulting-upgrade.bak'
        if rule not in current:
            ignore.write_text(current.rstrip() + '\n\n# BioTwin upgrade installer backups\n' + rule + '\n', encoding='utf-8')
    # Intentionally do NOT copy tests into the existing tests folder to avoid collisions.
    print('\nUpgrade ready. Install requirements and run:')
    print('   py -m pip install -r requirements.txt')
    print('   py serve.py')
    print('Open http://localhost:8000 > Evaluate > Get results > Export PDF report')


if __name__ == '__main__':
    try:
        install(Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve())
    except Exception as exc:
        print('INSTALLATION STOPPED:', exc, file=sys.stderr)
        sys.exit(1)
