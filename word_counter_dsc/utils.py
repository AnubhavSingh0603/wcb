from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Tuple

ZWSP = "\u200b"

import unicodedata

# Token pattern: Latin letters/digits with optional apostrophes, plus Devanagari letters.
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*|[\u0900-\u097F]+", re.UNICODE)

# Matches common English contractions that should collapse to the base word.
# Examples: they'd -> they, he'll -> he, it's -> it, can't -> can (handles n't as 't')
_CONTRACTION_RE = re.compile(r"^([a-z]+)(?:'(?:d|ll|ve|re|m|s|t))$", re.IGNORECASE)

def normalize_text(s: str) -> str:
    return (s or "").strip()

def normalize_word(w: str) -> str:
    """Normalize a token for counting/searching.

    - Unicode normalize (NFKC) + convert curly apostrophes to ASCII '
    - Case-fold (LOVE/Love/LoVe -> love)
    - Strip surrounding punctuation/symbols
    - Collapse common contractions to the base word (they'd -> they)
    """
    if not w:
        return ""
    w = unicodedata.normalize("NFKC", w)
    w = w.replace("’", "'").replace("‘", "'")
    w = w.casefold()

    # strip leading/trailing non-word chars (keep apostrophes inside)
    w = re.sub(r"^[^\w\u0900-\u097F']+|[^\w\u0900-\u097F']+$", "", w)

    # collapse contractions (latin)
    m = _CONTRACTION_RE.match(w)
    if m:
        base = m.group(1)
        # special-case n't -> base already captured (can, don, isn) which is fine; these are stopwords anyway
        w = base

    return w

def tokenize(s: str) -> List[str]:
    """Tokenize to normalized tokens (case-insensitive, punctuation-tolerant)."""
    s = normalize_text(s)
    if not s:
        return []
    s = unicodedata.normalize("NFKC", s).replace("’", "'").replace("‘", "'")
    raw = _TOKEN_RE.findall(s)
    out: List[str] = []
    for t in raw:
        nt = normalize_word(t)
        if nt:
            out.append(nt)
    return out
def split_csv_words(s: str) -> List[str]:
    """Split a user input string into normalized words (comma/space/newline separated)."""
    if not s:
        return []
    parts = re.split(r"[\s,]+", (s or "").strip())
    out: List[str] = []
    for p in parts:
        w = normalize_word(p)
        if w:
            out.append(w)
    return out

def keyword_display(keyword: str) -> str:
    """Pretty keyword for UI."""
    if not keyword:
        return ""
    # Title-case but keep common acronyms readable
    if keyword.isupper():
        return keyword
    return keyword[:1].upper() + keyword[1:].lower()

def build_keyword_regex(keyword: str, aliases: Sequence[str] | None = None) -> re.Pattern:
    """
    Build a regex to match:
      - keyword at token boundary (non-alnum before)
      - then optional letters (for simple suffixes: plural/verb forms)
      - stop on non-letter
    This catches:
      'fuck', 'fucks', 'fucking', 'abso-fucking-lutely'
    But tries to avoid matching inside other words like 'pass' for 'ass'
    by requiring a non-alnum boundary before the root.
    """
    kw = re.escape(keyword.lower())
    alts = [kw]
    if aliases:
        for a in aliases:
            a = a.strip().lower()
            if a:
                alts.append(re.escape(a))
    group = "(?:" + "|".join(sorted(set(alts), key=len, reverse=True)) + ")"
    # boundary before: not a letter/digit
    # after: allow letters for inflections, then require next char not a letter
    pat = rf"(?<![a-z0-9]){group}[a-z]*"
    return re.compile(pat, re.IGNORECASE)

def count_keyword_occurrences(message: str, keyword: str, aliases: Sequence[str] | None = None) -> int:
    """Count occurrences of keyword variants in a message.

    Uses normalized token stream so counts are case-insensitive and punctuation-tolerant.
    """
    if not message or not keyword:
        return 0

    # Normalize message into tokens, then join with spaces to make boundary matching consistent.
    norm_text = " ".join(tokenize(message))
    if not norm_text:
        return 0

    kw = normalize_word(keyword)
    alias_norm = [normalize_word(a) for a in (aliases or []) if normalize_word(a)]
    rx = build_keyword_regex(kw, aliases=alias_norm)
    return sum(1 for _ in rx.finditer(norm_text))

def user_mention(user_id: int) -> str:
    """Return a mention string. Use AllowedMentions.none() when sending to avoid pings."""
    return f"<@{int(user_id)}>"

def safe_allowed_mentions():
    import discord
    return discord.AllowedMentions.none()

def progress_bar(curr: int, target: int, width: int = 12) -> str:
    if target <= 0:
        return "█" * width
    curr = max(0, min(curr, target))
    filled = int(round(width * (curr / target)))
    filled = min(width, max(0, filled))
    return "█" * filled + "░" * (width - filled)
