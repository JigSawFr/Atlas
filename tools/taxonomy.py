"""What the explorer calls the same thing the same way (site/README.md).

Each source has its own words for a game's kind: Wikidata says "role-playing
video game", the Microsoft Store "Role-playing (RPG)", Steam's players' tags
"RPG" and IGDB's "Role-playing (RPG)" again. The explorer shows one notion for
all of them, with its icon and its name in the page's language:

- CONCEPTS: the notions (genre, theme, mode, perspective), each with its icon
  (Lucide's, site/icons/) and the words the sources use for it;
- find(): the notion a source's word stands for, whatever the kind it came in
  (Steam's "Singleplayer" tag is a mode, IGDB's "Action" theme a genre);
- clean_title(): a game's name without the trademark signs, the stray spaces
  and the other noise the stores put around it.

The names shown are the site's catalogs' (x_g_<key>, x_t_<key>, x_m_<key>,
x_p_<key>: genres, themes, modes, perspectives). Python's standard library only.
"""
import re
import unicodedata

# Letter of a notion's catalog keys and the kind its games are filed under.
KINDS = {"g": "genres", "t": "themes", "m": "modes", "p": "perspectives"}
# The icon of each kind of facet, for the menus (the notions have their own).
KIND_ICONS = {"genres": "shapes", "themes": "palette", "modes": "users-round", "perspectives": "scan-eye",
              "series": "library", "developers": "building-2", "publishers": "megaphone", "tags": "tag",
              "year": "calendar"}

# (kind letter, key, Lucide icon, the words sources use, folded by fold()).
CONCEPTS = [
    ("g", "action", "zap", "action|action game|action video game"),
    ("g", "adventure", "compass", "adventure|adventure video game|adventure game|graphic adventure game"),
    ("g", "action_adventure", "footprints", "action adventure|action adventure game|walking simulator"),
    ("g", "rpg", "scroll-text", "rpg|role playing|role playing rpg|role playing video game|role playing game|jrpg"
     "|japanese role playing video game|turn based japanese role playing game|turn based role playing game"
     "|tactical role playing game|strategy rpg|party based rpg|dungeon crawl|dungeon crawler|massively multiplayer online role playing game"),
    ("g", "action_rpg", "wand-sparkles", "action role playing game|action rpg|soulslike"),
    ("g", "strategy", "chess-knight", "strategy|strategy video game|strategy game|tactical|tactics|4x|4x explore expand exploit and exterminate"
     "|grand strategy|wargame|computer wargame|tower defense|tower defence|god game|multi player online battle arena|moba"),
    ("g", "turn_based", "hourglass", "turn based|turn based strategy|turn based strategy video game|turn based strategy tbs"
     "|turn based tactics|turn based combat"),
    ("g", "real_time", "timer", "real time|real time strategy|real time strategy rts|rts|real time tactics"),
    ("g", "simulation", "cog", "simulation|simulation video game|simulator|life simulation game|life sim|vehicle simulation game"
     "|virtual life|social simulation game|flight simulation video game|combat flight simulator game"
     "|space flight simulation game|biological simulation video game|automobile sim|farming simulator"),
    ("g", "management", "briefcase", "management|managerial|economic|economy|business|business simulation game"
     "|construction and management simulation|city building game|city builder|resource management|time management"),
    ("g", "sports", "trophy", "sports|sport|sports video game|association football video game|association football management game"
     "|basketball video game|baseball video game|american football video game|tennis video game|golf video game"
     "|ice hockey video game|boxing video game|professional wrestling video game|skateboarding video game"
     "|athletics video game|bowling video game|fitness video game|cricket video game|snowboarding video game"),
    ("g", "racing", "car", "racing|racing video game|racing flying|sim racing|kart racing game|rally|driving|mascot racer"
     "|vehicular combat game|naval|off road"),
    ("g", "fighting", "hand-fist", "fighting|fighting game|2d fighting game|3d fighting game|combat"),
    ("g", "beat_em_up", "sword", "beat em up|side scrolling beat em up|hack and slash|hack and slash beat em up"
     "|character action video game|crowd combat video game"),
    ("g", "shooter", "crosshair", "shooter|shooter game|first person shooter|fps|third person shooter|tactical shooter"
     "|hero shooter|light gun shooter|rail shooter|run and gun|multidirectional shooter|looter shooter"),
    ("g", "shmup", "rocket", "shoot em up|shmup|bullet hell|scrolling shooter|vertically scrolling shooter"
     "|horizontally scrolling shooter|fixed shooter"),
    ("g", "platformer", "mountain", "platformer|platform|platform game|2d platform game|3d platform game|puzzle platformer"
     "|isometric platformer|collect a thon platformer"),
    ("g", "puzzle", "puzzle", "puzzle|puzzle video game|puzzle trivia|falling block puzzle game|logic|nonogram video game"
     "|maze video game|breakout clone|hidden object|hidden object game|tile matching video game"),
    ("g", "horror", "ghost", "horror|horror video game|survival horror|psychological horror|psychological horror fiction"),
    ("g", "survival", "tent", "survival|survival game"),
    ("g", "stealth", "eye-off", "stealth|stealth game"),
    ("g", "roguelike", "dices", "roguelike|roguelite|action roguelike"),
    ("g", "metroidvania", "map", "metroidvania|metroidbrainia|soulsvania"),
    ("g", "visual_novel", "book-open", "visual novel|interactive fiction|dating sim|otome game|eroge|bishojo game|romance adventure game"
     "|choose your own adventure|text adventure|interactive film|narrative|harem"),
    ("g", "music", "music", "music|music video game|rhythm game|rhythm|dance video game|karaoke video game"),
    ("g", "party", "party-popper", "party|party video game|party game|mini games|minigame"),
    ("g", "arcade", "gamepad-2", "arcade|pinball|pinball video game|pinball machine game|traditional video game|classics|classic"),
    ("g", "card_board", "layers", "card board|card board game|card game|board game|board video game|card video game"
     "|collectible card video game|card battle video game|deckbuilding|chess video game|mahjong video game"),
    ("g", "point_click", "mouse-pointer-click", "point and click|point and click adventure"),
    ("g", "casual", "coffee", "casual|casual game"),
    ("g", "family", "baby", "family kids|family friendly|kids|children|family"),
    ("g", "educational", "graduation-cap", "educational|educational video game|education"),
    ("g", "sandbox", "box", "sandbox|sandbox game"),
    ("g", "open_world", "tree-pine", "open world"),
    ("t", "fantasy", "castle", "fantasy|fantasy video game|dark fantasy|dark fantasy video game|magic|medieval"),
    ("t", "scifi", "orbit", "science fiction|science fiction video game|sci fi|space|space opera video game|cyberpunk"
     "|cyberpunk video game|mecha video game"),
    ("t", "comedy", "laugh", "comedy|funny|humor"),
    ("t", "mystery", "search", "mystery|detective|detective mystery|mystery video game|espionage|neo noir video game"),
    ("t", "historical", "landmark", "historical|historical video game|history|modern"),
    ("t", "warfare", "flag", "warfare|war|military"),
    ("t", "romance", "heart", "romance|romance video game"),
    ("t", "mature", "flame", "erotic|erotic video game|sexual content|nudity|hentai"),
    ("t", "post_apocalyptic", "skull", "post apocalyptic|post apocalyptic video game|zombies|zombie apocalyptic video game"),
    ("m", "single", "user", "single player|singleplayer|single player video game"),
    ("m", "multiplayer", "users", "multiplayer|multiplayer video game|multi player|massively multiplayer online game"
     "|bot multiplayer|asymmetrical multiplayer"),
    ("m", "coop", "handshake", "co operative|co op|co op mode|coop|cooperative|online co op"),
    ("m", "local", "monitor-smartphone", "split screen|shared splitscreen multiplayer|local multiplayer|local co op|hotseat"
     "|two player video game|shared screen"),
    ("m", "online", "wifi", "online|multiplayer online game|online multiplayer"),
    ("m", "mmo", "globe", "massively multiplayer online mmo|massively multiplayer|mmo"),
    ("m", "pvp", "swords", "pvp|player versus player"),
    ("m", "battle_royale", "target", "battle royale|battle royale game"),
    ("p", "first", "eye", "first person|fpp|first person view"),
    ("p", "third", "person-standing", "third person|tpp|third person view"),
    ("p", "side", "move-horizontal", "side view|side scroller|side scrolling video game"),
    ("p", "isometric", "box", "bird view isometric|isometric|top down|top down view"),
    ("p", "text", "type", "text|text based"),
    ("p", "vr", "glasses", "virtual reality|vr"),
    ("p", "auditory", "ear", "auditory"),
]


def fold(text: str) -> str:
    """A word as the aliases are written: no accents, lower case, the apostrophes dropped
    and every other run of signs one space ("Shoot 'em Up" -> "shoot em up")."""
    text = unicodedata.normalize("NFD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"['’`]", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _aliases() -> dict:
    found = {}
    for letter, key, _icon, words in CONCEPTS:
        for word in (fold(key.replace("_", " ")), *(fold(w) for w in words.split("|"))):
            if word and found.setdefault(word, (letter, key)) != (letter, key):
                raise ValueError(f"taxonomy: {word!r} is two notions' word")
    return found


ALIASES = _aliases()


def find(value: str):
    """(kind letter, key) of the notion a source's word stands for, None when it is none of them."""
    return ALIASES.get(fold(value))


_MARKS = re.compile(r"[™®©℠]")
_SPACES = re.compile(r"[\s ​‌‍﻿]+")


def clean_title(name: str) -> str:
    """A name as the games' own: the trademark signs gone, one space between words, Unicode
    in its composed form, no dash or colon left at the ends."""
    name = unicodedata.normalize("NFC", str(name))
    name = _MARKS.sub("", name)
    name = _SPACES.sub(" ", name).strip()
    return name.strip(" :-–—,").strip()


_VIDEO_GAME = re.compile(r"\s+video\s+game$", re.I)


def tidy_label(name: str) -> str:
    """A genre or tag no notion names, as the others read: Wikidata's lower case labels get their
    capital and lose their "video game" ("social deduction video game" -> "Social deduction")."""
    name = clean_title(name)
    short = _VIDEO_GAME.sub("", name)
    name = short or name
    return name[:1].upper() + name[1:] if name[:1].islower() else name
