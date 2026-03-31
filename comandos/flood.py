import discord
from discord.ext import commands, tasks

from configuration import Config
from messages import Messages
from utils import strip_message

from typing import Optional

config = Config()

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

    @commands.Cog.listener()
    async def on_message(self, message):
        print("FloodSpam.on_message")
        await self.bot.process_commands(message)

        if message.author.bot or message.author.id == config.BOT_ID:
            return

        if len(message.content) < 5:
            return
        self._msg_channel = self.bot.get_channel(message.channel.id)
        self._msg_content = strip_message(message.content)
        self._msg_author = message.author
        self._msg_author_mention = self._msg_author.mention

        # skip coord role
        if self.coord_role in self._msg_author.roles:
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

        print("FloodSpam.on_message: spam_check")
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
        print(f"LOG: flood_check: {message}")

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

    async def mention_check(self, message):
        print("LOG: mention_check")

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
        print("LOG: add_spam_message")
        with open(config.log_spam_file, "a") as f:
            f.write(f"{message}\n")
        self.messages.spam.add(message)

    async def alert_moderation(self, title, reason):
        print("LOG: alert_moderation")

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
        view = ModActionView(self._msg_author, self._muted_role)
        thread = await self.main_mod_channel.create_thread(name=f"{title} - {self._msg_author_mention}",
            auto_archive_duration=60, type=discord.ChannelType.public_thread)
        await thread.send(embed=embed, view=view)