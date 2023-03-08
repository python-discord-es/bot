import discord
from discord.ext import commands


class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="ping", help="Comando de prueba", pass_context=True, with_app_command=True
    )
    async def pingpong(self, ctx: commands.Context):
        await ctx.send("pong", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if self.bot.user.mentioned_in(message):
            picture = None
            with open("resources/llama.gif", "rb") as f:
                picture = discord.File(f)

            if picture is None:
                await message.channel.send("*beep boop*")
            else:
                await message.channel.send(file=picture)
