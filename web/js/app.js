// Router and boot.
import { api } from "./api.js";
import { disposeAll } from "./charts.js";
import { store } from "./store.js";
import { reduceMotion, toast } from "./ui.js";
import * as home from "./views/home.js";
import * as evaluate from "./views/evaluate.js";
import * as results from "./views/results.js";
import * as saved from "./views/saved.js";
import * as evidence from "./views/evidence.js";

const routes = { "": home, evaluate, results, saved, evidence };
const viewEl = document.getElementById("view");
let current = null;
const ctx = { meta: null, geo: null, store, go: (r) => { location.hash = `#/${r}`; } };

function routeName() { return location.hash.replace(/^#\/?/, "").split("?")[0]; }

function setNav(name) {
  document.querySelectorAll(".nav nav a").forEach((a) => a.classList.toggle("active", a.dataset.route === name));
  const n = store.state.saved.length;
  document.getElementById("savedCount").textContent = n ? String(n) : "";
}

function swap() {
  const name = routeName();
  const view = routes[name] || home;
  try { current?.destroy?.(); } catch (e) { console.warn(e); }
  disposeAll();
  viewEl.innerHTML = "";
  viewEl.className = reduceMotion ? "" : "view-enter";
  window.scrollTo(0, 0);
  try {
    current = view.mount(viewEl, ctx) || null;
  } catch (e) {
    console.error(e);
    viewEl.innerHTML = `<div class="page empty"><h2>Something went wrong on this page.</h2><p>${e.message}</p></div>`;
  }
  setNav(name);
  document.title = `${({ "": "Home", evaluate: "New evaluation", results: "Results", saved: "Saved", evidence: "Evidence" })[name] ?? "Home"} · BioTwin Singapore`;
}

function render() {
  if (document.startViewTransition && !reduceMotion) document.startViewTransition(swap);
  else swap();
}

window.addEventListener("error", (e) => toast(`Unexpected error: ${e.message}`, "err"));
window.addEventListener("unhandledrejection", (e) => toast(e.reason?.message || "Something went wrong", "err"));
store.subscribe(() => setNav(routeName()));

async function boot() {
  try {
    [ctx.meta, ctx.geo] = await Promise.all([api.meta(), api.geo()]);
  } catch (e) {
    document.getElementById("boot").classList.add("gone");
    viewEl.innerHTML = `<div class="page empty"><h2>Can't load BioTwin data</h2><p>${e.message}</p>
      <button class="btn primary" onclick="location.reload()">Try again</button></div>`;
    return;
  }
  window.addEventListener("hashchange", render);
  swap();
  setTimeout(() => document.getElementById("boot").classList.add("gone"), 150);
}
boot();
