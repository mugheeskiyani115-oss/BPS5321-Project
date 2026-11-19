// Results: what this plant would do, year by year, against business as usual.
import * as charts from "../charts.js";
import { api } from "../api.js";
import { BioMap } from "../map.js";
import { countUp, csvCell, download, esc, fmt, reveal, segmented, tabs, toast } from "../ui.js";

export function mount(root, { meta, geo, store, go }) {
  const r = store.state.result;
  if (!r) {
    root.innerHTML = `<div class="page empty"><div class="eyebrow">Results</div><h2 class="title-l" style="margin-top:.4rem">No evaluation yet</h2>
      <p>Choose a location and a plant, then press Get results.</p><button class="btn primary lg" id="start">Start a new evaluation</button></div>`;
    root.querySelector("#start").addEventListener("click", () => go("evaluate"));
    return {};
  }
  const m = r.metrics, bau = r.bau, sc = r.scenario, d = r.drivers;
  const plants = [...new Set(r.layout.map((l) => l.label))].join(" + ");
  const where = r.layout.map((l) => l.name).join(", ");
  const regions = [...new Set(r.layout.map((l) => l.region))].join(", ");
  const lossOrGain = m.year2_cash_flow_sgd < 0 ? `loses <b>${fmt.money(-m.year2_cash_flow_sgd)}</b> a year from year 2`
    : `earns <b>${fmt.money(m.year2_cash_flow_sgd)}</b> a year from year 2`;
  const viable = m.break_even_gate_fee_sgd_per_t <= sc.gate_fee + 0.5;
  const summary = `Processes <b>${fmt.int(m.processed_t)} t</b> of woody waste a year into <b>${fmt.int(m.biochar_t)} t</b> of biochar.
    It ${lossOrGain}${m.payback_year ? `, paying back in <b>year ${m.payback_year}</b>` : ""}.
    ${viable ? "At your gate fee it breaks even." : `It needs a gate fee of <b>${fmt.money(m.break_even_gate_fee_sgd_per_t, "/t")}</b> to break even — incineration costs owners ${fmt.money(r.gate_fee_cap_sgd, "/t")}.`}
    Compared with burning the same waste for power, the climate effect is <b>${fmt.signed(m.net_climate_t)} t CO₂e</b> a year.`;
  const chips = [`Gate fee S$${fmt.int(sc.gate_fee)}/t`, sc.sell_credits ? "Selling credits" : "No credit sales",
    `${m.analysis_years} years at ${(m.discount_rate * 100).toFixed(0)}%`, sc.sites.length ? "Plots chosen by you" : "Plot chosen by the tool",
    sc.feedstock_basis === "six_sector_scenario" ? "Six-sector synthetic scenario" : "55-area vegetation proxy",
    ...(Object.keys(sc.advanced || {}).length ? [`${Object.keys(sc.advanced).length} advanced input(s) changed`] : [])];

  const tiles = [
    ["Waste processed", m.processed_t, (v) => `${fmt.int(v)} t`, "tonnes a year"],
    ["Capital cost", m.capex_sgd, (v) => fmt.money(v), "built in " + (d.first_year - 1)],
    [`Net present value`, m.npv_sgd, (v) => fmt.money(v), `${m.analysis_years} years, vs doing nothing`, m.npv_sgd < 0 ? "bad" : "ok"],
    ["Break-even gate fee", m.break_even_gate_fee_sgd_per_t, (v) => fmt.money(v, "/t"), `incineration: ${fmt.money(r.gate_fee_cap_sgd, "/t")}`],
    ["Biochar made", m.biochar_t, (v) => `${fmt.int(v)} t`, "tonnes a year"],
    ["Cash flow, year 2", m.year2_cash_flow_sgd, (v) => fmt.money(v), "income − running costs", m.year2_cash_flow_sgd < 0 ? "bad" : "ok"],
    ["Carbon credits", m.credits_t, (v) => `${fmt.int(v)} t`, "CO₂e a year"],
    ["Climate vs today", m.net_climate_t, (v) => `${fmt.signed(v)} t`, "CO₂e a year"],
  ];

  root.innerHTML = `
  <div class="page">
    <div class="res-head">
      <div class="reveal">
        <div class="eyebrow">Evaluation results</div>
        <h1 class="title-l" style="margin-top:.3rem">${esc(plants)}</h1>
        <p style="margin-top:.35rem;font-size:1.05rem">${esc(where)} · ${esc(regions)}</p>
      </div>
      <div class="actions reveal" style="--d:.08s">
        <button class="btn" id="edit">Edit inputs</button>
        <button class="btn" id="save">Save</button>
        <button class="btn" id="dl">Download CSV</button>
        <label class="btn" for="mapUpload" style="cursor:pointer">Use my map screenshot</label>
        <input id="mapUpload" type="file" accept="image/png,image/jpeg" hidden>
        <button class="btn primary" id="pdf">Export PDF report</button>
      </div>
    </div>
    <p class="summary reveal" style="--d:.12s">${summary}</p>
    <div class="reveal" style="--d:.16s;margin-top:.9rem">${chips.map((c) => `<span class="chip">${esc(c)}</span>`).join("")}</div>

    <div class="split">
      <div class="mapcard reveal"><div class="map" id="map" style="position:absolute;inset:0"></div>
        <div class="map-legend"><div><i style="background:#d95926"></i>Your plant${r.layout.length > 1 ? "s" : ""}</div>
          <div><i style="background:#86b6ef"></i>Trucks on OpenStreetMap roads</div>
          <div><i style="background:linear-gradient(90deg,#104281,#86b6ef)"></i>Planning areas supplying it</div></div></div>
      <div class="metrics">${tiles.map(([k, , , n, tone], i) => `<div class="tile reveal" style="--d:${0.04 * i}s">
        <div class="k">${k}</div><div class="v ${tone || ""}" data-i="${i}">—</div><div class="n">${esc(n)}</div></div>`).join("")}</div>
    </div>

    <section class="section">
      <div class="section-head reveal"><div><h2 class="title-m">Project cash flow integrity</h2>
        <p>Reconciled operating cash flows, investment and lifecycle costs.</p></div></div>
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

    <!-- BIOTWIN_COMMERCE_2026_RESULTS -->
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
      <div class="flow reveal" id="flow"></div>
    </section>

    <section class="section">
      <div class="section-head reveal"><div><h2 class="title-m">Business as usual vs our plant</h2>
        <p>The same tonnes of woody waste, followed through today's route and through our plant.</p></div></div>
      <div class="card reveal" style="padding:.4rem .6rem">${compareTable(r)}</div>
      <p class="muted reveal" style="margin-top:.6rem">Today's destinations are approximated by the mapped waste-to-energy plants and Gardens by the Bay's biomass plant; Singapore's biomass power plants are not mapped.</p>
    </section>

    <section class="section">
      <div class="section-head reveal"><div><h2 class="title-m">Findings</h2><p>The findings are as follows.</p></div></div>
      ${r.findings.map((f, i) => `<div class="finding reveal" style="--d:${0.04 * i}s"><div class="i">${String(i + 1).padStart(2, "0")}</div>
        <div><h4>${esc(f.title)}</h4><p>${esc(f.text)}</p></div></div>`).join("")}
    </section>

    <section class="section">
      <div class="section-head reveal"><div><h2 class="title-m">Year by year</h2>
        <p>Nominal cash flows. Year ${d.first_year - 1} builds the plant; each later year differs for the reasons below.</p></div></div>
      <div class="drivers reveal">
        <span class="chip"><span class="dot" style="background:#3987e5"></span>${d.first_year}: ${(d.ramp_up_year1 * 100).toFixed(0)}% output while commissioning</span>
        <span class="chip"><span class="dot" style="background:#d95926"></span>Staff +${(d.wage_growth * 100).toFixed(1)}%/yr (MOM wage trend)</span>
        <span class="chip"><span class="dot" style="background:#199e70"></span>Prices, power, land, trucking +${(d.inflation_long_run * 100).toFixed(0)}%/yr (MAS outlook)</span>
        ${sc.sell_credits ? `<span class="chip"><span class="dot" style="background:#86b6ef"></span>Credit price €${fmt.int(d.credit_price_first_eur)} → €${fmt.int(d.credit_price_last_eur)} (Senken path)</span>` : ""}
      </div>
      <div class="card reveal"><div class="card-head"><p class="muted" id="cfNote"></p><div id="cfMode"></div></div><div class="chart" id="cf"></div></div>
      <details class="accordion reveal" style="margin-top:.6rem"><summary>Show the yearly numbers <span class="chev">›</span></summary>
        <div class="acc-body" style="overflow-x:auto">${yearTable(r.years)}</div></details>
    </section>

    <section class="section">
      <div class="section-head reveal"><div><h2 class="title-m">Compare</h2><p>Where the money goes, and how other plots and plant sizes would do.</p></div></div>
      <div id="tabs" class="reveal"></div>
      <div class="card reveal"><div class="chart" id="cmp"></div><p class="muted" id="cmpNote" style="margin-top:.4rem"></p></div>
    </section>

    <section class="section">
      <details class="accordion reveal"><summary>Assumptions used in this evaluation <span class="chev">›</span></summary>
        <div class="acc-body" style="overflow-x:auto"><table class="tbl"><thead><tr><th>Input</th><th class="num">Used</th><th class="num">Default</th><th>Unit</th><th>Source</th></tr></thead>
        <tbody>${r.assumptions.map((a) => `<tr><td>${esc(a.input)}</td><td class="num">${esc(a.value)}</td><td class="num">${esc(a.default)}</td>
          <td class="k">${esc(a.unit)}</td><td class="k">${esc(a.source)}</td></tr>`).join("")}</tbody></table></div></details>
    </section>
  </div>
  <footer class="foot">Results are indicative — not a design for procurement.</footer>`;

  const $ = (id) => root.querySelector(`#${id}`);
  // metrics count up when visible
  root.querySelectorAll(".metrics .v").forEach((el) => {
    const [, v, f] = tiles[+el.dataset.i];
    el.textContent = f(v);
    el.closest(".reveal").addEventListener("revealed", () => { el.dataset.v = "0"; countUp(el, v, f, 1300); }, { once: true });
  });
  // comparison bars grow when visible
  root.querySelectorAll(".bar i").forEach((b) => b.closest(".reveal").addEventListener("revealed",
    () => requestAnimationFrame(() => (b.style.width = b.dataset.w)), { once: true }));

  $("flow").innerHTML = flowSvg(r);
  const map = new BioMap($("map"), { meta, geo, intro: false, onSiteClick: () => {} });
  map.showResult(r);

  // charts render when they scroll into view (so the entrance animation is seen)
  const cfEl = $("cf");
  const cfNotes = { year: `Building the plant (${fmt.money(m.capex_sgd)}) happens in ${d.first_year - 1} and is left out here so the yearly changes are visible.`,
    cum: "Running total including the cost of building the plant." };
  const showCf = (v) => { (v === "year" ? charts.yearly : charts.cumulative)(cfEl, r.years); $("cfNote").textContent = cfNotes[v]; };
  segmented($("cfMode"), [{ value: "year", label: "Each year" }, { value: "cum", label: "Cumulative" }], "year", showCf);
  cfEl.closest(".reveal").addEventListener("revealed", () => showCf("year"), { once: true });
  const cmpEl = $("cmp");
  const showCmp = (v) => {
    const note = $("cmpNote");
    if (v === "cost") { charts.perTonne(cmpEl, r.cost_per_t, r.income_per_t); note.textContent = "Levelised over the plant's life, per tonne of waste. Orange = costs, green = income."; }
    if (v === "plots") {
      const mine = new Set(r.layout.map((l) => l.site_id));
      charts.compare(cmpEl, r.sites_compare, { label: (x) => x.name.replace(/ \(.*\)/, ""), value: (x) => x.net_cost_sgd_per_t,
        highlight: (x) => mine.has(x.site_id), note: (x) => `${x.region} · land S$${x.rent_sgd_m2.toFixed(2)}/m² · ${x.mean_haul_km.toFixed(1)} km` });
      note.textContent = "Net cost per tonne for the same plant at every candidate plot. Orange = yours.";
    }
    if (v === "sizes") {
      const mine = new Set(r.layout.map((l) => l.size_class));
      charts.compare(cmpEl, r.sizes_compare, { label: (x) => x.label.replace(" continuous", "").replace(" semi-", " semi-"),
        value: (x) => x.net_cost_sgd_per_t, highlight: (x) => mine.has(x.size_class), note: (x) => `${fmt.int(x.processed_t)} t/yr · ${Math.round(x.staff_fte)} staff` });
      note.textContent = "Net cost per tonne for every plant size at your plot(s). Orange = yours.";
    }
  };
  tabs($("tabs"), [{ value: "cost", label: "Cost per tonne" }, { value: "plots", label: "Other plots" }, { value: "sizes", label: "Plant sizes" }],
    "cost", showCmp);
  cmpEl.closest(".reveal").addEventListener("revealed", () => showCmp("cost"), { once: true });

  // actions
  $("edit").addEventListener("click", () => {
    store.setInputs({ region: sc.region, mode: sc.sites.length ? "manual" : "auto", sites: sc.sites, size: sc.size,
      gate_fee: sc.gate_fee, sell_credits: sc.sell_credits, advanced: sc.advanced || {} });
    go("evaluate");
  });
  $("save").addEventListener("click", () => {
    const name = prompt("Name this evaluation", `${plants} · ${where}`.slice(0, 70));
    if (name == null) return;
    store.save(name.trim() || "Evaluation");
    toast("Saved — open Saved to compare");
  });
  $("dl").addEventListener("click", () => download("biotwin_evaluation.csv", toCsv(r, plants, where)));
  let uploadedMapCapture = null;
  $("mapUpload").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!["image/png", "image/jpeg"].includes(file.type) || file.size > 3000000) {
      toast("Choose a PNG or JPEG screenshot smaller than 3 MB", "err");
      return;
    }
    try {
      uploadedMapCapture = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error("Unable to read screenshot"));
        reader.readAsDataURL(file);
      });
      toast("Your 3D map screenshot has been attached to the PDF export");
    } catch (error) { toast(error.message, "err"); }
  });
  $("pdf").addEventListener("click", async () => {
    const button = $("pdf"); const oldLabel = button.textContent;
    button.disabled = true; button.textContent = "Preparing report...";
    try {
      const screenshot = uploadedMapCapture || await map.captureForReport();
      const pdf = await api.report(sc, screenshot);
      const url = URL.createObjectURL(pdf);
      const a = document.createElement("a");
      a.href = url; a.download = "BioTwin_Scenario_Assessment.pdf";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      toast("Consulting-style PDF report prepared");
    } catch (error) { toast(error.message, "err"); }
    finally { button.disabled = false; button.textContent = oldLabel; }
  });
  reveal(root);
  return { destroy: () => map.destroy() };
}

function compareTable(r) {
  const m = r.metrics, b = r.bau;
  const km = Math.max(m.mean_haul_km, b.mean_haul_km, 1), co = Math.max(Math.abs(m.credits_t), b.avoided_t, 1);
  const bar = (v, max, color) => `<div class="bar"><i style="background:${color}" data-w="${Math.max(2, (Math.abs(v) / max) * 100)}%"></i></div>`;
  const rows = [
    ["Where the woody waste goes", b.destination, "Pyrolysis into biochar", ""],
    ["Waste handled", `${fmt.int(b.processed_t)} t/yr`, `${fmt.int(m.processed_t)} t/yr`, "same tonnes"],
    ["Average trucking", `${fmt.dec(b.mean_haul_km)} km${bar(b.mean_haul_km, km, "#636366")}`, `${fmt.dec(m.mean_haul_km)} km${bar(m.mean_haul_km, km, "#3987e5")}`,
      `${fmt.signed(m.mean_haul_km - b.mean_haul_km, 1)} km`],
    ["Carbon outcome", `${fmt.int(b.avoided_t)} t CO₂e avoided by power${bar(b.avoided_t, co, "#636366")}`,
      `${fmt.int(m.credits_t)} t CO₂e credit${bar(m.credits_t, co, "#199e70")}`, `${fmt.signed(m.net_climate_t)} t`],
    ["Biochar made", "—", `${fmt.int(m.biochar_t)} t/yr`, ""],
    ["Jobs on site", "—", fmt.int(m.staff), ""],
  ];
  return `<table class="tbl fixed"><colgroup><col style="width:22%"><col style="width:33%"><col style="width:33%"><col style="width:12%"></colgroup>
    <thead><tr><th></th><th>Business as usual (today)</th><th>With your plant</th><th>Change</th></tr></thead><tbody>
    ${rows.map(([k, a, p, c]) => `<tr><td class="k">${k}</td><td>${a}</td><td>${p}</td><td class="d">${c}</td></tr>`).join("")}</tbody></table>`;
}

function yearTable(years) {
  const cols = [["calendar_year", "Year", (v) => v], ["tonnes", "Tonnes", fmt.int], ["biochar_sales_sgd", "Biochar", fmt.money],
    ["gate_fees_sgd", "Gate fees", fmt.money], ["credit_sales_sgd", "Credits", fmt.money], ["staff_sgd", "Staff", fmt.money],
    ["maintenance_sgd", "Maint.", fmt.money], ["trucking_sgd", "Trucking", fmt.money], ["capital_sgd", "Capital", fmt.money],
    ["cash_flow_sgd", "Cash flow", fmt.money], ["cumulative_sgd", "Cumulative", fmt.money]];
  return `<table class="tbl"><thead><tr>${cols.map(([, h]) => `<th class="num">${h}</th>`).join("")}</tr></thead><tbody>
    ${years.map((y) => `<tr>${cols.map(([k, , f]) => `<td class="num">${f(y[k])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function flowSvg(r) {
  const m = r.metrics, b = r.bau;
  const nAreas = new Set(r.flows.map((f) => f.origin)).size;
  const n = r.layout.length;
  const nodes = [
    [125, "Planning areas", `${nAreas} supplying`, `${fmt.int(m.processed_t)} t/yr`, "#3987e5"],
    [375, "Trucks", `${fmt.dec(m.mean_haul_km)} km average`, `today ${fmt.dec(b.mean_haul_km)} km`, "#a1a1a6"],
    [625, `${n} plant${n > 1 ? "s" : ""}`, [...new Set(r.layout.map((l) => l.label))].join(" + ").slice(0, 26), `${fmt.int(m.staff)} staff`, "#d95926"],
    [875, "Biochar", `${fmt.int(m.biochar_t)} t/yr`, `stores ${fmt.int(m.stored_co2_t)} t CO₂e`, "#199e70"],
  ];
  let s = `<svg viewBox="0 0 1000 190" role="img" aria-label="Process flow">`;
  for (let i = 0; i < 3; i++) {
    const x1 = nodes[i][0], x2 = nodes[i + 1][0];
    const p = `M${x1 + 92},95 C${x1 + 140},60 ${x2 - 140},130 ${x2 - 92},95`;
    s += `<path d="${p}" stroke="rgba(255,255,255,.08)" stroke-width="2" fill="none"/>
      <path class="dash" d="${p}" stroke="#2997ff" stroke-width="2" fill="none" opacity=".8"/>`;
    for (let k = 0; k < 3; k++) s += `<circle r="4" fill="#2997ff"><animateMotion dur="2.4s" begin="${0.8 * k}s" repeatCount="indefinite" path="${p}"/></circle>`;
  }
  nodes.forEach(([x, t, l1, l2, c]) => {
    s += `<rect x="${x - 92}" y="38" width="184" height="114" rx="20" fill="#1d1d1f" stroke="${c}" stroke-opacity=".55"/>
      <circle cx="${x - 64}" cy="62" r="6" fill="${c}"/>
      <text x="${x - 50}" y="67" fill="#f5f5f7" font-size="15" font-weight="600">${esc(t)}</text>
      <text x="${x - 72}" y="103" fill="#f5f5f7" font-size="14">${esc(l1)}</text>
      <text x="${x - 72}" y="127" fill="#a1a1a6" font-size="12.5">${esc(l2)}</text>`;
  });
  return s + "</svg>";
}

function toCsv(r, plants, where) {
  const lines = [["BioTwin Singapore evaluation"], ["Plant", plants], ["Where", where], [],
    ["Metric", "Value"], ...Object.entries(r.metrics).map(([k, v]) => [k, v]), [],
    ["Year", ...Object.keys(r.years[0])], ...r.years.map((y) => ["", ...Object.values(y)]), [],
    ["Finding", "Text"], ...r.findings.map((f, i) => [`${i + 1}. ${f.title}`, f.text])];
  return lines.map((l) => l.map(csvCell).join(",")).join("\n");
}
