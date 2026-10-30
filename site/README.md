# Atlas's website

`https://atlas.boreale.dev/` (until its domain is set: `https://jigsawfr.github.io/Atlas/`; every link inside it is relative, so it works at both): the project page and the explorer, in the fifteen languages of Boréale's sites.

```sh
git submodule update --init               # library/boreale-site, what Boréale's sites share
git clone --depth 1 -b data https://github.com/JigSawFr/Atlas data   # the data branch
python3 tools/build_site.py build data    # the pages, data/ and x/ (some 80 MB)
python3 tools/check_site.py build         # links, catalogs, CSP, the explorer's shards, its size (Pages: 1 GB)
python3 -m http.server -d build           # then http://localhost:8000/
SITE_AXE=axe.min.js python3 library/boreale-site/tools/site_layout.py build --skip data --skip x   # phones to desktop, with axe (Playwright; site.yml's adds the explorer's views)
```

- `template.html` is every page's frame; `home.html` the project page, `explore.html` the explorer (`assets/explore.js`), `status.html` the data's status (`status_body()` in `build_site.py`, from the data branch's `report.json` and `index.json`: each source's and platform's last day, marked late past its rhythm, 2 days or 9, against the report's day, and by `assets/site.js` against today; a note when there is no report). Each `{{key}}` is a text of `i18n/<language>.json`; the explorer's texts are the catalog's `x_` keys, put in the page as JSON data.
- `build_site.py` publishes the data branch as it is under `data/`, and `site_data.py` cuts it for the explorer under `x/<platform>/`: `lists.json` (the best known, the trending, the coming soon), `names.json` (for the search) and `g/<shard>.json` (each game's sheet: what every file says of it, its ids on the other stores). A sheet costs one small file; the explorer reads nothing else from anywhere.
- The look is Boréale's (`branding/README.md` in JigSawFr/boreale): the night, the aurora once at the top, Sora, Figtree and JetBrains Mono served with the site. What Boréale's sites share is [boreale-site](https://github.com/JigSawFr/boreale-site), the submodule `library/boreale-site`: the fonts, the marks (`marks/atlas.svg` is Atlas's: the frame in the aurora's colours, a folded map and the pole star in snow), `boreale.css` and `boreale.js` (the colours, the language menu and the menu of Boréale's sites), `lang.js`, `umami.js` and the texts of the two menus, copied into `assets/` at the build (`boreale.copy_assets()`); `social-preview.html` is the source of `assets/social-preview.png`, taken with Chromium at 1280 × 640.
- **The header**: the name opens the menu of Boréale's sites (boreale-site's `Site.switcher()` and `sites.json`), a popover placed by its `boreale.js`. A link to another of them keeps the origin and carries `utm_source=atlas&utm_medium=nav` (`Site.links_out()`, over every page). Unlike Lantern's, it shows no versions: the build reads nothing from boreale.dev.
- The Content-Security-Policy allows nothing but the site itself: no inline script (the explorer's texts are `application/json` data), no style attribute, no font or script from elsewhere; the one address a page may send to is Umami's (`connect-src`).
- **The audience**, counted by Umami Cloud (<https://cloud.umami.is>): `assets/umami.js` (boreale-site's copy) is its tracker, served with the site, that sends each page seen to `gateway.umami.is`, without cookie, and only from the site's own address (`SITE_URL`'s, not a local copy). Its site in Umami (boreale-site's `UMAMI_WEBSITE`) is Boréale's, shared with the other projects' sites: Umami's *Hostname* filter tells them apart. The footer links to boreale.dev's privacy and legal notice, which says what it counts.
- `.github/workflows/site.yml` builds it and publishes it to GitHub Pages after each successful `build` or `daily` run, at each push to main touching it, and on demand.
