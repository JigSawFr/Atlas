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
  const more = $("x-more"), loadAll = $("x-loadall"), active = $("x-active");
  // The filters' menus fold under one summary: open on a wide screen, folded on a phone (the list comes first).
  const filters = $("x-filters"), filtersTitle = $("x-filters-title");
  filters.open = window.matchMedia("(min-width: 701px)").matches;
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
  // The notions the data names once for every source (genres, themes, modes, perspectives, styles, moods,
  // gameplay, content, access) have a
  // name in the page's language and an icon (x_<letter>_<key>, #i-<letter>-<key>); the other
  // values (series, studios, tags) are the sources' own words.
  const NOTION = { genres: "g", themes: "t", modes: "m", perspectives: "p", styles: "y", moods: "o", gameplay: "h", content: "c", access: "a" };
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
  const BROWSABLE = ["genres", "themes", "modes", "perspectives", "styles", "moods", "gameplay", "content", "access", "series", "developers", "publishers"];
  const chip = (kind, value, href) => el(href ? "a" : "span", href ? { class: "chip", href } : { class: "chip" }, iconOf(kind, value), labelOf(kind, value));

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
  let from = "";               // the platform last shown, which a sheet of all a game's platforms goes back to ("" before any)
  function route() {
    const raw = location.hash.slice(1), q = raw.indexOf("?");
    const parts = decodeURIComponent(q < 0 ? raw : raw.slice(0, q)).split("/");
    const query = new URLSearchParams(q < 0 ? "" : raw.slice(q + 1));
    if (parts[0] === "all" && parts[1] === "search") return { platform: from || PLATFORMS[0], view: "searchall", arg: parts.slice(2).join("/"), query };
    if (parts[0] === "game" && parts[1]) return { platform: from || PLATFORMS[0], view: "ugame", arg: parts.slice(1).join("/"), query };
    const platform = PLATFORMS.includes(parts[0]) ? parts[0] : PLATFORMS[0];
    from = platform;
    const view = ["browse", "popular", "trending", "upcoming", "search", "game"].includes(parts[1]) ? parts[1] : "popular";
    return { platform, view, arg: parts.slice(2).join("/"), query };
  }
  const go = (hash) => { if (location.hash !== hash) location.hash = hash; else show(); };

  function pressed(group, attr, value) {
    const box = $(group);
    let on = null;
    for (const b of box.querySelectorAll("button:not(.layout)")) {
      b.setAttribute("aria-pressed", String(b.dataset[attr] === value));
      if (b.dataset[attr] === value) on = b;
    }
    // On a phone the row scrolls sideways: the button pressed is brought into it (the page itself does not move).
    if (on && box.scrollWidth > box.clientWidth) {
      const r = on.getBoundingClientRect(), g = box.getBoundingClientRect();
      if (r.left < g.left || r.right > g.right) box.scrollLeft += r.left - g.left - (g.width - r.width) / 2;
    }
  }

  function setStatus(text) {
    status.textContent = text;
  }

  function nameOf(id, name, platform) {
    return name ? el("span", { class: "name", text: name })
      : el("span", { class: "name none" }, el("code", { text: id }), el("small", { text: t("x_no_name") }));
  }

  // A tile for a game: Steam's header where the id is a Steam app's (a fixed name on the store's server, through
  // wsrv.nl), else a cover drawn by the page. No sheet is fetched for it: a shard of sheets is some 160 kB.
  // The other platforms' rows may name a picture (tools/site_data.py `picture()`): "s<app>" Steam's header of the
  // same game, "i<id>" IGDB's cover (vertical: its top kept), "g<name>" GOG's own cover.
  // A thumb is the same, small, at the head of a row of a list.
  function tileOrigin(kind, ref, pic) {
    if (kind === "steam" && /^\d+$/.test(ref)) return STORE_PICTURES.steam(ref, "header.jpg");
    const k = (pic || "")[0], n = (pic || "").slice(1);
    if (k === "s" && /^\d+$/.test(n)) return STORE_PICTURES.steam(n, "header.jpg");
    if (k === "i" && /^\w+$/.test(n)) return `https://images.igdb.com/igdb/image/upload/t_cover_big/${n}.jpg`;
    if (k === "g" && /^[\w.]+$/.test(n)) return STORE_PICTURES.gog(ref, n);
    return null;
  }

  function tile(kind, ref, name, thumb, pic) {
    const cls = thumb ? "tile thumb" : "tile";
    const draw = () => drawnCover({ id: ref, name }, cls);
    const origin = tileOrigin(kind, ref, pic);
    if (!origin) return draw();
    const [w, h] = thumb ? [128, 60] : [320, 150];
    const img = el("img", { src: proxied(origin, w, h) + (pic && pic[0] === "i" ? "&a=top" : ""), alt: "", loading: "lazy", decoding: "async",
      referrerpolicy: "no-referrer", width: String(w), height: String(h) });
    const figure = el("figure", { class: `cover ${cls}` }, img);
    img.addEventListener("error", () => figure.replaceWith(draw()));
    return figure;
  }

  let cards = false;           // lists as cards with a picture rather than rows (kept in the browser)
  try { cards = localStorage.getItem("atlas-cards") === "1"; } catch (e) { /* no storage: rows */ }

  // A game as a card: its picture, its name, its figures.
  function card(href, kind, ref, name, meta, pic) {
    return el("a", { class: "card", href }, tile(kind, ref, name, false, pic), nameOf(ref, name), el("span", { class: "meta" }, ...meta));
  }

  function row(platform, id, name, meta, pic) {
    if (cards) return el("li", {}, card(`#${platform}/game/${encodeURIComponent(id)}`, platform, id, name, meta, pic));
    return el("li", {}, el("a", { href: `#${platform}/game/${encodeURIComponent(id)}` },
      tile(platform, id, name, true, pic), nameOf(id, name, platform), el("span", { class: "meta" }, ...meta)));
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
    if (view === "upcoming") {
      for (const [id, name, when, , pic] of lists.upcoming) results.append(row(platform, id, name, [el("span", { class: "date", text: ymd(when) })], pic));
      count = lists.upcoming.length;
      note = t("x_upcoming_note");
    } else {
      const rows = lists[view] || [];
      for (const [id, name, s, tr, critics, pic] of rows) {
        results.append(row(platform, id, name, [score(s), trend(tr),
          critics ? el("span", { class: "dim", text: `${t("x_critics")} ${critics}` }) : null], pic));
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

  // The search over every platform at once: all the names lists, asked only when the visitor asks for it.
  async function findAll(words) {
    leaveBrowse();
    sheet.hidden = true;
    results.hidden = false;
    pressed("x-views", "view", "");
    const q = fold(words.trim());
    if (!q) return go(`#${from || PLATFORMS[0]}/popular`);
    setStatus(t("x_loading"));
    const lists = await Promise.all(PLATFORMS.map((p) => get(`x/${p}/names.json`).then((names) => [p, names], () => [p, []])));
    const found = [];
    for (const [p, names] of lists) for (const [id, name, s] of names) if (fold(name).includes(q)) found.push([p, id, name, s]);
    found.sort((a, b) => (b[3] - a[3]) || a[2].localeCompare(b[2]));
    const shown = found.slice(0, 200);
    results.replaceChildren(...shown.map(([p, id, name, s]) => row(p, id, name, [el("span", { class: "badge", text: S._names[p] || p }), score(s)])));
    bars(results);
    setStatus((found.length ? t("x_count", { n: num(found.length) }) : t("x_nothing")) + ` · ${t("x_loaded", { size: kb(read) })}`);
  }

  function section(title, ...content) {
    return el("section", {}, el("h3", { text: title }), ...content);
  }

  // The technical details of a game (tools/tech.py): where it runs, how the Steam Deck takes it, who can
  // play together, what it offers, its languages and its age ratings; each store's, put together.
  const OS_NAMES = { windows: "Windows", mac: "macOS", linux: "Linux", xbox: "Xbox" };
  const FEATURES = ["achievements", "cloud", "controller", "controller_partial", "crossplay", "play_anywhere", "4k", "hdr", "60fps", "vrr", "keyboard_mouse"];
  const AGES = ["PEGI", "ESRB", "USK", "CERO"];
  let languageNames = null;
  const languageName = (code) => {
    try {
      languageNames = languageNames || new Intl.DisplayNames([LANG], { type: "language" });
      return languageNames.of(code) || code;
    } catch (e) { return code; }
  };

  function techBlock(es, wd) {
    const techs = es.map((e) => e.tech).filter(Boolean);
    wd = wd || {};
    if (!techs.length && !(wd.age || wd.engine)) return null;
    const union = (key) => [...new Set(techs.flatMap((x) => x[key] || []))];
    const dl = el("dl", { class: "traits" });
    const row = (label, ...content) => dl.append(el("div", {}, el("dt", { text: label }), el("dd", {}, ...content)));
    const chips = (items) => items.map((x) => el("span", { class: "chip", text: x }));

    const os = union("os");
    if (os.length) row(t("x_runs_on"), ...chips(os.map((o) => OS_NAMES[o] || o)));
    const deck = techs.map((x) => x.deck).find(Boolean);
    if (deck) row("Steam Deck", ...chips([t(`x_deck_${deck}`)]));
    const most = (key) => Math.max(0, ...techs.map((x) => (x.players && x.players[key]) || 0));
    const players = [most("local") ? t("x_players_local", { n: most("local") }) : "", most("online") ? t("x_players_online", { n: most("online") }) : ""].filter(Boolean);
    if (players.length) row(t("x_players"), ...chips(players));
    const found = new Set(union("feat"));
    if (found.has("controller")) found.delete("controller_partial");
    const feat = FEATURES.filter((f) => found.has(f));
    if (feat.length) row(t("x_features"), ...chips(feat.map((f) => t(`x_f_${f}`))));
    if (wd.engine && wd.engine.length) row(t("x_engine"), ...chips(wd.engine));
    const ages = [];
    for (const system of AGES) {
      // The stores' ratings first, Wikidata's for the systems they do not give.
      const one = techs.flatMap((x) => x.age || []).concat(wd.age || []).find((a) => a[0] === system);
      if (one) ages.push(`${one[0]} ${one[1]}`);
    }
    if (ages.length) row(t("x_age"), ...chips(ages));
    const list = (label, codes) => {
      if (!codes.length) return;
      const items = chips(codes.map((c) => languageName(c)));
      const shown = items.slice(0, 6), rest = items.slice(6);
      row(label, ...shown, rest.length ? el("details", { class: "more-chips" }, el("summary", { class: "chip", text: `+${num(rest.length)}` }), ...rest) : null);
    };
    list(t("x_languages"), union("langs"));
    list(t("x_voices"), union("voices"));
    return dl.childElementCount ? section(t("x_tech"), dl) : null;
  }

  // The pictures of a game (tools/tech.py's `img`: the stores' own names for them). The visitor's browser
  // never asks a store: it asks wsrv.nl (an image cache and resize service in the European Union), which asks
  // the store, hands the picture back resized and sends nothing about the visitor on. Where a game has no
  // picture, or one does not load, the page draws a cover (a colour from its name, its first genre's icon).
  const PROXY = "https://wsrv.nl/";
  const STORE_PICTURES = {
    steam: (id, name) => `https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/${id}/${name}`,
    gog: (id, name, shot) => `https://images.gog-statics.com/${name}${shot ? ".jpg" : ""}`,
    xbox: (id, name) => `https://store-images.s-microsoft.com/image/${name}`,
  };
  const proxied = (origin, width, height) =>
    `${PROXY}?url=${encodeURIComponent(origin)}&w=${width}${height ? `&h=${height}&fit=cover` : ""}&output=webp&q=75`;

  // Which pictures a sheet draws: the first store that has each kind (landscape, vertical, screenshots).
  function pictures(es) {
    const found = { shots: [], backdrops: [] };
    for (const e of es) {
      // Steam's wide library art and logo are at fixed names for the games that have them: a missing one just does not load.
      if (e.p === "steam" && STORE_PICTURES.steam) {
        found.backdrops.push(STORE_PICTURES.steam(e.id, "library_hero.jpg"));
        if (!found.logo) found.logo = STORE_PICTURES.steam(e.id, "logo.png");
      }
      const img = e.tech && e.tech.img, make = STORE_PICTURES[e.p];
      if (!img || !make) continue;
      if (!found.hero && img.h) found.hero = make(e.id, img.h);
      if (!found.poster && img.v) found.poster = make(e.id, img.v);
      if (!found.shots.length && img.s && img.s.length) found.shots = img.s.map((n) => make(e.id, n, true));
    }
    if (found.hero) found.backdrops.push(found.hero);
    // Where no store has a vertical cover, IGDB's (it has one for the consoles' games too).
    // IGDB's artwork is a wide picture too: the backdrop of the games no store has one for (the consoles' games).
    const art = es.find((e) => e.igdb_art);
    if (art) found.backdrops.push(`https://images.igdb.com/igdb/image/upload/t_1080p/${art.igdb_art}.jpg`);
    const igdb = es.find((e) => e.igdb_cover);
    if (!found.poster && igdb) found.poster = `https://images.igdb.com/igdb/image/upload/t_cover_big/${igdb.igdb_cover}.jpg`;
    return found;
  }

  const hueOf = (text) => {
    let h = 0;
    for (const c of String(text)) h = (Math.imul(h, 31) + c.charCodeAt(0)) >>> 0;
    return h % 360;
  };

  // A cover drawn by the page: no tracker, no request, always there.
  function drawnCover(m, extra) {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 460 215");
    svg.setAttribute("preserveAspectRatio", "xMidYMid slice");
    svg.setAttribute("aria-hidden", "true");
    const hue = hueOf(m.qid || m.id || m.name || "");
    const rect = document.createElementNS(SVG, "rect");
    for (const [k, v] of [["width", "460"], ["height", "215"], ["fill", `hsl(${hue} 42% 22%)`]]) rect.setAttribute(k, v);
    svg.append(rect);
    const glow = document.createElementNS(SVG, "circle");
    for (const [k, v] of [["cx", "360"], ["cy", "40"], ["r", "170"], ["fill", `hsl(${(hue + 40) % 360} 60% 38%)`], ["opacity", "0.35"]]) glow.setAttribute(k, v);
    svg.append(glow);
    const genre = m.traits && m.traits.genres && m.traits.genres[0];
    if (genre && document.getElementById(`i-g-${genre}`)) {
      const use = document.createElementNS(SVG, "use");
      for (const [k, v] of [["href", `#i-g-${genre}`], ["x", "290"], ["y", "30"], ["width", "150"], ["height", "150"],
        ["fill", "none"], ["stroke", "currentColor"], ["stroke-width", "1.2"], ["opacity", "0.35"]]) use.setAttribute(k, v);
      svg.append(use);
    }
    return el("figure", { class: `cover drawn${extra ? ` ${extra}` : ""}` }, svg, el("figcaption", { text: m.name || m.id || "" }));
  }

  function pictureCover(m, origin, kind) {
    const vertical = kind === "poster";
    const img = el("img", { src: proxied(origin, vertical ? 280 : 920, vertical ? 420 : 430), alt: "", decoding: "async", referrerpolicy: "no-referrer",
      width: vertical ? "140" : "460", height: vertical ? "210" : "215" });
    const figure = el("figure", { class: `cover${vertical ? " poster" : ""}` }, img);
    img.addEventListener("error", () => figure.replaceWith(drawnCover(m, vertical ? "poster" : "")));
    return figure;
  }

  // A screenshot opens in a dialog on the page (arrows, Escape, a swipe) instead of a new tab; the link still goes
  // to the picture for a middle click. Only the opened picture is fetched at its large size.
  let viewer = null;
  function openViewer(origins, start) {
    if (!viewer) {
      const img = el("img", { alt: "", decoding: "async", referrerpolicy: "no-referrer" });
      const mk = (cls, key, text) => el("button", { type: "button", class: `viewer-btn ${cls}`, "aria-label": t(key), text });
      const prev = mk("prev", "x_prev", "‹"), next = mk("next", "x_next", "›"), close = mk("close", "x_close", "✕");
      const count = el("p", { class: "viewer-count", "aria-live": "polite" });
      const dialog = el("dialog", { class: "viewer" }, img, prev, next, close, count);
      viewer = { dialog, img, count, origins: [], at: 0 };
      const go = (d) => { const n = viewer.origins.length; viewer.at = (viewer.at + d + n) % n; viewerShow(); };
      prev.addEventListener("click", () => go(-1));
      next.addEventListener("click", () => go(1));
      close.addEventListener("click", () => dialog.close());
      dialog.addEventListener("click", (ev) => { if (ev.target === dialog || ev.target === img) dialog.close(); });
      dialog.addEventListener("keydown", (ev) => {
        if (ev.key === "ArrowLeft") go(-1);
        else if (ev.key === "ArrowRight") go(1);
      });
      let x0 = null;
      dialog.addEventListener("pointerdown", (ev) => { x0 = ev.clientX; });
      dialog.addEventListener("pointerup", (ev) => { if (x0 !== null && Math.abs(ev.clientX - x0) > 50) go(ev.clientX < x0 ? 1 : -1); x0 = null; });
      document.body.append(dialog);
    }
    viewer.origins = origins;
    viewer.at = start;
    viewerShow();
    viewer.dialog.showModal();
  }

  // The picture asked, its place among the others, and the next one fetched ahead so the arrow shows it at once.
  function viewerShow() {
    const { origins, at } = viewer, n = origins.length;
    viewer.img.src = proxied(origins[at], 1280);
    viewer.count.textContent = `${num(at + 1)} / ${num(n)}`;
    viewer.dialog.classList.toggle("single", n < 2);
    if (n > 1) {
      const ahead = new Image();
      ahead.referrerPolicy = "no-referrer";
      ahead.src = proxied(origins[(at + 1) % n], 1280);
    }
  }

  function gallery(origins) {
    if (!origins.length) return null;
    const strip = el("div", { class: `shots n${Math.min(origins.length, 5)}` });
    origins.forEach((origin, i) => {
      const img = el("img", { src: proxied(origin, i ? 320 : 480, i ? 180 : 270), alt: t("x_screenshot", { n: i + 1 }), loading: "lazy", decoding: "async",
        referrerpolicy: "no-referrer", width: i ? "240" : "360", height: i ? "135" : "203" });
      // On a wide screen the first is large and four more beside it; the last of them says how many are left.
      const link = el("a", { href: proxied(origin, 1280), target: "_blank", rel: "noreferrer noopener", referrerpolicy: "no-referrer", class: i ? "" : "first",
        "data-more": i === 4 && origins.length > 5 ? `+${num(origins.length - 5)}` : null }, img);
      link.addEventListener("click", (ev) => {
        if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button || typeof HTMLDialogElement === "undefined") return;
        ev.preventDefault();
        openViewer(origins, i);
      });
      img.addEventListener("error", () => link.remove());
      strip.append(link);
    });
    return section(t("x_gallery"), strip);
  }

  // The wide picture behind the head of a sheet: the first of the candidates that loads, else a vertical cover
  // blurred, else nothing (the head then draws its cover). Decorative: no alt, no request without a candidate.
  function backdrop(origins, poster) {
    const layer = el("div", { class: "backdrop", "aria-hidden": "true" });
    const queue = origins.slice();
    let blur = false;
    const img = el("img", { alt: "", decoding: "async", referrerpolicy: "no-referrer", width: "1280", height: "430" });
    const next = () => {
      let origin = queue.shift();
      if (!origin && poster && !blur) { origin = poster; blur = true; layer.classList.add("blurred"); }
      if (!origin) { layer.remove(); return; }
      img.src = proxied(origin, 1280, 430);
    };
    img.addEventListener("load", () => layer.classList.add("ready"));
    img.addEventListener("error", next);
    layer.append(img);
    next();
    return layer;
  }

  const toneOf = (v) => (v >= 75 ? "high" : v >= 50 ? "mid" : "low");

  // A score out of 100 as a ring (a dasharray set by script, as the bars' widths: the CSP allows no style attribute).
  // A ring says what it measures when pressed (a finger has no hover): its help under the rings.
  function ring(v, label, help, helpBox) {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 36 36");
    svg.setAttribute("aria-hidden", "true");
    for (const cls of ["track", "arc"]) {
      const c = document.createElementNS(SVG, "circle");
      for (const [k, x] of [["cx", "18"], ["cy", "18"], ["r", "15.5"], ["class", cls]]) c.setAttribute(k, x);
      if (cls === "arc") { c.setAttribute("pathLength", "100"); c.setAttribute("stroke-dasharray", `${Math.max(2, Math.min(100, v))} 100`); }
      svg.append(c);
    }
    const b = el("button", { type: "button", class: `ring ${toneOf(v)}`, "aria-label": `${label}: ${v} / 100`, "aria-expanded": "false", title: help },
      svg, el("b", { text: String(v), "aria-hidden": "true" }), el("small", { text: label, "aria-hidden": "true" }));
    b.addEventListener("click", () => {
      const open = b.getAttribute("aria-expanded") !== "true";
      for (const other of b.parentNode.querySelectorAll(".ring")) other.setAttribute("aria-expanded", "false");
      b.setAttribute("aria-expanded", String(open));
      helpBox.textContent = open ? help : "";
      helpBox.hidden = !open;
    });
    return b;
  }

  // A sheet is drawn from one model, whether it is of a game on one platform or on several:
  //   { name, id, qid, platforms: [{ p, id, release, upcoming, popular, reviews, rating, igdb_rating, steam,
  //     gamepass, editions, edition_of }], traits, similar: [[kind, ref, name, score]], links }
  // (a similar game's kind is "u" for a game with a sheet of all its platforms, else its platform).
  const gameHref = (kind, ref) => (kind === "u" ? `#game/${encodeURIComponent(ref)}` : `#${kind}/game/${encodeURIComponent(ref)}`);
  const storeName = (p) => (p === "steam" ? "Steam" : STORE_NAMES[p] || S._names[p] || p);

  function renderSheet(m, backHref) {
    sheet.replaceChildren();
    sheet.hidden = false;
    const es = m.platforms;
    const back = el("a", { class: "back", href: backHref }, `← ${t("x_back")}`);
    const shown = pictures(es);
    const wide = shown.backdrops.length || shown.poster;
    const cover = wide ? null : shown.hero ? pictureCover(m, shown.hero, "hero") : drawnCover(m);
    const best = es.filter((e) => e.popular).sort((x, y) => y.popular[0] - x.popular[0])[0];
    const critics = Math.max(0, ...es.map((e) => (e.popular ? e.popular[2] : 0)));
    const title = el("h2", { tabindex: "-1" }, m.name || m.id || "");
    const logo = shown.logo ? el("img", { class: "logo", src: proxied(shown.logo, 560), alt: "", decoding: "async", referrerpolicy: "no-referrer" }) : null;
    const rings = el("div", { class: "rings" });
    const ringHelp = el("p", { class: "ring-help", "aria-live": "polite", hidden: "" });
    if (best) rings.append(ring(best.popular[0], t("x_score"), t("x_score_help"), ringHelp));
    if (critics) rings.append(ring(critics, t("x_critics"), t("x_critics_help"), ringHelp));
    const info = el("div", { class: "info" }, logo, title,
      // On a sheet of several platforms each badge opens that platform's own sheet.
      el("p", { class: "ids" }, ...es.map((e) => (es.length > 1
        ? el("a", { class: "badge", href: `#${e.p}/game/${encodeURIComponent(e.id)}?alone`, text: S._names[e.p] || e.p })
        : el("span", { class: "badge", text: S._names[e.p] || e.p }))),
        m.name && m.id ? el("code", { text: m.id }) : null,
        /^Q\d+$/.test(m.qid || "") ? el("a", { href: `https://www.wikidata.org/wiki/${m.qid}`, rel: "noreferrer noopener", referrerpolicy: "no-referrer", text: m.qid }) : null,
        !m.name ? el("small", { text: t("x_no_name") }) : null),
      rings.childElementCount ? rings : null, rings.childElementCount ? ringHelp : null);
    const head = el("header", { class: wide ? "masthead" : "" }, back, cover,
      wide ? el("div", { class: "banner" }, shown.poster ? pictureCover(m, shown.poster, "poster") : null, info) : info);
    if (logo) {
      logo.addEventListener("load", () => head.classList.add("has-logo"));
      logo.addEventListener("error", () => logo.remove());
    }
    if (wide) sheet.append(backdrop(shown.backdrops, shown.poster));
    sheet.classList.toggle("with-backdrop", !!wide);
    sheet.append(head);

    const stats = el("dl", { class: "stats" });
    const stat = (label, value) => { if (value !== null && value !== undefined && value !== "") stats.append(el("div", {}, el("dt", { text: label }), el("dd", {}, value))); };
    // A store's reviews: the share of good ones large, in the rings' colours, how many under it.
    const reviewed = (label, [n, p]) => stats.append(el("div", { class: "rev" }, el("dt", { text: label }),
      el("dd", {}, el("b", { class: `pct ${toneOf(p)}`, text: `${p} %` }), el("small", { text: t("x_review_count", { n: num(n) }) }))));
    if (best && best.popular[1]) stat(t("x_trend"), trend(best.popular[1]));
    for (const e of es) {
      if (e.reviews) reviewed(storeName(e.p), e.reviews);
      if (e.rating) reviewed(storeName(e.p), e.rating);
    }
    const players = es.filter((e) => e.igdb_rating && e.igdb_rating[1] >= 20).sort((x, y) => y.igdb_rating[1] - x.igdb_rating[1])[0];
    if (players) stat(t("x_players_rating"), `${players.igdb_rating[0]} / 100`);
    const out = es.map((e) => e.release).filter(Boolean);
    const soon = es.map((e) => e.upcoming).filter(Boolean);
    if (out.length) stat(t("x_release"), ymd(Math.min(...out)));
    else if (soon.length) stat(t("x_release"), t("x_coming", { date: ymd(Math.min(...soon)) }));
    if (stats.childElementCount) sheet.append(stats);
    for (const e of es) {
      if (e.steam && (e.steam.owners || e.steam.ccu)) {
        sheet.append(el("p", { class: "dim figures", text: t("x_steam_figures", { owners: num(e.steam.owners || 0), ccu: num(e.steam.ccu || 0) }) }));
        break;
      }
    }

    // Wide screens: the story (pictures, traits, text, alike games) beside what stays in view (the facts, platforms, team, links).
    const main = el("div", { class: "main" }), side = el("aside", { class: "side" });
    sheet.append(el("div", { class: "cols" }, main, side));
    const shots = gallery(shown.shots);
    if (shots) main.append(shots);

    // A trait is a way into the platform's games with it: the studio's, the series', the genre's page is the browse view filtered.
    const home = (es[0] && es[0].p) || from || PLATFORMS[0];
    const traitHref = (kind, value) => (BROWSABLE.includes(kind) ? `#${home}/browse?${new URLSearchParams([[kind, value]])}` : undefined);
    if (m.traits) {
      const dl = el("dl", { class: "traits" });
      for (const [kind, names] of Object.entries(m.traits)) {
        dl.append(el("div", {}, el("dt", {}, icon(`i-k-${kind}`), t(`x_${kind}`)), el("dd", {}, ...names.map((n) => chip(kind, n, traitHref(kind, n))))));
      }
      main.append(dl);
    }
    const technical = techBlock(es, m.wd);
    if (technical) side.append(technical);

    if (es.length > 1) {
      side.append(section(t("x_by_platform"), el("ul", { class: "byplat" }, ...es.map((e) => el("li", {}, el("a", { href: `#${e.p}/game/${encodeURIComponent(e.id)}?alone` },
        el("span", { class: "badge", text: S._names[e.p] || e.p }),
        e.popular ? score(e.popular[0]) : null,
        e.release ? el("span", { class: "date", text: ymd(e.release) }) : (e.upcoming ? el("span", { class: "date", text: t("x_coming", { date: ymd(e.upcoming) }) }) : null),
        e.reviews || e.rating ? el("span", { class: "dim", text: t("x_reviews", { n: num((e.reviews || e.rating)[0]), p: (e.reviews || e.rating)[1] }) }) : null,
        e.gamepass ? el("span", { class: "chip", text: "Game Pass" }) : null,
        el("span", { class: "out", "aria-hidden": "true", text: "→" })))))));
    }

    // The first lines of the Wikipedia page, in the visitor's language else English, with its credit (CC BY-SA 4.0).
    const about = m.wd && m.wd.about;
    if (about) {
      const own = LANG.split("-")[0], l = about[own] ? own : about.en ? "en" : null;
      if (l) {
        const page = m.wd.wiki && m.wd.wiki[l];
        main.append(section(t("x_about"), el("div", { class: "about" },
          el("p", { text: about[l] }),
          page ? el("p", { class: "dim" }, el("a", { class: "out-link", href: `https://${l}.wikipedia.org/wiki/${page}`, rel: "noreferrer noopener", referrerpolicy: "no-referrer", text: `${t("x_wikipedia_text")} ↗` })) : el("p", { class: "dim", text: t("x_wikipedia_text") }))));
      }
    }

    // How much Wikipedia read the game, a week at a time (the best known games': tools/trends.py).
    const curve = (es.find((e) => e.views) || {}).views;
    if (curve && curve.length >= 4) {
      const W = 240, H = 48, top = Math.max(...curve, 1), step = W / (curve.length - 1);
      const svg = document.createElementNS(SVG, "svg");
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      svg.setAttribute("class", "curve");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", t("x_views_curve", { n: curve.length, first: num(curve[0]), last: num(curve[curve.length - 1]) }));
      const points = curve.map((v, i) => `${(i * step).toFixed(1)},${(H - 3 - (v / top) * (H - 8)).toFixed(1)}`);
      const area = document.createElementNS(SVG, "polygon");
      for (const [k, v] of [["points", `0,${H} ${points.join(" ")} ${W},${H}`], ["fill", "currentColor"], ["opacity", "0.15"]]) area.setAttribute(k, v);
      const line = document.createElementNS(SVG, "polyline");
      for (const [k, v] of [["points", points.join(" ")], ["fill", "none"], ["stroke", "currentColor"], ["stroke-width", "2"], ["stroke-linejoin", "round"]]) line.setAttribute(k, v);
      svg.append(area, line);
      main.append(section(t("x_views_title"), el("div", { class: "views" }, svg,
        el("p", { class: "dim", text: t("x_views_curve", { n: curve.length, first: num(curve[0]), last: num(curve[curve.length - 1]) }) }))));
    }

    const won = m.wd && m.wd.awards;
    if (won && won.length) {
      main.append(section(t("x_awards"), el("ul", { class: "awards" }, ...won.map(([name, year]) => el("li", {}, el("span", { class: "chip", text: year ? `${name} (${year})` : name }))))));
    }

    const team = m.wd && m.wd.team;
    if (team) {
      const dl = el("dl", { class: "traits" });
      for (const [role, key] of [["director", "x_director"], ["composer", "x_composer"], ["writer", "x_writer"]]) {
        if (team[role] && team[role].length) dl.append(el("div", {}, el("dt", { text: t(key) }), el("dd", {}, ...team[role].map((n) => el("span", { class: "chip", text: n })))));
      }
      if (dl.childElementCount) side.append(section(t("x_team"), dl));
    }

    // Not the game itself (a platform's list can name the sheet of all its platforms, or one of them).
    // Nor another entry of it under the same name (an edition the links do not tie to it).
    const alike = (m.similar || []).filter(([kind, ref, name]) => !(kind === "u" && ref === m.qid) && !es.some((e) => e.p === kind && e.id === ref)
      && !(name && m.name && fold(name) === fold(m.name)));
    if (alike.length) {
      main.append(section(t("x_similar"), el("ul", { class: "cardgrid" }, ...alike.map(([kind, ref, name, s, pic]) =>
        el("li", {}, card(gameHref(kind, ref), kind, ref, name, [score(s)], pic))))));
    }
    for (const e of es) {
      if (e.edition_of) {
        const [o, name] = e.edition_of;
        main.append(section(t("x_edition_of"), el("ul", { class: "cardgrid" }, el("li", {}, card(gameHref(e.p, o), e.p, o, name, [])))));
      }
      if (e.editions) {
        main.append(section(t("x_editions"), el("ul", { class: "cardgrid" }, ...e.editions.map(([o, name]) =>
          el("li", {}, card(gameHref(e.p, o), e.p, o, name, []))))));
      }
    }
    const wd = m.wd || {};
    const outside = [];
    const open = (label, href) => outside.push(el("li", {}, el("a", { class: "out-link", href, rel: "noreferrer noopener", referrerpolicy: "no-referrer", text: `${label} ↗` })));
    if (wd.web) open(t("x_official_site"), wd.web);
    if (wd.wiki) {
      // The visitor's language first (the catalogs' es-419, fr-CA, pt-BR… are Spanish, French, Portuguese), English after.
      const own = LANG.split("-")[0], langs = [own, "en"].filter((l, i, all) => wd.wiki[l] && all.indexOf(l) === i);
      for (const l of langs) open(langs.length > 1 ? `Wikipedia (${l})` : "Wikipedia", `https://${l}.wikipedia.org/wiki/${wd.wiki[l]}`);
    }
    if (wd.pcgw) open("PCGamingWiki", `https://www.pcgamingwiki.com/wiki/${encodeURIComponent(wd.pcgw)}`);
    (wd.yt || []).forEach((id, i, all) => open(all.length > 1 ? `YouTube ${i + 1}` : "YouTube", `https://www.youtube.com/watch?v=${encodeURIComponent(id)}`));
    if (outside.length) side.append(section(t("x_links"), el("ul", { class: "links" }, ...outside)));
    if (m.links && Object.keys(m.links).length) {
      const items = [];
      for (const [p, ids] of Object.entries(m.links)) {
        if (p === "ps_product") continue;
        for (const other of ids) {
          const inData = PLATFORMS.includes(p) && !es.some((e) => e.p === p);
          items.push(el("li", {}, el("span", { class: "badge", text: STORE_NAMES[p] || p }),
            inData ? el("a", { href: gameHref(p, other) }, el("code", { text: other })) : el("code", { text: other }),
            STORES[p] ? el("a", { class: "out", href: STORES[p](other), rel: "noreferrer noopener", referrerpolicy: "no-referrer", text: "↗", "aria-label": `${STORE_NAMES[p]} ${other}` }) : null));
        }
      }
      if (items.length) side.append(section(t("x_other_platforms"), el("ul", { class: "links" }, ...items)));
    }
    bars(sheet);
    fitSide();
    setStatus(t("x_loaded", { size: kb(read) }));
    head.querySelector("h2").focus({ preventScroll: true });
    window.scrollTo({ top: sheet.getBoundingClientRect().top + window.scrollY - 16 });
  }

  // The facts' column stays in view while the story scrolls, only when it fits the window: a taller one scrolls
  // with the page (a scroll inside a scroll hides its end).
  function fitSide() {
    const side = sheet.querySelector(".side");
    if (side) side.classList.toggle("stuck", side.scrollHeight <= window.innerHeight - 32);
  }
  window.addEventListener("resize", () => { if (!sheet.hidden) fitSide(); });

  const backTo = (platform) => (lastBrowse.startsWith(`#${platform}/browse`) ? lastBrowse : `#${platform}/popular`);

  // The sheet of a game on several platforms, by its Wikidata item.
  async function unified(qid) {
    leaveBrowse();
    results.hidden = true;
    pressed("x-views", "view", "");
    setStatus(t("x_loading"));
    const meta = await get("x/u/meta.json");
    const part = await get(`x/u/${shard(qid, meta.shards)}.json`);
    const u = part[qid];
    if (!u) {
      sheet.replaceChildren(el("a", { class: "back", href: backTo(from || PLATFORMS[0]) }, `← ${t("x_back")}`), el("p", { text: t("x_not_found") }));
      sheet.hidden = false;
      setStatus("");
      return;
    }
    if (!from) {
      // Arrived by the address alone: the first of its platforms that has a button is the one shown.
      from = (u.platforms.find((e) => document.querySelector(`#x-platforms button[data-platform="${e.p}"]`)) || u.platforms[0]).p;
      pressed("x-platforms", "platform", from);
      machine.value = [...machine.options].some((o) => o.value === from) ? from : "";
    }
    renderSheet(u, backTo(from));
  }

  // The sheet of a game on one platform; a game on several goes to the sheet of all of them
  // (the address is replaced), unless the address asks for this platform's alone.
  async function game(platform, id, query) {
    leaveBrowse();
    results.hidden = true;
    pressed("x-views", "view", "");
    setStatus(t("x_loading"));
    const lists = await get(`x/${platform}/lists.json`);
    const part = await get(`x/${platform}/g/${shard(id, lists.shards)}.json`);
    const g = part[id];
    if (g && g.unified && !query.has("alone")) {
      history.replaceState(null, "", gameHref("u", g.qid));
      from = platform;
      return unified(g.qid);
    }
    if (!g) {
      sheet.replaceChildren(el("a", { class: "back", href: backTo(platform) }, `← ${t("x_back")}`), el("p", { text: t("x_not_found") }));
      sheet.hidden = false;
      setStatus("");
      return;
    }
    const entry = { p: platform, id };
    for (const k of ["release", "upcoming", "popular", "reviews", "rating", "igdb_rating", "igdb_cover", "igdb_art", "views", "steam", "gamepass", "tech", "editions", "edition_of"]) if (g[k]) entry[k] = g[k];
    renderSheet({ name: g.name, id, qid: g.qid, wd: g.wd, platforms: [entry], traits: g.traits,
      similar: (g.similar || []).map(([o, name, s, pic]) => [platform, o, name, s, pic]), links: g.links }, backTo(platform));
  }

  // Browsing: facets.json gives the menus, then the pages of games, best known
  // first, a page at a time. Every filter narrows (a game must have all the
  // values picked); the rows are filtered here, in the browser.
  const FACETS = ["genres", "themes", "modes", "perspectives", "styles", "moods", "gameplay", "content", "access", "series", "developers", "publishers", "tags", "year"];
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
    active.hidden = true;
  }

  // The values picked, above the list: each one a link to the same view without it.
  function drawActive(b, v) {
    const items = [];
    for (const [kind, n] of v.found) {
      const value = b.f.facets[kind][n][0], name = labelOf(kind, value);
      const params = new URLSearchParams(v.query);
      const rest = params.getAll(kind).filter((x) => x !== value);
      params.delete(kind);
      for (const x of rest) params.append(kind, x);
      items.push(el("a", { class: "chip on", href: hashOf(b.platform, params), "aria-label": t("x_remove_filter", { name }) },
        iconOf(kind, value), el("span", { text: name }), el("span", { class: "x", "aria-hidden": "true", text: "×" })));
    }
    if (items.length > 1 || v.unknown) items.push(el("a", { class: "clear", href: hashOf(b.platform, new URLSearchParams(v.how !== "popular" ? [["sort", v.how]] : [])), text: t("x_clear") }));
    active.replaceChildren(...items);
    active.hidden = !items.length;
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
    filtersTitle.textContent = v.found.length ? `${t("x_filters")} · ${num(v.found.length)}` : t("x_filters");
  }

  function draw(b) {
    const { ids, found, how } = V;
    results.replaceChildren(...ids.slice(0, limit).map((i) => {
      const [id, name, s, tr, critics, year, pic] = b.rows[i];
      return row(b.platform, id, name, [score(s), trend(tr),
        critics ? el("span", { class: "dim", text: `${t("x_critics")} ${critics}` }) : null,
        year ? el("span", { class: "dim", text: String(year) }) : null], pic);
    }));
    bars(results);
    syncFacets(b, V);
    renderSaved();
    drawActive(b, V);
    if (V.unknown) {
      // A value the data does not know (an old link, a typo): nothing matches, and no page would change that.
      more.hidden = true;
      loadAll.hidden = true;
      setStatus(t("x_nothing"));
      return;
    }
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
  // Saved views: a name for a list's filters and sort, kept in this browser only (nothing leaves it).
  const VIEWS = "atlas-views";
  const savedViews = () => {
    try {
      const list = JSON.parse(localStorage.getItem(VIEWS) || "[]");
      return Array.isArray(list) ? list.filter((v) => v && typeof v.name === "string" && typeof v.p === "string" && typeof v.q === "string") : [];
    } catch (e) { return []; }
  };
  const keepViews = (list) => { try { localStorage.setItem(VIEWS, JSON.stringify(list.slice(-50))); } catch (e) { /* no storage: nothing kept */ } };
  function renderSaved() {
    const box = $("x-saved"), ul = box.querySelector("ul");
    const mine = savedViews().filter((v) => B && v.p === B.platform);
    ul.replaceChildren(...mine.map((v) => {
      const remove = el("button", { type: "button", class: "x", "aria-label": t("x_remove_view", { name: v.name }), text: "×" });
      remove.addEventListener("click", () => {
        keepViews(savedViews().filter((w) => !(w.p === v.p && w.q === v.q && w.name === v.name)));
        renderSaved();
      });
      return el("li", {}, el("a", { class: "chip", href: `#${v.p}/browse${v.q ? `?${v.q}` : ""}`, text: v.name }), remove);
    }));
    box.hidden = !mine.length;
  }
  $("x-save").addEventListener("click", () => {
    if (!B) return;
    const name = (window.prompt(t("x_view_name")) || "").trim().slice(0, 60);
    if (!name) return;
    const q = address().split("?")[1] || "";
    keepViews(savedViews().filter((v) => !(v.p === B.platform && v.name === name)).concat({ name, p: B.platform, q }));
    renderSaved();
  });
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
    // On a sheet the page's own heading folds to a line: the sheet is what is read.
    document.body.classList.toggle("x-on-sheet", view === "game" || view === "ugame");
    pressed("x-platforms", "platform", platform);
    machine.value = [...machine.options].some((o) => o.value === platform) ? platform : "";
    try {
      if (view === "browse") await browse(platform, query);
      else if (view === "ugame") await unified(arg);
      else if (view === "game") await game(platform, arg, query);
      else if (view === "searchall") { if (search.value !== arg) search.value = arg; await findAll(arg); }
      else if (view === "search") { if (search.value !== arg) search.value = arg; await find(platform, arg); }
      else await list(platform, view);
    } catch (e) {
      setStatus(t("x_error"));
    }
  }

  const layout = document.getElementById("x-layout");
  function syncLayout() {
    results.classList.toggle("cards", cards);
    layout.setAttribute("aria-pressed", String(cards));
    layout.textContent = cards ? "☰" : "▦";
    const label = t(cards ? "x_as_list" : "x_as_cards");
    layout.title = label;
    layout.setAttribute("aria-label", label);
  }
  layout.addEventListener("click", () => {
    cards = !cards;
    try { localStorage.setItem("atlas-cards", cards ? "1" : "0"); } catch (e) { /* not kept */ }
    syncLayout();
    show();
  });
  syncLayout();

  document.getElementById("x-platforms").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-platform]");
    if (!b) return;
    const { view } = route();
    const keep = view === "game" || view === "ugame" || view === "search" || view === "searchall" ? "popular" : view;
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
  $("x-search-all").addEventListener("click", () => {
    clearTimeout(timer);       // the typing's own search, waiting its turn, would take the address back
    const q = search.value.trim();
    if (q) go(`#all/search/${encodeURIComponent(q)}`);
  });
  // "/" goes to the search box, as on most sites with one; Escape in it empties it.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey || e.target.closest("input, select, textarea, [contenteditable], dialog")) return;
    e.preventDefault();
    search.focus();
  });
  search.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && search.value) { e.preventDefault(); search.value = ""; search.dispatchEvent(new Event("input")); }
  });
  window.addEventListener("hashchange", show);
  show();
})();
