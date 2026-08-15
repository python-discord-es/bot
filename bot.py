import asyncio
import csv
import discord
import logging
from discord.ext import commands
from datetime import datetime

from configuration import Config
from utils import read_csv_dicts

# Add cogs
from comandos.ping import Ping
from comandos.moderacion import Moderacion
from comandos.ayuda import Ayuda
from comandos.flood import FloodSpam
from comandos.limpia import Limpia
from comandos.archivar import Archivar
from comandos.enviar import Enviar
from comandos.retencion import Retencion

# Every cog to register on startup. Add a class here (and to the imports
# above) to wire up a new command/listener group - nothing else needs to
# change.
COGS = (Ping, Ayuda, Limpia, Archivar, Moderacion, FloodSpam, Enviar, Retencion)

# Global instance of the server
guild = None

# Configuration
config = Config()

# Use '%' as command prefix
intents = discord.Intents().all()
bot = commands.Bot(command_prefix="%", intents=intents)

handler = logging.FileHandler(filename="bot.log", encoding="utf-8", mode="w")
discord.utils.setup_logging(level=logging.INFO, handler=handler)
logger = logging.getLogger(__name__)


@bot.event
async def on_message(message: discord.Message):
    # Main log. Uses csv.writer (not hand-built quoting) so a message
    # containing a literal '"' or a newline - both common in real messages -
    # doesn't silently corrupt the row.
    with open(config.log_main_file, "a", newline="") as f:
        date_str = f"{datetime.now()}"
        csv.writer(f, delimiter=";").writerow([
            date_str,
            "",  # command - this log covers every message, not just commands
            message.id,
            message.channel,
            message.author.id,
            message.author,
            message.content,
        ])


@bot.event
async def on_ready():
    logger.info("Syncing tree...")
    # await bot.tree.sync()


@bot.event
async def on_command_error(msg, error):
    if isinstance(error, (commands.MissingRole, commands.MissingAnyRole)):
        logger.warning("MissingRole ERROR: %s", error)
    else:
        logger.error("Unhandled command error", exc_info=error)


async def main():
    # Reading data
    data_mod = read_csv_dicts(config.log_mod_file)
    data_accepted = read_csv_dicts(config.log_accepted_file)
    data_rejected = read_csv_dicts(config.log_rejected_file)

    # Pending moderation
    # Get 'message_id' from the 'accepted' and 'rejected' files
    ready_ids = {row["message_id"] for row in data_accepted} | {
        row["message_id"] for row in data_rejected
    }

    # keeping the data in the bot instance, keyed by message_id
    bot.data_mod = {  # type: ignore[attr-defined]
        row["message_id"]: row for row in data_mod if row["message_id"] not in ready_ids
    }

    for cog_cls in COGS:
        await bot.add_cog(cog_cls(bot))

    # Removing the help command
    # bot.remove_command("help")

    logger.info("Running...")
    await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
