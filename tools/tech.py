"""A game's technical sheet, from what each store says of it (site/README.md): where it runs, how the
Steam Deck takes it, its languages, what it offers (controllers, achievements, cloud saves, cross-play…),
how many play it, its age ratings and the names of its pictures. Each store has its own words (Steam's
category numbers, GOG's slugs, Microsoft's capabilities); the sheet has one set.

    {"os": ["windows", "mac", "linux"],        # where it runs ("xbox" for the consoles' store)
     "deck": 3,                                # Steam Deck: 1 unsupported, 2 playable, 3 verified (0: not tested, not kept)
     "langs": ["en", "fr"], "voices": ["en"],  # languages (BCP 47), and those with voices
     "feat": ["achievements", "cloud", "controller", "crossplay", …],
     "players": {"local": 4, "online": 8},     # the most players the store says
     "age": [["PEGI", "16"], ["ESRB", "M"]],
     "img": {"h": …, "v": …, "t": …, "s": […]}}    # horizontal, vertical, thumbnail, screenshots: the store's names

Every key is left out when the store says nothing of it. Python's standard library only.
"""
import re

import common

# Steam's language numbers (ELanguage) as BCP 47 codes; a number it adds later is left out.
STEAM_LANGS = {0: "en", 1: "de", 2: "fr", 3: "it", 4: "ko", 5: "es", 6: "zh-Hans", 7: "zh-Hant", 8: "ru", 9: "th",
               10: "ja", 11: "pt", 12: "pl", 13: "da", 14: "nl", 15: "fi", 16: "no", 17: "sv", 18: "hu", 19: "cs",
               20: "ro", 21: "tr", 22: "ar", 23: "pt-BR", 24: "bg", 25: "el", 26: "uk", 27: "vi", 28: "es-419"}
# Steam's category numbers that are features of the sheet (the others: modes, the store's own services).
STEAM_FEATURES = {22: "achievements", 23: "cloud", 28: "controller", 18: "controller_partial", 27: "crossplay"}
GOG_FEATURES = {"achievements": "achievements", "cloud_saves": "cloud", "controller_support": "controller"}
GOG_OS = {"windows": "windows", "osx": "mac", "linux": "linux"}
GOG_AGES = {"pegiRating": "PEGI", "esrbRating": "ESRB", "uskRating": "USK", "ceroRating": "CERO"}
MS_FEATURES = {"XblAchievements": "achievements", "XblCloudSaves": "cloud", "XblCrossPlatformMultiPlayer": "crossplay",
               "XblCrossPlatformCoop": "crossplay", "XPA": "play_anywhere", "Capability4k": "4k", "CapabilityHDR": "hdr",
               "60fps": "60fps", "CapabilityVRR": "vrr", "PcGamePad": "controller", "ConsoleKeyboardMouse": "keyboard_mouse"}
MS_LOCAL = ("XblLocalCoop", "XblLocalMultiPlayer", "SharedSplitScreen")
MS_ONLINE = ("XblOnlineCoop", "XblOnlineMultiPlayer")
MS_AGES = ("PEGI", "ESRB", "USK", "CERO")
# The eShop's age rating (the US list's `rating`: the ESRB's minimum age) as its letters.
SWITCH_AGES = {6: "E", 10: "E10+", 13: "T", 17: "M"}
SWITCH_TID = re.compile(r"^0100[0-9A-F]{9}000$")      # a base game's title id (tools/build.py's TID)
FEATURES = ("achievements", "cloud", "controller", "controller_partial", "crossplay", "play_anywhere", "4k", "hdr",
            "60fps", "vrr", "keyboard_mouse")       # the sheet's order


def ordered(found):
    return [f for f in FEATURES if f in found]


def clean(out: dict) -> dict:
    return {k: v for k, v in out.items() if v}


def steam(item: dict) -> dict:
    """A Steam game's sheet, from the item collect.steam_item kept."""
    platforms = item.get("platforms") or {}
    langs, voices = [], []
    for number, voiced in item.get("languages") or []:
        code = STEAM_LANGS.get(number)
        if code and code not in langs:
            langs.append(code)
            if voiced:
                voices.append(code)
    categories = item.get("categories") or {}
    found = {STEAM_FEATURES[c] for ids in categories.values() if isinstance(ids, list) for c in ids if c in STEAM_FEATURES}
    if "controller" in found:
        found.discard("controller_partial")
    assets = item.get("assets") or {}
    deck = platforms.get("steam_deck_compat_category")
    return clean({
        "os": [name for key, name in (("windows", "windows"), ("mac", "mac"), ("steamos_linux", "linux")) if platforms.get(key)],
        "deck": deck if deck in (1, 2, 3) else 0, "langs": langs, "voices": voices, "feat": ordered(found),
        "img": clean({"h": assets.get("header"), "t": assets.get("small_capsule"), "s": item.get("screenshots")})})


def gog(product: dict) -> dict:
    """A GOG game's sheet, from the product collect.gog_product kept."""
    found = {GOG_FEATURES[f] for f in product.get("features") or [] if f in GOG_FEATURES}
    age = [[GOG_AGES[n], str(a)] for n, a in product.get("ratings") or [] if n in GOG_AGES]
    pictures = product.get("pictures") or {}
    return clean({
        "os": [GOG_OS[o] for o in product.get("operatingSystems") or [] if o in GOG_OS],
        "feat": ordered(found), "age": age,
        "img": clean({"h": pictures.get("cover"), "v": pictures.get("poster"), "s": pictures.get("screenshots")})})


def ms(product: dict) -> dict:
    """A Microsoft Store game's sheet, from the product collect.ms_product kept."""
    props = product.get("Properties") or {}
    attributes = {a["Name"]: a.get("Maximum") for a in props.get("Attributes") or [] if isinstance(a, dict) and a.get("Name")}
    found = {MS_FEATURES[n] for n in attributes if n in MS_FEATURES}
    players = {}
    for key, names in (("local", MS_LOCAL), ("online", MS_ONLINE)):
        most = max((attributes[n] for n in names if isinstance(attributes.get(n), int)), default=0)
        if most > 1:
            players[key] = most
    market = (product.get("MarketProperties") or [{}])[0]
    age = []
    for r in market.get("ContentRatings") or []:
        system, _, value = str(r.get("RatingId") or "").partition(":")
        if system in MS_AGES and value and system not in [a[0] for a in age]:
            age.append([system, "E10+" if (system, value) == ("ESRB", "E10") else value])
    pictures = {}
    for purpose, name in ((product.get("LocalizedProperties") or [{}])[0].get("Images") or []):
        if purpose == "SuperHeroArt":
            pictures.setdefault("h", name)
        elif purpose in ("BoxArt", "Poster"):
            pictures.setdefault("v", name)
        elif purpose == "Screenshot":
            pictures.setdefault("s", []).append(name)
    platforms = props.get("Platforms") or []
    return clean({
        "os": [o for o, p in (("windows", "Windows.Desktop"), ("xbox", "Windows.Xbox")) if p in platforms],
        "feat": ordered(found), "players": players, "age": age, "img": pictures})


def matches(lang: str, locale: str) -> bool:
    """Whether a game's language (a sheet's `langs`: "fr", "pt-BR", "zh-Hant"…) is a site locale's (site/i18n:
    "fr-CA", "en-US", "zh-Hans"…): the same language, and the same region or script unless one of the two names none
    (a game in "pt" is in "pt-BR" for the visitor, "zh-Hans" is not "zh-Hant"). The explorer does the same (explore.js)."""
    a, b = lang.split("-", 1), locale.split("-", 1)
    return a[0] == b[0] and (len(a) == 1 or len(b) == 1 or a[1] == b[1])


def switch(entry: dict) -> dict:
    """A Switch game's sheet, from the entry of titledb's US list that collect.collect_titledb kept. Its number
    of players is the most that play on one console, so it is the local count."""
    langs, said = [], entry.get("languages") or []
    for code in said:
        # Two `zh` are the two scripts (what the site's locales tell apart); one is Chinese, whichever script.
        for one in (("zh-Hans", "zh-Hant") if code == "zh" and said.count("zh") > 1 else (code,)):
            if isinstance(one, str) and one and one not in langs:
                langs.append(one)
    count = entry.get("numberOfPlayers")
    letters = SWITCH_AGES.get(entry.get("rating"))
    return clean({"langs": langs, "players": {"local": count} if isinstance(count, int) and count > 1 else {},
                  "age": [["ESRB", letters]] if letters else []})


def switch_id(key, record):
    """A base game's title id in titledb's list (its keys are the eShop's own); a demo is not that game."""
    tid = str(record.get("id") or "").strip().upper()
    return tid if SWITCH_TID.match(tid) and record.get("isDemo") not in (True, "True") else None


READERS = {"steam": ("sources/steam-store/apps.json", steam), "gog": ("sources/gog/catalog/US.json", gog),
           "xbox": ("sources/msstore/products.json", ms), "switch": ("sources/titledb/US.json", switch)}
IDENTIFIERS = {"switch": switch_id}       # a source not keyed by the game's id on the platform


def read(data_dir: str, platform: str) -> dict:
    """{game id: sheet} of a store's games, from its source in the data (nothing for a platform
    that is not one of the stores, or without its source)."""
    if platform not in READERS:
        return {}
    name, make = READERS[platform]
    games = (common.read_records(data_dir, name) or {}).get("games") or {}
    out = {}
    ident = IDENTIFIERS.get(platform)
    for gid, record in games.items():
        if isinstance(record, dict):
            gid = ident(gid, record) if ident else gid
            made = make(record) if gid else None
            if made:
                out[str(gid)] = made
    return out
