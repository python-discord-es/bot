import re
import discord
from datetime import datetime

from configuration import Config

config = Config()


def get_moderation_channel(bot, channel_id):
    channel_mod = bot.get_channel(channel_id)
    return channel_mod


def get_message_to_moderate(message):
    aceptar_emoji = "\N{WHITE HEAVY CHECK MARK}"
    rechazar_emoji = "\N{CROSS MARK}"
    msg = (
        f"{datetime.utcnow()} UTC\n"
        f"Mensaje enviado desde {message.channel.mention} por {message.author.mention}\n\n"
        f"```\n{message.content}\n```\n\n**¿Cumple con todos los requisitos?**\n\n"
        f"{aceptar_emoji} Para aceptarlo, envía el siguiente mensaje:\n\n"
        f"`%aceptar {message.id}`\n\n"
        f"{rechazar_emoji} Para rechazarlo, envía el siguiente mensaje:\n\n"
        f"`%rechazar {message.id} 'razón del rechazo'`"
    )
    embed = discord.Embed(
        title="Moderación de mensaje",
        description=msg,
        colour=0x2B597B,
    )

    return embed


def strip_message(message):
    m = message[:].lower()

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
    m = re.sub(r"\ +", " ", m)

    return m.strip()
