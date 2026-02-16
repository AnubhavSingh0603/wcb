from __future__ import annotations

import discord


class PagedEmbedView(discord.ui.View):
    def __init__(
        self,
        embeds: list[discord.Embed],
        *,
        timeout: float = 60,
        author_id: int | None = None,
    ):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.i = 0
        self.author_id = author_id
        self._sync_buttons()

    def _sync_buttons(self):
        self.prev_btn.disabled = self.i <= 0
        self.next_btn.disabled = self.i >= len(self.embeds) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id is None:
            return True
        return interaction.user.id == self.author_id

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
