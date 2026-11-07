// boreale-site (README.md), the same in each of Boréale's sites (each its
// own origin, so its own memory). The language chosen in the header's menu
// is kept ("boreale-lang": the folder, "en-US" for English) and an English
// page that has a translation sends a visitor who chose another language to
// it, at the same place (#hash). At a first visit, nothing chosen, the
// English home page (the root, marked data-first-visit) sends a visitor
// whose browser prefers one of the site's other languages to its folder
// (/fr/, /de/, /zh-hant/...). The page not found follows the same choice:
// one 404.html per folder (data-lost) or one holding every language
// (.not-found[data-lang] blocks). Loaded in <head>, before the page is
// drawn, so the move shows nothing. Never document.referrer: every page
// sends none.
//
// For the site's own scripts: window.boreale.lang, the folder chosen (or
// null), and window.boreale.browser(), the browser's (null for English).
(function () {
  const KEY = "boreale-lang";
  // The site's languages by their folder (boreale_site's LANGUAGES); the
  // first, English, at the root, by its code (the menu's data-lang).
  const SITE = ["en-US", "fr", "fr-ca", "de", "es", "es-419", "it", "nl", "pt", "pt-br", "ru", "ja", "ko",
    "zh-hans", "zh-hant"];
  let chosen = null;
  try { chosen = localStorage.getItem(KEY); } catch (e) { /* storage refused: no memory */ }
  // English chosen before its code was en-US ("en", boreale.dev's and
  // Atlas's menus until boreale-site#2): kept as "en-US" once. To delete
  // after 2027-01-31 (workbench plans/boreale/suivi.md).
  if (chosen === "en") {
    chosen = "en-US";
    try { localStorage.setItem(KEY, chosen); } catch (e) { /* idem */ }
  }

  const root = document.documentElement;
  // The browser's first language the site has (English stops the search):
  // Canada's French, Spain's Spanish or Latin America's, Brazil's Portuguese
  // or Portugal's, Traditional Chinese (Taiwan, Hong Kong, Macao) or Simplified.
  const browser = () => {
    for (const tag of navigator.languages || [navigator.language || ""]) {
      const t = String(tag).toLowerCase();
      const [base, region = ""] = t.split("-");
      if (base === "en") return null;
      if (base === "fr") return region === "ca" ? "fr-ca" : "fr";
      if (base === "es") return !region || region === "es" ? "es" : "es-419";
      if (base === "pt") return region === "br" ? "pt-br" : "pt";
      if (base === "zh") return ["tw", "hk", "mo", "hant"].includes(region) || t.includes("hant") ? "zh-hant" : "zh-hans";
      if (SITE.includes(base)) return base;
    }
    return null;
  };
  window.boreale = { lang: SITE.includes(chosen) ? chosen : null, browser };

  // The site's path (/, /Atlas/): where this file is, in its assets/.
  const script = document.currentScript && document.currentScript.src;
  const site = script ? new URL("..", script).pathname : "/";
  const lost = root.getAttribute("data-lost");
  // The language folder of an address, if it is in one.
  const folderOf = (base) => {
    if (!location.pathname.startsWith(base)) return null;
    const first = location.pathname.slice(base.length).split("/")[0].toLowerCase();
    return first !== "en-us" && SITE.includes(first) ? first : null;
  };

  // An English page: to the language chosen when the page has it (its
  // rel=alternate hreflang, or the home page), to the browser's on a first
  // visit to the home page.
  if (lost === null && !folderOf(site) && location.pathname.startsWith(site)) {
    const home = root.hasAttribute("data-first-visit");
    const translated = (folder) => home || Array.from(document.querySelectorAll('link[rel="alternate"][hreflang]'))
      .some((l) => l.hreflang.toLowerCase() === (folder === "pt" ? "pt-pt" : folder));
    const wanted = chosen ? chosen : home ? browser() : null;
    if (wanted && wanted !== SITE[0] && SITE.includes(wanted) && translated(wanted)) {
      location.replace(`${site}${wanted}/${location.pathname.slice(site.length)}${location.search}${location.hash}`);
      return;
    }
  }

  // A page that is not there: GitHub Pages serves the root's 404.html (in
  // the first language, data-lost holding the site's path) at any address.
  // It sends to the 404.html of the language the address is in (/fr/...),
  // else of the one chosen, else of the browser's.
  if (lost !== null) {
    const wanted = folderOf(lost) || (SITE.includes(chosen) ? chosen : browser());
    if (wanted && wanted !== SITE[0]) {
      location.replace(`${lost}${wanted}/404.html`);
      return;
    }
  }

  // Or one 404.html, served at any address, holding a .not-found block per
  // language (data-lang: its code or folder, the English one shown): the
  // address' language, else the one chosen, else the browser's, shown with
  // <html lang> and the title in it.
  const notFound = () => {
    const blocks = Array.from(document.querySelectorAll(".not-found[data-lang]"));
    if (blocks.length < 2) return;
    const byFolder = (f) => f && blocks.find((b) => (b.dataset.lang === "en-US" ? "en-US" : b.dataset.lang.toLowerCase()) === f);
    const english = byFolder("en-US");
    const block = byFolder(folderOf(site)) || byFolder(chosen) || byFolder(browser()) || english;
    if (!block) return;
    for (const b of blocks) b.hidden = b !== block;
    root.lang = block.lang || root.lang;
    const heading = (b) => b && b.querySelector("h1") && b.querySelector("h1").textContent;
    if (english && heading(english) && heading(block)) document.title = document.title.replace(heading(english), heading(block));
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", notFound);
  else notFound();

  // A language chosen in the header's menu (its links' data-lang, the
  // folder): kept, and the page opens at the same place (#hash) in it.
  document.addEventListener("click", (event) => {
    const link = event.target.closest && event.target.closest("a[data-lang]");
    if (!link) return;
    try { localStorage.setItem(KEY, link.getAttribute("data-lang")); } catch (e) { /* idem */ }
    if (!location.hash || link.hash || event.defaultPrevented || event.button !== 0
        || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    location.href = link.href + location.hash;
  });
})();
