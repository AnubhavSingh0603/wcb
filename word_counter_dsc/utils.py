import os
import re
from collections import Counter

WORD_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)

# Built-in stopwords (applied at ingest time)
BUILTIN_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "then",
    "else",
    "is",
    "am",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "to",
    "of",
    "in",
    "on",
    "at",
    "for",
    "from",
    "with",
    "as",
    "i",
    "me",
    "my",
    "we",
    "us",
    "our",
    "you",
    "your",
    "he",
    "him",
    "she",
    "her",
    "they",
    "them",
    "their",
    "it",
    "its",
    "this",
    "that",
    "these",
    "those",
    "not",
    "no",
    "yes",
    "do",
    "does",
    "did",
    "doing",
    "have",
    "has",
    "had",
    "having",
    "so",
    "too",
    "very",
    "just",
    "hi",
    "hello",
}


def clear_terminal() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text or "")]


def counter_from_mode(words_all: list[str], mode: str) -> Counter:
    mode = (mode or "UNIQUE").upper()
    if mode == "ALL":
        return Counter(words_all)
    # UNIQUE: count each word once per message
    return Counter(set(words_all))


def chunk_list(items, size: int):
    size = max(1, int(size))
    for i in range(0, len(items), size):
        yield items[i : i + size]
