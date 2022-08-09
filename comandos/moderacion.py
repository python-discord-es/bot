import base64

import discord
from datetime import datetime
from discord.ext import commands

class Moderacion(commands.Cog):
    def __init__(self, bot, log_rejected_file, log_accepted_file):
        self.bot = bot
        self.log_rejected_file = log_rejected_file
        self.log_accepted_file = log_accepted_file

    @bot.command(
        name="rechazar", help="Comando para rechazar mensajes en moderación", pass_context=True
    )
    @commands.has_role(config.MOD_ROLE)
    async def rechazar_mensaje(self, ctx):
        global data_mod

        # Skip if it's the bot
        if ctx.author.id == config.BOT_ID:
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
                    for channel, values in config.CHANNELS.items():
                        if send_channel.id == values["submission"]:
                            channel_mod = bot.get_channel(values["moderation"])
                            channel_ann = bot.get_channel(values["main"])

                    # Log
                    with open(str(self.log_rejected_file), "a") as f:

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
    @commands.command(name="aceptar", help="Comando para aceptar mensajes en moderación", pass_context=True)
    @commands.has_role(config.MOD_ROLE)
    async def aceptar_mensaje(self, ctx):
        global data_mod

        # Skip if it's the bot
        if ctx.author.id == config.BOT_ID:
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
                    for channel, values in config.CHANNELS.items():
                        if send_channel.id == values["submission"]:
                            channel_mod = bot.get_channel(values["moderation"])
                            channel_ann = bot.get_channel(values["main"])

                    # Log
                    with open(str(self.log_accepted_file), "a") as f:
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


    @commands.command(name="mod", help="Comando para listar los mensajes pendientes", pass_context=True)
    @commands.has_role(config.MOD_ROLE)
    async def mostrar_mensajes(self, ctx):
        global data_mod

        # Skip if it's the bot
        if ctx.author.id == config.BOT_ID:
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
                            title="Mensaje pendiente de moderación",
                            description=msg,
                            colour=0x2B597B,
                        )
                        await channel_mod.send(embed=embed)
                    else:
                        await channel_mod.send(f"ID no encontrado: {post_id}")
            else:
                e = get_mod_pending(data_mod, bot)
                await channel_mod.send(embed=e)

    @commands.command(name="limpia", help="Comando para limpiar historial de moderación", pass_context=True)
    @commands.has_role(config.MOD_ROLE)
    async def limpia(ctx, number):

        # Skip if it's the bot
        if ctx.author.id == config.BOT_ID:
            return

        # Check which channel combination we are using from the
        # configuration information
        channel_mod = get_moderation_channel(ctx.channel.id)

        # We add one to include the current message with the instruction
        number = int(number) + 1
        if channel_mod:
            await ctx.channel.purge(limit=number)

    def get_mod_pending(self, data, bot):
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

