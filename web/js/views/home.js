// Home: what the tool does, how an evaluation works, what you get.
import { esc, fmt, reveal, countUp } from "../ui.js";

export function mount(root, { meta, store, go }) {
  const n = meta.national;
  const last = store.state.result;
  root.innerHTML = `
  <section class="hero">
    <div class="glow"></div>
    <div class="eyebrow reveal">BioTwin Singapore</div>
    <h1 class="title-xl reveal" style="--d:.05s"><span class="grad">Evaluate a biochar plant,<br>anywhere in Singapore.</span></h1>
    <p class="lead reveal" style="--d:.12s">Choose a region and a plant. BioTwin estimates the tree trimmings it can collect,
      routes the trucks on real roads, costs the plant with Singapore wages and land rents, and shows whether it pays —
      and what it does for the climate compared with today.</p>
    <div class="cta reveal" style="--d:.2s">
      <button class="btn primary lg" data-go="evaluate">Start a new evaluation</button>
      ${last ? `<button class="btn lg" data-go="results">Open last result</button>` : `<button class="btn lg" data-go="evidence">See the evidence</button>`}
    </div>
  </section>
  <div class="page" style="padding-top:0">
    <div class="grid g4">
      ${[["Horticultural waste, 2025", n.waste_2025_t, "t", "NEA, national total"],
         ["Woody share", n.woody_share * 100, "%", "Notebook 2"],
         ["Candidate plots", meta.sites.length, "", "industrial zoning, URA 2019"],
         ["Plant sizes", meta.plants.length, "", "2 to 100 t/day"]].map(([k, v, u, note], i) =>
        `<div class="tile reveal" style="--d:${i * 0.06}s"><div class="k">${k}</div><div class="v" data-count="${v}" data-unit="${u}">0</div><div class="n">${note}</div></div>`).join("")}
    </div>

    <section class="section">
      <div class="section-head reveal"><div><h2 class="title-m">How an evaluation works</h2>
        <p>The same flow as a feasibility study: inputs, then results you can defend.</p></div></div>
      <div class="grid g4">
        ${[["Choose a location", "Pick a region. Let the tool find the cheapest plot, or click plots on the 3D map."],
           ["Choose a plant", "From a 2 t/day batch kiln to a 100 t/day continuous line — or let the tool size it."],
           ["Business inputs", "The gate fee you'd charge and whether to sell carbon credits. Everything else is pre-filled."],
           ["Get results", "Output, a 15-year cash flow, today vs your plant, numbered findings and comparisons."]]
          .map(([t, d], i) => `<div class="card hover reveal" style="--d:${i * 0.08}s"><div class="num">Step ${i + 1}</div><h4>${t}</h4><p>${d}</p></div>`).join("")}
      </div>
      <div class="flowline reveal" style="margin-top:1.6rem"></div>
    </section>

    <section class="section">
      <div class="section-head reveal"><div><h2 class="title-m">Built on public data</h2>
        <p>Every number is sourced, calculated, or labelled as an assumption — see Evidence.</p></div></div>
      <div class="reveal">${["NEA waste statistics", "NParks tree records", "ESA WorldCover", "URA Master Plan 2019",
        "OpenStreetMap roads", "MOM wages 2025", "JTC land rents 2026", "SP Group tariff", "MAS inflation outlook",
        "Senken credit prices", "Notebook 2 carbon model"].map((c) => `<span class="chip">${esc(c)}</span>`).join("")}</div>
    </section>
  </div>
  <footer class="foot">Results are indicative — not a design for procurement. Fingerprint ${esc(meta.fingerprint)}.</footer>`;
  root.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => go(b.dataset.go)));
  root.querySelectorAll("[data-count]").forEach((el) => {
    const v = parseFloat(el.dataset.count), u = el.dataset.unit;
    const f = (x) => fmt.int(x) + (u === "%" ? "%" : u ? ` ${u}` : "");
    el.textContent = f(v);
    el.closest(".reveal").addEventListener("revealed", () => { el.dataset.v = "0"; countUp(el, v, f); }, { once: true });
  });
  reveal(root);
  return {};
}
