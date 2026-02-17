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

# postgres url
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ------------------------
# Defaults used by cogs
# ------------------------
DEFAULT_TOP_N = int(os.getenv("DEFAULT_TOP_N", "10"))

# When a keyword is removed, keep medal rows for a short grace window before cleanup
KEYWORD_REMOVAL_GRACE_SECONDS = int(os.getenv("KEYWORD_REMOVAL_GRACE_SECONDS", "600"))

# ------------------------
# Backfill controls
# ------------------------
AUTO_BACKFILL_ENABLED = os.getenv("AUTO_BACKFILL_ENABLED", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
BACKFILL_LIMIT_PER_CHANNEL = int(os.getenv("BACKFILL_LIMIT_PER_CHANNEL", "200"))

# ------------------------
# Intents warning
# ------------------------
REQUIRE_MESSAGE_CONTENT_INTENT = True

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
# Medals (Knight / Nobility theme)
# ------------------------
# Medal thresholds: (min_count, tier_number, tier_title)
# NOTE: The *display* name shown to users is "The {tier_title} of <keyword>"
MEDAL_THRESHOLDS = [
    (10, 1, "Page"),
    (25, 2, "Squire"),
    (50, 3, "Knight"),
    (100, 4, "Baron"),
    (250, 5, "Count"),
    (500, 6, "Duke"),
    (1000, 7, "Prince"),
    (2500, 8, "King"),
    (5000, 9, "Emperor"),
]

# Emoji per tier (shown in medals + profile)
# Keyed by tier_title lowercase
MEDAL_EMOJIS = {
    "page": "📜",
    "squire": "🪶",
    "knight": "🛡️",
    "baron": "🏰",
    "count": "📯",
    "duke": "👑",
    "prince": "⚔️",
    "king": "🦁",
    "emperor": "🜲",
}
