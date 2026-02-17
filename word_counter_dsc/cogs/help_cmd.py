import discord
from discord.ext import commands

BOT_DESC = (
    "**WordCounter DSC** tracks word usage per server, channel, and user.\n"
    "It also supports **keyword tracking with variants** (plurals/verbs/in-word use) and optional "
    "abbreviation mappings (e.g., `wtf` → a keyword).\n\n"
    "Tip: Most command responses are public. Admin-style edits (adding/removing keywords/stopwords) are private."
)

COMMON = [
    "/help",
    "/search word:<word> n:10",
    "/search word:<word> channel:<#channel>",
    "/search word:<word> user:<@user>",
    "/top word:<word> n:10",
    "/keyword list",
    "/keyword add words:\"a, b, c\"  (private)",
    "/keyword remove words:\"a, b\"  (private)",
    "/keyword abbrev_add mapping:\"wtf = what the fuck\"  (private)",
    "/stopword add words:\"a, b\"  (private)",
    "/me",
    "/profile user:<@user>",
]


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="Show what the bot does and the available commands")
    async def help_(self, interaction: discord.Interaction):
        # ACK immediately so Discord never times out
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True)

        try:
            embed = discord.Embed(title="📚 WordCounter DSC — Help", color=0x4C78FF)
            embed.description = BOT_DESC

            # Tree commands (top-level). Groups like /keyword show as a single entry here.
            cmds = sorted(self.bot.tree.get_commands(), key=lambda c: c.name)
            cmd_lines = [f"**/{c.name}** — {c.description or 'No description'}" for c in cmds]

            embed.add_field(name="Quick start", value="\n".join(f"• {c}" for c in COMMON), inline=False)
            embed.add_field(name="Top-level slash commands", value="\n".join(cmd_lines) or "—", inline=False)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Help failed: `{type(e).__name__}: {e}`", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
