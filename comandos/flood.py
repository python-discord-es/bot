import hashlib
import logging
import time

from io import BytesIO

import discord
from discord.ext import commands, tasks
from PIL import Image, UnidentifiedImageError

from configuration import Config
from messages import Messages
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

WARNING_COLOR = 0x2B597B

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

        self.messages = Messages()
        self.messages.spam = config.get_spam_messages()
        self.messages.normal = {}
        self.messages.image_spam = config.get_spam_image_hashes()
        self.messages.image_authors = {}
        self.guild = None

        self._coord_role: Optional[discord.Role] = None
        self._muted_role: Optional[discord.Role] = None

        self._msg_channel: Optional[discord.TextChannel | discord.ForumChannel | discord.VoiceChannel] = None
        self._msg_content: Optional[str] = None
        self._msg_author: Optional[discord.Member] = None
        self._msg_author_mention: Optional[str] = None

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
        self.messages.normal = {}
        self.messages.image_authors = {}

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
        self._msg_channel = self.bot.get_channel(message.channel.id)
        self._msg_content = strip_message(message.content)
        self._msg_author = message.author
        self._msg_author_mention = self._msg_author.mention

        # skip coord role
        if self.coord_role in self._msg_author.roles:
            return

        if await self.attachment_check(message):
            return

        if await self.flood_check(message):
            return

        if self._msg_content in self.messages.spam:
            await self.alert_moderation(
                "Alerta de SPAM (Mensaje conocido)",
                "known",
            )

            # Set muted role
            await self._msg_author.add_roles(self.muted_role)

            await discord.Message.delete(message)
            msg = (
                f"El mensaje del usuario {self._msg_author_mention} fue borrado por ser un "
                "mensaje detectado previamente como spam.\n"
            )
            embed = discord.Embed(
                title="\N{NO ENTRY} Alerta de posible SPAM",
                description=msg,
                colour=WARNING_COLOR,
            )
            await self._msg_channel.send(embed=embed, delete_after = 60)

        # Check first more than 3 mentions
        if await self.mention_check(message):
            self.add_spam_message(self._msg_content)
            await discord.Message.delete(message)
            msg = (
                f"El mensaje del usuario {self._msg_author_mention} fue borrado por tener muchas "
                "menciones y podría ser un engaño.\nEvita `hacer click` en enlaces de "
                "**usuarios que no conozcas**."
            )
            embed = discord.Embed(
                title="\N{NO ENTRY} Alerta de posible SPAM",
                description=msg,
                colour=WARNING_COLOR,
            )
            await self._msg_channel.send(embed=embed, delete_after=300)

        if await self.spam_check(message):
            self.add_spam_message(self._msg_content)
            await discord.Message.delete(message)
            msg = (
                f"El mensaje del usuario {self._msg_author_mention} fue borrado y podría ser "
                "un engaño.\nEvita `hacer click` en enlaces de **usuarios que no conozcas**."
            )
            embed = discord.Embed(
                title="\N{NO ENTRY} Alerta de posible SCAM",
                description=msg,
                colour=WARNING_COLOR,
            )
            await self._msg_channel.send(embed=embed, delete_after = 300)

    async def spam_check(self, message: discord.Message):
        author = message.author

        if not isinstance(author, discord.Member):
            return

        if not any(all(i in message.content for i in sw) for sw in SPAM_WORDS):
            return False

        await self.alert_moderation("Alerta de SCAM", "scam")

        # Set muted role
        await author.add_roles(self.muted_role)

        _msg = (
            f"Usuario {author.mention} silenciado por compartir un mensaje que "
            "parece contener enlaces de engaño. El equipo de coordinación ha sido notificado."
        )
        embed = discord.Embed(
            title="\N{NO ENTRY} Alerta de posible SCAM",
            description=_msg,
            colour=WARNING_COLOR,
        )
        # Send message notifying the user is muted
        await message.channel.send(embed=embed, delete_after = 300)
        return True

    async def flood_check(self, message):
        logger.debug("flood_check: %s", message.id)

        # Textless (image-only) messages are handled by attachment_check
        if not self._msg_content:
            return False

        if self._msg_author not in self.messages.normal:
            self.messages.normal[self._msg_author] = {self._msg_content: 1}
        else:
            if self._msg_content not in self.messages.normal[self._msg_author]:
                self.messages.normal[self._msg_author][self._msg_content] = 1
            else:
                self.messages.normal[self._msg_author][self._msg_content] += 1
                if self.messages.normal[self._msg_author][self._msg_content] >= config.FLOOD_LIMIT:
                    self.add_spam_message(self._msg_content)
                    await self.alert_moderation(
                        "Alerta de Flood",
                        "flood",
                    )

                    # Set muted role
                    await self._msg_author.add_roles(self.muted_role)

                    # Reset author counters
                    self.messages.normal[self._msg_author] = {}

                    _msg = (
                        f"Usuario {self._msg_author_mention} silenciado por enviar mensajes "
                        "repetitivos. El equipo de coordinación ha sido notificado."
                    )
                    embed = discord.Embed(
                        title="\N{NO ENTRY} Alerta de posible SCAM",
                        description=_msg,
                        colour=WARNING_COLOR,
                    )
                    # Send message notifying the user is muted
                    await self._msg_channel.send(embed=embed, delete_after = 120)

    @staticmethod
    async def _hash_attachment(attachment: discord.Attachment) -> str:
        data = await attachment.read()
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    async def _sanitize_attachment(attachment: discord.Attachment) -> Optional[discord.File]:
        """Decode and re-encode an attachment before it's shown to moderators.

        Images from a compromised/malicious account are untrusted input: a
        crafted file could try to exploit a bug in whatever renders its
        thumbnail (e.g. the libwebp CVE-2023-4863 heap overflow). Re-encoding
        via Pillow into a fresh PNG strips anything relying on a malformed
        file structure, and the result is still sent as a spoiler so viewing
        it requires an explicit click rather than an automatic preview.
        Returns ``None`` if the attachment can't be safely decoded.
        """
        try:
            data = await attachment.read()
            with Image.open(BytesIO(data)) as img:
                img.load()
                clean = img.convert("RGB")
            buf = BytesIO()
            clean.save(buf, format="PNG")
            buf.seek(0)
            return discord.File(buf, filename="evidencia.png", spoiler=True)
        except (UnidentifiedImageError, OSError, ValueError):
            logger.warning("_sanitize_attachment: could not decode %r, skipping", attachment.filename)
            return None

    async def attachment_check(self, message: discord.Message) -> bool:
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
        logger.debug("attachment_check: %s", message.id)

        images = [
            a for a in message.attachments
            if (a.content_type or "").startswith("image/")
        ]
        if not images:
            return False

        # Fast path: any image already known to be spam/scam
        for attachment in images:
            digest = await self._hash_attachment(attachment)
            if digest in self.messages.image_spam:
                await self.alert_moderation(
                    "Alerta de SPAM (Imagen conocida)",
                    "known_image",
                    attachments=images,
                )

                # Set muted role
                await self._msg_author.add_roles(self.muted_role)

                await discord.Message.delete(message)
                msg = (
                    f"El mensaje del usuario {self._msg_author_mention} fue borrado por "
                    "contener una imagen detectada previamente como spam."
                )
                embed = discord.Embed(
                    title="\N{NO ENTRY} Alerta de posible SPAM",
                    description=msg,
                    colour=WARNING_COLOR,
                )
                await self._msg_channel.send(embed=embed, delete_after=60)
                return True

        if len(images) < config.IMAGE_ATTACHMENT_LIMIT:
            return False

        # Burst path: same author, 2+ images, 2+ different channels, short window
        now = time.time()
        channels = self.messages.image_authors.get(self._msg_author, {})
        channels = {
            channel_id: ts
            for channel_id, ts in channels.items()
            if now - ts <= config.IMAGE_BURST_WINDOW
        }
        channels[message.channel.id] = now
        self.messages.image_authors[self._msg_author] = channels

        if len(channels) < 2:
            return False

        await self.alert_moderation(
            "Alerta de SPAM (Imágenes en varios canales)",
            "image_burst",
            attachments=images,
        )

        # Set muted role
        await self._msg_author.add_roles(self.muted_role)

        # Cache the images involved so future occurrences hit the fast path
        for attachment in images:
            digest = await self._hash_attachment(attachment)
            self.add_spam_image_hash(digest)

        # Reset author's channel tracking now that we've acted on it
        self.messages.image_authors[self._msg_author] = {}

        await discord.Message.delete(message)
        msg = (
            f"El mensaje del usuario {self._msg_author_mention} fue borrado por compartir "
            "imágenes en varios canales en poco tiempo, lo cual podría indicar una cuenta "
            "comprometida.\nEvita **hacer click** en enlaces o seguir instrucciones de "
            "imágenes de **usuarios que no conozcas**."
        )
        embed = discord.Embed(
            title="\N{NO ENTRY} Alerta de posible SCAM",
            description=msg,
            colour=WARNING_COLOR,
        )
        await self._msg_channel.send(embed=embed, delete_after=300)
        return True

    async def mention_check(self, message):
        logger.debug("mention_check: %s", message.id)

        # Skip if 2 mentions or less
        if (len(message.mentions) + len(message.role_mentions)) < config.MENTIONS_LIMIT:
            return False

        await self.alert_moderation(
            "Alerta de Flood (Menciones)",
            "menciones",
        )

        # Set muted role
        await self._msg_author.add_roles(self.muted_role)

        _msg = (
            f"Usuario {self._msg_author_mention} silenciado por hacer muchas menciones. "
            "El equipo de coordinación ha sido notificado."
        )
        embed = discord.Embed(
            title="\N{NO ENTRY} Alerta de SPAM de menciones",
            description=_msg,
            colour=WARNING_COLOR,
        )
        # Send message notifying the user is muted
        await self._msg_channel.send(embed=embed, delete_after = 300)

        return True

    def add_spam_message(self, message):
        logger.info("add_spam_message: %r", message)
        with open(config.log_spam_file, "a") as f:
            f.write(f"{message}\n")
        self.messages.spam.add(message)

    def add_spam_image_hash(self, digest):
        logger.info("add_spam_image_hash: %s", digest)
        with open(config.log_image_spam_file, "a") as f:
            f.write(f"{digest}\n")
        self.messages.image_spam.add(digest)

    async def alert_moderation(self, title, reason, attachments=None):
        logger.debug("alert_moderation: %s (%s)", title, reason)

        d_msg = {
            "menciones": (
                f"{self.coord_role.mention} Se detectó un mensaje con muchas menciones "
                f"de {self._msg_author_mention} y se ha muteado."
            ),
            "flood": (
                f"{self.coord_role.mention} Se detectaron mensajes repetitivos de "
                f"{self._msg_author_mention} y se ha muteado."
            ),
            "scam": (
                f"{self.coord_role.mention} Se detectó un mensaje de SCAM de "
                f"{self._msg_author_mention} y se ha muteado."
            ),
            "known": (
                f"{self.coord_role.mention} Se detectó un mensaje previamente reconocido "
                f"como spam de {self._msg_author_mention} y se ha muteado."
            ),
            "known_image": (
                f"{self.coord_role.mention} Se detectó una imagen previamente reconocida "
                f"como spam/scam de {self._msg_author_mention} y se ha muteado."
            ),
            "image_burst": (
                f"{self.coord_role.mention} Se detectaron imágenes enviadas por "
                f"{self._msg_author_mention} en varios canales en poco tiempo "
                "(posible cuenta comprometida) y se ha muteado."
            ),
        }
        msg = d_msg[reason]
        embed = discord.Embed(
            title=f"\N{NO ENTRY} {title}",
            description=msg,
            colour=WARNING_COLOR,
        )
        embed.add_field(name="Mensaje", value=f"`{repr(self._msg_content)[1:-1]}`", inline=False)
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
        if attachments:
            for attachment in attachments:
                sanitized = await self._sanitize_attachment(attachment)
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

        view = ModActionView(self._msg_author, self._muted_role)
        thread = await self.main_mod_channel.create_thread(name=f"{title} - {self._msg_author_mention}",
            auto_archive_duration=60, type=discord.ChannelType.public_thread)
        await thread.send(embed=embed, view=view, files=files)