import discord
from discord.ext import commands

import colors
from configuration import Config

config = Config()


class Ayuda(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ayuda", help="Comando de ayuda")
    async def mensaje_ayuda(self, ctx):
        # Skip if it's the bot
        if ctx.author.id == config.BOT_ID:
            return

        await ctx.channel.send(embed=self.get_mod_help())

    @commands.command(
        name="terminos",
        help="Muestra el enlace a los Términos de Uso y Política de Datos del bot",
    )
    async def terminos(self, ctx):
        await ctx.channel.send(
            "\N{PAGE FACING UP} Términos de Uso y Política de Datos de LlamaBot: "
            f"{config.TERMS_URL}"
        )

    def get_mod_help(self):
        embed = discord.Embed(
            title="Comandos Disponibles",
            colour=colors.BRAND,
        )
        embed.add_field(
            name="`%mod`",
            value="Lista todos los post pendientes de moderación",
            inline=False,
        )
        embed.add_field(
            name="`%mod ID`",
            value="Lista información del post ID pendiente de moderación",
            inline=False,
        )
        embed.add_field(
            name="`%aceptar ID`",
            value="Acepta mensaje, lo envia al canal asociado",
            inline=False,
        )
        embed.add_field(
            name="`%rechazar ID RAZON`",
            value=(
                "Rechaza el mensaje ID, lo envia al canal asociado. "
                "El usuario será notificado, con el mensaje RAZON"
            ),
            inline=False,
        )
        embed.add_field(
            name="`%limpia`",
            value="Limpia N mensajes del canal de moderación",
            inline=False,
        )
        embed.add_field(
            name="`%terminos`",
            value="Muestra el enlace a los Términos de Uso y Política de Datos del bot",
            inline=False,
        )
        return embed
