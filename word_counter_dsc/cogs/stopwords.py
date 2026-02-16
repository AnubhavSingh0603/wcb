import time
import discord
from discord.ext import commands

from word_counter_dsc.utils import tokenize
from word_counter_dsc.ui.theme import base_embed, Theme


class StopwordsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    stopword = discord.app_commands.Group(name="stopword", description="Manage server stopwords")

    @stopword.command(name="add", description="Add a stopword (excluded from counting + medals going forward)")
    async def add(self, interaction: discord.Interaction, word: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        toks = tokenize(word)
        if not toks:
            return await interaction.response.send_message("Invalid word.", ephemeral=True)
        w = toks[0]

        async with self.bot.db_lock:
            await self.bot.dbx.execute(
                "INSERT INTO stopwords (guild_id, word, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, word) DO NOTHING",
                (interaction.guild.id, w, int(time.time())),
            )
            await self.bot.dbx.commit()

        await interaction.response.send_message(
            embed=base_embed("✅ Stopword added", f"`{w}` will no longer be counted going forward.", color=Theme.SLATE),
            ephemeral=True,
        )

    @stopword.command(name="remove", description="Remove a stopword")
    async def remove(self, interaction: discord.Interaction, word: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        toks = tokenize(word)
        if not toks:
            return await interaction.response.send_message("Invalid word.", ephemeral=True)
        w = toks[0]

        async with self.bot.db_lock:
            await self.bot.dbx.execute(
                "DELETE FROM stopwords WHERE guild_id=? AND word=?",
                (interaction.guild.id, w),
            )
            await self.bot.dbx.commit()

        await interaction.response.send_message(
            embed=base_embed("🗑️ Stopword removed", f"`{w}` can be counted again.", color=Theme.BLUE),
            ephemeral=True,
        )

    @stopword.command(name="list", description="List stopwords")
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
