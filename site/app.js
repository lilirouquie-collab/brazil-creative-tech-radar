(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const PAGE = 40;
  const state = { view: "top", q: "", sector: "", uf: "", web: false, inova: false, city: "", shown: PAGE };
  let DATA = [], STATS = {}, META = {}, GEO = [], MAP_ROWS = [];
  const cityKey = (r) => `${r.cc || "BR"}|${r.c}|${r.uf}`;

  const fmtInt = (n) => (n || 0).toLocaleString("en-GB");
  const fmtDate = (iso) => iso ? new Date(iso + "T12:00:00").toLocaleDateString("en-GB",
    { day: "numeric", month: "short", year: "numeric" }) : "";
  const monthLabel = (ym, withYear) => {
    const d = new Date(ym + "-15T12:00:00");
    return d.toLocaleDateString("en-GB", withYear ? { month: "short", year: "numeric" } : { month: "short" });
  };
  const fmtCnpj = (c) => `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}`;
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v; else node.setAttribute(k, v);
    }
    for (const c of children.flat()) {
      if (c === null || c === undefined || c === false) continue;
      node.append(c.nodeType ? c : document.createTextNode(String(c)));
    }
    return node;
  }

  async function load() {
    const get = (name) => fetch(`data/${name}`, { cache: "no-cache" }).then((r) => r.ok ? r.json() : null);
    const [companies, stats, meta, picks] = await Promise.all(
      ["companies.json", "stats.json", "meta.json", "picks.json"].map(get));
    DATA = (companies || []).map((r) => ({ ...r, _q: norm([r.n, r.ln, r.c, r.uf, r.a, r.d, (r.s || []).join(" ")].join(" ")) }));
    STATS = stats || {}; META = meta || {};
    const countries = META.countries || ["BR"];
    GEO = (await Promise.all(countries.map((cc) => fetch(`geo/${cc.toLowerCase()}.json`)
      .then((r) => r.ok ? r.json() : null).catch(() => null)))).filter(Boolean);
    renderHeader(); renderKpis(); renderPicks(picks || {}); renderCharts(); setupFilters(); renderList();
    let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => { renderCharts(); renderMap(MAP_ROWS); }, 150); });
  }

  // ---------- header & figures ----------
  function renderHeader() {
    if (META.title) { $("title").textContent = META.title; document.title = META.title; }
    $("tagline").textContent = META.tagline || "";
    const parts = [];
    if (META.updated) parts.push(`Updated ${fmtDate(META.updated)}`);
    if (META.data_month) parts.push(`registry release ${monthLabel(META.data_month, true)}`);
    if (META.author) parts.push(`curated by ${META.author}`);
    $("meta").textContent = parts.join(" · ");
    $("m-window").textContent = META.window_months || 12;
    const foot = $("foot-author");
    foot.append(META.author_link ? el("a", { href: META.author_link }, META.author) : (META.author || ""),
      " · Updated every week from Receita Federal open data.");
  }

  function renderKpis() {
    $("k-total").textContent = fmtInt(STATS.total);
    $("k-week").textContent = fmtInt(DATA.filter((r) => r.nw || r.sn).length);
    $("k-online").textContent = fmtInt(STATS.online);
    $("k-inova").textContent = fmtInt(STATS.inova);
    if (STATS.scanned) $("k-note").textContent =
      `Selected from ${fmtInt(STATS.scanned)} companies opened in Brazil over the last ${META.window_months || 12} months and still active.`;
  }

  function renderPicks(picks) {
    const list = (picks && picks.picks) || [];
    if (!list.length) return;
    $("picks").hidden = false;
    $("picks-edition").textContent = picks.edition || "";
    const grid = $("picks-grid");
    for (const p of list) {
      const name = p.link ? el("a", { href: p.link, rel: "noopener", target: "_blank" }, p.name) : p.name;
      grid.append(el("article", { class: "pick" },
        p.sector ? el("div", { class: "sector" }, p.sector) : null,
        el("h3", {}, name), el("p", {}, p.note || "")));
    }
  }

  // ---------- charts ----------
  const SVG = "http://www.w3.org/2000/svg";
  function s(tag, attrs) {
    const n = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    return n;
  }
  function niceScale(v) {  // whole-number ticks: returns [max, step]
    const raw = Math.max(1, v / 4);
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 5, 10].map((m) => m * p).find((x) => x >= raw);
    return [Math.max(step, Math.ceil(v / step) * step), step];
  }
  function roundedTop(x, y, w, h, r) {  // bar with 4px rounded data-end, square at the baseline
    r = Math.min(r, w / 2, h);
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  }
  function roundedRight(x, y, w, h, r) {
    r = Math.min(r, h / 2, w);
    return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
  }
  const tip = $("tooltip");
  function showTip(evt, html) {
    tip.innerHTML = html; tip.hidden = false;
    const x = Math.min(window.innerWidth - tip.offsetWidth - 8, evt.clientX + 12);
    tip.style.left = `${Math.max(8, x)}px`;
    tip.style.top = `${Math.max(8, evt.clientY - tip.offsetHeight - 12)}px`;
  }
  const hideTip = () => { tip.hidden = true; };

  function monthSeries() {
    const months = STATS.months || [];
    if (!months.length) return [];
    const out = [];
    let [y, m] = months[0].split("-").map(Number);
    const last = months[months.length - 1];
    for (let guard = 0; guard < 60; guard++) {
      const ym = `${y}-${String(m).padStart(2, "0")}`;
      const counts = (STATS.by_month || {})[ym] || {};
      out.push({ ym, v: Object.values(counts).reduce((a, b) => a + b, 0), counts });
      if (ym === last) break;
      m++; if (m > 12) { m = 1; y++; }
    }
    return out;
  }

  function renderCharts() {
    const series = monthSeries();
    const box = $("chart-month");
    box.innerHTML = "";
    const table = $("table-month");
    table.innerHTML = "<tr><th>Month</th><th>Companies</th></tr>";
    if (!series.length) { box.append(el("p", { class: "muted" }, "No data yet.")); }
    else {
      const W = Math.max(280, box.clientWidth), H = 220, ml = 34, mr = 8, mt = 18, mb = 26;
      const iw = W - ml - mr, ih = H - mt - mb;
      const [max, step] = niceScale(Math.max(...series.map((d) => d.v)));
      const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, height: H });
      for (let val = 0; val <= max; val += step) {
        const y = mt + ih - (val / max) * ih;
        svg.append(s("line", { x1: ml, x2: W - mr, y1: y, y2: y, class: "grid" }));
        const t = s("text", { x: ml - 6, y: y + 4, "text-anchor": "end" }); t.textContent = fmtInt(val); svg.append(t);
      }
      const band = iw / series.length, bw = Math.max(4, Math.min(36, band * 0.62));
      const maxIdx = series.reduce((b, d, i, a) => d.v > a[b].v ? i : b, 0);
      const lastFull = series.length - 2;
      series.forEach((d, i) => {
        const x = ml + band * i + (band - bw) / 2, h = (d.v / max) * ih, y = mt + ih - h;
        const partial = i === series.length - 1 && d.ym === STATS.partial_month;
        const g = s("g", { class: "col" });
        const hit = s("rect", { x: ml + band * i, y: mt, width: band, height: ih, class: "hit", tabindex: 0 });
        const bar = s("path", { d: h > 0 ? roundedTop(x, y, bw, h, 4) : "", class: "bar", opacity: partial ? 0.45 : 1 });
        const label = `<strong>${monthLabel(d.ym, true)}</strong><br>${fmtInt(d.v)} companies${partial ? " (month still filling in)" : ""}`;
        hit.addEventListener("mousemove", (e) => showTip(e, label));
        hit.addEventListener("mouseleave", hideTip);
        hit.addEventListener("focus", () => { const r = hit.getBoundingClientRect(); showTip({ clientX: r.left, clientY: r.top + 20 }, label); });
        hit.addEventListener("blur", hideTip);
        g.append(bar, hit);
        svg.append(g);
        const showYear = i === 0 || d.ym.endsWith("-01");
        if (series.length <= 14 || i % 2 === 0) {
          const t = s("text", { x: x + bw / 2, y: H - 8, "text-anchor": "middle" });
          t.textContent = monthLabel(d.ym, false) + (showYear ? ` ’${d.ym.slice(2, 4)}` : "");
          svg.append(t);
        }
        if (i === maxIdx || i === lastFull) {
          const t = s("text", { x: x + bw / 2, y: y - 5, "text-anchor": "middle", class: "value" });
          t.textContent = fmtInt(d.v); svg.append(t);
        }
        table.append(el("tr", {}, el("td", {}, monthLabel(d.ym, true) + (partial ? " (partial)" : "")), el("td", {}, fmtInt(d.v))));
      });
      box.append(svg);
    }

    // sector bar list
    const sb = $("chart-sector");
    sb.innerHTML = "";
    const rows = Object.entries(STATS.by_sector || {}).sort((a, b) => b[1] - a[1]);
    if (rows.length) {
      const W = Math.max(260, sb.clientWidth), rowH = 26, H = rows.length * rowH + 4, lw = 118, vw = 44;
      const max = Math.max(...rows.map((r) => r[1]));
      const total = rows.reduce((a, r) => a + r[1], 0);
      const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, height: H });
      rows.forEach(([name, v], i) => {
        const y = i * rowH + 4, bh = 14, w = Math.max(2, ((W - lw - vw) * v) / max);
        const t = s("text", { x: 0, y: y + 11, class: "label" }); t.textContent = name; svg.append(t);
        svg.append(s("path", { d: roundedRight(lw, y, w, bh, 4), class: "bar" }));
        const vt = s("text", { x: lw + w + 6, y: y + 11, class: "value" }); vt.textContent = fmtInt(v); svg.append(vt);
        const hit = s("rect", { x: 0, y: y - 5, width: W, height: rowH, class: "hit" });
        const label = `<strong>${name}</strong><br>${fmtInt(v)} companies · ${Math.round((v / total) * 100)}% of sector tags`;
        hit.addEventListener("mousemove", (e) => showTip(e, label));
        hit.addEventListener("mouseleave", hideTip);
        svg.append(hit);
      });
      sb.append(svg);
    }
    const st = Object.entries(STATS.by_state || {}).slice(0, 8);
    $("states").textContent = st.length ? "Top states: " + st.map(([uf, n]) => `${uf} ${fmtInt(n)}`).join(" · ") : "";
  }

  // ---------- map ----------
  function projector(width) {
    let minLon = 180, maxLon = -180, minLat = 90, maxLat = -90;
    const visit = (c) => { if (typeof c[0] === "number") { minLon = Math.min(minLon, c[0]); maxLon = Math.max(maxLon, c[0]); minLat = Math.min(minLat, c[1]); maxLat = Math.max(maxLat, c[1]); } else c.forEach(visit); };
    GEO.forEach((g) => g.features.forEach((f) => visit(f.geometry.coordinates)));
    const k = Math.cos(((minLat + maxLat) / 2) * Math.PI / 180);  // keeps shapes from stretching
    const pad = 8, w = (maxLon - minLon) * k, h = maxLat - minLat;
    const scale = (width - 2 * pad) / w;
    const height = Math.min(560, h * scale + 2 * pad);
    const sc = Math.min(scale, (height - 2 * pad) / h);
    const ox = (width - w * sc) / 2;
    const project = (lon, lat) => [ox + (lon - minLon) * k * sc, pad + (maxLat - lat) * sc];
    return { project, height };
  }

  function geoPath(geom, project) {
    const ring = (r) => r.map((c, i) => { const [x, y] = project(c[0], c[1]); return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`; }).join("") + "Z";
    const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.type === "MultiPolygon" ? geom.coordinates : [];
    return polys.map((p) => p.map(ring).join("")).join("");
  }

  function renderMap(rows) {
    const box = $("map");
    box.innerHTML = "";
    if (!GEO.length) { box.append(el("p", { class: "muted" }, "Map unavailable.")); return; }
    const W = Math.max(280, box.clientWidth);
    const { project, height } = projector(W);
    const svg = s("svg", { viewBox: `0 0 ${W} ${height}`, height });
    GEO.forEach((g) => g.features.forEach((f) => svg.append(s("path", { d: geoPath(f.geometry, project), class: "state" }))));

    const groups = new Map();
    for (const r of rows) {
      if (r.lat === null || r.lat === undefined) continue;
      const key = cityKey(r);
      let g = groups.get(key);
      if (!g) { g = { key, c: r.c, uf: r.uf, lat: r.lat, lon: r.lon, n: 0, sectors: {} }; groups.set(key, g); }
      g.n++;
      for (const x of r.s || []) g.sectors[x] = (g.sectors[x] || 0) + 1;
    }
    const cities = [...groups.values()].sort((a, b) => b.n - a.n);
    const max = cities.length ? cities[0].n : 1;
    const rMax = Math.max(14, Math.min(30, W / 22)), rMin = 2.5;
    const radius = (n) => rMin + (rMax - rMin) * Math.sqrt(n / max);
    const dimOthers = Boolean(state.city);
    for (const g of cities) {  // biggest first, so small cities stay visible on top
      [g.x, g.y] = project(g.lon, g.lat);
      g.r = radius(g.n);
      const cls = "bubble" + (state.city === g.key ? " selected" : dimOthers ? " dim" : "");
      svg.append(s("circle", { cx: g.x, cy: g.y, r: g.r, class: cls }));
    }
    // One hit layer: the city whose centre is nearest the pointer wins, so a big
    // city stays clickable even when small neighbours sit on top of it.
    const pick = (evt) => {
      const pt = svg.getBoundingClientRect(), sx = W / pt.width;
      const px = (evt.clientX - pt.left) * sx, py = (evt.clientY - pt.top) * sx;
      let best = null, bestD = Infinity;
      for (const g of cities) {
        const d = Math.hypot(g.x - px, g.y - py);
        if (d <= Math.max(g.r, 8) && d < bestD) { best = g; bestD = d; }
      }
      return best;
    };
    const layer = s("rect", { x: 0, y: 0, width: W, height, class: "hit" });
    layer.addEventListener("mousemove", (e) => {
      const g = pick(e);
      layer.style.cursor = g ? "pointer" : "default";
      if (!g) return hideTip();
      const top = Object.entries(g.sectors).sort((a, b) => b[1] - a[1])[0];
      showTip(e, `<strong>${esc(g.c)}, ${esc(g.uf)}</strong><br>${fmtInt(g.n)} ${g.n === 1 ? "company" : "companies"}` +
        (top ? `<br>Top sector: ${esc(top[0])} (${fmtInt(top[1])})` : "") +
        `<br><em>Click to ${state.city === g.key ? "clear" : "filter"}</em>`);
    });
    layer.addEventListener("mouseleave", hideTip);
    layer.addEventListener("click", (e) => { const g = pick(e); if (g) { hideTip(); setCity(g.key); } });
    svg.append(layer);
    // size legend
    if (cities.length) {
      const vals = [...new Set([max, Math.round(max / 10), 1].filter((v) => v >= 1))];
      let lx = 12;
      const ly = height - 12;
      vals.forEach((v) => {
        const r = radius(v);
        svg.append(s("circle", { cx: lx + r, cy: ly - r, r, class: "legend-circle" }));
        const t = s("text", { x: lx + r, y: ly + 11, "text-anchor": "middle" }); t.textContent = fmtInt(v);
        svg.append(t);
        lx += 2 * r + 14;
      });
    }
    box.append(svg);

    const list = $("cities");
    list.innerHTML = "";
    if (!cities.length) list.append(el("li", { class: "muted" }, "No company to place."));
    for (const g of cities.slice(0, 10)) {
      const b = el("button", { "aria-pressed": String(state.city === g.key) },
        el("span", {}, `${g.c}, ${g.uf}`), el("span", {}, fmtInt(g.n)));
      b.addEventListener("click", () => setCity(g.key));
      list.append(el("li", {}, b));
    }
  }

  // ---------- explorer ----------
  function setupFilters() {
    const sectors = [...new Set(DATA.flatMap((r) => r.s || []))].sort();
    for (const x of sectors) $("f-sector").append(el("option", { value: x }, x));
    const ufs = [...new Set(DATA.map((r) => r.uf).filter(Boolean))].sort();
    for (const x of ufs) $("f-state").append(el("option", { value: x }, x));
    document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
      state.view = b.dataset.view; state.shown = PAGE; renderList();
    }));
    let t;
    $("q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { state.q = norm(e.target.value.trim()); state.shown = PAGE; renderList(); }, 120); });
    $("f-sector").addEventListener("change", (e) => { state.sector = e.target.value; state.shown = PAGE; renderList(); });
    $("f-state").addEventListener("change", (e) => { state.uf = e.target.value; state.shown = PAGE; renderList(); });
    for (const [id, key] of [["f-web", "web"], ["f-inova", "inova"]]) {
      $(id).addEventListener("click", (e) => {
        state[key] = !state[key]; e.currentTarget.setAttribute("aria-pressed", String(state[key]));
        state.shown = PAGE; renderList();
      });
    }
    $("more").addEventListener("click", () => { state.shown += PAGE; renderList(); });
    $("f-city").addEventListener("click", () => setCity(""));
  }

  function setCity(key) {
    state.city = state.city === key ? "" : key;
    state.shown = PAGE;
    const chip = $("f-city");
    chip.hidden = !state.city;
    if (state.city) { const [, c, uf] = state.city.split("|"); chip.textContent = `${c}, ${uf}`; chip.setAttribute("aria-label", `Remove city filter ${c}`); }
    renderList();
  }

  function filtered(ignoreCity) {
    let rows = DATA.filter((r) =>
      (ignoreCity || !state.city || cityKey(r) === state.city) &&
      (!state.q || r._q.includes(state.q)) &&
      (!state.sector || (r.s || []).includes(state.sector)) &&
      (!state.uf || r.uf === state.uf) &&
      (!state.web || ["live", "social"].includes(r.ws)) &&
      (!state.inova || r.inv));
    if (state.view === "week") rows = rows.filter((r) => r.nw || r.sn);
    if (state.view === "recent") rows = [...rows].sort((a, b) => b.o.localeCompare(a.o) || b.sc - a.sc);
    return rows;
  }

  const REASONS = { activities: "Tech + creative activities", name: "Name signal", inova: "Inova Simples" };

  function item(r) {
    const site = r.w && ["live", "social", "soon"].includes(r.ws)
      ? el("a", { href: r.w, rel: "noopener nofollow", target: "_blank" },
          r.ws === "live" ? "Website" : r.ws === "social" ? "Social page" : "Website (coming soon)")
      : null;
    const q = encodeURIComponent(r.n);
    const links = el("span", { class: "links" },
      site,
      r.ig ? el("a", { href: r.ig, rel: "noopener nofollow", target: "_blank" }, "Instagram") : null,
      r.li ? el("a", { href: r.li, rel: "noopener nofollow", target: "_blank" }, "LinkedIn")
           : el("a", { href: `https://www.linkedin.com/search/results/companies/?keywords=${q}`, rel: "noopener nofollow", target: "_blank" }, "Search LinkedIn"),
      el("a", { href: `https://www.google.com/search?q=${encodeURIComponent(`"${r.n}" ${r.c}`)}`, rel: "noopener nofollow", target: "_blank" }, "Search the web"));
    const flags = [];
    if (r.nw) flags.push(el("span", { class: "chip flag" }, "New this week"));
    if (r.sn) flags.push(el("span", { class: "chip flag" }, "Website just went live"));
    const sub = [r.c && r.uf ? `${r.c}, ${r.uf}` : r.uf, `opened ${fmtDate(r.o)}`,
                 r.cap ? `capital R$ ${fmtInt(Math.round(r.cap))}` : null].filter(Boolean).join(" · ");
    return el("li", { class: "item" },
      el("div", {}, el("h3", {}, r.n), el("div", { class: "sub" }, sub)),
      el("span", { class: "score", title: "Score out of 10 (see How it works)" }, String(r.sc), el("small", {}, " /10")),
      r.d ? el("p", { class: "desc" }, r.d) : null,
      el("div", { class: "activity" }, `Registered activity: ${r.a || "–"} · CNPJ ${fmtCnpj(r.id)}`),
      el("div", { class: "row" },
        ...flags,
        ...(r.s || []).map((x) => el("span", { class: "chip" }, x)),
        ...(r.r || []).map((x) => el("span", { class: "chip" }, REASONS[x] || x)),
        links));
  }

  function renderList() {
    const rows = filtered();
    MAP_ROWS = filtered(true);
    renderMap(MAP_ROWS);
    const list = $("list");
    list.innerHTML = "";
    const n = rows.length;
    $("count").textContent = `${fmtInt(n)} ${n === 1 ? "company" : "companies"}`;
    if (!n) {
      list.append(el("li", { class: "empty" }, state.view === "week"
        ? "Nothing new this week yet. New registry data arrives once a month; websites are checked every week."
        : "No company matches these filters."));
    }
    rows.slice(0, state.shown).forEach((r) => list.append(item(r)));
    $("more").hidden = state.shown >= n;
  }

  load().catch((e) => {
    $("list").append(el("li", { class: "empty" }, "The data could not be loaded. Please try again later."));
    console.error(e);
  });
})();
