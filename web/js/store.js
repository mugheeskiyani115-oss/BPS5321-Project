// App state: evaluation inputs, the latest result and saved evaluations (kept in this browser only).

const KEY = "biotwin.v2";
const listeners = new Set();

const defaults = () => ({
  inputs: { region: "All", feedstock_basis: "vegetation_proxy", mode: "auto", sites: [], size: null, gate_fee: 0, sell_credits: false, advanced: {} },
  result: null,
  saved: [],
});

function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "null");
    if (!raw) return defaults();
    const d = defaults();
    return { inputs: { ...d.inputs, ...(raw.inputs || {}) }, result: raw.result || null,
             saved: Array.isArray(raw.saved) ? raw.saved : [] };
  } catch {
    return defaults();
  }
}

export const store = {
  state: load(),
  persist() {
    try {
      localStorage.setItem(KEY, JSON.stringify(this.state));
    } catch {
      // storage full or blocked: keep working in memory
      try { localStorage.setItem(KEY, JSON.stringify({ ...this.state, result: null })); } catch { /* ignore */ }
    }
  },
  setInputs(patch) {
    this.state.inputs = { ...this.state.inputs, ...patch };
    this.persist();
    listeners.forEach((f) => f(this.state));
  },
  setResult(r) { this.state.result = r; this.persist(); listeners.forEach((f) => f(this.state)); },
  save(name) {
    if (!this.state.result) return;
    this.state.saved = [...this.state.saved, { id: Date.now(), name, time: new Date().toLocaleString("en-SG",
      { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }), result: this.state.result }].slice(-20);
    this.persist();
    listeners.forEach((f) => f(this.state));
  },
  remove(id) { this.state.saved = this.state.saved.filter((s) => s.id !== id); this.persist(); listeners.forEach((f) => f(this.state)); },
  subscribe(f) { listeners.add(f); return () => listeners.delete(f); },
};

// Request body for /api/evaluate from the current inputs.
export function requestBody(inputs) {
  return {
    region: inputs.region,
    feedstock_basis: inputs.feedstock_basis || "vegetation_proxy",
    sites: inputs.mode === "manual" ? inputs.sites : [],
    size: inputs.size,
    gate_fee: Number(inputs.gate_fee) || 0,
    sell_credits: !!inputs.sell_credits,
    advanced: inputs.advanced || {},
  };
}
