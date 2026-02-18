# word_counter_dsc/main.py
from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord.ext import commands

from word_counter_dsc.database import init_db, Database

# Extensions list (keep updated)
EXTENSIONS = [
    "word_counter_dsc.cogs.tracker",
    "word_counter_dsc.cogs.search",
    "word_counter_dsc.cogs.keyword",
    "word_counter_dsc.cogs.stopwords",
    "word_counter_dsc.cogs.help_cmd",
    "word_counter_dsc.cogs.medals",
    "word_counter_dsc.cogs.profile",
    # optional:
    # "word_counter_dsc.cogs.settings",
    # "word_counter_dsc.cogs.stats",
    # "word_counter_dsc.cogs.analytics",
]

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("word_counter_dsc")


class WCBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        # Needed for counting messages content:
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        # keep a logger attribute (your medals.py expects it)
        self.logger = logger

        # db handle
        self.dbx: Database | None = None

    async def setup_hook(self):
        # init db
        self.dbx = await init_db()
        logger.info("DB initialized: %s", type(self.dbx).__name__)

        # load extensions but don't hard-crash if one fails
        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                logger.info("Loaded extension: %s", ext)
            except Exception:
                logger.exception("Failed loading extension %s", ext)

        # sync commands
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d slash commands.", len(synced))
        except Exception:
            logger.exception("Slash command sync failed")

        logger.info("If counting is not working, enable MESSAGE CONTENT INTENT in the Discord Developer Portal.")


async def main():
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN env var not set (Render Environment).")

    bot = WCBot()
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
