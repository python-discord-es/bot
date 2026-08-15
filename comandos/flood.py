import hashlib
import logging
import time

from dataclasses import dataclass
from io import BytesIO

import discord
from discord.ext import commands, tasks
from PIL import Image, UnidentifiedImageError

import colors
from configuration import Config
from utils import strip_message

from typing import Optional

config = Config()
logger = logging.getLogger(__name__)

SPAM_WORDS = [
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
    ("gratis", "full", "youtube.com", "telegra.ph"),
]


@dataclass(frozen=True)
class MessageContext:
    """Per-message state, threaded explicitly through the ``*_check``
    methods and ``alert_moderation`` as a parameter.

    This used to live on shared ``FloodSpam`` instance attributes
    (``self._msg_channel``/``_msg_content``/``_msg_author``/
    ``_msg_author_mention``), set once at the top of ``on_message`` and
    read back by whichever check ran next. That made those methods hard
    to call/test independently, and - since real handling has plenty of
    ``await`` points in between - a second ``on_message`` call for a
    *different* message running concurrently could overwrite that shared
    state while the first call was still relying on it.
    """

    message: discord.Message
    content: str  # message.content, stripped via strip_message()

    @property
    def channel(self):
        return self.message.channel

    @property
    def author(self):
        return self.message.author

    @property
    def author_mention(self):
        return self.message.author.mention


# Modal view to 'ban' or 'remove role' from users that get reported
# as spam.
class ModActionView(discord.ui.View):
    def __init__(self, author: discord.Member, muted_role: discord.Role):
        super().__init__(timeout=None)  # None = buttons never expire
        self.author = author
        self.muted_role = muted_role

    @discord.ui.button(label="Banear Usuario", style=discord.ButtonStyle.danger)
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.author.ban(reason=f"Baneado por un moderador: {interaction.user.mention}")
        await interaction.response.send_message(f"{self.author.mention} fue baneado por moderación {interaction.user}.", ephemeral=True)

    @discord.ui.button(label="Desmutear", style=discord.ButtonStyle.secondary)
    async def remove_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.author.remove_roles(self.muted_role)
        await interaction.response.send_message(f"{self.author.mention} ha sido desmuteado por moderación: {interaction.user.mention}.", ephemeral=True)


class FloodSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._main_mod_channel: Optional[discord.TextChannel] = None

        # Known spam/scam text and image hashes, plus the short-lived
        # per-author tracking used to detect floods and image bursts.
        self.spam = config.get_spam_messages()
        self.normal = {}
        self.image_spam = config.get_spam_image_hashes()
        self.image_authors = {}
        self.guild = None

        self._coord_role: Optional[discord.Role] = None
        self._muted_role: Optional[discord.Role] = None

    @property
    def muted_role(self) -> discord.Role:
        assert self._muted_role is not None, "Muted role not found - make sure it exists first"
        return self._muted_role

    @property
    def coord_role(self) -> discord.Role:
        assert self._coord_role is not None, "Coordination role not found - make sure it exists first"
        return self._coord_role

    @property
    def main_mod_channel(self) -> discord.TextChannel:
        assert self._main_mod_channel is not None, "Main Moderation channel not found - make sure it exists first"
        return self._main_mod_channel

    @commands.Cog.listener()
    async def on_ready(self):
        # Setting up variables on the first message
        if self.guild is None:
            self.guild = self.bot.get_guild(config.GUILD)

        if self._coord_role is None:
            self._coord_role = discord.utils.get(self.guild.roles, name=config.MOD_ROLE)

        if self._muted_role is None:
            self._muted_role = discord.utils.get(self.guild.roles, name=config.MUTED_ROLE)

        if self._main_mod_channel is None:
            self._main_mod_channel = self.bot.get_channel(config.MOD_MAIN)

        self.clear_messages.start()

    # Remove messages every hour
    @tasks.loop(seconds=60 * 30)
    async def clear_messages(self):
        self.normal = {}
        self.image_authors = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        logger.debug("on_message: %s", message.id)
        await self.bot.process_commands(message)

        if message.author.bot or message.author.id == config.BOT_ID:
            return

        # Ignore short, textless messages, unless they carry attachments
        # (e.g. an image-only spam message has no text at all).
        if len(message.content) < 5 and not message.attachments:
            return

        ctx = MessageContext(message=message, content=strip_message(message.content))

        # skip coord role
        if self.coord_role in ctx.author.roles:
            return

        if await self.attachment_check(ctx):
            return

        if await self.flood_check(ctx):
            return

        if ctx.content in self.spam:
            await self.alert_moderation(
                ctx,
                "Alerta de SPAM (Mensaje conocido)",
                "known",
            )

            # Set muted role
            await ctx.author.add_roles(self.muted_role)

            await discord.Message.delete(message)
            msg = (
                f"El mensaje del usuario {ctx.author_mention} fue borrado por ser un "
                "mensaje detectado previamente como spam.\n"
            )
            embed = discord.Embed(
                title="\N{NO ENTRY} Alerta de posible SPAM",
                description=msg,
                colour=colors.BRAND,
            )
            await ctx.channel.send(embed=embed, delete_after = 60)

        # Check first more than 3 mentions
        if await self.mention_check(ctx):
            self.add_spam_message(ctx.content)
            await discord.Message.delete(message)
            msg = (
                f"El mensaje del usuario {ctx.author_mention} fue borrado por tener muchas "
                "menciones y podría ser un engaño.\nEvita `hacer click` en enlaces de "
                "**usuarios que no conozcas**."
            )
            embed = discord.Embed(
                title="\N{NO ENTRY} Alerta de posible SPAM",
                description=msg,
                colour=colors.BRAND,
            )
            await ctx.channel.send(embed=embed, delete_after=300)

        if await self.spam_check(ctx):
            self.add_spam_message(ctx.content)
            await discord.Message.delete(message)
            msg = (
                f"El mensaje del usuario {ctx.author_mention} fue borrado y podría ser "
                "un engaño.\nEvita `hacer click` en enlaces de **usuarios que no conozcas**."
            )
            embed = discord.Embed(
                title="\N{NO ENTRY} Alerta de posible SCAM",
                description=msg,
                colour=colors.BRAND,
            )
            await ctx.channel.send(embed=embed, delete_after = 300)

    async def spam_check(self, ctx: MessageContext):
        if not isinstance(ctx.author, discord.Member):
            return

        if not any(all(i in ctx.message.content for i in sw) for sw in SPAM_WORDS):
            return False

        await self.alert_moderation(ctx, "Alerta de SCAM", "scam")

        # Set muted role
        await ctx.author.add_roles(self.muted_role)

        _msg = (
            f"Usuario {ctx.author_mention} silenciado por compartir un mensaje que "
            "parece contener enlaces de engaño. El equipo de coordinación ha sido notificado."
        )
        embed = discord.Embed(
            title="\N{NO ENTRY} Alerta de posible SCAM",
            description=_msg,
            colour=colors.BRAND,
        )
        # Send message notifying the user is muted
        await ctx.channel.send(embed=embed, delete_after = 300)
        return True

    async def flood_check(self, ctx: MessageContext):
        logger.debug("flood_check: %s", ctx.message.id)

        # Textless (image-only) messages are handled by attachment_check
        if not ctx.content:
            return False

        if ctx.author not in self.normal:
            self.normal[ctx.author] = {ctx.content: 1}
        else:
            if ctx.content not in self.normal[ctx.author]:
                self.normal[ctx.author][ctx.content] = 1
            else:
                self.normal[ctx.author][ctx.content] += 1
                if self.normal[ctx.author][ctx.content] >= config.FLOOD_LIMIT:
                    self.add_spam_message(ctx.content)
                    await self.alert_moderation(
                        ctx,
                        "Alerta de Flood",
                        "flood",
                    )

                    # Set muted role
                    await ctx.author.add_roles(self.muted_role)

                    # Reset author counters
                    self.normal[ctx.author] = {}

                    _msg = (
                        f"Usuario {ctx.author_mention} silenciado por enviar mensajes "
                        "repetitivos. El equipo de coordinación ha sido notificado."
                    )
                    embed = discord.Embed(
                        title="\N{NO ENTRY} Alerta de posible SPAM",
                        description=_msg,
                        colour=colors.BRAND,
                    )
                    # Send message notifying the user is muted
                    await ctx.channel.send(embed=embed, delete_after = 120)

    @staticmethod
    def _hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    async def _sanitize_bytes(data: bytes) -> Optional[discord.File]:
        """Decode and re-encode image bytes before they're shown to moderators.

        Images from a compromised/malicious account are untrusted input: a
        crafted file could try to exploit a bug in whatever renders its
        thumbnail (e.g. the libwebp CVE-2023-4863 heap overflow). Re-encoding
        via Pillow into a fresh PNG strips anything relying on a malformed
        file structure, and the result is still sent as a spoiler so viewing
        it requires an explicit click rather than an automatic preview.
        Returns ``None`` if the image can't be safely decoded.
        """
        try:
            with Image.open(BytesIO(data)) as img:
                img.load()
                clean = img.convert("RGB")
            buf = BytesIO()
            clean.save(buf, format="PNG")
            buf.seek(0)
            return discord.File(buf, filename="evidencia.png", spoiler=True)
        except (UnidentifiedImageError, OSError, ValueError):
            logger.warning("_sanitize_bytes: could not decode image, skipping")
            return None

    async def attachment_check(self, ctx: MessageContext) -> bool:
        """Detect image-based spam/scam bursts from (often compromised) accounts.

        Two mechanisms:
        - Fast path: the message contains an image matching a hash we've
          already confirmed as spam/scam (see ``add_spam_image_hash``).
        - Burst path: the same author posts a message with 2+ image
          attachments in 2+ different channels within a short time window,
          which is the signature of a compromised account spraying the
          same images across the server. When this fires, the offending
          images are hashed and cached for the fast path above.
        """
        logger.debug("attachment_check: %s", ctx.message.id)

        images = [
            a for a in ctx.message.attachments
            if (a.content_type or "").startswith("image/")
        ]
        if not images:
            return False

        # Read each attachment's bytes once and reuse them below for hashing
        # and (if needed) sanitizing, instead of re-downloading from
        # Discord's CDN for each separate step.
        image_bytes = [await a.read() for a in images]

        # Fast path: any image already known to be spam/scam
        for data in image_bytes:
            digest = self._hash_bytes(data)
            if digest in self.image_spam:
                await self.alert_moderation(
                    ctx,
                    "Alerta de SPAM (Imagen conocida)",
                    "known_image",
                    image_bytes=image_bytes,
                )

                # Set muted role
                await ctx.author.add_roles(self.muted_role)

                await discord.Message.delete(ctx.message)
                msg = (
                    f"El mensaje del usuario {ctx.author_mention} fue borrado por "
                    "contener una imagen detectada previamente como spam.\nEl equipo de "
                    "coordinación ha sido notificado."
                )
                embed = discord.Embed(
                    title="\N{NO ENTRY} Alerta de posible SPAM",
                    description=msg,
                    colour=colors.BRAND,
                )
                await ctx.channel.send(embed=embed, delete_after=60)
                return True

        if len(images) < config.IMAGE_ATTACHMENT_LIMIT:
            return False

        # Burst path: same author, 2+ images, 2+ different channels, short window
        now = time.time()
        channels = self.image_authors.get(ctx.author, {})
        channels = {
            channel_id: ts
            for channel_id, ts in channels.items()
            if now - ts <= config.IMAGE_BURST_WINDOW
        }
        channels[ctx.channel.id] = now
        self.image_authors[ctx.author] = channels

        if len(channels) < 2:
            return False

        await self.alert_moderation(
            ctx,
            "Alerta de SPAM (Imágenes en varios canales)",
            "image_burst",
            image_bytes=image_bytes,
        )

        # Set muted role
        await ctx.author.add_roles(self.muted_role)

        # Cache the images involved so future occurrences hit the fast path
        for data in image_bytes:
            self.add_spam_image_hash(self._hash_bytes(data))

        # Reset author's channel tracking now that we've acted on it
        self.image_authors[ctx.author] = {}

        await discord.Message.delete(ctx.message)
        msg = (
            f"El mensaje del usuario {ctx.author_mention} fue borrado por compartir "
            "imágenes en varios canales en poco tiempo, lo cual podría indicar una cuenta "
            "comprometida.\nEvita **hacer click** en enlaces o seguir instrucciones de "
            "imágenes de **usuarios que no conozcas**.\nEl equipo de coordinación ha sido "
            "notificado."
        )
        embed = discord.Embed(
            title="\N{NO ENTRY} Alerta de posible SPAM",
            description=msg,
            colour=colors.BRAND,
        )
        await ctx.channel.send(embed=embed, delete_after=300)
        return True

    async def mention_check(self, ctx: MessageContext):
        logger.debug("mention_check: %s", ctx.message.id)

        # Skip if 2 mentions or less
        if (len(ctx.message.mentions) + len(ctx.message.role_mentions)) < config.MENTIONS_LIMIT:
            return False

        await self.alert_moderation(
            ctx,
            "Alerta de Flood (Menciones)",
            "menciones",
        )

        # Set muted role
        await ctx.author.add_roles(self.muted_role)

        _msg = (
            f"Usuario {ctx.author_mention} silenciado por hacer muchas menciones. "
            "El equipo de coordinación ha sido notificado."
        )
        embed = discord.Embed(
            title="\N{NO ENTRY} Alerta de SPAM de menciones",
            description=_msg,
            colour=colors.BRAND,
        )
        # Send message notifying the user is muted
        await ctx.channel.send(embed=embed, delete_after = 300)

        return True

    def add_spam_message(self, message):
        logger.info("add_spam_message: %r", message)
        with open(config.log_spam_file, "a") as f:
            f.write(f"{message}\n")
        self.spam.add(message)

    def add_spam_image_hash(self, digest):
        logger.info("add_spam_image_hash: %s", digest)
        with open(config.log_image_spam_file, "a") as f:
            f.write(f"{digest}\n")
        self.image_spam.add(digest)

    async def alert_moderation(self, ctx: MessageContext, title, reason, image_bytes=None):
        logger.debug("alert_moderation: %s (%s)", title, reason)

        d_msg = {
            "menciones": (
                f"{self.coord_role.mention} Se detectó un mensaje con muchas menciones "
                f"de {ctx.author_mention} y se ha muteado."
            ),
            "flood": (
                f"{self.coord_role.mention} Se detectaron mensajes repetitivos de "
                f"{ctx.author_mention} y se ha muteado."
            ),
            "scam": (
                f"{self.coord_role.mention} Se detectó un mensaje de SCAM de "
                f"{ctx.author_mention} y se ha muteado."
            ),
            "known": (
                f"{self.coord_role.mention} Se detectó un mensaje previamente reconocido "
                f"como spam de {ctx.author_mention} y se ha muteado."
            ),
            "known_image": (
                f"{self.coord_role.mention} Se detectó una imagen previamente reconocida "
                f"como spam/scam de {ctx.author_mention} y se ha muteado."
            ),
            "image_burst": (
                f"{self.coord_role.mention} Se detectaron imágenes enviadas por "
                f"{ctx.author_mention} en varios canales en poco tiempo "
                "(posible cuenta comprometida) y se ha muteado."
            ),
        }
        msg = d_msg[reason]
        embed = discord.Embed(
            title=f"\N{NO ENTRY} {title}",
            description=msg,
            colour=colors.BRAND,
        )
        # Escape backticks so message content can't break out of the inline
        # code span (repr(...)[1:-1] used to do this by stripping repr's
        # quote characters - fragile, and didn't actually escape backticks).
        safe_content = ctx.content.replace("`", "'") if ctx.content else "(sin texto)"
        embed.add_field(name="Mensaje", value=f"`{safe_content}`", inline=False)
        embed.add_field(
            name="En caso de ser spam",
            value=(
                "Recuerda hacer clic en el botón 'Banear Usuario', o haciendo clic derecho sobre su "
                "nick y seleccionando la opción 'Ban'"
            ),
            inline=False,
        )
        embed.add_field(
            name="En caso de ser un error",
            value=(
                'Clic en el botón "Desmutear", o haciendo click derecho en el nick, '
                'luego "Roles" y deselecciona el rol "Muted".'
            ),
            inline=False,
        )
        # Re-upload a sanitized copy of any flagged images so moderators can
        # still see them in the thread after the original message gets
        # deleted. Images from a compromised/malicious account are untrusted
        # input, so they're decoded/re-encoded (stripping anything relying on
        # a malformed file to exploit an image parser) and sent as a spoiler
        # so viewing them requires an explicit click.
        files = []
        if image_bytes:
            for data in image_bytes:
                sanitized = await self._sanitize_bytes(data)
                if sanitized is not None:
                    files.append(sanitized)
            embed.add_field(
                name="\N{WARNING SIGN} Imágenes adjuntas",
                value=(
                    "Las imágenes fueron re-codificadas y se muestran como spoiler por "
                    "provenir de una cuenta comprometida/no confiable. Ábrelas bajo tu "
                    "propio criterio."
                ),
                inline=False,
            )

        view = ModActionView(ctx.author, self._muted_role)
        thread = await self.main_mod_channel.create_thread(name=f"{title} - {ctx.author_mention}",
            auto_archive_duration=60, type=discord.ChannelType.public_thread)
        await thread.send(embed=embed, view=view, files=files)
