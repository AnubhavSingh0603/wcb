import discord
from discord.ext import commands
from discord import app_commands

from word_counter_dsc.ui.pagination import Paginator
from word_counter_dsc.ui.theme import base_embed, Theme
from word_counter_dsc.utils import (
    user_link_no_ping,
    medal_rank_for_count,
    medal_emoji,
    medal_title,
    medal_progress_text,
    BUILTIN_STOPWORDS,
)


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _top3_keyword_game(self, guild_id: int, user_id: int):
        rows = await self.bot.dbx.fetch(
            """
            SELECT
                k.keyword AS keyword,
                COALESCE(SUM(w.count), 0) AS total
            FROM keywords k
            LEFT JOIN word_counts w
              ON w.guild_id = k.guild_id
             AND w.word = k.keyword
             AND w.user_id = ?
            WHERE k.guild_id = ?
              AND k.is_active = 1
            GROUP BY k.keyword
            ORDER BY total DESC, k.keyword ASC
            LIMIT 3
            """,
            user_id,
            guild_id,
        )
        out = []
        for r in rows:
            kw = str(r["keyword"])
            total = int(r["total"])
            tier, rank, next_thr = medal_rank_for_count(total)
            out.append(
                {"keyword": kw, "total": total, "tier": tier, "rank": rank, "next": next_thr}
            )
        return out

    async def _most_used_word(self, guild_id: int, user_id: int):
        row = await self.bot.dbx.fetchrow(
            """
            SELECT word, SUM(count) AS total
            FROM word_counts
            WHERE guild_id = ? AND user_id = ?
            GROUP BY word
            ORDER BY total DESC, word ASC
            LIMIT 1
            """,
            guild_id,
            user_id,
        )
        if not row:
            return None
        return str(row["word"]), int(row["total"])

    async def _most_unique_word(self, guild_id: int, user_id: int):
        # Heuristic: among words used only once, pick the longest
        rows = await self.bot.dbx.fetch(
            """
            SELECT word, SUM(count) AS total
            FROM word_counts
            WHERE guild_id = ? AND user_id = ?
            GROUP BY word
            HAVING SUM(count) = 1
            ORDER BY LENGTH(word) DESC, word ASC
            LIMIT 1
            """,
            guild_id,
            user_id,
        )
        if not rows:
            return None
        r = rows[0]
        return str(r["word"]), int(r["total"])

    def _render_game_lines(self, game_items):
        if not game_items:
            return ["No keywords configured yet. Use `/keyword list` to see what's being tracked."]
        lines = []
        for it in game_items:
            kw = it["keyword"]
            total = it["total"]
            rank = it["rank"]
            nxt = it["next"]
            emoji = medal_emoji(rank)
            title = medal_title(rank, kw)
            prog = medal_progress_text(total, nxt)
            lines.append(f"{emoji} **{title}** — {prog}")
        return lines

    def _clean_word_for_display(self, w: str) -> str:
        w = (w or "").strip()
        if not w:
            return w
        if w.lower() in BUILTIN_STOPWORDS:
            return f"{w} (common word)"
        return w

    async def _build_profile_pages(self, interaction: discord.Interaction, user: discord.abc.User):
        assert interaction.guild is not None
        guild_id = int(interaction.guild.id)
        user_id = int(user.id)

        game = await self._top3_keyword_game(guild_id, user_id)
        most_used = await self._most_used_word(guild_id, user_id)
        most_unique = await self._most_unique_word(guild_id, user_id)

        header = f"{user_link_no_ping(user_id)}"

        # Page 1: Game / medals (top3)
        lines = self._render_game_lines(game)
        e1 = base_embed(
            title="⚔️ Hall of Deeds",
            description="\n".join([header, "", "**Top keyword titles**", *lines]),
            color=Theme.INFO,
        )

        # Page 2: Fun facts
        fact_lines = [header, ""]
        if most_used:
            w, c = most_used
            fact_lines.append(f"**Most used tracked word:** `{self._clean_word_for_display(w)}` (**{c:,}**)")
        if most_unique:
            w, _c = most_unique
            fact_lines.append(f"**Most unique tracked word:** `{w}`")
        if len(fact_lines) == 2:
            fact_lines.append("No stats yet — start chatting and I’ll build your profile over time.")

        e2 = base_embed(
            title="📜 Wordcraft Summary",
            description="\n".join(fact_lines),
            color=Theme.INFO,
        )

        return [e1, e2]

    # ---- Commands ----
    @app_commands.command(name="me", description="Show your WordCounter profile.")
    async def me(self, interaction: discord.Interaction):
        await self.userprofile(interaction, user=None)

    @app_commands.command(name="profile", description="Show a user's WordCounter profile.")
    @app_commands.describe(user="Optional user to view (defaults to you)")
    async def userprofile(self, interaction: discord.Interaction, user: discord.Member | None = None):
        user = user or interaction.user
        pages = await self._build_profile_pages(interaction, user)

        paginator = Paginator(pages=pages, author_id=interaction.user.id, timeout=60)
        await paginator.send(
            interaction,
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
