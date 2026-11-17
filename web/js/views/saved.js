// Saved evaluations: compare side by side.
import * as charts from "../charts.js";
import { csvCell, download, esc, fmt, reveal } from "../ui.js";

const ROWS = [
  ["Plant", (r) => [...new Set(r.layout.map((l) => l.label))].join(" + "), "text"],
  ["Plots", (r) => r.layout.map((l) => l.name).join(", "), "text"],
  ["Waste processed (t/yr)", (r) => r.metrics.processed_t, "int"],
  ["Biochar (t/yr)", (r) => r.metrics.biochar_t, "int"],
  ["Capital cost", (r) => r.metrics.capex_sgd, "money"],
  ["Cash flow, year 2", (r) => r.metrics.year2_cash_flow_sgd, "money"],
  ["Net present value", (r) => r.metrics.npv_sgd, "money"],
  ["Levelised cost (per t)", (r) => r.metrics.levelised_cost_sgd_per_t, "money"],
  ["Break-even gate fee (per t)", (r) => r.metrics.break_even_gate_fee_sgd_per_t, "money"],
  ["Carbon credits (t CO₂e/yr)", (r) => r.metrics.credits_t, "int"],
  ["Climate vs today (t CO₂e/yr)", (r) => r.metrics.net_climate_t, "signed"],
  ["Average trucking (km)", (r) => r.metrics.mean_haul_km, "dec"],
  ["Staff", (r) => r.metrics.staff, "int"],
  ["Gate fee charged", (r) => r.scenario.gate_fee, "money"],
  ["Credits sold", (r) => (r.scenario.sell_credits ? "yes" : "no"), "text"],
];
const F = { int: fmt.int, money: (v) => fmt.money(v), signed: (v) => fmt.signed(v), dec: (v) => fmt.dec(v), text: (v) => v };

export function mount(root, { store, go }) {
  const draw = () => {
    const saved = store.state.saved;
    if (!saved.length) {
      root.innerHTML = `<div class="page empty"><div class="eyebrow">Saved evaluations</div><h2 class="title-l" style="margin-top:.4rem">Nothing saved yet</h2>
        <p>Run an evaluation and press Save on the results page. Saved evaluations stay in this browser.</p>
        <button class="btn primary lg" id="start">Start a new evaluation</button></div>`;
      root.querySelector("#start").addEventListener("click", () => go("evaluate"));
      return;
    }
    root.innerHTML = `<div class="page">
      <div class="res-head"><div class="reveal"><div class="eyebrow">Saved evaluations</div>
        <h1 class="title-l" style="margin-top:.3rem">Compare scenarios</h1>
        <p style="margin-top:.35rem">One big plant against several small ones, or the same plant in different regions.</p></div>
        <div class="actions reveal"><button class="btn" id="csv">Download comparison</button></div></div>
      <div class="grid g2 section" style="margin-top:2rem">
        <div class="card reveal"><h4>Levelised cost per tonne</h4><p class="muted">lower is better</p><div class="chart" id="c1" style="height:300px"></div></div>
        <div class="card reveal" style="--d:.06s"><h4>Break-even gate fee</h4><p class="muted">lower is better · dashed line = incineration fee</p><div class="chart" id="c2" style="height:300px"></div></div>
      </div>
      <div class="card reveal" style="margin-top:1rem;overflow-x:auto;padding:.4rem .6rem"><table class="tbl"><thead><tr><th></th>
        ${saved.map((s, i) => `<th>${i + 1}. ${esc(s.name)}<br><span class="muted">${esc(s.time)}</span></th>`).join("")}</tr></thead><tbody>
        ${ROWS.map(([k, f, t]) => `<tr><td class="k">${k}</td>${saved.map((s) => `<td class="${t === "text" ? "" : "num"}">${esc(F[t](f(s.result)))}</td>`).join("")}</tr>`).join("")}
        <tr><td></td>${saved.map((s) => `<td><button class="link-btn" data-open="${s.id}">Open</button> &nbsp; <button class="link-btn" style="color:#ff6961" data-del="${s.id}">Delete</button></td>`).join("")}</tr>
      </tbody></table></div></div>`;
    const names = saved.map((s, i) => `${i + 1}. ${s.name}`);
    const cap = saved[0].result.gate_fee_cap_sgd;
    root.querySelector("#c1").closest(".reveal").addEventListener("revealed", () =>
      charts.bars(root.querySelector("#c1"), names, saved.map((s) => s.result.metrics.levelised_cost_sgd_per_t), { unit: "/t" }), { once: true });
    root.querySelector("#c2").closest(".reveal").addEventListener("revealed", () =>
      charts.bars(root.querySelector("#c2"), names, saved.map((s) => s.result.metrics.break_even_gate_fee_sgd_per_t),
        { unit: "/t", ref: cap, refLabel: "incineration" }), { once: true });
    root.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", () => {
      store.setResult(saved.find((s) => String(s.id) === b.dataset.open).result); go("results");
    }));
    root.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => { store.remove(Number(b.dataset.del)); charts.disposeAll(); draw(); }));
    root.querySelector("#csv").addEventListener("click", () => {
      const lines = [["", ...names], ...ROWS.map(([k, f]) => [k, ...saved.map((s) => f(s.result))])];
      download("biotwin_saved_evaluations.csv", lines.map((l) => l.map(csvCell).join(",")).join("\n"));
    });
    reveal(root);
  };
  draw();
  return {};
}
