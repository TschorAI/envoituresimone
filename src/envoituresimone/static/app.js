// Map page: address entry, parameters, calls to the API, drawing of stations and routes.
"use strict";

const $ = (id) => document.getElementById(id);
const eur = (x) => x.toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
const km = (x) => `${x.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} km`;
const hm = (h) => { const m = Math.round(h * 60); return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}` : `${m} min`; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let CFG = null;
const points = { home: null };   // {lat, lon, label}
const markers = {};
let picking = null;

// ---------- map ----------
const map = L.map("map").setView([46.6, 2.5], 6);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "© OpenStreetMap",
}).addTo(map);
const layers = { refill: L.layerGroup().addTo(map), leg: L.layerGroup().addTo(map) };
const PIN = { home: "🏠" };

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
["home"].forEach((id) => {
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
let compareIds = [];                       // up to 2 stations ticked for comparison
const CMP_COL = ["#1f5fbf", "#e07b00"];    // route colours of the two compared stations
const p3 = (x) => `${x.toLocaleString("fr-FR", { minimumFractionDigits: 3, maximumFractionDigits: 3 })} €/L`;
const tripEur = (s) => s.detour_fuel_eur + s.wear_eur;
const rankOf = (s) => refillData.stations.indexOf(s) + 1;
const stationById = (id) => refillData?.stations.find((x) => x.id === id);

$("go-refill").addEventListener("click", () => run($("go-refill"), $("refill-out"), async () => {
  const home = await ensurePoint("home");
  const d = await post("/api/refill", { ...common(), home, litres: +$("litres").value, radius_km: +$("radius").value });
  refillData = d; compareIds = []; layers.refill.clearLayers(); layers.leg.clearLayers();
  const out = $("refill-out");
  if (!d.stations.length) { out.innerHTML = notes(d.notes, "warn"); return; }
  const rows = d.stations.map((s, i) => `<tr class="station ${i === 0 ? "best" : ""}" data-id="${s.id}">
      <td><input type="checkbox" class="cmp" data-id="${s.id}" title="Ajouter à la comparaison"></td>
      <td>${i + 1}</td>
      <td>${esc(s.address)}<br><span class="muted">${esc(s.city)} · ${km(s.one_way_km)}${s.estimated ? " ≈" : ""}${s.id === d.cheapest_pump_id ? " · pompe la moins chère" : ""}</span></td>
      <td class="num">${s.price.toFixed(3)}</td>
      <td class="num">${eur(tripEur(s))}</td>
      <td class="num"><b>${eur(s.total_eur)}</b></td></tr>`).join("");
  out.innerHTML = `
    ${notes(d.notes)}
    <div id="refill-detail"></div>
    <div class="row cmp-bar">
      <span class="muted" id="cmp-hint">Cochez 2 stations pour les comparer.</span>
      <button id="cmp-go" class="small" disabled>Comparer (0/2)</button>
    </div>
    <div id="refill-compare"></div>
    <p class="muted">${d.found} stations trouvées, ${d.routed} classées par itinéraire réel. Trajet = aller-retour (carburant + usure). ${d.prices.kind === "snapshot" ? `Prix relevés le ${new Date(d.prices.at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}.` : "Prix en direct."}</p>
    <table><thead><tr><th></th><th>#</th><th>Station</th><th class="num">Pompe €/L</th><th class="num">Trajet</th><th class="num">Total</th></tr></thead><tbody>${rows}</tbody></table>`;
  const n = d.stations.length;
  d.stations.forEach((s, i) => {
    const t = n > 1 ? i / (n - 1) : 0, col = `hsl(${140 - 140 * t},65%,40%)`;
    L.circleMarker([s.lat, s.lon], { radius: i === 0 ? 10 : 7, color: "#fff", weight: 2, fillColor: col, fillOpacity: 0.95 })
      .bindTooltip(`${i + 1}. ${esc(s.address)} — ${s.price.toFixed(3)} €/L — ${eur(s.total_eur)}`)
      .on("click", () => selectStation(s.id)).addTo(layers.refill);
  });
  map.fitBounds(L.latLngBounds([[home.lat, home.lon], ...d.stations.map((s) => [s.lat, s.lon])]).pad(0.1));
  out.querySelectorAll("tr.station").forEach((tr) => tr.addEventListener("click", (e) => {
    if (!e.target.classList.contains("cmp")) selectStation(tr.dataset.id);
  }));
  out.querySelectorAll("input.cmp").forEach((cb) => cb.addEventListener("change", () => toggleCompare(cb.dataset.id, cb.checked)));
  $("cmp-go").addEventListener("click", showCompare);
  selectStation(d.stations[0].id, false);
}));

function detailHtml(s) {
  const best = refillData.stations[0], diff = s.total_eur - best.total_eur;
  return `<div class="detail">
    <div class="detail-head"><span class="rank">${rankOf(s)}</span>
      <div><b>${esc(s.address)}</b>, ${esc(s.city)}<br>
      <span class="muted">${km(s.one_way_km)} et ${hm(s.one_way_hours)} (aller)${s.estimated ? " · distance estimée" : ""}${s.updated ? ` · prix du ${new Date(s.updated).toLocaleDateString("fr-FR")}` : ""}</span></div></div>
    <dl class="bill">
      <dt>Prix à la pompe</dt><dd>${p3(s.price)}</dd>
      <dt>Plein : ${s.litres_bought.toLocaleString("fr-FR")} L × ${s.price.toLocaleString("fr-FR", { minimumFractionDigits: 3 })} €</dt><dd>${eur(s.fuel_bought_eur)}</dd>
      <dt>Trajet A/R ${km(2 * s.one_way_km)} : carburant (${s.detour_litres.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} L)</dt><dd>${eur(s.detour_fuel_eur)}</dd>
      <dt>Trajet A/R : usure</dt><dd>${eur(s.wear_eur)}</dd>
      <dt class="sub">Coût du trajet</dt><dd class="sub">${eur(tripEur(s))}</dd>
      <dt class="tot">Total</dt><dd class="tot">${eur(s.total_eur)}</dd>
      <dt>Coût réel par litre</dt><dd>${p3(s.eur_per_litre_real)}</dd>
    </dl>
    <div class="${diff < 0.005 ? "good" : "muted"}">${diff < 0.005 ? "Option la moins chère." : `+${eur(diff)} par rapport à la meilleure option (n° 1).`}</div>
  </div>`;
}

async function legGeometry(s) {
  const h = points.home;
  if (CFG.routing) {
    try { return { geom: (await post("/api/leg", { a: h, b: { lat: s.lat, lon: s.lon } })).geometry, dashed: false }; } catch { /* straight line */ }
  }
  return { geom: [[h.lat, h.lon], [s.lat, s.lon]], dashed: true };
}

async function drawLegs(stations, fit) {
  layers.leg.clearLayers();
  const legs = await Promise.all(stations.map(legGeometry));
  legs.forEach(({ geom, dashed }, i) => L.polyline(geom, {
    color: stations.length > 1 ? CMP_COL[i] : CMP_COL[0], weight: 5, opacity: 0.85, dashArray: dashed ? "6 8" : null,
  }).bindTooltip(`${rankOf(stations[i])}. ${esc(stations[i].address)}`).addTo(layers.leg));
  if (fit) map.fitBounds(L.latLngBounds(legs.flatMap((l) => l.geom)).pad(0.2));
}

async function selectStation(id, fit = true) {
  const s = stationById(id); if (!s) return;
  document.querySelectorAll("tr.station").forEach((tr) => tr.classList.toggle("sel", tr.dataset.id === id));
  $("refill-detail").innerHTML = detailHtml(s);
  $("refill-compare").innerHTML = "";
  await drawLegs([s], fit);
}

function toggleCompare(id, on) {
  compareIds = compareIds.filter((x) => x !== id);
  if (on) compareIds.push(id);
  if (compareIds.length > 2) compareIds.shift();      // keep the 2 latest ticks
  document.querySelectorAll("input.cmp").forEach((cb) => (cb.checked = compareIds.includes(cb.dataset.id)));
  $("cmp-go").disabled = compareIds.length !== 2;
  $("cmp-go").textContent = `Comparer (${compareIds.length}/2)`;
}

async function showCompare() {
  const [a, b] = compareIds.map(stationById).sort((x, y) => x.total_eur - y.total_eur);
  const cheap = a.total_eur;
  const line = (label, f, cls = "") => `<tr class="${cls}"><th>${label}</th><td class="num">${f(a)}</td><td class="num">${f(b)}</td></tr>`;
  const head = (s, i) => `<th class="num"><span class="swatch" style="background:${CMP_COL[i]}"></span> n° ${rankOf(s)}<br><span class="muted">${esc(s.address)}</span></th>`;
  $("refill-compare").innerHTML = `<table class="compare">
    <thead><tr><th></th>${head(a, 0)}${head(b, 1)}</tr></thead><tbody>
    ${line("Prix pompe", (s) => p3(s.price))}
    ${line("Distance A/R", (s) => km(2 * s.one_way_km))}
    ${line("Carburant acheté", (s) => eur(s.fuel_bought_eur))}
    ${line("Trajet : carburant", (s) => eur(s.detour_fuel_eur))}
    ${line("Trajet : usure", (s) => eur(s.wear_eur))}
    ${line("Coût du trajet", (s) => eur(tripEur(s)))}
    ${line("Total", (s) => `<b>${eur(s.total_eur)}</b>`, "tot")}
    ${line("Coût réel par litre", (s) => p3(s.eur_per_litre_real))}
    ${line("Écart", (s) => s.total_eur - cheap < 0.005 ? "0 €" : `+${eur(s.total_eur - cheap)}`, "diff")}
    </tbody></table>`;
  $("refill-detail").innerHTML = "";
  document.querySelectorAll("tr.station").forEach((tr) => tr.classList.toggle("sel", compareIds.includes(tr.dataset.id)));
  await drawLegs([a, b], true);
}

// ---------- start ----------
(async () => {
  CFG = await (await fetch("/api/config")).json();
  $("fuel").innerHTML = Object.entries(CFG.fuels).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("fuel").value = CFG.fuels[localStorage.getItem("fuel")] ? localStorage.getItem("fuel") : "e10";
  $("fuel").addEventListener("change", () => { localStorage.setItem("fuel", fuel()); renderCurve(); });
  $("wear").value = CFG.wear_eur_km;
  $("routing-warning").hidden = CFG.routing;
  renderCurve();
  for (const name of ["home"]) {
    const p = localStorage.getItem(`pt-${name}`);
    if (p) setPoint(name, JSON.parse(p));
  }
  if (points.home) map.setView([points.home.lat, points.home.lon], 12);
})();
