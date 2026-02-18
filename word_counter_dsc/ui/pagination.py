from __future__ import annotations

import discord


class PagedEmbedView(discord.ui.View):
    """
    Simple Prev/Next embed paginator.
    """

    def __init__(self, embeds: list[discord.Embed], author_id: int, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.author_id = author_id
        self.i = 0
        self._sync_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user is not None and interaction.user.id == self.author_id

    def _sync_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label == "Prev":
                    item.disabled = self.i <= 0
                elif item.label == "Next":
                    item.disabled = self.i >= len(self.embeds) - 1

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.i = max(0, self.i - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.i], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.i = min(len(self.embeds) - 1, self.i + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.i], view=self)


class Paginator:
    """
    Backwards-compatible wrapper expected by cogs.
    """

    def __init__(self, pages: list[discord.Embed], author_id: int, timeout: float = 120):
        self.pages = pages
        self.author_id = author_id
        self.timeout = timeout

    async def send(
        self,
        interaction: discord.Interaction,
        *,
        ephemeral: bool = False,
        allowed_mentions: discord.AllowedMentions | None = None,
    ) -> None:
        view = None
        embed = self.pages[0] if self.pages else discord.Embed(description="(no pages)")
        if len(self.pages) > 1:
            view = PagedEmbedView(self.pages, author_id=self.author_id, timeout=self.timeout)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral, allowed_mentions=allowed_mentions)
        else:
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=ephemeral, allowed_mentions=allowed_mentions
            )
