// Evidence: waste-data check, sources, validation upload, research-PDF checks.
import { api } from "../api.js";
import { csvCell, download, esc, fmt, reveal, tabs, toast } from "../ui.js";

const TAGS = { web: "Published source", notebook: "Team Notebook 2", derived: "Calculated", assumption: "Assumption", pdf: "Research PDF" };

export function mount(root) {
  root.innerHTML = `<div class="page"><div class="reveal"><div class="eyebrow">Evidence</div>
    <h1 class="title-l" style="margin-top:.3rem">Where every number comes from</h1>
    <p style="margin-top:.35rem;max-width:760px">Web sources first, the team's Notebook 2 for the carbon model, and labelled assumptions or forecasts where no data exists.</p></div>
    <div id="tabs" style="margin-top:2rem"></div><div id="body"><div class="skeleton" style="height:320px"></div></div></div>`;
  let data = null;
  const body = root.querySelector("#body");
  const show = (v) => {
    if (!data) return;
    body.innerHTML = { waste: waste, sources: sources, validation: validation, pdf: pdf }[v](data);
    if (v === "sources") wireSources(body, data);
    if (v === "validation") wireValidation(body, data);
    reveal(body);
  };
  const t = tabs(root.querySelector("#tabs"), [{ value: "waste", label: "Waste data" }, { value: "sources", label: "Sources" },
    { value: "validation", label: "Validation" }, { value: "pdf", label: "Research PDF" }], "waste", show);
  api.evidence().then((d) => { data = d; show("waste"); t.set("waste"); }).catch((e) => {
    body.innerHTML = `<p>Couldn't load evidence: ${esc(e.message)}</p>`;
  });
  reveal(root);
  return {};
}

function table(rows, cols) {
  return `<div class="card reveal" style="overflow-x:auto;padding:.4rem .6rem"><table class="tbl"><thead><tr>${cols.map(([, h]) => `<th>${h}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${cols.map(([k, , f]) => `<td>${f ? f(r[k], r) : esc(r[k])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
const link = (u) => (u ? `<a href="${esc(u)}" target="_blank" rel="noopener">open ↗</a>` : "");

function waste(d) {
  return `<div class="grid g3" style="margin-bottom:1rem">
      <div class="tile reveal"><div class="k">Finest public breakdown</div><div class="v">National</div><div class="n">one figure a year from NEA</div></div>
      <div class="tile reveal" style="--d:.05s"><div class="k">Sources checked</div><div class="v">${d.waste_data_check.length}</div><div class="n">official, research and industry</div></div>
      <div class="tile reveal" style="--d:.1s"><div class="k">Best lead</div><div class="v">NParks</div><div class="n">tracks volumes from landscape contractors</div></div></div>
    <p class="reveal" style="margin:0 0 1rem;max-width:820px">No public dataset splits horticultural waste by area, collector or source, so BioTwin
      <b style="color:var(--text)">estimates</b> it from NParks tree records and satellite greenery (and labels it as an estimate).
      The national figures cross-check across sources. NParks and NEA hold the detailed records.</p>
    ${table(d.waste_data_check, [["source", "Source"], ["verdict", "Verdict"], ["granularity", "Detail"], ["what_it_has", "What it has"], ["url", "", link]])}`;
}

function sources(d) {
  const counts = d.parameters.reduce((m, p) => (m[p.tag] = (m[p.tag] || 0) + 1, m), {});
  return `<div class="grid g4" style="grid-template-columns:repeat(5,1fr);margin-bottom:1rem">${Object.entries(TAGS).map(([k, v], i) =>
      `<div class="tile reveal" style="--d:${i * 0.04}s;min-height:96px"><div class="k">${v}</div><div class="v">${counts[k] || 0}</div></div>`).join("")}</div>
    <div class="reveal" id="tagChips" style="margin-bottom:.8rem">${Object.entries(TAGS).map(([k, v]) =>
      `<button class="chip" data-tag="${k}" style="cursor:pointer" aria-pressed="true">${v}</button>`).join("")}</div>
    <div id="ptable">${paramTable(d.parameters)}</div>`;
}
const paramTable = (rows) => table(rows, [["key", "Parameter"], ["value", "Value", (v) => esc(v)], ["unit", "Unit"],
  ["tag", "Tag", (v) => esc(TAGS[v] || v)], ["source", "Source"], ["url", "", link]]);
function wireSources(body, d) {
  const on = new Set(Object.keys(TAGS));
  body.querySelectorAll("[data-tag]").forEach((b) => b.addEventListener("click", () => {
    const k = b.dataset.tag;
    on.has(k) ? on.delete(k) : on.add(k);
    b.style.opacity = on.has(k) ? 1 : 0.35;
    b.setAttribute("aria-pressed", on.has(k));
    body.querySelector("#ptable").innerHTML = paramTable(d.parameters.filter((p) => on.has(p.tag)));
    body.querySelectorAll("#ptable .reveal").forEach((e) => e.classList.add("in"));
  }));
}

function validation(d) {
  return `<p class="reveal" style="max-width:780px;margin-bottom:1rem">Upload independent 2025 tonnages by region or collection sector to measure how good the area
      estimates are. Never fill the template with model values.</p>
    <div class="grid g2"><div class="card reveal"><h4>1 · Choose how to compare</h4>
      <div style="margin:.6rem 0 1rem"><select id="unit" class="btn" style="padding:0 1rem">${Object.entries(d.units).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
      <button class="btn" id="tmpl">Download blank template</button>
      <h4 style="margin-top:1.4rem">2 · Upload completed CSV</h4>
      <input type="file" id="file" accept=".csv" style="margin-top:.6rem;color:var(--text-2)"></div>
      <div class="card reveal" id="vres"><h4>Result</h4><p class="muted" style="margin-top:.4rem">No records uploaded — the area estimates have not been validated.</p></div></div>`;
}
function wireValidation(body, d) {
  const unit = () => body.querySelector("#unit").value;
  body.querySelector("#tmpl").addEventListener("click", () => {
    const u = unit(), names = d.estimates[u].map((r) => r[u]);
    const lines = [[u, "year", "observed_t", "source", "record_type", "coverage_note"], ...names.map((n) => [n, 2025, "", "", "independent record", ""])];
    download(`validation_template_${u}.csv`, lines.map((l) => l.map(csvCell).join(",")).join("\n"));
  });
  body.querySelector("#file").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const box = body.querySelector("#vres");
    box.innerHTML = `<div class="skeleton" style="height:140px"></div>`;
    try {
      const r = await api.validate(unit(), f);
      box.innerHTML = `<h4>Result</h4><div class="grid g3" style="margin:.8rem 0">
        <div class="tile"><div class="k">Average error</div><div class="v">${fmt.pct(r.wape, 1)}</div></div>
        <div class="tile"><div class="k">Ranking agreement</div><div class="v">${r.rank_spearman == null ? "—" : r.rank_spearman.toFixed(2)}</div></div>
        <div class="tile"><div class="k">Share error</div><div class="v">${fmt.dec(r.share_mae_pp)} pts</div></div></div>
        <p class="muted">${r.compared} of ${Math.round(r.compared / r.coverage)} units compared.</p>`;
    } catch (err) {
      box.innerHTML = `<h4>Result</h4><p style="color:#ff6961;margin-top:.4rem">${esc(err.message)}</p>`;
      toast(err.message, "err");
    }
  });
}

function pdf(d) {
  return `<p class="reveal" style="max-width:780px;margin-bottom:1rem">The research PDF was checked against its own links. It is used only where nothing better was found online.</p>
    ${table(d.pdf_checks, [["topic", "Topic"], ["claim_in_research_pdf", "Claim"], ["status", "Status"], ["evidence_checked_16_nov_2026", "Evidence"], ["used_in_model_as", "Used as"]])}`;
}
