import os

# -----------------------------
# Storage backend
# -----------------------------
# Default is SQLite (aiosqlite). For Postgres, set:
#   DB_DIALECT=postgres
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname
DB_DIALECT = os.getenv("DB_DIALECT", "sqlite").strip().lower()
DB_PATH = os.getenv("DB_PATH", "word_counts.db").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# -----------------------------
# Counting mode
# -----------------------------
# UNIQUE => each word counts at most once per message
# ALL    => every occurrence counts
COUNT_MODE = os.getenv("COUNT_MODE", "UNIQUE").strip().upper()

# -----------------------------
# Auto-backfill
# -----------------------------
AUTO_BACKFILL_ENABLED = os.getenv("AUTO_BACKFILL_ENABLED", "0") == "1"  # default off on hosted deployments
BACKFILL_LIMIT_PER_CHANNEL = int(os.getenv("BACKFILL_LIMIT_PER_CHANNEL", "2000"))

# -----------------------------
# Keyword removal grace (seconds)
# -----------------------------
KEYWORD_REMOVAL_GRACE_SECONDS = int(
    os.getenv("KEYWORD_REMOVAL_GRACE_SECONDS", str(7 * 24 * 3600))
)

# -----------------------------
# Medal thresholds
# -----------------------------
MEDAL_THRESHOLDS = [
    (50, 1, "Squire"),
    (100, 2, "Knight"),
    (500, 3, "Baron"),
    (1000, 4, "Duke"),
    (5000, 5, "Archduke"),
    (10000, 6, "Sovereign"),
]

DEFAULT_TOP_N = int(os.getenv("DEFAULT_TOP_N", "10"))
