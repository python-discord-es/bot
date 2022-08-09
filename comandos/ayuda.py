from discord.ext import commands


class Ayuda(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ayuda", help="Comando de ayuda", pass_context=True)
    async def mensaje_ayuda(self, ctx):

        # Skip if it's the bot
        if ctx.author.id == config.BOT_ID:
            return

        # Check which channel combination we are using from the
        # configuration information
        channel_mod = get_moderation_channel(ctx.channel.id)

        if channel_mod:
            e = self.get_mod_help()
            await channel_mod.send(embed=e)
        else:
            e = self.get_main_help()
            await ctx.channel.send(embed=e)

    def get_mod_help(self):
        embed = discord.Embed(
            title="Comandos Disponibles",
            colour=0x2B597B,
        )
        embed.add_field(
            name="`%mod`", value="Lista todos los post pendientes de moderación", inline=False
        )
        embed.add_field(
            name="`%mod ID`",
            value="Lista información del post ID pendiente de moderación",
            inline=False,
        )
        embed.add_field(
            name="`%aceptar ID`", value="Acepta mensaje, lo envia al canal asociado", inline=False
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
            name="`%limpia`", value="Limpia N mensajes del canal de moderación", inline=False
        )
        return embed

    def get_main_help(self):
        embed = discord.Embed(
            title="Comandos Disponibles",
            colour=0x2B597B,
        )
        embed.add_field(
            name='`%encuesta "pregunta"`',
            value=("Para hacer preguntas de Sí y No.\n" 'Ejemplo:\n `%encuesta "¿Te gusta el té?"`'),
            inline=False,
        )
        embed.add_field(
            name='`%encuesta "pregunta" "opción a" "opción b" ...`',
            value=(
                "Para hacer preguntas con varias opciones.\n"
                'Ejemplo:\n `%encuesta "¿Lenguaje favorito?" "Inglés" "Español" "Python"`'
            ),
            inline=False,
        )
        embed.set_footer(text='Importante: La pregunta y opciones deben ir entre comillas dobles "..."')
        return embed

