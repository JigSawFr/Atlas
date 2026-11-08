// The explorer (explore/): Atlas's data as tools/site_data.py cut it
// under x/, read from this site, a file when a view needs it and kept for
// the visit. The address says what is shown, so it can be shared:
//   #<platform>/<popular|trending|upcoming>    a list
//   #<platform>/browse?<facet>=<value>&…&sort=<key>
//                                              the games with every value picked, a page at a time
//   #<platform>/search/<words>                 the games whose name has them
//   #<platform>/game/<id>                      a game's sheet
//   #<platform>/stats                          the platform's figures (x/<platform>/stats.json)
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
    const view = ["browse", "popular", "trending", "upcoming", "search", "game", "stats", "favorites", "compare"].includes(parts[1]) ? parts[1] : "popular";
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
  // `extra`: { shared: ["g:farm", …] the notions it has in common with the sheet's game, badge: the platform's name }.
  const INV = Object.fromEntries(Object.entries(NOTION).map(([k, v]) => [v, k]));
  function sharedLine(shared) {
    const items = (shared || []).map((x) => {
      const at = x.indexOf(":"), kind = INV[x.slice(0, at)], value = x.slice(at + 1);
      return kind ? el("span", { class: "mini" }, iconOf(kind, value), labelOf(kind, value)) : null;
    }).filter(Boolean);
    return items.length ? el("span", { class: "shared", role: "group", "aria-label": t("x_in_common") }, ...items) : null;
  }
  function card(href, kind, ref, name, meta, pic, extra) {
    const e = extra || {};
    return el("a", { class: "card", href }, tile(kind, ref, name, false, pic),
      e.badge ? el("span", { class: "pbadge", text: e.badge }) : null, sharedLine(e.shared),
      nameOf(ref, name), el("span", { class: "meta" }, ...meta));
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
  // Set two frames after the bars are in the page, so they grow from nothing (site.css's transition; none when the
  // visitor asks for less motion). Columns take a height (data-h) the same way.
  function bars(root) {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      for (const i of root.querySelectorAll("i[data-w]")) i.style.width = `${Math.max(2, Math.min(100, +i.dataset.w))}%`;
      for (const i of root.querySelectorAll("i[data-h]")) i.style.height = `${Math.max(0, Math.min(100, +i.dataset.h))}%`;
    }));
    stagger(root);
  }

  // The first rows of a list come in one after the other (a delay each, as a custom property the CSP allows).
  function stagger(root) {
    const items = root.matches && root.matches(".results") ? root.children : [];
    for (let i = 0; i < Math.min(items.length, 40); i++) items[i].style.setProperty("--i", String(i));
  }

  const MOTION = window.matchMedia("(prefers-reduced-motion: no-preference)");
  // A figure counts up to its value (the value at once when the visitor asks for less motion).
  function countUp(root) {
    for (const e of root.querySelectorAll("[data-count]")) {
      const to = +e.dataset.count, digits = +(e.dataset.digits || 0);
      const fmt = new Intl.NumberFormat(LANG, { minimumFractionDigits: digits, maximumFractionDigits: digits });
      if (!MOTION.matches) { e.textContent = fmt.format(to); continue; }
      const start = performance.now(), span = 900;
      const step = (now) => {
        const k = Math.min(1, (now - start) / span), eased = 1 - Math.pow(1 - k, 3);
        e.textContent = fmt.format(to * eased);
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }
  }

  // A sheet's or the figures' sections rise into view as they are scrolled to (with motion only).
  const seen = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
    for (const en of entries) if (en.isIntersecting) { en.target.classList.add("seen"); seen.unobserve(en.target); }
  }, { rootMargin: "0px 0px -8% 0px" }) : null;
  function reveal(root) {
    if (!seen || !MOTION.matches) return;
    for (const e of root.querySelectorAll(":scope section, :scope .cols > * > section")) { e.classList.add("unveil"); seen.observe(e); }
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
  function ringSvg(v) {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 36 36");
    svg.setAttribute("aria-hidden", "true");
    for (const cls of ["track", "arc"]) {
      const c = document.createElementNS(SVG, "circle");
      for (const [k, x] of [["cx", "18"], ["cy", "18"], ["r", "15.5"], ["class", cls]]) c.setAttribute(k, x);
      if (cls === "arc") { c.setAttribute("pathLength", "100"); c.setAttribute("stroke-dasharray", `${Math.max(2, Math.min(100, v))} 100`); }
      svg.append(c);
    }
    return svg;
  }

  // A small ring with no help, for a platform's tile (the renown there; its label is the tile's text).
  const miniRing = (v, label) => el("span", { class: `mini-ring ${toneOf(v)}`, role: "img", "aria-label": `${label}: ${v} / 100` }, ringSvg(v), el("b", { text: String(v), "aria-hidden": "true" }));

  function ring(v, label, help, helpBox) {
    const svg = ringSvg(v);
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

  // A platform's tile on a sheet: its short name large and faint behind it, with a computer or a console drawn
  // beside, and a tint of its own (no brand's logo: the platforms' owners keep theirs).
  const SHORT = { switch: "Switch", steam: "Steam", gog: "GOG", xbox: "Xbox", ps4: "PS4", ps5: "PS5", ps3: "PS3", ps2: "PS2", ps1: "PS1",
    psp: "PSP", psv: "Vita", "3ds": "3DS", nds: "DS", wiiu: "Wii U", wii: "Wii", gamecube: "GameCube", n64: "N64", snes: "SNES", nes: "NES",
    "xbox-og": "Xbox", xbox360: "360", genesis: "Mega Drive", dreamcast: "Dreamcast", saturn: "Saturn", gb: "Game Boy", gbc: "GBC", gba: "GBA" };
  const PC = new Set(["steam", "gog", "dos", "amiga", "atarist", "c64", "msx", "zxspectrum", "amstradcpc", "apple2"]);
  // Each platform's own colour, the one its machines and stores are known by (a colour, not a mark); a hue from
  // the id for the others.
  const TINTS = { switch: "#e60012", "3ds": "#ce181e", nds: "#b8bcc6", wii: "#34bedd", wiiu: "#009ac7", gamecube: "#6a5acd",
    n64: "#2c9a3c", snes: "#8f7fd0", nes: "#e60012", fds: "#e8b400", gb: "#8bac0f", gbc: "#f5b60a", gba: "#5a4fcf",
    steam: "#1a9fff", gog: "#a649d6", xbox: "#107c10", "xbox-og": "#3fa535", xbox360: "#9bc848",
    ps1: "#b7b7b7", ps2: "#2d50c8", ps3: "#5a6e8c", ps4: "#0070d1", ps5: "#2f6ff0", psp: "#6d7c95", psv: "#1f63c6",
    genesis: "#0060a8", sms: "#e03a3e", gamegear: "#3a3d9c", saturn: "#4b5bb5", dreamcast: "#f26f22", segacd: "#2b6cc4",
    neogeo: "#d8a71d", turbografx16: "#ff6a13", atari2600: "#c8102e", colecovision: "#e4572e", c64: "#6c5eb5",
    amiga: "#ff5a1f", atarist: "#9a9a9a", msx: "#2f7ad8", zxspectrum: "#e8262e", amstradcpc: "#2fb34a", apple2: "#58b947",
    dos: "#00a6a6", "3do": "#d4af37", cdi: "#3b6fd1", arcade: "#ff3cac" };
  function platTile(p, main, store) {
    const li = el("li", { class: "plat" }, el("span", { class: "wm", "aria-hidden": "true" },
      icon(PC.has(p) ? "i-d-pc" : "i-d-console"), el("b", { text: SHORT[p] || p.toUpperCase() })), main, store || null);
    li.style.setProperty("--tint", TINTS[p] || `hsl(${hueOf(p)} 60% 50%)`);
    return li;
  }

  // The time between two releases, in the visitor's language and the unit that reads best ("11 months").
  const dayOf = (n) => { const x = String(n); return Date.UTC(+x.slice(0, 4), +x.slice(4, 6) - 1, +x.slice(6, 8)) / 86400000; };
  function gap(from, to) {
    const d = Math.round(dayOf(to) - dayOf(from));
    const [unit, n] = d < 60 ? ["day", d] : d < 730 ? ["month", Math.round(d / 30.4)] : ["year", Math.round(d / 36.5) / 10];
    return new Intl.NumberFormat(LANG, { style: "unit", unit, unitDisplay: "long", maximumFractionDigits: 1 }).format(n);
  }

  // The "By platform" tiles: the platform's own colour, its renown as a small ring, the release with how long after
  // the first it came, the reviews, what the platform adds (Game Pass, Steam Deck), a link to the store where there
  // is one, and the one it is best known on marked.
  function platformTiles(es) {
    const first = Math.min(...es.map((e) => e.release || e.upcoming || Infinity));
    const dated = new Set(es.map((e) => e.release || e.upcoming).filter(Boolean)).size > 1;
    const top = es.filter((e) => e.popular).sort((x, y) => y.popular[0] - x.popular[0])[0];
    return es.map((e) => {
      const when = e.release || e.upcoming;
      const rev = e.reviews || e.rating;
      const name = S._names[e.p] || e.p;
      const deck = e.tech && e.tech.deck >= 2 ? `Steam Deck · ${t(`x_deck_${e.tech.deck}`)}` : "";
      const lines = [];
      lines.push(el("span", { class: "plat-name" }, el("span", { class: "badge", text: name }),
        top === e && es.filter((x) => x.popular).length > 1 ? el("span", { class: "star", title: t("x_best_platform"), "aria-label": t("x_best_platform"), text: "★" }) : null));
      if (when) {
        const later = dated && when > first ? el("span", { class: "chip gap", title: t("x_later", { d: gap(first, when) }), text: `+${gap(first, when)}` }) : null;
        lines.push(el("span", { class: "plat-when" }, el("span", { class: "date", text: e.release ? ymd(when) : t("x_coming", { date: ymd(when) }) }), later,
          dated && when === first ? el("span", { class: "chip first", text: t("x_first") }) : null));
      }
      const extras = [e.gamepass ? el("span", { class: "chip", text: "Game Pass" }) : null, deck ? el("span", { class: "chip", text: deck }) : null].filter(Boolean);
      if (rev || extras.length) lines.push(el("span", { class: "plat-more" }, rev ? el("span", { class: "dim", text: t("x_reviews", { n: num(rev[0]), p: rev[1] }) }) : null, ...extras));
      const main = el("a", { class: `plat-main${e.popular ? " has-ring" : ""}`, href: `#${e.p}/game/${encodeURIComponent(e.id)}?alone` },
        e.popular ? miniRing(e.popular[0], t("x_score")) : null, ...lines, el("span", { class: "out", "aria-hidden": "true", text: "→" }));
      const shop = STORES[e.p] && /^[\w-]+$/.test(e.id) ? el("a", { class: "store", href: STORES[e.p](e.id), rel: "noreferrer noopener", referrerpolicy: "no-referrer", target: "_blank",
        title: t("x_open_store", { store: name }), "aria-label": t("x_open_store", { store: name }), text: "↗" }) : null;
      const li = platTile(e.p, main, shop);
      if (top === e && es.filter((x) => x.popular).length > 1) li.classList.add("best");
      return li;
    });
  }

  // The release dates of a game on several platforms on one axis: a row a platform (name, a dot where its date falls
  // between the first and the last, the date); the dot is for the eye, the names and dates are the text.
  function timeline(es) {
    const dated = es.filter((e) => e.release).sort((x, y) => x.release - y.release || x.p.localeCompare(y.p));
    if (dated.length < 2 || dated[0].release === dated[dated.length - 1].release) return null;
    const a = dayOf(dated[0].release), span = dayOf(dated[dated.length - 1].release) - a;
    return el("figure", { class: "timeline" }, el("figcaption", { text: t("x_timeline") }),
      el("ol", {}, ...dated.map((e) => {
        const dot = el("i", {});
        dot.style.setProperty("left", `${(((dayOf(e.release) - a) / span) * 100).toFixed(1)}%`);
        dot.style.setProperty("--tint", TINTS[e.p] || `hsl(${hueOf(e.p)} 60% 50%)`);
        return el("li", {}, el("span", { class: "tl-name", text: S._names[e.p] || e.p }), el("span", { class: "tl-track", "aria-hidden": "true" }, dot), el("span", { class: "tl-date", text: ymd(e.release) }));
      })));
  }

  // Where a score falls among the platform's: its 101 cut points counted in bands of 5, one bar a band, one line for
  // the game. The sentence under it is the chart's text.
  function distribution(q, v, platform) {
    const BANDS = 20, count = new Array(BANDS).fill(0);
    for (const x of q) count[Math.min(BANDS - 1, Math.floor(x / (100 / BANDS)))] += 1;
    const top = Math.max(...count, 1), W = 240, H = 56, w = W / BANDS;
    const p = Math.round((q.filter((x) => x < v).length / q.length) * 100);
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H + 4}`);
    svg.setAttribute("class", "dist-chart");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `${t("x_dist_title", { platform })}. ${t("x_dist_help", { p: num(p) })}`);
    count.forEach((n, i) => {
      const h = Math.max(n ? 2 : 0, (n / top) * H);
      const r = document.createElementNS(SVG, "rect");
      for (const [k, x] of [["x", (i * w + 0.5).toFixed(1)], ["y", (H - h).toFixed(1)], ["width", (w - 1).toFixed(1)], ["height", h.toFixed(1)], ["rx", "1.5"]]) r.setAttribute(k, x);
      r.setAttribute("class", i === Math.min(BANDS - 1, Math.floor(v / (100 / BANDS))) ? "band here" : "band");
      svg.append(r);
    });
    const at = Math.min(W - 1, Math.max(1, (v / 100) * W));
    const line = document.createElementNS(SVG, "line");
    for (const [k, x] of [["x1", at.toFixed(1)], ["x2", at.toFixed(1)], ["y1", "0"], ["y2", String(H + 4)], ["class", "mark"]]) line.setAttribute(k, x);
    svg.append(line);
    return el("figure", { class: "dist" }, el("figcaption", { text: t("x_dist_title", { platform }) }), svg,
      el("p", { class: "dim", text: t("x_dist_help", { p: num(p) }) }));
  }

  // The bar that slides in once the head has left the window: the game, its score, the sheet's sections (the one in
  // view marked). Buttons, not links: the address belongs to the router.
  let barOff = null;
  function sectionBar(head, name, score) {
    if (barOff) barOff();
    const targets = [...sheet.querySelectorAll(".cols section")].filter((x) => x.querySelector(":scope > h3"));
    if (!targets.length) return null;
    const ctl = new AbortController(), on = { signal: ctl.signal, passive: true };
    const buttons = targets.map((sec) => {
      const b = el("button", { type: "button", class: "tab", text: sec.querySelector(":scope > h3").textContent });
      b.addEventListener("click", () => sec.scrollIntoView({ behavior: MOTION.matches ? "smooth" : "auto", block: "start" }));
      return b;
    });
    const bar = el("div", { class: "sheet-bar", inert: "" },
      el("p", { class: "bar-title" }, el("span", { text: name }), score ? el("b", { text: String(score) }) : null),
      el("nav", { "aria-label": t("x_sections") }, ...buttons));
    let frame = 0;
    const update = () => {
      frame = 0;
      const shownBar = head.getBoundingClientRect().bottom < 0;
      bar.classList.toggle("on", shownBar);
      bar.toggleAttribute("inert", !shownBar);
      let here = -1;
      targets.forEach((sec, i) => { if (sec.getBoundingClientRect().top <= window.innerHeight * 0.3) here = i; });
      buttons.forEach((b, i) => { b.classList.toggle("here", i === here); if (i === here) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current"); });
      const cur = buttons[here];
      if (cur && shownBar) { const nav = bar.querySelector("nav"); nav.scrollLeft = cur.offsetLeft - (nav.clientWidth - cur.offsetWidth) / 2; }
    };
    const ask = () => { if (!frame) frame = requestAnimationFrame(update); };
    window.addEventListener("scroll", ask, on);
    window.addEventListener("resize", ask, on);
    barOff = () => { ctl.abort(); barOff = null; };
    ask();
    return bar;
  }

  // Where a sheet was opened from (kept for the tab): the list's address, how far it was scrolled, how many rows it
  // showed and its games in order. The sheet steps to the one before and after (arrows too), and the list comes
  // back as it was.
  const TRAIL = "atlas-trail";
  const trail = () => { try { return JSON.parse(sessionStorage.getItem(TRAIL) || "null"); } catch (e) { return null; } };
  let pagerNow = null;
  function pager(es) {
    pagerNow = null;
    const tr = trail();
    if (!tr || !Array.isArray(tr.rows)) return null;
    const mine = new Set([location.hash.split("?")[0], ...es.map((e) => `#${e.p}/game/${encodeURIComponent(e.id)}`)]);
    const at = tr.rows.findIndex(([h]) => mine.has(h));
    if (at < 0) return null;
    const step = (r, key, label, sign) => (r
      ? el("a", { class: `step ${key}`, href: r[0], rel: key, title: `${label}: ${r[1]}`, "aria-label": `${label}: ${r[1]}`, text: sign })
      : el("span", { class: `step ${key} off`, "aria-hidden": "true", text: sign }));
    const prev = tr.rows[at - 1], next = tr.rows[at + 1];
    pagerNow = { prev: prev && prev[0], next: next && next[0] };
    return el("span", { class: "pager" }, step(prev, "prev", t("x_prev"), "‹"), el("span", { class: "dim", text: `${num(at + 1)} / ${num(tr.rows.length)}` }), step(next, "next", t("x_next"), "›"));
  }

  // Favourites: games marked with a heart, kept in this browser only (a key "<platform>/<id>", or "u/<Wikidata item>"
  // for a game on several platforms, and its name).
  const FAVS = "atlas-favs";
  const favs = () => {
    try {
      const list = JSON.parse(localStorage.getItem(FAVS) || "[]");
      return Array.isArray(list) ? list.filter((f) => f && typeof f.k === "string" && f.k.includes("/")) : [];
    } catch (e) { return []; }
  };
  const keepFavs = (list) => { try { localStorage.setItem(FAVS, JSON.stringify(list.slice(-60))); } catch (e) { /* no storage: nothing kept */ } };
  const favHref = (k) => { const at = k.indexOf("/"); return gameHref(k.slice(0, at), k.slice(at + 1)); };
  const favButton = $("x-fav");
  const countFavs = () => { const n = favs().length; favButton.textContent = n ? `${t("x_favorites")} · ${num(n)}` : t("x_favorites"); };
  function heart(m, es) {
    if (es.length > 1 && !m.qid) return null;
    const k = es.length > 1 ? `u/${m.qid}` : `${es[0].p}/${es[0].id}`;
    const b = el("button", { type: "button", class: "fav" });
    const draw = () => {
      const on = favs().some((f) => f.k === k), label = t(on ? "x_fav_remove" : "x_fav_add");
      b.classList.toggle("on", on);
      b.textContent = on ? "♥" : "♡";
      b.title = label;
      b.setAttribute("aria-label", label);
    };
    b.addEventListener("click", () => {
      keepFavs(favs().some((f) => f.k === k) ? favs().filter((f) => f.k !== k) : favs().concat({ k, name: m.name || m.id || "" }));
      draw();
      countFavs();
    });
    draw();
    return b;
  }

  function renderSheet(m, backHref) {
    if (barOff) barOff();
    sheet.replaceChildren();
    sheet.hidden = false;
    const es = m.platforms;
    // The way back is a round button that stays in the corner of the window, not a link on the picture.
    const back = el("a", { class: "back fab", href: backHref, title: t("x_back"), "aria-label": t("x_back"), text: "←" });
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
    // The players' rating (IGDB, from 20 ratings) and each store's share of good reviews are rings too.
    const voters = es.filter((e) => e.igdb_rating && e.igdb_rating[1] >= 20).sort((x, y) => y.igdb_rating[1] - x.igdb_rating[1])[0];
    if (voters) rings.append(ring(voters.igdb_rating[0], t("x_players_rating"), t("x_players_help", { n: num(voters.igdb_rating[1]) }), ringHelp));
    for (const e of es) {
      for (const r of [e.reviews, e.rating]) {
        if (r && r[0]) rings.append(ring(r[1], storeName(e.p), t("x_store_help", { p: r[1], n: num(r[0]), store: storeName(e.p) }), ringHelp));
      }
    }
    // The platforms are the tiles' where there are several: the line under the title is then the id alone (and its
    // missing name). The Wikidata item is among the links.
    const ids = el("p", { class: "ids" }, es.length === 1 ? el("span", { class: "badge", text: S._names[es[0].p] || es[0].p }) : null,
      m.name && m.id ? el("code", { text: m.id }) : null,
      !m.name ? el("small", { text: t("x_no_name") }) : null);
    const info = el("div", { class: "info" }, logo, title, ids.childElementCount ? ids : null,
      rings.childElementCount ? rings : null, rings.childElementCount ? ringHelp : null);
    const top = el("div", { class: "topline" }, el("span", { class: "tools" }, pager(es), heart(m, es)));
    const head = el("header", { class: wide ? "masthead" : "" }, top, cover,
      wide ? el("div", { class: "banner" }, shown.poster ? pictureCover(m, shown.poster, "poster") : null, info) : info);
    if (logo) {
      logo.addEventListener("load", () => head.classList.add("has-logo"));
      logo.addEventListener("error", () => logo.remove());
    }
    if (wide) sheet.append(backdrop(shown.backdrops, shown.poster));
    sheet.classList.toggle("with-backdrop", !!wide);
    sheet.append(back, head);     // outside the head, whose entrance animation would make it the button's frame

    const stats = el("dl", { class: "stats" });
    const stat = (label, value) => { if (value !== null && value !== undefined && value !== "") stats.append(el("div", {}, el("dt", { text: label }), el("dd", {}, value))); };
    // A store's reviews: the share of good ones large, in the rings' colours, how many under it.
    // (The stores' shares of good reviews and the players' rating are rings in the head; their counts here.)
    if (best && best.popular[1]) stat(t("x_trend"), trend(best.popular[1]));
    for (const e of es) {
      for (const r of [e.reviews, e.rating]) if (r && r[0]) stat(storeName(e.p), t("x_review_count", { n: num(r[0]) }));
    }
    const out = es.map((e) => e.release).filter(Boolean);
    const soon = es.map((e) => e.upcoming).filter(Boolean);
    if (out.length) stat(t("x_release"), ymd(Math.min(...out)));
    else if (soon.length) stat(t("x_release"), t("x_coming", { date: ymd(Math.min(...soon)) }));
    if (stats.childElementCount) sheet.append(stats);
    // Where the game stands on its best known platform (its stats.json, a few kB, asked after the sheet is drawn).
    if (best) {
      const where = el("p", { class: "insights", hidden: "" });
      sheet.append(where);
      get(`x/${best.p}/stats.json`).then((st) => {
        const plat = S._names[best.p] || best.p, items = [];
        const q = (st.renown && st.renown.q) || [];
        if (q.length) {
          const p = Math.round((q.filter((x) => x < best.popular[0]).length / q.length) * 100);
          if (p >= 50) items.push(el("span", { class: "chip insight" }, t("x_rank", { p: num(p), platform: plat })));
        }
        const c = best.popular[2], avg = st.critics && st.critics.mean;
        if (c && avg) {
          const d = Math.round(c - avg);
          if (d) items.push(el("span", { class: `chip insight ${d > 0 ? "above" : "below"}` }, t(d > 0 ? "x_vs_above" : "x_vs_below", { d: num(Math.abs(d)), platform: plat, avg: fmt1.format(avg) })));
        }
        where.replaceChildren(...items);
        where.hidden = !items.length;
        if (q.length) where.after(distribution(q, best.popular[0], plat));
      }, () => where.remove());
    }
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
        dl.append(el("div", {}, el("dt", {}, icon(`i-k-${kind}`), t(`x_${kind}`)), el("dd", {}, ...names.map((n) => {
          const c = chip(kind, n, traitHref(kind, n));
          if (c.href) { c.dataset.kind = kind; c.dataset.value = n; }
          return c;
        }))));
      }
      main.append(dl);
      // How many games of the platform have it, once its menus are in (a few kB, the browse view's own).
      const homeName = S._names[home] || home;
      get(`x/${home}/facets.json`).then((f) => {
        for (const c of dl.querySelectorAll("a.chip[data-kind]")) {
          const found = ((f.facets || {})[c.dataset.kind] || []).find(([v]) => v === c.dataset.value);
          if (!found) continue;
          const sentence = t("x_trait_count", { n: num(found[1]), platform: homeName });
          const label = c.textContent;
          c.append(el("small", { class: "n", text: num(found[1]) }));
          c.title = sentence;
          c.setAttribute("aria-label", `${label}: ${sentence}`);
        }
      }, () => {});
    }
    const technical = techBlock(es, m.wd);
    if (technical) side.append(technical);

    if (es.length > 1) {
      side.append(section(t("x_by_platform"), el("ul", { class: "byplat" }, ...platformTiles(es)), timeline(es)));
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

    // The games of its series, oldest first (the build's `family`): the one on this sheet marked.
    if (m.family && m.family[1].length > 1) {
      main.append(section(`${t("x_series")} · ${labelOf("series", m.family[0])}`, el("ul", { class: "cardgrid family carousel" }, ...m.family[1].map(([kind, ref, name, when, pic]) => {
        const here = es.some((e) => e.p === kind && e.id === ref);
        const c = card(gameHref(kind, ref), kind, ref, name, when ? [el("span", { class: "dim", text: String(Math.floor(when / 10000)) })] : [], pic);
        if (here) { c.setAttribute("aria-current", "page"); c.classList.add("here"); }
        return el("li", {}, c);
      }))));
    }

    // Not the game itself (a platform's list can name the sheet of all its platforms, or one of them).
    // Nor another entry of it under the same name (an edition the links do not tie to it).
    const alike = (m.similar || []).filter(([kind, ref, name]) => !(kind === "u" && ref === m.qid) && !es.some((e) => e.p === kind && e.id === ref)
      && !(name && m.name && fold(name) === fold(m.name)));
    if (alike.length) {
      // On a sheet of several platforms a game that is on one only says which; the figure is how alike, not how known.
      main.append(section(t("x_similar"), el("ul", { class: "cardgrid alike carousel" }, ...alike.map(([kind, ref, name, s, pic, shared]) =>
        el("li", {}, card(gameHref(kind, ref), kind, ref, name, [el("span", { class: "sim", text: t("x_alike_pct", { n: num(s) }) })], pic,
          { shared, badge: es.length > 1 && kind !== "u" ? S._names[kind] || kind : "" }))))));
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
    if (/^Q\d+$/.test(m.qid || "")) open(`Wikidata · ${m.qid}`, `https://www.wikidata.org/wiki/${m.qid}`);
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
    const bar = sectionBar(head, m.name || m.id || "", best ? best.popular[0] : 0);
    if (bar) sheet.append(bar);
    bars(sheet);
    reveal(sheet);
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

  // The platform's figures: stats.json, condensed at the build (tools/site_data.py `stats()`), and x/stats.json,
  // every platform's headline figures side by side. One hue for every series (Boréale's ice): one measure a chart.
  const statsBox = $("x-stats"), tipBox = $("x-tip");
  const fmt1 = new Intl.NumberFormat(LANG, { maximumFractionDigits: 1 });

  function figure(label, value, digits, i) {
    if (value === null || value === undefined) return null;
    const b = el("b", { "data-count": String(value), "data-digits": String(digits || 0), text: digits ? fmt1.format(value) : num(value) });
    const d = el("div", { class: "fig" }, b, el("span", { text: label }));
    d.style.setProperty("--i", String(i || 0));
    return d;
  }

  // Columns: [label, value, tip], the tallest full height. The marks are a picture (aria-hidden); the same figures
  // are a table under it for screen readers and for reading the numbers.
  function columns(items, every, head) {
    const top = Math.max(1, ...items.map((x) => x[1]));
    const chart = el("div", { class: "colchart", "aria-hidden": "true" }, ...items.map(([label, value, tip], i) =>
      el("div", { class: "col", "data-tip": tip }, el("span", { class: "colbar" }, el("i", { "data-h": String((value / top) * 100) })),
        el("small", { text: i % every === 0 || i === items.length - 1 ? label : "" }))));
    const table = el("details", { class: "as-table" }, el("summary", { text: t("x_st_table") }),
      el("table", {}, el("thead", {}, el("tr", {}, el("th", { scope: "col", text: head }), el("th", { scope: "col", class: "num", text: t("x_st_games") }))),
        el("tbody", {}, ...items.map(([label, value]) => el("tr", {}, el("th", { scope: "row", text: label }), el("td", { class: "num", text: num(value) }))))));
    return [chart, table];
  }

  // Horizontal bars: [label, value, aside, href, icon], each a row of text a screen reader reads as it is.
  // (`scale`, the value of a full bar, when several lists share one.)
  function hbars(items, scale) {
    const top = scale || Math.max(1, ...items.map((x) => x[1]));
    return el("ol", { class: "hbars" }, ...items.map(([label, value, aside, href, ico]) => {
      const inner = [el("span", { class: "hb-name" }, ico || null, el("span", { text: label })),
        el("span", { class: "hb-bar" }, el("i", { "data-w": String((value / top) * 100) })),
        el("span", { class: "hb-n", text: num(value) }), aside ? el("span", { class: "hb-aside", text: aside }) : el("span", { class: "hb-aside" })];
      return el("li", {}, href ? el("a", { href }, ...inner) : el("div", {}, ...inner));
    }));
  }

  async function statsView(platform) {
    leaveBrowse();
    sheet.hidden = true;
    results.hidden = true;
    pressed("x-views", "view", "stats");
    setStatus(t("x_loading"));
    const [st, every] = await Promise.all([get(`x/${platform}/stats.json`), get("x/stats.json").catch(() => null)]);
    const avg = (v) => (v === null || v === undefined ? "" : t("x_st_avg", { n: fmt1.format(v) }));
    const browseBy = (kind, value) => `#${platform}/browse?${new URLSearchParams([[kind, value]])}`;
    const parts = [];
    const share = st.games ? Math.round((st.critics.n / st.games) * 100) : 0;
    const figs = el("div", { class: "figs" },
      figure(t("x_st_games"), st.games, 0, 0), figure(t("x_st_mean"), st.critics.mean, 1, 1),
      figure(`${t("x_st_rated")} (%)`, share, 0, 2), figure(t("x_score"), st.renown.mean, 1, 3));
    parts.push(el("p", { class: "dim", text: t("x_st_note", { n: num(st.games), date: st.generated || "" }) }), figs);
    if (st.critics.n) {
      const bins = st.critics.hist.map((n, i) => [`${i * 10}`, n, t("x_st_tip_bin", { from: i * 10, to: i === 9 ? 100 : i * 10 + 9, n: num(n) })]);
      parts.push(section(t("x_st_critics_dist"), ...columns(bins, 1, t("x_critics"))));
    }
    if (st.years.length > 2) {
      const ys = st.years.map(([y, n, c]) => [String(y), n, `${t("x_st_tip_year", { year: y, n: num(n) })}${c ? ` · ${avg(c)}` : ""}`]);
      parts.push(section(t("x_st_years"), ...columns(ys, 5, t("x_year"))));
    }
    const grid = el("div", { class: "fig-grid" });
    if (st.genres.length) grid.append(section(t("x_st_genres"), hbars(st.genres.map(([g, n, c]) => [labelOf("genres", g), n, avg(c), browseBy("genres", g), iconOf("genres", g)]))));
    if (st.modes && st.modes.length) grid.append(section(t("x_modes"), hbars(st.modes.map(([m, n]) => [labelOf("modes", m), n, "", browseBy("modes", m), iconOf("modes", m)]))));
    if (st.developers.length) grid.append(section(t("x_st_developers"), hbars(st.developers.map(([d, n, c]) => [d, n, avg(c), browseBy("developers", d)]))));
    if (st.publishers.length) grid.append(section(t("x_st_publishers"), hbars(st.publishers.map(([d, n, c]) => [d, n, avg(c), browseBy("publishers", d)]))));
    if (grid.childElementCount) parts.push(grid);
    const games = (list) => el("ul", { class: "cardgrid carousel" }, ...list.map(([id, name, c, r, pic]) =>
      el("li", {}, card(`#${platform}/game/${encodeURIComponent(id)}`, platform, id, name, [el("span", { class: `pct ${toneOf(c)}`, text: String(c) }), score(r)], pic))));
    if (st.best.length) parts.push(section(t("x_st_best"), games(st.best)));
    if (st.gems.length) parts.push(section(t("x_st_gems"), el("p", { class: "dim", text: t("x_st_gems_note") }), games(st.gems)));
    if (every && every.platforms.length > 1) {
      // The fifteen with the most games in view, the others behind one fold (the same scale for all).
      const rowsOf = every.platforms.map(([p, n, , c]) => [S._names[p] || p, n, avg(c), `#${p}/stats`]);
      const top = Math.max(1, ...rowsOf.map((r) => r[1]));
      const rest = rowsOf.slice(15);
      parts.push(section(t("x_st_platforms"), hbars(rowsOf.slice(0, 15), top),
        rest.length ? el("details", { class: "as-table" }, el("summary", { text: `+${num(rest.length)}` }), hbars(rest, top)) : null));
    }
    statsBox.replaceChildren(...parts);
    statsBox.hidden = false;
    bars(statsBox);
    countUp(statsBox);
    reveal(statsBox);
    setStatus(t("x_loaded", { size: kb(read) }));
  }

  // One tooltip for every chart's marks (data-tip), placed by the pointer; a mark's figures are in its table too.
  document.addEventListener("pointerover", (e) => {
    const m = e.target.closest && e.target.closest("[data-tip]");
    if (!m) { tipBox.hidden = true; return; }
    tipBox.textContent = m.dataset.tip;
    tipBox.hidden = false;
  });
  document.addEventListener("pointermove", (e) => {
    if (tipBox.hidden) return;
    const w = tipBox.offsetWidth, x = Math.min(window.innerWidth - w - 8, Math.max(8, e.clientX - w / 2));
    tipBox.style.left = `${x}px`;
    tipBox.style.top = `${Math.max(8, e.clientY - tipBox.offsetHeight - 14)}px`;
  });

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
    renderSheet(platformSheet(platform, id, g), backTo(platform));
  }

  // The sheet of one platform's game, as renderSheet and the comparison take it.
  function platformSheet(platform, id, g) {
    const entry = { p: platform, id };
    for (const k of ["release", "upcoming", "popular", "reviews", "rating", "igdb_rating", "igdb_cover", "igdb_art", "views", "steam", "gamepass", "tech", "editions", "edition_of"]) if (g[k]) entry[k] = g[k];
    return { name: g.name, id, qid: g.qid, wd: g.wd, platforms: [entry], traits: g.traits,
      similar: (g.similar || []).map(([o, name, s, pic, shared]) => [platform, o, name, s, pic, shared]),
      family: g.family ? [g.family[0], g.family[1].map((r) => [platform, ...r])] : null, links: g.links };
  }

  // The favourites as a list, each with a box: two or three ticked are compared.
  async function favoritesView() {
    leaveBrowse();
    sheet.hidden = true;
    results.hidden = false;
    pressed("x-views", "view", "favorites");
    const list = favs();
    if (!list.length) {
      results.replaceChildren();
      setStatus(t("x_fav_empty"));
      return;
    }
    const picked = new Set(), boxes = [];
    const compare = el("button", { type: "button", class: "compare", disabled: "", text: t("x_compare_pick") });
    const sync = () => {
      compare.disabled = picked.size < 2;
      compare.textContent = picked.size >= 2 ? t("x_compare_n", { n: num(picked.size) }) : t("x_compare_pick");
      for (const b of boxes) b.disabled = picked.size >= 3 && !b.checked;
    };
    compare.addEventListener("click", () => go(`#${route().platform}/compare?${new URLSearchParams([...picked].map((k) => ["g", k]))}`));
    const items = list.slice().reverse().map((f) => {
      const at = f.k.indexOf("/"), kind = f.k.slice(0, at), ref = f.k.slice(at + 1);
      const box = el("input", { type: "checkbox", "aria-label": `${t("x_compare")}: ${f.name || ref}` });
      box.addEventListener("change", () => { if (box.checked) picked.add(f.k); else picked.delete(f.k); sync(); });
      boxes.push(box);
      const drop = el("button", { type: "button", class: "unfav", title: t("x_fav_remove"), "aria-label": `${t("x_fav_remove")}: ${f.name || ref}`, text: "×" });
      drop.addEventListener("click", () => { keepFavs(favs().filter((x) => x.k !== f.k)); countFavs(); favoritesView(); });
      return el("li", { class: "fav-item" }, box, el("a", { href: favHref(f.k) }, tile(kind, ref, f.name, true, ""), nameOf(ref, f.name)), drop);
    });
    results.replaceChildren(el("li", { class: "fav-bar" }, el("span", { class: "dim", text: t("x_fav_note") }), compare), ...items);
    setStatus(`${t("x_favorites")} · ${num(list.length)}`);
  }

  // A game's sheet from a favourite's key.
  async function sheetOfKey(k) {
    const at = k.indexOf("/"), kind = k.slice(0, at), ref = k.slice(at + 1);
    if (kind === "u") {
      const meta = await get("x/u/meta.json");
      const u = (await get(`x/u/${shard(ref, meta.shards)}.json`))[ref];
      return u ? Object.assign({ qid: ref }, u) : null;
    }
    if (!PLATFORMS.includes(kind)) return null;
    const lists = await get(`x/${kind}/lists.json`);
    const g = (await get(`x/${kind}/g/${shard(ref, lists.shards)}.json`))[ref];
    return g ? platformSheet(kind, ref, g) : null;
  }

  // Two or three games side by side: a table, a game a column, the figures as small rings, the highest marked.
  async function compareView(query) {
    leaveBrowse();
    results.hidden = true;
    pressed("x-views", "view", "favorites");
    setStatus(t("x_loading"));
    const got = (await Promise.all(query.getAll("g").slice(0, 3).map((k) => sheetOfKey(k).catch(() => null)))).filter(Boolean);
    const back = el("a", { class: "back", href: `#${route().platform}/favorites` }, `← ${t("x_favorites")}`);
    sheet.hidden = false;
    sheet.classList.remove("with-backdrop");
    if (got.length < 2) {
      sheet.replaceChildren(back, el("p", { text: t("x_not_found") }));
      setStatus("");
      return;
    }
    const facts = got.map((m) => {
      const es = m.platforms, top = es.filter((e) => e.popular).sort((x, y) => y.popular[0] - x.popular[0])[0];
      const voters = es.filter((e) => e.igdb_rating && e.igdb_rating[1] >= 20).sort((x, y) => y.igdb_rating[1] - x.igdb_rating[1])[0];
      const out = es.map((e) => e.release).filter(Boolean);
      return { score: top ? top.popular[0] : 0, critics: Math.max(0, ...es.map((e) => (e.popular ? e.popular[2] : 0))), players: voters ? voters.igdb_rating[0] : 0,
        release: out.length ? Math.min(...out) : 0 };
    });
    const figure = (key, label) => {
      const values = facts.map((f) => f[key]), best = Math.max(...values);
      return [label, values.map((v) => (v ? el("span", { class: "cv" }, miniRing(v, label),
        best > 0 && v === best && values.some((x) => x !== best) ? el("span", { class: "lead", title: t("x_highest"), "aria-label": t("x_highest"), text: "★" }) : null) : el("span", { class: "dim", text: "–" })))];
    };
    const names = (m) => m.platforms.map((e) => S._names[e.p] || e.p).join(", ");
    const rows = [figure("score", t("x_score")), figure("critics", t("x_critics")), figure("players", t("x_players_rating")),
      [t("x_release"), facts.map((f) => (f.release ? el("span", { text: ymd(f.release) }) : el("span", { class: "dim", text: "–" })))],
      [t("x_by_platform"), got.map((m) => el("span", { text: names(m) }))],
      [t("x_genres"), got.map((m) => el("span", { class: "chips" }, ...((m.traits && m.traits.genres) || []).slice(0, 4).map((n) => chip("genres", n))))],
      [t("x_series"), got.map((m) => ((m.traits && m.traits.series) ? el("span", { text: labelOf("series", m.traits.series[0]) }) : el("span", { class: "dim", text: "–" })))]];
    const heads = got.map((m) => {
      const e = m.platforms[0], cover = (m.platforms.find((x) => x.igdb_cover) || {}).igdb_cover;
      return el("th", { scope: "col" }, el("a", { href: m.platforms.length > 1 ? gameHref("u", m.qid) : gameHref(e.p, e.id) },
        tile(e.p, e.id, m.name, false, cover ? `i${cover}` : ""), el("span", { class: "name", text: m.name || e.id })));
    });
    const table = el("table", { class: "compare" }, el("thead", {}, el("tr", {}, el("th", { scope: "col", class: "corner", text: t("x_compare") }), ...heads)),
      el("tbody", {}, ...rows.map(([label, cells]) => el("tr", {}, el("th", { scope: "row", text: label }), ...cells.map((c) => el("td", {}, c))))));
    sheet.replaceChildren(back, el("h2", { tabindex: "-1", text: t("x_compare_n", { n: num(got.length) }) }), el("div", { class: "compare-wrap" }, table));
    setStatus("");
    window.scrollTo({ top: sheet.getBoundingClientRect().top + window.scrollY - 16 });
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
  let restore = null;      // the trail of the list being shown again, to put it back as it was
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
    if (restore && restore.n > limit) limit = restore.n;
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
    document.body.classList.toggle("x-on-sheet", view === "game" || view === "ugame" || view === "compare");
    if (barOff && view !== "game" && view !== "ugame") barOff();
    const tr = trail();
    restore = tr && tr.hash === location.hash && !["game", "ugame", "compare", "favorites"].includes(view) ? tr : null;
    statsBox.hidden = view !== "stats";
    tipBox.hidden = true;
    pressed("x-platforms", "platform", platform);
    machine.value = [...machine.options].some((o) => o.value === platform) ? platform : "";
    try {
      if (view === "browse") await browse(platform, query);
      else if (view === "ugame") await unified(arg);
      else if (view === "game") await game(platform, arg, query);
      else if (view === "stats") await statsView(platform);
      else if (view === "favorites") await favoritesView();
      else if (view === "compare") await compareView(query);
      else if (view === "searchall") { if (search.value !== arg) search.value = arg; await findAll(arg); }
      else if (view === "search") { if (search.value !== arg) search.value = arg; await find(platform, arg); }
      else await list(platform, view);
      // Back to a list a sheet was opened from: where it was scrolled.
      if (restore) { const y = restore.y; requestAnimationFrame(() => window.scrollTo(0, y)); }
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
  // A card or a platform's tile leans toward the pointer and catches a glint of light (a fine pointer that hovers, and
  // only for visitors who have not asked for less motion): the custom properties are read by site.css.
  const FINE = window.matchMedia("(hover: hover) and (pointer: fine)");
  document.addEventListener("pointermove", (e) => {
    if (!MOTION.matches || !FINE.matches || !e.target.closest) return;
    const c = e.target.closest(".cardgrid a.card, .byplat li.plat");
    if (!c) return;
    const r = c.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    const k = c.matches(".plat") ? 3 : 7;
    c.style.setProperty("--ry", `${((x - 0.5) * 2 * k).toFixed(2)}deg`);
    c.style.setProperty("--rx", `${((0.5 - y) * 2 * k).toFixed(2)}deg`);
    c.style.setProperty("--mx", `${(x * 100).toFixed(1)}%`);
    c.style.setProperty("--my", `${(y * 100).toFixed(1)}%`);
  });
  document.addEventListener("pointerout", (e) => {
    const c = e.target.closest && e.target.closest(".cardgrid a.card, .byplat li.plat");
    if (c && !c.contains(e.relatedTarget)) for (const v of ["--rx", "--ry", "--mx", "--my"]) c.style.removeProperty(v);
  });

  results.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a[href^='#']");
    if (!a || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || !/^#(game|[\w-]+\/game)\//.test(a.getAttribute("href"))) return;
    const rows = [...results.querySelectorAll("a[href^='#']")].filter((x) => /^#(game|[\w-]+\/game)\//.test(x.getAttribute("href"))).slice(0, 400)
      .map((x) => [x.getAttribute("href"), ((x.querySelector(".name") || x).textContent || "").trim()]);
    try { sessionStorage.setItem(TRAIL, JSON.stringify({ hash: location.hash, y: Math.round(window.scrollY), n: results.children.length, rows })); } catch (err) { /* no storage: no trail */ }
  });
  // The arrows step through the list a sheet was opened from.
  document.addEventListener("keydown", (e) => {
    if (!pagerNow || sheet.hidden || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || !["ArrowLeft", "ArrowRight"].includes(e.key)
      || (e.target.closest && e.target.closest("input, select, textarea, [contenteditable], dialog"))) return;
    const to = e.key === "ArrowLeft" ? pagerNow.prev : pagerNow.next;
    if (to) { e.preventDefault(); go(to); }
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
  countFavs();
  show();
})();
