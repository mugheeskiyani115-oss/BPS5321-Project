import importlib.util
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'install_into_existing_project.py'
spec=importlib.util.spec_from_file_location('bioinstaller',SCRIPT)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)


def test_patch_original_pathway_idempotence():
    sample='''from dataclasses import dataclass
import pandas as pd
@dataclass(frozen=True)
class Assumptions:
    labour_exponent: float = 0.25
    def __post_init__(self):
        checks = {
            "gate_fee": self.gate_fee_sgd_per_t >= 0, "truck": self.truck_hours > self.handling_h > 0,
        }
def workers_per_shift(plant: pd.Series, a: Assumptions) -> float:
    w = float(plant["workers_per_shift"])
    return w
'''
    p=mod.patch_pathway(sample)
    assert 'capital_grant_fraction: float' in p and 'continuous_crew_per_shift' in p
    assert mod.patch_pathway(p)==p


def test_patch_evaluate_idempotence():
    sample='''ADVANCED = {
    "biochar_price_usd": ("Biochar sale price", "US$/t biochar", 0.0, 1500.0, 10.0),
}
def pro_forma(ev, a, b=None):
    return {"years": []}
'''
    p=mod.patch_evaluate(sample)
    assert 'BIOTWIN_COMMERCE_2026_FINANCE_WRAP' in p
    assert mod.patch_evaluate(p)==p


def test_patch_api_original_and_old_finance_works():
    sample='''from biotwin import validation as vd

def _run():
    ev, pf, bau = res["eval"], res["pro_forma"], res["bau"]
    used = []
    a = res["assumptions"]
    return clean({
        "scenario": {"region": sc.region, "sites": list(sc.sites)},
        "bau": bau, "years": pf["years"], "drivers": pf["drivers"],
    })
'''
    p=mod.patch_api(sample)
    assert '"finance_audit": finance_audit' in p and '"commercial": pf.get("commercial", {})' in p
    assert '"input": "capital_grant_fraction"' in p
    assert mod.patch_api(p)==p


def test_patch_evaluate_html_and_results_template_idempotence():
    sample='''root.innerHTML = `
    <div class="step-h"><span class="n done">3</span><h3>Business inputs</h3></div>
          <details class="accordion" id="adv" style="margin-top:1rem">
    </details>`;
  const gate = $("gate");
'''
    p=mod.patch_evaluate_js(sample)
    assert 'id="commercialScenario"' in p
    assert mod.patch_evaluate_js(p)==p
    sample='''root.innerHTML = `
    <section class="section">
      <div class="flow reveal" id="flow"></div>
    </section>`;'''
    p=mod.patch_results(sample)
    assert 'BIOTWIN_COMMERCE_2026_RESULTS' in p
    assert mod.patch_results(p)==p
