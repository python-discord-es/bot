from discord.ext import commands
from discord import TextChannel, Embed, app_commands

import colors
from configuration import Config

config = Config()


class Enviar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.has_role(config.MOD_ROLE)
    @commands.hybrid_command(name="enviar", description="Send message to a channel")
    @app_commands.describe(
        channel="Channel name (using '#') to send the message",
        message="Message content, without quotes",
    )
    async def enviar(self, ctx: commands.Context, channel: TextChannel, *, message: str):

        reply_embed = Embed(
            title=f"Mensaje enviado a {channel}",
            description=f"{channel.mention}:\n{message}",
            colour=colors.BROADCAST,
        )

        try:
            await ctx.reply(embed=reply_embed)
        except AttributeError:
            await ctx.channel.send(embed=reply_embed)

        embed = Embed(
            title="Mensaje de Coordinación",
            description=message,
            colour=colors.BROADCAST,
        )

        # Send the command to the channel passed to the command
        await channel.send(embed=embed)
