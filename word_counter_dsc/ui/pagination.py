# word_counter_dsc/ui/pagination.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import discord


@dataclass
class Page:
    embed: discord.Embed


class Paginator(discord.ui.View):
    """
    Simple button paginator for Embeds.
    Usage:
        pages = [discord.Embed(...), ...]
        view = Paginator(interaction, pages)
        await view.start()
    """

    def __init__(
        self,
        interaction: discord.Interaction,
        embeds: List[discord.Embed],
        *,
        timeout: float = 120.0,
        ephemeral: bool = False,
    ):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.embeds = embeds
        self.index = 0
        self.ephemeral = ephemeral
        self._message: Optional[discord.Message] = None

        self._sync_button_state()

    def _sync_button_state(self):
        n = len(self.embeds)
        self.prev_btn.disabled = (n <= 1) or (self.index <= 0)
        self.next_btn.disabled = (n <= 1) or (self.index >= n - 1)
        self.page_btn.label = f"{self.index + 1}/{max(1, n)}"

    async def start(self):
        self._sync_button_state()
        # First response
        if not self.interaction.response.is_done():
            await self.interaction.response.send_message(
                embed=self.embeds[self.index],
                view=self,
                ephemeral=self.ephemeral,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            self._message = await self.interaction.original_response()
        else:
            # In case already responded
            self._message = await self.interaction.followup.send(
                embed=self.embeds[self.index],
                view=self,
                ephemeral=self.ephemeral,
                allowed_mentions=discord.AllowedMentions.none(),
            )

    async def _update(self, interaction: discord.Interaction):
        self._sync_button_state()
        await interaction.response.edit_message(
            embed=self.embeds[self.index],
            view=self,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
        await self._update(interaction)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # label-only button (disabled), no action
        return

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.embeds) - 1:
            self.index += 1
        await self._update(interaction)

    async def on_timeout(self):
        # disable buttons once timed out
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self._message:
            try:
                await self._message.edit(view=self)
            except Exception:
                pass
