/* StayZen frontend: renders the three portals and calls the backend through API (js/api.js). */
(function () {
"use strict";

/* ---------- helpers ---------- */
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = n => "₹" + Math.round(n).toLocaleString("en-IN");
const LV = { low: "Low", med: "Medium", high: "High" };
const PER_PAGE = 10;
const ALL_CELLS = { "0-0": "Gym", "0-1": "Spa", "0-2": "Swimming Pool", "0-3": "Garden Walk", "1-0": "Reception", "1-1": "Coffee Lounge", "1-2": "Restaurant" };
// What the two detail fields mean for each kind of facility.
const FAC_LABELS = { gym: ["Trainer", "Equipment"], pool: ["Lifeguard", "Pool details"], spa: ["Therapists", "Treatments"], restaurant: ["Service", "Menu"], coffee: ["Service", "Menu"], garden: ["Guide", "Features"], reception: ["Staff", "Services"] };
const ROLE_NAME = { guest: "Guest", staff: "Hotel Management", admin: "Stays Admin" };
const DEMO_EMAIL = { guest: "guest@stayzen.demo", staff: "staff@jasminecourt.demo", admin: "admin@stayzen.demo" };
const FB = [["overall", "Overall hotel experience"], ["clean", "Cleanliness"], ["facilities", "Facilities and amenities"], ["staff", "Staff service"], ["accuracy", "Accuracy of hotel information"], ["nav", "Indoor navigation"], ["crowd", "Crowd information accuracy"], ["queue", "Virtual queue experience"]];
const CHECK = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const tick = '<svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 1l1.9 1.4 2.3-.1.7 2.2 1.9 1.3-.7 2.2.7 2.2-1.9 1.3-.7 2.2-2.3-.1L8 15l-1.9-1.4-2.3.1-.7-2.2L1.2 10.2 1.9 8l-.7-2.2 1.9-1.3.7-2.2 2.3.1z" fill="currentColor"/><path d="M5.2 8.1l1.9 1.8 3.7-3.8" stroke="var(--surface)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
function isoDate(d) { const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000); return z.toISOString().slice(0, 10); }
const TODAY = isoDate(new Date());
const IN2 = isoDate(new Date(Date.now() + 2 * 86400000));
function nights(a, b) { return Math.round((new Date(b) - new Date(a)) / 86400000); }
function roomsNeeded(g) { return Math.max(1, Math.ceil(g / 2)); }
function ago(m) { return m < 1 ? "just now" : m === 1 ? "1 minute ago" : m + " minutes ago"; }
function mapsDir(lat, lng) { return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`; }
function statusPill(s) {
  const m = { pending: ["gold", "Pending"], confirmed: ["accent", "Confirmed"], rejected: ["high", "Rejected"], checked_in: ["low", "Checked in"], completed: ["neutral", "Completed"] };
  const x = m[s] || ["neutral", s]; return `<span class="pill ${x[0]}">${x[1]}</span>`;
}
function ratingText(h) { return h.rating ? `<b class="num">★ ${h.rating.toFixed(1)}</b> <span class="muted num">(${h.reviews.toLocaleString("en-IN")} reviews)</span>` : h.stars ? `<b>${h.stars}-star</b> hotel` : '<span class="muted">Rating not available</span>'; }

/* ---------- state ---------- */
// U = what the screen is showing. D = data loaded from the server.
const U = {
  user: null, loginRole: "guest", loginErr: "", showRegister: false,
  gtab: "search", stab: "bookings", atab: "hotels",
  search: { district: "", gps: null, budget: "", guests: "", ci: "", co: "", wants: [] },
  searched: false, editSearch: false, view: null, page: 0, stayCode: "", stayErr: "",
  searchErr: "", showN: 10, compare: [], sel: null, waitFor: null, dismissed: {},
  chatOpen: false, chat: [], lang: "en", speak: false, modal: null, flash: null, fbErr: "",
  staffHotel: null, arrival: null, facMsg: {}, detMsg: "", regMsg: "",
  adist: "", astat: "", aq: "", confirmRemove: null, busy: false,
};
const D = { meta: null, results: null, hotel: null, bookings: [], stay: null, notes: [], staffHotels: [], staff: null, admin: null, adminHotels: [], safety: null };
try { const saved = JSON.parse(localStorage.getItem("stayzen_ui") || "{}"); if (saved.lang) U.lang = saved.lang; if (saved.user) U.user = saved.user; } catch (e) { /* ignore */ }
function persist() { try { localStorage.setItem("stayzen_ui", JSON.stringify({ lang: U.lang, user: U.user })); } catch (e) { /* ignore */ } }
function flash(msg, kind) { U.flash = { msg, kind: kind || "good", at: Date.now() }; }

/* ---------- loading data ---------- */
async function doSearch() {
  const s = U.search; const q = new URLSearchParams({ budget: s.budget, guests: s.guests, check_in: s.ci, check_out: s.co, wants: s.wants.join(",") });
  if (s.gps) { q.set("lat", s.gps[0]); q.set("lng", s.gps[1]); } else q.set("district", s.district);
  const res = await API.get("/api/hotels/search?" + q);
  D.results = res.results; D.origin = res.origin;
}
async function load() {
  if (!D.meta) D.meta = await API.get("/api/meta");
  const u = U.user; if (!u) return;
  if (u.role === "guest") {
    const jobs = [API.get("/api/notifications").then(x => D.notes = x)];
    if (U.gtab === "search" && U.searched && !D.results) jobs.push(doSearch());
    if (U.gtab === "search" && U.view && (!D.hotel || D.hotel.hotel.id !== U.view)) jobs.push(API.get("/api/hotels/" + U.view).then(x => D.hotel = x));
    if (U.gtab === "bookings") jobs.push(API.get("/api/bookings/mine").then(x => D.bookings = x));
    if (U.gtab === "inhotel" && U.stayCode) jobs.push(API.get("/api/stay?code=" + encodeURIComponent(U.stayCode)).then(x => { D.stay = x.stay; U.stayErr = ""; })
      .catch(e => { D.stay = null; U.stayErr = e.message; U.stayCode = ""; }));
    if (U.gtab === "safety") jobs.push(API.get("/api/places/last-hotel").then(x => D.safety = x.hotel));
    await Promise.all(jobs);
  } else if (u.role === "staff") {
    D.staffHotels = await API.get("/api/staff/hotels");
    if (!U.staffHotel || !D.staffHotels.some(h => h.id === U.staffHotel)) U.staffHotel = u.hotel_id && D.staffHotels.some(h => h.id === u.hotel_id) ? u.hotel_id : (D.staffHotels[0] || {}).id;
    D.staff = U.staffHotel ? await API.get("/api/staff/hotels/" + U.staffHotel) : null;
  } else {
    const q = new URLSearchParams({ district: U.adist, status: U.astat, q: U.aq });
    [D.admin, D.adminHotels] = await Promise.all([API.get("/api/admin/summary"), API.get("/api/admin/hotels?" + q)]);
  }
}
async function refresh() {
  try { await load(); }
  catch (e) { if (e.status === 401) { signOutLocal(); flash(e.message, "warn"); } else flash(esc(e.message), "alert"); }
  render();
}
function signOutLocal() { U.user = null; API.setToken(null); U.chatOpen = false; persist(); }

/* ---------- render ---------- */
function render() {
  const u = U.user;
  let html = header() + '<main class="wrap">';
  if (U.flash && Date.now() - U.flash.at < 7000) html += `<div class="notice ${U.flash.kind}" role="status">${U.flash.msg}</div>`;
  if (!D.meta) html += `<section class="panel"><p class="muted">Connecting to the StayZen server…</p></section>`;
  else if (!u) html += loginView();
  else if (u.role === "guest") html += guestView();
  else if (u.role === "staff") html += staffView();
  else html += adminView();
  html += `</main>`;
  if (u && u.role === "guest") html += chatView();
  if (U.modal) html += modalView();
  const chatFocus = document.activeElement && document.activeElement.id === "chatq";
  $("#app").innerHTML = html;
  if (chatFocus && $("#chatq")) $("#chatq").focus();
  const m = $(".msgs"); if (m) m.scrollTop = m.scrollHeight;
}
function header() {
  const u = U.user;
  return `<div class="top"><div class="wrap">
    <div class="brand"><span class="brand-mark"><svg viewBox="0 0 20 20" fill="none"><path d="M3 15c3-1 4-5 7-5s4 4 7 5" stroke="var(--accent-ink)" stroke-width="2" stroke-linecap="round"/><circle cx="10" cy="5.5" r="2.2" fill="var(--accent-2)"/></svg></span>StayZen</div>
    ${u ? `<span class="portal-tag">${ROLE_NAME[u.role]} portal</span>` : ""}
    <span class="spacer"></span>
    ${u ? `<span class="small muted">${esc(u.name)}</span><button class="btn sm" data-act="logout">Sign out</button>` : ""}
  </div></div>`;
}

/* ----- login ----- */
function loginView() {
  const r = U.loginRole; const err = U.loginErr ? `<p class="err">${esc(U.loginErr)}</p>` : "";
  const reg = U.showRegister && r === "guest";
  const hreg = U.showRegister && r === "staff";
  return `<section class="login">
   <div class="hero-copy">
     <span class="label">Smart hotel &amp; resort stays · Tamil Nadu</span>
     <h1>Find the right stay.<br>Skip the crowd inside it.</h1>
     <p class="lede">Pick a hotel that fits your budget, book in a few taps, and know how busy the gym, pool and restaurant are before you walk in.</p>
     <div class="flow">
       <div><span class="n">${CHECK}</span><p><b>Best match for you.</b> Hotels ranked by your budget, distance, rating and the facilities you care about.</p></div>
       <div><span class="n">${CHECK}</span><p><b>Book without paying online.</b> Send a pre-booking request and get your Booking ID instantly.</p></div>
       <div><span class="n">${CHECK}</span><p><b>No more waiting in line.</b> See how crowded each facility is and get a free virtual token when it's busy.</p></div>
       <div><span class="n">${CHECK}</span><p><b>Help in Tamil and English.</b> Ask by text or voice, and find the nearest hospital or police station in one tap.</p></div>
     </div>
   </div>
   <div class="panel raised stack">
     <h2>Sign in</h2>
     <div class="role-pick">${["guest", "staff", "admin"].map(x => `<button data-act="role" data-id="${x}" class="${x === r ? "on" : ""}">${ROLE_NAME[x]}</button>`).join("")}</div>
     ${hreg ? `<form class="stack" data-form="registerHotel">
        <span class="label">Your account</span>
        <div class="field"><label for="hr-name">Your name</label><input id="hr-name" name="name" type="text" required></div>
        <div class="field"><label for="hr-email">Email</label><input id="hr-email" name="email" type="email" required></div>
        <div class="field"><label for="hr-pass">Password</label><input id="hr-pass" name="pass" type="password" minlength="6" required></div>
        <span class="label">Your hotel</span>
        <div class="field"><label for="hr-hotel">Hotel name</label><input id="hr-hotel" name="hotel" type="text" required></div>
        <div class="field"><label for="hr-district">District</label><select id="hr-district" name="district">${D.meta.districts.map(d => `<option>${esc(d.name)}</option>`).join("")}</select></div>
        <div class="field"><label for="hr-area">Area / address</label><input id="hr-area" name="area" type="text" required></div>
        <div class="field"><label for="hr-phone">Contact number</label><input id="hr-phone" name="phone" type="text" required></div>
        <div class="field"><label for="hr-price">Room price / night (₹)</label><input id="hr-price" name="price" type="number" min="300" required></div>
        <div class="field"><label for="hr-rooms">Rooms available</label><input id="hr-rooms" name="rooms" type="number" min="1" required></div>
        <div class="field"><label>Facilities</label><div class="wants">${D.meta.amenities.map(a => `<label class="chk"><input type="checkbox" name="amen" value="${a}">${a}</label>`).join("")}</div></div>
        ${err}<button class="btn primary gbtn">Register hotel</button>
        <p class="small muted">Your hotel shows to guests after the Stays Admin verifies it.</p>
        <button type="button" class="btn ghost sm" data-act="toggleReg">I already have an account</button></form>`
      : reg ? `<form class="stack" data-form="register">
        <div class="field"><label for="rg-name">Full name</label><input id="rg-name" name="name" type="text" required></div>
        <div class="field"><label for="rg-email">Email</label><input id="rg-email" name="email" type="email" required></div>
        <div class="field"><label for="rg-pass">Password</label><input id="rg-pass" name="pass" type="password" minlength="6" required></div>
        ${err}<button class="btn primary gbtn">Create guest account</button>
        <button type="button" class="btn ghost sm" data-act="toggleReg">I already have an account</button></form>`
      : `<form class="stack" data-form="login">
        <div class="field"><label for="lg-email">Email</label><input id="lg-email" name="email" type="email" value="${DEMO_EMAIL[r]}" required></div>
        <div class="field"><label for="lg-pass">Password</label><input id="lg-pass" name="pass" type="password" value="demo123" required></div>
        ${err}<button class="btn primary gbtn">Sign in to ${ROLE_NAME[r]}</button>
        ${r === "guest" ? `<button type="button" class="btn ghost sm" data-act="toggleReg">New guest? Create an account</button>` : ""}
        ${r === "staff" ? `<button type="button" class="btn ghost sm" data-act="toggleReg">New hotel manager? Register your hotel</button>` : ""}</form>`}
   </div></section>`;
}

/* ----- guest ----- */
// ← Previous / Next → arrows at the bottom of every page, moving through that portal's tabs.
function tabArrows(tabs, current, act) {
  const i = tabs.findIndex(t => t[0] === current); const prev = tabs[i - 1], next = tabs[i + 1];
  return `<nav class="pager tabnav" aria-label="Move between pages">
    ${prev ? `<button class="btn" data-act="${act}" data-id="${prev[0]}">← ${prev[1]}</button>` : "<span></span>"}
    ${next ? `<button class="btn primary" data-act="${act}" data-id="${next[0]}">${next[1]} →</button>` : "<span></span>"}</nav>`;
}
function guestView() {
  const tabs = [["search", "Find hotels"], ["bookings", "My bookings"], ["inhotel", "Crowd map"], ["safety", "Safety"]];
  let h = `<nav class="tabs">${tabs.map(t => `<button class="tab ${U.gtab === t[0] ? "on" : ""}" data-act="gtab" data-id="${t[0]}">${t[1]}</button>`).join("")}</nav>`;
  h += D.notes.map(n => `<div class="notice ${esc(n.kind)}" role="status"><span style="flex:1">${esc(n.message)}</span><button class="btn sm" data-act="seen" data-id="${n.id}">OK</button></div>`).join("");
  if (U.gtab === "search") h += searchView();
  else if (U.gtab === "bookings") h += bookingsView();
  else if (U.gtab === "inhotel") h += inHotelView();
  else h += safetyView();
  return h + tabArrows(tabs, U.gtab, "gtab");
}
function searchForm() {
  const s = U.search; const err = U.searchErr ? `<p class="err">${esc(U.searchErr)}</p>` : "";
  return `<section class="panel stack">
   <h2>Where are you staying?</h2>
   <form class="stack" data-form="search">
    <div class="search-form">
      <div class="field"><label for="s-loc">District</label>${s.gps ? `<div class="gpsbox"><span class="pill accent">Your current location</span><button type="button" class="btn sm ghost" data-act="gpsOff">Change</button></div>`
        : `<select id="s-loc" name="district"><option value="">Choose district</option>${D.meta.districts.map(d => `<option value="${esc(d.name)}" ${d.name === s.district ? "selected" : ""}>${esc(d.name)}</option>`).join("")}</select>`}</div>
      <div class="field"><label for="s-budget">Budget / night (₹)</label><input id="s-budget" name="budget" type="number" min="300" step="100" placeholder="e.g. 2500" value="${s.budget}"></div>
      <div class="field"><label for="s-guests">Guests</label><input id="s-guests" name="guests" type="number" min="1" max="8" placeholder="e.g. 2" value="${s.guests}"></div>
      <div class="field"><label for="s-ci">Check-in</label><input id="s-ci" name="ci" type="date" min="${TODAY}" value="${s.ci}"></div>
      <div class="field"><label for="s-co">Check-out</label><input id="s-co" name="co" type="date" min="${TODAY}" value="${s.co}"></div>
    </div>
    <div class="field"><label>Facilities that matter to you</label>
      <div class="wants">${D.meta.amenities.map(a => `<label class="chk"><input type="checkbox" name="wants" value="${a}" ${s.wants.includes(a) ? "checked" : ""}>${a}</label>`).join("")}</div></div>
    ${err}
    <div class="row"><button class="btn primary">Find hotels</button>
      ${s.gps ? "" : `<button type="button" class="btn" data-act="gps">Use my location</button>`}
      ${U.searched ? `<button type="button" class="btn ghost" data-act="cancelEdit">Cancel</button>` : ""}</div>
   </form></section>`;
}
function searchSummary() {
  const s = U.search; const n = nights(s.ci, s.co);
  const fmt = d => new Date(d + "T00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return `<section class="panel summary">
    <div class="sumitems"><span><b>${s.gps ? "Near you" : esc(s.district)}</b></span><span>${fmt(s.ci)} – ${fmt(s.co)} · ${n} night${n > 1 ? "s" : ""}</span><span>${s.guests} guest${s.guests > 1 ? "s" : ""}</span><span>Up to ${money(s.budget)}/night</span></div>
    <button class="btn sm" data-act="editSearch">Change search</button></section>`;
}
function searchView() {
  if (!U.searched || U.editSearch) return searchForm();
  let h = searchSummary();
  if (U.view) return h + hotelDetail();
  const R = D.results || [];
  if (!D.results) return h + `<section class="panel"><p class="muted">Loading hotels…</p></section>`;
  if (U.compare.length >= 2) h += compareView(R);
  const pages = Math.max(1, Math.ceil(R.length / PER_PAGE)); const pg = Math.min(U.page, pages - 1);
  h += `<p><b>${R.length} hotels</b> <span class="muted">${U.search.gps ? "near you" : "in " + esc(U.search.district)}</span></p>`;
  if (!R.length) h += `<section class="panel"><p class="muted">No hotels found here. Try another district.</p></section>`;
  h += '<div class="stack">' + R.slice(pg * PER_PAGE, pg * PER_PAGE + PER_PAGE).map((r, i) => hotelCard(r, pg === 0 && i === 0 && r.bookable)).join("") + "</div>";
  if (pages > 1) h += `<nav class="pager" aria-label="Pages">
    <button class="btn" data-act="page" data-id="${pg - 1}" ${pg === 0 ? "disabled" : ""}>← Previous</button>
    <span class="num">Page ${pg + 1} of ${pages}</span>
    <button class="btn" data-act="page" data-id="${pg + 1}" ${pg >= pages - 1 ? "disabled" : ""}>Next →</button></nav>`;
  return h;
}
function thumb(h, big) {
  return `<div class="thumb ${big ? "big" : ""}" style="${h.photo ? "" : `filter:hue-rotate(${(h.id * 37) % 360}deg)`}">${h.photo ? `<img src="${h.photo}" alt="">` : esc(h.name.split(" ").filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase())}</div>`;
}
function hotelCard(r, best) {
  const h = r.hotel; const inCmp = U.compare.includes(h.id);
  return `<article class="panel hotel clickable ${best ? "best" : ""}" data-act="open" data-id="${h.id}">
   ${thumb(h)}
   <div class="body">
     <div class="title"><h3><button class="linkish" data-act="open" data-id="${h.id}">${esc(h.name)}</button></h3>
       ${h.verified ? `<span class="verified">${tick}Verified</span>` : ""}
       ${best ? '<span class="bestmark">Best match for you</span>' : ""}${r.over_budget ? '<span class="pill high">Over budget</span>' : ""}</div>
     <p class="small muted">${esc(h.area)} · <span class="num">${r.distance_km} km</span> away</p>
     <div class="facts">
       <span>${ratingText(h)}</span>
       ${r.room ? `<span><b class="num">${money(r.room.price)}</b>/night</span><span>Total <b class="num">${money(r.total)}</b></span>` : '<span class="err">No rooms left</span>'}
     </div>
     <div class="chips">${h.amenities.slice(0, 5).map(a => `<span class="chip ${r.hits.includes(a) ? "hit" : ""}">${esc(a)}</span>`).join("")}${h.amenities.length > 5 ? `<span class="chip">+${h.amenities.length - 5}</span>` : ""}</div>
   </div>
   <div class="scorebox">
     <div style="text-align:right"><span class="label">Best Match</span><div class="score"><b class="num">${r.score}</b><span class="muted">/100</span></div>
       <div class="bar"><i style="width:${r.score}%"></i></div></div>
     <button class="btn sm ${inCmp ? "on" : ""}" data-act="cmp" data-id="${h.id}">${inCmp ? "Comparing" : "Compare"}</button>
   </div></article>`;
}
function amenityCards(h, rooms) {
  const p = h.parking || {}; let out = "";
  if (h.amenities.includes("Parking")) out += `<div class="faccard"><h4>Parking</h4>${p.cars == null && p.bikes == null && p.watchman == null ? '<p class="small muted">The hotel has not added details yet.</p>' : `<dl>
     ${p.watchman != null ? `<dt>Watchman</dt><dd>${p.watchman ? "Available" : "Not available"}</dd>` : ""}
     ${p.cars != null ? `<dt>Car parking</dt><dd class="num">${p.cars} cars</dd>` : ""}
     ${p.bikes != null ? `<dt>Bike parking</dt><dd class="num">${p.bikes} bikes</dd>` : ""}</dl>`}</div>`;
  if (h.amenities.includes("Wi-Fi")) out += `<div class="faccard"><h4>Wi-Fi</h4>${h.wifi_info ? `<dl><dt>Details</dt><dd>${esc(h.wifi_info)}</dd></dl>` : '<p class="small muted">The hotel has not added details yet.</p>'}</div>`;
  const ac = rooms.filter(r => r.ac === "AC"), non = rooms.filter(r => r.ac !== "AC");
  out += `<div class="faccard"><h4>AC rooms</h4><dl>
    <dt>AC</dt><dd>${ac.length ? ac.map(r => esc(r.type)).join(", ") : "None"}</dd>
    ${non.length ? `<dt>Non-AC</dt><dd>${non.map(r => esc(r.type)).join(", ")}</dd>` : ""}</dl></div>`;
  return out;
}
function hotelDetail() {
  const r = (D.results || []).find(x => x.hotel.id === U.view);
  if (!D.hotel || !r) return `<section class="panel"><p class="muted">Loading hotel…</p></section>`;
  const h = D.hotel.hotel; const inCmp = U.compare.includes(h.id);
  const extras = h.amenities.filter(a => !["Gym", "Swimming Pool", "Spa", "Restaurant", "Coffee Lounge", "Garden", "Parking", "Wi-Fi"].includes(a));
  const facs = D.hotel.facilities;
  return `<button class="btn back" data-act="close">← Back to hotels</button>
  <section class="panel stack raised">
   <div class="dhead">${thumb(h, true)}
     <div class="stack" style="gap:8px">
       <div class="title"><h2>${esc(h.name)}</h2>${h.verified ? `<span class="verified">${tick}Verified</span>` : ""}</div>
       <p class="muted">${esc(h.area)}, ${esc(h.district)} · <span class="num">${r.distance_km} km</span> away</p>
       <p>${ratingText(h)}</p>
     </div>
     <div class="dprice">${r.room ? `<span class="label">Your stay</span><b class="num">${money(r.total)}</b><span class="small muted num">${esc(r.room.type)} ${esc(r.room.ac)} · ${money(r.room.price)} × ${r.nights} night${r.nights > 1 ? "s" : ""}${r.rooms_needed > 1 ? " × " + r.rooms_needed + " rooms" : ""}</span>` : '<span class="err">No rooms left for your dates</span>'}</div>
   </div>
   <div class="row">
     <button class="btn primary" data-act="book" data-id="${h.id}" ${r.room && r.bookable ? "" : "disabled"}>Pre-book</button>
     <a class="btn" href="${mapsDir(h.lat, h.lng)}" target="_blank" rel="noopener">Route to hotel</a>
     <button class="btn ${inCmp ? "on" : ""}" data-act="cmp" data-id="${h.id}">${inCmp ? "Comparing" : "Add to compare"}</button>
   </div>
   ${r.bookable ? "" : '<p class="small muted">Pre-booking opens once this hotel\'s owner is verified.</p>'}
  </section>
  <section class="panel stack"><h3>Rooms</h3>
   <div class="tablewrap"><table><tr><th>Room</th><th>AC</th><th>Price / night</th><th>Rooms left</th></tr>
    ${D.hotel.rooms.map(x => `<tr><td>${esc(x.type)}</td><td>${esc(x.ac)}</td><td class="num">${money(x.price)}</td><td class="num">${x.avail}</td></tr>`).join("")}</table></div></section>
  <section class="panel stack"><h3>Facilities</h3>
   ${facs.length ? `<div class="facgrid">${facs.map(f => { const L = FAC_LABELS[f.code] || ["Staff", "Details"]; const any = f.open_hours || f.staff_help || f.equipment || f.notes;
     return `<div class="faccard"><h4>${esc(f.name)}</h4>${any ? `<dl>
       ${f.open_hours ? `<dt>Open</dt><dd>${esc(f.open_hours)}</dd>` : ""}
       ${f.staff_help ? `<dt>${L[0]}</dt><dd>${esc(f.staff_help)}</dd>` : ""}
       ${f.equipment ? `<dt>${L[1]}</dt><dd>${esc(f.equipment)}</dd>` : ""}
       ${f.notes ? `<dt>Good to know</dt><dd>${esc(f.notes)}</dd>` : ""}</dl>` : '<p class="small muted">The hotel has not added details yet.</p>'}</div>`; }).join("")}${amenityCards(h, D.hotel.rooms)}</div>`
     : `<div class="facgrid">${amenityCards(h, D.hotel.rooms)}</div>`}
   ${extras.length ? `<div class="chips">${extras.map(a => `<span class="chip">${esc(a)}</span>`).join("")}</div>` : ""}
  </section>
  <div class="grid2">
   <section class="panel stack"><h3>Food nearby</h3>${D.hotel.food.length ? `<ul class="plain">${D.hotel.food.map(f => `<li><b>${esc(f.name)}</b>${f.cuisine ? ` <span class="muted">· ${esc(f.cuisine)}</span>` : ""} <span class="muted num">· ${f.km} km</span></li>`).join("")}</ul>` : '<p class="muted">No restaurants listed within 1 km.</p>'}</section>
   <section class="panel stack"><h3>Contact</h3>
     <dl class="kv"><dt>Phone</dt><dd class="mono" style="user-select:all">${h.phone ? esc(h.phone) : "Not available"}</dd>
     <dt>Website</dt><dd>${h.website ? `<a href="${esc(h.website)}" target="_blank" rel="noopener">${esc(h.website.replace(/^https?:\/\//, "").replace(/\/$/, ""))}</a>` : "Not available"}</dd></dl></section>
  </div>`;
}
function compareView(R) {
  const rows = R.filter(r => U.compare.includes(r.hotel.id));
  if (rows.length < 2) return "";
  const best = rows.slice().sort((a, b) => b.score - a.score)[0];
  const same = new Set(rows.map(r => r.hotel.rating || r.hotel.stars)).size < rows.length;
  const c = r => r === best ? "winner" : "";
  const line = (label, fn) => `<tr><th>${label}</th>${rows.map(r => `<td class="${c(r)}">${fn(r)}</td>`).join("")}</tr>`;
  return `<section class="panel stack raised">
   <div class="row" style="justify-content:space-between"><h2>Compare ${rows.length} hotels</h2><button class="btn sm" data-act="cmpClear">Clear</button></div>
   ${same ? `<div class="notice info small"><span>Some of these hotels have the same rating. StayZen separates them using distance, price and the facilities you picked.</span></div>` : ""}
   <div class="tablewrap"><table>
    <tr><th></th>${rows.map(r => `<th class="${c(r)}">${esc(r.hotel.name)}${r === best ? '<br><span class="bestmark">Best for you</span>' : ""}</th>`).join("")}</tr>
    ${line("Best Match Score", r => `<b>${r.score}</b>/100`)}
    ${line("Price / night", r => r.room ? money(r.room.price) + (r.over_budget ? ' <span class="pill high">Over</span>' : "") : "Not available")}
    ${line("Estimated total", r => r.total ? money(r.total) : "Not available")}
    ${line("Rating", r => ratingText(r.hotel))}
    ${line("Distance", r => r.distance_km + " km")}
    ${line("Your facilities", r => U.search.wants.length ? `${r.hits.length} of ${U.search.wants.length}` : `${r.hotel.amenities.length} listed`)}
    ${line("Restaurants within 1 km", r => r.food.count)}
    ${line("Verified owner", r => r.bookable ? "Yes" : "No")}
    <tr><th></th>${rows.map(r => `<td class="${c(r)}"><button class="btn sm ${r === best ? "primary" : ""}" data-act="book" data-id="${r.hotel.id}" ${r.room && r.bookable ? "" : "disabled"}>Pre-book</button></td>`).join("")}</tr>
   </table></div></section>`;
}
function bookingsView() {
  const bk = D.bookings;
  if (!bk.length) return `<section class="panel stack"><h2>No bookings yet</h2><p class="muted">Search for a hotel and tap <b>Pre-book</b>. You get a Booking ID right away, and the hotel confirms it from their portal.</p>
    <div class="row"><button class="btn primary" data-act="gtab" data-id="search">Find hotels</button></div></section>`;
  return '<div class="stack">' + bk.map(b => `<article class="panel booking">
     <div class="head"><div><span class="label">Booking ID</span><div class="code">${esc(b.code)}</div></div>${statusPill(b.status)}</div>
     <dl class="kv">
       <dt>Hotel</dt><dd>${esc(b.hotel_name)}</dd><dt>Room</dt><dd>${esc(b.room_type)} × ${b.rooms}</dd>
       <dt>Dates</dt><dd class="num">${b.check_in} → ${b.check_out} (${b.nights} night${b.nights > 1 ? "s" : ""})</dd>
       <dt>Guests</dt><dd class="num">${b.guests}</dd><dt>Estimated total</dt><dd class="num">${money(b.total)}</dd>
       <dt>Hotel phone</dt><dd class="mono">${b.hotel_phone ? esc(b.hotel_phone) : "Not available"}</dd>
       <dt>Website</dt><dd>${b.hotel_website ? esc(b.hotel_website) : "Not available"}</dd>
     </dl>
     ${b.status === "pending" ? '<div class="notice warn small"><span>Waiting for the hotel to confirm. No payment is taken in StayZen.</span></div>' : ""}
     ${b.status === "rejected" ? '<div class="notice alert small"><span>The hotel could not hold this room. Try another hotel from your search.</span></div>' : ""}
     <div class="row">
       <a class="btn sm" href="${mapsDir(b.lat, b.lng)}" target="_blank" rel="noopener">Route to hotel</a>
       ${b.status === "confirmed" ? `<button class="btn sm primary" data-act="checkin" data-id="${esc(b.code)}">I have checked in</button>` : ""}
       ${b.status === "checked_in" ? `<button class="btn sm primary" data-act="gtab" data-id="inhotel">Open in-hotel view</button><button class="btn sm" data-act="finish" data-id="${esc(b.code)}">Finish trip</button>` : ""}
       ${b.status === "completed" && !b.has_feedback ? `<button class="btn sm primary" data-act="fb" data-id="${esc(b.code)}">Give feedback</button>` : ""}
       ${b.status === "completed" && b.has_feedback ? '<span class="ok">Thanks, your feedback was sent.</span>' : ""}
     </div></article>`).join("") + "</div>";
}
function inHotelView() {
  const st = D.stay;
  if (!st || !U.stayCode) return `<section class="panel stack"><h2>Enter your Booking ID</h2>
    <p class="muted">Type the Booking ID you got when you pre-booked to see how busy that hotel's facilities are right now.</p>
    <form class="row" data-form="staycode"><input id="stay-code" name="code" type="text" class="mono" placeholder="SZ-1234" style="max-width:200px" required><button class="btn primary">Show crowd map</button></form>
    ${U.stayErr ? `<p class="err">${esc(U.stayErr)}</p>` : ""}
    <div class="row"><button class="btn" data-act="gtab" data-id="bookings">My bookings</button><button class="btn primary" data-act="gtab" data-id="search">Find hotels</button></div></section>`;
  const F = st.facilities; const sel = F.find(f => f.code === U.sel) ? U.sel : null;
  return `<section class="stack">
   <div class="row" style="justify-content:space-between">
     <div><span class="label">You're staying at · ${esc(st.booking_code)}</span><h2>${esc(st.hotel.name)}</h2></div>
     <div class="row"><button class="btn sm" data-act="refresh">Refresh</button><button class="btn sm" data-act="changeCode">Change Booking ID</button></div>
   </div>
   ${st.status !== "checked_in" ? `<div class="notice info"><span>Your booking is <b>${st.status === "pending" ? "waiting for the hotel to confirm" : "confirmed"}</b>. You can check crowd levels now. Free queue tokens open after you check in.</span></div>` : ""}
   <div class="inhotel">
     <div class="panel stack">
       <div class="row" style="justify-content:space-between"><h3>Crowd heat map · Ground floor</h3><span class="small muted">Auto-refreshes every 60 s</span></div>
       ${floorPlan(F, sel)}
       <div class="legend"><span><i style="background:var(--low)"></i>Low · under 50%</span><span><i style="background:var(--med)"></i>Medium · 50–79%</span><span><i style="background:var(--high)"></i>High · 80%+</span><span><i style="background:repeating-linear-gradient(135deg,var(--sunk) 0 3px,var(--muted) 3px 4px)"></i>May be outdated</span></div>
       <div class="tablewrap"><table><tr><th>Facility</th><th>Crowd</th><th>People</th><th>Last updated</th></tr>
         ${F.map(f => `<tr><td><button class="btn sm ghost" data-act="sel" data-id="${f.code}" style="padding:0">${esc(f.name)}</button></td>
           <td><span class="pill ${f.level}">${LV[f.level]} · ${f.pct}%</span></td><td class="num">${f.count} / ${f.capacity}</td>
           <td class="small">${ago(f.mins_ago)}${f.stale ? ' <span class="pill gold">May be outdated</span>' : ""}</td></tr>`).join("")}
       </table></div>
     </div>
     <div class="cases">${sel ? facilityPanel(F, sel, st.status === "checked_in") : ""}${crowdRanking(F)}
       ${tokensPanel(F)}</div>
   </div></section>`;
}
function crowdRanking(F) {
  const list = F.filter(f => f.code !== "reception").slice().sort((a, b) => a.pct - b.pct);
  const quiet = list.filter(f => f.level === "low" && !f.stale);
  return `<div class="panel stack"><h3>Crowd right now</h3>
    ${quiet.length ? `<div class="notice good small"><span><b>Best time for ${esc(quiet[0].name)}</b>: it's quiet now (${quiet[0].pct}%).</span></div>` : ""}
    <div class="heatbars">${list.map(f => `<button class="hb" data-act="sel" data-id="${f.code}">
      <span class="hb-name">${esc(f.name)}</span>
      <span class="hb-track"><i class="${f.level}" style="width:${Math.max(4, Math.min(100, f.pct))}%"></i></span>
      <span class="hb-val num">${f.pct}%</span></button>`).join("")}</div>
    <p class="small muted">Tap a facility on the map or in this list for details.</p></div>`;
}
function floorPlan(F, sel) {
  let cells = "";
  for (let row = 0; row < 2; row++) for (let col = 0; col < 4; col++) {
    const f = F.find(x => x.col === col && x.row === row); const gr = row === 0 ? 1 : 3;
    if (!f) { const miss = ALL_CELLS[row + "-" + col];
      cells += `<div class="cell empty" style="grid-column:${col + 1};grid-row:${gr}">${miss ? `<span class="nm">${miss}</span><span class="sub">Not at this hotel</span>` : "Lifts &amp; stairs"}</div>`; continue; }
    cells += `<button class="cell ${f.level} ${f.stale ? "stale" : ""} ${sel === f.code ? "sel" : ""}" style="grid-column:${col + 1};grid-row:${gr}" data-act="sel" data-id="${f.code}" aria-label="${esc(f.name)}, ${LV[f.level]} crowd, ${f.pct} percent">
      <span class="nm">${esc(f.name)}</span><span class="pc num">${f.pct}%</span><span class="sub num">${f.count}/${f.capacity} · ${f.mins_ago}m ago</span></button>`;
  }
  let route = "";
  const t = sel && sel !== "reception" && F.find(x => x.code === sel);
  if (t) {
    const x = 50 + 100 * t.col, y = t.row === 0 ? 55 : 175;
    route = `<svg class="route" viewBox="0 0 400 230" preserveAspectRatio="none" aria-hidden="true"><path d="M50 175 L50 115 L${x} 115 L${x} ${y}" fill="none" stroke="var(--ink)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><circle cx="50" cy="175" r="6" fill="var(--accent)"/><circle cx="${x}" cy="${y}" r="6" fill="var(--ink)"/></svg>`;
  }
  return `<div class="plan">${cells}<div class="corridor">Main corridor</div>${route}</div>`;
}
function facilityPanel(F, code, inHotel) {
  const f = F.find(x => x.code === code);
  let out = `<div class="panel stack raised"><div class="row" style="justify-content:space-between"><h3>${esc(f.name)}</h3><span class="pill ${f.level}">${LV[f.level]} crowd · ${f.pct}%</span></div>
   <p class="small muted num">${f.count} of ${f.capacity} people · Last updated ${ago(f.mins_ago)}</p>`;
  if (f.stale) out += `<div class="notice warn small"><span><b>This data may be outdated.</b> Staff last updated it ${f.mins_ago} minutes ago, so the real crowd may be different.</span></div>`;
  if (f.level !== "high") {
    out += `<div class="notice good"><span><b>Not crowded.</b> ${code === "reception" || !inHotel ? "" : "Follow the route on the map."}</span></div>
      <div><span class="label">Directions from Reception</span><p style="margin-top:4px">${esc(f.directions)}</p></div>`;
  } else {
    out += `<div class="notice alert"><span><b>This facility is crowded.</b> You can head back or wait for a free slot.</span></div>`;
    if (!inHotel) {
      out += `<div><span class="label">Expected wait right now</span><div class="bigwait num">${f.wait[0]}–${f.wait[1]} min</div><p class="small muted">After check-in you can get a free queue token here.</p></div>`;
    } else if (U.waitFor !== code && !f.my_token) {
      out += `<div class="row"><button class="btn" data-act="sel" data-id="">Back to dashboard</button><button class="btn primary" data-act="wait" data-id="${code}">Wait</button></div>`;
    } else {
      out += `<div><span class="label">Estimated wait</span><div class="bigwait num">${f.wait[0]}–${f.wait[1]} min</div><p class="small muted">Shown as a range because crowds change minute to minute. ${f.queue.length} ${f.queue.length === 1 ? "person is" : "people are"} in the queue.</p></div>`;
      if (!f.my_token) out += `<div class="row"><button class="btn primary" data-act="token" data-id="${code}">Get free virtual token</button><button class="btn" data-act="sel" data-id="">Back to dashboard</button></div>`;
      const sg = U.dismissed[code] ? [] : f.suggestions;
      if (sg.length) out += `<div class="stack"><span class="label">Use the wait well</span>${sg.map(s => `<div class="sugg"><p><b>${esc(s.name)} is quiet now</b> (${s.pct}%). Spend about ${s.duration} min there and come back to the ${esc(f.name)} in about ${f.wait[0]}–${f.wait[1]} min.</p>
        <div class="row"><button class="btn sm primary" data-act="sel" data-id="${s.code}">Accept · show the way</button><button class="btn sm" data-act="dismiss" data-id="${code}">Dismiss</button></div></div>`).join("")}</div>`;
    }
  }
  return out + "</div>";
}
function tokensPanel(F) {
  const mine = F.filter(f => f.my_token);
  if (!mine.length) return "";
  return `<div class="panel stack"><h3>Your queue tokens</h3>${mine.map(f => { const wr = f.wait || [5, 10];
    return `<div class="token"><div><span class="label">${esc(f.name)}</span><div class="code" style="font-size:22px">${esc(f.my_token)}</div></div>
    <div class="small">Position <b class="num">${f.my_pos}</b> in queue · about <b class="num">${wr[0]}–${wr[1]} min</b>${f.my_pos === 1 ? '<br><b class="ok">Your turn is coming up</b>' : ""}</div>
    <button class="btn sm" data-act="untoken" data-id="${f.code}">Cancel token</button></div>`; }).join("")}</div>`;
}
function safetyView() {
  const h = D.safety; const dc = D.meta.districts.find(d => d.name === U.search.district) || D.meta.districts[0];
  const ll = h ? [h.lat, h.lng] : U.search.gps || [dc.lat, dc.lng];
  const near = h ? h.name : U.search.gps ? "your location" : dc.name;
  const cat = [["Police stations", "police station"], ["Hospitals", "hospital"], ["Medical shops & pharmacies", "pharmacy"], ["Fire & rescue", "fire station"]];
  return `<section class="stack">
   <div class="panel stack"><h2>Emergency numbers</h2>
    <div class="emerg"><div><b>112</b>All emergencies</div><div><b>100</b>Police</div><div><b>108</b>Ambulance</div><div><b>101</b>Fire</div></div>
    <p class="small muted">Numbers are selectable so you can copy them into your phone dialler.</p></div>
   <div class="panel stack"><h2>Help near ${esc(near)}</h2>
    <div class="grid2">${cat.map(c => `<div class="sugg"><h3>${c[0]}</h3><p class="small muted">Opens Google Maps with the nearest ${c[1]}s, their address, distance, phone and turn-by-turn directions.</p>
      <a class="btn sm primary" style="align-self:flex-start" href="https://www.google.com/maps/search/${encodeURIComponent(c[1])}/@${ll[0]},${ll[1]},15z" target="_blank" rel="noopener">Find nearest &amp; navigate</a></div>`).join("")}</div></div>
  </section>`;
}

/* ----- staff ----- */
function staffView() {
  if (!D.staff) return `<section class="panel"><p class="muted">No hotels to manage yet. Use "Register a hotel" to add yours.</p></section>` + staffRegister();
  const H = D.staff.hotel;
  const pend = D.staff.bookings.filter(b => b.status === "pending").length;
  const q = D.staff.facilities.reduce((a, f) => a + f.queue.length, 0);
  const tabs = [["bookings", "Pre-bookings", pend], ["facilities", "Facility status"], ["queues", "Queues", q], ["details", "Hotel details"]];
  let h = `<div class="row" style="justify-content:space-between"><div><span class="label">Managing</span><h2>${esc(H.name)} ${H.verified ? `<span class="verified">${tick}Verified</span>` : `<span class="pill gold">${esc(H.status)}</span>`}</h2><p class="small muted">${esc(H.area)}, ${esc(H.district)}</p></div>
</div>`;
  h += `<nav class="tabs">${tabs.map(t => `<button class="tab ${U.stab === t[0] ? "on" : ""}" data-act="stab" data-id="${t[0]}">${t[1]}${t[2] ? `<span class="dot">${t[2]}</span>` : ""}</button>`).join("")}</nav>`;
  if (U.stab === "bookings") h += staffBookings();
  else if (U.stab === "facilities") h += staffFacilities();
  else if (U.stab === "queues") h += staffQueues();
  else h += staffDetails();
  return h + tabArrows(tabs, U.stab, "stab");
}
function staffBookings() {
  const list = D.staff.bookings; const chk = U.arrival;
  let h = `<section class="panel stack"><h3>Check a guest's Booking ID on arrival</h3>
    <form class="row" data-form="arrival"><input id="arr-code" name="code" type="text" placeholder="SZ-1234" style="max-width:200px" class="mono" value="${chk ? esc(chk.code) : ""}"><button class="btn primary">Check ID</button></form>
    ${chk ? chk.valid ? `<div class="notice good"><span style="flex:1"><b>Valid booking ${esc(chk.booking.code)}</b> · ${esc(chk.booking.guest_name)} · ${esc(chk.booking.room_type)} × ${chk.booking.rooms}, ${chk.booking.nights} nights, ${chk.booking.guests} guests · ${statusPill(chk.booking.status)}</span>${chk.booking.status === "confirmed" ? `<button class="btn sm primary" data-act="staffCheckin" data-id="${esc(chk.booking.code)}">Mark checked in</button>` : ""}</div>`
      : `<div class="notice alert"><span><b>No booking found</b> for ${esc(chk.code)} at this hotel. Ask the guest to show the ID from their StayZen app.</span></div>` : ""}
  </section>`;
  if (!list.length) return h + `<section class="panel"><p class="muted">No pre-booking requests yet. When a guest taps <b>Pre-book</b> for this hotel, the request appears here for you to accept or reject.</p></section>`;
  return h + `<section class="panel"><div class="tablewrap"><table><tr><th>Booking ID</th><th>Guest</th><th>Room</th><th>Dates</th><th>Total</th><th>Status</th><th></th></tr>
   ${list.map(b => `<tr><td class="mono">${esc(b.code)}</td><td>${esc(b.guest_name)}<br><span class="small muted">${b.guests} guests</span></td><td>${esc(b.room_type)} × ${b.rooms}</td><td class="small num">${b.check_in} → ${b.check_out}</td><td class="num">${money(b.total)}</td><td>${statusPill(b.status)}</td>
    <td>${b.status === "pending" ? `<div class="row"><button class="btn sm primary" data-act="accept" data-id="${esc(b.code)}">Accept</button><button class="btn sm warn" data-act="reject" data-id="${esc(b.code)}">Reject</button></div>` : ""}</td></tr>`).join("")}
  </table></div></section>`;
}
function staffFacilities() {
  const msg = U.facMsg;
  return `<section class="panel stack"><div class="row" style="justify-content:space-between"><div><h3>Update head counts</h3><p class="small muted">Type how many people are in each facility right now and tap Save. Guests see the change on their heat map.</p></div></div>
   <div>${D.staff.facilities.map(f => `<form class="facrow" data-form="fac" data-id="${f.code}">
       <div><b>${esc(f.name)}</b><div class="small muted num">Capacity ${f.capacity} · updated ${ago(f.mins_ago)} ${f.stale ? '<span class="pill gold">Outdated</span>' : ""}</div></div>
       <div class="stack" style="gap:5px"><span class="pill ${f.level}" style="align-self:flex-start">${LV[f.level]} · ${f.pct}%</span><div class="meter"><i style="width:${Math.min(100, f.pct)}%;background:var(--${f.level})"></i></div></div>
       <input name="count" id="fc-${f.code}" type="number" value="${f.count}" aria-label="${esc(f.name)} head count">
       <div class="row"><button class="btn sm primary">Save</button>${msg[f.code] ? `<span class="${msg[f.code].ok ? "ok" : "err"}">${esc(msg[f.code].t)}</span>` : ""}</div>
     </form>`).join("")}</div>
   <p class="small muted">Crowd levels: under 50% Low, 50–79% Medium, 80% or more High (guests get a crowded alert and a wait-time range).</p></section>`;
}
function staffQueues() {
  const fs = D.staff.facilities.filter(f => f.code !== "reception");
  return `<section class="grid2">${fs.map(f => `<div class="panel stack"><div class="row" style="justify-content:space-between"><h3>${esc(f.name)}</h3><span class="pill ${f.level}">${f.pct}%</span></div>
      ${f.queue.length ? `<ol style="margin:0;padding-left:20px" class="mono">${f.queue.map(x => `<li>${esc(x.token)}${x.stayzen_guest ? ' <span class="pill accent">StayZen guest</span>' : ""}</li>`).join("")}</ol>` : '<p class="small muted">No one is waiting.</p>'}
      <button class="btn sm primary" style="align-self:flex-start" data-act="callNext" data-id="${f.code}" ${f.queue.length ? "" : "disabled"}>Call next</button></div>`).join("")}</section>`;
}
function staffDetails() {
  const H = D.staff.hotel;
  return `<form class="panel stack" data-form="details">
   <div class="row" style="justify-content:space-between"><h3>Hotel details</h3>${U.detMsg ? `<span class="ok">${esc(U.detMsg)}</span>` : ""}</div>
   <div class="grid2">
     <div class="field"><label for="d-phone">Contact number</label><input id="d-phone" name="phone" type="text" value="${esc(H.phone)}"></div>
     <div class="field"><label for="d-web">Website</label><input id="d-web" name="website" type="text" placeholder="https://" value="${esc(H.website)}"></div>
   </div>
   <div class="field"><label>Facilities and amenities</label><div class="wants">${D.meta.amenities.map(a => `<label class="chk"><input type="checkbox" name="amen" value="${a}" ${H.amenities.includes(a) ? "checked" : ""}>${a}</label>`).join("")}</div></div>
   <fieldset class="facedit"><legend>Parking and Wi-Fi</legend>
    <div class="grid2">
     <div class="field"><label for="pk-w">Parking watchman</label><select id="pk-w" name="pkw"><option value="">Not set</option><option value="1" ${H.parking && H.parking.watchman ? "selected" : ""}>Available</option><option value="0" ${H.parking && H.parking.watchman === 0 ? "selected" : ""}>Not available</option></select></div>
     <div class="field"><label for="pk-c">Car slots</label><input id="pk-c" name="pkc" type="number" min="0" value="${H.parking && H.parking.cars != null ? H.parking.cars : ""}"></div>
     <div class="field"><label for="pk-b">Bike slots</label><input id="pk-b" name="pkb" type="number" min="0" value="${H.parking && H.parking.bikes != null ? H.parking.bikes : ""}"></div>
     <div class="field"><label for="wf">Wi-Fi details</label><input id="wf" name="wifi" type="text" placeholder="e.g. Free in all rooms, 50 Mbps" value="${esc(H.wifi_info || "")}"></div>
    </div></fieldset>
   <div class="stack"><span class="label">Facility details guests will see</span>
    ${D.staff.facilities.filter(f => f.code !== "reception").map(f => { const L = FAC_LABELS[f.code] || ["Staff", "Details"]; return `<fieldset class="facedit"><legend>${esc(f.name)}</legend>
      <div class="grid2">
       <div class="field"><label for="oh-${f.code}">Open hours</label><input id="oh-${f.code}" name="oh-${f.code}" type="text" placeholder="e.g. 6:00 AM – 10:00 PM" value="${esc(f.open_hours)}"></div>
       <div class="field"><label for="sh-${f.code}">${L[0]}</label><input id="sh-${f.code}" name="sh-${f.code}" type="text" value="${esc(f.staff_help)}"></div>
      </div>
      <div class="field"><label for="eq-${f.code}">${L[1]}</label><textarea id="eq-${f.code}" name="eq-${f.code}" rows="2">${esc(f.equipment)}</textarea></div>
      <div class="field"><label for="nt-${f.code}">Good to know</label><input id="nt-${f.code}" name="nt-${f.code}" type="text" value="${esc(f.notes)}"></div>
     </fieldset>`; }).join("")}</div>
   <div class="field"><label for="d-photo">Hotel photo (under 300 KB)</label><input id="d-photo" name="photo" type="file" accept="image/*"></div>
   <div class="tablewrap"><table><tr><th>Room type</th><th>AC</th><th>Price / night (₹)</th><th>Rooms available</th></tr>
    ${D.staff.rooms.map(r => `<tr><td>${esc(r.type)}</td><td>${esc(r.ac)}</td><td><input type="number" min="0" id="p-${r.id}" name="price-${r.id}" value="${r.price}" style="max-width:130px"></td><td><input type="number" min="0" id="a-${r.id}" name="avail-${r.id}" value="${r.avail}" style="max-width:100px"></td></tr>`).join("")}
   </table></div>
   <div class="row"><button class="btn primary">Save and submit for review</button><span class="small muted">Changes show to guests now and are logged for the Stays Admin to review.</span></div>
  </form>`;
}
function staffRegister() {
  return `<form class="panel stack" data-form="newhotel">
   <h3>Register a new hotel or resort</h3><p class="small muted">New listings stay hidden from guests until the Stays Admin verifies them.</p>
   ${U.regMsg ? `<div class="notice good"><span>${esc(U.regMsg)}</span></div>` : ""}
   <div class="grid2">
     <div class="field"><label for="n-name">Hotel name</label><input id="n-name" name="name" type="text" required></div>
     <div class="field"><label for="n-district">District</label><select id="n-district" name="district">${D.meta.districts.map(d => `<option>${esc(d.name)}</option>`).join("")}</select></div>
     <div class="field"><label for="n-area">Area / address</label><input id="n-area" name="area" type="text" required></div>
     <div class="field"><label for="n-phone">Contact number</label><input id="n-phone" name="phone" type="text" required></div>
     <div class="field"><label for="n-price">Standard room price / night (₹)</label><input id="n-price" name="price" type="number" min="300" required></div>
     <div class="field"><label for="n-rooms">Rooms available</label><input id="n-rooms" name="rooms" type="number" min="1" required></div>
   </div>
   <div class="field"><label>Facilities and amenities</label><div class="wants">${D.meta.amenities.map(a => `<label class="chk"><input type="checkbox" name="amen" value="${a}">${a}</label>`).join("")}</div></div>
   <button class="btn primary" style="align-self:flex-start">Submit for verification</button></form>`;
}

/* ----- admin ----- */
function adminView() {
  const A = D.admin; if (!A) return "";
  const s = A.stats; const upd = A.updates.filter(u => !u.reviewed).length;
  const tabs = [["hotels", "Hotels", s.pending], ["updates", "Submitted updates", upd], ["freshness", "Data freshness", s.stale], ["feedback", "Guest feedback"]];
  let h = `<div class="stats">
    <div class="stat"><span class="label">Verified listings</span><b class="num">${s.live}</b></div>
    <div class="stat"><span class="label">Awaiting verification</span><b class="num">${s.pending}</b></div>
    <div class="stat"><span class="label">Listed from OSM</span><b class="num">${s.listed}</b></div>
    <div class="stat"><span class="label">Pre-bookings</span><b class="num">${s.bookings}</b></div>
    <div class="stat"><span class="label">Outdated crowd feeds</span><b class="num">${s.stale}</b></div></div>`;
  h += `<nav class="tabs">${tabs.map(t => `<button class="tab ${U.atab === t[0] ? "on" : ""}" data-act="atab" data-id="${t[0]}">${t[1]}${t[2] ? `<span class="dot">${t[2]}</span>` : ""}</button>`).join("")}</nav>`;
  if (U.atab === "hotels") h += adminHotels();
  else if (U.atab === "updates") h += A.updates.length ? `<section class="panel"><div class="tablewrap"><table><tr><th>Hotel</th><th>Change</th><th>Submitted</th><th></th></tr>
    ${A.updates.map(u => `<tr><td>${esc(u.hotel)}</td><td>${esc(u.text)}</td><td class="small">${ago(u.mins_ago)}</td><td>${u.reviewed ? '<span class="pill neutral">Reviewed</span>' : `<button class="btn sm primary" data-act="reviewed" data-id="${u.id}">Mark reviewed</button>`}</td></tr>`).join("")}</table></div></section>`
    : `<section class="panel"><p class="muted">No updates yet. When a hotel changes prices, rooms or amenities, it shows up here.</p></section>`;
  else if (U.atab === "freshness") h += `<section class="panel stack"><h3>Facilities with outdated crowd data</h3><p class="small muted">Guests see a "may be outdated" warning on these. Anything older than 15 minutes is flagged.</p>
    ${A.stale.length ? `<div class="tablewrap"><table><tr><th>Hotel</th><th>Facility</th><th>Last updated</th></tr>${A.stale.map(x => `<tr><td>${esc(x.hotel)}</td><td>${esc(x.facility)}</td><td><span class="pill gold">${x.mins} min ago</span></td></tr>`).join("")}</table></div>` : '<div class="notice good"><span>All crowd feeds are fresh.</span></div>'}</section>`;
  else h += A.feedback.length ? '<div class="stack">' + A.feedback.map(g => `<section class="panel stack"><div class="row" style="justify-content:space-between"><h3>${esc(g.hotel)}</h3><span class="small muted">${g.count} response${g.count > 1 ? "s" : ""}</span></div>
     <div class="tablewrap"><table><tr>${FB.map(f => `<th>${f[1]}</th>`).join("")}</tr><tr>${FB.map(f => `<td class="num"><b>★ ${g.avg[f[0]].toFixed(1)}</b></td>`).join("")}</tr></table></div>
     ${g.comments.map(c => `<p class="small"><span class="mono muted">${esc(c.code)}</span> · ${esc(c.text)}</p>`).join("")}</section>`).join("") + "</div>"
    : '<section class="panel"><p class="muted">No feedback yet. Guests are asked for feedback when they tap Finish Trip.</p></section>';
  return h + tabArrows(tabs, U.atab, "atab");
}
function adminHotels() {
  const st = { approved: `<span class="verified">${tick}Verified</span>`, pending: '<span class="pill gold">Pending review</span>', listed: '<span class="pill neutral">Listed · OSM</span>', rejected: '<span class="pill high">Rejected</span>', suspended: '<span class="pill neutral">Suspended</span>' };
  return `<form class="panel filters" data-form="afilter">
     <div class="field"><label for="af-d">District</label><select id="af-d" name="district"><option value="">All districts</option>${D.meta.districts.map(d => `<option ${d.name === U.adist ? "selected" : ""}>${esc(d.name)}</option>`).join("")}</select></div>
     <div class="field"><label for="af-s">Status</label><select id="af-s" name="status">${[["", "Any status"], ["pending", "Pending review"], ["approved", "Verified"], ["listed", "Listed · OSM"], ["suspended", "Suspended"], ["rejected", "Rejected"]].map(o => `<option value="${o[0]}" ${o[0] === U.astat ? "selected" : ""}>${o[1]}</option>`).join("")}</select></div>
     <div class="field" style="flex:1"><label for="af-q">Hotel name</label><input id="af-q" name="q" type="text" value="${esc(U.aq)}" placeholder="Search"></div>
     <button class="btn primary">Filter</button></form>
   <section class="panel"><p class="small muted" style="margin-bottom:8px">Showing up to 60 hotels. Pending ones come first.</p><div class="tablewrap"><table><tr><th>Hotel</th><th>District</th><th>Rooms from</th><th>Status</th><th>Actions</th></tr>
   ${D.adminHotels.map(h => { const conf = U.confirmRemove === h.id;
     return `<tr><td><b>${esc(h.name)}</b><br><span class="small muted">${esc(h.area || "")}${h.phone ? " · " + esc(h.phone) : ""}</span></td><td>${esc(h.district)}</td><td class="num">${h.min_price ? money(h.min_price) : "Not available"}</td><td>${st[h.status] || esc(h.status)}</td>
     <td><div class="row">${conf ? `<span class="small">Remove permanently?</span><button class="btn sm warn" data-act="remove" data-id="${h.id}">Yes, remove</button><button class="btn sm" data-act="cancelRemove">Cancel</button>` :
      `${h.status !== "approved" ? `<button class="btn sm primary" data-act="approve" data-id="${h.id}">Verify &amp; approve</button>` : ""}
       ${h.status === "pending" ? `<button class="btn sm warn" data-act="hreject" data-id="${h.id}">Reject</button>` : ""}
       ${h.status === "approved" ? `<button class="btn sm" data-act="suspend" data-id="${h.id}">Suspend</button>` : ""}
       <button class="btn sm ghost" data-act="askRemove" data-id="${h.id}">Remove</button>`}</div></td></tr>`; }).join("")}
  </table></div></section>`;
}

/* ----- modal ----- */
function modalView() {
  const m = U.modal; const s = U.search;
  if (m.type === "book") { const r = (D.results || []).find(x => x.hotel.id === m.id); if (!r) return "";
    return `<div class="scrim" data-act="closeModal"><div class="modal" role="dialog" aria-modal="true" aria-label="Pre-book" data-stop>
     <h2>Pre-book ${esc(r.hotel.name)}</h2>
     <dl class="kv"><dt>Room</dt><dd>${esc(r.room.type)} ${esc(r.room.ac)} × ${r.rooms_needed}</dd><dt>Check-in</dt><dd class="num">${s.ci}</dd><dt>Check-out</dt><dd class="num">${s.co}</dd>
     <dt>Guests</dt><dd class="num">${s.guests}</dd><dt>Price</dt><dd class="num">${money(r.room.price)} × ${r.nights} nights × ${r.rooms_needed}</dd><dt>Estimated total</dt><dd class="num" style="font-size:18px">${money(r.total)}</dd></dl>
     <div class="notice info small"><span>This is a request, not a payment. The hotel confirms it from their portal and you pay at the hotel.</span></div>
     <div class="row" style="justify-content:flex-end"><button class="btn" data-act="closeModal">Cancel</button><button class="btn primary" data-act="confirmBook" data-id="${r.hotel.id}">Send pre-booking request</button></div></div></div>`; }
  if (m.type === "booked") { const b = m.booking;
    return `<div class="scrim" data-act="closeModal"><div class="modal" role="dialog" aria-modal="true" aria-label="Booking sent" data-stop>
     <span class="label">Request sent · your Booking ID</span><div class="code" style="font-size:34px">${esc(b.code)}</div>
     <p>Show this ID at ${esc(b.hotel_name)} when you arrive. Status: ${statusPill(b.status)}</p>
     <dl class="kv"><dt>Estimated total</dt><dd class="num">${money(b.total)}</dd><dt>Hotel phone</dt><dd class="mono">${b.hotel_phone ? esc(b.hotel_phone) : "Not available"}</dd><dt>Website</dt><dd>${b.hotel_website ? esc(b.hotel_website) : "Not available"}</dd></dl>
     <div class="row" style="justify-content:flex-end"><a class="btn" href="${mapsDir(b.lat, b.lng)}" target="_blank" rel="noopener">Route to hotel</a><button class="btn primary" data-act="goBookings">View my bookings</button></div></div></div>`; }
  if (m.type === "fb") return `<div class="scrim" data-act="closeModal"><form class="modal" data-form="feedback" data-id="${esc(m.id)}" role="dialog" aria-modal="true" aria-label="Trip feedback" data-stop>
     <h2>How was your stay?</h2><p class="small muted">Booking <span class="mono">${esc(m.id)}</span>. Tap the stars for each item.</p>
     <div>${FB.map(f => `<div class="fbrow"><span>${f[1]}</span><span class="stars">${[5, 4, 3, 2, 1].map(n => `<input type="radio" id="fb-${f[0]}-${n}" name="${f[0]}" value="${n}"><label for="fb-${f[0]}-${n}" title="${n} star${n > 1 ? "s" : ""}">★</label>`).join("")}</span></div>`).join("")}</div>
     <div class="field"><label for="fb-c">Suggestions for improvement</label><textarea id="fb-c" name="c"></textarea></div>
     ${U.fbErr ? `<p class="err">${esc(U.fbErr)}</p>` : ""}
     <div class="row" style="justify-content:flex-end"><button type="button" class="btn" data-act="closeModal">Later</button><button class="btn primary">Send feedback</button></div></form></div>`;
  return "";
}

/* ----- chat ----- */
const QUICK = { en: ["Is the gym crowded?", "How do I get to the pool?", "What can I do while I wait?", "My token status", "Room prices", "Emergency numbers"],
  ta: ["ஜிம்மில் கூட்டம் உள்ளதா?", "நீச்சல் குளத்திற்கு எப்படி செல்வது?", "காத்திருக்கும்போது என்ன செய்யலாம்?", "என் டோக்கன் நிலை", "அறை விலை", "அவசர எண்கள்"] };
function chatView() {
  if (!U.chatOpen) return `<button class="btn primary chat-fab" data-act="chat">Ask StayZen</button>`;
  const t = U.lang;
  const msgs = U.chat.length ? U.chat : [{ who: "bot", text: t === "ta" ? "வணக்கம்! கூட்டம், வழி, டோக்கன், விலை அல்லது அவசர உதவி பற்றி கேளுங்கள்." : "Hi! I'm the StayZen assistant. Ask me anything: hotels, your booking, crowds, facilities, directions, or just chat." }];
  return `<aside class="chat" aria-label="StayZen assistant">
   <header><b style="flex:1">StayZen assistant</b>
    <div class="seg"><button class="${t === "en" ? "on" : ""}" data-act="lang" data-id="en">English</button><button class="${t === "ta" ? "on" : ""}" data-act="lang" data-id="ta">தமிழ்</button></div>
    <button class="btn sm ${U.speak ? "on" : ""}" data-act="speak" title="Read replies aloud">${U.speak ? "Voice on" : "Voice off"}</button>
    <button class="btn sm ghost" data-act="chat" aria-label="Close">✕</button></header>
   <div class="msgs">${msgs.map(m => `<div class="msg ${m.who}">${esc(m.text)}</div>`).join("")}</div>
   <div class="quick">${QUICK[t].map(q => `<button data-act="ask" data-id="${esc(q)}">${esc(q)}</button>`).join("")}</div>
   <form data-form="chat"><button type="button" class="btn" data-act="mic" title="Speak your question" aria-label="Speak your question">Mic</button><input id="chatq" name="q" type="text" autocomplete="off" placeholder="${t === "ta" ? "உங்கள் கேள்வி…" : "Type your question…"}"><button class="btn primary">Send</button></form>
  </aside>`;
}
function speak(text) { if (!U.speak) return; try { const u = new SpeechSynthesisUtterance(text); u.lang = U.lang === "ta" ? "ta-IN" : "en-IN"; speechSynthesis.cancel(); speechSynthesis.speak(u); } catch (e) { /* no voice support */ } }
async function ask(q) {
  q = q.trim(); if (!q) return;
  U.chat.push({ who: "me", text: q }); render();
  try { const r = await API.post("/api/chat", { message: q, lang: U.lang, history: U.chat.slice(0, -1).slice(-10) }); U.chat.push({ who: "bot", text: r.reply }); speak(r.reply); }
  catch (e) { U.chat.push({ who: "bot", text: e.message }); }
  render();
}
function listen() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { flash("Voice input needs Chrome or Edge.", "warn"); render(); return; }
  const rec = new SR(); rec.lang = U.lang === "ta" ? "ta-IN" : "en-IN"; rec.interimResults = false;
  rec.onresult = e => ask(e.results[0][0].transcript);
  rec.onerror = () => { flash("Couldn't hear that. Check microphone permission and try again.", "warn"); render(); };
  rec.start(); flash(U.lang === "ta" ? "கேட்கிறேன்… பேசுங்கள்." : "Listening… speak now.", "info"); render();
}

/* ---------- actions (buttons) ---------- */
const A = {
  role: id => { U.loginRole = id; U.loginErr = ""; U.showRegister = false; },
  toggleReg: () => { U.showRegister = !U.showRegister; U.loginErr = ""; },
  logout: async () => { try { await API.post("/api/auth/logout"); } catch (e) { /* already out */ } signOutLocal(); Object.assign(D, { results: null, bookings: [], stay: null, staff: null, admin: null }); },
  gtab: async id => { U.gtab = id; window.scrollTo(0, 0); await load(); },
  stab: async id => { U.stab = id; U.facMsg = {}; U.detMsg = ""; U.regMsg = ""; await load(); },
  atab: async id => { U.atab = id; await load(); },
  page: id => { U.page = Math.max(0, +id); window.scrollTo(0, 0); },
  open: async id => { U.view = +id; window.scrollTo(0, 0); await load(); },
  close: () => { U.view = null; D.hotel = null; },
  editSearch: () => { U.editSearch = true; U.view = null; },
  cancelEdit: () => { U.editSearch = false; },
  gps: () => {
    keepForm();
    if (!navigator.geolocation) { U.searchErr = "This browser can't share location. Choose your district instead."; return; }
    navigator.geolocation.getCurrentPosition(p => { U.search.gps = [p.coords.latitude, p.coords.longitude]; U.searchErr = ""; render(); },
      () => { U.searchErr = "Location permission was refused. Choose your district instead."; render(); }, { timeout: 10000 });
  },
  gpsOff: () => { keepForm(); U.search.gps = null; },
  cmp: id => { id = +id; const i = U.compare.indexOf(id); if (i >= 0) U.compare.splice(i, 1); else { if (U.compare.length >= 3) U.compare.shift(); U.compare.push(id); } },
  cmpClear: () => { U.compare = []; },
  book: id => { U.modal = { type: "book", id: +id }; },
  closeModal: () => { U.modal = null; U.fbErr = ""; },
  confirmBook: async id => { const r = D.results.find(x => x.hotel.id === +id); const s = U.search;
    const b = await API.post("/api/bookings", { hotel_id: r.hotel.id, room_id: r.room.id, check_in: s.ci, check_out: s.co, guests: s.guests });
    U.modal = { type: "booked", booking: b }; },
  goBookings: async () => { U.modal = null; U.gtab = "bookings"; await load(); },
  checkin: async code => { await API.post(`/api/bookings/${code}/checkin`); U.gtab = "inhotel"; U.stayCode = code; U.sel = null; flash("Welcome! Your in-hotel view is ready."); await load(); },
  demoStay: async () => { const r = await API.post("/api/demo-stay"); U.gtab = "inhotel"; U.sel = "gym"; flash(`Demo stay created: ${esc(r.code)} at ${esc(r.hotel)}, already checked in.`, "info"); await load(); },
  finish: async code => { await API.post(`/api/bookings/${code}/finish`); U.modal = { type: "fb", id: code }; await load(); },
  fb: code => { U.modal = { type: "fb", id: code }; },
  sel: id => { U.sel = id || null; if (!id) U.waitFor = null; },
  wait: id => { U.waitFor = id; },
  token: async id => { const r = await API.post("/api/stay/tokens", { facility: id }); U.waitFor = id; flash(`Token ${esc(r.token)} issued. We'll tell you when your turn is coming up.`); await load(); },
  untoken: async id => { await API.del("/api/stay/tokens/" + id); U.waitFor = null; await load(); },
  dismiss: id => { U.dismissed[id] = true; },
  changeCode: () => { U.stayCode = ""; D.stay = null; U.sel = null; },
  refresh: async () => { await load(); flash("Crowd data refreshed.", "info"); },
  seen: async id => { await API.post(`/api/notifications/${id}/seen`); await load(); },
  accept: async code => { await API.post(`/api/staff/bookings/${code}/accept`); flash(`${esc(code)} accepted. The guest has been notified.`); await load(); },
  reject: async code => { await API.post(`/api/staff/bookings/${code}/reject`); flash(`${esc(code)} rejected.`, "warn"); await load(); },
  staffCheckin: async code => { await API.post(`/api/staff/bookings/${code}/checkin`); U.arrival = null; flash(`${esc(code)} checked in.`); await load(); },
  callNext: async code => { const r = await API.post(`/api/staff/hotels/${U.staffHotel}/queues/${code}/call-next`); flash(`Called ${esc(r.called)}.`); await load(); },
  approve: async id => { await API.post(`/api/admin/hotels/${id}/approve`); flash("Hotel verified. Guests can now pre-book it."); await load(); },
  hreject: async id => { await API.post(`/api/admin/hotels/${id}/reject`); flash("Hotel rejected.", "warn"); await load(); },
  suspend: async id => { await API.post(`/api/admin/hotels/${id}/suspend`); flash("Hotel suspended and hidden from guests.", "warn"); await load(); },
  askRemove: id => { U.confirmRemove = +id; }, cancelRemove: () => { U.confirmRemove = null; },
  remove: async id => { await API.del(`/api/admin/hotels/${id}`); U.confirmRemove = null; flash("Hotel removed.", "warn"); await load(); },
  reviewed: async id => { await API.post(`/api/admin/updates/${id}/reviewed`); await load(); },
  chat: () => { U.chatOpen = !U.chatOpen; },
  lang: id => { U.lang = id; persist(); },
  speak: () => { U.speak = !U.speak; if (!U.speak) try { speechSynthesis.cancel(); } catch (e) { /* ignore */ } },
  ask: id => { ask(id); return "skip"; },
  mic: () => { listen(); return "skip"; },
};
function keepForm() {
  const f = document.querySelector('form[data-form="search"]'); if (!f) return;
  const s = U.search;
  if (f.district) s.district = f.district.value;
  s.budget = f.budget.value; s.guests = f.guests.value; s.ci = f.ci.value; s.co = f.co.value;
  s.wants = [...f.querySelectorAll("input[name=wants]:checked")].map(x => x.value);
}
async function refreshSearch() { try { await doSearch(); } catch (e) { U.searchErr = e.message; } render(); }

/* ---------- forms ---------- */
const F = {
  login: async f => {
    try { const r = await API.post("/api/auth/login", { email: f.email.value, password: f.pass.value, role: U.loginRole });
      API.setToken(r.token); U.user = r.user; U.loginErr = ""; persist(); D.results = null; await load(); }
    catch (e) { U.loginErr = e.message; }
  },
  register: async f => {
    try { const r = await API.post("/api/auth/register", { name: f.name.value, email: f.email.value, password: f.pass.value });
      API.setToken(r.token); U.user = r.user; U.showRegister = false; persist(); flash(`Welcome, ${esc(r.user.name)}! Your guest account is ready.`); await load(); }
    catch (e) { U.loginErr = e.message; }
  },
  registerHotel: async f => {
    try { const r = await API.post("/api/auth/register-hotel", { name: f.name.value, email: f.email.value, password: f.pass.value, hotel_name: f.hotel.value,
        district: f.district.value, area: f.area.value, phone: f.phone.value, price: +f.price.value, rooms: +f.rooms.value,
        amenities: [...f.querySelectorAll("input[name=amen]:checked")].map(x => x.value) });
      API.setToken(r.token); U.user = r.user; U.showRegister = false; U.stab = "details"; U.staffHotel = r.user.hotel_id; persist();
      flash(`Welcome, ${esc(r.user.name)}! Your hotel is registered and waiting for verification. Add your facility details below.`); await load(); }
    catch (e) { U.loginErr = e.message; }
  },
  search: async f => {
    keepForm();
    const s = U.search;
    if (!s.gps && !s.district) { U.searchErr = "Choose a district or use your location."; return; }
    if (!(+s.budget > 0)) { U.searchErr = "Enter your budget per night."; return; }
    if (!(+s.guests >= 1 && +s.guests <= 8)) { U.searchErr = "Enter the number of guests (1 to 8)."; return; }
    if (!s.ci || !s.co) { U.searchErr = "Choose your check-in and check-out dates."; return; }
    if (nights(s.ci, s.co) < 1) { U.searchErr = "Check-out must be at least one day after check-in."; return; }
    s.budget = +s.budget; s.guests = +s.guests;
    U.searchErr = ""; U.page = 0; U.view = null; U.compare = []; D.hotel = null;
    await doSearch(); U.searched = true; U.editSearch = false;
  },
  arrival: async f => { const code = f.code.value.trim().toUpperCase(); if (!code) return;
    const r = await API.get(`/api/staff/hotels/${U.staffHotel}/arrival/${encodeURIComponent(code)}`); U.arrival = { code, ...r }; },
  fac: async f => { const code = f.dataset.id; const raw = f.count.value; const v = Number(raw);
    if (raw === "" || !Number.isInteger(v)) { U.facMsg[code] = { ok: false, t: "Enter a whole number." }; return; }
    try { await API.put(`/api/staff/hotels/${U.staffHotel}/facilities/${code}`, { count: v }); U.facMsg[code] = { ok: true, t: "Saved" }; }
    catch (e) { U.facMsg[code] = { ok: false, t: e.message }; }
    await load(); },
  details: async f => {
    const body = { phone: f.phone.value, website: f.website.value, amenities: [...f.querySelectorAll("input[name=amen]:checked")].map(x => x.value),
      rooms: D.staff.rooms.map(r => ({ id: r.id, price: +f["price-" + r.id].value, avail: +f["avail-" + r.id].value })),
      parking_watchman: f.pkw.value === "" ? null : f.pkw.value === "1", parking_cars: f.pkc.value === "" ? null : +f.pkc.value, parking_bikes: f.pkb.value === "" ? null : +f.pkb.value, wifi_info: f.wifi.value,
      facilities: D.staff.facilities.filter(x => x.code !== "reception").map(x => ({ code: x.code, open_hours: f["oh-" + x.code].value, staff_help: f["sh-" + x.code].value, equipment: f["eq-" + x.code].value, notes: f["nt-" + x.code].value })) };
    const file = f.photo.files && f.photo.files[0];
    if (file) { if (file.size > 300000) { flash("That photo is over 300 KB. Pick a smaller image.", "alert"); return; }
      body.photo = await new Promise(res => { const rd = new FileReader(); rd.onload = () => res(rd.result); rd.readAsDataURL(file); }); }
    const r = await API.put(`/api/staff/hotels/${U.staffHotel}`, body);
    U.detMsg = r.changes.length ? "Saved and sent to the Stays Admin for review." : "No changes to save."; await load(); },
  newhotel: async f => {
    await API.post("/api/staff/hotels", { name: f.name.value, district: f.district.value, area: f.area.value, phone: f.phone.value, price: +f.price.value, rooms: +f.rooms.value,
      amenities: [...f.querySelectorAll("input[name=amen]:checked")].map(x => x.value) });
    U.regMsg = `${f.name.value} was submitted. The Stays Admin will verify it before guests can see it.`; await load(); },
  feedback: async f => {
    const body = { comments: f.c.value };
    for (const c of FB) { const v = f.querySelector(`input[name=${c[0]}]:checked`); if (!v) { U.fbErr = "Please rate every item before sending."; return; } body[c[0]] = +v.value; }
    await API.post(`/api/bookings/${f.dataset.id}/feedback`, body); U.fbErr = ""; U.modal = null;
    flash("Thanks! Your feedback was sent to the hotel and the Stays Admin."); await load(); },
  afilter: async f => { U.adist = f.district.value; U.astat = f.status.value; U.aq = f.q.value.trim(); await load(); },
  staycode: async f => { U.stayCode = f.code.value.trim().toUpperCase(); U.sel = null; await load(); },
  chat: f => { const q = f.q.value; f.q.value = ""; ask(q); return "skip"; },
};

/* ---------- wiring ---------- */
async function runAction(fn, ...args) {
  if (U.busy) return; U.busy = true;
  try { const r = await fn(...args); if (r === "skip") return; }
  catch (e) { if (e.status === 401) signOutLocal(); flash(esc(e.message), "alert"); }
  finally { U.busy = false; }
  render();
}
document.addEventListener("click", e => {
  const b = e.target.closest("[data-act]"); if (!b) return;
  if (b.classList.contains("scrim") && e.target.closest("[data-stop]")) return;
  e.preventDefault();
  const fn = A[b.dataset.act]; if (fn) runAction(fn, b.dataset.id);
});
document.addEventListener("submit", e => { e.preventDefault(); const fn = F[e.target.dataset.form]; if (fn) runAction(fn, e.target); });
document.addEventListener("change", e => { if (e.target.dataset.change === "staffHotel") { U.staffHotel = +e.target.value; U.arrival = null; U.facMsg = {}; U.detMsg = ""; refresh(); } });
document.addEventListener("keydown", e => { if (e.key === "Escape" && U.modal) { U.modal = null; render(); } });
// Keep live views fresh: crowd every 60 s, notifications and bookings every 20 s.
setInterval(() => { if (U.user && U.user.role === "guest" && U.gtab === "inhotel" && !U.modal) refresh(); }, 60000);
setInterval(() => { if (U.user && U.user.role === "guest" && !U.modal && U.gtab !== "search" && U.gtab !== "inhotel" && !U.busy) refresh(); }, 20000);

if (!API.hasToken()) U.user = null;
render(); refresh();
})();