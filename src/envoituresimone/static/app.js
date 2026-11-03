// Map page: address entry, parameters, calls to the API, drawing of stations and routes.
"use strict";

const $ = (id) => document.getElementById(id);
const eur = (x) => x.toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
const km = (x) => `${x.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} km`;
const hm = (h) => { const m = Math.round(h * 60); return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}` : `${m} min`; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let CFG = null;
const points = { home: null, start: null, end: null };   // {lat, lon, label}
const markers = {};
let picking = null;

// ---------- map ----------
const map = L.map("map").setView([46.6, 2.5], 6);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "© OpenStreetMap",
}).addTo(map);
const layers = { refill: L.layerGroup().addTo(map), trip: L.layerGroup().addTo(map), leg: L.layerGroup().addTo(map) };
const PIN = { home: "🏠", start: "A", end: "B" };

function setPoint(name, p) {
  points[name] = p;
  $(name).value = p.label || `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`;
  if (markers[name]) markers[name].remove();
  markers[name] = L.marker([p.lat, p.lon], {
    icon: L.divIcon({ className: "pin", html: `<b>${PIN[name]}</b>`, iconSize: [24, 24] }), draggable: true,
  }).addTo(map).on("dragend", async (e) => {
    const ll = e.target.getLatLng();
    setPoint(name, { lat: ll.lat, lon: ll.lng, label: await reverse(ll.lat, ll.lng) });
  });
  localStorage.setItem(`pt-${name}`, JSON.stringify(p));
}

async function reverse(lat, lon) {
  try { return (await (await fetch(`/api/reverse?lat=${lat}&lon=${lon}`)).json()).label; } catch { return null; }
}

map.on("click", async (e) => {
  if (!picking) return;
  const name = picking; disarm();
  setPoint(name, { lat: e.latlng.lat, lon: e.latlng.lng, label: await reverse(e.latlng.lat, e.latlng.lng) });
});
function disarm() { picking = null; document.querySelectorAll(".pick").forEach((b) => b.classList.remove("armed")); map.getContainer().style.cursor = ""; }
document.querySelectorAll(".pick").forEach((b) => b.addEventListener("click", () => {
  const t = b.dataset.target; disarm();
  picking = t; b.classList.add("armed"); map.getContainer().style.cursor = "crosshair";
}));
$("locate").addEventListener("click", () => navigator.geolocation?.getCurrentPosition(async (pos) => {
  const { latitude: lat, longitude: lon } = pos.coords;
  setPoint("home", { lat, lon, label: await reverse(lat, lon) }); map.setView([lat, lon], 13);
}));

// ---------- address autocomplete ----------
const sug = $("suggest");
let sugFor = null, sugItems = [], sugIdx = -1, sugTimer = null;
function showSuggest(input, items) {
  sugFor = input; sugItems = items; sugIdx = -1;
  if (!items.length) { sug.hidden = true; return; }
  const r = input.getBoundingClientRect();
  Object.assign(sug.style, { left: `${r.left}px`, top: `${r.bottom + 2}px`, width: `${r.width}px` });
  sug.innerHTML = items.map((it, i) => `<li data-i="${i}">${esc(it.label)}</li>`).join("");
  sug.hidden = false;
}
function choose(i) {
  const it = sugItems[i]; if (!it || !sugFor) return;
  setPoint(sugFor.id, it); map.setView([it.lat, it.lon], Math.max(map.getZoom(), 12)); sug.hidden = true;
}
sug.addEventListener("mousedown", (e) => { const li = e.target.closest("li"); if (li) choose(+li.dataset.i); });
["home", "start", "end"].forEach((id) => {
  const inp = $(id);
  inp.addEventListener("input", () => {
    points[id] = null; clearTimeout(sugTimer);
    sugTimer = setTimeout(async () => {
      const r = await fetch(`/api/complete?q=${encodeURIComponent(inp.value)}`);
      if (r.ok) showSuggest(inp, await r.json());
    }, 250);
  });
  inp.addEventListener("keydown", (e) => {
    if (sug.hidden) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      sugIdx = (sugIdx + (e.key === "ArrowDown" ? 1 : -1) + sugItems.length) % sugItems.length;
      [...sug.children].forEach((li, i) => li.classList.toggle("on", i === sugIdx)); e.preventDefault();
    } else if (e.key === "Enter") { choose(Math.max(sugIdx, 0)); e.preventDefault(); }
    else if (e.key === "Escape") sug.hidden = true;
  });
  inp.addEventListener("blur", () => setTimeout(() => (sug.hidden = true), 150));
});

async function ensurePoint(name) {
  if (points[name]) return points[name];
  const q = $(name).value.trim();
  if (!q) throw new Error("Adresse manquante.");
  const res = await (await fetch(`/api/geocode?q=${encodeURIComponent(q)}`)).json();
  if (!res.length) throw new Error(`Adresse introuvable : ${q}`);
  setPoint(name, res[0]); return res[0];
}

// ---------- tabs ----------
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tab").forEach((s) => (s.hidden = s.id !== `tab-${b.dataset.tab}`));
  const refill = b.dataset.tab === "refill";
  [layers.refill, layers.leg, markers.home].forEach((l) => l && (refill ? l.addTo(map) : l.remove()));
  [layers.trip, markers.start, markers.end].forEach((l) => l && (refill ? l.remove() : l.addTo(map)));
}));

// ---------- consumption curve ----------
const fuel = () => $("fuel").value;
function getCurve() {
  const saved = localStorage.getItem(`curve-${fuel()}`);
  return saved ? JSON.parse(saved) : CFG.curves[fuel()].map((p) => [...p]);
}
function saveCurve(c) { localStorage.setItem(`curve-${fuel()}`, JSON.stringify(c)); }
function renderCurve() {
  const c = getCurve().sort((a, b) => a[0] - b[0]);
  $("curve-table").querySelector("tbody").innerHTML = c.map((p, i) => `<tr>
      <td><input type="number" data-i="${i}" data-k="0" value="${p[0]}"></td>
      <td><input type="number" step="0.1" data-i="${i}" data-k="1" value="${p[1]}"></td>
      <td><button data-del="${i}" title="Supprimer">✕</button></td></tr>`).join("");
  // chart
  const W = 300, H = 120, pad = 24;
  const xs = c.map((p) => p[0]), ys = c.map((p) => p[1]);
  const x0 = 0, x1 = Math.max(140, ...xs), y0 = 0, y1 = Math.ceil(Math.max(...ys, 1) + 1);
  const X = (v) => pad + (v - x0) / (x1 - x0) * (W - pad - 6), Y = (v) => H - 16 - (v - y0) / (y1 - y0) * (H - 24);
  let g = `<line x1="${pad}" y1="${H - 16}" x2="${W - 6}" y2="${H - 16}" stroke="#c9d1db"/>`;
  for (let v = 0; v <= x1; v += 20) g += `<text x="${X(v)}" y="${H - 4}" font-size="9" text-anchor="middle" fill="#7a8492">${v}</text>`;
  for (let v = 0; v <= y1; v += 2) g += `<text x="${pad - 4}" y="${Y(v) + 3}" font-size="9" text-anchor="end" fill="#7a8492">${v}</text><line x1="${pad}" x2="${W - 6}" y1="${Y(v)}" y2="${Y(v)}" stroke="#eef0f3"/>`;
  g += `<polyline fill="none" stroke="#1f5fbf" stroke-width="2" points="${c.map((p) => `${X(p[0])},${Y(p[1])}`).join(" ")}"/>`;
  g += c.map((p) => `<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="3" fill="#1f5fbf"/>`).join("");
  $("curve-chart").innerHTML = g;
}
$("curve-table").addEventListener("change", (e) => {
  const t = e.target; if (!t.dataset.k) return;
  const c = getCurve().sort((a, b) => a[0] - b[0]); c[+t.dataset.i][+t.dataset.k] = parseFloat(t.value) || 0;
  saveCurve(c); renderCurve();
});
$("curve-table").addEventListener("click", (e) => {
  const i = e.target.dataset.del; if (i === undefined) return;
  const c = getCurve().sort((a, b) => a[0] - b[0]); if (c.length <= 2) return;
  c.splice(+i, 1); saveCurve(c); renderCurve();
});
$("curve-add").addEventListener("click", () => {
  const c = getCurve(); const last = c[c.length - 1] || [100, 6];
  c.push([last[0] + 10, last[1]]); saveCurve(c); renderCurve();
});
$("curve-reset").addEventListener("click", () => { localStorage.removeItem(`curve-${fuel()}`); renderCurve(); });

function common() {
  return {
    fuel: fuel(), curve: getCurve(),
    wear_eur_km: $("wear-on").checked ? parseFloat($("wear").value) || 0 : null,
  };
}
async function post(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || r.statusText));
  return j;
}
const notes = (list, cls = "") => (list || []).map((n) => `<div class="note ${cls}">${esc(n)}</div>`).join("");

async function run(btn, out, fn) {
  btn.disabled = true; out.innerHTML = `<div class="note">Calcul en cours…</div>`;
  try { await fn(); } catch (e) { out.innerHTML = `<div class="note err">${esc(e.message)}</div>`; }
  finally { btn.disabled = false; }
}

// ---------- use case A: refill ----------
let refillData = null;
$("go-refill").addEventListener("click", () => run($("go-refill"), $("refill-out"), async () => {
  const home = await ensurePoint("home");
  const d = await post("/api/refill", { ...common(), home, litres: +$("litres").value, radius_km: +$("radius").value });
  refillData = d; layers.refill.clearLayers(); layers.leg.clearLayers();
  const out = $("refill-out");
  if (!d.stations.length) { out.innerHTML = notes(d.notes, "warn"); return; }
  const best = d.stations[0], worst = d.stations[d.stations.length - 1];
  const rows = d.stations.map((s, i) => `<tr class="station ${i === 0 ? "best" : ""}" data-id="${s.id}">
      <td>${i + 1}</td>
      <td>${esc(s.address)}<br><span class="muted">${esc(s.city)} · ${km(s.one_way_km)}${s.estimated ? " ≈" : ""}${s.id === d.cheapest_pump_id ? " · pompe la moins chère" : ""}</span></td>
      <td class="num">${s.price.toFixed(3)}</td>
      <td class="num"><b>${eur(s.total_eur)}</b><br><span class="muted">${s.eur_per_litre_real.toFixed(3)} €/L</span></td></tr>`).join("");
  out.innerHTML = `
    <div class="verdict"><div class="big">${eur(best.total_eur)}</div>
      ${esc(best.address)}, ${esc(best.city)} — ${km(best.one_way_km)} (aller)<br>
      <span class="muted">plein ${eur(best.fuel_bought_eur)} + trajet ${eur(best.detour_fuel_eur)} + usure ${eur(best.wear_eur)}
      · ${eur(worst.total_eur - best.total_eur)} de moins que la plus chère des ${d.stations.length}</span></div>
    ${notes(d.notes)}
    <p class="muted">${d.found} stations trouvées, ${d.routed} classées par itinéraire réel (aller-retour).</p>
    <table><thead><tr><th>#</th><th>Station</th><th class="num">€/L</th><th class="num">Total</th></tr></thead><tbody>${rows}</tbody></table>`;
  const n = d.stations.length;
  d.stations.forEach((s, i) => {
    const t = n > 1 ? i / (n - 1) : 0, col = `hsl(${140 - 140 * t},65%,40%)`;
    L.circleMarker([s.lat, s.lon], { radius: i === 0 ? 10 : 7, color: "#fff", weight: 2, fillColor: col, fillOpacity: 0.95 })
      .bindTooltip(`${i + 1}. ${esc(s.address)} — ${s.price.toFixed(3)} €/L — ${eur(s.total_eur)}`)
      .on("click", () => selectStation(s.id)).addTo(layers.refill);
  });
  map.fitBounds(L.latLngBounds([[home.lat, home.lon], ...d.stations.map((s) => [s.lat, s.lon])]).pad(0.1));
  out.querySelectorAll("tr.station").forEach((tr) => tr.addEventListener("click", () => selectStation(tr.dataset.id)));
  selectStation(best.id, false);
}));

async function selectStation(id, fit = true) {
  const s = refillData?.stations.find((x) => x.id === id); if (!s) return;
  document.querySelectorAll("tr.station").forEach((tr) => tr.classList.toggle("sel", tr.dataset.id === id));
  layers.leg.clearLayers();
  const h = points.home;
  let geom = [[h.lat, h.lon], [s.lat, s.lon]], dashed = true;
  if (CFG.routing) {
    try { geom = (await post("/api/leg", { a: h, b: { lat: s.lat, lon: s.lon } })).geometry; dashed = false; } catch { /* straight line */ }
  }
  L.polyline(geom, { color: "#1f5fbf", weight: 5, opacity: 0.8, dashArray: dashed ? "6 8" : null }).addTo(layers.leg);
  if (fit) map.fitBounds(L.latLngBounds(geom).pad(0.2));
}

// ---------- use case B: trip ----------
const COL = { fastest: "#1f5fbf", toll: "#d64933", toll_free: "#2e9e5b" };
$("go-trip").addEventListener("click", () => run($("go-trip"), $("trip-out"), async () => {
  const [start, end] = [await ensurePoint("start"), await ensurePoint("end")];
  const price = parseFloat($("price").value);
  const d = await post("/api/trip", { ...common(), start, end, price_eur_l: isNaN(price) ? null : price, toll_eur_km: parseFloat($("toll").value) || 0 });
  layers.trip.clearLayers();
  // toll-free under, fastest on top with its tolled parts in red
  L.polyline(d.toll_free.geometry, { color: COL.toll_free, weight: 6, opacity: 0.75 }).bindTooltip("Sans péage").addTo(layers.trip);
  L.polyline(d.fastest.geometry, { color: COL.fastest, weight: 4, opacity: 0.85 }).bindTooltip("Le plus rapide").addTo(layers.trip);
  d.fastest.toll_ranges.forEach(([i, j]) => L.polyline(d.fastest.geometry.slice(i, j + 1), { color: COL.toll, weight: 5 }).bindTooltip("Péage").addTo(layers.trip));
  map.fitBounds(L.latLngBounds(d.fastest.geometry.concat(d.toll_free.geometry)).pad(0.05));

  const win = d.saved_eur > 0 ? "toll_free" : "fastest";
  const card = (key, title, sw) => {
    const r = d[key];
    return `<div class="card ${key === win ? "win" : ""}"><h3><span class="swatch" style="background:${sw}"></span>${title}</h3>
      <div class="big">${eur(r.total_eur)}</div>
      <dl><dt>Distance</dt><dd>${km(r.km)}</dd><dt>Durée</dt><dd>${hm(r.hours)}</dd>
      <dt>Carburant</dt><dd>${r.litres.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} L · ${eur(r.fuel_eur)}</dd>
      <dt>Usure</dt><dd>${eur(r.wear_eur)}</dd>
      <dt>Péages</dt><dd>${km(r.toll_km)} · ${eur(r.toll_eur)}</dd></dl></div>`;
  };
  let verdict;
  if (Math.abs(d.saved_eur) < 0.5) verdict = "Les deux options coûtent à peu près pareil.";
  else if (d.saved_eur > 0) verdict = `Sans péage : <b>${eur(d.saved_eur)} économisés</b> pour ${hm(Math.max(d.extra_hours, 0))} de plus` +
    (d.eur_per_hour_lost ? ` (soit ${eur(d.eur_per_hour_lost)} par heure perdue).` : ".");
  else verdict = `L'autoroute est <b>moins chère de ${eur(-d.saved_eur)}</b> et plus rapide de ${hm(Math.max(d.extra_hours, 0))}.`;
  $("trip-out").innerHTML = `<div class="verdict">${verdict}</div>
    <div class="cards">${card("fastest", "Le plus rapide", COL.fastest)}${card("toll_free", "Sans péage", COL.toll_free)}</div>
    ${notes(d.fastest.warnings, "warn")}${notes(d.notes)}`;
}));

// ---------- start ----------
(async () => {
  CFG = await (await fetch("/api/config")).json();
  $("fuel").innerHTML = Object.entries(CFG.fuels).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("fuel").value = CFG.fuels[localStorage.getItem("fuel")] ? localStorage.getItem("fuel") : "e10";
  $("fuel").addEventListener("change", () => { localStorage.setItem("fuel", fuel()); renderCurve(); });
  $("wear").value = CFG.wear_eur_km; $("toll").value = CFG.toll_eur_km;
  $("routing-warning").hidden = CFG.routing;
  renderCurve();
  for (const name of ["home", "start", "end"]) {
    const p = localStorage.getItem(`pt-${name}`);
    if (p) setPoint(name, JSON.parse(p));
  }
  markers.start?.remove(); markers.end?.remove();
  if (points.home) map.setView([points.home.lat, points.home.lon], 12);
})();
