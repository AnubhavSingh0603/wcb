"""Database backend (SQLite by default, Postgres optional).

This project is designed to run out-of-the-box with SQLite (aiosqlite).
For Postgres, set DB_DIALECT=postgres and provide DATABASE_URL.

All cogs should use the helper methods on `bot.dbx` (database adapter),
and the `bot.db_lock` to serialize writes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from word_counter_dsc.config import DB_DIALECT, DB_PATH, DATABASE_URL


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS word_counts (
    guild_id   INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    word       TEXT    NOT NULL,
    count      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, channel_id, user_id, word)
);

CREATE TABLE IF NOT EXISTS keywords (
    guild_id   INTEGER NOT NULL,
    keyword    TEXT    NOT NULL,
    created_at INTEGER NOT NULL,
    removed_at INTEGER,
    PRIMARY KEY (guild_id, keyword)
);

CREATE TABLE IF NOT EXISTS stopwords (
    guild_id   INTEGER NOT NULL,
    word       TEXT    NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS keyword_medals (
    guild_id   INTEGER NOT NULL,
    keyword    TEXT    NOT NULL,
    user_id    INTEGER NOT NULL,
    best_tier  INTEGER NOT NULL DEFAULT 0,
    awarded_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, keyword, user_id)
);

CREATE TABLE IF NOT EXISTS keyword_removals (
    guild_id   INTEGER NOT NULL,
    keyword    TEXT    NOT NULL,
    removed_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_word_guild_word ON word_counts(guild_id, word);
CREATE INDEX IF NOT EXISTS idx_word_guild_channel_word ON word_counts(guild_id, channel_id, word);
CREATE INDEX IF NOT EXISTS idx_word_guild_user_word ON word_counts(guild_id, user_id, word);
CREATE INDEX IF NOT EXISTS idx_kw_guild ON keywords(guild_id);
CREATE INDEX IF NOT EXISTS idx_medals_guild_keyword ON keyword_medals(guild_id, keyword);
"""


SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS word_counts (
    guild_id   BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    user_id    BIGINT NOT NULL,
    word       TEXT   NOT NULL,
    count      BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, channel_id, user_id, word)
);

CREATE TABLE IF NOT EXISTS keywords (
    guild_id   BIGINT NOT NULL,
    keyword    TEXT   NOT NULL,
    created_at BIGINT NOT NULL,
    removed_at BIGINT,
    PRIMARY KEY (guild_id, keyword)
);

CREATE TABLE IF NOT EXISTS stopwords (
    guild_id   BIGINT NOT NULL,
    word       TEXT   NOT NULL,
    created_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS keyword_medals (
    guild_id   BIGINT NOT NULL,
    keyword    TEXT   NOT NULL,
    user_id    BIGINT NOT NULL,
    best_tier  INT    NOT NULL DEFAULT 0,
    awarded_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, keyword, user_id)
);

CREATE TABLE IF NOT EXISTS keyword_removals (
    guild_id   BIGINT NOT NULL,
    keyword    TEXT   NOT NULL,
    removed_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_word_guild_word ON word_counts(guild_id, word);
CREATE INDEX IF NOT EXISTS idx_word_guild_channel_word ON word_counts(guild_id, channel_id, word);
CREATE INDEX IF NOT EXISTS idx_word_guild_user_word ON word_counts(guild_id, user_id, word);
CREATE INDEX IF NOT EXISTS idx_kw_guild ON keywords(guild_id);
CREATE INDEX IF NOT EXISTS idx_medals_guild_keyword ON keyword_medals(guild_id, keyword);
"""


class DBX:
    """Small adapter to hide placeholder differences."""

    async def close(self) -> None:
        raise NotImplementedError

    async def executescript(self, script: str) -> None:
        raise NotImplementedError

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> Any:
        raise NotImplementedError

    async def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[tuple]:
        raise NotImplementedError

    async def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[tuple]:
        raise NotImplementedError

    async def commit(self) -> None:
        raise NotImplementedError


@dataclass
class SQLiteDBX(DBX):
    conn: Any

    async def close(self) -> None:
        await self.conn.close()

    async def executescript(self, script: str) -> None:
        await self.conn.executescript(script)

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> Any:
        return await self.conn.execute(sql, tuple(params))

    async def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[tuple]:
        cur = await self.conn.execute(sql, tuple(params))
        return await cur.fetchone()

    async def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[tuple]:
        cur = await self.conn.execute(sql, tuple(params))
        return await cur.fetchall()

    async def commit(self) -> None:
        await self.conn.commit()


@dataclass
class PostgresDBX(DBX):
    pool: Any

    async def close(self) -> None:
        await self.pool.close()

    async def executescript(self, script: str) -> None:
        # simple split on semicolon for schema (safe enough for our schema)
        stmts = [s.strip() for s in script.split(";") if s.strip()]
        async with self.pool.acquire() as conn:
            for s in stmts:
                await conn.execute(s)

    def _pg(self, sql: str) -> str:
        # Convert SQLite '?' placeholders to Postgres '$1, $2, ...'
        out = []
        idx = 1
        for ch in sql:
            if ch == "?":
                out.append(f"${idx}")
                idx += 1
            else:
                out.append(ch)
        return "".join(out)

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> Any:
        sql = self._pg(sql)
        async with self.pool.acquire() as conn:
            return await conn.execute(sql, *list(params))

    async def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[tuple]:
        sql = self._pg(sql)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql, *list(params))
            return tuple(row) if row is not None else None

    async def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[tuple]:
        sql = self._pg(sql)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *list(params))
            return [tuple(r) for r in rows]

    async def commit(self) -> None:
        # autocommit is typical for asyncpg execute/fetch calls
        return None


async def init_db(bot) -> None:
    """Initialize `bot.dbx` + schema + lock."""
    if getattr(bot, "db_lock", None) is None:
        bot.db_lock = asyncio.Lock()

    if DB_DIALECT == "postgres":
        try:
            import asyncpg  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Postgres backend requested but asyncpg is not installed. "
                "Install with: pip install asyncpg"
            ) from e

        if not DATABASE_URL:
            raise RuntimeError("DB_DIALECT=postgres set but DATABASE_URL is empty")

        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        bot.dbx = PostgresDBX(pool=pool)
        async with bot.db_lock:
            await bot.dbx.executescript(SCHEMA_POSTGRES)
        return

    # default: sqlite
    import aiosqlite

    conn = await aiosqlite.connect(DB_PATH)
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA synchronous=NORMAL;")
    bot.dbx = SQLiteDBX(conn=conn)
    async with bot.db_lock:
        await bot.dbx.executescript(SCHEMA_SQLITE)
        await bot.dbx.commit()


async def close_db(bot) -> None:
    """Close the database connection/pool if it exists.

    Note: aiosqlite uses a background worker thread. On Windows,
    leaving a connection open can keep the process alive, making
    subprocess-based smoke tests appear to "hang".
    """
    dbx = getattr(bot, "dbx", None)
    if dbx is None:
        return
    try:
        await dbx.close()
    except Exception:
        pass
    finally:
        bot.dbx = None
