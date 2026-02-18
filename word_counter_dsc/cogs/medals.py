from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from word_counter_dsc.config import MEDAL_THRESHOLDS, KEYWORD_REMOVAL_GRACE_SECONDS
from word_counter_dsc.utils import (
    tokenize,
    medal_rank_for_count,
    medal_emoji,
    medal_title,
    medal_progress_text,
)


class MedalsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.thresholds = MEDAL_THRESHOLDS

    @property
    def log(self) -> logging.Logger:
        return getattr(self.bot, "logger", None) or logging.getLogger("word_counter_dsc")

    @commands.Cog.listener()
    async def on_ready(self):
        # Cleanup medals for long-removed keywords (tidy DB)
        try:
            cutoff = int(time.time()) - int(KEYWORD_REMOVAL_GRACE_SECONDS)
            await self.bot.dbx.execute(
                """
                DELETE FROM keyword_medals
                WHERE (guild_id, word) IN (
                    SELECT kr.guild_id, kr.word
                    FROM keyword_removals kr
                    LEFT JOIN keywords k
                      ON k.guild_id = kr.guild_id AND k.word = kr.word
                    WHERE k.word IS NULL AND kr.removed_at < ?
                )
                """,
                (cutoff,),
            )
        except Exception:
            self.log.exception("Medals cleanup failed")

    async def _get_best_tier(self, guild_id: int, user_id: int, word: str) -> int:
        row = await self.bot.dbx.fetchone(
            "SELECT tier FROM keyword_medals WHERE guild_id=? AND user_id=? AND word=?",
            (guild_id, user_id, word),
        )
        if not row:
            return 0
        return int(row[0])

    async def _set_medal(self, guild_id: int, user_id: int, word: str, tier: int, total_count: int) -> None:
        await self.bot.dbx.execute(
            """
            INSERT INTO keyword_medals (guild_id, user_id, word, tier, total_count, awarded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (guild_id, user_id, word)
            DO UPDATE SET tier=EXCLUDED.tier, total_count=EXCLUDED.total_count, awarded_at=EXCLUDED.awarded_at
            """,
            (guild_id, user_id, word, int(tier), int(total_count), int(time.time())),
        )

    async def _recently_removed(self, guild_id: int, word: str) -> bool:
        cutoff = int(time.time()) - int(KEYWORD_REMOVAL_GRACE_SECONDS)
        row = await self.bot.dbx.fetchone(
            "SELECT 1 FROM keyword_removals WHERE guild_id=? AND word=? AND removed_at >= ?",
            (guild_id, word, cutoff),
        )
        return bool(row)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild or not message.content:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        tokens = tokenize(message.content)
        if not tokens:
            return

        kws = await self.bot.dbx.fetchall("SELECT word FROM keywords WHERE guild_id=?", (guild_id,))
        tracked = {str(r[0]) for r in kws}
        if not tracked:
            return

        hit_words = {t for t in tokens if t in tracked}
        if not hit_words:
            return

        for w in hit_words:
            if await self._recently_removed(guild_id, w):
                continue

            row = await self.bot.dbx.fetchone(
                "SELECT COALESCE(SUM(count),0) FROM word_counts WHERE guild_id=? AND user_id=? AND word=?",
                (guild_id, user_id, w),
            )
            total = int(row[0]) if row and row[0] is not None else 0

            tier, rank = medal_rank_for_count(total, self.thresholds)
            if tier <= 0:
                continue

            prev = await self._get_best_tier(guild_id, user_id, w)
            if tier <= prev:
                continue

            await self._set_medal(guild_id, user_id, w, tier, total)

            title = medal_title(w, rank)
            emoji = medal_emoji(rank)
            progress = medal_progress_text(total, self.thresholds)

            msg = f"{emoji} **{title}** — {message.author.display_name} reached **{rank}** for **{w}** ({progress})"
            try:
                await message.channel.send(msg, allowed_mentions=discord.AllowedMentions.none())
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(MedalsCog(bot))
