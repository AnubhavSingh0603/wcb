from __future__ import annotations

import os
from collections.abc import Iterable as IterABC
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import aiosqlite

try:
    import asyncpg  # type: ignore
except Exception:  # pragma: no cover
    asyncpg = None  # type: ignore


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS word_counts (
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, channel_id, user_id, word)
);

CREATE TABLE IF NOT EXISTS keywords (
    guild_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS stopwords (
    guild_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS keyword_removals (
    guild_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    removed_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, word, removed_at)
);

CREATE TABLE IF NOT EXISTS keyword_medals (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    tier INTEGER NOT NULL,
    total_count INTEGER NOT NULL,
    awarded_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id, word)
);

CREATE TABLE IF NOT EXISTS abbreviations (
    guild_id INTEGER NOT NULL,
    abbreviation TEXT NOT NULL,
    expansion TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, abbreviation)
);
"""

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS word_counts (
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    word TEXT NOT NULL,
    count BIGINT NOT NULL DEFAULT 0,
    updated_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, channel_id, user_id, word)
);

CREATE TABLE IF NOT EXISTS keywords (
    guild_id BIGINT NOT NULL,
    word TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS stopwords (
    guild_id BIGINT NOT NULL,
    word TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS keyword_removals (
    guild_id BIGINT NOT NULL,
    word TEXT NOT NULL,
    removed_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, word, removed_at)
);

CREATE TABLE IF NOT EXISTS keyword_medals (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    word TEXT NOT NULL,
    tier INTEGER NOT NULL,
    total_count BIGINT NOT NULL,
    awarded_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, user_id, word)
);

CREATE TABLE IF NOT EXISTS abbreviations (
    guild_id BIGINT NOT NULL,
    abbreviation TEXT NOT NULL,
    expansion TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    PRIMARY KEY (guild_id, abbreviation)
);
"""


class DBX:
    dialect: str

    @staticmethod
    def _norm_params(params: Any | None) -> list[Any]:
        """Normalize params into a list. Accepts scalars (int, str, etc.)."""
        if params is None:
            return []
        if isinstance(params, (list, tuple)):
            return list(params)
        # Don't treat strings/bytes as iterables for SQL params
        if isinstance(params, (str, bytes, bytearray)):
            return [params]
        # If it's an iterable (e.g., generator), materialize it
        try:
            if isinstance(params, IterABC):
                return list(params)  # type: ignore[arg-type]
        except Exception:
            pass
        # Scalar (int, float, etc.)
        return [params]

    def _q(self, sql: str) -> str:
        raise NotImplementedError

    async def execute(self, sql: str, params: Any = None) -> Any:
        raise NotImplementedError

    async def fetchone(self, sql: str, params: Any = None) -> Optional[Any]:
        raise NotImplementedError

    async def fetchall(self, sql: str, params: Any = None) -> list[Any]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


@dataclass
class SQLiteDBX(DBX):
    sqlite_path: str
    dialect: str = "sqlite"
    _conn: Optional[aiosqlite.Connection] = None

    async def init(self) -> "SQLiteDBX":
        self._conn = await aiosqlite.connect(self.sqlite_path)
        # Return rows as dict-like objects (so code can do row["col"]) like asyncpg.
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA_SQLITE)
        await self._conn.commit()
        return self

    def _q(self, sql: str) -> str:
        return sql

    async def execute(self, sql: str, params: Any = None) -> Any:
        assert self._conn is not None
        cur = await self._conn.execute(self._q(sql), tuple(self._norm_params(params)))
        await self._conn.commit()
        return cur.rowcount

    async def fetchone(self, sql: str, params: Any = None) -> Optional[Any]:
        assert self._conn is not None
        cur = await self._conn.execute(self._q(sql), tuple(self._norm_params(params)))
        return await cur.fetchone()

    async def fetchall(self, sql: str, params: Any = None) -> list[Any]:
        assert self._conn is not None
        cur = await self._conn.execute(self._q(sql), tuple(self._norm_params(params)))
        return await cur.fetchall()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


@dataclass
class PostgresDBX(DBX):
    url: str
    dialect: str = "postgres"
    _pool: Any = None

    async def init(self) -> "PostgresDBX":
        if asyncpg is None:
            raise RuntimeError("asyncpg is not installed")
        self._pool = await asyncpg.create_pool(self.url, min_size=1, max_size=10, command_timeout=60)
        # asyncpg does not reliably accept multi-statement SQL via a single execute call.
        # Execute statements one-by-one.
        stmts = [s.strip() for s in SCHEMA_POSTGRES.split(";") if s.strip()]
        for s in stmts:
            await self.execute(s + ";")

        # --- Compatibility migrations (older schema variants) ---
        # Some earlier versions used different column names like `keyword`/`abbr`.
        # Since we use CREATE TABLE IF NOT EXISTS above, existing tables won't be altered.
        # Here we *safely* rename legacy columns to the current canonical names.
        async with self._pool.acquire() as conn:
            async def has_col(table: str, col: str) -> bool:
                q = """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1 AND column_name = $2
                LIMIT 1
                """
                return (await conn.fetchval(q, table, col)) is not None

            # column renames: (table, old, new)
            renames = [
                ("keywords", "keyword", "word"),
                ("stopwords", "stopword", "word"),
                ("keyword_removals", "keyword", "word"),
                ("keyword_medals", "keyword", "word"),
                ("word_counts", "keyword", "word"),
                ("abbreviations", "abbr", "abbreviation"),
            ]

            for table, old, new in renames:
                if await has_col(table, old) and not await has_col(table, new):
                    await conn.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}";')

            # Ensure timestamp columns exist (older schemas might not have them)
            # We keep them NOT NULL DEFAULT 0 to avoid breaking existing rows.
            add_cols = [
                ("keywords", "created_at", "BIGINT"),
                ("stopwords", "created_at", "BIGINT"),
                ("abbreviations", "created_at", "BIGINT"),
                ("word_counts", "updated_at", "BIGINT"),
                ("keyword_removals", "removed_at", "BIGINT"),
                # medals (older schemas might have only (guild_id,user_id,keyword,count) etc.)
                ("keyword_medals", "tier", "INTEGER"),
                ("keyword_medals", "awarded_at", "BIGINT"),
                ("keyword_medals", "total_count", "BIGINT"),
            ]
            for table, col, typ in add_cols:
                if not await has_col(table, col):
                    await conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {typ} NOT NULL DEFAULT 0;')

        return self

    def _q(self, sql: str) -> str:
        # Replace ? -> $1, $2...
        out = []
        i = 1
        for ch in sql:
            if ch == "?":
                out.append(f"${i}")
                i += 1
            else:
                out.append(ch)
        return "".join(out)

    async def execute(self, sql: str, params: Any = None) -> Any:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            return await conn.execute(self._q(sql), *self._norm_params(params))

    async def fetchone(self, sql: str, params: Any = None) -> Optional[Any]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(self._q(sql), *self._norm_params(params))

    async def fetchall(self, sql: str, params: Any = None) -> list[Any]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            return await conn.fetch(self._q(sql), *self._norm_params(params))

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


async def init_db(url: str | None = None, sqlite_path: str = "word_counts.db") -> DBX:
    """Initialize DB.

    - If url is provided or env DATABASE_URL looks like Postgres -> PostgresDBX
    - Else -> SQLiteDBX (local dev)
    """
    url = (url if url is not None else os.getenv("DATABASE_URL", "")).strip()
    # Postgres on Render usually starts with postgres:// or postgresql://
    u = url.lower()
    is_pg = u.startswith("postgres://") or u.startswith("postgresql://")
    if is_pg:
        return await PostgresDBX(url=url).init()
    return await SQLiteDBX(sqlite_path=sqlite_path).init()


# Backwards-compat: older code imports Database from this module.
Database = DBX
