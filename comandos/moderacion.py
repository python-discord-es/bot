import asyncio
import base64
from datetime import datetime

import pandas as pd
import discord
from discord.ext import commands

from configuration import Config
from utils import get_moderation_channel, get_message_to_moderate

config = Config()


class Moderacion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self._msg_content = None
        self._msg_author = None
        self._msg_id = None
        self._msg_enc = None

        self.channels = {}

    def get_channels_main_mod_sub(self, channel_id):
        channel_main = self.bot.get_channel(self.channels[channel_id]["main"])
        channel_mod = self.bot.get_channel(self.channels[channel_id]["mod"])
        channel_sub = self.bot.get_channel(channel_id)

        return channel_main, channel_mod, channel_sub

    def log_on_message(self, channel_sub):
        # Log
        # Add the new row to the data_mod, to have it in runtime
        # Add the new entry to the dat_mod file, to have it for the next time
        with open(str(config.log_mod_file), "a") as f:
            # date;message_id;channel;author;message
            date_str = f"{datetime.now()}"
            line = (
                f'"{date_str}";'
                f'"{self._msg_id}";'
                f'"{channel_sub}";'
                f'"{self._msg_author.id}";'
                f'"{self._msg_author}";'
                f'"{self._msg_enc}"\n'
            )

            # dictionary to add the data to the runtime DataFrame
            new_data = {
                "date": date_str,
                "message_id": f"{self._msg_id}",
                "channel": f"{channel_sub}",
                "author_id": f"{self._msg_author.id}",
                "author": f"{self._msg_author}",
                "message": f"{self._msg_enc}",
            }
            self.bot.data_mod = pd.concat([self.bot.data_mod, pd.DataFrame([new_data])])

            # Writing data to the CSV file
            f.write(line)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.channels:
            for channel, values in config.CHANNELS.items():
                if values["submission"] not in self.channels:
                    self.channels[values["submission"]] = {
                        "mod": values["moderation"],
                        "main": values["main"],
                    }

    def log_aceptar(self, row, post_id, author):
        # Log
        with open(str(config.log_accepted_file), "a") as f:
            # f.write("date;message_id;channel;author;message;moderator\n")
            # date;message_id;channel;author;message
            date_str = f"{datetime.now()}"
            line = (
                f'"{date_str}";'
                f'"{post_id}";'
                f'"{row["channel"].values[0]}";'
                f'"{row["author_id"].values[0]}";'
                f'"{row["author"].values[0]}";'
                f'"{row["message"].values[0]}";'
                f'"{author}"\n'
            )
            # Writing data to the CSV file
            f.write(line)

    def log_rechazar(self, row, post_id, author, reason):
        # Log
        with open(str(config.log_rejected_file), "a") as f:
            date_str = f"{datetime.now()}"
            line = (
                f'"{date_str}";'
                f'"{post_id}";'
                f'"{row["channel"].values[0]}";'
                f'"{row["author_id"].values[0]}";'
                f'"{row["author"].values[0]}";'
                f'"{row["message"].values[0]}";'
                f'"{author}";'
                f'"{reason}"\n'
            )
            # Writing data to the CSV file
            f.write(line)

    def get_mod_pending(self, data):
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
            author = self.bot.get_user(int(m_author_id))

            if author:
                embed.add_field(
                    name=f"ID: `{m_message_id}`",
                    value=(
                        f"{m_message[:30]}...\n" f"Fecha: `{m_date}`\n" f"Autor: {author.mention}"
                    ),
                    inline=False,
                )
                if not messages:
                    messages = True
            else:
                print(f"El author '{m_author_id}' ya no existe en el server. Mensaje {m_message}")

        if not messages:
            embed.set_footer(text="No hay mensajes pendientes de moderación")

        return embed

    @commands.Cog.listener()
    async def on_message(self, message):
        print("LOG: MensajeModeracion.on_message")

        # Skip limpia command
        if message.content.startswith("%limpia"):
            return
        # Not the same bot
        if message.author.id == config.BOT_ID:
            return
        # Only submissions channels will continue
        ch_id = message.channel.id
        if ch_id not in self.channels:
            return

        # Setup object values
        self._msg_id = message.id
        self._msg_content = message.content
        self._msg_author = message.author
        self._msg_enc = base64.b64encode(message.content.encode("utf-8"))

        ch_main, ch_mod, ch_sub = self.get_channels_main_mod_sub(ch_id)

        self.log_on_message(ch_sub)

        embed = discord.Embed(
            title="Mensaje Enviado",
            description=f"Gracias {self._msg_author.mention}, tu mensaje espera moderación.",
            colour=0x2B597B,
        )

        reply_msg = await ch_sub.send(embed=embed)

        embed = get_message_to_moderate(message)
        await ch_mod.send(embed=embed)

        # Remove messages
        await asyncio.sleep(3)
        await discord.Message.delete(message)

        await asyncio.sleep(3)
        await discord.Message.delete(reply_msg)

    @commands.command(
        name="rechazar",
        help="Comando para rechazar mensajes en moderación",
        pass_context=True,
    )
    @commands.has_role(config.MOD_ROLE)
    async def rechazar_mensaje(self, ctx):
        # Skip if it's the bot
        if ctx.author.id == config.BOT_ID:
            return

        # Check which channel combination we are using from the
        # configuration information
        channel_mod = get_moderation_channel(self.bot, ctx.channel.id)

        if channel_mod.id != ctx.message.channel.id:
            return

        _post = ctx.message.content.replace("%rechazar", "").strip()
        _post_id = _post.split()[0]
        _post_reason = " ".join(_post.split()[1:])
        post_id = None
        try:
            post_id = str(int(_post_id))
        except ValueError:
            await channel_mod.send(f"ID incorrecto: '{_post_id}', sólo utiliza números.")
            return

        if post_id not in set(self.bot.data_mod["message_id"]):
            await channel_mod.send(f"El ID {post_id} no fue encontrado")
            return

        # Sacar datos de df moderación
        condition = self.bot.data_mod["message_id"] == post_id
        mod_row = self.bot.data_mod[condition]

        # Get the submission channel id from the file
        channel_id = config.CHANNELS[mod_row["channel"].values[0].replace("envio-", "")][
            "submission"
        ]
        ch_main, ch_mod, ch_sub = self.get_channels_main_mod_sub(channel_id)

        self.log_rechazar(mod_row, post_id, ctx.message.author, _post_reason)

        message_dec = base64.b64decode(eval(mod_row["message"].values[0])).decode("utf-8")

        author = self.bot.get_user(int(mod_row["author_id"].values[0]))

        # Remove that row, because it was handled
        self.bot.data_mod = self.bot.data_mod[~condition]

        embed = discord.Embed(
            title="Mensaje rechazado",
            description=f"{author.mention} tu mensaje necesita atención.",
            colour=0x2B597B,
        )
        embed.add_field(
            name="Razón rechazado",
            value=f"{_post_reason}.\nPuedes re-enviarlo con la información faltante.",
            inline=False,
        )
        embed.add_field(name="Mensaje original", value=message_dec, inline=False)

        await ch_mod.send(f"Mensaje {post_id} rechazado, " f"enviada respuesta a {ch_main.mention}")
        await ch_sub.send(embed=embed)

    # This command can only be used within the "moderation" channels
    # described in the configuration file.
    @commands.command(
        name="aceptar",
        help="Comando para aceptar mensajes en moderación",
        pass_context=True,
    )
    @commands.has_role(config.MOD_ROLE)
    async def aceptar_mensaje(self, ctx):
        # Skip if it's the bot
        if ctx.author.id == config.BOT_ID:
            return

        # Check which channel combination we are using from the
        # configuration information
        channel_mod = get_moderation_channel(self.bot, ctx.channel.id)

        if channel_mod.id != ctx.message.channel.id:
            return

        _post = ctx.message.content.replace("%aceptar", "").strip()
        post_id = None
        try:
            post_id = str(int(_post))
        except ValueError:
            await channel_mod.send(f"ID incorrecto: '{_post}', sólo utiliza números.")
            return

        if post_id not in set(self.bot.data_mod["message_id"]):
            await channel_mod.send(f"El ID {post_id} no fue encontrado")
            return

        # Sacar datos de df moderación
        condition = self.bot.data_mod["message_id"] == post_id
        mod_row = self.bot.data_mod[condition]

        # Get the submission channel id from the file
        channel_id = config.CHANNELS[mod_row["channel"].values[0].replace("envio-", "")][
            "submission"
        ]
        ch_main, ch_mod, ch_sub = self.get_channels_main_mod_sub(channel_id)

        self.log_aceptar(mod_row, post_id, ctx.message.author)

        message_dec = base64.b64decode(eval(mod_row["message"].values[0])).decode("utf-8")
        author = self.bot.get_user(int(mod_row["author_id"].values[0]))

        # Remove that row, because it was handled
        self.bot.data_mod = self.bot.data_mod[~condition]

        await ch_mod.send(f"Mensaje {post_id} aceptado, enviado al canal {ch_main.mention}")
        await ch_main.send(f"[Enviado por {author.mention}]\n{message_dec}")

    @commands.command(
        name="mod",
        help="Comando para listar los mensajes pendientes",
        pass_context=True,
    )
    @commands.has_role(config.MOD_ROLE)
    async def mostrar_mensajes(self, ctx):
        # Skip if it's the bot
        if ctx.author.id == config.BOT_ID:
            return

        # Check which channel combination we are using from the
        # configuration information
        channel_mod = get_moderation_channel(self.bot, ctx.channel.id)

        if channel_mod.id != ctx.message.channel.id:
            return

        _post = ctx.message.content.replace("%mod", "").strip().split()
        # We have no message_id
        if len(_post) < 1:
            e = self.get_mod_pending(self.bot.data_mod)
            await channel_mod.send(embed=e)

        _post_id = _post[0]
        post_id = None
        try:
            post_id = str(int(_post_id))
        except ValueError:
            await channel_mod.send(f"ID incorrecto '{_post}', sólo utiliza números.")

        if post_id:
            if post_id in self.bot.data_mod["message_id"].to_list():
                # Sacar datos de df moderación
                condition = self.bot.data_mod["message_id"] == post_id
                mod_row = self.bot.data_mod[condition]

                m_date = mod_row["date"].values[0]
                m_message_id = mod_row["message_id"].values[0]
                m_message = base64.b64decode(eval(mod_row["message"].values[0])).decode("utf-8")
                m_author_id = mod_row["author_id"].values[0]

                author = self.bot.get_user(int(m_author_id))

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
