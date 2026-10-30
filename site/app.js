const NS = "http://www.w3.org/2000/svg";
const $ = (s, el = document) => el.querySelector(s);
const fmt = (v, d = 0) => Number(v).toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d });
const hh = h => `${String(h).padStart(2, "0")}:00`;
const ampm = h => (h % 12 || 12) + (h < 12 ? " am" : " pm");
const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const parse = ts => { const [d, t] = ts.split("T"); const [y, m, dd] = d.split("-").map(Number); return { y, m, d: dd, h: Number(t.slice(0, 2)), date: new Date(y, m - 1, dd, Number(t.slice(0, 2))) }; };
const dayLabel = p => `${DOW[p.date.getDay()]} ${p.d} ${MON[p.m - 1]}`;

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
function text(parent, x, y, str, attrs = {}) {
  const t = el("text", { x, y, ...attrs }, parent);
  t.textContent = str;
  return t;
}
function svg(host, w, h) {
  const s = el("svg", { viewBox: `0 0 ${w} ${h}`, role: "img" });
  host.appendChild(s);
  return s;
}

// --- tooltip ---------------------------------------------------------------
function tooltip(card) {
  const tip = $(".tip", card);
  return {
    show(evt, rows) {
      tip.replaceChildren();
      rows.forEach((r, i) => {
        const line = document.createElement("div");
        if (i === 0) { const s = document.createElement("strong"); s.textContent = r; line.appendChild(s); }
        else { line.className = "r"; line.textContent = r; }
        tip.appendChild(line);
      });
      const box = card.getBoundingClientRect();
      let x = evt.clientX - box.left + 14, y = evt.clientY - box.top + 14;
      tip.style.opacity = 1;
      const tw = tip.offsetWidth;
      if (x + tw > box.width - 8) x = evt.clientX - box.left - tw - 14;
      tip.style.left = Math.max(4, x) + "px";
      tip.style.top = y + "px";
    },
    hide() { tip.style.opacity = 0; },
  };
}

function yAxis(s, x0, x1, y, ticks, label) {
  ticks.forEach(t => {
    el("line", { x1: x0, x2: x1, y1: y(t), y2: y(t), stroke: "var(--grid)", "stroke-width": 1 }, s);
    text(s, x0 - 8, y(t) + 4, label(t), { "text-anchor": "end" });
  });
}
function xHours(s, x, y, every = 3) {
  for (let h = 0; h < 24; h += every) text(s, x(h), y, hh(h), { "text-anchor": "middle" });
}
function niceTicks(lo, hi, n = 4) {
  const step = Math.pow(10, Math.floor(Math.log10((hi - lo) / n)));
  const s = [1, 2, 2.5, 5, 10].map(m => m * step).find(v => (hi - lo) / v <= n) || step * 10;
  const out = [];
  for (let v = Math.ceil(lo / s) * s; v <= hi + 1e-9; v += s) out.push(+v.toFixed(6));
  return out;
}

// --- charts ----------------------------------------------------------------
function heatmap(D) {
  const host = $("#heat"), card = host.parentElement, tip = tooltip(card);
  const days = [...new Set(D.hourly.map(r => r.ts.slice(0, 10)))];
  const W = 960, L = 92, T = 6, ch = 15, gap = 2, cw = (W - L) / 24;
  const H = T + days.length * ch + 26;
  const s = svg(host, W, H);
  const vals = D.hourly.map(r => r.intensity), lo = Math.min(...vals), hi = Math.max(...vals);
  const bin = v => Math.min(7, 1 + Math.floor(((v - lo) / (hi - lo)) * 7));
  $("#ramp-range").textContent = `${fmt(lo)}–${fmt(hi)} gCO₂/kWh`;
  const idx = Object.fromEntries(days.map((d, i) => [d, i]));
  D.hourly.forEach(r => {
    const p = parse(r.ts), i = idx[r.ts.slice(0, 10)];
    const rect = el("rect", { x: L + p.h * cw + gap / 2, y: T + i * ch + gap / 2, width: cw - gap, height: ch - gap,
      rx: 2, fill: `var(--q${bin(r.intensity)})`, tabindex: -1 }, s);
    const rows = () => [`${fmt(r.intensity)} gCO₂/kWh`, `${dayLabel(p)}, ${hh(p.h)}`,
      `${fmt(r.clean_share * 100, 0)}% zero-carbon · solar ${fmt(r.solar / 1000, 0)} GW`,
      r.price != null ? `IEX ₹${fmt(r.price, 2)}/kWh` : "price n/a"];
    rect.addEventListener("pointermove", e => tip.show(e, rows()));
    rect.addEventListener("pointerleave", tip.hide);
  });
  days.forEach((d, i) => {
    if (i % 3 && i !== days.length - 1) return;
    text(s, L - 8, T + i * ch + ch - 4, dayLabel(parse(d + "T00:00")), { "text-anchor": "end" });
  });
  xHours(s, h => L + h * cw + cw / 2, H - 6);
}

function profile(D) {
  const host = $("#profile"), card = host.parentElement, tip = tooltip(card);
  const P = D.hour_of_day, W = 960, H = 300, L = 48, R = 16, T = 16, B = 28;
  const s = svg(host, W, H);
  const x = h => L + (h / 23) * (W - L - R);
  const lo = 400, hi = Math.ceil(Math.max(...P.map(p => p.intensity_p90)) / 100) * 100;
  const y = v => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  yAxis(s, L, W - R, y, niceTicks(lo, hi, 5), v => fmt(v));
  el("line", { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: "var(--axis)" }, s);
  const band = P.map(p => `${x(p.hour)},${y(p.intensity_p90)}`).concat([...P].reverse().map(p => `${x(p.hour)},${y(p.intensity_p10)}`));
  el("polygon", { points: band.join(" "), fill: "var(--band)" }, s);
  el("polyline", { points: P.map(p => `${x(p.hour)},${y(p.intensity_mean)}`).join(" "), fill: "none",
    stroke: "var(--s1)", "stroke-width": 2, "stroke-linejoin": "round" }, s);
  xHours(s, x, H - 8);
  [12, 21].forEach(h => {
    const p = P[h];
    el("circle", { cx: x(h), cy: y(p.intensity_mean), r: 4.5, fill: "var(--s1)", stroke: "var(--surface)", "stroke-width": 2 }, s);
    text(s, x(h), y(p.intensity_mean) + (h === 12 ? 22 : -12), `${ampm(h)} · ${fmt(p.intensity_mean)} g`, { "text-anchor": "middle", class: "lbl" });
  });
  const cross = el("line", { y1: T, y2: H - B, stroke: "var(--axis)", "stroke-width": 1, opacity: 0 }, s);
  const dot = el("circle", { r: 4.5, fill: "var(--s1)", stroke: "var(--surface)", "stroke-width": 2, opacity: 0 }, s);
  const hit = el("rect", { x: L, y: T, width: W - L - R, height: H - T - B, fill: "transparent" }, s);
  hit.addEventListener("pointermove", e => {
    const b = s.getBoundingClientRect();
    const vx = ((e.clientX - b.left) / b.width) * W;
    const h = Math.max(0, Math.min(23, Math.round(((vx - L) / (W - L - R)) * 23))), p = P[h];
    cross.setAttribute("x1", x(h)); cross.setAttribute("x2", x(h)); cross.setAttribute("opacity", 1);
    dot.setAttribute("cx", x(h)); dot.setAttribute("cy", y(p.intensity_mean)); dot.setAttribute("opacity", 1);
    tip.show(e, [`${fmt(p.intensity_mean)} gCO₂/kWh`, `${hh(h)} · 30-day mean`,
      `range ${fmt(p.intensity_p10)}–${fmt(p.intensity_p90)}`, `${fmt(p.clean_share * 100)}% zero-carbon`]);
  });
  hit.addEventListener("pointerleave", () => { tip.hide(); cross.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); });
}

function mix(D) {
  const host = $("#mix"), card = host.parentElement, tip = tooltip(card);
  const rows = D.hourly;
  const series = [
    { key: "Coal & lignite", c: "var(--s1)", f: r => r.thermal },
    { key: "Solar", c: "var(--s2)", f: r => r.solar },
    { key: "Wind, hydro, nuclear", c: "var(--s3)", f: r => r.wind + r.hydro + r.nuclear },
    { key: "Gas & other", c: "var(--s4)", f: r => r.gas },
  ];
  const byH = Array.from({ length: 24 }, (_, h) => {
    const rs = rows.filter(r => parse(r.ts).h === h);
    return series.map(s => rs.reduce((a, r) => a + s.f(r), 0) / rs.length / 1000);
  });
  const W = 480, H = 280, L = 40, R = 8, T = 10, B = 26;
  const s = svg(host, W, H);
  const hi = Math.ceil(Math.max(...byH.map(v => v.reduce((a, b) => a + b, 0))) / 50) * 50;
  const x = h => L + (h / 23) * (W - L - R), y = v => T + (1 - v / hi) * (H - T - B);
  yAxis(s, L, W - R, y, niceTicks(0, hi, 4), v => fmt(v));
  let base = Array(24).fill(0);
  series.forEach((ser, i) => {
    const top = base.map((b, h) => b + byH[h][i]);
    const pts = top.map((v, h) => `${x(h)},${y(v)}`).concat(base.map((v, h) => `${x(h)},${y(v)}`).reverse());
    el("polygon", { points: pts.join(" "), fill: ser.c, stroke: "var(--surface)", "stroke-width": 2, "stroke-linejoin": "round" }, s);
    base = top;
  });
  el("line", { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: "var(--axis)" }, s);
  xHours(s, x, H - 6, 6);
  const cross = el("line", { y1: T, y2: H - B, stroke: "var(--ink-2)", "stroke-width": 1, opacity: 0 }, s);
  const hit = el("rect", { x: L, y: T, width: W - L - R, height: H - T - B, fill: "transparent" }, s);
  hit.addEventListener("pointermove", e => {
    const b = s.getBoundingClientRect();
    const h = Math.max(0, Math.min(23, Math.round(((((e.clientX - b.left) / b.width) * W - L) / (W - L - R)) * 23)));
    cross.setAttribute("x1", x(h)); cross.setAttribute("x2", x(h)); cross.setAttribute("opacity", 0.6);
    tip.show(e, [`${hh(h)} · mean GW`, ...series.map((ser, i) => `${fmt(byH[h][i])} GW  ${ser.key}`)]);
  });
  hit.addEventListener("pointerleave", () => { tip.hide(); cross.setAttribute("opacity", 0); });
}

function bars(hostSel, values, opts) {
  const host = $(hostSel), card = host.parentElement, tip = tooltip(card);
  const W = opts.W || 480, H = opts.H || 280, L = 40, R = 8, T = 12, B = 26;
  const s = svg(host, W, H);
  const n = values.length, bw = (W - L - R) / n;
  const hi = opts.hi ?? Math.max(...values.map(v => v.v)) * 1.08, lo = opts.lo ?? 0;
  const y = v => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  yAxis(s, L, W - R, y, niceTicks(lo, hi, 4), opts.tick);
  values.forEach((d, i) => {
    const top = y(d.v), bottom = H - B, x0 = L + i * bw + 1, w = bw - 2;
    const r = Math.min(4, w / 2, bottom - top);
    el("path", { d: `M${x0},${bottom} V${top + r} Q${x0},${top} ${x0 + r},${top} H${x0 + w - r} Q${x0 + w},${top} ${x0 + w},${top + r} V${bottom} Z`,
      fill: d.c || opts.color }, s);
    const hit = el("rect", { x: L + i * bw, y: T, width: bw, height: H - T - B, fill: "transparent" }, s);
    hit.addEventListener("pointermove", e => tip.show(e, d.tip));
    hit.addEventListener("pointerleave", tip.hide);
  });
  el("line", { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: "var(--axis)" }, s);
  values.forEach((d, i) => { if (d.label) text(s, L + i * bw + bw / 2, H - 6, d.label, { "text-anchor": "middle" }); });
  return { s, y, bw, L };
}

function forecastChart(D) {
  const F = D.forecast, best = parse(F.best_2h.start).date.getTime();
  const vals = F.series.map((r, i) => {
    const p = parse(r.ts), t = p.date.getTime(), inBest = t >= best && t < best + 2 * 3600e3;
    return { v: r.intensity, c: inBest ? "var(--pick)" : "var(--q4)", label: i % 3 === 0 ? hh(p.h) : "",
      tip: [`${fmt(r.intensity)} gCO₂/kWh (forecast)`, `${dayLabel(p)}, ${hh(p.h)}`,
        r.price != null ? `IEX ₹${fmt(r.price, 2)}/kWh (cleared)` : "price not cleared yet", inBest ? "✓ chosen window" : ""].filter(Boolean) };
  });
  const { s, y, bw, L } = bars("#forecast", vals, { W: 960, H: 260, lo: 0, hi: 900, tick: v => fmt(v) });
  const i = F.series.findIndex(r => r.ts === F.best_2h.start);
  if (i >= 0) text(s, L + (i + 1) * bw, y(F.best_2h.carbon) - 10, `Run here · ~${fmt(F.best_2h.carbon)} g`, { "text-anchor": "middle", class: "lbl" });
}

// --- text blocks -----------------------------------------------------------
function tile(k, v, n) {
  const d = document.createElement("div"); d.className = "tile";
  for (const [cls, str] of [["k", k], ["v", v], ["n", n]]) { const e = document.createElement("div"); e.className = cls; e.textContent = str; d.appendChild(e); }
  return d;
}
function table(sel, head, rows) {
  const t = $(sel); t.replaceChildren();
  const tr = document.createElement("tr");
  head.forEach(h => { const th = document.createElement("th"); th.textContent = h; tr.appendChild(th); });
  t.appendChild(tr);
  rows.forEach(r => {
    const row = document.createElement("tr");
    r.forEach(c => { const td = document.createElement("td"); if (typeof c === "object") { td.textContent = c.t; td.className = c.cls; } else td.textContent = c; row.appendChild(td); });
    t.appendChild(row);
  });
}

function render(D) {
  const P = D.hour_of_day, noon = P[12], nine = P[21];
  const cut = 100 * (1 - noon.intensity_mean / nine.intensity_mean);
  const pcut = 100 * (1 - noon.price_mean / nine.price_mean);
  const r0 = parse(D.range[0]), r1 = parse(D.range[1]);
  $("#headline").textContent = `A kWh used at noon in India emits ${fmt(cut)}% less CO₂ than one used at 9 pm.`;
  const bt2 = D.backtest.find(b => b.job_hours === 2);
  $("#tiles").append(
    tile("Noon, 30-day mean", `${fmt(noon.intensity_mean)} g`, `CO₂ per kWh · ${fmt(noon.clean_share * 100)}% zero-carbon`),
    tile("9 pm, 30-day mean", `${fmt(nine.intensity_mean)} g`, `CO₂ per kWh · ${fmt(nine.clean_share * 100)}% zero-carbon`),
    tile("Power price, noon vs 9 pm", `₹${fmt(noon.price_mean, 2)} vs ₹${fmt(nine.price_mean, 2)}`, `IEX day-ahead, per kWh · ${fmt(pcut)}% cheaper`),
    tile("Scheduler, 2-hour jobs", `−${fmt(bt2.carbon_saving_pct, 1)}%`, `CO₂ vs starting immediately, ${bt2.submissions} backtested jobs`),
  );
  $("#heat-sub").textContent = `${dayLabel(r0)} to ${dayLabel(r1)} ${r1.y}: ${D.hourly.length} hours. Each cell is one hour; darker means more CO₂ per kWh. The pale band through the middle of every day is solar.`;
  heatmap(D); profile(D); mix(D);
  bars("#price", P.map(p => ({ v: p.price_mean, label: p.hour % 6 === 0 ? hh(p.hour) : "",
    tip: [`₹${fmt(p.price_mean, 2)}/kWh`, `${hh(p.hour)} · 30-day mean`] })), { color: "var(--s4)", tick: v => "₹" + fmt(v) });
  forecastChart(D);

  const b = parse(D.forecast.best_2h.start), e = new Date(b.date.getTime() + 2 * 3600e3);
  $("#scheduler pre code").textContent =
`$ python -m cleanhour plan --hours 2
  Best window : ${dayLabel(b)} ${hh(b.h)} -> ${hh(e.getHours())}  ~${fmt(D.forecast.best_2h.carbon)} gCO2/kWh

$ python -m cleanhour run --hours 2 --within 24 -- python train.py
[cleanhour] cleanest 2h window starts ${DOW[b.date.getDay()]} ${hh(b.h)}; waiting...
[cleanhour] starting: python train.py`;

  $("#bt-sub").textContent = `A job was submitted at every hour from day 8 onward (${bt2.submissions} submissions). The scheduler could only see a forecast built from the previous 7 days. Each pick was scored on what actually happened in the next 24 hours. "Hindsight" is the best window possible with perfect knowledge.`;
  table("#bt", ["Job length", "Start now", "CleanHour", "Hindsight best", "CO₂ saved", "₹/kWh now → scheduled"],
    D.backtest.map(b => [`${b.job_hours} h`, `${fmt(b.carbon_run_now)} g`, `${fmt(b.carbon_scheduled)} g`, `${fmt(b.carbon_oracle)} g`,
      { t: `−${fmt(b.carbon_saving_pct, 1)}%`, cls: "good" }, `₹${fmt(b.price_run_now, 2)} → ₹${fmt(b.price_scheduled, 2)} (−${fmt(b.price_saving_pct)}%)`]));

  const X = D.experiment;
  if (X) {
    $("#exp-sub").textContent = `${X.model}, ${X.epochs} epochs on a laptop ${X.device}: ${fmt(X.duration_s / 60, 1)} min, ${fmt(X.test_accuracy * 100, 1)}% test accuracy. Measured with CodeCarbon ${X.codecarbon_version}. Then the same energy was priced at noon and at 9 pm.`;
    table("#exp-table", ["Measured", ""], [
      ["Total energy", `${fmt(X.energy_kwh * 1000, 1)} Wh`],
      ["GPU (NVML, measured)", `${fmt(X.gpu_kwh * 1000, 1)} Wh · avg ${fmt(X.avg_gpu_w)} W`],
      ["CPU (estimated)", `${fmt(X.cpu_kwh * 1000, 1)} Wh`],
      ["RAM (estimated)", `${fmt(X.ram_kwh * 1000, 1)} Wh`],
      ["Shift 1 MWh of compute 9 pm → noon", { t: `−${fmt(X.per_mwh_kg_avoided)} kg CO₂, −₹${fmt(X.per_mwh_rs_saved)}`, cls: "good" }],
    ]);
    $("#exp-cmp").append(
      tile("Run at 12:00", `${fmt(X.noon.grams, 1)} g CO₂`, `${fmt(X.noon.intensity)} g/kWh grid`),
      tile("Run at 21:00", `${fmt(X.nine_pm.grams, 1)} g CO₂`, `${fmt(X.nine_pm.intensity)} g/kWh grid`),
      tile("Same job, noon instead", `−${fmt(X.saving_pct, 1)}%`, "CO₂"),
      tile("At exchange prices", `−${fmt(X.price_saving_pct)}%`, "cost per kWh"),
    );
  } else {
    $("#exp-sub").textContent = "Experiment pending.";
  }
  $("#foot").prepend(`Data ${D.range[0].slice(0, 10)} → ${D.range[1].slice(0, 10)}, generated ${D.generated.replace("T", " ")} IST. `);
}

// theme toggle (per-viewer convenience only)
(() => {
  const root = document.documentElement, btn = $("#theme");
  try { const t = localStorage.getItem("theme"); if (t) root.dataset.theme = t; } catch {}
  btn.addEventListener("click", () => {
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch {}
  });
})();

fetch("data.json").then(r => r.json()).then(render).catch(err => {
  $("#lede").textContent = "Could not load data.json: " + err.message;
});
