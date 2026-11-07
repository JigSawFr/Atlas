// The explorer (explore/): Atlas's data as tools/site_data.py cut it
// under x/, read from this site, a file when a view needs it and kept for
// the visit. The address says what is shown, so it can be shared:
//   #<platform>/<popular|trending|upcoming>    a list
//   #<platform>/browse?<facet>=<value>&…&sort=<key>
//                                              the games with every value picked, a page at a time
//   #<platform>/search/<words>                 the games whose name has them
//   #<platform>/game/<id>                      a game's sheet
// The texts are the page's (#x-strings, the catalog's x_ keys).
(function () {
  const $ = (id) => document.getElementById(id);
  const S = JSON.parse($("x-strings").textContent);
  const ROOT = document.body.dataset.root || "";
  const LANG = document.documentElement.lang || "en";
  const PLATFORMS = Object.keys(S._platforms);
  const STORES = {
    steam: (id) => `https://store.steampowered.com/app/${id}/`,
    ps: (id) => `https://store.playstation.com/concept/${id}`,
    xbox: (id) => `https://www.xbox.com/games/store/-/${id}`,
    gog: (id) => `https://www.gog.com/game/${id}`,
    epic: (id) => `https://store.epicgames.com/p/${id}`,
  };
  const STORE_NAMES = { switch: "Nintendo Switch", steam: "Steam", ps: "PlayStation", ps_product: "PlayStation",
    ps4: "PlayStation 4", ps5: "PlayStation 5", "3ds": "Nintendo 3DS",
    xbox: "Xbox", gog: "GOG", epic: "Epic Games" };
  const status = $("x-status"), results = $("x-results"), sheet = $("x-sheet");
  const search = $("x-search"), machine = $("x-machine");
  const panel = $("x-browse"), facetBox = $("x-facets"), sortBox = $("x-sort");
  const more = $("x-more"), loadAll = $("x-loadall");
  const cache = new Map();
  let read = 0;

  const t = (key, values) => {
    let s = S[key] || "";
    for (const [k, v] of Object.entries(values || {})) s = s.split(`{${k}}`).join(v);
    return s;
  };
  const el = (tag, attrs, ...children) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v);
    }
    for (const c of children.flat()) if (c !== null && c !== undefined && c !== "") e.append(c);
    return e;
  };
  const nf = new Intl.NumberFormat(LANG);
  const num = (n) => nf.format(n);
  const ymd = (n) => {
    if (!n) return "";
    const s = String(n);
    const d = new Date(Date.UTC(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8)));
    return new Intl.DateTimeFormat(LANG, { dateStyle: "medium", timeZone: "UTC" }).format(d);
  };
  const kb = (bytes) => {
    const unit = /^fr/.test(LANG) ? ["ko", "Mo"] : LANG === "ru" ? ["КБ", "МБ"] : ["kB", "MB"];
    return bytes < 1e6 ? `${num(Math.max(1, Math.round(bytes / 1000)))} ${unit[0]}`
      : `${new Intl.NumberFormat(LANG, { maximumFractionDigits: 1 }).format(bytes / 1e6)} ${unit[1]}`;
  };
  const shard = (id, shards) => {
    let h = 0;
    for (const c of id) h = (Math.imul(h, 31) + c.charCodeAt(0)) >>> 0;
    return h % shards;
  };
  const fold = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  // The notions the data names once for every source (genres, themes, modes, perspectives) have a
  // name in the page's language and an icon (x_<letter>_<key>, #i-<letter>-<key>); the other
  // values (series, studios, tags) are the sources' own words.
  const NOTION = { genres: "g", themes: "t", modes: "m", perspectives: "p" };
  const labelOf = (kind, value) => (NOTION[kind] && S[`x_${NOTION[kind]}_${value}`]) || value;
  const SVG = "http://www.w3.org/2000/svg";
  function icon(id) {
    if (!id || !document.getElementById(id)) return null;
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("class", "ico");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const use = document.createElementNS(SVG, "use");
    use.setAttribute("href", `#${id}`);
    svg.append(use);
    return svg;
  }
  const iconOf = (kind, value) => icon(NOTION[kind] ? `i-${NOTION[kind]}-${value}` : null);
  const chip = (kind, value) => el("span", { class: "chip" }, iconOf(kind, value), labelOf(kind, value));

  async function get(path) {
    if (cache.has(path)) return cache.get(path);
    const p = fetch(ROOT + path).then(async (r) => {
      if (!r.ok) throw new Error(`${path}: ${r.status}`);
      const text = await r.text();
      read += text.length;
      return JSON.parse(text);
    });
    cache.set(path, p);
    p.catch(() => cache.delete(path));
    return p;
  }

  // The address, read and written.
  function route() {
    const raw = location.hash.slice(1), q = raw.indexOf("?");
    const parts = decodeURIComponent(q < 0 ? raw : raw.slice(0, q)).split("/");
    const platform = PLATFORMS.includes(parts[0]) ? parts[0] : PLATFORMS[0];
    const view = ["browse", "popular", "trending", "upcoming", "search", "game"].includes(parts[1]) ? parts[1] : "popular";
    return { platform, view, arg: parts.slice(2).join("/"), query: new URLSearchParams(q < 0 ? "" : raw.slice(q + 1)) };
  }
  const go = (hash) => { if (location.hash !== hash) location.hash = hash; else show(); };

  function pressed(group, attr, value) {
    for (const b of document.querySelectorAll(`#${group} button`)) b.setAttribute("aria-pressed", String(b.dataset[attr] === value));
  }

  function setStatus(text) {
    status.textContent = text;
  }

  function nameOf(id, name, platform) {
    return name ? el("span", { class: "name", text: name })
      : el("span", { class: "name none" }, el("code", { text: id }), el("small", { text: t("x_no_name") }));
  }

  function row(platform, id, name, meta, extra) {
    return el("li", {}, el("a", { href: `#${platform}/game/${encodeURIComponent(id)}` },
      nameOf(id, name, platform), el("span", { class: "meta" }, ...meta), extra || null));
  }

  function trend(v) {
    if (!v) return null;
    return el("span", { class: v > 0 ? "trend up" : "trend down", text: `${v > 0 ? "+" : ""}${num(v)} %` });
  }

  function score(v) {
    return el("span", { class: "score", title: t("x_score") }, el("span", { class: "bar" }, el("i", { "data-w": String(v) })), String(v));
  }

  // Bars drawn without style attributes (the Content-Security-Policy): a
  // width from data-w, set by script, which the CSP allows.
  function bars(root) {
    for (const i of root.querySelectorAll("i[data-w]")) i.style.width = `${Math.max(2, Math.min(100, +i.dataset.w))}%`;
  }

  async function list(platform, view) {
    leaveBrowse();
    sheet.hidden = true;
    results.hidden = false;
    pressed("x-views", "view", view);
    setStatus(t("x_loading"));
    const lists = await get(`x/${platform}/lists.json`);
    results.replaceChildren();
    let note = "", count = 0;
    if (view === "upcoming") {    } else if (view === "upcoming") {
      for (const [id, name, when] of lists.upcoming) results.append(row(platform, id, name, [el("span", { class: "date", text: ymd(when) })]));
      count = lists.upcoming.length;
      note = t("x_upcoming_note");
    } else {
      const rows = lists[view] || [];
      for (const [id, name, s, tr, critics] of rows) {
        results.append(row(platform, id, name, [score(s), trend(tr),
          critics ? el("span", { class: "dim", text: `${t("x_critics")} ${critics}` }) : null]));
      }
      count = rows.length;
      note = t(view === "trending" ? "x_trending_note" : "x_popular_note");
    }
    bars(results);
    setStatus(`${note} ${t("x_count", { n: num(count) })} · ${t("x_loaded", { size: kb(read) })}`);
  }

  async function find(platform, words) {
    leaveBrowse();
    sheet.hidden = true;
    results.hidden = false;
    pressed("x-views", "view", "");
    const q = fold(words.trim());
    if (!q) return go(`#${platform}/popular`);
    if (/^[0-9a-f]{16}$/i.test(q) || (platform === "steam" && /^\d+$/.test(q))) {
      return go(`#${platform}/game/${platform === "switch" ? q.toUpperCase() : q}`);
    }
    setStatus(t("x_loading"));
    const names = await get(`x/${platform}/names.json`);
    const found = [];
    for (const [id, name, s] of names) {
      if (fold(name).includes(q)) found.push([id, name, s]);
      if (found.length >= 200) break;
    }
    results.replaceChildren(...found.map(([id, name, s]) => row(platform, id, name, [score(s)])));
    bars(results);
    setStatus((found.length ? t("x_count", { n: num(found.length) }) : t("x_nothing")) + ` · ${t("x_loaded", { size: kb(read) })}`);
  }

  function section(title, ...content) {
    return el("section", {}, el("h3", { text: title }), ...content);
  }

  async function game(platform, id) {
    leaveBrowse();
    results.hidden = true;
    pressed("x-views", "view", "");
    setStatus(t("x_loading"));
    const lists = await get(`x/${platform}/lists.json`);
    const part = await get(`x/${platform}/g/${shard(id, lists.shards)}.json`);
    const g = part[id];
    sheet.replaceChildren();
    sheet.hidden = false;
    const back = el("a", { class: "back", href: lastBrowse.startsWith(`#${platform}/browse`) ? lastBrowse : `#${platform}/popular` }, `← ${t("x_back")}`);
    if (!g) {
      sheet.append(back, el("p", { text: t("x_not_found") }));
      setStatus("");
      return;
    }
    const head = el("header", {}, back,
      el("h2", { tabindex: "-1" }, g.name || id),
      el("p", { class: "ids" }, el("span", { class: "badge", text: S._names[platform] }), g.name ? el("code", { text: id }) : null,
        g.qid ? el("a", { href: `https://www.wikidata.org/wiki/${g.qid}`, rel: "noreferrer noopener", referrerpolicy: "no-referrer", text: g.qid }) : null,
        !g.name ? el("small", { text: t("x_no_name") }) : null));
    sheet.append(head);

    const stats = el("dl", { class: "stats" });
    const stat = (label, value) => { if (value !== null && value !== undefined && value !== "") stats.append(el("div", {}, el("dt", { text: label }), el("dd", {}, value))); };
    if (g.popular) {
      stat(t("x_score"), score(g.popular[0]));
      if (g.popular[1]) stat(t("x_trend"), trend(g.popular[1]));
      if (g.popular[2]) stat(t("x_critics"), `${g.popular[2]} / 100`);
    }
    if (g.reviews) stat("Steam", t("x_reviews", { n: num(g.reviews[0]), p: g.reviews[1] }));
    if (g.igdb_rating && g.igdb_rating[1] >= 20) stat(t("x_players_rating"), `${g.igdb_rating[0]} / 100`);
    if (g.release) stat(t("x_release"), ymd(g.release));
    if (g.upcoming) stat(t("x_release"), t("x_coming", { date: ymd(g.upcoming) }));
    if (stats.childElementCount) sheet.append(stats);
    if (g.steam && (g.steam.owners || g.steam.ccu)) {
      sheet.append(el("p", { class: "dim", text: t("x_steam_figures", { owners: num(g.steam.owners || 0), ccu: num(g.steam.ccu || 0) }) }));
    }

    if (g.traits) {
      const dl = el("dl", { class: "traits" });
      for (const [kind, names] of Object.entries(g.traits)) {
        dl.append(el("div", {}, el("dt", {}, icon(`i-k-${kind}`), t(`x_${kind}`)), el("dd", {}, ...names.map((n) => chip(kind, n)))));
      }
      sheet.append(dl);
    }

    if (g.similar && g.similar.length) {
      sheet.append(section(t("x_similar"), el("ol", { class: "similar" }, ...g.similar.map(([o, name, s]) =>
        el("li", {}, el("a", { href: `#${platform}/game/${encodeURIComponent(o)}` }, nameOf(o, name, platform)), el("span", { class: "dim", text: `${s}` }))))));
    }
    if (g.edition_of) {
      const [o, name] = g.edition_of;
      sheet.append(section(t("x_edition_of"), el("p", {}, el("a", { href: `#${platform}/game/${encodeURIComponent(o)}` }, nameOf(o, name, platform)))));
    }
    if (g.editions) {
      sheet.append(section(t("x_editions"), el("ul", { class: "similar" }, ...g.editions.map(([o, name]) =>
        el("li", {}, el("a", { href: `#${platform}/game/${encodeURIComponent(o)}` }, nameOf(o, name, platform)))))));
    }
    if (g.links && Object.keys(g.links).length) {
      const items = [];
      for (const [p, ids] of Object.entries(g.links)) {
        if (p === "ps_product") continue;
        for (const other of ids) {
          const inData = PLATFORMS.includes(p) && p !== platform;
          items.push(el("li", {}, el("span", { class: "badge", text: STORE_NAMES[p] || p }),
            inData ? el("a", { href: `#${p}/game/${encodeURIComponent(other)}` }, el("code", { text: other }))
              : el("code", { text: other }),
            STORES[p] ? el("a", { class: "out", href: STORES[p](other), rel: "noreferrer noopener", referrerpolicy: "no-referrer", text: "↗", "aria-label": `${STORE_NAMES[p]} ${other}` }) : null));
        }
      }
      if (items.length) sheet.append(section(t("x_other_platforms"), el("ul", { class: "links" }, ...items)));
    }
    bars(sheet);
    setStatus(t("x_loaded", { size: kb(read) }));
    head.querySelector("h2").focus({ preventScroll: true });
    window.scrollTo({ top: sheet.getBoundingClientRect().top + window.scrollY - 16 });
  }

  // Browsing: facets.json gives the menus, then the pages of games, best known
  // first, a page at a time. Every filter narrows (a game must have all the
  // values picked); the rows are filtered here, in the browser.
  const FACETS = ["genres", "modes", "series", "developers", "publishers", "themes", "perspectives", "tags", "year"];
  const SORTS = ["popular", "trending", "critics", "year", "name"];
  const STEP = 50;
  let B = null;            // what is loaded of the platform being browsed
  let V = null;            // the games the filters keep, and how they are shown
  let limit = STEP;        // how many of them are listed
  let last = "";           // the filters of the last view, to start again from a first screen when they change
  let lastBrowse = "";     // where a sheet's back link goes
  let run = 0;

  function leaveBrowse() {
    panel.hidden = true;
    more.hidden = true;
  }

  async function browseState(platform) {
    if (B && B.platform === platform) return B;
    const f = await get(`x/${platform}/facets.json`);
    B = { platform, f, rows: [], have: {}, index: {}, boxes: new Map(), loaded: 0, chain: Promise.resolve() };
    for (const [kind, values] of Object.entries(f.facets)) {
      B.have[kind] = values.map(() => []);
      B.index[kind] = new Map(values.map(([v], i) => [v, i]));
    }
    buildFacets(B);
    return B;
  }

  // The next page, after the ones already in (one at a time, in order).
  function loadPage(b) {
    const p = b.chain.then(async () => {
      if (b.loaded >= b.f.pages) return;
      const page = await get(`x/${b.platform}/browse/${b.loaded}.json`);
      const offset = b.rows.length;
      for (const r of page.games) b.rows.push(r);
      for (const [kind, found] of Object.entries(page.facets)) {
        for (const [number, gaps] of found) {
          let at = offset;
          const into = b.have[kind][number];
          gaps.forEach((gap, i) => { at = i ? at + gap : offset + gap; into.push(at); });
        }
      }
      b.loaded += 1;
    });
    b.chain = p.catch(() => {});
    return p;
  }

  function buildFacets(b) {
    facetBox.replaceChildren();
    for (const kind of FACETS) {
      const values = b.f.facets[kind];
      if (!values) continue;
      const options = [];
      const list = el("ul", { class: "options" });
      values.forEach(([value], i) => {
        const input = el("input", { type: "checkbox", "data-kind": kind, "data-i": String(i) });
        const n = el("small", { class: "n" });
        const name = labelOf(kind, value);
        const li = el("li", {}, el("label", {}, input, iconOf(kind, value), el("span", { class: "v", text: name }), n));
        options.push({ input, n, li, value, text: fold(`${name} ${value}`) });
        list.append(li);
      });
      const find = el("input", { type: "search", autocomplete: "off", spellcheck: "false", placeholder: t("x_find_value"), "aria-label": `${t(`x_${kind}`)}: ${t("x_find_value")}` });
      find.addEventListener("input", () => {
        const q = fold(find.value.trim());
        for (const o of options) o.li.hidden = !!q && !o.text.includes(q);
      });
      const title = el("span", { text: t(`x_${kind}`) });
      const summary = el("summary", {}, icon(`i-k-${kind}`), title);
      const details = el("details", { class: "facet" }, summary, el("div", { class: "facet-body" }, find, list));
      b.boxes.set(kind, { title, details, options });
      facetBox.append(details);
    }
  }

  // The filters in the address, as [kind, number] (and how many values the data does not know).
  function picked(b, query) {
    const found = new Set();
    let unknown = 0;
    for (const kind of FACETS) {
      for (const value of query.getAll(kind)) {
        const n = b.index[kind] && b.index[kind].get(value);
        if (n === undefined) unknown += 1; else found.add(`${kind}\t${n}`);
      }
    }
    return { found: [...found].map((k) => { const [kind, n] = k.split("\t"); return [kind, +n]; }), unknown };
  }

  function sorted(b, ids, how) {
    if (how === "popular") return ids;       // the rows come best known first
    const R = b.rows;
    if (how === "name") {
      const c = new Intl.Collator(LANG);
      return ids.slice().sort((x, y) => c.compare(R[x][1], R[y][1]) || x - y);
    }
    const col = { trending: 3, critics: 4, year: 5 }[how];
    return ids.slice().sort((x, y) => (R[y][col] - R[x][col]) || x - y);
  }

  // The games (rows of what is loaded) with every value picked, in the order asked.
  function compute(b, query) {
    const { found, unknown } = picked(b, query);
    const how = SORTS.includes(query.get("sort")) ? query.get("sort") : "popular";
    const n = b.rows.length, mask = new Uint8Array(n), ids = [];
    if (!unknown) {
      if (!found.length) mask.fill(1);
      else {
        const hits = new Uint8Array(n);
        for (const [kind, number] of found) for (const i of b.have[kind][number]) hits[i] += 1;
        for (let i = 0; i < n; i++) if (hits[i] === found.length) mask[i] = 1;
      }
      for (let i = 0; i < n; i++) if (mask[i]) ids.push(i);
    }
    return { query, how, found, unknown, mask, ids: sorted(b, ids, how) };
  }

  const hashOf = (platform, params) => {
    const q = params.toString();
    return `#${platform}/browse${q ? `?${q}` : ""}`;
  };

  // The menus follow the address: boxes ticked, counts of what is left, values with no game left dimmed.
  function syncFacets(b, v) {
    const on = new Set(v.found.map(([kind, n]) => `${kind}\t${n}`));
    const partial = b.loaded < b.f.pages;
    sortBox.value = v.how;
    for (const [kind, box] of b.boxes) {
      let chosen = 0;
      box.options.forEach((o, i) => {
        const checked = on.has(`${kind}\t${i}`);
        o.input.checked = checked;
        chosen += checked ? 1 : 0;
        let count = b.f.facets[kind][i][1];
        if (v.found.length) {
          count = 0;
          for (const r of b.have[kind][i]) count += v.mask[r];
        }
        o.n.textContent = v.found.length && partial ? `≥ ${num(count)}` : num(count);
        o.li.classList.toggle("empty", !count && !checked && !partial);
        o.input.disabled = !count && !checked && !partial;
      });
      box.title.textContent = chosen ? `${t(`x_${kind}`)} · ${chosen}` : t(`x_${kind}`);
      if (chosen && !box.details.open) box.details.open = true;
    }
  }

  function draw(b) {
    const { ids, found, how } = V;
    results.replaceChildren(...ids.slice(0, limit).map((i) => {
      const [id, name, s, tr, critics, year] = b.rows[i];
      return row(b.platform, id, name, [score(s), trend(tr),
        critics ? el("span", { class: "dim", text: `${t("x_critics")} ${critics}` }) : null,
        year ? el("span", { class: "dim", text: String(year) }) : null]);
    }));
    bars(results);
    syncFacets(b, V);
    const partial = b.loaded < b.f.pages;
    const total = found.length ? (partial ? `≥ ${num(ids.length)}` : num(ids.length)) : num(b.f.games);
    const parts = [ids.length || !partial ? t("x_count_of", { shown: num(Math.min(limit, ids.length)), n: total }) : ""];
    if (partial && (found.length || how !== "popular")) parts.push(t("x_browse_partial", { loaded: num(b.rows.length), total: num(b.f.games) }));
    parts.push(t("x_loaded", { size: kb(read) }));
    setStatus(parts.filter(Boolean).join(" · "));
    more.hidden = !(ids.length > limit || partial);
    loadAll.hidden = !(partial && how !== "popular");
    if (!ids.length && !partial) setStatus(`${t("x_nothing")} · ${t("x_loaded", { size: kb(read) })}`);
  }

  // Pages are fetched while the games kept are fewer than the list wants.
  async function fill(b, mine) {
    while (!V.unknown && V.ids.length < limit && b.loaded < b.f.pages) {
      setStatus(t("x_loading"));
      await loadPage(b);
      if (mine !== run) return false;
      V = compute(b, V.query);
    }
    return true;
  }

  async function browse(platform, query) {
    const mine = ++run;
    sheet.hidden = true;
    results.hidden = false;
    panel.hidden = false;
    pressed("x-views", "view", "browse");
    lastBrowse = location.hash;
    setStatus(t("x_loading"));
    const b = await browseState(platform);
    if (mine !== run) return;
    if (!b.f.pages) {
      results.replaceChildren();
      panel.hidden = true;
      more.hidden = true;
      setStatus(t("x_nothing"));
      return;
    }
    const key = query.toString();
    if (key !== last) { limit = STEP; last = key; }
    if (!b.loaded) await loadPage(b);
    if (mine !== run) return;
    V = compute(b, query);
    if (!(await fill(b, mine))) return;
    draw(b);
  }

  // The filters ticked, as the address that shows them.
  function address() {
    const params = new URLSearchParams();
    for (const [kind, box] of B.boxes) for (const o of box.options) if (o.input.checked) params.append(kind, o.value);
    if (sortBox.value !== "popular") params.set("sort", sortBox.value);
    return hashOf(B.platform, params);
  }

  async function guarded(work) {
    try { await work(); } catch (e) { setStatus(t("x_error")); }
  }

  facetBox.addEventListener("change", (e) => { if (B && e.target.matches("input[type=checkbox]")) go(address()); });
  sortBox.addEventListener("change", () => { if (B) go(address()); });
  $("x-clear").addEventListener("click", () => { if (B) go(hashOf(B.platform, new URLSearchParams())); });
  $("x-random").addEventListener("click", () => {
    if (B && V && V.ids.length) go(`#${B.platform}/game/${encodeURIComponent(B.rows[V.ids[Math.floor(Math.random() * V.ids.length)]][0])}`);
  });
  more.addEventListener("click", () => guarded(async () => {
    const mine = ++run;
    limit += STEP;
    if (!(await fill(B, mine))) return;
    draw(B);
  }));
  loadAll.addEventListener("click", () => guarded(async () => {
    const mine = ++run;
    setStatus(t("x_loading"));
    while (B.loaded < B.f.pages) await loadPage(B);
    if (mine !== run) return;
    V = compute(B, V.query);
    draw(B);
  }));

  async function show() {
    const { platform, view, arg, query } = route();
    pressed("x-platforms", "platform", platform);
    machine.value = [...machine.options].some((o) => o.value === platform) ? platform : "";
    try {
      if (view === "browse") await browse(platform, query);
      else if (view === "game") await game(platform, arg);
      else if (view === "search") { if (search.value !== arg) search.value = arg; await find(platform, arg); }
      else await list(platform, view);
    } catch (e) {
      setStatus(t("x_error"));
    }
  }

  document.getElementById("x-platforms").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-platform]");
    if (!b) return;
    const { view } = route();
    const keep = view === "game" || view === "search" ? "popular" : view;
    go(`#${b.dataset.platform}/${keep}`);
  });
  machine.addEventListener("change", () => { if (machine.value) go(`#${machine.value}/popular`); });
  document.getElementById("x-views").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-view]");
    if (!b) return;
    search.value = "";
    go(`#${route().platform}/${b.dataset.view}`);
  });
  let timer = 0;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const q = search.value.trim();
      go(q ? `#${route().platform}/search/${encodeURIComponent(q)}` : `#${route().platform}/popular`);
    }, 250);
  });
  window.addEventListener("hashchange", show);
  show();
})();
