import time
import asyncio
import discord
from discord.ext import commands

from word_counter_dsc.config import AUTO_BACKFILL_ENABLED, BACKFILL_LIMIT_PER_CHANNEL, COUNT_MODE
from word_counter_dsc.utils import (
    tokenize,
    parse_word_list,
    BUILTIN_STOPWORDS,
    count_keyword_hits,
)
from word_counter_dsc.ui.theme import base_embed, Theme


class KeywordCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    keyword = discord.app_commands.Group(name="keyword", description="Manage tracked keyword set")

    async def _is_removed(self, guild_id: int, kw: str) -> bool:
        async with self.bot.db_lock:
            row = await self.bot.dbx.fetchone(
                "SELECT 1 FROM keyword_removals WHERE guild_id=? AND keyword=?",
                (guild_id, kw),
            )
        return row is not None

    async def _clear_removed(self, guild_id: int, kw: str):
        async with self.bot.db_lock:
            await self.bot.dbx.execute(
                "DELETE FROM keyword_removals WHERE guild_id=? AND keyword=?",
                (guild_id, kw),
            )
            await self.bot.dbx.execute(
                "UPDATE keywords SET removed_at=NULL WHERE guild_id=? AND keyword=?",
                (guild_id, kw),
            )
            await self.bot.dbx.commit()

    async def _get_server_stopwords(self, guild_id: int) -> set[str]:
        async with self.bot.db_lock:
            rows = await self.bot.dbx.fetchall(
                "SELECT word FROM stopwords WHERE guild_id=?",
                (guild_id,),
            )
        return {r[0] for r in rows}

    async def _get_abbrev_map(self, guild_id: int) -> dict[str, str]:
        async with self.bot.db_lock:
            rows = await self.bot.dbx.fetchall(
                "SELECT abbr, keyword FROM keyword_abbreviations WHERE guild_id=?",
                (guild_id,),
            )
        return {a: k for a, k in rows}

    async def _auto_backfill_keyword(self, guild: discord.Guild, kw: str):
        """
        Best-effort backfill:
          - scans recent history
          - credits permissive matches to the canonical keyword
          - recomputes medals quietly
        """
        if not AUTO_BACKFILL_ENABLED:
            return

        # small delay so the initial slash response completes reliably
        await asyncio.sleep(1)

        stop = BUILTIN_STOPWORDS | (await self._get_server_stopwords(guild.id))
        if kw in stop:
            return

        abbrev_map = await self._get_abbrev_map(guild.id)

        for ch in guild.text_channels:
            try:
                me = guild.me
                if me is None:
                    continue
                perms = ch.permissions_for(me)
                if not (perms.read_messages and perms.read_message_history):
                    continue

                async for msg in ch.history(limit=BACKFILL_LIMIT_PER_CHANNEL, oldest_first=True):
                    if msg.author.bot:
                        continue

                    raw_hits = count_keyword_hits(msg.content or "", kw, abbrev_to_keyword=abbrev_map)
                    if COUNT_MODE == "UNIQUE":
                        delta = 1 if raw_hits > 0 else 0
                    else:
                        delta = raw_hits

                    if delta <= 0:
                        continue

                    async with self.bot.db_lock:
                        await self.bot.dbx.execute(
                            """
                            INSERT INTO word_counts (guild_id, channel_id, user_id, word, count)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(guild_id, channel_id, user_id, word)
                            DO UPDATE SET count = word_counts.count + excluded.count
                            """,
                            (guild.id, ch.id, msg.author.id, kw, int(delta)),
                        )
                        await self.bot.dbx.commit()

                await asyncio.sleep(0)
            except Exception:
                continue

        medals_cog = self.bot.get_cog("MedalsCog")
        if medals_cog:
            try:
                await medals_cog.recompute_all_medals_for_keyword(guild.id, kw)
            except Exception:
                pass

    # ----------------------------
    # /keyword add (bulk)
    # ----------------------------
    @keyword.command(name="add", description="Add keyword(s). Accepts multiple: 'a, b, c'")
    async def add(self, interaction: discord.Interaction, words: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        kws = parse_word_list(words)
        if not kws:
            return await interaction.response.send_message("No valid keywords found.", ephemeral=True)

        now = int(time.time())

        async with self.bot.db_lock:
            for kw in kws:
                await self.bot.dbx.execute(
                    """
                    INSERT INTO keywords (guild_id, keyword, created_at, removed_at)
                    VALUES (?, ?, ?, NULL)
                    ON CONFLICT(guild_id, keyword)
                    DO UPDATE SET removed_at=NULL
                    """,
                    (interaction.guild.id, kw, now),
                )
            await self.bot.dbx.commit()

        # clear removal markers (if any)
        for kw in kws:
            if await self._is_removed(interaction.guild.id, kw):
                await self._clear_removed(interaction.guild.id, kw)

        e = base_embed(
            "✅ Keywords added",
            "Added: " + ", ".join(f"`{k}`" for k in kws) + ".\nAuto-backfill has been queued (best-effort).",
            color=Theme.GOLD,
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

        # background tasks (runs in-process)
        for kw in kws:
            asyncio.create_task(self._auto_backfill_keyword(interaction.guild, kw))

    # ----------------------------
    # /keyword remove (bulk)
    # ----------------------------
    @keyword.command(name="remove", description="Remove keyword(s). Accepts multiple: 'a, b, c'")
    async def remove(self, interaction: discord.Interaction, words: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        kws = parse_word_list(words)
        if not kws:
            return await interaction.response.send_message("No valid keywords found.", ephemeral=True)

        now = int(time.time())
        async with self.bot.db_lock:
            for kw in kws:
                await self.bot.dbx.execute(
                    "UPDATE keywords SET removed_at=? WHERE guild_id=? AND keyword=?",
                    (now, interaction.guild.id, kw),
                )
                await self.bot.dbx.execute(
                    """
                    INSERT INTO keyword_removals (guild_id, keyword, removed_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id, keyword) DO UPDATE SET removed_at=excluded.removed_at
                    """,
                    (interaction.guild.id, kw, now),
                )
            await self.bot.dbx.commit()

        e = base_embed(
            "🗑️ Keywords removed",
            "Removed: " + ", ".join(f"`{k}`" for k in kws) + ".\n"
            "Medal data will purge after **7 days** if not re-added. Raw word counts remain.",
            color=Theme.SLATE,
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ----------------------------
    # /keyword list (PUBLIC)
    # ----------------------------
    @keyword.command(name="list", description="List keywords")
    async def list_(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        async with self.bot.db_lock:
            rows = await self.bot.dbx.fetchall(
                "SELECT keyword, removed_at FROM keywords WHERE guild_id=? ORDER BY keyword ASC",
                (interaction.guild.id,),
            )

        if not rows:
            return await interaction.response.send_message(
                embed=base_embed("📌 Keywords", "None", color=Theme.SLATE),
                ephemeral=False,
            )

        active = [kw for kw, removed_at in rows if not removed_at]
        removed = [kw for kw, removed_at in rows if removed_at]

        e = base_embed("📌 Keywords", color=Theme.BLUE)
        e.add_field(name="Active", value=", ".join(f"`{k}`" for k in active) or "None", inline=False)
        e.add_field(
            name="Removed (grace active)",
            value=", ".join(f"`{k}`" for k in removed) or "None",
            inline=False,
        )
        await interaction.response.send_message(embed=e, ephemeral=False)

    # ----------------------------
    # /keyword abbrev add/remove/list (EPHEMERAL except list? you requested only keyword list visible)
    # ----------------------------
    @keyword.command(name="abbrev_add", description='Add abbreviation mapping: "abbr = phrase containing an existing keyword"')
    async def abbrev_add(self, interaction: discord.Interaction, mapping: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        if "=" not in (mapping or ""):
            return await interaction.response.send_message('Format must be: `abbr = phrase`', ephemeral=True)

        left, right = mapping.split("=", 1)
        abbrs = parse_word_list(left.strip())
        if len(abbrs) != 1:
            return await interaction.response.send_message("Abbreviation must be a single token.", ephemeral=True)
        abbr = abbrs[0]

        rhs_tokens = parse_word_list(right.strip())
        if not rhs_tokens:
            return await interaction.response.send_message("Right side must contain words.", ephemeral=True)

        # Find an active keyword inside the phrase
        async with self.bot.db_lock:
            kw_rows = await self.bot.dbx.fetchall(
                "SELECT keyword FROM keywords WHERE guild_id=? AND removed_at IS NULL",
                (interaction.guild.id,),
            )
        active_keywords = {r[0] for r in kw_rows}

        target = None
        for t in rhs_tokens:
            if t in active_keywords:
                target = t
                break

        if target is None:
            return await interaction.response.send_message(
                "No active keyword found in the phrase. Add the keyword first (or include it on the right side).",
                ephemeral=True,
            )

        now = int(time.time())
        async with self.bot.db_lock:
            await self.bot.dbx.execute(
                """
                INSERT INTO keyword_abbreviations (guild_id, abbr, keyword, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, abbr) DO UPDATE SET keyword=excluded.keyword
                """,
                (interaction.guild.id, abbr, target, now),
            )
            await self.bot.dbx.commit()

        e = base_embed("✅ Abbreviation added", f"`{abbr}` → `{target}`", color=Theme.GOLD)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @keyword.command(name="abbrev_remove", description="Remove an abbreviation mapping (single abbreviation)")
    async def abbrev_remove(self, interaction: discord.Interaction, abbr: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        toks = parse_word_list(abbr)
        if len(toks) != 1:
            return await interaction.response.send_message("Provide a single abbreviation.", ephemeral=True)
        a = toks[0]

        async with self.bot.db_lock:
            await self.bot.dbx.execute(
                "DELETE FROM keyword_abbreviations WHERE guild_id=? AND abbr=?",
                (interaction.guild.id, a),
            )
            await self.bot.dbx.commit()

        await interaction.response.send_message(
            embed=base_embed("🗑️ Abbreviation removed", f"Removed `{a}` mapping.", color=Theme.SLATE),
            ephemeral=True,
        )

    @keyword.command(name="abbrev_list", description="List abbreviation mappings (admin-only view)")
    async def abbrev_list(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        async with self.bot.db_lock:
            rows = await self.bot.dbx.fetchall(
                "SELECT abbr, keyword FROM keyword_abbreviations WHERE guild_id=? ORDER BY abbr ASC",
                (interaction.guild.id,),
            )
        if not rows:
            return await interaction.response.send_message(
                embed=base_embed("🔤 Abbreviations", "None", color=Theme.SLATE),
                ephemeral=True,
            )

        lines = [f"`{a}` → `{k}`" for a, k in rows]
        await interaction.response.send_message(
            embed=base_embed("🔤 Abbreviations", "\n".join(lines), color=Theme.BLUE),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(KeywordCog(bot))
