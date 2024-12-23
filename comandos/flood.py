import discord
from discord.ext import commands, tasks

from configuration import Config
from messages import Messages
from utils import strip_message

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


class FloodSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.main_mod_channel = None

        self.messages = Messages()
        self.messages.spam = config.get_spam_messages()
        self.messages.normal = {}
        self.guild = None

        self.coord_role = None
        self.muted_role = None

        self._msg_channel = None
        self._msg_content = None
        self._msg_author = None
        self._msg_author_mention = None

    @commands.Cog.listener()
    async def on_ready(self):
        # Setting up variables on the first message
        if self.guild is None:
            self.guild = self.bot.get_guild(config.GUILD)

        if self.coord_role is None:
            self.coord_role = discord.utils.get(self.guild.roles, name=config.MOD_ROLE)

        if self.muted_role is None:
            self.muted_role = discord.utils.get(self.guild.roles, name=config.MUTED_ROLE)

        if self.main_mod_channel is None:
            self.main_mod_channel = self.bot.get_channel(config.MOD_MAIN)

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

        print("LOG: setting data from message")
        self._msg_channel = self.bot.get_channel(message.channel.id)
        self._msg_content = strip_message(message.content)
        self._msg_author = message.author
        self._msg_author_mention = self._msg_author.mention

        # skip when user has more roles
        if len(self._msg_author.roles) > 1:
            return

        print("FloodSpam.on_message: flood check")
        if await self.flood_check(message):
            return

        print("FloodSpam.on_message: spam check")
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
            await self._msg_channel.send(embed=embed)

        # Check first more than 3 mentions
        print("FloodSpam.on_message: mention_check")
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
            await self._msg_channel.send(embed=embed)

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
            await self._msg_channel.send(embed=embed)

    async def spam_check(self, message):
        print("LOG: spam_check")

        if not any(all(i in self._msg_content for i in sw) for sw in SPAM_WORDS):
            return False

        await self.alert_moderation("Alerta de SCAM", "scam")

        # Set muted role
        await self._msg_author.add_roles(self.muted_role)

        _msg = (
            f"Usuario {self._msg_author_mention} silenciado por compartir un mensaje que "
            "parece contener enlaces de engaño. El equipo de coordinación ha sido notificado."
        )
        embed = discord.Embed(
            title="\N{NO ENTRY} Alerta de posible SCAM",
            description=_msg,
            colour=WARNING_COLOR,
        )
        # Send message notifying the user is muted
        await self._msg_channel.send(emebed=embed)
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
                    await self._msg_channel.send(embed=embed)

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
        await self._msg_channel.send(embed=embed)

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
                f"{self.coord_role.mention} Se detectaton mensajes repetitivos de "
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
        print(msg)
        embed = discord.Embed(
            title=f"\N{NO ENTRY} {title}",
            description=msg,
            colour=WARNING_COLOR,
        )
        embed.add_field(name="Mensaje", value=f"{self._msg_content}", inline=False)
        embed.add_field(
            name="En caso de ser spam",
            value=(
                "Recuerda banear al usuario haciendo click derecho sobre su "
                "nick y seleccionando la opción 'Ban'"
            ),
            inline=False,
        )
        embed.add_field(
            name="En caso de ser un error",
            value=(
                'Remueve el rol "Muted" haciendo click derecho en el nick, '
                'luego "Roles" y deselecciona el rol "Muted".'
            ),
            inline=False,
        )

        await self.main_mod_channel.send(embed=embed)
