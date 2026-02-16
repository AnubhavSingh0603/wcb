import time
import discord
from discord.ext import commands

from word_counter_dsc.config import MEDAL_THRESHOLDS, KEYWORD_REMOVAL_GRACE_SECONDS
from word_counter_dsc.ui.theme import base_embed, Theme


def tier_for_exact_count(cnt: int):
    for threshold, tier, title in MEDAL_THRESHOLDS:
        if cnt == threshold:
            return tier, title
    return None


def best_tier_for_total(cnt: int) -> int:
    best = 0
    for threshold, tier, _title in MEDAL_THRESHOLDS:
        if cnt >= threshold:
            best = max(best, tier)
    return best


class MedalsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_cleanup = 0

    async def _cleanup_removed_keywords(self):
        now = int(time.time())
        if now - self._last_cleanup < 900:
            return
        self._last_cleanup = now

        cutoff = now - KEYWORD_REMOVAL_GRACE_SECONDS
        async with self.bot.db_lock:
            rows = await self.bot.dbx.fetchall(
                "SELECT guild_id, keyword FROM keyword_removals WHERE removed_at < ?",
                (cutoff,),
            )

            for guild_id, keyword in rows:
                await self.bot.dbx.execute(
                    "DELETE FROM keyword_medals WHERE guild_id=? AND keyword=?",
                    (guild_id, keyword),
                )
                await self.bot.dbx.execute(
                    "DELETE FROM keyword_removals WHERE guild_id=? AND keyword=?",
                    (guild_id, keyword),
                )
            await self.bot.dbx.commit()

    async def _get_user_total(self, guild_id: int, user_id: int, keyword: str) -> int:
        async with self.bot.db_lock:
            row = await self.bot.dbx.fetchone(
                "SELECT COALESCE(SUM(count),0) FROM word_counts WHERE guild_id=? AND user_id=? AND word=?",
                (guild_id, user_id, keyword),
            )
        return int((row[0] if row else 0) or 0)

    async def _get_best_tier(self, guild_id: int, keyword: str, user_id: int) -> int:
        async with self.bot.db_lock:
            row = await self.bot.dbx.fetchone(
                "SELECT best_tier FROM keyword_medals WHERE guild_id=? AND keyword=? AND user_id=?",
                (guild_id, keyword, user_id),
            )
        return int(row[0]) if row else 0

    async def _set_best_tier(self, guild_id: int, keyword: str, user_id: int, tier: int):
        now = int(time.time())
        async with self.bot.db_lock:
            await self.bot.dbx.execute(
                """
                INSERT INTO keyword_medals (guild_id, keyword, user_id, best_tier, awarded_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, keyword, user_id)
                DO UPDATE SET best_tier=excluded.best_tier, awarded_at=excluded.awarded_at
                """,
                (guild_id, keyword, user_id, int(tier), now),
            )
            await self.bot.dbx.commit()

    async def recompute_all_medals_for_keyword(self, guild_id: int, keyword: str):
        # Silent recompute tiers (used after backfill)
        async with self.bot.db_lock:
            rows = await self.bot.dbx.fetchall(
                """
                SELECT user_id, SUM(count) AS total
                FROM word_counts
                WHERE guild_id=? AND word=?
                GROUP BY user_id
                """,
                (guild_id, keyword),
            )

        for user_id, total in rows:
            best = best_tier_for_total(int(total or 0))
            if best > 0:
                await self._set_best_tier(guild_id, keyword, int(user_id), int(best))

    async def handle_message_keywords(self, message: discord.Message, inc_counter):
        await self._cleanup_removed_keywords()

        guild_id = message.guild.id
        user_id = message.author.id

        async with self.bot.db_lock:
            rows = await self.bot.dbx.fetchall(
                "SELECT keyword FROM keywords WHERE guild_id=? AND removed_at IS NULL",
                (guild_id,),
            )
        active_kws = {r[0] for r in rows}

        hits = [w for w in inc_counter.keys() if w in active_kws]
        if not hits:
            return

        for kw in hits:
            total = await self._get_user_total(guild_id, user_id, kw)
            info = tier_for_exact_count(total)
            if not info:
                continue
            tier, title = info

            best = await self._get_best_tier(guild_id, kw, user_id)
            if tier <= best:
                continue
            await self._set_best_tier(guild_id, kw, user_id, tier)

            flair = {
                "squire": "✨ The court acknowledges your devotion.",
                "knight": "🛡️ Your honor is recognized.",
                "baron": "🔮 A noble presence emerges.",
                "duke": "🏰 The realm takes notice.",
                "archduke": "🔥 The realm trembles.",
                "sovereign": "👑 A new Sovereign rises.",
            }.get(title.lower(), "🏅 Achievement unlocked!")

            e = base_embed(
                f"🏅 Medal Unlocked — {title}",
                f"{message.author.mention} earned **{title}** for keyword `{kw}`!\n{flair}",
                color=Theme.medal_color(title),
            )
            try:
                e.set_thumbnail(url=message.author.display_avatar.url)
            except Exception:
                pass

            try:
                await message.reply(embed=e, mention_author=False)
            except Exception:
                try:
                    await message.channel.send(embed=e)
                except Exception:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(MedalsCog(bot))
