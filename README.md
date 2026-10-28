# PlayInsights

Open data about Nintendo Switch games, by title id, rebuilt every week from
sources that need no account: which games are well known, which are read
about more lately, what critics gave them, and which come out soon.
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

Each has a `schema` (1 for now: a new field may come, an old one keeps its
meaning), the day it was `generated` and its `source`. A game is a base
game's title id (16 hex digits, upper case, ending in `000`).

`popular.json`:

```json
{"schema": 1, "generated": "2026-10-28", "month": "2026-09", "views": true, "source": "...",
 "games": {"0100B0C013912000": [93, 12, 89], "010025400AECE000": [80, 0, 0]}}
```

Each game is `[score, trend, critics]`:

- **score**, 1 to 100: how well known it is. It weighs how many Wikipedias have a page on the game (Wikidata's sitelinks), how many critics reviewed it (Wikidata's review scores and their number of reviews, OpenCritic's mostly) and, when `views` is true, how often its English Wikipedia page was read last month. Each is on a log scale against the most of all.
- **trend**, -100 to 999: the change of its page's views last month against the two months before, in percent. It is 0 when the page was read fewer than 500 times or its views were not read.
- **critics**, 0 to 100: the critics' score that counts the most reviews (0 when none is known).

Wikimedia's pageviews are asked for the 400 best known games, one at a time. When too many are turned away (fewer than half read), `views` is false: every game is scored by its sitelinks and reviews alone, and none has a trend.

`upcoming.json`:

```json
{"schema": 1, "generated": "2026-10-28", "source": "blawar/titledb (US.en.json)",
 "games": {"0100000000010000": [20261204, "A game"]}}
```

The games whose release date, as the US eShop gives it, is in the next year: `[YYYYMMDD, name]`.

## The sources

| Source | What it gives | Licence |
|---|---|---|
| [Wikidata](https://www.wikidata.org/) | Switch title ids ([P11072](https://www.wikidata.org/wiki/Property:P11072)), sitelinks, English pages, review scores ([P444](https://www.wikidata.org/wiki/Property:P444)) and their number of reviews ([P7887](https://www.wikidata.org/wiki/Property:P7887)) | CC0 |
| [Wikimedia pageviews](https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews) | Monthly views of each English Wikipedia page | CC0 |
| [blawar/titledb](https://github.com/blawar/titledb) | The US eShop's release dates and names | as published there |

## Running it

```sh
python3 tools/build.py out/          # writes out/popular.json and out/upcoming.json
python3 -m unittest discover -s tests
```

Python 3.10 or later, no package to install. It takes a few minutes, most of
them on the pageviews and on titledb's list (about 90 MB).
