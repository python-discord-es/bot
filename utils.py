import csv
import re
import discord
from datetime import datetime, timezone

import colors
from configuration import Config

config = Config()


aceptar_emoji = "\N{WHITE HEAVY CHECK MARK}"
rechazar_emoji = "\N{CROSS MARK}"


def read_csv_dicts(path, delimiter=";"):
    """Read a semicolon-delimited CSV file (as written by csv.writer
    elsewhere in this project) into a list of {column: value} dicts."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def get_message_to_moderate(message):
    msg = (
        f"{datetime.now(timezone.utc).replace(tzinfo=None)} UTC\n"
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
        colour=colors.BRAND,
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
