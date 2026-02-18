from __future__ import annotations

import re
from typing import List, Tuple


WORD_RE = re.compile(r"[A-Za-z0-9']+")


def tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [m.group(0).lower() for m in WORD_RE.finditer(text)]


def user_mention(user_id: int, display_name: str | None = None) -> str:
    """Clickable profile link without pinging the user."""
    name = (display_name or f"User {user_id}").replace("[", "(").replace("]", ")")
    return f"[{name}](https://discord.com/users/{user_id})"


# ---------------- Medal helpers ----------------

# Rank names are used by medals/game
RANKS = [
    "Peasant",
    "Squire",
    "Baron",
    "Viscount",
    "Count",
    "Marquess",
    "Duke",
    "Prince",
    "King",
    "Emperor",
]


def medal_rank_for_count(total: int, thresholds: List[Tuple[int, int, str]]) -> Tuple[int, str]:
    """
    thresholds: list of (count_threshold, tier, rank_name)
    returns: (tier, rank_name)
    """
    best_tier = 0
    best_rank = ""
    for threshold, tier, rank in thresholds:
        if total >= threshold and tier > best_tier:
            best_tier = tier
            best_rank = rank
    return best_tier, best_rank


def medal_emoji(rank: str) -> str:
    # Simple mapping; you can expand later
    mapping = {
        "Peasant": "🥔",
        "Squire": "🛡️",
        "Baron": "🏰",
        "Viscount": "⚔️",
        "Count": "🦁",
        "Marquess": "👑",
        "Duke": "🐉",
        "Prince": "✨",
        "King": "👑",
        "Emperor": "🌟",
    }
    return mapping.get(rank, "🏅")


def medal_title(word: str, rank: str) -> str:
    # Keep it “The <rank> of <Word>”
    w = (word or "").strip()
    w = w[:1].upper() + w[1:] if w else word
    return f"The {rank} of {w}"


def medal_progress_text(total: int, thresholds: List[Tuple[int, int, str]]) -> str:
    # Find next threshold after total
    next_thr = None
    for thr, tier, rank in sorted(thresholds, key=lambda x: x[0]):
        if thr > total:
            next_thr = thr
            break
    if next_thr is None:
        return f"{total}/∞"
    return f"{total}/{next_thr}"
