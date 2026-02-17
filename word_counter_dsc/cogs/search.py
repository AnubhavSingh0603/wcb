import discord
from discord.ext import commands

from word_counter_dsc.config import DEFAULT_TOP_N
from word_counter_dsc.utils import tokenize, user_mention
from word_counter_dsc.ui.theme import base_embed, Theme


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(n)))


class SearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="search",
        description="Search counts (word or keyword-set) across server/channel/user.",
    )
    async def search(
        self,
        interaction: discord.Interaction,
        word: str | None = None,
        user: discord.Member | None = None,
        channel: discord.TextChannel | None = None,
        n: int = DEFAULT_TOP_N,
    ):
        if interaction.guild is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        n = clamp(n, 1, 50)
        guild_id = interaction.guild.id
        ch_id = channel.id if channel else None
        user_id = user.id if user else None

        resolved_word = None
        if word:
            toks = tokenize(word)
            if not toks:
                return await interaction.response.send_message("Invalid word.", ephemeral=True)
            resolved_word = toks[0]

        async with self.bot.db_lock:
            if resolved_word:
                where = ["guild_id=?", "word=?"]
                params = [guild_id, resolved_word]
                if ch_id is not None:
                    where.append("channel_id=?")
                    params.append(ch_id)
                if user_id is not None:
                    where.append("user_id=?")
                    params.append(user_id)
                where_sql = " AND ".join(where)

                if user_id is None:
                    q = f"""
                    SELECT user_id, SUM(count) AS total
                    FROM word_counts
                    WHERE {where_sql}
                    GROUP BY user_id
                    ORDER BY total DESC
                    LIMIT ?
                    """
                    rows = await self.bot.dbx.fetchall(q, (*params, n))
                    title = f'👥 Top users for "{resolved_word}"'
                    fmt = "user"
                elif ch_id is None:
                    q = f"""
                    SELECT channel_id, SUM(count) AS total
                    FROM word_counts
                    WHERE {where_sql}
                    GROUP BY channel_id
                    ORDER BY total DESC
                    LIMIT ?
                    """
                    rows = await self.bot.dbx.fetchall(q, (*params, n))
                    title = f'🗂️ Top channels for "{resolved_word}"'
                    fmt = "channel"
                else:
                    q = f"SELECT COALESCE(SUM(count),0) FROM word_counts WHERE {where_sql}"
                    row = await self.bot.dbx.fetchone(q, params)
                    total = int((row[0] if row else 0) or 0)
                    e = base_embed(
                        title=f"✅ Total for \"{resolved_word}\"",
                        description=f"{user.mention} in {channel.mention}: **{total}**",
                        color=Theme.GOLD,
                    )
                    return await interaction.response.send_message(embed=e)
            else:
                # keyword-set mode
                kws = await self.bot.dbx.fetchall(
                    "SELECT keyword FROM keywords WHERE guild_id=? AND removed_at IS NULL",
                    (guild_id,),
                )
                kws = [r[0] for r in kws]
                if not kws:
                    e = base_embed(
                        "No active keywords",
                        "Add keywords with `/keyword add <word>` first.",
                        color=Theme.SLATE,
                    )
                    return await interaction.response.send_message(embed=e)

                where = ["guild_id=?"]
                params = [guild_id]
                if ch_id is not None:
                    where.append("channel_id=?")
                    params.append(ch_id)
                if user_id is not None:
                    where.append("user_id=?")
                    params.append(user_id)
                where_sql = " AND ".join(where)

                placeholders = ",".join("?" for _ in kws)
                q = f"""
                SELECT word, SUM(count) AS total
                FROM word_counts
                WHERE {where_sql} AND word IN ({placeholders})
                GROUP BY word
                ORDER BY total DESC
                LIMIT ?
                """
                rows = await self.bot.dbx.fetchall(q, (*params, *kws, n))
                title = "🏷️ Keyword totals"
                fmt = "word"

        if not rows:
            e = base_embed("No data found", "Try a different scope or word.", color=Theme.SLATE)
            return await interaction.response.send_message(embed=e)

        e = base_embed(title, color=Theme.BLUE)
        lines = []
        for i, (key, total) in enumerate(rows, start=1):
            if fmt == "user":
                label = user_mention(int(key))
            elif fmt == "channel":
                ch = interaction.guild.get_channel(int(key))
                label = ch.mention if ch else f"`{key}`"
            else:
                label = f"`{key}`"
            lines.append(f"**{i}.** {label} — **{int(total)}**")

        e.description = "\n".join(lines)
        if channel:
            e.add_field(name="Scope", value=f"Channel: {channel.mention}")
        if user:
            e.add_field(name="Scope", value=f"User: {user_mention(user.id)}")

        await interaction.response.send_message(embed=e)

    @discord.app_commands.command(
        name="top",
        description="Top list: users/channels for a word, or keyword totals if word omitted.",
    )
    async def top(
        self,
        interaction: discord.Interaction,
        word: str | None = None,
        channel: discord.TextChannel | None = None,
        n: int = DEFAULT_TOP_N,
    ):
        await self.search.callback(self, interaction, word=word, user=None, channel=channel, n=n)


async def setup(bot: commands.Bot):
    await bot.add_cog(SearchCog(bot))
