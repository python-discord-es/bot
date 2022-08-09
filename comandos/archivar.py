import discord
from datetime import datetime
from discord.ext import commands

class Archivar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="archivar", help="Comando para archivar canales", pass_context=True)
    @commands.has_role(config.MOD_ROLE)
    async def archivar(self, ctx, *, channel: discord.TextChannel):
        global main_mod_channel

        if not main_mod_channel:
            main_mod_channel = bot.get_channel(config.MOD_MAIN)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_canal_{channel.name}.csv"
        messages = await channel.history(limit=None).flatten()

        status = self.archivar_canal(filename, messages)


        if status:
            e = discord.Embed(
                title=f"\N{PAGE FACING UP} Canal Archivado",
                description=f"El canal {channel.mention} tiene {len(messages)} mensajes",
                colour=0xFF0000,
            )
            await main_mod_channel.send(embed=e, file=discord.File(filename))
        else:
            await main_mod_channel.send(f"Error: Canal '{channel.name}' no fue archivado.")

    @commands.command(name="archivar_categoria", help="Comando para archivar los canales de una categoría", pass_context=True)
    @commands.has_role(config.MOD_ROLE)
    async def archivar_categoria(self, ctx, *, category: discord.CategoryChannel):
        global main_mod_channel

        if not main_mod_channel:
            main_mod_channel = bot.get_channel(config.MOD_MAIN)

        channels = category.channels
        for channel in channels:
            if isinstance(channel, discord.channel.TextChannel):
                await archivar(ctx, channel=channel)
                #timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                #filename = f"{timestamp}_canal_{channel.name}.csv"
                #messages = await channel.history(limit=None).flatten()
                #status = archivar_canal(filename, messages)
                #if status:
                #    await main_mod_channel.send(f"Canal '{channel.mention}' archivado.", file=discord.File(filename))
                #else:
                #    await main_mod_channel.send(f"Error: Canal '{channel.name}' no fue archivado.")

    def archivar_canal(self, filename: str, messages: List[discord.Message]):

        try:
            with open(filename, "w") as f:
                f.write("id;content;channel_id;channel_name;channel_category;author_id;"
                        "author_username;author_is_bot\n")

                for msg in messages:
                    m_id = msg.id
                    m_content = msg.content.strip().replace("\n", "\\n")
                    m_channel_id = msg.channel.id
                    m_channel_name = msg.channel.name
                    m_channel_category = msg.channel.category_id
                    m_author_id = msg.author.id
                    m_author_name = msg.author.name
                    m_author_discriminator = msg.author.discriminator
                    m_author_bot = msg.author.bot
                    f.write(f"{m_id};{m_content};{m_channel_id};{m_channel_name};{m_channel_category};"
                            f"{m_author_id};{m_author_name}#{m_author_discriminator};{m_author_bot}\n")
            print(f"File written: {filename}")
        except Exception as e:
            print(f"{type(e).__name__}: {e}")
            return False, None

        return True, filename

