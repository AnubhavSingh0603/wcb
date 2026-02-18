import os
import re
import hashlib
from collections import Counter
from typing import Iterable

from word_counter_dsc.config import MEDAL_THRESHOLDS, MEDAL_EMOJIS

# Token regex:
# - Keeps apostrophes inside tokens (don't -> don't)
# - Hyphens split into separate tokens (abso-fucking-lutely -> abso, fucking, lutely)
WORD_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)

# Built-in stopwords (applied at ingest time).
# This is intentionally "chat heavy": common filler words, aux verbs, pronouns,
# and frequent abbreviations that are usually not meaningful for profiles/stats.
BUILTIN_STOPWORDS = {
    # articles / conjunctions / prepositions
    "a","an","the","and","or","but","if","then","else","so","because","tho","though","while","when","whenever","where","wherever",
    "of","in","on","at","to","from","for","with","as","by","into","onto","over","under","about","around","between","within","without",
    # pronouns
    "i","me","my","mine","we","us","our","ours","you","your","yours","u","ur","urs",
    "he","him","his","she","her","hers","they","them","their","theirs","it","its",
    "this","that","these","those","there","here",
    # aux / common verbs
    "is","am","are","was","were","be","been","being",
    "do","does","did","doing","done",
    "have","has","had","having",
    "can","cant","cannot","could","couldnt",
    "will","wont","would","wouldnt",
    "shall","should","shouldnt",
    "may","might","must",
    "im","ive","ill","id","youre","were","theyre","isnt","arent","wasnt","werent",
    # negations / misc
    "not","no","yes","nah","yep","nope",
    "ok","okay","kk","k","alright","sure",
    "lol","lmao","rofl","lmfao","xd",
    "brb","afk","idk","ik","tbh","imo","imho","ngl","fr","rn","btw","atm","fyi","irl",
    "pls","plz","please","thx","thanks","ty","np",
    "hi","hello","hey","yo","sup",
    # filler / frequent chat words
    "like","just","very","really","literally","basically","actually","maybe","probably","kinda","sorta",
    "gonna","wanna","gotta","lemme","gimme",
    "go","goes","went","going",
    "get","gets","got","getting",
    "say","says","said","saying",
    "make","makes","made","making",
    "right","left","yeah","yup","hmm","hahaha","haha","hehe",
    # common short tokens / noise
    "rt","gt","dm","pm","msg","msgd",
}

# ------------------------
# General utilities
# ------------------------
def clear_terminal() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def tokenize(text: str) -> list[str]:
    """Tokenize message content into lowercase word-like tokens."""
    return [m.group(0).lower() for m in WORD_RE.finditer(text or "")]


def parse_word_list(text: str) -> list[str]:
    """
    Parse a user-provided input like:
      "a, b c\nd"
    into normalized tokens. We reuse tokenize() so commas/extra punctuation are fine.
    """
    toks = tokenize(text or "")
    # de-dup while preserving order
    seen = set()
    out = []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def counter_from_mode(words_all: list[str], mode: str) -> Counter:
    mode = (mode or "UNIQUE").upper()
    if mode == "ALL":
        return Counter(words_all)
    # UNIQUE: count each word once per message
    return Counter(set(words_all))


# ------------------------
# Keyword matching
# ------------------------
def _condense_token(tok: str) -> str:
    """Remove non-letters so mother-fucker -> motherfucker and f.u.c.k -> fuck."""
    return re.sub(r"[^a-z]", "", (tok or "").lower())


def count_keyword_hits(text: str, keyword: str, *, abbrev_to_keyword: dict[str, str] | None = None) -> int:
    """
    Count occurrences of a keyword in a message in a permissive, chat-friendly way:
      - counts plurals/verbs and in-word use (motherfucker, fucking, fuckin, fucks, etc.)
      - counts hyphenated and punctuated forms (abso-fucking-lutely, f.u.c.k)
      - supports abbreviation mapping: if a token equals an abbreviation that maps to this keyword,
        it counts as a hit (e.g., wtf -> fuck).

    NOTE: This function returns "raw hits" (for COUNT_MODE=ALL). UNIQUE mode should clamp to 0/1.
    """
    kw = (keyword or "").lower().strip()
    if not kw:
        return 0

    abbrev_to_keyword = abbrev_to_keyword or {}
    tokens = tokenize(text or "")
    hits = 0

    for t in tokens:
        # Abbreviation direct hit
        mapped = abbrev_to_keyword.get(t)
        if mapped == kw:
            hits += 1
            continue

        ct = _condense_token(t)
        if not ct:
            continue

        # To avoid silly false positives on tiny keywords, require exact for <=3
        if len(kw) <= 3:
            if ct == kw:
                hits += 1
        else:
            # substring match covers plurals/verbs/in-word use
            if kw in ct:
                hits += 1

    return hits


# ------------------------
# Non-pinging clickable mentions
# ------------------------
def user_link_no_ping(user_id: int) -> str:
    """
    Clickable user reference. To make this truly "no ping", always send the message with:
        allowed_mentions=discord.AllowedMentions.none()
    """
    return f"<@{int(user_id)}>"


# ------------------------
# Medal / game helpers
# ------------------------
_RANK_TEMPLATES: dict[str, list[str]] = {
    "novice": [
        "The Novice of {KW}",
        "A Newly-Sworn Page of {KW}",
        "The {KW} Scrollbearer of the Court",
    ],
    "squire": [
        "The Squire of {KW}",
        "Squire of the {KW} Banner, Keeper of Oaths and Ink",
        "The {KW} Squire Who Never Misses a Beat",
    ],
    "knight": [
        "The Knight of {KW}",
        "Knight-Errant of {KW}, Defender of the Realm’s Vibes",
        "The {KW} Knight of the Silver Tongue",
    ],
    "baron": [
        "The Baron of {KW}",
        "Baron of {KW}, Lord of Late-Night Declarations and Bold Claims",
        "The {KW} Baron Who Rules the Chatlands with Gilded Chaos",
    ],
    "count": [
        "The Count of {KW}",
        "Count of {KW}, Master of Tallies and Midnight Mischief",
        "The {KW} Count Who Commands the Ledger of Legends",
    ],
    "duke": [
        "The Duke of {KW}",
        "Duke of {KW}, High Marshal of Memes and Mayhem",
        "The {KW} Duke, Warden of the Wildest Wordcraft",
    ],
    "prince": [
        "The Prince of {KW}",
        "Prince of {KW}, Heir to the Court’s Most Dangerous Vocabulary",
        "The {KW} Prince Who Walks Among Legends",
    ],
    "king": [
        "The King of {KW}",
        "King of {KW}, Sovereign of Speech and Slayer of Silence",
        "The {KW} King, Crowned by Pure Unhinged Eloquence",
    ],
    "emperor": [
        "The Emperor of {KW}",
        "Emperor of {KW}, Supreme Ruler of Rhetoric and Relentless Style",
        "The {KW} Emperor, Eternal Master of the Realm’s Word-Forge",
    ],
}


def medal_rank_for_count(total: int) -> tuple[int, str, int | None]:
    """
    Returns: (tier_number, rank_name, next_threshold or None)
    tier_number is 0 if below the first threshold.
    """
    total = int(total or 0)
    thresholds = sorted(MEDAL_THRESHOLDS, key=lambda x: int(x[0]))
    current_tier = 0
    current_rank = "Unranked"
    next_thr = thresholds[0][0] if thresholds else None

    for thr, tier, rank in thresholds:
        if total >= int(thr):
            current_tier = int(tier)
            current_rank = str(rank)
        else:
            next_thr = int(thr)
            break
    else:
        next_thr = None

    return current_tier, current_rank, next_thr


def medal_emoji(rank_name: str) -> str:
    return MEDAL_EMOJIS.get((rank_name or "").lower(), "🏅")


def medal_title(rank_name: str, keyword: str) -> str:
    """Deterministically pick a quirky title for (rank, keyword)."""
    rank_key = (rank_name or "").lower()
    kw = (keyword or "").strip()
    kw_cap = kw[:1].upper() + kw[1:] if kw else "Keyword"

    templates = _RANK_TEMPLATES.get(rank_key) or [f"The {rank_name} of {{KW}}"]
    # deterministic index by hash so titles are stable across restarts/deploys
    h = hashlib.sha1(f"{rank_key}|{kw.lower()}".encode("utf-8")).hexdigest()
    idx = int(h[:8], 16) % len(templates)
    return templates[idx].format(KW=kw_cap)


def medal_progress_text(total: int, next_threshold: int | None) -> str:
    total = int(total or 0)
    if not next_threshold:
        return f"**{total:,}** (MAX)"
    return f"**{total:,}/{int(next_threshold):,}**"


def chunk_list(items: Iterable, size: int):
    size = max(1, int(size))
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i : i + size]
