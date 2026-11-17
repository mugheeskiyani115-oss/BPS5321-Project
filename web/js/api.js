// Thin fetch wrapper with timeouts and readable errors.

async function request(url, opts = {}, timeoutMs = 30000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...opts, signal: ctrl.signal });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const d = body.detail;
      const msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg).join("; ") : `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return body;
  } catch (e) {
    if (e.name === "AbortError") throw new Error("The server took too long to answer. Please try again.");
    if (e instanceof TypeError) throw new Error("Can't reach the BioTwin server. Is it running?");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  meta: () => request("api/meta"),
  geo: () => request("api/geo"),
  evidence: () => request("api/evidence"),
  evaluate: (inputs) => request("api/evaluate", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(inputs),
  }),
  validate: (unit, file) => {
    const fd = new FormData();
    fd.append("unit", unit);
    fd.append("file", file);
    return request("api/validate", { method: "POST", body: fd });
  },
};
