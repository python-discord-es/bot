import re
import time
import base64

import pandas as pd
import discord
from discord.ext import commands, tasks
from datetime import datetime
from typing import List

from configuration import Config
from messages import Messages

from utils import get_message_to_moderate

# Use '%' as command prefix
intents = discord.Intents().all()
bot = commands.Bot(command_prefix="%", intents=intents)

# Configuration
config = Config()
config.setup_log_files()

messages = Messages()
messages.spam = config.get_spam_messages()
messages.normal = {}

# Global instance of the server
guild = None

FLOOD_LIMIT = 3
MENTIONS_LIMIT = 3

def add_spam_message(message):
    global messages.spam
    with open(config.log_spam_file, "a") as f:
        f.write(f"{message}\n")
    messages.spam.add(message)


def get_moderation_channel(current_id):
    for channel, values in config.CHANNELS.items():
        if current_id == values["moderation"]:
            channel_mod = bot.get_channel(values["moderation"])
            return channel_mod
    return None


async def spam_check(message):
    global main_mod_channel
    spam_words = [
        ("discord", "nitro", "free", "http"),
        ("discord", "nitro", "gift", "http"),
        ("discord", "nitro", "month", "http"),
        ("discord", "gift", "http"),
        ("discord", "free", "http"),
        ("discord", "month", "http"),
        ("nitro", "free", "http"),
        ("nitro", "gift", "http"),
        ("nitro", "month", "http"),
        ("free", "gift", "http"),
        ("everyone", "gift", "http"),
        ("everyone", "free", "http"),
    ]

    if message.author.id != config.BOT_ID:
        if not main_mod_channel:
            main_mod_channel = bot.get_channel(config.MOD_MAIN)
        content = message.content.lower()
        if any(all(i in content for i in sw) for sw in spam_words):
            msg = (
                f"  **User:** {message.author.mention}\n"
                f"  **Mensaje:**\n "
                f"```"
                f"{message.content}"
                f"```\n\n"
                "En caso de ser SPAM, recuerda hacer `click-derecho` sobre el nickname y **banear**."
            )
            embed = discord.Embed(
                title="\N{WARNING SIGN} Alerta de posible SPAM",
                description=msg,
                colour=0xFF0000,
            )
            await main_mod_channel.send(embed=embed)
            return True
    return False


async def flood_check(message):
    global main_mod_channel, messages.normal, guild

    if message.author.id != config.BOT_ID:
        if not main_mod_channel:
            main_mod_channel = bot.get_channel(config.MOD_MAIN)

        _channel = bot.get_channel(message.channel.id)
        _content = strip_message(message.content.strip())
        _author = message.author

        if _author not in messages.normal:
            messages.normal[_author] = {_content: 1}
        else:
            if _content not in messages.normal[_author]:
                messages.normal[_author][_content] = 1
            else:
                messages.normal[_author][_content] += 1
                if messages.normal[_author][_content] >= config.FLOOD_LIMIT:

                    add_spam_message(strip_message(_content))
                    await alert_moderation(
                        main_mod_channel, _author, _content, "Alerta de Flood", "flood"
                    )

                    # Set muted role
                    role = discord.utils.get(_author.guild.roles, name=config.MUTED_ROLE)
                    await _author.add_roles(role)

                    # Reset author counters
                    messages.normal[_author] = {}

                    # Send message notifying the user is muted
                    await _channel.send(
                        f"Usuario {_author.mention} silenciado por enviar mensajes repetitivos. "
                        f"El equipo de coordinación ha sido notificado."
                    )


async def alert_moderation(channel, author, content, title, reason):
    global main_mod_channel, guild

    if not guild:
        guild = bot.get_guild(config.GUILD)

    coord_role = discord.utils.get(guild.roles, name=config.MOD_ROLE)
    d_msg = {
        "menciones": f"{coord_role.mention} Se detectó un mensaje con muchas menciones de {author.mention} y se ha muteado.",
        "flood": f"{coord_role.mention} Se detectaton mensajes repetitivos de {author.mention} y se ha muteado.",
        "known": f"{coord_role.mention} Se detectó un mensaje previamente reconocido como spam de {author.mention} y se ha muteado.",
    }
    msg = d_msg[reason]
    e = discord.Embed(
        title=f"\N{NO ENTRY} {title}",
        description=msg,
        colour=0x2B597B,
    )
    e.add_field(name="Mensaje", value=f"{content}", inline=False)
    e.add_field(
        name="En caso de ser spam",
        value=(
            "Recuerda banear al usuario haciendo click derecho sobre su "
            "nick y seleccionando la opción 'Ban'"
        ),
        inline=False,
    )
    e.add_field(
        name="En caso de ser un error",
        value=(
            'Remueve el rol "Muted" haciendo click derecho en el nick, '
            'luego "Roles" y deselecciona el rol "Muted".'
        ),
        inline=False,
    )
    await channel.send(embed=e)


async def mention_check(message):
    global main_mod_channel, guild

    if message.author.id != config.BOT_ID:
        if not main_mod_channel:
            main_mod_channel = bot.get_channel(config.MOD_MAIN)

        # Skip if 2 mentions or less
        if len(message.mentions) + len(message.role_mentions) < config.MENTIONS_LIMIT:
            return False

        _channel = bot.get_channel(message.channel.id)
        _content = message.content.strip()
        _author = message.author

        await alert_moderation(
            main_mod_channel, _author, _content, "Alerta de Flood (Menciones)", "menciones"
        )

        # Set muted role
        role = discord.utils.get(_author.guild.roles, name=config.MUTED_ROLE)
        await _author.add_roles(role)

        # Send message notifying the user is muted
        await _channel.send(
            f"Usuario {_author.mention} silenciado por hacer muchas menciones. "
            f"El equipo de coordinación ha sido notificado."
        )
        return True


def strip_message(message):
    m = message[:]

    # Remove newlines, and tabs
    ft = (
        ("\n", " "),
        ("\r", " "),
        ("\t", " "),
    )
    for f, t in ft:
        m = m.replace(f, t)

    # Remove mentions
    m = re.sub("<@[^>]*>", "", m)

    # Remove multiple whitepaces
    m = re.sub("\ +", " ", m)

    return m.strip()


def main_log(message):
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
async def on_message(message):
    global main_mod_channel, data_mod, messages.spam
    await bot.process_commands(message)

    if message.author.id == config.BOT_ID:
        return

    main_log(message)
    user_roles = message.author.roles
    clean_message = strip_message(message.content)

    if clean_message in messages.spam:
        if not main_mod_channel:
            main_mod_channel = bot.get_channel(config.MOD_MAIN)
        await alert_moderation(
            main_mod_channel,
            message.author,
            clean_message,
            "Alerta de SPAM (Mensaje conocido)",
            "known",
        )

        # Set muted role
        role = discord.utils.get(message.author.guild.roles, name=config.MUTED_ROLE)
        await message.author.add_roles(role)

        await discord.Message.delete(message)
        channel = bot.get_channel(message.channel.id)
        msg = f"El mensaje del usuario {message.author.mention} fue borrado por ser un mensaje detectado previamente como spam.\n"
        embed = discord.Embed(
            title="\N{NO ENTRY} Alerta de posible SPAM",
            description=msg,
            colour=0x2B597B,
        )
        reply_msg = await channel.send(embed=embed)

    # Check first more than 3 mentions
    if await mention_check(message):
        add_spam_message(clean_message)
        _channel_id = message.channel.id
        _author_mention = message.author.mention
        await discord.Message.delete(message)
        channel = bot.get_channel(_channel_id)
        msg = (
            f"El mensaje del usuario {_author_mention} fue borrado por tener muchas menciones y podría ser un engaño.\n"
            "Evita `hacer click` en enlaces de **usuarios que no conozcas**."
        )
        embed = discord.Embed(
            title="\N{NO ENTRY} Alerta de posible SPAM",
            description=msg,
            colour=0x2B597B,
        )
        reply_msg = await channel.send(embed=embed)
    elif len(user_roles) == 1 and await spam_check(message):
        add_spam_message(clean_message)
        await discord.Message.delete(message)
        channel = bot.get_channel(message.channel.id)
        msg = (
            f"El mensaje del usuario {message.author.mention} fue borrado y podría ser un engaño.\n"
            "Evita `hacer click` en enlaces de **usuarios que no conozcas**."
        )
        embed = discord.Embed(
            title="\N{NO ENTRY} Alerta de posible SPAM",
            description=msg,
            colour=0x2B597B,
        )
        reply_msg = await channel.send(embed=embed)
        time.sleep(10)
        await discord.Message.delete(reply_msg)
    else:

        # Check which channel combination we are using
        channel_mod = None
        channel_sub = None
        for channel, values in config.CHANNELS.items():
            if message.channel.id == values["submission"]:
                channel_mod = bot.get_channel(values["moderation"])
                channel_sub = bot.get_channel(values["submission"])

        if len(user_roles) == 1:
            # Check flood per message
            await flood_check(message)

        # Moderación Canal X
        if channel_mod and channel_sub and message.author.id != config.BOT_ID:

            # Log
            # Add the new row to the data_mod, to have it in runtime
            # Add the new entry to the dat_mod file, to have it for the next time
            with open(str(config.log_mod_file), "a") as f:
                # date;message_id;channel;author;message
                message_enc = base64.b64encode(message.content.encode("utf-8"))
                date_str = f"{datetime.now()}"
                line = (
                    f'"{date_str}";'
                    f'"{message.id}";'
                    f'"{channel_sub}";'
                    f'"{message.author.id}";'
                    f'"{message.author}";'
                    f'"{message_enc}"\n'
                )

                # dictionary to add the data to the runtime DataFrame
                new_data = {
                    "date": date_str,
                    "message_id": f"{message.id}",
                    "channel": f"{channel_sub}",
                    "author_id": f"{message.author.id}",
                    "author": f"{message.author}",
                    "message": f"{message_enc}",
                }
                data_mod = data_mod.append(new_data, ignore_index=True)

                # Writing data to the CSV file
                f.write(line)

            embed_reply = discord.Embed(
                title="Mensaje Enviado",
                description=f"Gracias {message.author.mention}, tu mensaje espera moderación.",
                colour=0x2B597B,
            )
            reply_msg = await channel_sub.send(embed=embed_reply)
            e = get_message_to_moderate(message)
            await channel_mod.send(embed=e)
            time.sleep(3)
            await discord.Message.delete(message)

        elif channel_sub:
            time.sleep(3)
            await discord.Message.delete(message)

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
async def on_ready():
    clear_messages.start()
    print("Comenzando deteccion de flood...")


# Remove messages every hour
@tasks.loop(seconds=60 * 60)
async def clear_messages():
    global messages.normal
    messages.normal = {}


@bot.event
async def on_command_error(msg, error):
    if isinstance(error, (commands.MissingRole, commands.MissingAnyRole)):
        print(f"MissingRole ERROR: {error}")
    else:
        print(error)


if __name__ == "__main__":

    # Main moderation channel
    main_mod_channel = None

    # Reading data
    data_mod = pd.read_csv(str(config.log_mod_file), sep=";", dtype=str)
    data_accepted = pd.read_csv(str(config.log_accepted_file), sep=";", dtype=str)
    data_rejected = pd.read_csv(str(config.log_rejected_file), sep=";", dtype=str)

    # Pending moderation
    # Get 'message_id' from the 'accepted' and 'rejected' files
    ready_ids = set(data_accepted["message_id"]).union(data_rejected["message_id"])
    data_mod = data_mod[~data_mod["message_id"].isin(ready_ids)]

    # Add cogs
    from comandos.ping import Ping
    from comandos.encuesta import Encuesta
    from comandos.moderacion import Moderacion
    from comandos.ayuda import Ayuda

    bot.add_cog(Ping(bot))
    bot.add_cog(Encuesta(bot, config.log_file))
    bot.add_cog(Moderacion(bot, config.log_rejected_file, config.log_accepted_file))
    bot.add_cog(Ayuda(bot))

    # Removing the help command
    bot.remove_command("help")

    # Starting the bot
    print("Running...")
    bot.run(config.TOKEN)
