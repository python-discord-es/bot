from discord.ext import commands
from discord import app_commands, Embed, NotFound

from configuration import Config

config = Config()


class Limpia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.has_role(config.MOD_ROLE)
    @commands.hybrid_command(
        name="limpia",
        help="Comando para borrar mensajes",
        pass_context=True,
    )
    @app_commands.describe(
        limit="Number of messages to remove (default: 5). If '-1' is passed, all messages are removed.",
    )
    async def purge(self, ctx: commands.Context, limit: int = 1) -> None:
        print(dir(ctx.message.reference))
        if hasattr(ctx.message.reference, "message_id"):
            reply_id = ctx.message.reference.message_id
            msg = []
            async for m in ctx.channel.history():
                msg.append(m)
                if m.id == reply_id:
                    break
            await ctx.channel.delete_messages(msg)
        else:
            await ctx.defer(ephemeral=True)
            await ctx.channel.purge(limit=limit + 1)
            try:
                await ctx.message.delete()
            except NotFound:
                print("Slash command, no need to remove command message")

            # await ctx.channel.typing()
            embed = Embed(
                title=f"Borrados '{limit}' mensajes\n\n",
                description=f"Comando ejecuta por {ctx.author.mention}",
                colour=0x178D38,
            )
            await ctx.send(embed=embed, ephemeral=True)
            await ctx.channel.purge(limit=1)
