from __future__ import annotations

import discord
from discord.ext import commands

from word_counter_dsc.config import KEYWORD_ALIASES, MATCH_MODE
import time

from word_counter_dsc.utils import tokenize, count_keyword_occurrences

class TrackerCog(commands.Cog):
    """Tracks keyword usage as messages arrive."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore bots / DMs
        if message.author.bot:
            return
        if not message.guild:
            return
        if not self.bot.dbx:
            return

        gid = int(message.guild.id)
        cid = int(message.channel.id)
        uid = int(message.author.id)

        text = (message.content or "")
        if not text.strip():
            return

        # ---- server keyword list + abbreviations ----
        kw_rows = await self.bot.dbx.fetchall(
            "SELECT word FROM keywords WHERE guild_id=?",
            (gid,),
        )
        keywords = [str(r["word"]) for r in kw_rows]
        if not keywords:
            return

        ab_rows = await self.bot.dbx.fetchall(
            "SELECT abbreviation, expansion FROM abbreviations WHERE guild_id=?",
            (gid,),
        )
        abbr_map = {str(r["abbreviation"]): str(r["expansion"]) for r in ab_rows}

        lower_text = text.lower()

        # If message contains abbreviations, append their expansions to the text
        tokens = tokenize(lower_text)
        for t in tokens:
            exp = abbr_map.get(t)
            if exp:
                lower_text += " " + exp

        # ---- count keyword occurrences ----
        now = int(time.time())

        for kw in keywords:
            aliases = KEYWORD_ALIASES.get(kw, [])
            if MATCH_MODE == 0:
                c = sum(1 for t in tokens if t == kw or t in aliases)
            else:
                c = count_keyword_occurrences(lower_text, kw, aliases=aliases)

            if c <= 0:
                continue

            await self.bot.dbx.execute(
                """
                INSERT INTO word_counts (guild_id, channel_id, user_id, word, count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, channel_id, user_id, word)
                -- Postgres needs qualification here (count exists in both target table and EXCLUDED)
                DO UPDATE SET count = word_counts.count + excluded.count,
                              updated_at = excluded.updated_at
                """,
                (gid, cid, uid, kw, int(c), now),
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(TrackerCog(bot))
