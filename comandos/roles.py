import discord
from discord.ext import commands
from enum import Enum
from textwrap import dedent

from configuration import Config

config = Config()

add_emoji = "\N{HEAVY PLUS SIGN}"
del_emoji = "\N{HEAVY MINUS SIGN}"
check_emoji = "\N{WHITE HEAVY CHECK MARK}"
cross_emoji = "\N{CROSS MARK}"


class RoleButton(discord.ui.Button["Role"]):
    def __init__(self, x: int, y: int, label: str, style: discord.ButtonStyle):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y
        self.label = label
        self.style = style

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: Role = self.view

        role = self.view.labels[self.label]["role"]
        action = self.view.labels[self.label]["action"]

        rol_name = "".join(self.label.split()[1:])

        msg = desc = ""
        if action == "add":
            msg = f"{check_emoji} Agregando Rol"
            desc = f"Rol **{rol_name}** agregado a {interaction.user.mention}",
            await interaction.user.add_roles(role)
        elif action == "del":
            msg = f"{cross_emoji} Quitando Rol"
            desc=f"Rol **{rol_name}** removido de {interaction.user.mention}",
            await interaction.user.remove_roles(role)

        embed = discord.Embed(
            title=msg,
            colour=0xda373c,
            description=desc,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)


class RolesView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.value = None
        self.guild = guild

        self.labels = {}

        for rn in config.ROLES.keys():
            rol = discord.utils.get(self.guild.roles, name=rn)
            self.labels[f"{add_emoji} {rn}"] = {
                "role": rol,
                "action": "add",
                "style": discord.ButtonStyle.primary,
            }

            self.labels[f"{del_emoji} {rn}"] = {
                "role": rol,
                "action": "del",
                "style": discord.ButtonStyle.red,
            }

        for idx, (label, d) in enumerate(self.labels.items()):
            x = idx // 2
            y = idx % 2
            self.add_item(RoleButton(x, y, label, d["style"]))


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guild = None

    @commands.Cog.listener()
    async def on_ready(self):
        if self.guild is None:
            self.guild = self.bot.get_guild(config.GUILD)

        channel_roles = self.bot.get_channel(config.ROLES_CHANNEL)
        await channel_roles.purge()
        view = RolesView(self.guild)

        embed = discord.Embed(
            title="¿Qué rol te gustaría tener?",
            colour=0xFF8331,
        )

        for rol, desc in config.ROLES.items():
            embed.add_field(
                name=f"■ {rol}",
                value=desc,
                inline=False,
            )

        await channel_roles.send(embed=embed, view=view)
