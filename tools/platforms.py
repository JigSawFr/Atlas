"""The platforms Atlas has files of, each its folder in platforms/<id>/ on
the data branch, and platforms.json, their registry: each platform's id, its
name, its Wikidata item, its IGDB platform (slug) and Aurore's id for it,
when Aurore runs there.

The ids are Aurore's where the two meet (switch, 3ds, psv, ps4, ios,
android), a store's name for a store (steam, gog, xbox: the Microsoft
Store's games, Xbox and PC), and a machine's short name for the others
(the retro ones, a folder a machine, from Wikidata's P400). Each has its
kind: store, console (a machine whose games no store sells any more, with
a source of its own: the 3DS) or retro (Wikidata alone).
"""
import datetime
import os

import common

FOLDER = "platforms"

# (id, name, Wikidata item, IGDB platform slug, Aurore's id, kind)
STORES = [
    ("switch", "Nintendo Switch", "Q19610114", "switch", "switch", "store"),
    ("steam", "Steam", "Q337535", "win", None, "store"),
    ("gog", "GOG", None, "win", None, "store"),
    ("xbox", "Xbox and Microsoft Store", "Q13361286", "xboxone", None, "store"),
]
# Consoles with files of their own though no store sells their games any more (tools/n3ds.py).
CONSOLES = [
    ("3ds", "Nintendo 3DS", "Q203597", "3ds", "3ds", "console"),
]
# The machines no store Atlas reads sells games of any more (tools/retro.py).
RETRO = [
    ("nes", "Nintendo Entertainment System", "Q172742", "nes", None),
    ("fds", "Famicom Disk System", "Q135321", "fds", None),
    ("snes", "Super Nintendo Entertainment System", "Q183259", "snes", None),
    ("n64", "Nintendo 64", "Q184839", "n64", None),
    ("gamecube", "Nintendo GameCube", "Q182172", "ngc", None),
    ("wii", "Wii", "Q8079", "wii", None),
    ("wiiu", "Wii U", "Q56942", "wiiu", None),
    ("gb", "Game Boy", "Q186437", "gb", None),
    ("gbc", "Game Boy Color", "Q203992", "gbc", None),
    ("gba", "Game Boy Advance", "Q188642", "gba", None),
    ("nds", "Nintendo DS", "Q170323", "nds", None),
    ("ps1", "PlayStation", "Q10677", "ps", None),
    ("ps2", "PlayStation 2", "Q10680", "ps2", None),
    ("ps3", "PlayStation 3", "Q10683", "ps3", None),
    ("psp", "PlayStation Portable", "Q170325", "psp", None),
    ("psv", "PlayStation Vita", "Q188808", "psvita", "psv"),
    ("xbox-og", "Xbox (2001)", "Q132020", "xbox", None),
    ("xbox360", "Xbox 360", "Q48263", "xbox360", None),
    ("sms", "Sega Master System", "Q209868", "sms", None),
    ("genesis", "Sega Genesis / Mega Drive", "Q10676", "genesis-slash-megadrive", None),
    ("segacd", "Sega CD / Mega-CD", "Q1047516", "segacd", None),
    ("gamegear", "Game Gear", "Q751719", "gamegear", None),
    ("saturn", "Sega Saturn", "Q200912", "saturn", None),
    ("dreamcast", "Dreamcast", "Q184198", "dc", None),
    ("atari2600", "Atari 2600", "Q206261", "atari2600", None),
    ("atarist", "Atari ST", "Q627302", "atari-st", None),
    ("colecovision", "ColecoVision", "Q1046862", "colecovision", None),
    ("turbografx16", "TurboGrafx-16 / PC Engine", "Q1057377", "turbografx16--1", None),
    ("neogeo", "Neo Geo", "Q1054350", None, None),
    ("3do", "3DO", "Q229429", "3do", None),
    ("cdi", "Philips CD-i", "Q1023103", "philips-cd-i", None),
    ("arcade", "Arcade", "Q192851", "arcade", None),
    ("c64", "Commodore 64", "Q99775", "c64", None),
    ("amiga", "Amiga", "Q100047", "amiga", None),
    ("zxspectrum", "ZX Spectrum", "Q23882", "zxs", None),
    ("amstradcpc", "Amstrad CPC", "Q478829", "acpc", None),
    ("msx", "MSX", "Q853547", "msx", None),
    ("apple2", "Apple II", "Q3017175", "appleii", None),
    ("dos", "MS-DOS", "Q47604", None, None),
]
RETRO_BY_QID = {qid: pid for pid, _, qid, _, _ in RETRO}
# What a machine of retro.py's query is not RETRO's: its own folder, its own tool.
OWN = {qid for _, _, qid, _, _, _ in CONSOLES}


def path(platform, name):
    """A platform's file on the data branch: platforms/<id>/<name>."""
    return f"{FOLDER}/{platform}/{name}"


def registry(today=None):
    """platforms.json's content."""
    entries = {}
    for pid, name, qid, igdb, aurore, kind in STORES + CONSOLES + [r + ("retro",) for r in RETRO]:
        entries[pid] = {k: v for k, v in (("name", name), ("qid", qid), ("igdb", igdb), ("aurore", aurore),
                                          ("kind", kind)) if v}
    return {"schema": 1, "generated": (today or datetime.date.today()).isoformat(),
            "source": "Atlas (Wikidata items, IGDB platforms, Aurore's ids)", "platforms": entries}


def write_registry(out_dir, today=None):
    """platforms.json in out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    common._dump(os.path.join(out_dir, "platforms.json"), registry(today))
