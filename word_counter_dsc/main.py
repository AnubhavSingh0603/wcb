# word_counter_dsc/main.py
from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord.ext import commands

# When running this file directly (python word_counter_dsc/main.py) the
# package may not be on sys.path which causes ModuleNotFoundError. Try the
# normal absolute imports first and fall back to inserting the project
# root into sys.path so `word_counter_dsc` can be imported.
try:
    from word_counter_dsc.config import REQUIRE_MESSAGE_CONTENT_INTENT, get_bot_token
    from word_counter_dsc.database import init_db, Database
except ModuleNotFoundError:
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    from word_counter_dsc.config import REQUIRE_MESSAGE_CONTENT_INTENT, get_bot_token
    from word_counter_dsc.database import init_db, Database

EXTENSIONS = [
    "word_counter_dsc.cogs.tracker",
    "word_counter_dsc.cogs.search",
    "word_counter_dsc.cogs.keyword",
    "word_counter_dsc.cogs.stopwords",
    "word_counter_dsc.cogs.help_cmd",
    "word_counter_dsc.cogs.medals",
    "word_counter_dsc.cogs.profile",
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
        intents.guilds = True
        intents.members = True  # for resolving display names in guild
        intents.messages = True
        intents.message_content = bool(REQUIRE_MESSAGE_CONTENT_INTENT)

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        # a logger attribute (some cogs expect it)
        self.logger = logger

        self.dbx: Database | None = None

    async def setup_hook(self):
        self.dbx = await init_db()
        logger.info("DB initialized: %s", type(self.dbx).__name__)

        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                logger.info("Loaded extension: %s", ext)
            except Exception:
                logger.exception("Failed loading extension %s", ext)

        try:
            synced = await self.tree.sync()
            logger.info("Synced %d slash commands.", len(synced))
        except Exception:
            logger.exception("Slash command sync failed")

        if REQUIRE_MESSAGE_CONTENT_INTENT:
            logger.info("If counting is not working, enable MESSAGE CONTENT INTENT in the Discord Developer Portal.")
        else:
            logger.info("Message counting is disabled (REQUIRE_MESSAGE_CONTENT_INTENT=0).")


async def main():
    token = get_bot_token().strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN (or BOT_TOKEN) env var not set (Render Environment).")

    bot = WCBot()
    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
