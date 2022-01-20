import discord
import base64
from datetime import datetime


def get_mod_help():
    embed = discord.Embed(
        title="Comandos Disponibles",
        colour=0x2B597B,
    )
    embed.add_field(
        name="`%mod`", value="Lista todos los post pendientes de moderación", inline=False
    )
    embed.add_field(
        name="`%mod ID`",
        value="Lista información del post ID pendiente de moderación",
        inline=False,
    )
    embed.add_field(
        name="`%aceptar ID`", value="Acepta mensaje, lo envia al canal asociado", inline=False
    )
    embed.add_field(
        name="`%rechazar ID RAZON`",
        value=(
            "Rechaza el mensaje ID, lo envia al canal asociado. "
            "El usuario será notificado, con el mensaje RAZON"
        ),
        inline=False,
    )
    embed.add_field(
        name="`%limpia`", value="Limpia N mensajes del canal de moderación", inline=False
    )
    return embed


def get_main_help():
    embed = discord.Embed(
        title="Comandos Disponibles",
        colour=0x2B597B,
    )
    embed.add_field(
        name='`%encuesta "pregunta"`',
        value=("Para hacer preguntas de Sí y No.\n" 'Ejemplo:\n `%encuesta "¿Te gusta el té?"`'),
        inline=False,
    )
    embed.add_field(
        name='`%encuesta "pregunta" "opción a" "opción b" ...`',
        value=(
            "Para hacer preguntas con varias opciones.\n"
            'Ejemplo:\n `%encuesta "¿Lenguaje favorito?" "Inglés" "Español" "Python"`'
        ),
        inline=False,
    )
    embed.set_footer(text='Importante: La pregunta y opciones deben ir entre comillas dobles "..."')
    return embed


def get_mod_pending(data, bot):
    # Imprimir todos los posts que necesitan moderación
    messages = False

    embed = discord.Embed(
        title="Mensajes pendientes de moderación",
        colour=0x2B597B,
    )

    for idx, mod_row in data.iterrows():
        m_date = mod_row["date"]
        m_message_id = mod_row["message_id"]
        m_message = base64.b64decode(eval(mod_row["message"])).decode("utf-8")
        m_author_id = mod_row["author_id"]
        author = bot.get_user(int(m_author_id))

        if author:
            embed.add_field(
                name=f"`{m_message_id}`",
                value=(f"{m_message[:30]}...\n" f"Fecha: `{m_date}`\n" f"Autor: {author.mention}"),
                inline=False,
            )
            if not messages:
                messages = True
        else:
            print(f"El author '{m_author_id}' ya no existe en el server. Mensaje {m_message}")

    if not messages:
        embed.set_footer(text="No hay mensajes pendientes de moderación")

    return embed


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


def get_help_error():
    embed = discord.Embed(
        title="\N{NO ENTRY} No se encontró ningún argumento.\n\n",
        description="**¿Cómo realizar encuestas?**",
        colour=0x2B597B,
    )
    embed.add_field(name="Para preguntas de Sí y No", value='`%encuesta "pregunta"`', inline=False)
    embed.add_field(
        name="Para preguntas de varias opciones",
        value='`%encuesta "pregunta" "opción 1" "opción 2" ...`',
        inline=False,
    )
    return embed
