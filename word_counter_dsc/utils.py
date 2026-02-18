from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Tuple

ZWSP = "\u200b"

_WORD_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)

def normalize_text(s: str) -> str:
    return (s or "").lower()

def tokenize(s: str) -> List[str]:
    """Tokenize to simple lowercase word-ish tokens."""
    s = normalize_text(s)
    return _WORD_RE.findall(s)

def split_csv_words(s: str) -> List[str]:
    """Split a user input string into words: supports commas/newlines/spaces."""
    if not s:
        return []
    # allow: "a, b  c\n d"
    parts = re.split(r"[\s,]+", s.strip())
    out = []
    for p in parts:
        p = p.strip().lower()
        if p:
            out.append(p)
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
    """Count occurrences of keyword variants in a raw message."""
    if not message or not keyword:
        return 0
    rx = build_keyword_regex(keyword, aliases=aliases)
    return sum(1 for _ in rx.finditer(message))

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
