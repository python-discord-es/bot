import discord
import base64
from datetime import datetime



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
