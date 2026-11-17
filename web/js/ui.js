// Small UI helpers: formatting, escaping, count-up numbers, reveal-on-scroll, toasts, segmented controls.

export const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const MINUS = "−";
export const fmt = {
  int: (v) => (v == null || !isFinite(v) ? "—" : (v < 0 ? MINUS : "") + Math.abs(Math.round(v)).toLocaleString("en-SG")),
  dec: (v, d = 1) => (v == null || !isFinite(v) ? "—" : (v < 0 ? MINUS : "") +
    Math.abs(v).toLocaleString("en-SG", { minimumFractionDigits: d, maximumFractionDigits: d })),
  money: (v, unit = "") => {
    if (v == null || !isFinite(v)) return "—";
    const a = Math.abs(v), s = v < 0 ? MINUS : "";
    const body = a >= 1e6 ? (a / 1e6).toLocaleString("en-SG", { maximumFractionDigits: 2, minimumFractionDigits: a >= 1e8 ? 0 : 1 }) + "M"
      : a >= 1e4 ? Math.round(a / 1e3).toLocaleString("en-SG") + "k" : Math.round(a).toLocaleString("en-SG");
    return `${s}S$${body}${unit}`;
  },
  signed: (v, d = 0) => (v == null || !isFinite(v) ? "—" : (v > 0 ? "+" : v < 0 ? MINUS : "") +
    Math.abs(v).toLocaleString("en-SG", { minimumFractionDigits: d, maximumFractionDigits: d })),
  pct: (v, d = 0) => (v == null || !isFinite(v) ? "—" : `${(v * 100).toFixed(d)}%`),
};

// Animate a number into an element. `format` turns a number into display text.
export function countUp(el, to, format = fmt.int, dur = 1100) {
  if (!el) return;
  const from = parseFloat(el.dataset.v || "0");
  el.dataset.v = String(to);
  if (reduceMotion || !isFinite(to) || from === to) { el.textContent = format(to); return; }
  const t0 = performance.now();
  const tick = (t) => {
    const p = Math.min((t - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3);
    el.textContent = format(from + (to - from) * e);
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// Fade/slide elements with .reveal into view as they scroll in.
let io = null;
export function reveal(root = document) {
  if (reduceMotion || !("IntersectionObserver" in window)) {
    root.querySelectorAll(".reveal").forEach((e) => e.classList.add("in"));
    return;
  }
  io = io || new IntersectionObserver((entries) => entries.forEach((en) => {
    if (en.isIntersecting) {
      en.target.classList.add("in");
      en.target.dispatchEvent(new CustomEvent("revealed"));
      io.unobserve(en.target);
    }
  }), { threshold: 0, rootMargin: "0px 0px -6% 0px" });   // any part in view (tall tables never reach a % threshold)
  root.querySelectorAll(".reveal:not(.in)").forEach((e) => io.observe(e));
}

export function toast(msg, kind = "") {
  const box = document.getElementById("toasts");
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 320); }, kind === "err" ? 5200 : 2800);
}

// Segmented control with a sliding indicator. options: [{value, label}]
export function segmented(container, options, value, onChange, { full = false } = {}) {
  container.className = `seg${full ? " full" : ""}`;
  container.setAttribute("role", "radiogroup");
  container.innerHTML = `<span class="ind"></span>` + options.map((o) =>
    `<button type="button" role="radio" data-v="${esc(o.value)}">${esc(o.label)}</button>`).join("");
  const ind = container.querySelector(".ind");
  const set = (v, animate = true) => {
    container.querySelectorAll("button").forEach((b) => {
      const on = b.dataset.v === String(v);
      b.classList.toggle("on", on);
      b.setAttribute("aria-checked", on);
      if (on) {
        if (!animate) ind.style.transition = "none";
        ind.style.left = `${b.offsetLeft}px`;
        ind.style.width = `${b.offsetWidth}px`;
        if (!animate) requestAnimationFrame(() => (ind.style.transition = ""));
      }
    });
  };
  container.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    set(b.dataset.v);
    onChange(b.dataset.v);
  });
  requestAnimationFrame(() => set(value, false));
  window.addEventListener("resize", () => set(container.querySelector("button.on")?.dataset.v ?? value, false));
  return { set };
}

// Tabs with a sliding underline. Returns setter.
export function tabs(container, options, value, onChange) {
  container.className = "tabs";
  container.innerHTML = options.map((o) => `<button type="button" data-v="${esc(o.value)}">${esc(o.label)}</button>`).join("")
    + `<span class="ul"></span>`;
  const ul = container.querySelector(".ul");
  const set = (v) => container.querySelectorAll("button").forEach((b) => {
    const on = b.dataset.v === v;
    b.classList.toggle("on", on);
    if (on) { ul.style.left = `${b.offsetLeft}px`; ul.style.width = `${b.offsetWidth}px`; }
  });
  container.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) { set(b.dataset.v); onChange(b.dataset.v); }
  });
  requestAnimationFrame(() => set(value));
  return { set };
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function download(name, text, type = "text/csv") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const csvCell = (v) => {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
