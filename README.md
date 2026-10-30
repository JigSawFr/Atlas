# Atlas

Open data about video games on every platform it can read without an
account, rebuilt every week, with prices every day: which games are well
known, which are read about more lately, what critics and players gave them,
which come out soon, what each game is (its series, developers, publishers,
genres), which games are most like it, and what it costs in 13 countries.
Each platform has a folder: the Nintendo Switch (`platforms/switch/`, by title id),
Steam (`platforms/steam/`), GOG (`platforms/gog/`) and the Xbox and Microsoft Store (`platforms/xbox/`);
`links.json` ties a game's ids on every platform together. With IGDB's keys
(see "Keys"), the Switch's files also take IGDB's themes, keywords,
perspectives, popularity and hype.
[PlayShelf](https://github.com/JigSawFr/PlayShelf) reads the Switch's for its
Home tab; anything else may too.

Atlas was called PlayInsights until 2026-10-30; the data's formats and paths
didn't change with the name.

## The files

They live on the [`data`](../../tree/data) branch, made again every Monday by
[`build.yml`](.github/workflows/build.yml) (and on demand), and are served by
jsDelivr. Each platform has a folder of its own in `platforms/`, by its id
(`platforms.json` lists them); the Switch's is `platforms/switch/`:

| File | Address |
|---|---|
| `platforms/switch/popular.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/switch/popular.json` |
| `platforms/switch/upcoming.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/switch/upcoming.json` |
| `platforms/switch/games.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/switch/games.json` |
| `platforms/switch/similar.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/switch/similar.json` |
| `platforms/switch/names.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/switch/names.json` |
| `platforms/switch/editions.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/switch/editions.json` |
| `platforms/switch/prices/<country>.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/switch/prices/FR.json` |
| `platforms/steam/popular.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/steam/popular.json` |
| `platforms/steam/games.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/steam/games.json` |
| `platforms/steam/upcoming.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/steam/upcoming.json` |
| `platforms/steam/similar.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/steam/similar.json` |
| `platforms/steam/prices/<country>.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/steam/prices/FR.json` |
| `platforms/gog/popular.json`, `platforms/gog/games.json`, `platforms/gog/upcoming.json`, `platforms/gog/similar.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/gog/popular.json`… |
| `platforms/gog/prices/<country>.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/gog/prices/FR.json` |
| `platforms/xbox/popular.json`, `platforms/xbox/games.json`, `platforms/xbox/gamepass.json`, `platforms/xbox/upcoming.json`, `platforms/xbox/similar.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/xbox/popular.json`… |
| `platforms/xbox/prices/<country>.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/xbox/prices/FR.json` |
| `platforms/3ds/games.json`, `popular.json`, `similar.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/3ds/games.json`… |
| `platforms/<machine>/popular.json`, `games.json`, `similar.json` (the old machines: `nes`, `snes`, `gba`, `ps2`…) | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms/nes/popular.json`… |
| `platforms.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/platforms.json` |
| `links.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/links.json` |
| `index.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/Atlas@data/index.json` |

The files have moved twice: until 2026-10-30 the Switch's were at the
branch's root (`popular.json`, `prices/FR.json`…), then each platform's
folder was (`switch/`, `steam/`, `gog/`, `xbox/`, and `retro/` for every old
machine together). The first run after each move put them in their new
place (`tools/migrate.py`), keeping them as the last run's for the guard,
the trends and the lowest prices; `retro/` made way for a folder a machine.

`platforms.json` is the platforms' registry, `{"platforms": {id: {name,
qid, igdb, aurore, kind}}}`: its Wikidata item, its IGDB platform (slug),
[Aurore](https://github.com/JigSawFr/Aurore)'s id when Aurore runs there
(`switch`, `3ds`, `psv`…: the same ids), and its kind: `store`, `console`
(no store sells its games any more, but it has a source of its own: the 3DS)
or `retro` (Wikidata alone). It has a
`schema` like every file: a reader skips an entry's fields, and a kind, it
does not know.

`index.json` lists every file with the day it was made, its size and a hash of its content: a reader can ask for it every day and fetch only the files whose hash changed.
Each entry also says the file's `source`, its `license` (the terms of the
sources it was made from: CC0-1.0 for Wikidata's and Wikimedia's, the
store's own terms for a store's) and its `attribution` (whom to credit).

`schemas/` has a [JSON Schema](https://json-schema.org/) (2020-12) for every
file, at the same path (`schemas/platforms/switch/popular.schema.json` for
`platforms/switch/popular.json`). Every file is checked against its own
before it is published: one that does not match is not published (the last
run's stays) and the run says so; the tests also check the data branch's
files against this branch's schemas.

`report.json` says how the data is: for each source its files, records,
size and the last day it answered; for each platform its games, how many
have a name, a score, a link to another platform (`linked`), a price
(`priced`, in any country) and reviews or a rating (`reviewed`), as shares
of 1; and how long each step of the run took. A file of another schema
counts as none there.

The `data` branch is one commit with no history, replaced at each run (`tools/publish.sh`): each run only needs the last files, and keeping every day's prices would grow the repository by hundreds of MB a year.

Each has a `schema` (1 for now: a new field may come, an old one keeps its
meaning), the day it was `generated` and its `source`; a platform's files
also have their `platform` (its id in `platforms.json`: `switch`, `steam`, `gog`, `xbox`, `nes`…). In `platforms/switch/`, a game is a base game's
title id (16 hex digits, upper case, ending in `000`).

The schema moves up only when a field changes meaning (its unit, its type,
or it goes). A reader skips the fields it does not know, and takes a file
of another schema as no file. Schema 2 of a file will be published at a
path of its own, `platforms/switch/v2/popular.json` next to
`platforms/switch/popular.json`,
both made at each run until the readers of schema 1 (PlayShelf's
installed versions) are gone; only then does the old path stop. The tools
read the last run's files back the same way: one of another schema counts
as none (the guard lets the new file through, the lowest prices start over,
the daily trends wait for the weekly build).

`links.json`, made every Monday:

```json
{"schema": 1, "generated": "2026-11-02", "source": "Wikidata (P11072, P1733, …)",
 "games": {"Q900001": {"switch": ["0100A1B2C3D4E000"], "steam": ["900010"], "ps": ["10900001"],
                       "ps_product": ["EP0001-PPSA00001_00-AMBERLANTERN0000"], "xbox": ["9ZZZZZZZZZZ1"],
                       "gog": ["amber_lantern"], "epic": ["amber-lantern"]}}}
```

Every Wikidata item with an id on one of the stores, by its Wikidata id (some
131,000; a few are software rather than games), with its ids on each: a
Switch base game's title id (`switch`), a Steam app id (`steam`), a
PlayStation Store concept (`ps`) and its products in North America, Europe
and Japan (`ps_product`), a Microsoft Store product id, Xbox and PC (`xbox`),
a GOG page's slug (`gog`), an Epic Games Store page's slug (`epic`). A
platform the game has no id on is left out; a game may have several of one
(editions, regions). It takes one Wikidata query; when Wikidata's service
turns the run away, [QLever](https://qlever.dev)'s copy of Wikidata is asked.

`platforms/switch/popular.json`:

```json
{"schema": 1, "generated": "2026-10-28", "month": "2026-09", "views": true, "source": "...",
 "games": {"0100B0C013912000": [93, 12, 89], "010025400AECE000": [80, 0, 0]}}
```

Each game is `[score, trend, critics]`:

- **score**, 1 to 100: how well known it is. It weighs how many Wikipedias have a page on the game (Wikidata's sitelinks), how many critics reviewed it (Wikidata's review scores and their number of reviews, OpenCritic's mostly) and, when `views` is true, how often its English Wikipedia page was read last month. Each is on a log scale against the most of all. A game also sold on Steam can be lifted by its Steam reviews (a quarter of the score at most), never lowered; with IGDB, a game can be lifted the same way by its popularity there (its rank among the games for its visits on IGDB and the players who want to play it, play it or have played it).
- **trend**, -100 to 999: how much more (or less) the game was read on Wikipedia in the last seven days than in a week of the four before, in percent, its pages in English, French, German, Spanish, Italian, Japanese, Dutch and Portuguese added up. It is measured every day for the 400 best known games ([`daily.yml`](.github/workflows/daily.yml), `tools/trends.py`), and `trends` gives the day; it is 0 when the game was read fewer than 300 times in the week. Between two measures, and for the others, it is the weekly build's: last month's English views against the two months before.
- **critics**, 0 to 100: the critics' score that counts the most reviews (0 when none is known).

Wikimedia's pageviews are asked for the 400 best known games, one at a time. When too many are turned away (fewer than half read), `views` is false: every game is scored by its sitelinks and reviews alone, and none has a trend.

`platforms/switch/upcoming.json`:

```json
{"schema": 1, "generated": "2026-10-28", "source": "blawar/titledb (US.en.json)",
 "games": {"0100000000010000": [20261204, "A game"]}}
```

The games whose release date, as the US eShop gives it, is in the next year: `[YYYYMMDD, name]`, or `[YYYYMMDD, name, hypes]` when IGDB says how many people follow the game.

`platforms/switch/games.json`:

```json
{"schema": 1, "generated": "2026-10-29", "source": "...",
 "games": {"0100000000010000": {"name": "Lantern Tale", "series": [["Q123", "A series"]], "developers": [["Q456", "A studio"]],
   "publishers": [...], "genres": [...], "modes": [...],
   "steam": {"app": 504230, "positive": 117545, "negative": 3057, "owners": 2000000, "ccu": 1174}}}}
```

A game has its `name` (titledb's US list's, else the British or the Japanese one's); `platforms/switch/names.json` gives every base game titledb knows its name, `{title id: name}`. Each trait is `[Wikidata id, English label]` (the label is empty when Wikidata has none), 12 at most of a kind. With IGDB, a game may also have `themes`, `keywords` and `perspectives`, each trait `[IGDB id, name]`, and `igdb_rating`: `[players' rating 0..100, how many rated]` (IGDB's users, not the critics). `steam` is there for a game also sold on Steam: its reviews (`positive`, `negative`), from Steam's store at every run (its count and share of positive reviews), and the lower bound of its `owners` and its players at once (`ccu`) when SteamSpy last saw it (0 when it never did). SteamSpy allows a request a second, so each run asks it for as many games as 10 minutes allow, the ones not known yet first, and keeps the last run's figures for the others.

`platforms/switch/similar.json`:

```json
{"schema": 1, "generated": "2026-10-29", "source": "games.json's traits",
 "games": {"0100000000010000": [["0100000000020000", 86], ["0100000000030000", 41]]}}
```

Each game's 12 most similar, `[title id, 1..100]`, the most first. Two games are alike by the traits they share, each weighed by its kind (a series 4, a developer 2, a genre, an IGDB theme or keyword 1, a publisher, a mode or a perspective 0.5) and by how rare it is: a cosine over weighted sets. Two games sharing only a publisher, a mode or a perspective are not alike.

Wikidata describes a few thousand Switch games; the eShop has many more. For
those, games are also found alike by what the eShop says of them (titledb's
names, intros, descriptions, categories and publishers): each game's
weightiest words by tf-idf, compared as a cosine (`tools/text.py`). A
likeness by words counts four fifths of one by traits, 10 at most a game and
25 at least; a game's list keeps the best 12 of both. That brings
`similar.json` from some 2,400 games to some 14,000.

`platforms/switch/editions.json`:

```json
{"schema": 1, "generated": "2026-10-30", "source": "blawar/titledb (US.en.json)",
 "games": {"0100000000020000": "0100000000010000"}}
```

A game's other editions (a Deluxe, a Complete Edition, a Game of the Year, the game with a DLC pack), each with the game it is one of: the edition out first, under the same publisher and a name that differs only by its edition words (`tools/editions.py`). Words that make another game (Remastered, Special, Enhanced, a second title after "+") keep the games apart. `similar.json` leaves a game's own editions out of its list.

`platforms/switch/prices/<country>.json`, made every day ([`daily.yml`](.github/workflows/daily.yml)) for US, CA, MX, BR, GB, FR, DE, ES, IT, NL, PT, AU and JP:

```json
{"schema": 1, "generated": "2026-10-30", "country": "FR", "currency": "EUR", "since": "2026-10-29", "source": "...",
 "games": {"0100000000010000": [19.99, 13.99, 20261101, 13.99, 20261030], "0100000000020000": [39.99, 0, 0, 29.99, 20261029]}}
```

Each game the country's eShop sells is `[regular, sale, until, lowest, lowest_day]`: its price, its sale price (0 when not on sale), the sale's last day (YYYYMMDD, 0 when none), the lowest price it has had since `since` (the day the files began) and the last day it had it, in the country's currency. Each day's price is weighed against the last run's file. The eShop's price service answers by its own ids, which differ from one region to the next: titledb's list of each region (US, GB, JP) gives them with the title ids. A game no longer sold is left out.

### Steam

`platforms/steam/` has the Switch's files' formats, by Steam app id (`"620"`), made every
Monday by `tools/steam.py` in a job of its own:

- `platforms/steam/popular.json`: `[score, trend, critics]` as `platforms/switch/popular.json`.
  The score weighs half the game's renown on Wikipedia (as the Switch's:
  sitelinks, critics, the English page's views for the 400 best known) and
  half its Steam reviews, on a log scale against the most; Steam's 100 most
  played of last week are lifted by their rank.
- `platforms/steam/games.json`: the 40,000 best known games and the upcoming ones
  (all 120,000 would make some 50 MB): each one's `name`, `release`
  (YYYYMMDD), `reviews` (`[count, percent positive]`), `qid` (its Wikidata
  item), and its traits: `series` (its franchise), `developers` and
  `publishers` as `[id, name]`, and `tags`, its players' first 10 tags, by
  Steam's tag id, whose names are in the file's `tags`.

  ```json
  {"schema": 1, "platform": "steam", "generated": "2026-11-02", "source": "...",
   "tags": {"19": "Action", "492": "Indie"},
   "games": {"900010": {"name": "Amber Lantern", "qid": "Q900001", "release": 20231114, "reviews": [1200, 91],
                        "series": [["franchise:lantern", "Lantern"]], "developers": [["clan:77", "Lantern Works"]],
                        "publishers": [["name:tiny owl", "Tiny Owl"]], "tags": [19, 492]}}}
  ```
- `platforms/steam/upcoming.json`: `[YYYYMMDD, name]` of the games out in the next year.
- `platforms/steam/similar.json`: the 12 most similar, `[app id, 1..100]`, of the 30,000
  best known games, by their traits as the Switch's (a tag weighs as a genre).

- `platforms/steam/prices/<country>.json`, made every day (`tools/steam_prices.py`)
  for the same 13 countries as the Switch's, for the games of
  `platforms/steam/games.json`: each row is `[regular, sale, until, lowest,
  lowest_day, lowest_30]`, the first five as `platforms/switch/prices/`, and
  `lowest_30` Steam's own lowest price of the last 30 days (as its store
  shows it in Europe; 0 when it gives none). A free game, or one a country's
  store does not sell (Germany's sells some 4,000 fewer), is left out.
  Each country is asked in a job of its own (`steam-store:FR`, 45 minutes
  at most): a country whose job fails or runs out of time keeps its last
  file, and the others are published.

The games are those Wikidata gives a Steam app id (some 128,000 items) and
Steam's most played; Steam's store says which are games (not a DLC, a tool or
a soundtrack) and gives the rest, 200 apps a request.

### GOG

`platforms/gog/` has the same formats, by GOG product id (`"1207658924"`), from GOG's
catalog (`tools/gog.py`), every game and pack it sells (some 8,400):

- every Monday: `platforms/gog/popular.json` (half the game's renown on Wikipedia, by
  the Wikidata item that gives its GOG page, P2725; half its GOG reviews;
  GOG's 100 first in its "trending" order lifted by their rank),
  `platforms/gog/games.json` (each game's `name`, `slug`, `release`, `reviews` as
  `[count, percent]`, its rating out of 5 doubled into a percent, `qid`,
  `pack` for a bundle, and its traits as `[id, name]`: `developers`,
  `publishers`, `genres`, `tags`), `platforms/gog/upcoming.json` and
  `platforms/gog/similar.json`;
- every day: `platforms/gog/prices/<country>.json`, `[regular, sale, until, lowest,
  lowest_day]` as `platforms/switch/prices/`, for the 13 countries (Japan in US
  dollars, as GOG sells there). GOG doesn't say when a sale ends: `until` is
  0. A free game is left out.

### Xbox and the Microsoft Store

`platforms/xbox/` has the same formats, by Microsoft Store product id (`"9N7TB1SB2M0K"`,
Xbox and PC alike), for the games Wikidata gives a Microsoft Store id (P5885)
and the Game Pass's (some 6,700), from the store's catalog
(`displaycatalog.mp.microsoft.com`, no key, `tools/xbox.py`):

- every Monday: `platforms/xbox/popular.json` (half the game's renown on Wikipedia,
  half its players' ratings on the store; a game in the Game Pass lifted),
  `platforms/xbox/games.json` (each game's `name`, `release`, `rating` as `[count,
  percent]`, its stars out of 5 into a percent, `gamepass`, `qid`, and its
  traits as `[id, name]`: `developers`, `publishers`, `genres`),
  `platforms/xbox/gamepass.json` (the games in the Game Pass: `["console", "pc"]`, from
  its public lists), `platforms/xbox/upcoming.json`, `platforms/xbox/similar.json`;
- every day: `platforms/xbox/prices/<country>.json`, `[regular, sale, until, lowest,
  lowest_day]` as `platforms/switch/prices/`, for the 13 countries. The store's short
  answer doesn't say when a sale ends: `until` is 0. A free game is left out.

### Nintendo 3DS

`platforms/3ds/`, every Monday (`tools/n3ds.py`), a game a family: one game
across its regions, by its product code's serial (`"CTR-AKD"` for the
`CTR-N-AKDJ`, `CTR-N-AKDE`… of its cards and downloads; `KTR-` for the New
3DS's own).

- `games.json`: each family's `name` (its American or European one first),
  `regions`, `tids` (its base games' title ids by region), its `updates`',
  `dlc`'s and `demos`' title ids, `publisher`, `release` (its first day on
  the eShop), and for the ones Wikidata knows, `qid` and traits
  (`series`, `developers`, `publishers`, `genres`).
- `popular.json`: `[score, trend, critics]` as `platforms/switch/popular.json`,
  from Wikidata and Wikipedia for the games Wikidata knows; `critics` is 0.
- `similar.json`: the 12 most alike, by their traits.

No prices: the 3DS's eShop closed in March 2023. No pictures nor texts.
The titles come from [Nlib API](https://api.nlib.cc/ctr/)'s 3DS (its lists
of title ids by category, then each base game's name, region, publisher,
product code and first day, asked once and kept in
`sources/nlib-ctr/titles.json`: a run asks only the titles it does not know
yet, two at a time, and the first some 4,400, about 25 minutes). Wikidata
has no 3DS title id: one of its 3DS games (P400 = Q203597) is matched to a
family by its English name, only when exactly one of each has that name;
`links.json` gives the family as `3ds`. Measured live on 2026-10-30: 4,364 base titles in
2,198 families; of Wikidata's 814 3DS games, 478 matched (59 %; 22 % of the
families), the others left without `qid` rather than matched wrong.

### Retro

The consoles, handhelds and computers no store Atlas reads sells any more
have a folder each, `platforms/<machine>/` (`nes`, `snes`, `n64`, `gba`,
`ps2`, `psv`, `xbox360`, `genesis`, `arcade`, `c64`, `dos`…: 39, see
`platforms.json`; the 3DS has its own, above), their games by Wikidata item (`"Q900001"`), every Monday,
from Wikidata alone (`tools/retro.py`): some 25,000 games. A game on
several machines is in each one's folder; a game also sold today (on Steam,
say) is here too, by its Wikidata item: `links.json` gives its store ids.

- `popular.json`: `[score, trend, critics]` as `platforms/switch/popular.json`,
  from the game's renown on Wikipedia alone (its sitelinks, and its English
  page's views for the 400 best known of all), weighed among the machine's
  games; `critics` is 0.
- `games.json`: each game's `name`, `platforms` (`[[QID, name]]`) and
  traits as `[QID, name]`: `series`, `developers`, `publishers`, `genres`.
- `similar.json`: the 12 most alike among the machine's games, by their traits.

## What changed, and the prices' history

Every run, once its files are made (`tools/changes.py`):

- `changes.json`: by platform, the games new since the last run (`new`),
  the ones out today (`out_today`), the trends that moved by 100 points or
  more (`trends`: `[id, before, now]`), and by country the sales that
  started and ended and the new lowest prices (`sales`), 200 of each at
  most:

  ```json
  {"schema": 1, "generated": "2026-11-02", "source": "Atlas (the run's files against the last run's)",
   "platforms": {"switch": {"new": ["0100000000030000"], "trends": [["0100000000010000", 10, 210]],
                            "sales": {"FR": {"started": ["0100000000010000"], "ended": [], "lowest": []}}}}}
  ```

- `history/<platform>/YYYY-MM.json`: each game's price by country, on the
  days it changed only, `[YYYYMMDD, regular, sale]` (sale 0: none), a file
  a month, kept from day to day. It stays on the data branch (and in the
  weekly archives); the website does not copy it.
- `platforms/<id>/games.lite.json`, beside a `games.json` over 1 MB: each
  game's `name`, `qid`, `release` and `reviews` or `rating` alone, for a
  reader that needs no more.

The last run's files of another schema count as none (nothing is said new
against them), and a month's history of another schema is left as it is.

## The archives

The `data` branch keeps only the last files. Every Monday's build also keeps
them as a [release](../../releases), `data-YYYY-MM-DD`, tagged on the commit
that made them: each file the branch had that day, attached on its own
(`platforms/switch/prices/FR.json` as `switch-prices-FR.json`, a release's files having
no folders),
all of them in one zip with their folders (`atlas-data-YYYY-MM-DD.zip`,
about 3 MB), and their `SHA256SUMS.txt`. Some 17 MB a week, kept for good, as the data's
history: the prices of a Monday, the trends of a week.

The last week's files have addresses of their own, which follow each new
release:

```
https://github.com/JigSawFr/Atlas/releases/latest/download/switch-popular.json
https://github.com/JigSawFr/Atlas/releases/download/data-2026-11-02/switch-prices-FR.json
https://github.com/JigSawFr/Atlas/releases/download/data-2026-11-02/atlas-data-2026-11-02.zip
```

Each file, and the zip, is attested:

```sh
gh attestation verify switch-popular.json -R JigSawFr/Atlas
```

## Website

Atlas's website, [atlas.boreale.dev](https://atlas.boreale.dev/?utm_source=github&utm_medium=readme), shows the project and an explorer of the data (the best known games, the trends, the deals by country, the games coming soon, each game's sheet), in fifteen languages. It is built from `site/` with a copy of the `data` branch, served with it under `data/` (`.github/workflows/site.yml`, after each run); see [`site/README.md`](site/README.md).

## The sources

Each source is asked once a run, and what it answered is published as it
came, only the fields Atlas uses, under `sources/<source>/` on the `data`
branch: the platforms' files are then made from these, asking nothing more
(`tools/collect.py`). A file larger than 15 MB is cut in parts
(`sources/titledb/US/1.json`…), each with the same fields, its `part` and
`parts`; read together they are the one file.

| Folder | What it keeps | When |
|---|---|---|
| `sources/wikidata/` | Each query's rows, `{variable: value}`: `switch`, `switch-<series, developers, publishers, genres, modes>`, `switch-steam`, `switch-igdb`, `steam`, `gog`, `xbox`, `links`, `retro`, `retro-<kind>`; `switch-pages` (daily) | Monday, every day |
| `sources/titledb/` | `US.json`, `GB.json`, `JP.json`: titledb's lists by its key (the US one with names, descriptions, categories, publishers; the others with ids and names) | every day |
| `sources/eshop/prices/` | The eShop's answer by eShop id: status, regular price, discount, its last day, currency | every day |
| `sources/steam-store/` | `apps.json` (GetItems by app id), `tags.json`, `most-played.json`; `prices/<country>.json` (GetItems' prices) | Monday, every day |
| `sources/steamspy/` | `apps.json`: owners and players by app id, as many as 10 minutes allow | Monday |
| `sources/gog/catalog/` | The catalog's products by product id, in its trending order, a country a file | Monday (US), every day |
| `sources/msstore/` | `products.json`, `gamepass.json`; `prices/<country>.json` ([list price, MSRP] by product id) | Monday, every day |
| `sources/nlib-ctr/` | `categories.json` (the 3DS's title ids by category), `titles.json` (each base game's name, region, publisher, product code, first day; kept from run to run) | Monday |
| `sources/igdb/` | `games.json`, `popularity.json`: IGDB's records (with its keys only) | Monday |
| `sources/wikipedia/` | `monthly.json` (the best known games' English pages' views a month), `daily.json` (their pages' views a day, 8 languages) | Monday, every day |

Each file says its source, its licence or terms, the day it was
collected (`generated`) and its `schema` (1), which moves up like a
platform file's: a new field keeps it, a field changing meaning moves it.
A tool reads a source file of another schema as no file (the guard lets
the new one through, the platform's file is made from the last run's or
left as it was), and skips the fields it does not know.

| Source | What it gives | Licence |
|---|---|---|
| [Wikidata](https://www.wikidata.org/) | The stores' ids for `links.json` ([P1733](https://www.wikidata.org/wiki/Property:P1733) Steam, [P12332](https://www.wikidata.org/wiki/Property:P12332), [P5944](https://www.wikidata.org/wiki/Property:P5944), [P5971](https://www.wikidata.org/wiki/Property:P5971), [P5999](https://www.wikidata.org/wiki/Property:P5999) PlayStation, [P5885](https://www.wikidata.org/wiki/Property:P5885) Microsoft, [P2725](https://www.wikidata.org/wiki/Property:P2725) GOG, [P6278](https://www.wikidata.org/wiki/Property:P6278) Epic); Switch title ids ([P11072](https://www.wikidata.org/wiki/Property:P11072)), sitelinks, English pages, review scores ([P444](https://www.wikidata.org/wiki/Property:P444)) and their number of reviews ([P7887](https://www.wikidata.org/wiki/Property:P7887)) | CC0 |
| [Wikimedia pageviews](https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews) | Monthly views of each English Wikipedia page | CC0 |
| [blawar/titledb](https://github.com/blawar/titledb) | The US eShop's release dates and names, and each game's description, categories and publisher (for `similar.json`) | as published there |
| [SteamSpy](https://steamspy.com/api.php) | Steam owners and players, for the games also on Steam (Wikidata's Steam id, [P1733](https://www.wikidata.org/wiki/Property:P1733)) | as published there |
| [Steam's store](https://store.steampowered.com/) (`IStoreBrowseService/GetItems`, `IStoreService/GetTagList`, `ISteamChartsService/GetMostPlayedGames`, no key) | Steam's games: names, reviews, releases, franchises, developers, publishers, tags, most played; their prices and sales by country (`platforms/steam/prices/`) | [Steam Web API terms](https://steamcommunity.com/dev/apiterms); data from Valve, not endorsed by it |
| [GOG's catalog](https://www.gog.com/) (`catalog.gog.com`, no key) | GOG's games: names, releases, reviews, developers, publishers, genres, tags, trending order; prices and sales by country (`platforms/gog/prices/`) | as published there; data from GOG |
| [Microsoft Store's catalog](https://www.xbox.com/) (`displaycatalog.mp.microsoft.com`, `catalog.gamepass.com`, no key) | The Xbox and PC games: names, releases, players' ratings, developers, publishers, genres, the Game Pass; prices and sales by country (`platforms/xbox/prices/`) | as published there; data from Microsoft |
| [Nintendo eShop's prices](https://api.ec.nintendo.com/v1/price) | Each game's price and sale, by country (`platforms/switch/prices/`) | as published there |
| [Nlib API](https://api.nlib.cc/ctr/) (3DS, no key; asked as `Atlas/1.0 (+https://atlas.boreale.dev)`, two requests at a time) | The 3DS's titles: names, regions, publishers, product codes, first days on the eShop; their updates', add-ons' and demos' title ids | as published there (no terms stated) |
| [IGDB](https://www.igdb.com/) (only with its keys) | Themes, keywords, player perspectives, popularity and hype of the games Wikidata links to it ([P5794](https://www.wikidata.org/wiki/Property:P5794)) | [IGDB's API terms](https://api-docs.igdb.com/#about); data from IGDB.com |

## When a source fails

A file that comes out with fewer than 70 % of the games (or, for a source's
file, of the records) the last run's had (a source down or answering half,
rather than the world changing) is not published: the last run's file stays on the `data` branch, the run says so
with a warning, and the workflow's summary lists each file's games against
the last run's.

A source that fails leaves its last run's file, and the platforms' files are
made from that; a daily file (prices, trends) is made only from what was
collected that day, else left as it was.

Whatever goes wrong in a run — the job failing, one of the daily steps
failing on its own, a file kept by the guard — opens an issue labelled
`data-alert` (`tools/alert.sh`), or adds a comment to the one still open,
so it does not go unseen.

GitHub turns off a public repository's schedules after 60 days without activity: the daily run enables both workflows again each day, which starts those 60 days over.

## Keys

Every source works without a key, but IGDB, which needs one:

| Platform | Source | Key | Where | Secret |
|---|---|---|---|---|
| Switch | IGDB | optional (more traits, popularity, hype, players' rating) | [Twitch's developer console](https://dev.twitch.tv/console/apps) | `IGDB_CLIENT_ID`, `IGDB_CLIENT_SECRET` |
| GOG | GOG's catalog | none | — | — |
| Xbox / Microsoft Store | the store's catalog, the Game Pass's lists | none | — | — |
| Retro | Wikidata | none | — | — |
| Steam | Steam's store | none (a key, `STEAM_API_KEY`, would only add Steam's full list of apps; not read yet) | [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) | `STEAM_API_KEY` |

Each key is read only when its secret is set; without it, the files are made
from the other sources.

### IGDB

IGDB is asked only when `IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET` are set: a
[Twitch application](https://dev.twitch.tv/console/apps)'s client id and
secret, kept in the repository's Actions secrets (the workflow passes them to
the build). Without them, or when IGDB fails, the files are made from the
other sources alone. IGDB answers 4 requests a second, which the build keeps
to.

## Running it

```sh
python3 tools/migrate.py last/       # a data branch from before switch/: its Switch files moved there
# Each source, asked once: writes out/sources/<source>/ (fresh/: this run's sources one needs)
python3 tools/collect.py wikidata weekly out/ last/
python3 tools/collect.py titledb weekly out/ last/          # about 90 MB a region, some 10 s
python3 tools/collect.py steam-store weekly out/ last/ out/ # some 650 requests (some 8 minutes)
python3 tools/collect.py steamspy weekly out/ last/ out/    # 10 minutes
python3 tools/collect.py gog weekly out/ last/
python3 tools/collect.py msstore weekly out/ last/ out/
python3 tools/collect.py igdb weekly out/ last/ out/        # with IGDB_CLIENT_ID and IGDB_CLIENT_SECRET only
python3 tools/collect.py nlib-ctr weekly out/ last/         # the 3DS's titles not known yet (the first time some 25 minutes)
python3 tools/collect.py wikipedia weekly out/ last/ out/   # after the stores: their best known games' pages
python3 tools/collect.py wikidata daily out/ last/          # the pages of last/platforms/switch/popular.json's best known
python3 tools/collect.py wikipedia daily out/ last/ out/
python3 tools/collect.py eshop daily out/ last/ out/        # after titledb (some 20 minutes)
python3 tools/collect.py steam-store daily out/ last/       # last/platforms/steam/games.json's prices (some 4 minutes a country)
python3 tools/collect.py steam-store:FR,DE daily out/ last/ # only those countries (daily.yml: a country a job)
python3 tools/collect.py gog daily out/ last/               # every country's catalog (some 6 minutes)
python3 tools/collect.py msstore daily out/ last/           # last/platforms/xbox/games.json's prices (some 4 minutes)
# Each platform's files from the sources (out/ this run's, else last/'s), asking nothing:
python3 tools/links.py out/ last/ out/          # out/links.json, out/platforms.json
python3 tools/build.py out/ last/ out/          # out/platforms/switch/*.json
python3 tools/steam.py out/ last/ out/          # out/platforms/steam/*.json
python3 tools/gog.py catalog out/ last/ out/    # out/platforms/gog/*.json
python3 tools/xbox.py catalog out/ last/ out/   # out/platforms/xbox/*.json
python3 tools/retro.py out/ last/ out/          # out/platforms/<machine>/*.json
python3 tools/n3ds.py out/ last/ out/           # out/platforms/3ds/*.json
python3 tools/trends.py out/ last/ out/         # last/platforms/switch/popular.json with today's trends
python3 tools/prices.py out/ last/ out/         # out/platforms/switch/prices/*.json
python3 tools/steam_prices.py out/ last/ out/   # out/platforms/steam/prices/*.json
python3 tools/gog.py prices out/ last/ out/     # out/platforms/gog/prices/*.json
python3 tools/xbox.py prices out/ last/ out/    # out/platforms/xbox/prices/*.json
python3 -m unittest discover -s tests
```

`tools/common.py` holds what every tool shares: the requests, Wikidata's query
service, the guard and publishing a file (a platform's or a source's, cut in
parts when too large), reading the sources, the lowest price kept from run to
run.

Python 3.10 or later, no package to install.
