import sys
import toml
import time

import base64
import discord
import pandas as pd
from discord.ext import commands
from pathlib import Path
from datetime import datetime


# Use '%' as command prefix
intents = discord.Intents().all()
bot = commands.Bot(command_prefix="%", intents=intents)


def get_moderation_channel(current_id):
    for channel, values in CHANNELS.items():
        if current_id == values["moderation"]:
            channel_mod = bot.get_channel(values["moderation"])
            return channel_mod
    return None


@bot.command(name="ayuda", help="Comando de ayuda", pass_context=True)
async def ayuda(ctx):

    # Skip if it's the bot
    if ctx.author.id == BOT_ID:
        return

    # Check which channel combination we are using from the
    # configuration information
    channel_mod = get_moderation_channel(ctx.channel.id)

    if channel_mod:
        msg = (
            "Comandos disponibles:\n"
            "```"
            "%mod               - Lista todos los post pendientes de moderación\n"
            "%mod ID            - Lista información del post ID pendiente de moderación\n"
            "%aceptar ID        - Acepta mensaje, lo envia al canal asociado\n"
            "%rechazar ID RAZON - Rechaza el mensaje ID, lo envia al canal asociado\n"
            "                     El usuario será notificado, con el mensaje RAZON\n"
            "%limpia N          - Limpia N mensajes del canal de moderación\n"
            "```"
        )

        await channel_mod.send(msg)
    else:
        msg = (
            "Comandos disponibles:\n"
            "```"
            '%encuesta "pregunta"\n'
            "    Para hacer preguntas de Sí y No\n"
            '    Ejemplo: %encuesta "¿Te gusta el té?"\n\n'
            '%encuesta "pregunta" "opción a" "opción b" ...\n'
            "    Para hacer preguntas con varias opciones.\n"
            '    Ejemplo: %encuesta "¿Cuál es tu lenguaje favorito?" "Inglés" "Español" "Python"\n\n'
            'Importante: La pregunta y opciones deben ir entre comillas dobles "..."'
            "```"
        )

        await ctx.channel.send(msg)


@bot.command(name="limpia", help="Comando para limpiar historial de moderación", pass_context=True)
async def limpia(ctx, number):

    # Skip if it's the bot
    if ctx.author.id == BOT_ID:
        return

    # Check which channel combination we are using from the
    # configuration information
    channel_mod = get_moderation_channel(ctx.channel.id)

    # We add one to include the current message with the instruction
    number = int(number) + 1
    if channel_mod:
        await ctx.channel.purge(limit=number)


@bot.command(name="mod", help="Comando para listar los mensajes pendientes", pass_context=True)
async def mod(ctx):
    global data_mod

    # Skip if it's the bot
    if ctx.author.id == BOT_ID:
        return

    # Check which channel combination we are using from the
    # configuration information
    channel_mod = get_moderation_channel(ctx.channel.id)

    if channel_mod:
        _post = ctx.message.content.replace("%mod", "").strip().split()
        # We have a message_id
        if len(_post) > 0:
            _post_id = _post[0]
            post_id = None
            try:
                post_id = int(_post_id)
            except ValueError:
                await channel_mod.send(f"ID incorrecto '{_post}', sólo utiliza números.")
            post_id = str(post_id)
            if post_id:
                if post_id in data_mod["message_id"].to_list():

                    # Sacar datos de df moderación
                    condition = data_mod["message_id"] == post_id
                    mod_row = data_mod[condition]

                    m_date = mod_row["date"].values[0]
                    m_message_id = mod_row["message_id"].values[0]
                    m_message = base64.b64decode(eval(mod_row["message"].values[0])).decode("utf-8")
                    m_author_id = mod_row["author_id"].values[0]

                    author = bot.get_user(int(m_author_id))

                    msg = (
                        f"Post de {author.mention} el {m_date}\n"
                        f"**ID:** {m_message_id}\n"
                        f"**Mensaje:**\n"
                        f"```\n{m_message}\n```\n"
                    )
                    embed = discord.Embed(
                        title=f"Mensaje pendiente de moderación",
                        description=msg,
                        colour=0x2b597b,
                    )
                    await channel_mod.send(embed=embed)
                else:
                    await channel_mod.send(f"ID no encontrado: {post_id}")
        else:
            # Imprimir todos los posts que necesitan moderación
            msg = ""
            messages = False
            for idx, mod_row in data_mod.iterrows():
                m_date = mod_row["date"]
                m_message_id = mod_row["message_id"]
                m_message = base64.b64decode(eval(mod_row["message"])).decode("utf-8")
                m_author_id = mod_row["author_id"]
                author = bot.get_user(int(m_author_id))

                msg += (
                    f"\n**{m_message_id}** ({author.mention}) en `{m_date}`\n"
                    f"```\n"
                    f"{m_message[:30]}...\n"
                    f"```\n\n"
                )
                if not messages:
                    messages = True

            if not messages:
                msg = "No hay mensajes pendientes de moderación"

            embed = discord.Embed(
                title=f"Mensajes pendientes de moderación",
                description=msg,
                colour=0x2b597b,
            )

            await channel_mod.send(embed=embed)


@bot.command(
    name="rechazar", help="Comando para rechazar mensajes en moderación", pass_context=True
)
async def rechazar(ctx):
    global data_mod

    # Skip if it's the bot
    if ctx.author.id == BOT_ID:
        return

    # Check which channel combination we are using from the
    # configuration information
    channel_mod = get_moderation_channel(ctx.channel.id)

    if channel_mod:
        _post = ctx.message.content.replace("%rechazar", "").strip().split()
        _post_id = _post[0]
        _post_reason = " ".join(_post[1:])
        post_id = None
        try:
            post_id = int(_post_id)
        except ValueError:
            await channel_mod.send(f"ID incorrecto '{_post_id}', sólo utiliza números.")

        post_id = str(post_id)

        if post_id:
            if post_id in data_mod["message_id"].to_list():

                # Sacar datos de df moderación
                condition = data_mod["message_id"] == post_id
                mod_row = data_mod[condition]

                channel_mod = None
                channel_ann = None
                send_channel = discord.utils.get(
                    ctx.guild.channels, name=mod_row["channel"].values[0]
                )
                for channel, values in CHANNELS.items():
                    if send_channel.id == values["submission"]:
                        channel_mod = bot.get_channel(values["moderation"])
                        channel_ann = bot.get_channel(values["main"])

                # Log
                with open(str(log_rejected_file), "a") as f:

                    date_str = f"{datetime.now()}"
                    line = (
                        f'"{date_str}";'
                        f'"{post_id}";'
                        f'"{mod_row["channel"].values[0]}";'
                        f'"{mod_row["author_id"].values[0]}";'
                        f'"{mod_row["author"].values[0]}";'
                        f'"{mod_row["message"].values[0]}";'
                        f'"{ctx.message.author}";'
                        f'"{_post_reason}"\n'
                    )
                    print(line)
                    # Writing data to the CSV file
                    f.write(line)

                _author_id = mod_row["author_id"].values[0]
                author = bot.get_user(int(_author_id))

                message_answer = (
                    f"{author.mention} tu mensaje necesita atención: "
                    f'"{_post_reason}".\n'
                    f"Puedes re-enviarlo con la información faltante."
                )

                # Remove that entry from the moderation DataFrame
                data_mod = data_mod[~condition]

                await channel_mod.send(
                    f"Mensaje {post_id} rechazado, "
                    f"enviada respuesta al canal {channel_ann.mention}"
                )
                await channel_ann.send(message_answer)
            else:
                await channel_mod.send(f"El ID {post_id} no fue encontrado")


# This command can only be used within the "moderation" channels
# described in the configuration file.
@bot.command(name="aceptar", help="Comando para aceptar mensajes en moderación", pass_context=True)
async def aceptar(ctx):
    global data_mod

    # Skip if it's the bot
    if ctx.author.id == BOT_ID:
        return

    # Check which channel combination we are using from the
    # configuration information
    channel_mod = get_moderation_channel(ctx.channel.id)

    if channel_mod:
        _post = ctx.message.content.replace("%aceptar", "").strip()
        post_id = None
        try:
            post_id = int(_post)
        except ValueError:
            await channel_mod.send(f"ID incorrecto: '{_post}', sólo utiliza números.")

        post_id = str(post_id)

        if post_id:
            if post_id in data_mod["message_id"].to_list():

                # Sacar datos de df moderación
                condition = data_mod["message_id"] == post_id
                mod_row = data_mod[condition]

                channel_mod = None
                channel_ann = None
                send_channel = discord.utils.get(
                    ctx.guild.channels, name=mod_row["channel"].values[0]
                )
                for channel, values in CHANNELS.items():
                    if send_channel.id == values["submission"]:
                        channel_mod = bot.get_channel(values["moderation"])
                        channel_ann = bot.get_channel(values["main"])

                # Log
                with open(str(log_accepted_file), "a") as f:
                    # f.write("date;message_id;channel;author;message;moderator\n")
                    # date;message_id;channel;author;message

                    date_str = f"{datetime.now()}"
                    line = (
                        f'"{date_str}";'
                        f'"{post_id}";'
                        f'"{mod_row["channel"].values[0]}";'
                        f'"{mod_row["author_id"].values[0]}";'
                        f'"{mod_row["author"].values[0]}";'
                        f'"{mod_row["message"].values[0]}";'
                        f'"{ctx.message.author}"\n'
                    )
                    print(line)
                    # Writing data to the CSV file
                    f.write(line)

                message_dec = base64.b64decode(eval(mod_row["message"].values[0])).decode("utf-8")
                _author_id = mod_row["author_id"].values[0]
                author = bot.get_user(int(_author_id))
                data_mod = data_mod[~condition]

                await channel_mod.send(
                    f"Mensaje {post_id} aceptado, enviado al canal {channel_ann.mention}"
                )
                await channel_ann.send(f"Enviado por {author.mention}\n{message_dec}")
            else:
                await channel_mod.send(f"El ID {post_id} no fue encontrado")

async def spam_check(message):
    global main_mod_channel
    spam_words = ('discord', 'nitro', 'free', 'http')

    if message.author.id != BOT_ID:
        if not main_mod_channel:
            main_mod_channel = bot.get_channel(MOD_MAIN)
        content = message.content.lower()
        if all(i in content for i in spam_words):
            msg = (f"  **User:** {message.author.mention}\n"
                   f"  **Mensaje:**\n "
                   f"```"
                   f"{message.content}"
                   f"```\n\n"
                   "En caso de ser SPAM, recuerda hacer `click-derecho` sobre el nickname y **banear**.")
            embed = discord.Embed(
                title=f"\N{WARNING SIGN} Alerta de posible SPAM",
                description=msg,
                colour=0xff0000,
            )
            await main_mod_channel.send(embed=embed)
            return True
    return False


@bot.event
async def on_message(message):
    global data_mod
    await bot.process_commands(message)

    if await spam_check(message):
        await discord.Message.delete(message)
        channel = bot.get_channel(message.channel.id)
        msg = (f"El mensaje del usuario {message.author.mention} fue borrado y podría ser un engaño.\n"
                "Evita `hacer click` en enlaces de **usuarios que no conozcas**.")
        embed = discord.Embed(
            title=f"\N{NO ENTRY} Alerta de posible SPAM",
            description=msg,
            colour=0x2b597b,
        )
        reply_msg = await channel.send(embed=embed)
        time.sleep(10)
        await discord.Message.delete(reply_msg)
    else:
        # Check which channel combination we are using
        channel_mod = None
        channel_sub = None
        channel_id = None
        for channel, values in CHANNELS.items():
            if message.channel.id == values["submission"]:
                channel_mod = bot.get_channel(values["moderation"])
                channel_sub = bot.get_channel(values["submission"])

        # Moderación Canal X
        if channel_mod and channel_sub and message.author.id != BOT_ID:

            # Log
            # Add the new row to the data_mod, to have it in runtime
            # Add the new entry to the dat_mod file, to have it for the next time
            with open(str(log_mod_file), "a") as f:
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
                print(line)

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
                title=f"Mensaje Enviado",
                description=f"Gracias {message.author.mention}, tu mensaje espera moderación.",
                colour=0x2b597b,
            )
            reply_msg = await channel_sub.send(embed=embed_reply)
            aceptar_emoji = "\N{WHITE HEAVY CHECK MARK}"
            rechazar_emoji = "\N{CROSS MARK}"
            msg = (
                f"{datetime.utcnow()} UTC\n"
                f"Mensaje enviado desde {message.channel.mention} por {message.author.mention}\n\n"
                f"```\n{message.content}\n```\n\n**¿Cumple con todos los requisitos?**\n\n"
                f"{aceptar_emoji} Para aceptarlo, envía el siguiente mensaje:\n\n`%aceptar {message.id}`\n\n"
                f"{rechazar_emoji} Para rechazarlo, envía el siguiente mensaje:\n\n`%rechazar {message.id} 'razón del rechazo'`"
            )
            embed = discord.Embed(
                title=f"Moderación de mensaje",
                description=msg,
                colour=0x2b597b,
            )
            await channel_mod.send(embed=embed)
            time.sleep(3)
            print("!", reply_msg)
            await discord.Message.delete(message)

        elif channel_sub:
            time.sleep(3)
            await discord.Message.delete(message)


@bot.command(name="encuesta", help="Comando de encuesta", pass_context=True)
async def encuesta(ctx, *args):
    def get_number_emoji(n):
        if 0 <= n < 10:
            return f"{n}\N{COMBINING ENCLOSING KEYCAP}"
        else:
            return n

    # Log
    with open(str(log_file), "a") as f:
        # date;command;message_id;channel;author;message
        message = " ".join(args).encode("utf-8")
        message_enc = base64.b64encode(message)
        line = (
            f'"{datetime.now()}";'
            f'"encuesta";'
            f'"{ctx.message.id}";'
            f'"{ctx.channel.name}";'
            f'"{ctx.message.author.id}";'
            f'"{ctx.message.author}";'
            f'"{message_enc}"\n'
        )
        print(line)
        f.write(line)

    # Errors
    n = len(args)
    if n < 1:
        await ctx.send(
            "\N{NO ENTRY} No se encontró ningún argumento.\n\n"
            "**¿Cómo realizar encuestas?**\n"
            "Para preguntas de **Sí** y **No**::\n"
            "```\n"
            '%encuesta "pregunta"'
            "```\n"
            "y para preguntas de **múltiples opciones**:\n"
            "```"
            '%encuesta "pregunta" "opción 1" "opción 2" "..."'
            "```\n"
        )
        return

    # Error, because one question, with one option makes no sense.
    elif n == 2:
        await ctx.send("\N{NO ENTRY} No es posible tener solo una opción por pregunta.")
        return

    head = f"**Encuesta \N{BAR CHART}**\n" f"Pregunta: **{args[0]}**\n\n"
    foot = "\n\n¡Participa utilizando las reacciones al mensaje \N{HAPPY PERSON RAISING ONE HAND}!"

    # Only one arg, assumes a Yes/No question
    if n == 1:
        si_emoji = "\N{WHITE HEAVY CHECK MARK}"
        no_emoji = "\N{CROSS MARK}"

        msg = await ctx.send(f"{head}{si_emoji} Sí\n{no_emoji} No{foot}")

        await msg.add_reaction(si_emoji)
        await msg.add_reaction(no_emoji)

    # Maximum options: 10
    elif n < 11:
        body = "\n".join(f"{get_number_emoji(i-1)} {args[i]}" for i in range(1, n))
        msg = await ctx.send(f"{head}{body}{foot}")

        for i in range(1, n):
            await msg.add_reaction(get_number_emoji(i - 1))
    await discord.Message.delete(ctx.message)


# This function will monitor all the messages, even if they are from
# before the bot became online.
# The difference with the "on_reaction_add", is that the signature is
# different, and we need to find the message by the 'payload' ID first.
@bot.event
async def on_raw_reaction_add(payload):
    guild = bot.get_guild(payload.guild_id)
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
        print("! Mensaje no encontrado")


if __name__ == "__main__":
    # Configuration file
    config = None
    with open("config.toml") as f:
        config = toml.loads(f.read())

    if not config:
        print("Error: Failed to load the config")
        sys.exit(-1)

    TOKEN = config["bot"]["token"]
    BOT_ID = config["bot"]["id"]
    GUILD = config["server"]["guild"]
    CHANNELS = config["channels"]

    MOD_MAIN = config["bot"]["moderation_main"]
    LOG_FILE = config["bot"]["general_log"]
    LOG_MOD_FILE = config["bot"]["moderation_log"]

    log_file = Path(LOG_FILE)
    log_mod_file = Path(LOG_MOD_FILE)

    # create an '_accepted' file based on the moderation log file
    LOG_MOD_ACCEPTED_FILE = f"{log_mod_file.stem}_accepted{log_mod_file.suffix}"
    # create an '_rejected' file based on the moderation log file
    LOG_MOD_REJECTED_FILE = f"{log_mod_file.stem}_rejected{log_mod_file.suffix}"

    log_accepted_file = Path(LOG_MOD_ACCEPTED_FILE)
    log_rejected_file = Path(LOG_MOD_REJECTED_FILE)

    # Main moderation channel
    main_mod_channel = None

    # Checking files
    if not log_file.is_file():
        with open(str(log_file), "w") as f:
            f.write("date;command;message_id;channel;author_id;author;message\n")

    if not log_mod_file.is_file():
        with open(str(log_mod_file), "w") as f:
            f.write("date;message_id;channel;author_id;author;message\n")
    data_mod = pd.read_csv(str(log_mod_file), sep=";", dtype=str)
    print(data_mod)

    if not log_accepted_file.is_file():
        with open(str(log_accepted_file), "w") as f:
            f.write("date;message_id;channel;author_id;author;message;moderator\n")
    data_accepted = pd.read_csv(str(log_accepted_file), sep=";", dtype=str)

    if not log_rejected_file.is_file():
        with open(str(log_rejected_file), "w") as f:
            f.write("date;message_id;channel;author_id;author;message;moderator;reason\n")
    data_rejected = pd.read_csv(str(log_rejected_file), sep=";", dtype=str)

    # Pending moderation
    # Get 'message_id' from the 'accepted' and 'rejected' files
    ready_ids = set(data_accepted["message_id"]).union(data_rejected["message_id"])

    data_mod = data_mod[~data_mod["message_id"].isin(ready_ids)]

    # Removing the help command
    bot.remove_command("help")

    # Starting the bot
    print("Running...")
    bot.run(TOKEN)
