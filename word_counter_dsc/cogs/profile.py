import datetime as dt
import discord
from discord.ext import commands

from word_counter_dsc.config import MEDAL_THRESHOLDS
from word_counter_dsc.ui.theme import base_embed, Theme
from word_counter_dsc.ui.pagination import PagedEmbedView


TIER_BY_NUM = {tier: title for _thr, tier, title in MEDAL_THRESHOLDS}


def fmt_ts(ts: int | None) -> str:
    if not ts:
        return "—"
    return dt.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="userprofile", description="Show a user profile: stats, keywords, medals")
    async def userprofile(self, interaction: discord.Interaction, user: discord.Member | None = None):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        user = user or interaction.user
        guild_id = interaction.guild.id

        async with self.bot.db_lock:
            row_total = await self.bot.dbx.fetchone(
                "SELECT COALESCE(SUM(count),0) FROM word_counts WHERE guild_id=? AND user_id=?",
                (guild_id, user.id),
            )
            total_words = int((row_total[0] if row_total else 0) or 0)

            row_dist = await self.bot.dbx.fetchone(
                "SELECT COUNT(DISTINCT word) FROM word_counts WHERE guild_id=? AND user_id=?",
                (guild_id, user.id),
            )
            distinct_words = int((row_dist[0] if row_dist else 0) or 0)

            kw_rows = await self.bot.dbx.fetchall(
                "SELECT keyword, removed_at FROM keywords WHERE guild_id=?",
                (guild_id,),
            )
            kws = [r[0] for r in kw_rows]
            removed_map = {r[0]: bool(r[1]) for r in kw_rows}

            keyword_usage = []
            total_keyword_usage = 0
            if kws:
                placeholders = ",".join("?" for _ in kws)
                rows = await self.bot.dbx.fetchall(
                    f"""
                    SELECT word, COALESCE(SUM(count),0) AS total
                    FROM word_counts
                    WHERE guild_id=? AND user_id=? AND word IN ({placeholders})
                    GROUP BY word
                    ORDER BY total DESC
                    """,
                    (guild_id, user.id, *kws),
                )
                used_map = {w: int(t or 0) for w, t in rows}
                # include zeros for unused keywords
                keyword_usage = [
                    (k, used_map.get(k, 0), removed_map.get(k, False))
                    for k in kws
                ]
                keyword_usage.sort(key=lambda x: (-x[1], x[0]))
                total_keyword_usage = sum(t for _w, t, _rm in keyword_usage)

            medal_rows = await self.bot.dbx.fetchall(
                """
                SELECT keyword, best_tier, awarded_at
                FROM keyword_medals
                WHERE guild_id=? AND user_id=?
                """,
                (guild_id, user.id),
            )

        # Sort medals by tier desc, then keyword
        medals = sorted(
            [(kw, int(tier), int(ts or 0)) for kw, tier, ts in medal_rows if int(tier or 0) > 0],
            key=lambda x: (-x[1], x[0]),
        )

        # Build paged embeds (keywords list can be long)
        header = base_embed("👤 User Profile", color=Theme.GOLD)
        header.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
        header.set_thumbnail(url=user.display_avatar.url)

        joined = getattr(user, "joined_at", None)
        joined_str = joined.strftime("%Y-%m-%d") if joined else "—"

        header.add_field(name="Total words", value=f"**{total_words}**", inline=True)
        header.add_field(name="Distinct words", value=f"**{distinct_words}**", inline=True)
        header.add_field(name="Keyword usage", value=f"**{total_keyword_usage}**", inline=True)
        header.add_field(name="Joined", value=joined_str, inline=True)

        embeds = [header]

        # Keyword usage pages
        if keyword_usage:
            per_page = 12
            for p in range(0, len(keyword_usage), per_page):
                chunk = keyword_usage[p : p + per_page]
                e = base_embed("🏷️ Keywords (usage)", color=Theme.BLUE)
                e.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
                lines = []
                for i, (w, t, is_removed) in enumerate(chunk, start=p + 1):
                    tag = " *(removed)*" if is_removed else ""
                    lines.append(f"**{i}.** `{w}` — **{t}**{tag}")
                e.description = "\n".join(lines)
                embeds.append(e)
        else:
            e = base_embed("🏷️ Keywords (usage)", "No keyword usage yet (or no active keywords).", color=Theme.SLATE)
            e.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
            embeds.append(e)

        # Medals page(s)
        if medals:
            per_page = 12
            for p in range(0, len(medals), per_page):
                chunk = medals[p : p + per_page]
                e = base_embed("🏅 Medals", color=Theme.PURPLE)
                e.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
                lines = []
                for kw, tier, ts in chunk:
                    title = TIER_BY_NUM.get(tier, f"Tier {tier}")
                    lines.append(f"**{title}** — `{kw}`  *(awarded {fmt_ts(ts)})*")
                e.description = "\n".join(lines)
                embeds.append(e)
        else:
            e = base_embed("🏅 Medals", "No medals yet.", color=Theme.SLATE)
            e.set_author(name=f"{user.display_name}", icon_url=user.display_avatar.url)
            embeds.append(e)

        view = PagedEmbedView(embeds, timeout=90, author_id=interaction.user.id)
        await interaction.response.send_message(embed=embeds[0], view=view)

    @discord.app_commands.command(name="profile", description="Your profile")
    async def profile(self, interaction: discord.Interaction):
        await self.userprofile.callback(self, interaction, user=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
