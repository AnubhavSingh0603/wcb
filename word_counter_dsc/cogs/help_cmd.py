from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from word_counter_dsc.ui.theme import base_embed
from word_counter_dsc.utils import safe_allowed_mentions

BOT_DESC = (
    "**WordCounterBot** tracks server keywords (with common variants) and turns them into a tiny knightly game.\n\n"
    "**Commands:**\n"
    "• `/keyword list` — show tracked keywords (public)\n"
    "• `/keyword add` / `/keyword remove` — edit keywords (admin, ephemeral)\n"
    "• `/keyword abbrev_add` — map abbreviations to phrases that contain tracked keywords\n"
    "• `/rank <keyword>` — show the leaderboard for that keyword\n"
    "• `/me` — your profile (titles + stats)\n"
    "• `/profile [user]` — someone else's profile\n"
    "• `/stopword seed|add|remove|list` — controls which common words are ignored for fun stats\n\n"
    "Tip: Mentions in leaderboards are **clickable but won't ping** anyone."
)

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show bot help.")
    async def help(self, interaction: discord.Interaction):
        emb = base_embed("Help", BOT_DESC)
        await interaction.response.send_message(embed=emb, ephemeral=True, allowed_mentions=safe_allowed_mentions())

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
