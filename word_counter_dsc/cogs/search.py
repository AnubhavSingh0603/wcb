from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from word_counter_dsc.config import DEFAULT_TOP_N
from word_counter_dsc.utils import user_mention, safe_allowed_mentions
from word_counter_dsc.ui.theme import base_embed


class SearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="rank", description="Top users for a keyword in this server.")
    @app_commands.describe(keyword="Tracked keyword", top_n="How many users to show")
    async def rank(self, interaction: discord.Interaction, keyword: str, top_n: int | None = None):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)
        kw = (keyword or "").strip().lower()
        n = int(top_n or DEFAULT_TOP_N)
        n = max(1, min(n, 25))

        # Validate keyword exists
        exists = await self.bot.dbx.fetchone(
            "SELECT 1 AS ok FROM keywords WHERE guild_id=? AND keyword=?",
            (gid, kw),
        )
        if not exists:
            await interaction.response.send_message(
                f"`{kw}` is not in /keyword list for this server.",
                ephemeral=True,
            )
            return

        rows = await self.bot.dbx.fetchall(
            """
            SELECT user_id, SUM(count) AS total
            FROM word_counts
            WHERE guild_id=? AND word=?
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT ?
            """,
            (gid, kw, n),
        )

        emb = base_embed(f"Top {len(rows)} for '{kw}'", "Keyword leaderboard (server-wide).")
        if not rows:
            emb.description = "_No counts yet._"
        else:
            lines = []
            for i, r in enumerate(rows, start=1):
                uid = int(r["user_id"])
                total = int(r["total"])
                lines.append(f"**{i}.** {user_mention(uid)} — **{total}**")
            emb.add_field(name="Leaderboard", value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=emb, allowed_mentions=safe_allowed_mentions())


async def setup(bot: commands.Bot):
    await bot.add_cog(SearchCog(bot))
