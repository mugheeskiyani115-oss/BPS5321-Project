// New evaluation: step panel (location, plant, business inputs) + live 3D map.
import { api } from "../api.js";
import { BioMap } from "../map.js";
import { requestBody } from "../store.js";
import { countUp, esc, fmt, reduceMotion, segmented, sleep, toast } from "../ui.js";

const STEPS = ["Choosing the plot and plant size", "Routing trucks on the road network", "Costing staff, power and land",
  "Comparing with today's route", "Writing the findings"];

export function mount(root, { meta, geo, store, go }) {
  const inp = () => store.state.inputs;
  const median = (a) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor((s.length - 1) / 2)] : 0; };
  const cap = meta.gate_fee_cap_sgd;
  root.innerHTML = `
  <div class="workspace">
    <aside class="panel">
      <div class="panel-inner">
        <div class="eyebrow">New evaluation</div>
        <h2 class="title-m" style="margin:.25rem 0 .35rem">Where should the plant go?</h2>
        <p style="font-size:.88rem">Three steps. Defaults come from Notebook 2 and published sources.</p>

        <div class="step">
          <div class="step-h"><span class="n done">1</span><h3>Location</h3></div>
          <div id="region"></div>
          <div class="stats">
            <div class="stat"><div class="v" id="stWoody">—</div><div class="k">woody waste t/yr</div></div>
            <div class="stat"><div class="v" id="stPlots">—</div><div class="k">candidate plots</div></div>
            <div class="stat"><div class="v" id="stRent">—</div><div class="k">median land S$/m²</div></div>
          </div>
          <div id="mode"></div>
          <p class="muted" id="modeHint" style="margin-top:.6rem"></p>
          <div class="rows" id="plots"></div>
        </div>

        <div class="step">
          <div class="step-h"><span class="n done">2</span><h3>Plant</h3></div>
          <p class="step-sub">Bigger continuous plants need fewer staff per tonne. Small batch kilns earn about half the credit per tonne.</p>
          <div class="plants" id="plants"></div>
        </div>

        <div class="step">
          <div class="step-h"><span class="n done">3</span><h3>Business inputs</h3></div>
          <div class="field">
            <label for="gate">Gate fee you charge waste owners <b id="gateV" style="float:right;color:var(--text)"></b></label>
            <div class="range"><input id="gate" type="range" min="0" max="150" step="5" aria-label="Gate fee">
              <span class="mark" style="left:${(cap / 150) * 100}%"><span>incineration S$${cap.toFixed(0)}</span></span></div>
          </div>
          <div style="height:1.9rem"></div>
          <label class="switch"><input type="checkbox" id="credits"><span class="track"></span>
            <span><span style="color:var(--text)">Certify and sell carbon credits</span><br><span class="muted">Registry eligibility isn't established.</span></span></label>
          <details class="accordion" id="adv" style="margin-top:1rem">
            <summary>Advanced inputs <span class="chev">›</span></summary>
            <div class="acc-body"><div class="grid g2" id="advFields" style="gap:.75rem;margin:.4rem 0 .8rem"></div>
              <button class="link-btn" id="advReset">Reset to default values</button></div>
          </details>
        </div>
      </div>
      <div class="panel-foot runbox" id="runbox">
        <button class="btn primary lg block" id="run">Get results</button>
        <div class="prog"><i></i></div>
        <div class="msg" id="msg"></div>
      </div>
    </aside>
    <section class="mapwrap">
      <div class="map" id="map"></div>
      <div class="map-hud" id="hud"></div>
      <div class="map-legend">
        <div><i style="background:#8e8e93"></i>Candidate plots (click to choose)</div>
        <div><i style="background:#2997ff"></i>Your chosen plots</div>
        <div><i style="background:#199e70"></i>Today's incinerators &amp; biomass plant</div>
        <div><i style="background:linear-gradient(90deg,#104281,#86b6ef)"></i>Woody waste available</div>
      </div>
    </section>
  </div>`;

  const $ = (id) => root.querySelector(`#${id}`);
  const map = new BioMap($("map"), { meta, geo, intro: false, onSiteClick: (id) => onSite(id) });

  // ---- step 1: location -------------------------------------------------------------------------
  const regions = [{ value: "All", label: "All" }, ...meta.regions.map((r) => ({ value: r, label: r }))];
  segmented($("region"), regions, inp().region, (v) => { store.setInputs({ region: v, sites: inp().sites.filter((s) => site(s).region === v || v === "All") }); refresh(true); });
  const modeSeg = segmented($("mode"), [{ value: "auto", label: "Let the tool pick the best plot" }, { value: "manual", label: "Choose plots" }],
    inp().mode, (v) => { store.setInputs({ mode: v }); refresh(); }, { full: true });
  const site = (id) => meta.sites.find((s) => s.site_id === id);
  const regionSites = () => meta.sites.filter((s) => inp().region === "All" || s.region === inp().region);

  function onSite(id) {
    const s = site(id);
    if (!s) return;
    const patch = {};
    if (inp().region !== "All" && s.region !== inp().region) patch.region = s.region;
    if (inp().mode !== "manual") { patch.mode = "manual"; patch.sites = [id]; modeSeg.set("manual"); }
    else {
      const cur = inp().sites.filter((x) => (patch.region ? site(x).region === patch.region : true));
      patch.sites = cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
    }
    store.setInputs(patch);
    if (patch.region) { root.querySelector("#region").querySelector(`[data-v="${patch.region}"]`)?.click(); return; }
    refresh();
  }

  function renderPlots() {
    const manual = inp().mode === "manual";
    const box = $("plots");
    box.className = `rows${manual ? "" : " auto"}`;
    const list = regionSites();
    $("modeHint").textContent = manual
      ? `${inp().sites.length || "No"} plot${inp().sites.length === 1 ? "" : "s"} chosen. Several plots = several plants of the same size.`
      : `The tool will test all ${list.length} plots ${inp().region === "All" ? "across Singapore" : `in ${inp().region}`} and pick the cheapest for your plant.`;
    box.innerHTML = list.map((s) => `
      <button type="button" class="row${inp().sites.includes(s.site_id) && manual ? " on" : ""}" data-id="${s.site_id}" ${manual ? "" : 'tabindex="-1"'}>
        <span class="box"></span>
        <span><span class="nm">${esc(s.name)}</span><br><span class="rg">${esc(s.site_id)} · ${esc(s.region)}</span></span>
        <span class="rent">S$${s.rent.toFixed(2)}/m²</span>
      </button>`).join("");
    box.querySelectorAll(".row").forEach((r) => {
      r.addEventListener("mouseenter", () => map.setHover(r.dataset.id));
      r.addEventListener("mouseleave", () => map.setHover(null));
      r.addEventListener("click", () => { if (inp().mode === "manual") onSite(r.dataset.id); });
    });
  }

  function renderStats() {
    const r = inp().region;
    const areas = meta.areas.filter((a) => r === "All" || a.region === r);
    const sites = regionSites();
    countUp($("stWoody"), areas.reduce((s, a) => s + a.woody_available_t, 0));
    countUp($("stPlots"), sites.length);
    countUp($("stRent"), median(sites.map((s) => s.rent)), (v) => fmt.dec(v, 1));
    $("hud").innerHTML = `<h4>${r === "All" ? "All of Singapore" : `${esc(r)} region`}</h4>
      <p>${areas.length} planning areas · ${sites.length} candidate plots</p>
      <p class="muted" style="margin-top:.2rem">${inp().mode === "manual" ? "Click columns to add or remove plots" : "Click any column to choose it yourself"}</p>`;
  }

  // ---- step 2: plant ----------------------------------------------------------------------------
  function renderPlants() {
    const cards = [{ size_class: null, label: "Let the tool size it", auto: true }, ...meta.plants];
    $("plants").innerHTML = cards.map((p) => p.auto
      ? `<button type="button" class="plant auto${inp().size == null ? " on" : ""}" data-size=""><div class="t">Let the tool size it</div>
          <div class="m">Tests all six sizes and keeps the lowest net cost per tonne.</div></button>`
      : `<button type="button" class="plant${inp().size === p.size_class ? " on" : ""}" data-size="${p.size_class}">
          <div class="t">${esc(p.label)}</div>
          <div class="m">${fmt.int(p.annual_t)} t/yr · build ${fmt.money(p.capex_sgd)}<br>${Math.round(p.staff)} staff · ~${fmt.money(p.cost_sgd_per_t)}/t</div>
          ${p.carbon_class === "small" ? '<span class="badge-s">½ credit per tonne</span>' : ""}</button>`).join("");
    $("plants").querySelectorAll(".plant").forEach((b) => b.addEventListener("click", () => {
      store.setInputs({ size: b.dataset.size || null });
      $("plants").querySelectorAll(".plant").forEach((x) => x.classList.toggle("on", x === b));
    }));
  }

  // ---- step 3: inputs ---------------------------------------------------------------------------
  const gate = $("gate");
  const paintGate = () => {
    gate.style.setProperty("--p", `${(gate.value / 150) * 100}%`);
    $("gateV").textContent = `S$${Number(gate.value).toFixed(0)}/t`;
  };
  gate.value = inp().gate_fee;
  paintGate();
  gate.addEventListener("input", () => { paintGate(); store.setInputs({ gate_fee: Number(gate.value) }); });
  $("credits").checked = !!inp().sell_credits;
  $("credits").addEventListener("change", (e) => store.setInputs({ sell_credits: e.target.checked }));

  function renderAdvanced() {
    const adv = meta.advanced, cur = inp().advanced || {};
    $("advFields").innerHTML = Object.entries(adv).map(([k, d]) => {
      const v = cur[k] ?? d.default;
      return `<div class="field"><label for="adv_${k}" title="${esc(d.source)}">${esc(d.label)} <span class="muted">(${esc(d.unit)})</span></label>
        <input type="number" id="adv_${k}" data-k="${k}" min="${d.min}" max="${d.max}" step="${d.step}" value="${v}" class="${k in cur ? "changed" : ""}"></div>`;
    }).join("");
    $("advFields").querySelectorAll("input").forEach((el) => el.addEventListener("change", () => {
      const k = el.dataset.k, d = adv[k];
      let v = Number(el.value);
      if (!isFinite(v)) v = d.default;
      v = Math.min(d.max, Math.max(d.min, v));
      el.value = v;
      const next = { ...(inp().advanced || {}) };
      if (Math.abs(v - d.default) < 1e-12) delete next[k]; else next[k] = v;
      el.classList.toggle("changed", k in next);
      store.setInputs({ advanced: next });
    }));
  }
  $("advReset").addEventListener("click", () => { store.setInputs({ advanced: {} }); renderAdvanced(); toast("Advanced inputs reset"); });
  if (Object.keys(inp().advanced || {}).length) $("adv").open = true;

  // ---- run --------------------------------------------------------------------------------------
  const runBtn = $("run");
  function canRun() {
    const ok = inp().mode === "auto" || inp().sites.length > 0;
    runBtn.disabled = !ok;
    $("msg").textContent = ok ? "" : "Choose at least one plot, or let the tool pick.";
  }
  runBtn.addEventListener("click", async () => {
    const box = $("runbox"), bar = box.querySelector(".prog i");
    box.classList.add("busy");
    runBtn.disabled = true;
    runBtn.textContent = "Evaluating…";
    let step = 0;
    const tick = () => { $("msg").textContent = STEPS[Math.min(step, STEPS.length - 1)]; bar.style.width = `${Math.min(92, (step + 1) * 18)}%`; step++; };
    tick();
    const timer = setInterval(tick, 260);
    try {
      const [res] = await Promise.all([api.evaluate(requestBody(inp())), sleep(reduceMotion ? 0 : 1100)]);
      clearInterval(timer);
      bar.style.width = "100%";
      $("msg").textContent = "Done";
      store.setResult(res);
      await sleep(reduceMotion ? 0 : 220);
      go("results");
    } catch (e) {
      clearInterval(timer);
      box.classList.remove("busy");
      bar.style.width = "0";
      runBtn.textContent = "Get results";
      canRun();
      toast(e.message, "err");
    }
  });

  function refresh(fly = false) {
    renderPlots();
    renderStats();
    map.setSelection({ mode: inp().mode, selected: inp().mode === "manual" ? inp().sites : [] });
    if (fly) map.setRegion(inp().region, true);
    canRun();
  }
  renderPlants();
  renderAdvanced();
  refresh();
  map.setRegion(inp().region, true);
  return { destroy: () => map.destroy() };
}
