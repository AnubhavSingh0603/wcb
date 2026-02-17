import os
import sys
import logging
import asyncio
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv

from word_counter_dsc.database import init_db

LOG = logging.getLogger("word_counter_dsc")


def _ensure_project_root_on_syspath():
    # Allows running as: python word_counter_dsc/main.py
    # while still importing word_counter_dsc.*
    this_file = os.path.abspath(__file__)
    pkg_dir = os.path.dirname(this_file)              # .../word_counter_dsc
    project_root = os.path.dirname(pkg_dir)           # .../ (parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def load_token() -> str | None:
    load_dotenv()
    tok = os.getenv("DISCORD_TOKEN", "").strip()
    tok = tok.strip('"').strip("'").strip()
    return tok or None


def validate_token_format(token: str) -> tuple[bool, str]:
    if len(token) < 30:
        return False, "Token looks too short. Make sure you copied the BOT TOKEN (not Client Secret)."
    if " " in token or "\n" in token or "\r" in token or "\t" in token:
        return False, "Token contains whitespace/newlines. Remove them."
    return True, "ok"


def build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True  # required for on_message tracking
    bot = commands.Bot(command_prefix="!", intents=intents, allowed_mentions=discord.AllowedMentions.none())

    # --------- GLOBAL APP COMMAND ERROR HANDLER ----------
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: Exception):
        # Print full traceback to terminal
        LOG.error("App command error: %s", repr(error))
        traceback.print_exception(type(error), error, error.__traceback__)

        # Try to respond to user (ephemeral)
        try:
            msg = f"❌ Error: `{type(error).__name__}` — {error}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    # --------- INTERACTION TRACE LOGGING ----------
    @bot.listen("on_interaction")
    async def on_interaction_debug(interaction: discord.Interaction):
        # Helps confirm Discord is delivering interactions
        if interaction.type == discord.InteractionType.application_command:
            try:
                name = interaction.data.get("name") if interaction.data else "unknown"
            except Exception:
                name = "unknown"
            LOG.info(
                "Interaction received: /%s | guild=%s channel=%s user=%s",
                name,
                getattr(interaction.guild, "id", None),
                getattr(interaction.channel, "id", None),
                getattr(interaction.user, "id", None),
            )

    @bot.event
    async def on_ready():
        LOG.info("Logged in as %s (id=%s)", bot.user, bot.user.id)

        await init_db(bot)

        # Load cogs
        for ext in (
            "word_counter_dsc.cogs.tracker",
            "word_counter_dsc.cogs.search",
            "word_counter_dsc.cogs.keyword",
            "word_counter_dsc.cogs.stopwords",
            "word_counter_dsc.cogs.help_cmd",
            "word_counter_dsc.cogs.medals",
            "word_counter_dsc.cogs.profile",
        ):
            try:
                await bot.load_extension(ext)
                LOG.info("Loaded extension: %s", ext)
            except Exception as e:
                LOG.error("Failed loading extension %s: %s", ext, e)
                traceback.print_exception(type(e), e, e.__traceback__)

        # Sync slash commands
        try:
            synced = await bot.tree.sync()
            LOG.info("Synced %d slash commands.", len(synced))
        except Exception as e:
            LOG.error("Slash sync failed: %s", e)
            traceback.print_exception(type(e), e, e.__traceback__)

    return bot


async def main_async(test_mode: bool = False) -> int:
    token = load_token()
    if not token:
        LOG.error("DISCORD_TOKEN not set. Put it in .env: DISCORD_TOKEN=YOUR_BOT_TOKEN")
        return 2

    ok, why = validate_token_format(token)
    if not ok:
        LOG.error("Token problem: %s", why)
        return 2

    bot = build_bot()

    if test_mode:
        await init_db(bot)
        # IMPORTANT: close DB to avoid hanging process on Windows
        try:
            await bot.db.close()
        except Exception:
            pass
        LOG.info("TEST_MODE OK (DB init succeeded).")
        return 0

    try:
        await bot.start(token)
        return 0
    except discord.LoginFailure:
        LOG.error("401 Unauthorized: invalid bot token.")
        return 3
    except Exception as e:
        LOG.error("Fatal start error: %s", e)
        traceback.print_exception(type(e), e, e.__traceback__)
        return 1
    finally:
        try:
            if getattr(bot, "db", None):
                await bot.db.close()
        except Exception:
            pass
        try:
            await bot.close()
        except Exception:
            pass


def main():
    _ensure_project_root_on_syspath()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    test_mode = "--test" in sys.argv
    try:
        code = asyncio.run(main_async(test_mode=test_mode))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        code = 130
    raise SystemExit(code)


if __name__ == "__main__":
    main()
