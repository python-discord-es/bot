import base64
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

from configuration import Config

config = Config()


class Encuesta(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # FIXME: Here the problem is that with app_commands  I couldn't
    # figure out the option of having "*option" (former implementation),
    # but for slash commands. Tried to look for "multiple optional commands"
    # but I couldn't find anything.
    @commands.hybrid_command(name="encuesta", help="Comando de encuesta", pass_context=True)
    async def encuesta(
        self,
        ctx,
        pregunta: str,
        option_0: Optional[str] = "",
        option_1: Optional[str] = "",
        option_2: Optional[str] = "",
        option_3: Optional[str] = "",
        option_4: Optional[str] = "",
        option_5: Optional[str] = "",
        option_6: Optional[str] = "",
        option_7: Optional[str] = "",
        option_8: Optional[str] = "",
        option_9: Optional[str] = "",
    ):
        def get_number_emoji(n):
            if 0 <= n < 10:
                return f"{n}\N{COMBINING ENCLOSING KEYCAP}"
            else:
                return n

        if not pregunta:
            e = self.get_help_error()
            await ctx.send(embed=e)
            return

        options = [
            option_0,
            option_1,
            option_2,
            option_3,
            option_4,
            option_5,
            option_6,
            option_7,
            option_8,
            option_9,
        ]

        # Log
        with open(str(config.log_file), "a") as f:
            # date;command;message_id;channel;author;message
            message = " ".join(options).encode("utf-8")
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

        head = f"**Encuesta \N{BAR CHART}**\n" f"Pregunta: **{pregunta}**\n\n"
        foot = (
            "\n\n¡Participa utilizando las reacciones al mensaje \N{HAPPY PERSON RAISING ONE HAND}!"
        )

        # Errors
        n = sum(1 for o in options if o)

        # Only one arg, assumes a Yes/No question
        if n == 0:
            si_emoji = "\N{WHITE HEAVY CHECK MARK}"
            no_emoji = "\N{CROSS MARK}"

            msg = await ctx.send(f"{head}{si_emoji} Sí\n{no_emoji} No{foot}")

            await msg.add_reaction(si_emoji)
            await msg.add_reaction(no_emoji)

        # Error, because one question, with one option makes no sense.
        elif n == 1:
            await ctx.send("\N{NO ENTRY} No es posible tener solo una opción por pregunta.")
            return
        else:
            # Collapse options
            options = [o for o in options if o]

            body = "\n".join(f"{get_number_emoji(i)} {options[i]}" for i in range(n))
            msg = await ctx.send(f"{head}{body}{foot}")

            for i in range(1, n):
                await msg.add_reaction(get_number_emoji(i - 1))

        try:
            await discord.Message.delete(ctx.message)
        except discord.NotFound:
            print("Using slash command, no need to remove original message")

    def get_help_error(self):
        embed = discord.Embed(
            title="\N{NO ENTRY} No se encontró ningún argumento.\n\n",
            description="**¿Cómo realizar encuestas?**",
            colour=0x2B597B,
        )
        embed.add_field(
            name="Para preguntas de Sí y No",
            value='`%encuesta "pregunta"`',
            inline=False,
        )
        embed.add_field(
            name="Para preguntas de varias opciones",
            value='`%encuesta "pregunta" "opción 1" "opción 2" ...`',
            inline=False,
        )
        return embed
