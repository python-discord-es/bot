import base64
from datetime import datetime

import discord
from discord.ext import commands


class Encuesta(commands.Cog):
    def __init__(self, bot, log_file):
        self.bot = bot
        self.log_file = log_file

    @commands.command(name="encuesta", help="Comando de encuesta", pass_context=True)
    async def encuesta(self, ctx, *args):
        def get_number_emoji(n):
            if 0 <= n < 10:
                return f"{n}\N{COMBINING ENCLOSING KEYCAP}"
            else:
                return n

        # Log
        with open(str(self.log_file), "a") as f:
            # date;command;message_id;channel;author;message
            message = " ".join(args).encode("utf-8")
            message_enc = base64.b64encode(message)
            line = (
                f'"{datetime.now()}";'
                f'"encuesta";'
                f'"{ctx.message.id}";'
                f'"{ctx.channel.name}";'
                f'"{ctx.message.author.id}";'
                f'"{ctx.message.author}";'
                f'"{message_enc}"\n'
            )
            f.write(line)

        # Errors
        n = len(args)
        if n < 1:
            e = self.get_help_error()
            await ctx.send(embed=e)
            return

        # Error, because one question, with one option makes no sense.
        elif n == 2:
            await ctx.send("\N{NO ENTRY} No es posible tener solo una opción por pregunta.")
            return

        head = f"**Encuesta \N{BAR CHART}**\n" f"Pregunta: **{args[0]}**\n\n"
        foot = "\n\n¡Participa utilizando las reacciones al mensaje \N{HAPPY PERSON RAISING ONE HAND}!"

        # Only one arg, assumes a Yes/No question
        if n == 1:
            si_emoji = "\N{WHITE HEAVY CHECK MARK}"
            no_emoji = "\N{CROSS MARK}"

            msg = await ctx.send(f"{head}{si_emoji} Sí\n{no_emoji} No{foot}")

            await msg.add_reaction(si_emoji)
            await msg.add_reaction(no_emoji)

        # Maximum options: 10
        elif n < 11:
            body = "\n".join(f"{get_number_emoji(i-1)} {args[i]}" for i in range(1, n))
            msg = await ctx.send(f"{head}{body}{foot}")

            for i in range(1, n):
                await msg.add_reaction(get_number_emoji(i - 1))
        await discord.Message.delete(ctx.message)


    def get_help_error(self):
        embed = discord.Embed(
            title="\N{NO ENTRY} No se encontró ningún argumento.\n\n",
            description="**¿Cómo realizar encuestas?**",
            colour=0x2B597B,
        )
        embed.add_field(name="Para preguntas de Sí y No", value='`%encuesta "pregunta"`', inline=False)
        embed.add_field(
            name="Para preguntas de varias opciones",
            value='`%encuesta "pregunta" "opción 1" "opción 2" ...`',
            inline=False,
        )
        return embed
