from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from word_counter_dsc.config import DEFAULT_TOP_N
from word_counter_dsc.utils import tokenize, user_mention
from word_counter_dsc.ui.theme import Theme, base_embed


class SearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="top", description="Top users for a tracked word (server-wide by default).")
    @app_commands.describe(word="Tracked word to rank.", channel="Optional channel filter.", n="How many users to show.")
    async def top(
        self,
        interaction: discord.Interaction,
        word: str,
        channel: discord.TextChannel | None = None,
        n: int = DEFAULT_TOP_N,
    ):
        assert interaction.guild is not None
        guild_id = interaction.guild.id
        channel_id = channel.id if channel else None

        w = word.strip().lower()
        if not w:
            await interaction.response.send_message("Provide a word.", ephemeral=True)
            return

        exists = await self.bot.dbx.fetchone(
            "SELECT 1 FROM keywords WHERE guild_id=? AND word=?",
            (guild_id, w),
        )
        if not exists:
            await interaction.response.send_message(
                f"❌ `{word}` is not in the keyword list. Use `/keyword list` to see available keywords.",
                ephemeral=True,
            )
            return

        n = max(1, min(int(n), 25))

        if channel_id is None:
            rows = await self.bot.dbx.fetchall(
                """
                SELECT user_id, SUM(word_counts.count) AS total
                FROM word_counts
                WHERE guild_id=? AND word=?
                GROUP BY user_id
                ORDER BY total DESC
                LIMIT ?
                """,
                (guild_id, w, n),
            )
        else:
            rows = await self.bot.dbx.fetchall(
                """
                SELECT user_id, SUM(word_counts.count) AS total
                FROM word_counts
                WHERE guild_id=? AND channel_id=? AND word=?
                GROUP BY user_id
                ORDER BY total DESC
                LIMIT ?
                """,
                (guild_id, channel_id, w, n),
            )

        embed = base_embed(
            title=f"🏆 Top for “{w}”",
            theme=Theme.DEFAULT,
            description=("Channel: " + channel.mention) if channel else "Scope: **Server-wide**",
        )

        if not rows:
            embed.add_field(name="No data yet", value="No matches recorded.", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return

        lines: list[str] = []
        for i, r in enumerate(rows, start=1):
            uid = int(r[0])
            total = int(r[1]) if r[1] is not None else 0
            member = interaction.guild.get_member(uid)
            display = member.display_name if member else f"User {uid}"
            lines.append(f"**{i}.** {user_mention(uid, display)} — **{total}**")

        embed.add_field(name="Leaderboard", value="\n".join(lines), inline=False)

        await interaction.response.send_message(
            embed=embed,
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="search", description="Tokenize text and show hits against your keyword list.")
    @app_commands.describe(text="Text to test locally (does not query Discord history).")
    async def search(self, interaction: discord.Interaction, text: str):
        tokens = tokenize(text)
        if not tokens:
            await interaction.response.send_message("No tokens found.", ephemeral=True)
            return

        assert interaction.guild is not None
        guild_id = interaction.guild.id
        kws = await self.bot.dbx.fetchall("SELECT word FROM keywords WHERE guild_id=? ORDER BY word", (guild_id,))
        keyword_set = {str(r[0]) for r in kws}

        hits = [t for t in tokens if t in keyword_set]
        embed = base_embed(title="🔎 Search", theme=Theme.DEFAULT)
        embed.add_field(
            name="Input tokens",
            value=", ".join(tokens[:80]) + (" ..." if len(tokens) > 80 else ""),
            inline=False,
        )
        embed.add_field(name="Keyword hits", value=", ".join(hits) if hits else "(none)", inline=False)

        await interaction.response.send_message(
            embed=embed,
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SearchCog(bot))
