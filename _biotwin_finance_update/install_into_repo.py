#!/usr/bin/env python3
"""Apply the BioTwin commercial sensitivity and finance integrity patch.

Works with the selected FastAPI/JavaScript 'ui-changes' website, including
existing consultancy PDF and six-sector upgrades. Run at the repo root:

    py BioTwin_Finance_Model_Upgrade\\install_into_repo.py .

Preflight plans ALL updates before writing them. Makes backups. Repeat-safe.
"""
from __future__ import annotations
import ast
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent


def edit(s: str, before: str, after: str, name: str) -> str:
    if after in s:
        return s
    n = s.count(before)
    if n != 1:
        raise RuntimeError(f"{name}: expected exactly one source anchor; found {n}. No changes written.")
    return s.replace(before, after, 1)


def patch_pathway(s: str) -> str:
    s = edit(s, '    labour_exponent: float = 0.25\n',
             '    labour_exponent: float = 0.25\n'
             '    continuous_crew_per_shift: float = 0.0  # 0 uses existing size-scaled model; >0 is scenario assumption\n'
             '    seasonal_woody_amplitude: float = 0.0  # sensitivity only, not measured monthly tonnes\n    woody_share_uncertainty_sd: float = 0.05  # hypothetical standard deviation of composition draws\n',
             'model assumption fields')
    s = edit(s, '            "gate_fee": self.gate_fee_sgd_per_t >= 0, "truck": self.truck_hours > self.handling_h > 0,',
             '            "gate_fee": self.gate_fee_sgd_per_t >= 0, "truck": self.truck_hours > self.handling_h > 0,\n'
             '            "continuous_crew_per_shift": 0 <= self.continuous_crew_per_shift <= 12,\n'
             '            "seasonal_woody_amplitude": 0 <= self.seasonal_woody_amplitude <= 0.2,\n'
             '            "woody_share_uncertainty_sd": 0 <= self.woody_share_uncertainty_sd <= 0.15,',
             'model assumption ranges')
    s = edit(s, 'def workers_per_shift(plant: pd.Series, a: Assumptions) -> float:\n    w = float(plant["workers_per_shift"])',
             '''def workers_per_shift(plant: pd.Series, a: Assumptions) -> float:
    # Technology-specific assumption, not a validated supplier crew roster.
    technology = str(plant.get("technology", "")).lower()
    if a.continuous_crew_per_shift > 0 and "continuous" in technology:
        return a.continuous_crew_per_shift
    w = float(plant["workers_per_shift"])''', 'continuous staffing override')
    return s


def patch_evaluate(s: str) -> str:
    s = edit(s, '    "biochar_price_usd": ("Biochar sale price", "US$/t biochar", 0.0, 1500.0, 10.0),',
             '''    "biochar_price_usd": ("Biochar sale price", "US$/t biochar", 0.0, 1500.0, 10.0),
    "continuous_crew_per_shift": ("Continuous plant crew per shift (0 = baseline model)", "people/shift", 0.0, 12.0, 0.5),
    "seasonal_woody_amplitude": ("Seasonal woody-fraction decrease during monsoon", "fraction; sensitivity only", 0.0, 0.20, 0.0125),
    "woody_share_uncertainty_sd": ("Hypothetical woody-fraction standard deviation (Monte Carlo)", "fraction; not observed", 0.0, 0.15, 0.01),''',
             'commercial / seasonality advanced fields')
    return s


def patch_api(s: str) -> str:
    s = edit(s, 'from biotwin import validation as vd\n',
             'from biotwin import validation as vd\n'
             'from biotwin.finance_audit import audit_financial_result, seasonal_composition\n',
             'auditing imports')
    s = edit(s, '    ev, pf, bau = res["eval"], res["pro_forma"], res["bau"]',
             '''    ev, pf, bau = res["eval"], res["pro_forma"], res["bau"]
    actual_a = res["assumptions"]
    finance_audit = audit_financial_result({
        "years": pf["years"].to_dict(orient="records"),
        "metrics": {"discount_rate": pf["discount_rate"], "capex_sgd": pf["capex_sgd"],
                    "npv_sgd": pf["npv_sgd"], "levelised_cost_sgd_per_t": pf["levelised_cost_sgd_per_t"]},
    })
    seasonality = seasonal_composition(
        float(actual_a["woody_share"]), float(actual_a.get("seasonal_woody_amplitude", 0.0)),
        float(actual_a["national_t"]), float(actual_a["collectable_share"]),
        float(actual_a.get("woody_share_uncertainty_sd", 0.05)),
    )''', 'model financial audit')
    s = edit(s, '        "bau": bau, "years": pf["years"], "drivers": pf["drivers"],',
             '        "bau": bau, "years": pf["years"], "drivers": pf["drivers"],\n'
             '        "finance_audit": finance_audit, "seasonality": seasonality,',
             'API audit response')
    s = edit(s, '    return clean({\n        "scenario": {"region": sc.region,',
             '''    used.extend([
        {"input": "continuous_crew_per_shift", "value": actual_a.get("continuous_crew_per_shift", 0.0),
         "default": 0.0, "unit": "people/shift (0 = baseline)",
         "source": "Illustrative automation/crew scenario; supplier quotation needed", "tag": "assumption"},
        {"input": "seasonal_woody_amplitude", "value": actual_a.get("seasonal_woody_amplitude", 0.0),
         "default": 0.0, "unit": "woody share fraction", "source": "Unvalidated seasonal sensitivity, not measured monthly tonnes", "tag": "assumption"},
        {"input": "woody_share_uncertainty_sd", "value": actual_a.get("woody_share_uncertainty_sd", 0.05),
         "default": 0.05, "unit": "woody fraction SD", "source": "Illustrative 500-draw Monte Carlo composition uncertainty, not empirically calibrated", "tag": "assumption"},
    ])
    return clean({
        "scenario": {"region": sc.region,''', 'assumption provenance')
    return s


def patch_evaluate_js(s: str) -> str:
    s = edit(s, '          <details class="accordion" id="adv" style="margin-top:1rem">',
             '''          <div class="field" style="margin:1.15rem 0 .65rem">
            <label for="biocharPreset">Biochar sales scenario</label>
            <select id="biocharPreset" class="btn" style="width:100%;margin-top:.35rem;text-align:left">
              <option value="default">Original model: US$100/t biochar</option>
              <option value="150">Illustrative commodity: S$150/t biochar</option>
              <option value="300">Illustrative bulk: S$300/t biochar</option>
              <option value="1000">Illustrative premium: S$1,000/t biochar</option>
              <option value="custom">Custom price (advanced inputs)</option>
            </select>
            <p class="muted" style="font-size:.76rem;margin-top:.35rem">Prices are scenarios, not confirmed Singapore buyer quotations. The simulator converts S$ to US$ using the model FX rate.</p>
          </div>
          <div class="field" style="margin:.85rem 0">
            <label for="staffPreset">Continuous / semi-continuous crew</label>
            <select id="staffPreset" class="btn" style="width:100%;margin-top:.35rem;text-align:left">
              <option value="0">Original size-scaled staffing model</option>
              <option value="3">Automation sensitivity: 3 people per shift</option>
              <option value="5">Moderate sensitivity: 5 people per shift</option>
              <option value="custom">Custom crew (advanced inputs)</option>
            </select>
            <p class="muted" style="font-size:.76rem;margin-top:.35rem">Assumed staff per shift is multiplied by shift coverage and leave factors. Neither alternative has been verified by a plant vendor.</p>
          </div>
          <div class="field" style="margin:.85rem 0 1.15rem">
            <label for="seasonPreset">Seasonal woody/leafy sensitivity</label>
            <select id="seasonPreset" class="btn" style="width:100%;margin-top:.35rem;text-align:left">
              <option value="0">Off: annual composition only</option>
              <option value="0.1125">Illustrative wet/dry shift around current annual mean</option>
              <option value="word75">Unverified Word example: 75% mean / 63.75%-78.75%</option>
              <option value="custom">Custom seasonal variation (advanced inputs)</option>
            </select>
            <p class="muted" style="font-size:.76rem;margin-top:.35rem">This displays monthly composition sensitivity, not observed waste supply. Annual cash flows remain unchanged without a validated monthly dispatch/storage model.</p>
          </div>
          <details class="accordion" id="adv" style="margin-top:1rem">''', 'Evaluate sensitivity controls')
    s = edit(s, '  const gate = $("gate");',
             '''  const presetInput = (key, value) => {
    const next = { ...(inp().advanced || {}) };
    if (value === null) delete next[key]; else next[key] = value;
    store.setInputs({ advanced: next });
    renderAdvanced();
  };
  const biocharPreset = $("biocharPreset");
  const staffPreset = $("staffPreset");
  const seasonPreset = $("seasonPreset");
  const currentPriceUSD = Number(inp().advanced?.biochar_price_usd ?? meta.advanced?.biochar_price_usd?.default ?? 100);
  const sgdFx = Number(meta.fx?.usd_sgd || 1.2881);
  const currentSGD = currentPriceUSD * sgdFx;
  biocharPreset.value = !Object.prototype.hasOwnProperty.call(inp().advanced || {}, "biochar_price_usd") ? "default"
    : [150,300,1000].find((v) => Math.abs(currentSGD - v) < .5)?.toString() || "custom";
  const currentCrew = Number(inp().advanced?.continuous_crew_per_shift || 0);
  staffPreset.value = [0,3,5].includes(currentCrew) ? String(currentCrew) : "custom";
  const currentAmplitude = Number(inp().advanced?.seasonal_woody_amplitude || 0);
  seasonPreset.value = currentAmplitude === 0 ? "0" : Math.abs(currentAmplitude - .1125) < .0001
    ? (Math.abs(Number(inp().advanced?.woody_share || meta.advanced?.woody_share?.default || 0.70) - .75) < 1e-6 ? "word75" : "0.1125") : "custom";
  biocharPreset.addEventListener("change", () => {
    if (biocharPreset.value === "custom") { $("adv").open = true; return; }
    presetInput("biochar_price_usd", biocharPreset.value === "default" ? null : Number(biocharPreset.value) / sgdFx);
  });
  staffPreset.addEventListener("change", () => {
    if (staffPreset.value === "custom") { $("adv").open = true; return; }
    presetInput("continuous_crew_per_shift", staffPreset.value === "0" ? null : Number(staffPreset.value));
  });
  seasonPreset.addEventListener("change", () => {
    if (seasonPreset.value === "custom") { $("adv").open = true; return; }
    const next = { ...(inp().advanced || {}) };
    if (seasonPreset.value === "0") delete next.seasonal_woody_amplitude;
    else {
      next.seasonal_woody_amplitude = 0.1125;
      if (seasonPreset.value === "word75") next.woody_share = 0.75; // explicit, unverified annual composition override
    }
    store.setInputs({ advanced: next }); renderAdvanced();
  });
  const gate = $("gate");''', 'Evaluate preset logic')
    # Correct typo that would make selection fail on revisit. Use normalized literal.
    s = s.replace(' ? ".1125" : "custom";', ' ? "0.1125" : "custom";')
    return s


def patch_results_js(s: str) -> str:
    s = edit(s, '    <section class="section">\n      <div class="flow reveal" id="flow"></div>',
             '''    <section class="section">
      <div class="section-head reveal"><div><h2 class="title-m">Project cash flow integrity</h2>
        <p>Reconciled operating cash flows, investment and lifecycle costs. Negative NPV is a model result, not an automatic calculation error.</p></div></div>
      ${r.finance_audit ? `<div class="card reveal" style="padding:1.2rem 1.4rem">
        <p class="muted">Integrity check: <b>${esc(r.finance_audit.status)}</b> · Largest yearly discrepancy ${fmt.money(r.finance_audit.max_annual_gap_sgd)}</p>
        <table class="tbl" style="margin-top:.7rem"><thead><tr><th>Year 2 operating summary</th><th class="num">S$ per year</th></tr></thead><tbody>
          <tr><td>Biochar + gate fees + conditional credit sales</td><td class="num">${fmt.money(r.finance_audit.year2.revenue_sgd)}</td></tr>
          <tr><td>Cash OPEX (labour, plant, land, transport, certification)</td><td class="num">${fmt.money(r.finance_audit.year2.cash_opex_sgd)}</td></tr>
          <tr><td><b>Cash flow (revenue minus cash OPEX)</b></td><td class="num"><b>${fmt.money(r.finance_audit.year2.cash_flow_sgd)}</b></td></tr>
        </tbody></table>
        <p class="muted" style="margin-top:.7rem">Initial construction CAPEX is a separate year-zero outflow; levelised cost includes discounted CAPEX and discounted OPEX. It is not the same as yearly cash OPEX.</p>
      </div>` : `<div class="card reveal" style="padding:1rem">Re-run this older saved evaluation to receive a financial reconciliation audit.</div>`}
    </section>

    <section class="section">
      <div class="section-head reveal"><div><h2 class="title-m">Seasonal composition sensitivity</h2>
        <p>Illustrative monthly woody fraction. Not observed collection tonnages or a prediction of rainfall effects.</p></div></div>
      <div class="card reveal" style="padding:1.2rem 1.4rem">
        ${r.seasonality ? `<div style="display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:5px;align-items:end;height:115px;margin:1.2rem 0">
          ${r.seasonality.months.map((x) => `<div style="display:flex;flex-direction:column;height:100%;align-items:center;justify-content:flex-end;gap:6px" title="Month ${x.month}: ${(x.woody_share*100).toFixed(2)}% woody share">
            <div style="background:${x.monsoon ? "#d95926" : "#3987e5"};width:100%;max-width:32px;height:${Math.max(8,x.woody_share*95)}px;border-radius:3px 3px 0 0"></div>
            <small class="muted" style="font-size:.7rem">${x.month}</small></div>`).join("")}</div>
          <p class="muted">500 synthetic composition draws; annual mean ${(r.seasonality.mean_woody_share*100).toFixed(2)}%; monsoon month values ${((r.seasonality.mean_woody_share-r.seasonality.amplitude)*100).toFixed(2)}%. Variation is ${r.seasonality.amplitude ? "enabled" : "off"}. Not connected to the 15-year cash-flow schedule without a validated monthly supply model.</p>
          <details class="accordion"><summary>Show illustrative P10/P90 accessible woody supply ranges</summary><div class="acc-body">
            <table class="tbl"><thead><tr><th>Month</th><th>Assumed woody fraction</th><th>P10 available tonnes</th><th>P90 available tonnes</th></tr></thead><tbody>
            ${r.seasonality.months.map((x) => `<tr><td>${x.month}</td><td>${(100*x.woody_share).toFixed(2)}%</td><td>${fmt.int(x.p10_woody_available_t)}</td><td>${fmt.int(x.p90_woody_available_t)}</td></tr>`).join("")}</tbody></table>
            <p class="muted">Ranges arise from a hypothetical normal distribution of composition, not observed monthly waste quantities.</p>
          </div></details>` : "No seasonal profile available for this saved evaluation."}
      </div>
    </section>

    <section class="section">
      <div class="flow reveal" id="flow"></div>''', 'Results financial and seasonal displays')
    return s


def patch_reporting(s: str) -> str:
    if 'def make_report(result: dict' not in s:
        raise RuntimeError('Unknown consultancy PDF module; no report was modified')
    s = edit(s, '    if not site_view_png or map_source != \'browser\':',
             '''    from .finance_audit import audit_financial_result
    audit = audit_financial_result(result)  # reject inconsistent financial reports
    if not site_view_png or map_source != 'browser':''', 'PDF pre-export audit')
    s = edit(s, r"    story.append(P('Indicative nominal cash flows, including construction year and the app\'s operating assumptions. All amounts in S$ thousands.'))",
             r"    story.append(P('Indicative nominal cash flows, including construction year and the app\'s operating assumptions. All amounts in S$ thousands.'))" + "\n"
             "    story.append(P('Checked: each cash flow equals biochar sales plus gate fees plus applicable carbon credit sales, less cash operating expenses and any capital expenditure. Construction capital is deducted once in year zero.', 'muted'))",
             'PDF reconciled cashflow caption')
    return s


def install(root: Path) -> None:
    if not all((root / p).is_file() for p in ("serve.py", "api/server.py", "web/js/views/evaluate.js", "biotwin/pathway.py")):
        raise RuntimeError('Expected FastAPI/JavaScript BioTwin website (serve.py, api/, web/, biotwin/).')
    actions = {
        "biotwin/pathway.py": patch_pathway,
        "biotwin/evaluate.py": patch_evaluate,
        "api/server.py": patch_api,
        "web/js/views/evaluate.js": patch_evaluate_js,
        "web/js/views/results.js": patch_results_js,
    }
    # Report generator is optional if user has not yet installed the consultancy export.
    if (root / "biotwin/reporting.py").is_file():
        actions["biotwin/reporting.py"] = patch_reporting
    planned = []
    for rel, fn in actions.items():
        target = root / rel
        before = target.read_text(encoding='utf-8')
        after = fn(before)
        if target.suffix == '.py':
            ast.parse(after, filename=rel)
        planned.append((target, before, after))
    # Write only after all source patches have passed validation.
    for target, before, after in planned:
        if before == after:
            print('UNCHANGED', target.relative_to(root))
            continue
        backup = target.with_suffix(target.suffix + '.pre-finance-upgrade.bak')
        if not backup.exists(): backup.write_text(before, encoding='utf-8')
        target.write_text(after, encoding='utf-8')
        print('UPDATED', target.relative_to(root))
    finance_file = root / 'biotwin/finance_audit.py'
    if not finance_file.exists() or finance_file.read_bytes() != (PACKAGE / 'biotwin/finance_audit.py').read_bytes():
        shutil.copy2(PACKAGE / 'biotwin/finance_audit.py', finance_file)
        print('INSTALLED', finance_file.relative_to(root))
    ignore = root / '.gitignore'
    if ignore.is_file():
        s = ignore.read_text(encoding='utf-8')
        if '*.pre-finance-upgrade.bak' not in s:
            ignore.write_text(s.rstrip() + '\n\n# Finance upgrade backups\n*.pre-finance-upgrade.bak\n', encoding='utf-8')
    print('\nDone. Start BioTwin with: py serve.py')
    print('Evaluate > commercial assumptions > Get results > finance integrity panel')
    if (root / 'biotwin/reporting.py').exists():
        print('PDF export now rejects financially inconsistent data.')
    else:
        print('NOTE: Consultancy PDF export is not installed in this repository; this patch improves the app calculations and interface.')


if __name__ == '__main__':
    try:
        install(Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve())
    except Exception as exc:
        print(f'UPGRADE STOPPED: {exc}', file=sys.stderr)
        sys.exit(1)
