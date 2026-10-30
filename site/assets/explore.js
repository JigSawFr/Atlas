// The explorer (explore/): Atlas's data as tools/site_data.py cut it
// under x/, read from this site, a file when a view needs it and kept for
// the visit. The address says what is shown, so it can be shared:
//   #<platform>/<popular|trending|upcoming>    a list
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
    const parts = decodeURIComponent(location.hash.slice(1)).split("/");
    const platform = PLATFORMS.includes(parts[0]) ? parts[0] : PLATFORMS[0];
    const view = ["popular", "trending", "upcoming", "search", "game"].includes(parts[1]) ? parts[1] : "popular";
    return { platform, view, arg: parts.slice(2).join("/") };
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
    results.hidden = true;
    pressed("x-views", "view", "");
    setStatus(t("x_loading"));
    const lists = await get(`x/${platform}/lists.json`);
    const part = await get(`x/${platform}/g/${shard(id, lists.shards)}.json`);
    const g = part[id];
    sheet.replaceChildren();
    sheet.hidden = false;
    const back = el("a", { class: "back", href: `#${platform}/popular` }, `← ${t("x_back")}`);
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
        dl.append(el("div", {}, el("dt", { text: t(`x_${kind}`) }), el("dd", {}, ...names.map((n) => el("span", { class: "chip", text: n })))));
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

  async function show() {
    const { platform, view, arg } = route();
    pressed("x-platforms", "platform", platform);
    machine.value = [...machine.options].some((o) => o.value === platform) ? platform : "";
    try {
      if (view === "game") await game(platform, arg);
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
