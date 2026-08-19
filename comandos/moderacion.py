import ast
import asyncio
import base64
import csv
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

import discord
from discord.ext import commands

import colors
from configuration import Config
from utils import get_message_to_moderate, aceptar_emoji, rechazar_emoji

config = Config()
logger = logging.getLogger(__name__)


def _encode_message(content: str) -> str:
    """Base64-encode a message's content for storage in data_mod/the log files."""
    return base64.b64encode(content.encode("utf-8")).decode("ascii")


def _decode_message(stored: str) -> str:
    """Reverse ``_encode_message``.

    Also tolerates the legacy on-disk format: older code stored the
    *repr* of the base64 `bytes` object (e.g. ``"b'aG9sYQ=='"``, via
    ``f"{base64.b64encode(...)}"``) and reversed it with ``eval()``. Rows
    written before this change still look like that, so a plain
    ``b64decode`` fails validation and we fall back to safely parsing that
    literal with ``ast.literal_eval`` instead - no ``eval()`` involved.
    """
    try:
        return base64.b64decode(stored, validate=True).decode("utf-8")
    except ValueError:
        return base64.b64decode(ast.literal_eval(stored)).decode("utf-8")


@dataclass
class ValidatedPost:
    post_id: str
    mod_row: dict
    ch_main: discord.TextChannel
    ch_mod: discord.TextChannel
    ch_sub: discord.TextChannel
    message_dec: str
    author: discord.User


async def _pending_author(cog, message_id: int):
    """Resolve a still-pending post's author live, at click time, from
    ``bot.data_mod`` - used by the persistent Aprobar/Rechazar buttons below
    so they never depend on the Python state of the moment the message was
    first sent, which is gone after a bot restart. Delegates to
    ``Moderacion._lookup_author`` (falls back to fetching the member from
    the API, not just the local cache - see its docstring)."""
    mod_row = cog.bot.data_mod.get(str(message_id))
    if mod_row is None:
        return None
    return await cog._lookup_author(int(mod_row["author_id"]))


def _mention_or_unknown(author) -> str:
    return f"de {author.mention}" if author else "(el autor ya no está disponible)"


class RejectModal(discord.ui.Modal, title="Rechazar Mensaje"):
    reason = discord.ui.TextInput(
        label="Razón del rechazo",
        style=discord.TextStyle.paragraph,
        placeholder="Ingresa la razón del rechazo...",
        required=True
    )

    def __init__(self, cog, message_id: int, author: Optional[discord.abc.User] = None):
        super().__init__()
        self.cog = cog
        self.message_id = message_id
        self.author = author

    async def on_submit(self, interaction: discord.Interaction):
        mod = interaction.user
        await interaction.response.send_message(
            f"{mod.mention} rechazó el mensaje {_mention_or_unknown(self.author)}.\n"
            f"Razón: {self.reason.value}",
            ephemeral=True
        )
        await self.cog._rechazar_mensaje(interaction, self.message_id, self.reason.value)


class ApproveButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"moderacion:aprobar:(?P<message_id>[0-9]+)",
):
    """A button whose target message is encoded in its ``custom_id``
    instead of Python closure/constructor state.

    ``discord.ui.View(timeout=None)`` alone (the previous approach) only
    keeps a button from visually expiring - it does NOT make it survive a
    bot restart, since the view instance holding ``author``/``message_id``
    in memory is gone once the process restarts, and Discord has nothing to
    route the click to. This DynamicItem (paired with
    ``bot.add_dynamic_items()`` in bot.py) is reconstructed from the
    ``custom_id`` alone via ``from_custom_id``, so a click always works
    regardless of how long ago the message was sent or whether the bot
    restarted since.
    """

    def __init__(self, message_id: int):
        super().__init__(
            discord.ui.Button(
                label="Aprobar",
                style=discord.ButtonStyle.success,
                custom_id=f"moderacion:aprobar:{message_id}",
            )
        )
        self.message_id = message_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["message_id"]))

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Moderacion")
        if cog is None:
            return
        mod = interaction.user
        author = await _pending_author(cog, self.message_id)
        await interaction.response.send_message(
            f"{mod.mention} aprobó el mensaje {_mention_or_unknown(author)}.",
            ephemeral=True,
        )
        await cog._aceptar_mensaje(interaction, self.message_id)


class RejectButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"moderacion:rechazar:(?P<message_id>[0-9]+)",
):
    """Persistent counterpart to ``ApproveButton`` above - see its
    docstring."""

    def __init__(self, message_id: int):
        super().__init__(
            discord.ui.Button(
                label="Rechazar",
                style=discord.ButtonStyle.danger,
                custom_id=f"moderacion:rechazar:{message_id}",
            )
        )
        self.message_id = message_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["message_id"]))

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Moderacion")
        if cog is None:
            return
        author = await _pending_author(cog, self.message_id)
        await interaction.response.send_modal(
            RejectModal(cog=cog, message_id=self.message_id, author=author)
        )


class ApproveRejectView(discord.ui.View):
    """Sent once, right after a submission - built from the persistent
    DynamicItem buttons above, so it keeps responding to clicks even across
    a bot restart (as long as ``bot.add_dynamic_items()`` ran on startup -
    see bot.py)."""

    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.add_item(ApproveButton(message_id))
        self.add_item(RejectButton(message_id))


class Moderacion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._msg_id = None
        self._msg_enc = None
        self.channels = {}
        self.guild = None

    def _resolve_author(self, ctx) -> discord.User | discord.Member:
        return ctx.user if isinstance(ctx, discord.Interaction) else ctx.author

    async def _lookup_author(self, author_id: int):
        """Resolve a stored ``author_id`` to a Member/User.

        ``bot.get_user()``/``guild.get_member()`` only consult the local
        cache - since this bot doesn't request the privileged Members
        intent (see bot.py), that cache only ever holds users the bot has
        *directly* observed an event from since its last reconnect/restart.
        Someone who's been a member of the server the whole time, but
        hasn't sent a message/reaction/etc. since then, can still resolve
        to None from cache alone even though they never left - so fall
        back to fetching them from the API by ID, which works regardless
        of intents (it's a single, explicit lookup, not the bulk member
        list the Members intent gates).
        """
        user = self.bot.get_user(author_id)
        if user is not None:
            return user
        if self.guild is None:
            return None
        member = self.guild.get_member(author_id)
        if member is not None:
            return member
        try:
            return await self.guild.fetch_member(author_id)
        except discord.NotFound:
            return None
        except discord.HTTPException:
            logger.exception("Fallo al buscar al member %s vía la API", author_id)
            return None

    def _is_bot(self, ctx) -> bool:
        return self._resolve_author(ctx).id == config.BOT_ID

    def get_channels_main_mod_sub(self, channel_id):
        channel_main = self.bot.get_channel(self.channels[channel_id]["main"])
        channel_mod = self.bot.get_channel(self.channels[channel_id]["mod"])
        channel_sub = self.bot.get_channel(channel_id)
        return channel_main, channel_mod, channel_sub

    async def _parse_post_id(
        self, ctx, message_id: Optional[int], command_name: str
    ) -> Optional[str]:
        """Parse and validate the post_id from interaction or command message."""
        channel_mod = self.bot.get_channel(ctx.channel.id)

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
        if self._is_bot(ctx):
            return None

        channel_mod = self.bot.get_channel(ctx.channel.id)

        post_id = await self._parse_post_id(ctx, message_id, command_name)
        if post_id is None:
            return None

        mod_row = self.bot.data_mod.get(post_id)
        if mod_row is None:
            await channel_mod.send(f"El ID {post_id} no fue encontrado")
            return None

        channel_id = config.CHANNELS[
            mod_row["channel"].replace("envio-", "")
        ]["submission"]
        ch_main, ch_mod, ch_sub = self.get_channels_main_mod_sub(channel_id)

        message_dec = _decode_message(mod_row["message"])
        author = await self._lookup_author(int(mod_row["author_id"]))
        if author is None:
            # Same condition get_mod_pending() silently skips - here we can't
            # silently skip it (the moderator is actively trying to act on
            # it), so make it an explicit, visible failure instead of
            # continuing with author=None and crashing later on
            # author.mention with no trace of why.
            logger.warning("El author '%s' ya no existe en el server.", mod_row["author_id"])
            await channel_mod.send(
                f"El autor del mensaje `{post_id}` (ID `{mod_row['author_id']}`) ya no está "
                "en el servidor; no se puede procesar."
            )
            return None

        return ValidatedPost(
            post_id=post_id,
            mod_row=mod_row,
            ch_main=ch_main,
            ch_mod=ch_mod,
            ch_sub=ch_sub,
            message_dec=message_dec,
            author=author,
        )

    def _log_action(self, action: str, row, post_id, moderator, reason: str = ""):
        """
        Unified log writer for accept/reject actions.
        action: "aceptar" or "rechazar"

        Uses csv.writer (not hand-built quoting) so a channel/author name or
        message containing a literal '"' or newline doesn't silently corrupt
        the row - these files are re-parsed on every bot startup, so a
        malformed row there can break loading the pending queue.
        """
        filename = (
            config.log_accepted_file if action == "aceptar" else config.log_rejected_file
        )
        date_str = f"{datetime.now()}"
        fields = [
            date_str,
            post_id,
            row["channel"],
            row["author_id"],
            row["author"],
            row["message"],
            moderator,
        ]
        # log_rejected_file's header always has a "reason" column - include
        # it (even if empty) for every rechazar row, not just when reason is
        # truthy, so the column count always matches the header.
        if action != "aceptar":
            fields.append(reason)

        with open(str(filename), "a", newline="") as f:
            csv.writer(f, delimiter=";").writerow(fields)

    def log_on_message(self, channel_sub, author):
        date_str = f"{datetime.now()}"
        message_id = f"{self._msg_id}"
        new_data = {
            "date": date_str,
            "message_id": message_id,
            "channel": f"{channel_sub}",
            "author_id": f"{author.id}",
            "author": f"{author}",
            "message": f"{self._msg_enc}",
        }
        self.bot.data_mod[message_id] = new_data

        with open(str(config.log_mod_file), "a", newline="") as f:
            csv.writer(f, delimiter=";").writerow([
                date_str, self._msg_id, channel_sub, author.id, author, self._msg_enc,
            ])

    @commands.Cog.listener()
    async def on_ready(self):
        if self.guild is None:
            self.guild = self.bot.get_guild(config.GUILD)

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
        self._msg_enc = _encode_message(message.content)

        ch_main, ch_mod, ch_sub = self.get_channels_main_mod_sub(ch_id)
        self.log_on_message(ch_sub, message.author)

        embed = discord.Embed(
            title="Mensaje Enviado",
            description=f"Gracias {message.author.mention}, tu mensaje espera moderación.",
            colour=colors.BRAND,
        )
        reply_msg = await ch_sub.send(embed=embed)

        embed = get_message_to_moderate(message)
        view = ApproveRejectView(message_id=message.id)
        await ch_mod.send(embed=embed, view=view)

        await asyncio.sleep(3)
        await discord.Message.delete(message)
        await asyncio.sleep(3)
        await discord.Message.delete(reply_msg)

    async def _aceptar_mensaje(self, ctx, message_id: Optional[int] = None):
        vp = await self._get_validated_post(ctx, message_id, "%aceptar")
        if vp is None:
            return

        # Post to the destination channel *first*, and only log the accept /
        # drop it from bot.data_mod once that actually succeeds. Doing this
        # the other way around (as before) meant a failure here - message
        # over Discord's 2000-char limit, missing permissions in the
        # destination channel, a transient network hiccup - silently lost
        # the post: it had already been logged "aceptado" and removed from
        # the pending queue, so nothing showed it never actually went out.
        try:
            sent_message = await vp.ch_main.send(
                f"> [Enviado por {vp.author.mention}]\n{vp.message_dec}"
            )
        except Exception:
            logger.exception(
                "Fallo al enviar el mensaje aceptado %s a %s", vp.post_id, vp.ch_main
            )
            await vp.ch_mod.send(
                f"\N{WARNING SIGN} No se pudo enviar el mensaje `{vp.post_id}` a "
                f"{vp.ch_main.mention}. Sigue pendiente - revisa bot.log e intenta de nuevo."
            )
            return

        moderator = self._resolve_author(ctx)
        self._log_action("aceptar", vp.mod_row, vp.post_id, moderator)
        del self.bot.data_mod[vp.post_id]

        # Link to the message that was actually posted there, instead of
        # guessing at a URL (the old code built the link from self._msg_id -
        # the *original submission's* id in a different channel entirely -
        # before the message below even existed).
        await vp.ch_mod.send(
            f"{aceptar_emoji} Mensaje `{vp.post_id}` aceptado, "
            f"enviado al canal {vp.ch_main.mention}\nVer en {sent_message.jump_url}"
        )

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

        embed = discord.Embed(
            title="Mensaje rechazado",
            description=f"{vp.author.mention} tu mensaje necesita atención.",
            colour=colors.BRAND,
        )
        embed.add_field(
            name="Razón rechazado",
            value=f"{reason}.\nPuedes re-enviarlo con la información faltante.",
            inline=False,
        )
        embed.add_field(name="Mensaje original", value=vp.message_dec, inline=False)

        # Same reasoning as _aceptar_mensaje: notify the submitter *first*,
        # only log the reject / drop it from bot.data_mod once that actually
        # goes through, so a failure here doesn't quietly lose the item.
        try:
            await vp.ch_sub.send(embed=embed)
        except Exception:
            logger.exception(
                "Fallo al notificar el rechazo del mensaje %s a %s", vp.post_id, vp.ch_sub
            )
            await vp.ch_mod.send(
                f"\N{WARNING SIGN} No se pudo notificar el rechazo del mensaje `{vp.post_id}` "
                f"a {vp.ch_sub.mention}. Sigue pendiente - revisa bot.log e intenta de nuevo."
            )
            return

        moderator = self._resolve_author(ctx)
        self._log_action("rechazar", vp.mod_row, vp.post_id, moderator, reason or "")
        del self.bot.data_mod[vp.post_id]

        await vp.ch_mod.send(
            f"{rechazar_emoji} Mensaje `{vp.post_id}` rechazado, "
            f"enviada respuesta a {vp.ch_mod.mention}"
        )

    @commands.command(name="rechazar", help="Comando para rechazar mensajes en moderación")
    @commands.has_role(config.MOD_ROLE)
    async def rechazar_mensaje(self, ctx):
        await self._rechazar_mensaje(ctx)

    async def get_mod_pending(self, data):
        messages = False
        embed = discord.Embed(
            title="Mensajes pendientes de moderación",
            colour=colors.BRAND,
        )
        for mod_row in data.values():
            author = await self._lookup_author(int(mod_row["author_id"]))
            if not author:
                logger.warning("El author '%s' ya no existe en el server.", mod_row["author_id"])
                continue
            m_message = _decode_message(mod_row["message"])
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
        if self._is_bot(ctx):
            return

        channel_mod = self.bot.get_channel(ctx.channel.id)
        _post = ctx.message.content.replace("%mod", "").strip().split()

        if not _post:
            await channel_mod.send(embed=await self.get_mod_pending(self.bot.data_mod))
            return

        post_id = await self._parse_post_id(ctx, None, "%mod")
        if post_id is None:
            return

        mod_row = self.bot.data_mod.get(post_id)
        if mod_row is None:
            await channel_mod.send(f"ID no encontrado: {post_id}")
            return

        author = await self._lookup_author(int(mod_row["author_id"]))
        if author is None:
            logger.warning("El author '%s' ya no existe en el server.", mod_row["author_id"])
            await channel_mod.send(
                f"El autor del mensaje `{post_id}` (ID `{mod_row['author_id']}`) ya no está "
                "en el servidor; no se puede mostrar."
            )
            return
        m_message = _decode_message(mod_row["message"])

        embed = discord.Embed(
            title="Mensaje pendiente de moderación",
            description=(
                f"Post de {author.mention} el {mod_row['date']}\n"
                f"**ID:** {mod_row['message_id']}\n"
                f"**Mensaje:**\n```\n{m_message}\n```\n"
            ),
            colour=colors.BRAND,
        )
        await channel_mod.send(embed=embed)
