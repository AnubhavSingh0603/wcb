import time
import discord
from discord.ext import commands

from word_counter_dsc.utils import parse_word_list
from word_counter_dsc.ui.theme import base_embed, Theme


class StopwordsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    stopword = discord.app_commands.Group(name="stopword", description="Manage server stopwords")

    @stopword.command(name="add", description="Add stopword(s). Accepts multiple: 'a, b, c'")
    async def add(self, interaction: discord.Interaction, words: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        toks = parse_word_list(words)
        if not toks:
            return await interaction.response.send_message("No valid stopwords found.", ephemeral=True)

        now = int(time.time())
        async with self.bot.db_lock:
            for w in toks:
                await self.bot.dbx.execute(
                    "INSERT INTO stopwords (guild_id, word, created_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(guild_id, word) DO NOTHING",
                    (interaction.guild.id, w, now),
                )
            await self.bot.dbx.commit()

        await interaction.response.send_message(
            embed=base_embed(
                "✅ Stopwords added",
                "Added: " + ", ".join(f"`{w}`" for w in toks) + "\nThese will no longer be counted going forward.",
                color=Theme.SLATE,
            ),
            ephemeral=True,
        )

    @stopword.command(name="remove", description="Remove stopword(s). Accepts multiple: 'a, b, c'")
    async def remove(self, interaction: discord.Interaction, words: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        toks = parse_word_list(words)
        if not toks:
            return await interaction.response.send_message("No valid stopwords found.", ephemeral=True)

        async with self.bot.db_lock:
            for w in toks:
                await self.bot.dbx.execute(
                    "DELETE FROM stopwords WHERE guild_id=? AND word=?",
                    (interaction.guild.id, w),
                )
            await self.bot.dbx.commit()

        await interaction.response.send_message(
            embed=base_embed("🗑️ Stopwords removed", "Removed: " + ", ".join(f"`{w}`" for w in toks), color=Theme.BLUE),
            ephemeral=True,
        )

    @stopword.command(name="list", description="List stopwords (admin-only view)")
    async def list_(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        async with self.bot.db_lock:
            rows = await self.bot.dbx.fetchall(
                "SELECT word FROM stopwords WHERE guild_id=? ORDER BY word ASC",
                (interaction.guild.id,),
            )

        words = [r[0] for r in rows]
        e = base_embed("🚫 Stopwords", ", ".join(f"`{w}`" for w in words) or "None", color=Theme.SLATE)
        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StopwordsCog(bot))
