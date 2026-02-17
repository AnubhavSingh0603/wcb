import asyncio
import logging
import os
import sys
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv

from word_counter_dsc.database import init_db
from word_counter_dsc.config import (
    BOT_TOKEN,
    LOG_LEVEL,
    EXTENSIONS,
    REQUIRE_MESSAGE_CONTENT_INTENT,
)

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format=LOG_FORMAT)
log = logging.getLogger("word_counter_dsc")


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


async def main():
    load_dotenv()

    token = BOT_TOKEN or os.getenv("DISCORD_BOT_TOKEN") or os.getenv("TOKEN") or ""
    if not token or len(token) < 20:
        log.error(
            "Token problem: Token looks too short. Make sure you copied the BOT TOKEN (not Client Secret)."
        )
        sys.exit(1)

    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    intents.messages = True

    # IMPORTANT: required to read message content for counting in most servers
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)
    # Prevent any <@id> strings from pinging users/roles/everyone
    bot.allowed_mentions = discord.AllowedMentions.none()

    bot.dbx = None
    bot.db_lock = asyncio.Lock()

    @bot.event
    async def on_ready():
        log.info(f"Logged in as {bot.user} (id={bot.user.id})")

    @bot.event
    async def setup_hook():
        # init DB
        try:
            bot.dbx = await init_db()
        except Exception as e:
            log.error("DB init failed: %s", e)
            traceback.print_exc()
            raise

        # load extensions
        for ext in EXTENSIONS:
            try:
                await bot.load_extension(ext)
                log.info("Loaded extension: %s", ext)
            except Exception as e:
                log.error("Failed loading extension %s: %s", ext, e)
                traceback.print_exc()

        # sync slash commands
        try:
            synced = await bot.tree.sync()
            log.info("Synced %d slash commands.", len(synced))
        except Exception as e:
            log.error("Slash command sync failed: %s", e)
            traceback.print_exc()

        # basic warning if intent not enabled in dev portal
        if REQUIRE_MESSAGE_CONTENT_INTENT:
            if not bot.intents.message_content:
                log.warning("Message Content Intent is OFF in code.")
            # Cannot detect portal setting from code reliably; we still warn.
            log.info(
                "If counting is not working, enable MESSAGE CONTENT INTENT in the Discord Developer Portal."
            )

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        log.error("App command error: %r", error, exc_info=True)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ Error: `{type(error).__name__}`. Check logs.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Error: `{type(error).__name__}`. Check logs.", ephemeral=True
                )
        except Exception:
            pass

    try:
        await bot.start(token)
    finally:
        try:
            if bot.dbx is not None:
                await bot.dbx.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
