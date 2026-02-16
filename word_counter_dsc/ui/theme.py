import discord


class Theme:
    """Royal + minimal theme."""

    BG = 0x0B0F14
    GOLD = 0xD4AF37
    BLUE = 0x3B82F6
    PURPLE = 0x7C3AED
    EMERALD = 0x10B981
    CRIMSON = 0xDC2626
    SLATE = 0x94A3B8

    @staticmethod
    def medal_color(tier_name: str) -> int:
        name = (tier_name or "").lower()
        if name == "squire":
            return Theme.SLATE
        if name == "knight":
            return Theme.BLUE
        if name == "baron":
            return Theme.PURPLE
        if name == "duke":
            return Theme.GOLD
        if name == "archduke":
            return Theme.EMERALD
        if name == "sovereign":
            return Theme.CRIMSON
        return Theme.BLUE


def base_embed(title: str, description: str | None = None, *, color: int | None = None) -> discord.Embed:
    e = discord.Embed(title=title, description=description or "", color=color or Theme.BLUE)
    e.set_footer(text="Word Counter DSC")
    return e
