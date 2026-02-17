import datetime as dt
import discord
from discord.ext import commands

from word_counter_dsc.config import MEDAL_THRESHOLDS
from word_counter_dsc.ui.theme import base_embed, Theme
from word_counter_dsc.ui.pagination import PagedEmbedView
from word_counter_dsc.utils import user_link_no_ping

TIER_BY_NUM = {tier: title for _thr, tier, title in MEDAL_THRESHOLDS}


def fmt_ts(ts: int | None) -> str:
    if not ts:
        return "—"
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _top_word(self, guild_id: int, user_id: int) -> tuple[str | None, int]:
        async with self.bot.db_lock:
            row = await self.bot.dbx.fetchone(
                """
                SELECT word, SUM(count) AS c
                FROM word_counts
                WHERE guild_id=? AND user_id=?
                GROUP BY word
                ORDER BY c DESC
                LIMIT 1
                """,
                (guild_id, user_id),
            )
        if not row:
            return (None, 0)
        return (row[0], int(row[1] or 0))

    async def _unique_word(self, guild_id: int, user_id: int) -> tuple[str | None, int]:
        """
        A "unique word" here means: used by this user in this server, and never used by anyone else.
        We return the strongest such word by this user's count.
        """
        async with self.bot.db_lock:
            row = await self.bot.dbx.fetchone(
                """
                WITH me AS (
                    SELECT word, SUM(count) AS myc
                    FROM word_counts
                    WHERE guild_id=? AND user_id=?
                    GROUP BY word
                ),
                others AS (
                    SELECT word, SUM(count) AS oc
                    FROM word_counts
                    WHERE guild_id=? AND user_id<>?
                    GROUP BY word
                )
                SELECT me.word, me.myc
                FROM me
                LEFT JOIN others ON others.word = me.word
                WHERE COALESCE(others.oc, 0) = 0
                ORDER BY me.myc DESC
                LIMIT 1
                """,
                (guild_id, user_id, guild_id, user_id),
            )
        if not row:
            return (None, 0)
        return (row[0], int(row[1] or 0))

    async def _top_keyword(self, guild_id: int, user_id: int) -> tuple[str | None, int]:
        async with self.bot.db_lock:
            row = await self.bot.dbx.fetchone(
                """
                SELECT wc.word, SUM(wc.count) AS c
                FROM word_counts wc
                JOIN keywords k
                  ON k.guild_id = wc.guild_id
                 AND k.keyword = wc.word
                 AND k.removed_at IS NULL
                WHERE wc.guild_id=? AND wc.user_id=?
                GROUP BY wc.word
                ORDER BY c DESC
                LIMIT 1
                """,
                (guild_id, user_id),
            )
        if not row:
            return (None, 0)
        return (row[0], int(row[1] or 0))

    async def _medals_summary(self, guild_id: int, user_id: int) -> list[tuple[str, str, int]]:
        """
        Returns list of (keyword, tier_title, total_count) for this user,
        ordered by tier desc then count desc.
        """
        async with self.bot.db_lock:
            rows = await self.bot.dbx.fetchall(
                """
                SELECT m.keyword, m.tier, m.total_count
                FROM keyword_medals m
                WHERE m.guild_id=? AND m.user_id=?
                ORDER BY m.tier DESC, m.total_count DESC
                """,
                (guild_id, user_id),
            )
        out = []
        for kw, tier, total in rows:
            out.append((kw, TIER_BY_NUM.get(int(tier), f"Tier {tier}"), int(total or 0)))
        return out

    async def _render_profile(self, interaction: discord.Interaction, member: discord.Member):
        gid = interaction.guild.id
        uid = member.id

        topw, topw_c = await self._top_word(gid, uid)
        uniqw, uniqw_c = await self._unique_word(gid, uid)
        topk, topk_c = await self._top_keyword(gid, uid)
        medals = await self._medals_summary(gid, uid)

        title = f"👤 Profile · {member.display_name}"
        e = base_embed(title, color=Theme.BLUE)
        e.set_thumbnail(url=member.display_avatar.url)

        # Quick facts
        e.add_field(
            name="Most used word",
            value=(f"`{topw}` · **{topw_c:,}**" if topw else "—"),
            inline=True,
        )
        e.add_field(
            name="Most unique word",
            value=(f"`{uniqw}` · **{uniqw_c:,}**" if uniqw else "—"),
            inline=True,
        )
        e.add_field(
            name="Top keyword",
            value=(f"`{topk}` · **{topk_c:,}**" if topk else "—"),
            inline=True,
        )

        # Medal list (paged)
        if not medals:
            e.add_field(name="Medals", value="No medals yet.", inline=False)
            e.set_footer(text=f"User: {user_link_no_ping(uid)}")
            return await interaction.response.send_message(embed=e, ephemeral=False)

        lines = [f"**{tier}** · `{kw}` · **{total:,}**" for kw, tier, total in medals]
        pages = []
        chunk = 10
        for i in range(0, len(lines), chunk):
            p = base_embed(title, color=Theme.BLUE)
            p.set_thumbnail(url=member.display_avatar.url)
            p.add_field(name="Medals", value="\n".join(lines[i : i + chunk]), inline=False)
            p.set_footer(text=f"User: {user_link_no_ping(uid)}")
            pages.append(p)

        view = PagedEmbedView(pages, author_id=interaction.user.id)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=False)

    @discord.app_commands.command(name="me", description="Show your profile")
    async def me(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        await self._render_profile(interaction, interaction.user)

    @discord.app_commands.command(name="profile", description="Show a user's profile")
    async def profile(self, interaction: discord.Interaction, user: discord.Member | None = None):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        await self._render_profile(interaction, user or interaction.user)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
