import os
import re
from collections import Counter
from typing import Iterable

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


def user_link_no_ping(user_id: int) -> str:
    """
    Clickable user reference without notifications.
    This renders as the per-server display name in clients, and stays clickable.
    """
    return f"<@{int(user_id)}>"


def chunk_list(items: Iterable, size: int):
    size = max(1, int(size))
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i : i + size]
