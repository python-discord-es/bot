import asyncio
import base64
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import discord
from discord.ext import commands

from configuration import Config
from utils import get_moderation_channel, get_message_to_moderate, aceptar_emoji, rechazar_emoji

config = Config()

EMBED_COLOR = 0x2B597B


@dataclass
class ValidatedPost:
    post_id: str
    mod_row: pd.DataFrame
    ch_main: discord.TextChannel
    ch_mod: discord.TextChannel
    ch_sub: discord.TextChannel
    message_dec: str
    author: discord.User
    condition: pd.Series


class RejectModal(discord.ui.Modal, title="Rechazar Mensaje"):
    reason = discord.ui.TextInput(
        label="Razón del rechazo",
        style=discord.TextStyle.paragraph,
        placeholder="Ingresa la razón del rechazo...",
        required=True
    )

    def __init__(self, author: discord.Member, cog, message_id: int):
        super().__init__()
        self.author = author
        self.cog = cog
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        mod = interaction.user
        await interaction.response.send_message(
            f"{mod.mention} rechazó el mensaje de {self.author.mention}.\n"
            f"Razón: {self.reason.value}",
            ephemeral=True
        )
        await self.cog._rechazar_mensaje(interaction, self.message_id, self.reason.value)


class ApproveRejectView(discord.ui.View):
    def __init__(self, author: discord.Member, cog, message_id: int):
        super().__init__(timeout=None)
        self.author = author
        self.cog = cog
        self.message_id = message_id

    @discord.ui.button(label="Aprobar", style=discord.ButtonStyle.success)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        mod = interaction.user
        await interaction.response.send_message(
            f"{mod.mention} aprobó el mensaje de {self.author.mention}.",
            ephemeral=True
        )
        await self.cog._aceptar_mensaje(interaction, self.message_id)

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.danger)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            RejectModal(author=self.author, cog=self.cog, message_id=self.message_id)
        )


class Moderacion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._msg_id = None
        self._msg_enc = None
        self.channels = {}

    def _resolve_author(self, ctx) -> discord.User | discord.Member:
        return ctx.user if isinstance(ctx, discord.Interaction) else ctx.author

    def _is_bot(self, ctx) -> bool:
        return self._resolve_author(ctx).id == config.BOT_ID

    def _is_valid_channel(self, ctx) -> bool:
        channel_mod = get_moderation_channel(self.bot, ctx.channel.id)
        return channel_mod.id == ctx.message.channel.id

    def get_channels_main_mod_sub(self, channel_id):
        channel_main = self.bot.get_channel(self.channels[channel_id]["main"])
        channel_mod = self.bot.get_channel(self.channels[channel_id]["mod"])
        channel_sub = self.bot.get_channel(channel_id)
        return channel_main, channel_mod, channel_sub

    async def _parse_post_id(
        self, ctx, message_id: Optional[int], command_name: str
    ) -> Optional[str]:
        """Parse and validate the post_id from interaction or command message."""
        channel_mod = get_moderation_channel(self.bot, ctx.channel.id)

        if isinstance(ctx, discord.Interaction) and message_id is not None:
            return str(message_id)

        raw = ctx.message.content.replace(command_name, "").strip().split()[0]
        try:
            return str(int(raw))
        except ValueError:
            await channel_mod.send(f"ID incorrecto: '{raw}', sólo utiliza números.")
            return None

    async def _get_validated_post(
        self, ctx, message_id: Optional[int], command_name: str
    ) -> Optional[ValidatedPost]:
        """
        Shared validation for accept/reject:
        - Checks bot and channel validity
        - Parses post_id
        - Looks up the row in data_mod
        - Resolves channels and decodes the message
        Returns a ValidatedPost or None if any step fails.
        """
        if self._is_bot(ctx) or not self._is_valid_channel(ctx):
            return None

        channel_mod = get_moderation_channel(self.bot, ctx.channel.id)

        post_id = await self._parse_post_id(ctx, message_id, command_name)
        if post_id is None:
            return None

        if post_id not in set(self.bot.data_mod["message_id"]):
            await channel_mod.send(f"El ID {post_id} no fue encontrado")
            return None

        condition = self.bot.data_mod["message_id"] == post_id
        mod_row = self.bot.data_mod[condition]

        channel_id = config.CHANNELS[
            mod_row["channel"].values[0].replace("envio-", "")
        ]["submission"]
        ch_main, ch_mod, ch_sub = self.get_channels_main_mod_sub(channel_id)

        message_dec = base64.b64decode(eval(mod_row["message"].values[0])).decode("utf-8")
        author = self.bot.get_user(int(mod_row["author_id"].values[0]))

        return ValidatedPost(
            post_id=post_id,
            mod_row=mod_row,
            ch_main=ch_main,
            ch_mod=ch_mod,
            ch_sub=ch_sub,
            message_dec=message_dec,
            author=author,
            condition=condition,
        )

    def _log_action(self, action: str, row, post_id, moderator, reason: str = ""):
        """
        Unified log writer for accept/reject actions.
        action: "aceptar" or "rechazar"
        """
        filename = (
            config.log_accepted_file if action == "aceptar" else config.log_rejected_file
        )
        date_str = f"{datetime.now()}"
        line = (
            f'"{date_str}";'
            f'"{post_id}";'
            f'"{row["channel"].values[0]}";'
            f'"{row["author_id"].values[0]}";'
            f'"{row["author"].values[0]}";'
            f'"{row["message"].values[0]}";'
            f'"{moderator}"'
        )
        if reason:
            line += f';"{reason}"'
        line += "\n"

        with open(str(filename), "a") as f:
            f.write(line)

    def log_on_message(self, channel_sub, author):
        date_str = f"{datetime.now()}"
        new_data = {
            "date": date_str,
            "message_id": f"{self._msg_id}",
            "channel": f"{channel_sub}",
            "author_id": f"{author.id}",
            "author": f"{author}",
            "message": f"{self._msg_enc}",
        }
        self.bot.data_mod = pd.concat([self.bot.data_mod, pd.DataFrame([new_data])])

        line = (
            f'"{date_str}";'
            f'"{self._msg_id}";'
            f'"{channel_sub}";'
            f'"{author.id}";'
            f'"{author}";'
            f'"{self._msg_enc}"\n'
        )
        with open(str(config.log_mod_file), "a") as f:
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

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.content.startswith("%limpia"):
            return
        if message.author.id == config.BOT_ID:
            return
        ch_id = message.channel.id
        if ch_id not in self.channels:
            return

        self._msg_id = message.id
        self._msg_enc = base64.b64encode(message.content.encode("utf-8"))

        ch_main, ch_mod, ch_sub = self.get_channels_main_mod_sub(ch_id)
        self.log_on_message(ch_sub, message.author)

        embed = discord.Embed(
            title="Mensaje Enviado",
            description=f"Gracias {message.author.mention}, tu mensaje espera moderación.",
            colour=EMBED_COLOR,
        )
        reply_msg = await ch_sub.send(embed=embed)

        embed = get_message_to_moderate(message)
        view = ApproveRejectView(message.author, cog=self, message_id=message.id)
        await ch_mod.send(embed=embed, view=view)

        await asyncio.sleep(3)
        await discord.Message.delete(message)
        await asyncio.sleep(3)
        await discord.Message.delete(reply_msg)

    async def _aceptar_mensaje(self, ctx, message_id: Optional[int] = None):
        vp = await self._get_validated_post(ctx, message_id, "%aceptar")
        if vp is None:
            return

        moderator = self._resolve_author(ctx)
        self._log_action("aceptar", vp.mod_row, vp.post_id, moderator)
        self.bot.data_mod = self.bot.data_mod[~vp.condition]

        jump_url = f"https://discord.com/channels/{self.bot.guilds[0].id}/{vp.ch_main.id}/{self._msg_id}"
        await vp.ch_mod.send(
            f"{aceptar_emoji} Mensaje `{vp.post_id}` aceptado, "
            f"enviado al canal {vp.ch_main.mention}\nVer en {jump_url}"
        )
        await vp.ch_main.send(f"> [Enviado por {vp.author.mention}]\n{vp.message_dec}")

    @commands.command(name="aceptar", help="Comando para aceptar mensajes en moderación")
    @commands.has_role(config.MOD_ROLE)
    async def aceptar_mensaje(self, ctx):
        await self._aceptar_mensaje(ctx)

    async def _rechazar_mensaje(
        self, ctx, message_id: Optional[int] = None, reason: Optional[str] = None
    ):
        vp = await self._get_validated_post(ctx, message_id, "%rechazar")
        if vp is None:
            return

        # For command-based rejection, parse reason from message
        if not isinstance(ctx, discord.Interaction):
            _post = ctx.message.content.replace("%rechazar", "").strip().split()
            reason = " ".join(_post[1:])  # everything after the ID

        moderator = self._resolve_author(ctx)
        self._log_action("rechazar", vp.mod_row, vp.post_id, moderator, reason or "")
        self.bot.data_mod = self.bot.data_mod[~vp.condition]

        embed = discord.Embed(
            title="Mensaje rechazado",
            description=f"{vp.author.mention} tu mensaje necesita atención.",
            colour=EMBED_COLOR,
        )
        embed.add_field(
            name="Razón rechazado",
            value=f"{reason}.\nPuedes re-enviarlo con la información faltante.",
            inline=False,
        )
        embed.add_field(name="Mensaje original", value=vp.message_dec, inline=False)

        await vp.ch_mod.send(
            f"{rechazar_emoji} Mensaje `{vp.post_id}` rechazado, "
            f"enviada respuesta a {vp.ch_mod.mention}"
        )
        await vp.ch_sub.send(embed=embed)

    @commands.command(name="rechazar", help="Comando para rechazar mensajes en moderación")
    @commands.has_role(config.MOD_ROLE)
    async def rechazar_mensaje(self, ctx):
        await self._rechazar_mensaje(ctx)

    def get_mod_pending(self, data):
        messages = False
        embed = discord.Embed(
            title="Mensajes pendientes de moderación",
            colour=EMBED_COLOR,
        )
        for idx, mod_row in data.iterrows():
            author = self.bot.get_user(int(mod_row["author_id"]))
            if not author:
                print(f"El author '{mod_row['author_id']}' ya no existe en el server.")
                continue
            m_message = base64.b64decode(eval(mod_row["message"])).decode("utf-8")
            embed.add_field(
                name=f"ID: `{mod_row['message_id']}`",
                value=f"{m_message[:30]}...\nFecha: `{mod_row['date']}`\nAutor: {author.mention}",
                inline=False,
            )
            messages = True

        if not messages:
            embed.set_footer(text="No hay mensajes pendientes de moderación")
        return embed

    @commands.command(name="mod", help="Comando para listar los mensajes pendientes")
    @commands.has_role(config.MOD_ROLE)
    async def mostrar_mensajes(self, ctx):
        if self._is_bot(ctx) or not self._is_valid_channel(ctx):
            return

        channel_mod = get_moderation_channel(self.bot, ctx.channel.id)
        _post = ctx.message.content.replace("%mod", "").strip().split()

        if not _post:
            await channel_mod.send(embed=self.get_mod_pending(self.bot.data_mod))
            return

        post_id = await self._parse_post_id(ctx, None, "%mod")
        if post_id is None:
            return

        if post_id not in self.bot.data_mod["message_id"].to_list():
            await channel_mod.send(f"ID no encontrado: {post_id}")
            return

        condition = self.bot.data_mod["message_id"] == post_id
        mod_row = self.bot.data_mod[condition]
        author = self.bot.get_user(int(mod_row["author_id"].values[0]))
        m_message = base64.b64decode(eval(mod_row["message"].values[0])).decode("utf-8")

        embed = discord.Embed(
            title="Mensaje pendiente de moderación",
            description=(
                f"Post de {author.mention} el {mod_row['date'].values[0]}\n"
                f"**ID:** {mod_row['message_id'].values[0]}\n"
                f"**Mensaje:**\n```\n{m_message}\n```\n"
            ),
            colour=EMBED_COLOR,
        )
        await channel_mod.send(embed=embed)
