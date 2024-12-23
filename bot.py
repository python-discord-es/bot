import asyncio
import pandas as pd
import discord
import logging
from discord.ext import commands
from datetime import datetime

from configuration import Config
from messages import Messages

# Add cogs
from comandos.ping import Ping
from comandos.encuesta import Encuesta
from comandos.moderacion import Moderacion
from comandos.ayuda import Ayuda
from comandos.flood import FloodSpam
from comandos.limpia import Limpia
from comandos.archivar import Archivar
from comandos.enviar import Enviar
from comandos.roles import Roles

# Global instance of the server
guild = None

# Configuration
config = Config()

# Use '%' as command prefix
intents = discord.Intents().all()
bot = commands.Bot(command_prefix="%", intents=intents)

handler = logging.FileHandler(filename="bot.log", encoding="utf-8", mode="w")
discord.utils.setup_logging(level=logging.INFO, handler=handler)


@bot.event
async def on_message(message):
    # Main log
    with open(config.log_main_file, "a") as f:
        date_str = f"{datetime.now()}"
        line = (
            f'"{date_str}";'
            f'"{message.id}";'
            f'"{message.channel}";'
            f'"{message.author.id}";'
            f'"{message.author}";'
            f'"{message.content}"\n'
        )
        f.write(line)


@bot.event
async def on_ready():
    print("Syncing tree...")
    # await bot.tree.sync()


# This function will monitor all the messages, even if they are from
# before the bot became online.
# The difference with the "on_reaction_add", is that the signature is
# different, and we need to find the message by the 'payload' ID first.
@bot.event
async def on_raw_reaction_add(payload):
    global guild
    if not guild:
        # guild = bot.get_guild(payload.guild_id)
        guild = bot.get_guild(config.GUILD)
    channel = guild.get_channel(payload.channel_id)

    if channel is None:
        print(f"Couldn't get instance of channel {payload.channel_id}")
        return

    try:
        message = await channel.fetch_message(payload.message_id)

        if message.content.startswith("**Encuesta "):
            # We don't allow reactions from other bots
            if not payload.member.bot:
                for r in message.reactions:
                    if not r.me:
                        await message.remove_reaction(payload.emoji, payload.member)
    except discord.errors.NotFound:
        print("ERROR: Reaccion en Mensaje no encontrado")


@bot.event
async def on_command_error(msg, error):
    if isinstance(error, (commands.MissingRole, commands.MissingAnyRole)):
        print(f"MissingRole ERROR: {error}")
    else:
        print(error)


async def main():
    # Reading data
    data_mod = pd.read_csv(str(config.log_mod_file), sep=";", dtype=str)
    data_accepted = pd.read_csv(str(config.log_accepted_file), sep=";", dtype=str)
    data_rejected = pd.read_csv(str(config.log_rejected_file), sep=";", dtype=str)

    # Pending moderation
    # Get 'message_id' from the 'accepted' and 'rejected' files
    ready_ids = set(data_accepted["message_id"]).union(data_rejected["message_id"])

    # keeping the data in the bot instance
    bot.data_mod = data_mod[~data_mod["message_id"].isin(ready_ids)]

    await bot.add_cog(Ping(bot))
    await bot.add_cog(Encuesta(bot))
    await bot.add_cog(Moderacion(bot))
    await bot.add_cog(Ayuda(bot))
    await bot.add_cog(FloodSpam(bot))
    await bot.add_cog(Limpia(bot))
    await bot.add_cog(Archivar(bot))
    await bot.add_cog(Enviar(bot))
    await bot.add_cog(Roles(bot))

    # Removing the help command
    # bot.remove_command("help")

    print("Running...")
    await bot.start(config.TOKEN)


asyncio.run(main())
