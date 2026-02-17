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
# Backfill controls
# ------------------------
AUTO_BACKFILL_ENABLED = os.getenv("AUTO_BACKFILL_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")
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
# Medal thresholds: (min_count, tier_number, tier_title)
MEDAL_THRESHOLDS = [
    (25, 1, "Squire"),
    (100, 2, "Baron"),
    (250, 3, "Count"),
    (500, 4, "Duke"),
    (1000, 5, "Prince"),
]
