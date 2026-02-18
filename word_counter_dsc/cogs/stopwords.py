from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from word_counter_dsc.utils import split_csv_words, safe_allowed_mentions
from word_counter_dsc.ui.theme import base_embed

# A reasonably large default set of common chat filler words.
# Users can add/remove their own stopwords per-server.
DEFAULT_STOPWORDS = {
    "a","an","the","and","or","but","if","then","else","so","because",
    "i","im","i'm","me","my","mine","you","u","ur","your","yours","we","our","ours",
    "he","she","they","them","their","theirs","it","its","this","that","these","those",
    "is","am","are","was","were","be","been","being","do","does","did","doing",
    "to","of","in","on","at","for","from","with","without","as","by","about","into","over","under",
    "not","no","yes","yeah","nah","ok","okay","k","kk","lol","lmao","lmfao","rofl",
    "brb","afk","idk","imo","tbh","btw","omw","rn","fr","ngl","jk","ty","thx","pls","plz",
    "hi","hey","hello","yo","sup","gg","wp","gl","hf","rip",
    "like","just","really","very","maybe","literally","actually",
    "go","going","went","come","came","get","got","make","made","take","took",
}

class StopwordGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="stopword", description="Manage stopwords (words ignored for fun stats)")

class StopwordsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.group = StopwordGroup()
        self.group.add_command(self.list_sw)
        self.group.add_command(self.add_sw)
        self.group.add_command(self.remove_sw)
        self.group.add_command(self.seed_defaults)

    async def cog_load(self):
        self.bot.tree.add_command(self.group)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.group.name, type=self.group.type)

    @app_commands.command(name="list", description="Show stopwords for this server.")
    async def list_sw(self, interaction: discord.Interaction):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)
        rows = await self.bot.dbx.fetchall(
            "SELECT word FROM stopwords WHERE guild_id=? ORDER BY word ASC",
            (gid,),
        )
        words = [r["word"] for r in rows]
        emb = base_embed("Stopwords", "Stopwords are ignored for 'interesting stats' like top words.")
        emb.add_field(
            name=f"Stopwords ({len(words)})",
            value=("• " + "\n• ".join(words[:120])) if words else "_No stopwords set yet._",
            inline=False,
        )
        if len(words) > 120:
            emb.set_footer(text=f"Showing first 120 of {len(words)} stopwords.")
        await interaction.response.send_message(embed=emb, allowed_mentions=safe_allowed_mentions())

    @app_commands.command(name="add", description="Add one or more stopwords (comma/space separated).")
    @app_commands.describe(words="Example: the, and, lol")
    async def add_sw(self, interaction: discord.Interaction, words: str):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)
        items = sorted(set(split_csv_words(words)))
        if not items:
            await interaction.response.send_message("No stopwords provided.", ephemeral=True)
            return
        for w in items:
            await self.bot.dbx.execute(
                "INSERT OR IGNORE INTO stopwords (guild_id, word) VALUES (?, ?)",
                (gid, w),
            )
        await interaction.response.send_message(f"Added {len(items)} stopword(s).", ephemeral=True)

    @app_commands.command(name="remove", description="Remove one or more stopwords (comma/space separated).")
    async def remove_sw(self, interaction: discord.Interaction, words: str):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)
        items = sorted(set(split_csv_words(words)))
        if not items:
            await interaction.response.send_message("No stopwords provided.", ephemeral=True)
            return
        for w in items:
            await self.bot.dbx.execute(
                "DELETE FROM stopwords WHERE guild_id=? AND word=?",
                (gid, w),
            )
        await interaction.response.send_message(f"Removed {len(items)} stopword(s).", ephemeral=True)

    @app_commands.command(name="seed", description="Seed a good default stopword list (Ephemeral).")
    async def seed_defaults(self, interaction: discord.Interaction):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)
        for w in sorted(DEFAULT_STOPWORDS):
            await self.bot.dbx.execute(
                "INSERT OR IGNORE INTO stopwords (guild_id, word) VALUES (?, ?)",
                (gid, w),
            )
        await interaction.response.send_message(f"Seeded {len(DEFAULT_STOPWORDS)} default stopwords.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(StopwordsCog(bot))
