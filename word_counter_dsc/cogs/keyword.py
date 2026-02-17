import time
import asyncio
import discord
from discord.ext import commands

from word_counter_dsc.config import AUTO_BACKFILL_ENABLED, BACKFILL_LIMIT_PER_CHANNEL, COUNT_MODE
from word_counter_dsc.utils import tokenize, BUILTIN_STOPWORDS
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

    async def _auto_backfill_keyword(self, guild: discord.Guild, kw: str, *, notify_ch: discord.abc.Messageable | None):
        if not AUTO_BACKFILL_ENABLED:
            return

        # small delay so the initial slash response completes reliably
        await asyncio.sleep(1)

        stop = BUILTIN_STOPWORDS | (await self._get_server_stopwords(guild.id))
        if kw in stop:
            # keyword is stopworded; don't backfill
            return

        counted_msgs = 0
        scanned = 0

        for ch in guild.text_channels:
            try:
                me = guild.me
                if me is None:
                    continue
                perms = ch.permissions_for(me)
                if not (perms.read_messages and perms.read_message_history):
                    continue

                async for msg in ch.history(limit=BACKFILL_LIMIT_PER_CHANNEL, oldest_first=True):
                    scanned += 1
                    if msg.author.bot:
                        continue
                    words = tokenize(msg.content)
                    if not words:
                        continue
                    if kw not in words:
                        continue

                    # If UNIQUE: keyword counts 1 per message. If ALL: count occurrences.
                    delta = sum(1 for w in words if w == kw) if COUNT_MODE == "ALL" else 1

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
                    counted_msgs += 1

                # cooperative yield
                await asyncio.sleep(0)
            except Exception:
                continue

        # Silently recompute best medal tiers (no announcement spam)
        medals_cog = self.bot.get_cog("MedalsCog")
        if medals_cog:
            try:
                await medals_cog.recompute_all_medals_for_keyword(guild.id, kw)
            except Exception:
                pass

    @keyword.command(name="add", description="Add keyword (auto-backfills history)")
    async def add(self, interaction: discord.Interaction, word: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        toks = tokenize(word)
        if not toks:
            return await interaction.response.send_message("Invalid keyword.", ephemeral=True)
        kw = toks[0]

        now = int(time.time())
        async with self.bot.db_lock:
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

        if await self._is_removed(interaction.guild.id, kw):
            await self._clear_removed(interaction.guild.id, kw)

        e = base_embed(
            "✅ Keyword added",
            f"Added `{kw}`. Auto-backfill has been queued (best-effort).",
            color=Theme.GOLD,
        )
        await interaction.response.send_message(embed=e, ephemeral=False)

        # Background task (runs in-process)
        asyncio.create_task(
            self._auto_backfill_keyword(interaction.guild, kw, notify_ch=interaction.channel)
        )

    @keyword.command(name="remove", description="Remove keyword (medals purge after 7 days if not re-added)")
    async def remove(self, interaction: discord.Interaction, word: str):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        toks = tokenize(word)
        if not toks:
            return await interaction.response.send_message("Invalid keyword.", ephemeral=True)
        kw = toks[0]

        now = int(time.time())
        async with self.bot.db_lock:
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
            "🗑️ Keyword removed",
            f"Removed `{kw}`. Medal data will purge after **7 days** if not re-added. Raw word counts remain.",
            color=Theme.SLATE,
        )
        await interaction.response.send_message(embed=e, ephemeral=False)

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
            return await interaction.response.send_message(embed=base_embed("📌 Keywords", "None", color=Theme.SLATE), ephemeral=False)

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


async def setup(bot: commands.Bot):
    await bot.add_cog(KeywordCog(bot))
