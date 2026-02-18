from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from word_counter_dsc.utils import split_csv_words
from word_counter_dsc.utils import safe_allowed_mentions
from word_counter_dsc.ui.theme import base_embed


class KeywordGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="keyword", description="Manage tracked keywords")


class KeywordCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.group = KeywordGroup()

        # Register commands onto the group
        self.group.add_command(self.list_keywords)
        self.group.add_command(self.add_keywords)
        self.group.add_command(self.remove_keywords)
        self.group.add_command(self.add_abbrev)
        self.group.add_command(self.list_abbrev)
        self.group.add_command(self.remove_abbrev)

    async def cog_load(self):
        self.bot.tree.add_command(self.group)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.group.name, type=self.group.type)

    # ---------------------------
    # /keyword list  (PUBLIC)
    # ---------------------------
    @app_commands.command(name="list", description="Show tracked keywords for this server.")
    async def list_keywords(self, interaction: discord.Interaction):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)
        rows = await self.bot.dbx.fetchall(
            "SELECT keyword FROM keywords WHERE guild_id=? ORDER BY keyword ASC",
            (gid,),
        )
        kws = [r["keyword"] for r in rows]
        emb = base_embed("Tracked Keywords", "Server-wide tracked keywords.")
        emb.add_field(
            name=f"Keywords ({len(kws)})",
            value=("• " + "\n• ".join(kws)) if kws else "_No keywords yet. Use /keyword add (admin)._",
            inline=False,
        )
        await interaction.response.send_message(embed=emb, allowed_mentions=safe_allowed_mentions())

    # ---------------------------
    # /keyword add  (EPHEMERAL)
    # ---------------------------
    @app_commands.command(name="add", description="Add one or more keywords (comma/space separated).")
    @app_commands.describe(words="Example: hello, world, foo")
    async def add_keywords(self, interaction: discord.Interaction, words: str):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)
        kws = split_csv_words(words)
        kws = sorted(set(kws))
        if not kws:
            await interaction.response.send_message("No keywords provided.", ephemeral=True)
            return

        for kw in kws:
            await self.bot.dbx.execute(
                "INSERT OR IGNORE INTO keywords (guild_id, keyword) VALUES (?, ?)",
                (gid, kw),
            )

        await interaction.response.send_message(
            f"Added {len(kws)} keyword(s): " + ", ".join(kws),
            ephemeral=True,
        )

    # ---------------------------
    # /keyword remove (EPHEMERAL)
    # ---------------------------
    @app_commands.command(name="remove", description="Remove one or more keywords (comma/space separated).")
    @app_commands.describe(words="Example: hello, world")
    async def remove_keywords(self, interaction: discord.Interaction, words: str):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)
        kws = split_csv_words(words)
        kws = sorted(set(kws))
        if not kws:
            await interaction.response.send_message("No keywords provided.", ephemeral=True)
            return

        for kw in kws:
            await self.bot.dbx.execute(
                "DELETE FROM keywords WHERE guild_id=? AND keyword=?",
                (gid, kw),
            )
            # record removal time for cleanup (medals cog)
            await self.bot.dbx.execute(
                "INSERT INTO keyword_removals (guild_id, keyword, removed_at) VALUES (?, ?, strftime('%s','now'))",
                (gid, kw),
            )

        await interaction.response.send_message(
            f"Removed {len(kws)} keyword(s): " + ", ".join(kws),
            ephemeral=True,
        )

    # ---------------------------
    # Abbreviations
    # ---------------------------
    @app_commands.command(name="abbrev_add", description="Add abbreviations: abbr=phrase. (Ephemeral)")
    @app_commands.describe(rules="Example: wtf=fuck | lol=fuck this | (use commas/newlines for multiple)")
    async def add_abbrev(self, interaction: discord.Interaction, rules: str):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)

        # get keyword set to validate expansions
        kw_rows = await self.bot.dbx.fetchall("SELECT keyword FROM keywords WHERE guild_id=?", (gid,))
        kw_set = {r["keyword"] for r in kw_rows}

        pairs = []
        for line in rules.splitlines():
            for part in line.split(","):
                part = part.strip()
                if not part:
                    continue
                if "=" not in part:
                    continue
                abbr, exp = part.split("=", 1)
                abbr = abbr.strip().lower()
                exp = exp.strip().lower()
                if not abbr or not exp:
                    continue
                # must reference at least one existing keyword
                if kw_set and not any(k in exp for k in kw_set):
                    continue
                pairs.append((abbr, exp))

        if not pairs:
            await interaction.response.send_message(
                "No valid abbreviation rules found. Use format like `wtf=fuck` and ensure the expansion contains an existing keyword.",
                ephemeral=True,
            )
            return

        for abbr, exp in pairs:
            await self.bot.dbx.execute(
                "INSERT OR REPLACE INTO abbreviations (guild_id, abbr, expansion) VALUES (?, ?, ?)",
                (gid, abbr, exp),
            )

        await interaction.response.send_message(
            f"Saved {len(pairs)} abbreviation rule(s).",
            ephemeral=True,
        )

    @app_commands.command(name="abbrev_list", description="List abbreviation rules (public).")
    async def list_abbrev(self, interaction: discord.Interaction):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)
        rows = await self.bot.dbx.fetchall(
            "SELECT abbr, expansion FROM abbreviations WHERE guild_id=? ORDER BY abbr ASC",
            (gid,),
        )
        emb = base_embed("Keyword Abbreviations", "These map short forms to phrases containing tracked keywords.")
        if not rows:
            emb.description = "_No abbreviation rules yet._"
        else:
            lines = [f"• **{r['abbr']}** = {r['expansion']}" for r in rows[:50]]
            emb.add_field(name=f"Rules ({len(rows)})", value="\n".join(lines), inline=False)
            if len(rows) > 50:
                emb.set_footer(text=f"Showing first 50 of {len(rows)} rules.")
        await interaction.response.send_message(embed=emb, allowed_mentions=safe_allowed_mentions())

    @app_commands.command(name="abbrev_remove", description="Remove abbreviations by name (comma/space). (Ephemeral)")
    @app_commands.describe(abbrs="Example: wtf, lol")
    async def remove_abbrev(self, interaction: discord.Interaction, abbrs: str):
        assert self.bot.dbx is not None
        gid = int(interaction.guild_id or 0)
        items = split_csv_words(abbrs)
        items = sorted(set(items))
        if not items:
            await interaction.response.send_message("No abbreviations provided.", ephemeral=True)
            return

        for a in items:
            await self.bot.dbx.execute(
                "DELETE FROM abbreviations WHERE guild_id=? AND abbr=?",
                (gid, a),
            )

        await interaction.response.send_message(f"Removed: {', '.join(items)}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(KeywordCog(bot))
