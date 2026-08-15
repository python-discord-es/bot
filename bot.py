import asyncio
import csv
import pandas as pd
import discord
import logging
from discord.ext import commands
from datetime import datetime

from configuration import Config

# Add cogs
from comandos.ping import Ping
from comandos.moderacion import Moderacion
from comandos.ayuda import Ayuda
from comandos.flood import FloodSpam
from comandos.limpia import Limpia
from comandos.archivar import Archivar
from comandos.enviar import Enviar

# Every cog to register on startup. Add a class here (and to the imports
# above) to wire up a new command/listener group - nothing else needs to
# change.
COGS = (Ping, Ayuda, Limpia, Archivar, Moderacion, FloodSpam, Enviar)

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
    data_mod = pd.read_csv(str(config.log_mod_file), sep=";", dtype=str)
    data_accepted = pd.read_csv(str(config.log_accepted_file), sep=";", dtype=str)
    data_rejected = pd.read_csv(str(config.log_rejected_file), sep=";", dtype=str)

    # Pending moderation
    # Get 'message_id' from the 'accepted' and 'rejected' files
    ready_ids = set(data_accepted["message_id"]).union(data_rejected["message_id"])

    # keeping the data in the bot instance
    bot.data_mod = data_mod[~data_mod["message_id"].isin(ready_ids)]  # type: ignore[attr-defined]

    for cog_cls in COGS:
        await bot.add_cog(cog_cls(bot))

    # Removing the help command
    # bot.remove_command("help")

    logger.info("Running...")
    await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
