# Atlas's website

`https://atlas.boreale.dev/` (until its domain is set: `https://jigsawfr.github.io/Atlas/`; every link inside it is relative, so it works at both): the project page and the explorer, in the fifteen languages of Boréale's sites.

```sh
git clone --depth 1 -b data https://github.com/JigSawFr/Atlas data   # the data branch
python3 tools/build_site.py build data    # the pages, data/ and x/ (some 80 MB)
python3 tools/check_site.py build         # links, catalogs, CSP, the explorer's shards
python3 -m http.server -d build           # then http://localhost:8000/
SITE_AXE=axe.min.js python3 tools/site_layout.py build   # phones to desktop, with axe (Playwright)
```

- `template.html` is every page's frame; `home.html` the project page, `explore.html` the explorer (`assets/explore.js`). Each `{{key}}` is a text of `i18n/<language>.json`; the explorer's texts are the catalog's `x_` keys, put in the page as JSON data.
- `build_site.py` publishes the data branch as it is under `data/`, and `site_data.py` cuts it for the explorer under `x/<platform>/`: `lists.json` (the best known, the trending, the coming soon), `deals/<country>.json` (the sales above a floor price, the best known first), `names.json` (for the search) and `g/<shard>.json` (each game's sheet: what every file says of it, its prices in every country, its ids on the other stores). A sheet costs one small file; the explorer reads nothing else from anywhere.
- The look is Boréale's (`branding/README.md` in JigSawFr/boreale): the night, the aurora once at the top, Sora, Figtree and JetBrains Mono served with the site. `assets/mark.svg` is Atlas's mark (the frame in the aurora's colours, a folded map and the pole star in snow); `social-preview.html` is the source of `assets/social-preview.png`, taken with Chromium at 1280 × 640.
- The Content-Security-Policy allows nothing but the site itself: no inline script (the explorer's texts are `application/json` data), no style attribute, no font or script from elsewhere; the one address a page may send to is Umami's (`connect-src`).
- **The audience**, counted by Umami Cloud (<https://cloud.umami.is>): `assets/umami.js` is its tracker, served with the site, that sends each page seen to `gateway.umami.is`, without cookie, and only from the site's own address (`SITE_URL`'s, not a local copy). It is a copy (Boréale's sites share it): take it again from <https://cloud.umami.is/script.js> when Umami changes it. Its site in Umami (`UMAMI_WEBSITE` in `tools/build_site.py`) is Boréale's, shared with the other projects' sites: Umami's *Hostname* filter tells them apart. The footer links to boreale.dev's privacy and legal notice, which says what it counts.
- `.github/workflows/site.yml` builds it and publishes it to GitHub Pages after each successful `build` or `daily` run, at each push to main touching it, and on demand.
