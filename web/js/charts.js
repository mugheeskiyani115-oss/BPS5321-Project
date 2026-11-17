// ECharts helpers: dark, quiet axes, staggered entrance animations.
import { fmt, reduceMotion } from "./ui.js";

const C = { blue: "#3987e5", orange: "#d95926", aqua: "#199e70", grey: "#636366", text2: "#a1a1a6", text3: "#6e6e73",
  grid: "#232325", axis: "#38383a", tip: "#1d1d1f" };
const charts = new Set();
window.addEventListener("resize", () => charts.forEach((c) => c.resize()));

function base() {
  return {
    backgroundColor: "transparent",
    textStyle: { fontFamily: "Inter, -apple-system, sans-serif", color: C.text2 },
    animation: !reduceMotion, animationDuration: 900, animationEasing: "cubicOut",
    animationDurationUpdate: 700, animationEasingUpdate: "cubicInOut",
    tooltip: { trigger: "axis", backgroundColor: C.tip, borderColor: "rgba(255,255,255,.08)", textStyle: { color: "#f5f5f7", fontSize: 12 },
      axisPointer: { type: "shadow", shadowStyle: { color: "rgba(255,255,255,.04)" } } },
    legend: { top: 0, left: 0, textStyle: { color: C.text2 }, icon: "roundRect", itemWidth: 10, itemHeight: 10 },
    grid: { left: 8, right: 16, top: 40, bottom: 8, containLabel: true },
  };
}
const axis = (extra = {}) => ({ axisLine: { lineStyle: { color: C.axis } }, axisTick: { show: false },
  axisLabel: { color: C.text3 }, splitLine: { lineStyle: { color: C.grid } }, ...extra });

export function mount(el) {
  const existing = echarts.getInstanceByDom(el);
  if (existing) return existing;
  const c = echarts.init(el, null, { renderer: "canvas" });
  charts.add(c);
  return c;
}
export function disposeAll() { charts.forEach((c) => c.dispose()); charts.clear(); }

// Cash flow: income (+) and costs (−) stacked per year, cumulative line.
export function cashflow(el, years) {
  const c = mount(el);
  const x = years.map((y) => String(y.calendar_year));
  const income = years.map((y) => y.biochar_sales_sgd + y.gate_fees_sgd + y.credit_sales_sgd);
  const running = years.map((y) => -(y.staff_sgd + y.maintenance_sgd + y.land_sgd + y.electricity_sgd + y.trucking_sgd + y.certification_sgd));
  const capital = years.map((y) => -y.capital_sgd);
  const money = (v) => fmt.money(v);
  c.setOption({
    ...base(),
    tooltip: { ...base().tooltip, valueFormatter: money },
    xAxis: { type: "category", data: x, ...axis({ splitLine: { show: false } }) },
    yAxis: { type: "value", ...axis({ axisLabel: { color: C.text3, formatter: (v) => fmt.money(v) } }) },
    series: [
      { name: "Income", type: "bar", stack: "cf", data: income, itemStyle: { color: C.aqua, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 28,
        animationDelay: (i) => i * 45 },
      { name: "Running costs", type: "bar", stack: "cf", data: running, itemStyle: { color: C.orange, borderRadius: [0, 0, 4, 4] },
        animationDelay: (i) => i * 45 + 120 },
      { name: "Building the plant", type: "bar", stack: "cf", data: capital, itemStyle: { color: C.grey, borderRadius: [0, 0, 4, 4] } },
      { name: "Cumulative", type: "line", data: years.map((y) => y.cumulative_sgd), smooth: 0.25, symbol: "circle", symbolSize: 6,
        lineStyle: { color: C.blue, width: 2.5 }, itemStyle: { color: C.blue }, z: 5, animationDuration: 1600 },
    ],
  }, true);
  return c;
}

// Each operating year: income (+) and running costs (−) with the net as a line — capital shown separately.
export function yearly(el, years) {
  const c = mount(el);
  const ys = years.filter((y) => y.year > 0);
  const income = ys.map((y) => y.biochar_sales_sgd + y.gate_fees_sgd + y.credit_sales_sgd);
  const running = ys.map((y) => -(y.staff_sgd + y.maintenance_sgd + y.land_sgd + y.electricity_sgd + y.trucking_sgd + y.certification_sgd));
  c.setOption({
    ...base(),
    tooltip: { ...base().tooltip, valueFormatter: (v) => fmt.money(v) },
    xAxis: { type: "category", data: ys.map((y) => String(y.calendar_year)), ...axis({ splitLine: { show: false } }) },
    yAxis: { type: "value", ...axis({ axisLabel: { color: C.text3, formatter: (v) => fmt.money(v) } }) },
    series: [
      { name: "Income", type: "bar", stack: "y", data: income, barMaxWidth: 26, itemStyle: { color: C.aqua, borderRadius: [4, 4, 0, 0] },
        animationDelay: (i) => i * 50 },
      { name: "Running costs", type: "bar", stack: "y", data: running, itemStyle: { color: C.orange, borderRadius: [0, 0, 4, 4] },
        animationDelay: (i) => i * 50 + 100 },
      { name: "Net cash flow", type: "line", data: ys.map((y) => y.cash_flow_sgd), symbol: "circle", symbolSize: 7, smooth: 0.2,
        lineStyle: { color: C.blue, width: 2.5 }, itemStyle: { color: C.blue }, z: 5, animationDuration: 1500 },
    ],
  }, true);
  return c;
}

// Running total including capital.
export function cumulative(el, years) {
  const c = mount(el);
  c.setOption({
    ...base(), legend: { show: false },
    tooltip: { ...base().tooltip, valueFormatter: (v) => fmt.money(v) },
    xAxis: { type: "category", data: years.map((y) => String(y.calendar_year)), boundaryGap: false, ...axis({ splitLine: { show: false } }) },
    yAxis: { type: "value", ...axis({ axisLabel: { color: C.text3, formatter: (v) => fmt.money(v) } }) },
    series: [{ name: "Cumulative cash", type: "line", data: years.map((y) => y.cumulative_sgd), smooth: 0.2, symbol: "circle", symbolSize: 6,
      lineStyle: { color: C.blue, width: 2.5 }, itemStyle: { color: C.blue },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(57,135,229,.28)" }, { offset: 1, color: "rgba(57,135,229,0)" }]) },
      markLine: { symbol: "none", lineStyle: { color: C.text3, type: "dashed" }, label: { show: false }, data: [{ yAxis: 0 }] },
      animationDuration: 1500 }],
  }, true);
  return c;
}

// Horizontal bars for cost and income per tonne.
export function perTonne(el, costs, income) {
  const c = mount(el);
  const items = [...Object.entries(costs).map(([k, v]) => ({ k, v, kind: "Cost" })),
    ...Object.entries(income).map(([k, v]) => ({ k, v, kind: "Income" }))];
  c.setOption({
    ...base(), legend: { show: false },
    tooltip: { ...base().tooltip, valueFormatter: (v) => fmt.money(v, "/t") },
    grid: { left: 8, right: 60, top: 10, bottom: 8, containLabel: true },
    yAxis: { type: "category", inverse: true, data: items.map((d) => d.k), ...axis({ splitLine: { show: false }, axisLabel: { color: C.text2 } }) },
    xAxis: { type: "value", ...axis({ axisLabel: { color: C.text3, formatter: (v) => `S$${v}` } }) },
    series: [{ type: "bar", data: items.map((d, i) => ({ value: d.v, itemStyle: { color: d.kind === "Cost" ? C.orange : C.aqua, borderRadius: 4 } })),
      barMaxWidth: 18, label: { show: true, position: "right", color: C.text2, formatter: (p) => fmt.money(p.value) },
      animationDelay: (i) => i * 70 }],
  }, true);
  return c;
}

// Vertical bars comparing options; highlighted ids drawn in orange.
export function compare(el, rows, { label, value, highlight, unit = "/t", note = "" }) {
  const c = mount(el);
  c.setOption({
    ...base(), legend: { show: false },
    tooltip: { ...base().tooltip, formatter: (ps) => { const p = ps[0]; const r = rows[p.dataIndex];
      return `<b>${p.name}</b><br>${fmt.money(p.value, unit)}${note ? `<br><span style="color:#a1a1a6">${note(r)}</span>` : ""}`; } },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: rows.map(label), ...axis({ splitLine: { show: false }, axisLabel: { color: C.text3, interval: 0, rotate: rows.length > 6 ? 28 : 0 } }) },
    yAxis: { type: "value", ...axis({ axisLabel: { color: C.text3, formatter: (v) => `S$${v}` } }) },
    series: [{ type: "bar", barMaxWidth: 34, data: rows.map((r) => ({ value: value(r),
      itemStyle: { color: highlight(r) ? C.orange : C.blue, borderRadius: [5, 5, 0, 0] } })), animationDelay: (i) => i * 60,
      label: { show: true, position: "top", color: C.text2, fontSize: 11, formatter: (p) => fmt.money(p.value) } }],
  }, true);
  return c;
}

// Simple bars for saved-evaluation comparisons.
export function bars(el, names, values, { unit = "", better = "low", ref = null, refLabel = "" } = {}) {
  const c = mount(el);
  const best = better === "low" ? Math.min(...values) : Math.max(...values);
  c.setOption({
    ...base(), legend: { show: false },
    tooltip: { ...base().tooltip, valueFormatter: (v) => fmt.money(v, unit) },
    grid: { left: 8, right: 16, top: 20, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: names, ...axis({ splitLine: { show: false }, axisLabel: { color: C.text3, interval: 0, overflow: "truncate", width: 110 } }) },
    yAxis: { type: "value", ...axis({ axisLabel: { color: C.text3, formatter: (v) => fmt.money(v) } }) },
    series: [{ type: "bar", barMaxWidth: 40, data: values.map((v) => ({ value: v, itemStyle: { color: v === best ? C.aqua : C.blue, borderRadius: [5, 5, 0, 0] } })),
      animationDelay: (i) => i * 80,
      markLine: ref == null ? undefined : { symbol: "none", lineStyle: { color: C.text3, type: "dashed" }, label: { color: C.text3, formatter: refLabel },
        data: [{ yAxis: ref }] } }],
  }, true);
  return c;
}
