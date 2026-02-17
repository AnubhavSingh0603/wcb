import asyncio
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import aiosqlite

try:
    import asyncpg  # type: ignore
except Exception:  # pragma: no cover
    asyncpg = None

from word_counter_dsc.config import DB_DIALECT, DB_PATH, DATABASE_URL

log = logging.getLogger("word_counter_dsc")


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

CREATE TABLE IF NOT EXISTS keyword_removals (
    guild_id   INTEGER NOT NULL,
    keyword    TEXT    NOT NULL,
    removed_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, keyword)
);

CREATE TABLE IF NOT EXISTS stopwords (
    guild_id   INTEGER NOT NULL,
    word       TEXT    NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS keyword_abbreviations (
    guild_id   INTEGER NOT NULL,
    abbr       TEXT    NOT NULL,
    keyword    TEXT    NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, abbr)
);

CREATE TABLE IF NOT EXISTS keyword_medals (
    guild_id    INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    keyword     TEXT    NOT NULL,
    tier        INTEGER NOT NULL,
    total_count INTEGER NOT NULL,
    awarded_at  INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_wc_guild_word ON word_counts(guild_id, word);
CREATE INDEX IF NOT EXISTS idx_wc_guild_user ON word_counts(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_kw_guild ON keywords(guild_id);
CREATE INDEX IF NOT EXISTS idx_abbr_guild ON keyword_abbreviations(guild_id);
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

CREATE TABLE IF NOT EXISTS keyword_removals (
    guild_id   BIGINT NOT NULL,
    keyword    TEXT   NOT NULL,
    removed_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, keyword)
);

CREATE TABLE IF NOT EXISTS stopwords (
    guild_id   BIGINT NOT NULL,
    word       TEXT   NOT NULL,
    created_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS keyword_abbreviations (
    guild_id   BIGINT NOT NULL,
    abbr       TEXT    NOT NULL,
    keyword    TEXT    NOT NULL,
    created_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, abbr)
);

CREATE TABLE IF NOT EXISTS keyword_medals (
    guild_id    BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    keyword     TEXT   NOT NULL,
    tier        BIGINT NOT NULL,
    total_count BIGINT NOT NULL,
    awarded_at  BIGINT NOT NULL,
    PRIMARY KEY (guild_id, user_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_wc_guild_word ON word_counts(guild_id, word);
CREATE INDEX IF NOT EXISTS idx_wc_guild_user ON word_counts(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_kw_guild ON keywords(guild_id);
CREATE INDEX IF NOT EXISTS idx_abbr_guild ON keyword_abbreviations(guild_id);
"""


def _now() -> int:
    return int(time.time())


@dataclass
class DBX:
    dialect: str

    async def connect(self):
        raise NotImplementedError

    async def close(self):
        raise NotImplementedError

    async def execute(self, sql: str, params: Iterable[Any] = ()):
        raise NotImplementedError

    async def fetchone(self, sql: str, params: Iterable[Any] = ()):
        raise NotImplementedError

    async def fetchall(self, sql: str, params: Iterable[Any] = ()):
        raise NotImplementedError

    async def commit(self):
        raise NotImplementedError


class SQLiteDBX(DBX):
    def __init__(self, path: str):
        super().__init__("sqlite")
        self.path = path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("PRAGMA synchronous=NORMAL;")
        await self.conn.execute("PRAGMA foreign_keys=ON;")
        await self.conn.commit()

    async def close(self):
        if self.conn is not None:
            await self.conn.close()

    async def execute(self, sql: str, params: Iterable[Any] = ()):
        assert self.conn is not None
        return await self.conn.execute(sql, list(params))

    async def fetchone(self, sql: str, params: Iterable[Any] = ()):
        assert self.conn is not None
        cur = await self.conn.execute(sql, list(params))
        return await cur.fetchone()

    async def fetchall(self, sql: str, params: Iterable[Any] = ()):
        assert self.conn is not None
        cur = await self.conn.execute(sql, list(params))
        return await cur.fetchall()

    async def commit(self):
        assert self.conn is not None
        await self.conn.commit()


class PostgresDBX(DBX):
    def __init__(self, url: str):
        super().__init__("postgres")
        self.url = url
        self.pool: Any = None

    async def connect(self):
        if asyncpg is None:
            raise RuntimeError("asyncpg is not installed but postgres dialect was requested.")
        self.pool = await asyncpg.create_pool(self.url, min_size=1, max_size=5)

    async def close(self):
        if self.pool is not None:
            await self.pool.close()

    def _q(self, sql: str) -> str:
        # convert "?" placeholders to $1 $2 ...
        out = []
        i = 1
        for ch in sql:
            if ch == "?":
                out.append(f"${i}")
                i += 1
            else:
                out.append(ch)
        return "".join(out)

    async def execute(self, sql: str, params: Iterable[Any] = ()):
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await conn.execute(self._q(sql), *list(params))

    async def fetchone(self, sql: str, params: Iterable[Any] = ()):
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(self._q(sql), *list(params))

    async def fetchall(self, sql: str, params: Iterable[Any] = ()):
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(self._q(sql), *list(params))
            # normalize to tuples so rest of code can treat sqlite/pg similarly
            return [tuple(r) for r in rows]

    async def commit(self):
        # asyncpg auto-commits each statement unless you use explicit transactions
        return


async def init_db() -> DBX:
    if DB_DIALECT == "postgres":
        dbx = PostgresDBX(DATABASE_URL)
        await dbx.connect()
        # create schema
        for stmt in [s.strip() for s in SCHEMA_POSTGRES.split(";") if s.strip()]:
            await dbx.execute(stmt)
        return dbx

    # default sqlite
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    dbx = SQLiteDBX(DB_PATH)
    await dbx.connect()
    for stmt in [s.strip() for s in SCHEMA_SQLITE.split(";") if s.strip()]:
        await dbx.execute(stmt)
    await dbx.commit()
    return dbx
