# PlayInsights

Open data about Nintendo Switch games, by title id, rebuilt every week from
sources that need no account: which games are well known, which are read
about more lately, what critics gave them, which come out soon, what each
game is (its series, developers, publishers, genres, modes), how it does on
Steam, and which games are most like it. With IGDB's keys (see below), it
also takes each game's themes, keywords, perspectives, popularity and hype
from IGDB.
[PlayShelf](https://github.com/JigSawFr/PlayShelf) reads it for its Home
tab's **Popular**, **Trending** and **Coming soon** rows; anything else may
too.

## The files

They live on the [`data`](../../tree/data) branch, made again every Monday by
[`build.yml`](.github/workflows/build.yml) (and on demand), and are served by
jsDelivr:

| File | Address |
|---|---|
| `popular.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/PlayInsights@data/popular.json` |
| `upcoming.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/PlayInsights@data/upcoming.json` |
| `games.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/PlayInsights@data/games.json` |
| `similar.json` | `https://cdn.jsdelivr.net/gh/JigSawFr/PlayInsights@data/similar.json` |

`index.json` lists every file with the day it was made, its size and a hash of its content: a reader can ask for it every day and fetch only the files whose hash changed.

The `data` branch is one commit with no history, replaced at each run (`tools/publish.sh`): each run only needs the last files, and keeping every day's prices would grow the repository by hundreds of MB a year.

Each has a `schema` (1 for now: a new field may come, an old one keeps its
meaning), the day it was `generated` and its `source`. A game is a base
game's title id (16 hex digits, upper case, ending in `000`).

`popular.json`:

```json
{"schema": 1, "generated": "2026-10-28", "month": "2026-09", "views": true, "source": "...",
 "games": {"0100B0C013912000": [93, 12, 89], "010025400AECE000": [80, 0, 0]}}
```

Each game is `[score, trend, critics]`:

- **score**, 1 to 100: how well known it is. It weighs how many Wikipedias have a page on the game (Wikidata's sitelinks), how many critics reviewed it (Wikidata's review scores and their number of reviews, OpenCritic's mostly) and, when `views` is true, how often its English Wikipedia page was read last month. Each is on a log scale against the most of all. A game also sold on Steam can be lifted by its Steam reviews (a quarter of the score at most), never lowered; with IGDB, a game can be lifted the same way by its popularity there (its rank among the games for its visits on IGDB and the players who want to play it, play it or have played it).
- **trend**, -100 to 999: how much more (or less) the game was read on Wikipedia in the last seven days than in a week of the four before, in percent, its pages in English, French, German, Spanish, Italian, Japanese, Dutch and Portuguese added up. It is measured every day for the 400 best known games ([`daily.yml`](.github/workflows/daily.yml), `tools/trends.py`), and `trends` gives the day; it is 0 when the game was read fewer than 300 times in the week. Between two measures, and for the others, it is the weekly build's: last month's English views against the two months before.
- **critics**, 0 to 100: the critics' score that counts the most reviews (0 when none is known).

Wikimedia's pageviews are asked for the 400 best known games, one at a time. When too many are turned away (fewer than half read), `views` is false: every game is scored by its sitelinks and reviews alone, and none has a trend.

`upcoming.json`:

```json
{"schema": 1, "generated": "2026-10-28", "source": "blawar/titledb (US.en.json)",
 "games": {"0100000000010000": [20261204, "A game"]}}
```

The games whose release date, as the US eShop gives it, is in the next year: `[YYYYMMDD, name]`, or `[YYYYMMDD, name, hypes]` when IGDB says how many people follow the game.

`games.json`:

```json
{"schema": 1, "generated": "2026-10-29", "source": "...",
 "games": {"0100000000010000": {"series": [["Q123", "A series"]], "developers": [["Q456", "A studio"]],
   "publishers": [...], "genres": [...], "modes": [...],
   "steam": {"app": 504230, "positive": 117545, "negative": 3057, "owners": 2000000, "ccu": 1174}}}}
```

Each trait is `[Wikidata id, English label]` (the label is empty when Wikidata has none), 12 at most of a kind. With IGDB, a game may also have `themes`, `keywords` and `perspectives`, each trait `[IGDB id, name]`. `steam` is there for a game also sold on Steam: its reviews, the lower bound of its owners and its players at once when SteamSpy last saw it. SteamSpy allows a request a second, so each run asks it for as many games as 45 minutes allow, the ones not known yet first, and keeps the last run's figures for the others.

`similar.json`:

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

`prices/<country>.json`, made every day ([`daily.yml`](.github/workflows/daily.yml)) for US, CA, MX, BR, GB, FR, DE, ES, IT, NL, PT, AU and JP:

```json
{"schema": 1, "generated": "2026-10-30", "country": "FR", "currency": "EUR", "since": "2026-10-29", "source": "...",
 "games": {"0100000000010000": [19.99, 13.99, 20261101, 13.99, 20261030], "0100000000020000": [39.99, 0, 0, 29.99, 20261029]}}
```

Each game the country's eShop sells is `[regular, sale, until, lowest, lowest_day]`: its price, its sale price (0 when not on sale), the sale's last day (YYYYMMDD, 0 when none), the lowest price it has had since `since` (the day the files began) and the last day it had it, in the country's currency. Each day's price is weighed against the last run's file. The eShop's price service answers by its own ids, which differ from one region to the next: titledb's list of each region (US, GB, JP) gives them with the title ids. A game no longer sold is left out.

## The sources

| Source | What it gives | Licence |
|---|---|---|
| [Wikidata](https://www.wikidata.org/) | Switch title ids ([P11072](https://www.wikidata.org/wiki/Property:P11072)), sitelinks, English pages, review scores ([P444](https://www.wikidata.org/wiki/Property:P444)) and their number of reviews ([P7887](https://www.wikidata.org/wiki/Property:P7887)) | CC0 |
| [Wikimedia pageviews](https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews) | Monthly views of each English Wikipedia page | CC0 |
| [blawar/titledb](https://github.com/blawar/titledb) | The US eShop's release dates and names, and each game's description, categories and publisher (for `similar.json`) | as published there |
| [SteamSpy](https://steamspy.com/api.php) | Steam reviews, owners and players, for the games also on Steam (Wikidata's Steam id, [P1733](https://www.wikidata.org/wiki/Property:P1733)) | as published there |
| [Nintendo eShop's prices](https://api.ec.nintendo.com/v1/price) | Each game's price and sale, by country (`prices/`) | as published there |
| [IGDB](https://www.igdb.com/) (only with its keys) | Themes, keywords, player perspectives, popularity and hype of the games Wikidata links to it ([P5794](https://www.wikidata.org/wiki/Property:P5794)) | [IGDB's API terms](https://api-docs.igdb.com/#about); data from IGDB.com |

## When a source fails

A file that comes out with fewer than 70 % of the games the last run's had (a
source down or answering half, rather than the world changing) is not
published: the last run's file stays on the `data` branch, the run says so
with a warning, and the workflow's summary lists each file's games against
the last run's.

Whatever goes wrong in a run — the job failing, one of the daily steps
failing on its own, a file kept by the guard — opens an issue labelled
`data-alert` (`tools/alert.sh`), or adds a comment to the one still open,
so it does not go unseen.

GitHub turns off a public repository's schedules after 60 days without activity: the daily run enables both workflows again each day, which starts those 60 days over.

## IGDB's keys

IGDB is asked only when `IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET` are set: a
[Twitch application](https://dev.twitch.tv/console/apps)'s client id and
secret, kept in the repository's Actions secrets (the workflow passes them to
the build). Without them, or when IGDB fails, the files are made from the
other sources alone. IGDB answers 4 requests a second, which the build keeps
to.

## Running it

```sh
python3 tools/build.py out/ [last/]  # writes out/*.json; last/: the last run's files, for Steam
python3 tools/prices.py out/ [last/] # writes out/prices/*.json, every country's (some 20 minutes)
python3 tools/trends.py out/ last/   # last/popular.json with today's trends, as out/popular.json
python3 -m unittest discover -s tests
```

Python 3.10 or later, no package to install. It takes up to an hour: SteamSpy's
45 minutes, the pageviews, and titledb's list (about 90 MB).
