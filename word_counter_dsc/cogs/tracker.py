import discord
from discord.ext import commands

from word_counter_dsc.config import COUNT_MODE
from word_counter_dsc.utils import (
    tokenize,
    counter_from_mode,
    BUILTIN_STOPWORDS,
    count_keyword_hits,
)


class Tracker(commands.Cog):
    """
    Message ingest:
      - tokenizes and stores word counts (excluding stopwords)
      - additionally, for ACTIVE keywords, counts permissive variants (plurals/verbs/in-word use)
        and credits them to the canonical keyword in the DB.
        Example: keyword='fuck' counts 'fucks', 'fucking', 'motherfucker', 'abso-fucking-lutely', etc.
      - abbreviation mapping (server-configurable): tokens like 'wtf' can be mapped to a keyword.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        content = message.content or ""
        words_all = tokenize(content)
        if not words_all:
            return

        inc = counter_from_mode(words_all, COUNT_MODE)

        # Built-in stopwords
        for sw in BUILTIN_STOPWORDS:
            inc.pop(sw, None)

        # Server stopwords (excluded from counting going forward)
        async with self.bot.db_lock:
            rows = await self.bot.dbx.fetchall(
                "SELECT word FROM stopwords WHERE guild_id=?",
                (message.guild.id,),
            )
        for (w,) in rows:
            inc.pop(w, None)

        # Load ACTIVE keywords + abbreviations (best-effort, should never break counting)
        active_keywords: list[str] = []
        abbrev_map: dict[str, str] = {}
        try:
            async with self.bot.db_lock:
                kw_rows = await self.bot.dbx.fetchall(
                    "SELECT keyword FROM keywords WHERE guild_id=? AND removed_at IS NULL",
                    (message.guild.id,),
                )
                ab_rows = await self.bot.dbx.fetchall(
                    "SELECT abbr, keyword FROM keyword_abbreviations WHERE guild_id=?",
                    (message.guild.id,),
                )
            active_keywords = [r[0] for r in kw_rows]
            abbrev_map = {a: k for a, k in ab_rows}
        except Exception:
            active_keywords = []
            abbrev_map = {}

        # Upgrade counts for active keywords using permissive matching.
        # Avoid double counting: if exact token counts already exist for the keyword,
        # only add the "extra" hits.
        if active_keywords:
            for kw in active_keywords:
                raw_hits = count_keyword_hits(content, kw, abbrev_to_keyword=abbrev_map)
                if COUNT_MODE == "UNIQUE":
                    desired = 1 if raw_hits > 0 else 0
                else:
                    desired = raw_hits

                if desired <= 0:
                    continue

                current = int(inc.get(kw, 0))
                if desired > current:
                    inc[kw] = desired

        if not inc:
            return

        async with self.bot.db_lock:
            for w, delta in inc.items():
                await self.bot.dbx.execute(
                    """
                    INSERT INTO word_counts (guild_id, channel_id, user_id, word, count)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id, channel_id, user_id, word)
                    DO UPDATE SET count = word_counts.count + excluded.count
                    """,
                    (message.guild.id, message.channel.id, message.author.id, w, int(delta)),
                )
            await self.bot.dbx.commit()

        medals_cog = self.bot.get_cog("MedalsCog")
        if medals_cog is not None:
            try:
                await medals_cog.handle_message_keywords(message, inc)
            except Exception:
                # medals must not break counting
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Tracker(bot))
