import discord
from discord.ext import commands

BOT_DESC = (
    "**WordCounter DSC** tracks word usage per server, channel, and user.\n"
    "Run advanced searches, manage keyword sets, filter stopwords, and unlock medals."
)

COMMON = [
    "/help",
    "/search word:<word> n:10",
    "/search word:<word> channel:<#channel>",
    "/search word:<word> user:<@user>",
    "/keyword add <word>",
    "/stopword add <word>",
    "/profile",
    "/userprofile user:<@user>",
]

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="Show all commands and what the bot does")
    async def help_(self, interaction: discord.Interaction):
        # ACK immediately so Discord never times out
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            embed = discord.Embed(title="📚 WordCounter DSC — Help")
            embed.description = BOT_DESC

            cmds = sorted(self.bot.tree.get_commands(), key=lambda c: c.name)
            cmd_lines = [f"**/{c.name}** — {c.description or 'No description'}" for c in cmds]

            embed.add_field(
                name="✅ Slash Commands",
                value="\n".join(cmd_lines) if cmd_lines else "None",
                inline=False
            )
            embed.add_field(
                name="⭐ Examples",
                value="\n".join(COMMON),
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            # If anything goes wrong, don't let it silently timeout
            try:
                await interaction.followup.send(f"❌ Help failed: `{type(e).__name__}` — {e}", ephemeral=True)
            except Exception:
                pass

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
