"""What the explorer calls the same thing the same way (site/README.md).

Each source has its own words for a game's kind: Wikidata says "role-playing
video game", the Microsoft Store "Role-playing (RPG)", Steam's players' tags
"RPG" and IGDB's "Role-playing (RPG)" again. The explorer shows one notion for
all of them, with its icon and its name in the page's language:

- CONCEPTS: the notions (genre, theme, mode, perspective, and the ones the stores' players' tags
  say: visual style, mood, gameplay, content, access), each with its icon
  (Lucide's, site/icons/) and the words the sources use for it;
- find(): the notion a source's word stands for, whatever the kind it came in
  (Steam's "Singleplayer" tag is a mode, IGDB's "Action" theme a genre);
- clean_title(): a game's name without the trademark signs, the stray spaces
  and the other noise the stores put around it.

The names shown are the site's catalogs' (x_<letter>_<key>: g genres, t themes, m modes, p perspectives,
y styles, o moods, h gameplay, c content, a access). Python's standard library only.
"""
import html
import re
import unicodedata

# Letter of a notion's catalog keys and the kind its games are filed under.
KINDS = {"g": "genres", "t": "themes", "m": "modes", "p": "perspectives", "y": "styles", "o": "moods",
         "h": "gameplay", "c": "content", "a": "access"}
# The icon of each kind of facet, for the menus (the notions have their own).
KIND_ICONS = {"genres": "shapes", "themes": "palette", "modes": "users-round", "perspectives": "scan-eye",
              "styles": "paintbrush", "moods": "smile", "gameplay": "joystick", "content": "triangle-alert",
              "access": "ticket", "series": "library", "developers": "building-2", "publishers": "megaphone",
              "tags": "tag", "year": "calendar"}
# A genre inside others: filtering by the larger one takes the smaller's games too (the facets, not the sheets).
PARENTS = {"platformer": ("action",), "shooter": ("action",), "shmup": ("action",), "fighting": ("action",),
           "beat_em_up": ("action",), "stealth": ("action",), "action_rpg": ("action", "rpg"), "jrpg": ("rpg",),
           "action_adventure": ("action", "adventure"), "metroidvania": ("action", "adventure"),
           "point_click": ("adventure",), "visual_novel": ("adventure",), "walking_sim": ("adventure",),
           "turn_based": ("strategy",), "real_time": ("strategy",), "tactics": ("strategy", "rpg"),
           "tower_defense": ("strategy",), "moba": ("strategy",), "management": ("simulation",),
           "life_sim": ("simulation",)}

# (kind letter, key, Lucide icon, the words sources use, folded by fold()).
CONCEPTS = [
    ("g", "action", "zap", 'action|action game|action video game'),
    ("g", "adventure", "compass", 'adventure|adventure video game|adventure game|graphic adventure game'),
    ("g", "action_adventure", "binoculars", 'action adventure|action adventure game'
     '|immersive sim'),
    ("g", "rpg", "scroll-text", 'rpg|role playing|role playing rpg|role playing video game|role playing game'
     '|turn based role playing game|dungeon crawl|dungeon crawler'
     '|massively multiplayer online role playing game|crpg|mmorpg|creature collector'),
    ("g", "action_rpg", "wand-sparkles", 'action role playing game|action rpg|soulslike|souls like'),
    ("g", "strategy", "chess-knight", 'strategy|strategy video game|strategy game|4x|4x explore expand exploit and exterminate'
     '|grand strategy|wargame|computer wargame|god game'),
    ("g", "turn_based", "hourglass", 'turn based|turn based strategy|turn based strategy video game|turn based strategy tbs'
     '|turn based combat'),
    ("g", "real_time", "timer", 'real time|real time strategy|real time strategy rts|rts'
     '|action rts'),
    ("g", "simulation", "cog", 'simulation|simulation video game|simulator|vehicle simulation game'
     '|flight simulation video game|combat flight simulator game|space flight simulation game'
     '|biological simulation video game|automobile sim|hunting video game|fishing video game'
     '|submarine simulator|ship simulation game|train simulator|tank simulation game|space sim'
     '|trains|flight|photography game'
     '|fishing'),
    ("g", "management", "briefcase", 'management|managerial|economic|economy|business|business simulation game'
     '|construction and management simulation|city building game|city builder|resource management'
     '|time management|colony sim|base building|automation|trading|capitalism|inventory management'
     '|political sim|government simulation game'
     '|building'),
    ("g", "sports", "trophy", 'sports|sport|sports video game|association football video game'
     '|association football management game|basketball video game|baseball video game'
     '|american football video game|tennis video game|golf video game|ice hockey video game'
     '|boxing video game|professional wrestling video game|skateboarding video game'
     '|athletics video game|bowling video game|fitness video game|cricket video game'
     '|snowboarding video game|soccer|pool|snooker|winter sports|extreme sports|handball'
     '|miniature golf|olympic|esports'
     '|football soccer'),
    ("g", "racing", "car", 'racing|racing video game|racing flying|sim racing|kart racing game|rally|driving'
     '|mascot racer|vehicular combat game|naval|off road|combat racing|arcade racing game'
     '|horse racing'
     '|vehicular combat'),
    ("g", "fighting", "hand-fist", 'fighting|fighting game|2d fighting game|3d fighting game|combat|2d fighter|3d fighter'
     '|spectacle fighter|platform fighter|arena fighter|martial arts|swordplay'),
    ("g", "beat_em_up", "sword", 'beat em up|side scrolling beat em up|hack and slash|hack and slash beat em up'
     '|character action video game|crowd combat video game'
     '|character action'),
    ("g", "shooter", "crosshair", 'shooter|shooter game|first person shooter|fps|third person shooter|tactical shooter'
     '|hero shooter|light gun shooter|rail shooter|run and gun|multidirectional shooter'
     '|looter shooter|twin stick shooter|top down shooter|arena shooter|boomer shooter'
     '|horde shooter|tube shooter'),
    ("g", "shmup", "rocket", 'shoot em up|shmup|bullet hell|scrolling shooter|vertically scrolling shooter'
     '|horizontally scrolling shooter|fixed shooter'
     '|bullet heaven'),
    ("g", "platformer", "mountain", 'platformer|platform|platform game|2d platform game|3d platform game|puzzle platformer'
     '|isometric platformer|collect a thon platformer|2d platformer|3d platformer'
     '|precision platformer|collectathon|cinematic platformer|runner|endless runner game|parkour'),
    ("g", "puzzle", "puzzle", 'puzzle|puzzle video game|puzzle trivia|falling block puzzle game|logic|nonogram video game'
     '|maze video game|breakout clone|hidden object|hidden object game|tile matching video game'
     '|word game|word|sudoku|match 3|escape room|casino game'
     '|sokoban|solitaire'),
    ("g", "horror", "ghost", 'horror|horror video game|survival horror|psychological horror|psychological horror fiction'
     '|lovecraftian|science fiction horror'),
    ("g", "survival", "tent", 'survival|survival game|open world survival craft'),
    ("g", "stealth", "eye-off", 'stealth|stealth game'),
    ("g", "roguelike", "dices", 'roguelike|roguelite|action roguelike|roguelike deckbuilder|roguelike deck building game'
     '|mystery dungeon'),
    ("g", "metroidvania", "map", 'metroidvania|metroidbrainia|soulsvania'),
    ("g", "visual_novel", "book-open", 'visual novel|interactive fiction|dating sim|otome game|eroge|bishojo game'
     '|romance adventure game|choose your own adventure|text adventure|interactive film|narrative'
     '|harem|fmv|full motion video'
     '|otome'),
    ("g", "music", "music", 'music|music video game|rhythm game|rhythm|dance video game|karaoke video game'),
    ("g", "party", "party-popper", 'party|party video game|party game|mini games|minigame'),
    ("g", "arcade", "gamepad-2", 'arcade|pinball|pinball video game|pinball machine game|traditional video game|classics'
     '|classic|score attack'),
    ("g", "card_board", "layers", 'card board|card board game|card game|board game|board video game|card video game'
     '|collectible card video game|card battle video game|deckbuilding|chess video game'
     '|mahjong video game|card battler|trading card game|tabletop|auto battler'),
    ("g", "point_click", "mouse-pointer-click", 'point and click|point and click adventure'),
    ("g", "casual", "coffee", 'casual|casual game'),
    ("g", "family", "baby", 'family kids|family friendly|kids|children|family'),
    ("g", "educational", "graduation-cap", 'educational|educational video game|education'),
    ("g", "sandbox", "box", 'sandbox|sandbox game'),
    ("g", "open_world", "tree-pine", 'open world'),
    ("t", "fantasy", "castle", 'fantasy|fantasy video game|dark fantasy|dark fantasy video game|magic|medieval|demons'),
    ("t", "scifi", "orbit", 'science fiction|science fiction video game|sci fi|space|space opera video game|cyberpunk'
     '|cyberpunk video game|mecha video game|aliens|robots|mechs|futuristic|time travel'),
    ("t", "comedy", "laugh", 'comedy|funny|humor|dark humor|dark comedy|parody|memes'),
    ("t", "mystery", "search", 'mystery|detective|detective mystery|mystery video game|espionage|neo noir video game'
     '|investigation'),
    ("t", "historical", "landmark", 'historical|historical video game|history|modern|alternate history'),
    ("t", "warfare", "flag", 'warfare|war|military'),
    ("t", "romance", "heart", 'romance|romance video game'),
    ("t", "post_apocalyptic", "skull", 'post apocalyptic|post apocalyptic video game|zombies|zombie apocalyptic video game'),
    ("m", "single", "user", 'single player|singleplayer|single player video game'),
    ("m", "multiplayer", "users", 'multiplayer|multiplayer video game|multi player|massively multiplayer online game'
     '|bot multiplayer|asymmetrical multiplayer'),
    ("m", "coop", "handshake", 'co operative|co op|co op mode|coop|cooperative|online co op'),
    ("m", "local", "monitor-smartphone", 'split screen|shared splitscreen multiplayer|local multiplayer|local co op|hotseat'
     '|two player video game|shared screen|4 player local'),
    ("m", "online", "wifi", 'online|multiplayer online game|online multiplayer'),
    ("m", "mmo", "globe", 'massively multiplayer online mmo|massively multiplayer|mmo'),
    ("m", "pvp", "swords", 'pvp|player versus player|competitive|team based'),
    ("m", "battle_royale", "target", 'battle royale|battle royale game'),
    ("p", "first", "eye", 'first person|fpp|first person view'),
    ("p", "third", "person-standing", 'third person|tpp|third person view'),
    ("p", "side", "move-horizontal", 'side view|side scroller|side scrolling video game'),
    ("p", "isometric", "box", 'bird view isometric|isometric|top down|top down view'),
    ("p", "text", "type", 'text|text based'),
    ("p", "vr", "glasses", 'virtual reality|vr'),
    ("p", "auditory", "ear", 'auditory'),
    ("g", "jrpg", "sparkles", 'jrpg|japanese role playing video game|turn based japanese role playing game'),
    ("g", "tactics", "grid-3x3", 'tactical|tactics|tactical rpg|tactical role playing game|turn based tactics'
     '|real time tactics|hex grid|grid based movement|strategy rpg|party based rpg'),
    ("g", "moba", "radar", 'moba|multiplayer online battle arena|multi player online battle arena'),
    ("g", "tower_defense", "shield", 'tower defense|tower defence'),
    ("g", "walking_sim", "footprints", 'walking simulator|walking sim'),
    ("g", "idle", "clock", 'idle|idler|incremental|clicker'),
    ("g", "life_sim", "sprout", 'life simulation game|life sim|virtual life|social simulation game|farming sim'
     '|farming simulation game|farming simulator|agriculture|cooking|virtual pet'),
    ("t", "western", "tent", 'western|wild west'),
    ("t", "ww2", "flag", 'world war ii|world war 2|ww2'),
    ("t", "crime", "briefcase", 'crime|noir|gangster'),
    ("t", "mythology", "gem", 'mythology|norse|greek mythology'),
    ("t", "pirates", "anchor", 'pirates|pirate'),
    ("t", "steampunk", "cog", 'steampunk'),
    ("t", "dystopian", "skull", 'dystopian'),
    ("t", "supernatural", "ghost", 'supernatural|vampire|vampire video game|occult'),
    ("t", "animals", "cat", 'cats|dinosaurs|dogs|animals'),
    ("t", "nature", "tree-deciduous", 'nature|underwater'),
    ("t", "drama", "drama", 'drama|drama anime and manga'),
    ("t", "thriller", "triangle-alert", 'thriller|psychological|psychological thriller'),
    ("y", "pixel_art", "grip", 'pixel graphics|pixel art|8 bit|16 bit'),
    ("y", "flat_2d", "square", '2d|2 5d|side on'),
    ("y", "model_3d", "cuboid", '3d'),
    ("y", "hand_drawn", "pencil", 'hand drawn|hand painted|watercolor'),
    ("y", "cartoon", "paintbrush", 'cartoony|cartoon|comic book|cel shaded'),
    ("y", "anime", "sparkles", 'anime|manga'),
    ("y", "realistic", "eye", 'realistic|photorealistic'),
    ("y", "stylized", "wand-sparkles", 'stylized|abstract|low poly'),
    ("y", "minimalist", "square", 'minimalist|minimalism'),
    ("y", "colorful", "rainbow", 'colorful|colourful|psychedelic'),
    ("y", "retro", "gamepad-2", 'retro|old school|1980s|1990s|1990 s|1980 s'),
    ("y", "voxel", "box", 'voxel'),
    ("o", "atmospheric", "wind", 'atmospheric|cinematic'),
    ("o", "relaxing", "coffee", 'relaxing|chill'),
    ("o", "cozy", "sun-snow", 'cozy|wholesome|cosy'),
    ("o", "dark", "moon", 'dark|gloomy'),
    ("o", "emotional", "heart", 'emotional|touching'),
    ("o", "cute", "smile", 'cute|kawaii'),
    ("o", "difficult", "mountain-snow", 'difficult|challenging|hard|punishing'),
    ("o", "fast_paced", "zap", 'fast paced'),
    ("o", "surreal", "brain-circuit", 'surreal|experimental'),
    ("h", "story_rich", "book-open", 'story rich|lore rich|dialogue heavy|narration'),
    ("h", "choices", "shuffle", 'choices matter|multiple endings|nonlinear'),
    ("h", "exploration", "compass", 'exploration'),
    ("h", "crafting", "hammer", 'crafting'),
    ("h", "customization", "palette", 'character customization|customization'),
    ("h", "procedural", "dices", 'procedural generation|roguelike elements'),
    ("h", "permadeath", "skull", 'perma death|permadeath'),
    ("h", "physics", "orbit", 'physics|destruction'),
    ("h", "replayable", "clock", 'replay value'),
    ("h", "moddable", "wrench", 'moddable|level editor|mod support'),
    ("c", "mature", "flame", 'erotic|erotic video game|sexual content|nudity|hentai|mature'),
    ("c", "violence", "triangle-alert", 'violent|violence'),
    ("c", "gore", "droplet", 'gore|blood'),
    ("c", "lgbtq", "rainbow", 'lgbtq|video game with lgbt character|lgbt themed video game|lgbt themed'),
    ("a", "indie", "sprout", 'indie'),
    ("a", "free_to_play", "ticket", 'free to play|f2p'),
    ("a", "early_access", "flask-conical", 'early access'),
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


def with_parents(genres) -> list:
    """The genres and the larger ones they are in (each once, in order): a platformer is also an action game."""
    out = []
    for g in genres:
        for key in (g, *PARENTS.get(g, ())):
            if key not in out:
                out.append(key)
    return out


def find(value: str):
    """(kind letter, key) of the notion a source's word stands for, None when it is none of them."""
    word = fold(value)
    found = ALIASES.get(word)
    for suffix in (" video game", " game"):
        if not found and word.endswith(suffix):
            found = ALIASES.get(word[:-len(suffix)])      # "horse racing video game" is "horse racing"
    return found


# The words a company's name ends with by law, not by name.
LEGAL = {"inc", "incorporated", "ltd", "limited", "llc", "llp", "lp", "plc", "co", "corp", "corporation", "company",
         "gmbh", "ag", "sa", "sas", "sarl", "srl", "spa", "bv", "nv", "ab", "as", "oy", "aps", "kk", "pty", "sp", "zoo", "ou"}
# The same, written in the scripts that glue it to the name ("株式会社カプコン").
LEGAL_CJK = ("株式会社", "有限会社", "合同会社", "有限公司", "股份有限公司", "(株)", "（株）")
# The places a branch of a company is named after ("Atlus USA", "Nintendo of America"): the company's own name without them.
REGIONS = {"usa", "america", "americas", "europe", "uk", "japan", "germany", "france", "italy", "spain", "asia", "australia", "canada"}
# One company under the names its branches and its legal entities go by; {key: the key it shares}, curated:
# a name is added when it is plainly the same company, not when it only starts alike ("Avalanche Software"
# and "Avalanche Studios" are two studios, "Atari Games" an arcade maker apart from "Atari").
COMPANY_ALIASES = {
    "ubisoft entertainment": "ubisoft",
    "konami digital entertainment": "konami",
    "activision publishing": "activision",
    "sega interactive": "sega",
    "sega enterprises": "sega",
    "sega games": "sega",
    "capcom entertainment": "capcom",
    "bandai namco entertainment": "bandai namco",
    "bandai namco games": "bandai namco",
    "koei tecmo games": "koei tecmo",
    "team17 digital": "team17",
    "team17 software": "team17",
    "microprose software": "microprose",
    "tinybuild games": "tinybuild",
    "interplay entertainment": "interplay",
    "interplay productions": "interplay",
    "sierra entertainment": "sierra",
    "midway games": "midway",
    "acclaim entertainment": "acclaim",
    "acclaim games": "acclaim",
    "telltale games": "telltale",
    "headup games": "headup",
    "kalypso media digital": "kalypso media",
    "kalypso media group": "kalypso media",
    "ziggurat interactive": "ziggurat",
    "eidos interactive": "eidos",
    "infogrames studios": "infogrames",
    "virgin interactive entertainment": "virgin interactive",
    "warner bros interactive entertainment": "warner bros games",
    "warner bros interactive": "warner bros games",
    "warner bros": "warner bros games",
    "sony computer entertainment": "sony interactive entertainment",
    "codemasters software": "codemasters",
    "slitherine software": "slitherine",
    "ocean software": "ocean",
    "lucasfilm games": "lucasfilm",
    "mindscape international": "mindscape",
    "jaleco entertainment": "jaleco",
    # More names of the same company, found in the published data (2026-11):
    "sega studios": "sega", "sega entertainment": "sega", "atari interactive": "atari",
    "bandai namco studio": "bandai namco studios", "namco bandai games": "bandai namco",
    "namco bandai studios": "bandai namco studios", "snk games": "snk", "thq studio": "thq",
    "thq digital studios": "thq", "codemasters digital": "codemasters", "xbox games studios": "xbox game studios",
    "microsoft studios": "xbox game studios", "microsoft game studios": "xbox game studios",
    "acclaim studios": "acclaim", "infogrames entertainment": "infogrames", "2k games": "2k",
    "gremlin": "gremlin interactive", "gremlin graphics": "gremlin graphics software",
    "virgin games": "virgin interactive", "marvelous entertainment": "marvelous",
    "marvelous interactive": "marvelous", "marvelous games": "marvelous",
    "ubisoft montreal studio": "ubisoft montreal", "ubisoft paris studio": "ubisoft paris",
    "ubisoft paris studios": "ubisoft paris", "visual concepts entertainment": "visual concepts",
    "headup publishing": "headup", "mastertronic group": "mastertronic", "rockstar studios": "rockstar games",
    "majesco": "majesco entertainment", "aspyr media": "aspyr", "aspyr studios": "aspyr",
    "titus": "titus interactive", "titus software": "titus interactive", "gamersky": "gamersky games",
    "maximum entertainment": "maximum games", "crave": "crave entertainment", "gearbox": "gearbox software",
    "double fine": "double fine productions", "system 3 software": "system 3",
    "qubyte game studio": "qubyte interactive", "cyanide": "cyanide studio", "cyanide studios": "cyanide studio",
    "saber software": "saber interactive", "alawar entertainment": "alawar", "popcap": "popcap games",
    "domark": "domark software", "empire software": "empire interactive", "empire games": "empire interactive",
    "empire interactive entertainment": "empire interactive", "maxis software": "maxis",
    "high voltage": "high voltage software", "zoo digital": "zoo", "zoo digital publishing": "zoo",
    "zoo publishing": "zoo", "zoo games": "zoo", "grabthegames studios": "grabthegames",
    "dinamic games": "dinamic software", "goblinz studio": "goblinz publishing", "goblinz": "goblinz publishing",
    "goblinz digital": "goblinz publishing", "gamemill publishing": "gamemill entertainment",
    "gamemill": "gamemill entertainment", "vivendi": "vivendi games", "eurocom entertainment software": "eurocom",
    "blitz games studios": "blitz games", "toplitz": "toplitz productions", "raven studio": "raven software",
    "big ant": "big ant studios", "apogee software": "apogee entertainment", "epic games publishing": "epic games",
    "techland publishing": "techland", "firebird games": "firebird software", "firebird": "firebird software",
    "deck13 interactive": "deck13", "3d realms entertainment": "3d realms", "soedesco publishing": "soedesco",
    "armor games": "armor games studios", "tt games publishing": "tt games", "tt studios": "tt games",
    "crytek studios": "crytek", "pid publishing": "pid games", "neversoft entertainment": "neversoft",
    "medibang": "medibang games", "cave interactive": "cave", "five bn": "five bn games",
    "gsc world publishing": "gsc game world", "whitethorn digital": "whitethorn games",
    "sting entertainment": "sting", "8floor games": "8floor", "larian studios games": "larian studios",
    "octo games studio": "octo games", "funbox": "funbox media", "funbox games": "funbox media",
    "stardock": "stardock entertainment", "astragon": "astragon entertainment", "pm entertainment": "pm studios",
    "pm studio": "pm studios", "eko": "eko software", "asmik ace": "asmik ace entertainment",
    "merge publishing": "merge games", "cryo studios": "cryo interactive", "ravenscourt games": "ravenscourt",
    "martech": "martech games", "skybound entertainment": "skybound games", "remedy games": "remedy entertainment",
    "remedy": "remedy entertainment", "softstar": "softstar entertainment", "sammy studios": "sammy",
    "zeppelin studio": "zeppelin games", "visceral": "visceral games", "kadokawa": "kadokawa games",
    "electric dreams": "electric dreams software", "croteam publishing": "croteam",
    "application systems heidelberg software": "application systems heidelberg",
    "utv ignition entertainment": "utv ignition games", "starbyte software": "starbyte", "firaxis": "firaxis games",
    "criterion software": "criterion games", "aldorlea": "aldorlea games", "palace game": "palace software",
    "asobo": "asobo studio", "starbreeze entertainment": "starbreeze studios",
    "starbreeze publishing": "starbreeze studios", "starbreeze": "starbreeze studios",
    "chorus worldwide": "chorus worldwide games", "gray matter interactive": "gray matter",
    "gray matter studios": "gray matter",
}

# The words a studio's or a publisher's name adds to the company's own ("Konami Digital Entertainment").
DESCRIPTORS = {"entertainment", "games", "game", "studios", "studio", "software", "interactive", "publishing", "digital",
               "productions", "production", "group", "media", "labs", "works", "international", "holdings",
               "technologies", "technology", "network"}
# Names that look like another company's with a descriptor added, and are not.
NOT_THE_SAME = {"atari games"}          # the arcade maker, apart from Atari
MAX_ABSORBED = 4                        # a base name that absorbs more than this many is a common word ("Phoenix")


def company_core(key: str) -> str:
    """A company key without the descriptors it ends with ("konami digital entertainment" is "konami")."""
    words = key.split()
    while len(words) > 1 and words[-1] in DESCRIPTORS:
        words.pop()
    return " ".join(words)


def company_merges(uses: dict) -> dict:
    """{key: the key of the company it adds descriptors to} from {company key: games that name it}.
    Only a name the data has itself is a base ("Konami" is there, so "Konami Digital Entertainment" is
    Konami; "Avalanche Software" and "Avalanche Studios" stay two when there is no "Avalanche"), and a base that
    would take in many names, or is a descriptor, is left alone."""
    merges = {}
    for key in uses:
        core = company_core(key)
        if core != key and len(core) >= 3 and core in uses and core not in DESCRIPTORS and key not in NOT_THE_SAME:
            merges[key] = core
    taken = {}
    for base in merges.values():
        taken[base] = taken.get(base, 0) + 1
    return {k: b for k, b in merges.items() if taken[b] <= MAX_ABSORBED}


_SEPARATORS = re.compile(r"\s*;\s*|\s+/\s+|\s+\+\s+")


def split_company(name: str) -> list:
    """The companies a credit names when it lists several ("id Software / Nightdive Studios", "A; B")."""
    return [part for part in _SEPARATORS.split(str(name)) if part.strip()]


_NOTE = re.compile(r"\s*[(（][^()（）]*[)）]\s*$")


def drop_note(name: str) -> str:
    """A company's name without the note in brackets at its end ("Feral Interactive (Mac)", "Atlus (Japan)"),
    unless nothing else is left."""
    while True:
        short = _NOTE.sub("", name)
        if not short.strip() or short == name:
            return name
        name = short


def company_key(name: str) -> str:
    """What two spellings of a studio or a publisher share ("Nintendo Co., Ltd." and "NINTENDO" are
    "nintendo", "Atlus USA" and "ATLUS" are "atlus"): the name folded (in any script, not only the
    Latin one), without its note in brackets, its leading "the", the legal words it ends with, the
    place of a branch, and its other names in COMPANY_ALIASES."""
    text = unicodedata.normalize("NFKC", html.unescape(str(name)))
    text = drop_note(text)
    for word in LEGAL_CJK:
        text = text.replace(word, " ")
    text = unicodedata.normalize("NFD", text.casefold())
    text = unicodedata.normalize("NFC", "".join(c for c in text if not "\u0300" <= c <= "\u036f"))   # accents, not kana's marks
    text = re.sub(r"['’`]", "", text)
    words = re.sub(r"[\W_]+", " ", text).split()
    kept = list(words)

    def strip(until):
        while len(words) > 1 and until():
            words.pop()

    if words[:1] == ["the"] and len(words) > 1:
        words = words[1:]
    strip(lambda: words[-1] in LEGAL)
    if len(words) > 2 and words[-2] == "of" and words[-1] in REGIONS:
        words = words[:-2]
    strip(lambda: words[-1] in REGIONS)
    strip(lambda: words[-1] in LEGAL)
    key = " ".join(words) or " ".join(kept)
    return COMPANY_ALIASES.get(key, key)


_MARKS = re.compile(r"[™®©℠]")
_SPACES = re.compile(r"[\s ​‌‍﻿]+")


def clean_title(name: str) -> str:
    """A name as the games' own: the trademark signs gone, one space between words, Unicode
    in its composed form, no dash or colon left at the ends."""
    name = unicodedata.normalize("NFC", html.unescape(str(name)))
    name = _MARKS.sub("", name)
    name = _SPACES.sub(" ", name).strip()
    return name.strip(" :-–—,").strip()


# Words a shouted title keeps as they are: acronyms and brands the games write in capitals.
GAME_KEEP = frozenset({"DOOM", "LEGO", "FIFA", "UEFA", "NASCAR", "NHL", "NFL", "NBA", "MLB", "WWE", "UFC", "PGA",
                       "GTA", "RPG", "FPS", "VR", "HD", "DX", "EX", "XL", "DLC", "FAQ", "BMX", "ATV", "SD",
                       "PES", "TNT", "TV", "DJ", "MC", "AI", "OK", "ZX", "ARK", "RAGE", "LIMBO", "INSIDE"})
_SMALL_WORDS = frozenset({"of", "the", "and", "a", "an", "in", "on", "to", "for", "at", "by", "vs", "or", "with"})
_ROMAN = re.compile(r"^(?=[IVXLCDM]+$)M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$")
_LETTERS = re.compile(r"[^\W\d_]")


def game_title(name: str) -> str:
    """A game's name as clean_title leaves it, and a shouting one (two letters or more, every one a
    capital: "THE WITCHER 3: WILD HUNT") in the case of a title ("The Witcher 3: Wild Hunt"). The
    acronyms of GAME_KEEP, the Roman numerals and the words without a vowel ("NBA") stay as written;
    a name with any lower case letter is never touched."""
    name = clean_title(name)
    letters = _LETTERS.findall(name)
    if len(letters) < 2 or any(c != c.upper() for c in letters):
        return name
    out, start = [], True
    for word in name.split(" "):
        core = re.sub(r"[^\w]", "", word)
        if not core or core.isdigit() or core in GAME_KEEP or _ROMAN.match(core) or not re.search(r"[AEIOUY]", core.upper()) \
                or (re.search(r"\d", core) and core[0].isdigit() and core.upper() == core):
            out.append(word)
        elif not start and core.lower() in _SMALL_WORDS:
            out.append(word.lower())
        else:
            out.append(re.sub(r"(?<![\w'’])[^\W\d_]+", lambda m: m.group(0).capitalize(), word.lower()))
        start = word.endswith(":")
    return " ".join(out)


_VIDEO_GAME = re.compile(r"\s+video\s+game$", re.I)


def tidy_label(name: str) -> str:
    """A genre or tag no notion names, as the others read: Wikidata's lower case labels get their
    capital and lose their "video game" ("social deduction video game" -> "Social deduction")."""
    name = clean_title(name)
    short = _VIDEO_GAME.sub("", name)
    name = short or name
    return name[:1].upper() + name[1:] if name[:1].islower() else name
