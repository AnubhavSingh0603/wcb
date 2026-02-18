import os

# ------------------------
# Logging
# ------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ------------------------
# Discord Token
# ------------------------
# Primary expected key on Render:
#   DISCORD_TOKEN
# Backward compatible fallbacks:
#   BOT_TOKEN, DISCORD_BOT_TOKEN, TOKEN
BOT_TOKEN = (
    os.getenv("DISCORD_TOKEN", "")
    or os.getenv("BOT_TOKEN", "")
    or os.getenv("DISCORD_BOT_TOKEN", "")
    or os.getenv("TOKEN", "")
)

# ------------------------
# Counting mode
# ------------------------
# UNIQUE: count a word at most once per message
# ALL: count repeated occurrences within the same message
COUNT_MODE = os.getenv("COUNT_MODE", "UNIQUE").upper()
if COUNT_MODE not in ("UNIQUE", "ALL"):
    COUNT_MODE = "UNIQUE"

# ------------------------
# Database
# ------------------------
# sqlite (local) or postgres (hosted)
DB_DIALECT = os.getenv("DB_DIALECT", "sqlite").lower()

# sqlite path
DB_PATH = os.getenv("DB_PATH", "word_counts.db")

# postgres url (Render/Neon/etc)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ------------------------
# Backfill controls
# ------------------------
AUTO_BACKFILL_ENABLED = os.getenv("AUTO_BACKFILL_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")
BACKFILL_LIMIT_PER_CHANNEL = int(os.getenv("BACKFILL_LIMIT_PER_CHANNEL", "200"))

# ------------------------
# Intents warning
# ------------------------
REQUIRE_MESSAGE_CONTENT_INTENT = True

# ------------------------
# Search defaults
# ------------------------
DEFAULT_TOP_N = int(os.getenv("DEFAULT_TOP_N", "10"))

# ------------------------
# Keyword removal grace (seconds)
# ------------------------
# When a keyword is removed, we keep its medal table entry for a short while
# so queries don't flicker while moderators are editing the list.
KEYWORD_REMOVAL_GRACE_SECONDS = int(os.getenv("KEYWORD_REMOVAL_GRACE_SECONDS", str(7 * 24 * 3600)))  # 7 days

# ------------------------
# Extensions
# ------------------------
EXTENSIONS = [
    "word_counter_dsc.cogs.tracker",
    "word_counter_dsc.cogs.search",
    "word_counter_dsc.cogs.keyword",
    "word_counter_dsc.cogs.stopwords",
    "word_counter_dsc.cogs.help_cmd",
    "word_counter_dsc.cogs.medals",
    "word_counter_dsc.cogs.profile",
]

# ------------------------
# Medal thresholds (keyword game)
# ------------------------
# (min_count, tier_number, rank_name)
# rank_name is the *rank* (Squire/Baron/etc). The final displayed title is
# generated from rank + keyword (e.g., "🏰 The Baron of Fuck").
MEDAL_THRESHOLDS = [
    (10,   1, "Novice"),
    (25,   2, "Squire"),
    (50,   3, "Knight"),
    (100,  4, "Baron"),
    (250,  5, "Count"),
    (500,  6, "Duke"),
    (1000, 7, "Prince"),
    (2500, 8, "King"),
    (5000, 9, "Emperor"),
]

# Emoji per rank (used in /profile + medal unlock messages)
MEDAL_EMOJIS = {
    "novice": "📜",
    "squire": "✨",
    "knight": "🛡️",
    "baron": "🏰",
    "count": "📯",
    "duke": "⚔️",
    "prince": "👑",
    "king": "👑",
    "emperor": "👑",
}
