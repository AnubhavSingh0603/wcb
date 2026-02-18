import time
import discord
from discord.ext import commands

from word_counter_dsc.config import MEDAL_THRESHOLDS, KEYWORD_REMOVAL_GRACE_SECONDS
from word_counter_dsc.ui.theme import base_embed, Theme
from word_counter_dsc.utils import medal_rank_for_count, medal_emoji, medal_title, medal_progress_text


class MedalsCog(commands.Cog):
    """Awards themed 'keyword medals' when users hit thresholds."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Pre-sort thresholds by min_count
        self.thresholds = sorted([(int(t), int(tier), str(rank)) for (t, tier, rank) in MEDAL_THRESHOLDS], key=lambda x: x[0])

    async def _get_user_total(self, guild_id: int, user_id: int, keyword: str) -> int:
        row = await self.bot.dbx.fetchrow(
            """
            SELECT COALESCE(SUM(count), 0) AS total
            FROM word_counts
            WHERE guild_id = ? AND user_id = ? AND word = ?
            """,
            guild_id,
            user_id,
            keyword,
        )
        return int(row["total"] if row else 0)

    async def _get_best_tier(self, guild_id: int, user_id: int, keyword: str) -> int:
        row = await self.bot.dbx.fetchrow(
            """
            SELECT tier
            FROM keyword_medals
            WHERE guild_id = ? AND user_id = ? AND keyword = ?
            """,
            guild_id,
            user_id,
            keyword,
        )
        return int(row["tier"]) if row else 0

    async def _set_best_tier(self, guild_id: int, user_id: int, keyword: str, tier: int, total: int) -> None:
        now = int(time.time())
        await self.bot.dbx.execute(
            """
            INSERT INTO keyword_medals (guild_id, user_id, keyword, tier, total_count, awarded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (guild_id, user_id, keyword)
            DO UPDATE SET tier = EXCLUDED.tier, total_count = EXCLUDED.total_count, awarded_at = EXCLUDED.awarded_at
            """,
            guild_id,
            user_id,
            keyword,
            int(tier),
            int(total),
            now,
        )

    async def maybe_award(self, message: discord.Message, keyword: str) -> None:
        """Called by the tracker after it increments a keyword."""
        if not message.guild or message.author.bot:
            return

        guild_id = int(message.guild.id)
        user_id = int(message.author.id)
        keyword = (keyword or "").lower().strip()
        if not keyword:
            return

        try:
            total = await self._get_user_total(guild_id, user_id, keyword)
            best_tier = await self._get_best_tier(guild_id, user_id, keyword)

            # Determine tier for current total
            tier_now, rank_now, next_thr = medal_rank_for_count(total)

            if tier_now <= best_tier:
                return

            # announce ONLY if total hits the exact threshold for that tier
            tier_threshold = None
            for thr, tier, _rank in self.thresholds:
                if tier == tier_now:
                    tier_threshold = thr
                    break

            if tier_threshold is not None and total != tier_threshold:
                # still update DB silently so profile is correct
                await self._set_best_tier(guild_id, user_id, keyword, tier_now, total)
                return

            await self._set_best_tier(guild_id, user_id, keyword, tier_now, total)

            emoji = medal_emoji(rank_now)
            title = medal_title(rank_now, keyword)
            prog = medal_progress_text(total, next_thr)

            desc_lines = [
                f"{emoji} **{title}**",
                f"Progress: {prog}",
            ]
            if next_thr:
                _, next_rank, _ = medal_rank_for_count(next_thr)
                desc_lines.append(f"Next rank at **{next_thr:,}** → **{next_rank}**")

            e = base_embed(
                title="New Title Earned!",
                description="\n".join(desc_lines),
                color=Theme.medal_color(rank_now),
            )

            await message.channel.send(
                embed=e,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        except Exception:
            self.bot.logger.exception("Medal award failed")

    @commands.Cog.listener()
    async def on_ready(self):
        # Clean medals for keywords removed long ago
        try:
            cutoff = int(time.time()) - int(KEYWORD_REMOVAL_GRACE_SECONDS)
            await self.bot.dbx.execute(
                """
                DELETE FROM keyword_medals
                WHERE (guild_id, keyword) IN (
                    SELECT guild_id, keyword
                    FROM keyword_removals
                    WHERE removed_at < ?
                )
                """,
                cutoff,
            )
        except Exception:
            self.bot.logger.exception("Medals cleanup failed")


async def setup(bot: commands.Bot):
    await bot.add_cog(MedalsCog(bot))
