import discord
from discord.ext import commands

from word_counter_dsc.config import COUNT_MODE
from word_counter_dsc.utils import tokenize, counter_from_mode, BUILTIN_STOPWORDS


class Tracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        words_all = tokenize(message.content)
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
