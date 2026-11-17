// Animated 3D map: MapLibre (OpenStreetMap basemap) + deck.gl layers.
import { esc, fmt, reduceMotion } from "./ui.js";

const BASEMAP = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const SG_BOUNDS = [[103.6, 1.215], [104.03, 1.475]];
const SEQ = [[16, 66, 129], [24, 79, 149], [28, 92, 171], [37, 106, 191], [42, 120, 214], [57, 135, 229],
  [85, 152, 231], [134, 182, 239], [183, 211, 246]];
const ACCENT = [41, 151, 255], ORANGE = [217, 89, 38], AQUA = [25, 158, 112], GREY = [142, 142, 147], DIM = [40, 40, 43];
const easeOut = (t) => 1 - Math.pow(1 - t, 3);
const easeSpring = (t) => { const c4 = (2 * Math.PI) / 3; return t === 0 ? 0 : t === 1 ? 1 : Math.pow(2, -9 * t) * Math.sin((t * 10 - 0.75) * c4) + 1; };

function ramp(v, vmax, a = 225) {
  const x = vmax > 0 ? Math.min(Math.max(v / vmax, 0), 1) * (SEQ.length - 1) : 0;
  const i = Math.min(Math.floor(x), SEQ.length - 2), f = x - i;
  return [0, 1, 2].map((k) => Math.round(SEQ[i][k] + (SEQ[i + 1][k] - SEQ[i][k]) * f)).concat(a);
}

function webglOK() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch { return false; }
}

const metres = (a, b) => {
  const dx = (b[0] - a[0]) * 111320 * Math.cos(((a[1] + b[1]) / 2) * Math.PI / 180), dy = (b[1] - a[1]) * 110540;
  return Math.hypot(dx, dy);
};

export class BioMap {
  constructor(el, { meta, geo, onSiteClick = () => {}, intro = true } = {}) {
    this.el = el; this.meta = meta; this.geo = geo; this.onSiteClick = onSiteClick;
    this.s = { region: "All", mode: "auto", selected: [], hover: null, result: null, best: null };
    this.t = 0; this.last = 0; this.alive = true; this.loaded = false;
    this.supply = Object.fromEntries(meta.areas.map((a) => [a.planning_area, a.woody_available_t]));
    this.regionOf = Object.fromEntries(meta.areas.map((a) => [a.planning_area, a.region]));
    this.vmax = Math.max(...Object.values(this.supply));
    this.tip = document.getElementById("maptip");
    if (!window.maplibregl || !window.deck || !webglOK()) {
      el.innerHTML = `<div class="nomap">The 3D map needs WebGL, which this browser has turned off.<br>
        Everything else still works — choose plots from the list.</div>`;
      this.ok = false;
      return;
    }
    this.ok = true;
    this.map = new maplibregl.Map({
      container: el, style: BASEMAP, center: [103.82, 1.34], zoom: intro && !reduceMotion ? 9.4 : 10.2,
      pitch: intro && !reduceMotion ? 20 : 50, bearing: intro && !reduceMotion ? -40 : -12, maxPitch: 70,
      attributionControl: { compact: true }, fadeDuration: 0,
    });
    this.map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    this.overlay = new deck.MapboxOverlay({
      interleaved: false, layers: [],
      onClick: (info) => { if (info.layer?.id === "sites" && info.object) this.onSiteClick(info.object.site_id); },
      onHover: (info) => this._hover(info),
      getCursor: ({ isHovering }) => (isHovering ? "pointer" : "grab"),
    });
    this.map.addControl(this.overlay);
    this.map.on("load", () => {
      this.loaded = true;
      this.render();
      if (intro && !reduceMotion) this.map.easeTo({ zoom: 10.2, pitch: 50, bearing: -12, duration: 2200, easing: easeOut });
    });
    this.map.on("error", () => {});   // basemap hiccups shouldn't break the app
    this._loop = this._loop.bind(this);
    this.raf = requestAnimationFrame(this._loop);
  }

  // ---- public API ------------------------------------------------------------------------------
  setRegion(region, animate = true) {
    if (!this.ok) return;
    this.s.region = region;
    this._fit(this._regionBounds(region), animate);
    this.render();
  }
  setSelection({ mode, selected, best }) {
    this.s.mode = mode; this.s.selected = selected || []; this.s.best = best || null;
    this.render();
  }
  setHover(siteId) { this.s.hover = siteId; this.render(); }
  showResult(res) {
    if (!this.ok) return;
    this.s.result = res;
    this.s.selected = res.layout.map((l) => l.site_id);
    this.trips = this._trips(res);
    const pts = res.flows.flatMap((f) => [f.from, f.to]);
    if (pts.length) {
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      this._fit([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], true);
    }
    this.render();
  }
  resize() { this.map?.resize(); }
  destroy() {
    this.alive = false;
    cancelAnimationFrame(this.raf);
    this.tip?.classList.remove("show");
    try { this.map?.remove(); } catch { /* already gone */ }
  }

  // ---- internals --------------------------------------------------------------------------------
  _regionBounds(region) {
    if (region === "All") return SG_BOUNDS;
    const pts = this.meta.areas.filter((a) => a.region === region).map((a) => [a.lon, a.lat])
      .concat(this.meta.sites.filter((s) => s.region === region).map((s) => [s.longitude, s.latitude]));
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    return [[Math.min(...xs) - 0.02, Math.min(...ys) - 0.02], [Math.max(...xs) + 0.02, Math.max(...ys) + 0.02]];
  }
  _fit(bounds, animate) {
    if (!this.map) return;
    const opts = { padding: { top: 70, bottom: 70, left: 70, right: 70 }, pitch: 50, bearing: -12, maxZoom: 12.2 };
    if (!animate || reduceMotion) this.map.fitBounds(bounds, { ...opts, duration: 0 });
    else this.map.fitBounds(bounds, { ...opts, duration: 1500, easing: easeOut, essential: true });
  }
  _trips(res) {
    const flows = res.flows.filter((f) => f.tonnes > 0.5);
    if (!flows.length) return [];
    const maxT = Math.max(...flows.map((f) => f.tonnes));
    const paths = flows.map((f) => {
      const p = f.path && f.path.length > 1 ? f.path : [f.from, [(f.from[0] + f.to[0]) / 2, (f.from[1] + f.to[1]) / 2], f.to];
      const cum = [0];
      for (let i = 1; i < p.length; i++) cum.push(cum[i - 1] + metres(p[i - 1], p[i]));
      return { f, p, cum, len: cum[cum.length - 1] || 1 };
    });
    const maxLen = Math.max(...paths.map((x) => x.len));
    this.loopLen = 2600;
    const trips = [];
    paths.forEach(({ f, p, cum }) => {
      const n = 1 + Math.round(3 * f.tonnes / maxT);
      for (let k = 0; k < n; k++) {
        const offset = (k * this.loopLen) / n + (f.tonnes * 7) % 300;
        trips.push({ path: p, timestamps: cum.map((d) => offset + (d / maxLen) * 1500), road: !!f.path });
      }
    });
    this.routes = paths.map(({ p, f }) => ({ path: p, road: !!f.path, t: f.tonnes }));
    return trips;
  }
  _siteState(s) {
    const built = this.s.result && this.s.result.layout.some((l) => l.site_id === s.site_id);
    if (built) return "built";
    if (this.s.selected.includes(s.site_id)) return "selected";
    if (this.s.hover === s.site_id) return "hover";
    if (this.s.region !== "All" && s.region !== this.s.region) return "other";
    return "available";
  }
  layers() {
    const r = this.s.result, region = this.s.region;
    const sent = r ? Object.fromEntries(Object.entries(r.flows.reduce((m, f) => (m[f.origin] = (m[f.origin] || 0) + f.tonnes, m), {}))) : null;
    const sentMax = sent ? Math.max(1, ...Object.values(sent)) : 1;
    const key = `${region}|${r ? r.metrics.processed_t + r.layout.map((l) => l.site_id).join() : ""}`;
    const areaVal = (f) => {
      const pa = f.properties.planning_area;
      if (sent) return { v: sent[pa] || 0, max: sentMax, inside: !!sent[pa] };
      const inside = region === "All" || this.regionOf[pa] === region;
      return { v: this.supply[pa] || 0, max: this.vmax, inside };
    };
    const layers = [
      new deck.GeoJsonLayer({
        id: "areas", data: this.geo, extruded: !r, pickable: true, opacity: r ? 0.6 : 0.82,
        getFillColor: (f) => { const a = areaVal(f); return a.inside ? ramp(a.v, a.max) : [...DIM, 210]; },
        getElevation: (f) => { const a = areaVal(f); return a.inside ? 80 + (a.v / a.max) * 1200 : 25; },
        getLineColor: [255, 255, 255, 30],
        updateTriggers: { getFillColor: key, getElevation: key },
        transitions: reduceMotion ? {} : { getElevation: { duration: 900, easing: easeOut }, getFillColor: { duration: 650 } },
      }),
    ];
    if (r && this.routes) {
      layers.push(new deck.PathLayer({
        id: "routes", data: this.routes, getPath: (d) => d.path, parameters: { depthTest: false },
        getColor: (d) => (d.road ? [255, 255, 255, 46] : [255, 255, 255, 26]),
        getWidth: (d) => 1 + 3 * Math.sqrt(d.t / Math.max(...this.routes.map((x) => x.t))), widthUnits: "pixels",
        jointRounded: true, capRounded: true,
      }));
      if (!reduceMotion && this.trips?.length) {
        layers.push(new deck.TripsLayer({
          id: "trucks", data: this.trips, getPath: (d) => d.path, getTimestamps: (d) => d.timestamps,
          getColor: [236, 242, 255], widthMinPixels: 3.5, trailLength: 220, currentTime: this.t, fadeTrail: true,
          parameters: { depthTest: false },
          jointRounded: true, capRounded: true,
        }));
      }
    }
    const stateH = { built: 3800, selected: 2700, hover: 2300, available: 1500, other: 380 };
    const stateC = { built: [...ORANGE, 255], selected: [...ACCENT, 255], hover: [190, 190, 196, 255], available: [...GREY, 235], other: [70, 70, 74, 150] };
    layers.push(new deck.ColumnLayer({
      id: "sites", data: this.meta.sites, getPosition: (s) => [s.longitude, s.latitude], radius: 430, extruded: true,
      pickable: true, diskResolution: 24,
      getElevation: (s) => stateH[this._siteState(s)], getFillColor: (s) => stateC[this._siteState(s)],
      updateTriggers: { getElevation: [this.s.selected.join(), this.s.hover, region, key], getFillColor: [this.s.selected.join(), this.s.hover, region, key] },
      transitions: reduceMotion ? {} : { getElevation: { duration: 700, easing: easeSpring }, getFillColor: { duration: 300 } },
    }));
    if (this.meta.facilities?.length) {
      layers.push(new deck.ColumnLayer({
        id: "facilities", data: this.meta.facilities, getPosition: (f) => [f.longitude, f.latitude], radius: 240,
        getElevation: 1900, getFillColor: [...AQUA, 230], extruded: true, pickable: true,
      }));
    }
    const pulseSites = this.meta.sites.filter((s) => ["built", "selected"].includes(this._siteState(s)));
    if (pulseSites.length && !reduceMotion) {
      const ph = (this.t % 900) / 900;
      layers.push(new deck.ScatterplotLayer({
        id: "pulse", data: pulseSites, getPosition: (s) => [s.longitude, s.latitude, 40], stroked: true, filled: false,
        parameters: { depthTest: false },
        getRadius: 450 + 1500 * ph, getLineColor: (s) => [...(this._siteState(s) === "built" ? ORANGE : ACCENT), Math.round(220 * (1 - ph))],
        lineWidthMinPixels: 2, updateTriggers: { getRadius: ph, getLineColor: ph },
      }));
    }
    return layers;
  }
  render() { if (this.ok && this.loaded && this.alive) this.overlay.setProps({ layers: this.layers() }); }
  _loop(now) {
    if (!this.alive) return;
    const dt = this.last ? Math.min(now - this.last, 64) : 16;
    this.last = now;
    const animating = !reduceMotion && (this.s.result || this.s.selected.length);
    if (animating) {
      this.t = (this.t + dt * 0.55) % (this.loopLen || 2600);
      this.render();
    }
    this.raf = requestAnimationFrame(this._loop);
  }
  _hover(info) {
    if (!this.tip) return;
    const o = info.object;
    if (!o) { this.tip.classList.remove("show"); if (this.s.hover && info.layer?.id !== "sites") { /* keep */ } return; }
    let html = "";
    if (info.layer.id === "sites") {
      html = `<b>${esc(o.name)}</b><span>${esc(o.region)} · land S$${o.rent.toFixed(2)}/m²/yr</span>`;
      const l = this.s.result?.layout.find((x) => x.site_id === o.site_id);
      if (l) html += `<br><span>${esc(l.label)} · ${fmt.int(l.throughput_t)} t/yr</span>`;
      else html += `<br><span>Click to ${this.s.selected.includes(o.site_id) ? "remove" : "choose"} this plot</span>`;
    } else if (info.layer.id === "areas") {
      const pa = o.properties.planning_area;
      const r = this.s.result;
      const v = r ? r.flows.filter((f) => f.origin === pa).reduce((s, f) => s + f.tonnes, 0) : this.supply[pa];
      html = `<b>${esc(pa.charAt(0) + pa.slice(1).toLowerCase())}</b><span>${fmt.int(v)} t/yr ${r ? "to your plant" : "woody waste available"}</span>`;
    } else if (info.layer.id === "facilities") {
      html = `<b>${esc(o.name)}</b><span>${esc(o.facility_type)} · today's destination</span>`;
    } else return;
    const box = this.el.getBoundingClientRect();
    this.tip.innerHTML = html;
    this.tip.style.left = `${box.left + info.x + 14}px`;
    this.tip.style.top = `${box.top + info.y + 14}px`;
    this.tip.classList.add("show");
  }
}
