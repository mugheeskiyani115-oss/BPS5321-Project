#!/usr/bin/env python3
"""Update the EXISTING FastAPI + JavaScript BioTwin website in place.

Run from the repository containing serve.py:
    py _commercial_patch\\install_into_existing_project.py .

Safe preflight: all required source anchors are inspected and Python compiled
before ANY existing project file is changed. Backups stored in .biotwin_backups.
Works with original ui-changes and prior finance, PDF and PWC updates.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import shutil
import sys

PACKAGE = Path(__file__).resolve().parent
MARK = "BIOTWIN_COMMERCE_2026"


def replace_one(s, old, new, name):
    if new in s:
        return s
    count = s.count(old)
    if count != 1:
        raise ValueError(f"{name}: expected 1 insertion point, found {count}. Nothing was written.")
    return s.replace(old, new, 1)


def patch_pathway(s):
    if "    capital_grant_fraction: float = 0.0" not in s:
        s=replace_one(s, "    labour_exponent: float = 0.25\n",
            "    labour_exponent: float = 0.25\n"
            "    capital_grant_fraction: float = 0.0  # 0-50%; illustrative grant, NOT awarded\n"
            "    illustrative_tax_rate: float = 0.0  # 0 or a modelled income-tax sensitivity\n",
            "financial assumption definitions")
    if '"capital_grant_fraction":' not in s:
        s=replace_one(s, '            "gate_fee": self.gate_fee_sgd_per_t >= 0, "truck": self.truck_hours > self.handling_h > 0,',
            '            "gate_fee": self.gate_fee_sgd_per_t >= 0, "truck": self.truck_hours > self.handling_h > 0,\n'
            '            "capital_grant_fraction": 0 <= self.capital_grant_fraction <= 0.5,\n'
            '            "illustrative_tax_rate": 0 <= self.illustrative_tax_rate <= 0.25,',
            "financial assumption validation")
    if '    continuous_crew_per_shift: float = 0.0' not in s:
        s=replace_one(s,'    capital_grant_fraction: float = 0.0  # 0-50%; illustrative grant, NOT awarded\n',
            '    capital_grant_fraction: float = 0.0  # 0-50%; illustrative grant, NOT awarded\n'
            '    continuous_crew_per_shift: float = 0.0  # 0 = original model, >0 = vendor-unsupported sensitivity\n',
            'labour scenario field')
    if '"continuous_crew_per_shift": 0 <=' not in s:
        s=replace_one(s,'            "capital_grant_fraction": 0 <= self.capital_grant_fraction <= 0.5,',
            '            "capital_grant_fraction": 0 <= self.capital_grant_fraction <= 0.5,\n'
            '            "continuous_crew_per_shift": 0 <= self.continuous_crew_per_shift <= 12,',
            'labour scenario validation')
    if 'if a.continuous_crew_per_shift > 0' not in s:
        s=replace_one(s,'def workers_per_shift(plant: pd.Series, a: Assumptions) -> float:\n    w = float(plant["workers_per_shift"])',
'''def workers_per_shift(plant: pd.Series, a: Assumptions) -> float:
    # Commercial sensitivity. A supplier roster must validate this headcount.
    if a.continuous_crew_per_shift > 0 and "continuous" in str(plant.get("technology", "")).lower():
        return a.continuous_crew_per_shift
    w = float(plant["workers_per_shift"])''',
            'plant labour scenario')
    return s


def patch_evaluate(s):
    if '"capital_grant_fraction": (' not in s:
        s=replace_one(s,
            '    "biochar_price_usd": ("Biochar sale price", "US$/t biochar", 0.0, 1500.0, 10.0),',
'''    "biochar_price_usd": ("Biochar sale price", "US$/t biochar", 0.0, 1500.0, 10.0),
    "capital_grant_fraction": ("Illustrative grant share of construction CAPEX (not awarded)", "fraction", 0.0, 0.50, 0.05),
    "illustrative_tax_rate": ("Simplified income tax sensitivity (not tax advice)", "fraction", 0.0, 0.25, 0.01),''',
            'advanced finance scenario controls')
    if '"continuous_crew_per_shift": (' not in s:
        s=replace_one(s, '    "capital_grant_fraction": ("Illustrative grant share of construction CAPEX (not awarded)", "fraction", 0.0, 0.50, 0.05),',
            '    "capital_grant_fraction": ("Illustrative grant share of construction CAPEX (not awarded)", "fraction", 0.0, 0.50, 0.05),\n'
            '    "continuous_crew_per_shift": ("Continuous plant staffing (0 = original)", "people/shift", 0.0, 12.0, 0.5),',
            'advanced staffing scenario control')
    if 'BIOTWIN_COMMERCE_2026_FINANCE_WRAP' not in s:
        s += '''\n\n# BIOTWIN_COMMERCE_2026_FINANCE_WRAP
# Existing pro_forma calculates all three revenues and cash OPEX. Keep it intact.
# Add only optional grant, cash tax and an audit-ready cash-flow schedule.
from .commercial_finance import apply_financial_scenario as _bt_apply_financial_scenario
_bt_original_pro_forma = pro_forma

def pro_forma(ev: dict, a, b=None) -> dict:
    original = _bt_original_pro_forma(ev, a, b)
    return _bt_apply_financial_scenario(original, ev, a, b)
'''
    return s


def patch_api(s):
    if 'from biotwin.finance_audit import audit_financial_result' not in s:
        s=replace_one(s, 'from biotwin import validation as vd\n',
              'from biotwin import validation as vd\nfrom biotwin.finance_audit import audit_financial_result\n',
              'import financial audit')
    if 'finance_audit = audit_financial_result(' not in s:
        s=replace_one(s, '    ev, pf, bau = res["eval"], res["pro_forma"], res["bau"]',
'''    ev, pf, bau = res["eval"], res["pro_forma"], res["bau"]
    finance_audit = audit_financial_result({
        "years": pf["years"].to_dict(orient="records"),
        "metrics": {"discount_rate": pf["discount_rate"], "capex_sgd": pf["capex_sgd"],
                    "npv_sgd": pf["npv_sgd"], "levelised_cost_sgd_per_t": pf["levelised_cost_sgd_per_t"]},
    })''', 'API financial reconciliation')
    if '"finance_audit": finance_audit' not in s:
        s=replace_one(s,'        "bau": bau, "years": pf["years"], "drivers": pf["drivers"],',
              '        "bau": bau, "years": pf["years"], "drivers": pf["drivers"],\n'
              '        "finance_audit": finance_audit,', 'API audit response')
    if '"commercial": pf.get("commercial", {})' not in s:
        s=replace_one(s,'        "finance_audit": finance_audit,',
            '        "finance_audit": finance_audit, "commercial": pf.get("commercial", {}),', 'API commercial finance response')
    if '"input": "capital_grant_fraction"' not in s:
        s=replace_one(s, '    return clean({\n        "scenario": {"region": sc.region,',
'''    used.extend([
        {"input": "capital_grant_fraction", "value": float(a.get("capital_grant_fraction", 0.0)),
         "default": 0.0, "unit": "share of construction CAPEX", "tag": "assumption",
         "source": "Hypothetical funding scenario; NEA 3R Fund / EnterpriseSG eligibility and award not established"},
        {"input": "illustrative_tax_rate", "value": float(a.get("illustrative_tax_rate", 0.0)),
         "default": 0.0, "unit": "fraction; simplified illustration", "tag": "assumption",
         "source": "Illustrative profit tax with straight-line noncash depreciation; not Singapore tax capital allowance advice"},
        {"input": "continuous_crew_per_shift", "value": float(a.get("continuous_crew_per_shift", 0.0)),
         "default": 0.0, "unit": "people/shift (0 = original)", "tag": "assumption",
         "source": "Automation sensitivity only; vendor staffing schedule needed"},
    ])
    return clean({
        "scenario": {"region": sc.region,''', 'commercial evidence register')
    # a is the dict of actual assumptions defined earlier in _run; normalise
    if '    a = res["assumptions"]' not in s:
        s=replace_one(s, '    used.extend([\n        {"input": "capital_grant_fraction"',
            '    a = res["assumptions"]\n    used.extend([\n        {"input": "capital_grant_fraction"', 'API local assumptions binding')
    return s


def patch_evaluate_js(s):
    if 'id="commercialScenario"' not in s:
        s=replace_one(s,'          <details class="accordion" id="adv" style="margin-top:1rem">',
'''          <!-- BIOTWIN_COMMERCE_2026: documented illustrations, never procurement quotes -->
          <div class="card" style="padding:1rem;margin:1.15rem 0;background:rgba(255,255,255,.035)">
            <h4 style="margin-bottom:.4rem">Commercial sensitivity</h4>
            <label for="commercialScenario" class="muted">Choose a revenue scenario</label>
            <select id="commercialScenario" class="btn" style="width:100%;margin:.5rem 0;text-align:left">
              <option value="baseline">Original BioTwin assumptions</option>
              <option value="industrial">Construction product S$300/t + illustrative CORCs S$230/tCO₂e</option>
              <option value="premium">Unverified premium product S$1,000/t + illustrative CORCs</option>
              <option value="custom">Custom prices using advanced inputs</option>
            </select>
            <p class="muted" style="font-size:.77rem;margin-bottom:1rem">Product values are unverified market scenarios. Carbon credit sales require separate certification and eligible end use; price does not imply issuance.</p>
            <label for="staffingScenario" class="muted">Continuous plant automation sensitivity</label>
            <select id="staffingScenario" class="btn" style="width:100%;margin:.5rem 0;text-align:left">
              <option value="0">Original plant staffing model</option>
              <option value="3">Hypothetical 3 workers per shift</option>
              <option value="5">Hypothetical 5 workers per shift</option>
              <option value="custom">Custom crew size in advanced inputs</option>
            </select>
            <p class="muted" style="font-size:.77rem;margin-bottom:1rem">Staffing excludes unverified vendor quotation; full FTE calculations include shift coverage, leave and supervisor.</p>
            <label for="grantScenario" class="muted">Hypothetical capital grant (none approved)</label>
            <select id="grantScenario" class="btn" style="width:100%;margin:.5rem 0;text-align:left">
              <option value="0">No grant (base case)</option>
              <option value="0.1">Assume 10% of construction CAPEX</option>
              <option value="0.2">Assume 20% of construction CAPEX</option>
              <option value="0.3">Assume 30% of construction CAPEX</option>
              <option value="custom">Custom grant fraction in advanced inputs</option>
            </select>
            <label for="taxScenario" class="muted">Income tax sensitivity</label>
            <select id="taxScenario" class="btn" style="width:100%;margin:.5rem 0;text-align:left">
              <option value="0">Before tax, original model</option>
              <option value="0.17">Illustrative 17% profit tax and straight-line depreciation</option>
              <option value="custom">Custom assumed rate in advanced inputs</option>
            </select>
            <p class="muted" style="font-size:.77rem">Initial CAPEX remains a year-zero cost. Depreciation is noncash and is used only in the optional simplified tax scenario. Grants require formal eligibility and award verification.</p>
          </div>
          <details class="accordion" id="adv" style="margin-top:1rem">''', 'Evaluate commercial controls')
    if 'const commercialScenario = $("commercialScenario")' not in s:
        s=replace_one(s,'  const gate = $("gate");',
'''  // BIOTWIN_COMMERCE_2026_CONTROL
  const commercialScenario = $("commercialScenario"), grantScenario = $("grantScenario"), taxScenario = $("taxScenario");
  const fxUSD = Number(meta.fx?.usd_sgd || 1.2881), fxEUR = Number(meta.fx?.eur_sgd || 1.4236);
  const commercialAdvanced = () => ({ ...(inp().advanced || {}) });
  const commercialStore = (patch) => {
    store.setInputs(patch);
    if (typeof renderAdvanced === "function") renderAdvanced();
  };
  const makePreset = (mode) => {
    if (mode === "custom") { $("adv").open = true; return; }
    const adv = commercialAdvanced();
    if (mode === "baseline") {
      delete adv.biochar_price_usd; delete adv.credit_price_eur;
      commercialStore({ advanced: adv, sell_credits: false, gate_fee: 0 });
      $("credits").checked = false; $("gate").value = 0;
    } else {
      adv.biochar_price_usd = (mode === "premium" ? 1000 : 300) / fxUSD;
      adv.credit_price_eur = 230 / fxEUR;
      commercialStore({ advanced: adv, sell_credits: true, gate_fee: Number(meta.gate_fee_cap_sgd) });
      $("credits").checked = true; $("gate").value = Number(meta.gate_fee_cap_sgd);
    }
    $("gate").dispatchEvent(new Event("input"));
    if ($("biocharPreset")) $("biocharPreset").value = "custom";
  };
  // Reflect existing cached inputs rather than mislabelling them as a selected preset.
  const priceSGD = Number(inp().advanced?.biochar_price_usd ?? meta.advanced?.biochar_price_usd?.default ?? 100) * fxUSD;
  const creditSGD = Number(inp().advanced?.credit_price_eur ?? meta.advanced?.credit_price_eur?.default ?? 120.67) * fxEUR;
  commercialScenario.value = !inp().sell_credits && !Object.hasOwn(inp().advanced || {}, "biochar_price_usd")
    ? "baseline" : (inp().sell_credits && Math.abs(creditSGD - 230) < .5 && Math.abs(priceSGD - 300) < .5)
    ? "industrial" : (inp().sell_credits && Math.abs(creditSGD - 230) < .5 && Math.abs(priceSGD - 1000) < .5)
    ? "premium" : "custom";
  commercialScenario.addEventListener("change", () => makePreset(commercialScenario.value));
  const staffingScenario = $("staffingScenario");
  const crew = Number(inp().advanced?.continuous_crew_per_shift || 0);
  staffingScenario.value = [0,3,5].includes(crew) ? String(crew) : "custom";
  staffingScenario.addEventListener("change", () => {
    if (staffingScenario.value === "custom") { $("adv").open = true; return; }
    const adv = commercialAdvanced();
    if (Number(staffingScenario.value) === 0) delete adv.continuous_crew_per_shift;
    else adv.continuous_crew_per_shift = Number(staffingScenario.value);
    commercialStore({advanced: adv});
    if ($("staffPreset")) $("staffPreset").value = staffingScenario.value;
  });
  const grant = Number(inp().advanced?.capital_grant_fraction || 0);
  grantScenario.value = [0,.1,.2,.3].includes(grant) ? String(grant) : "custom";
  grantScenario.addEventListener("change", () => {
    if (grantScenario.value === "custom") { $("adv").open = true; return; }
    const adv = commercialAdvanced();
    if (Number(grantScenario.value) === 0) delete adv.capital_grant_fraction;
    else adv.capital_grant_fraction = Number(grantScenario.value);
    commercialStore({advanced: adv});
  });
  const tax = Number(inp().advanced?.illustrative_tax_rate || 0);
  taxScenario.value = tax === 0 ? "0" : tax === .17 ? "0.17" : "custom";
  taxScenario.addEventListener("change", () => {
    if (taxScenario.value === "custom") { $("adv").open = true; return; }
    const adv = commercialAdvanced();
    if (Number(taxScenario.value) === 0) delete adv.illustrative_tax_rate;
    else adv.illustrative_tax_rate = Number(taxScenario.value);
    commercialStore({advanced: adv});
  });
  const gate = $("gate");''', 'Evaluate commercial event handlers')
    # Sliding to published NEA benchmark requires a slider increment that represents S$82.20.
    s=s.replace('id="gate" type="range" min="0" max="150" step="5"',
                'id="gate" type="range" min="0" max="150" step="0.2"',1)
    # When selecting a 2026 scenario on a cached 2025 saved screen, current HUD should be correct.
    # Existing gate handler still owns the definitive state update.
    # Avoid reloading model automatically; user clicks Get results.
    # Keep any installed previous finance controls functional.
    s=s.replace('  commercialScenario.value = "custom"; // Avoid treating saved custom values as the baseline.',
                '  commercialScenario.value = "custom"; // Avoid treating saved custom values as the baseline.',1)
    return s


def patch_results(s):
    if 'BIOTWIN_COMMERCE_2026_RESULTS' not in s:
        s=replace_one(s,'    <section class="section">\n      <div class="flow reveal" id="flow"></div>',
'''    <!-- BIOTWIN_COMMERCE_2026_RESULTS -->
    <section class="section">
      <div class="section-head reveal"><div><h2 class="title-m">Commercial viability & funding</h2>
      <p>Physical product sales, conditional credit revenue, and the effects of hypothetical grant and tax assumptions.</p></div></div>
      ${r.commercial ? `<div class="card reveal" style="padding:1.3rem">
        <div class="grid g3" style="margin-bottom:1rem">
          <div class="tile"><div class="k">Product sales, operating year 2</div><div class="v">${fmt.money(r.commercial.modelled_biochar_revenue_year2_sgd)}</div></div>
          <div class="tile"><div class="k">Potential carbon credit sales, year 2</div><div class="v">${fmt.money(r.commercial.modelled_credit_revenue_year2_sgd)}</div></div>
          <div class="tile"><div class="k">Gate fees, year 2</div><div class="v">${fmt.money(r.commercial.modelled_gate_fee_revenue_year2_sgd)}</div></div>
        </div>
        <table class="tbl"><thead><tr><th>Investment adjustment</th><th class="num">Modelled amount</th></tr></thead><tbody>
        <tr><td>Gross plant construction CAPEX</td><td class="num">${fmt.money(r.commercial.gross_capex_sgd)}</td></tr>
        <tr><td>Hypothetical public grant, not approved</td><td class="num">${fmt.money(r.commercial.illustrative_grant_sgd)}</td></tr>
        <tr><td>Net initial funding required if grant awarded</td><td class="num">${fmt.money(r.commercial.net_initial_cash_outlay_sgd)}</td></tr>
        <tr><td>Illustrative income taxes, total life</td><td class="num">${fmt.money(r.commercial.total_illustrative_cash_taxes_sgd)}</td></tr>
        <tr><td>Annual NONCASH depreciation for tax sensitivity</td><td class="num">${fmt.money(r.commercial.annual_non_cash_depreciation_sgd)}</td></tr>
        <tr><td><b>Scenario NPV</b></td><td class="num"><b>${fmt.money(r.commercial.after_scenario_npv_sgd)}</b></td></tr>
        </tbody></table>
        <p class="muted" style="font-size:.8rem;margin-top:1rem">Capital cost is expensed once as year-zero cash investment, never deducted twice. Grants are assumptions, not awarded funding. Carbon credits are conditional on certification and do not represent avoided-emission claims. A higher product price requires a buyer agreement and material qualification.</p>
      </div>` : `<div class="card reveal" style="padding:1rem">Run a new evaluation to see grant, tax and dual-revenue reconciliation.</div>`}
    </section>
    <section class="section">
      <div class="flow reveal" id="flow"></div>''', 'Results commercial section')
    return s



def patch_reporting(s):
    """Keep the consultancy PDF cash-flow table mathematically interpretable.

    The other-net column reconciles initial CAPEX, hypothetical grant and
    simplified cash taxes, avoiding the old sample's unexplained discrepancy.
    Unknown report variants are left unchanged rather than destroyed.
    """
    if 'audit_financial_result(result)' not in s and 'def make_report(result: dict' in s:
        anchor = '    """Build a PDF from the *current evaluated scenario* without changing model results."""'
        if anchor in s:
            s = s.replace(anchor, anchor + "\n    from .finance_audit import audit_financial_result\n    audit_financial_result(result)  # Refuse inconsistent consultancy reports.", 1)
        else:
            print("WARNING: Unknown report template: direct report audit not inserted; API audit still applies")
    if "Other net (S$k)" in s:
        return s
    a="['Calendar year','Processed tonnes','Revenue (S$k)','Operating cost (S$k)','Net cash flow (S$k)']"
    b="['Calendar year','Processed tonnes','Revenue (S$k)','Operating cost (S$k)','Other net (S$k)','Net cash flow (S$k)']"
    if a not in s:
        print("WARNING: custom PDF table layout detected; finance rows still audit at API level")
        return s
    s=s.replace(a,b,1)
    target="                         num(float(x.get('cash_flow_sgd') or 0)/1000)] for x in selected],"
    addition="""                         num((float(x.get('grant_sgd') or 0)-float(x.get('illustrative_tax_sgd') or 0)-float(x.get('capital_sgd') or 0))/1000),
                         num(float(x.get('cash_flow_sgd') or 0)/1000)] for x in selected],"""
    s=replace_one(s,target,addition,'PDF other cash movements')
    s=replace_one(s,'[26*mm,30*mm,36*mm,42*mm,38*mm],small=True)',
                  '[23*mm,23*mm,33*mm,34*mm,30*mm,29*mm],small=True)',
                  'PDF finance column sizing')
    s=s.replace('The first row is construction expenditure. Operating capital recovery charges are not additionally deducted from project cash flow.',
      'Other net is hypothetical grant less simplified cash tax and capital investment. Revenue less operating cost plus Other net equals reported cash flow. Construction CAPEX is deducted once; noncash depreciation is not a second expense.')
    if "'capital_grant_fraction'" not in s:
        s=s.replace("'plant_life_years','operator_wage_sgd_month'", "'plant_life_years','capital_grant_fraction','illustrative_tax_rate','operator_wage_sgd_month'",1)
    return s


def install(project: Path):
    if not all((project/p).is_file() for p in ["serve.py","api/server.py","biotwin/pathway.py","biotwin/evaluate.py","web/js/views/evaluate.js","web/js/views/results.js"]):
        raise RuntimeError("Not the FastAPI/JavaScript BioTwin project. Choose the folder containing serve.py, api, biotwin, web.")
    patches={"biotwin/pathway.py":patch_pathway,"biotwin/evaluate.py":patch_evaluate,
             "api/server.py":patch_api,"web/js/views/evaluate.js":patch_evaluate_js,
             "web/js/views/results.js":patch_results}
    planned=[]
    for rel,patch in patches.items():
        path=project/rel
        before=path.read_text(encoding="utf-8")
        after=patch(before)
        if path.suffix==".py":ast.parse(after,filename=rel)
        planned.append((path,before,after))
    # The report is optional on the original GitHub branch; update it if installed.
    if (project/"biotwin/reporting.py").exists():
        p=project/"biotwin/reporting.py"
        old=p.read_text(encoding="utf-8")
        new=patch_reporting(old)
        ast.parse(new,filename="reporting.py")
        planned.append((p,old,new))
    backup=project/".biotwin_backups"/datetime.now().strftime("%Y%m%d_%H%M%S")
    backup.mkdir(parents=True,exist_ok=True)
    for path,before,after in planned:
        rel=path.relative_to(project)
        if before!=after:
            b=backup/rel
            b.parent.mkdir(parents=True,exist_ok=True)
            b.write_text(before,encoding="utf-8")
            path.write_text(after,encoding="utf-8")
            print("UPDATED", rel)
        else:print("ALREADY CURRENT",rel)
    for rel in ["biotwin/commercial_finance.py","biotwin/finance_audit.py"]:
        src=PACKAGE/rel
        dst=project/rel
        if dst.exists() and dst.read_bytes()!=src.read_bytes():
            b=backup/rel;b.parent.mkdir(parents=True,exist_ok=True)
            b.write_bytes(dst.read_bytes())
        shutil.copy2(src,dst)
        print("INSTALLED",rel)
    tests_dst=project/"tests"/"test_commercial_finance_upgrade.py"
    tests_dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(PACKAGE/"tests"/"test_commercial_finance.py",tests_dst)
    ignore=project/".gitignore"
    if ignore.exists():
        txt=ignore.read_text(encoding="utf-8")
        if ".biotwin_backups/" not in txt:
            ignore.write_text(txt.rstrip()+"\n\n# Local safety backups from commercial model upgrade\n.biotwin_backups/\n",encoding="utf-8")
    print("\nSUCCESS. Launch the existing website: py serve.py")
    print("Evaluate > Commercial sensitivity > Get results > Results")
    print("Backups:", backup)

if __name__=='__main__':
    try: install(Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve())
    except Exception as e:
        print("INSTALLATION STOPPED SAFELY:",e,file=sys.stderr)
        raise SystemExit(1)
