# word_counter_dsc/utils.py
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Union

import discord

# Word-ish token: letters/digits with internal ' or - allowed.
# Example: "abso-fucking-lutely" stays as one token, "don't" stays together.
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")

def tokenize(text: str) -> List[str]:
    """
    Tokenize message content into lowercased tokens.
    Keeps hyphenated/contracted words as single tokens.
    """
    if not text:
        return []
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


def normalize_kw(s: str) -> str:
    return (s or "").strip().lower()


def user_mention(
    user: Union[int, discord.abc.User, discord.Member],
    *,
    display_name: Optional[str] = None,
) -> str:
    """
    Return a CLICKABLE user reference that does NOT ping/tag.
    Uses a profile link rather than <@id>.
    """
    if isinstance(user, int):
        uid = user
        name = display_name or f"User {uid}"
    else:
        uid = user.id
        # prefer server nickname/display name when available
        name = display_name or getattr(user, "display_name", None) or user.name

    # Clickable profile link without ping
    # Discord renders this as a normal link, not a mention.
    safe_name = str(name).replace("[", "\\[").replace("]", "\\]")
    return f"[{safe_name}](https://discord.com/users/{uid})"


def make_progress_bar(current: int, target: int, width: int = 12) -> str:
    """
    Text progress bar like: ███████░░░░░ 324/500
    """
    if target <= 0:
        return f"{current}/{target}"
    current = max(0, current)
    ratio = min(1.0, current / target)
    filled = int(round(ratio * width))
    return f"{'█' * filled}{'░' * (width - filled)} {current}/{target}"
