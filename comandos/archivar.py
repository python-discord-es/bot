from datetime import datetime
from typing import List

import discord
from discord.ext import commands

from configuration import Config

config = Config()


class Archivar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mod_channel = None

    @commands.Cog.listener()
    async def on_ready(self):
        if self.mod_channel is None:
            self.mod_channel = self.bot.get_channel(config.MOD_MAIN)

    @commands.command(name="archivar", help="Comando para archivar canales", pass_context=True)
    @commands.has_role(config.MOD_ROLE)
    async def archivar(self, ctx, *, channel: discord.TextChannel):

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_canal_{channel.name}.csv"
        messages = [m async for m in channel.history(limit=None)]

        status = self.archivar_canal(filename, messages)

        if status:
            e = discord.Embed(
                title="\N{PAGE FACING UP} Canal Archivado",
                description=f"El canal {channel.mention} tiene {len(messages)} mensajes",
                colour=0xFF0000,
            )
            await self.mod_channel.send(embed=e, file=discord.File(filename))
        else:
            await self.mod_channel.send(f"Error: Canal '{channel.name}' no fue archivado.")

    @commands.command(
        name="archivar_categoria",
        help="Comando para archivar los canales de una categoría",
        pass_context=True,
    )
    @commands.has_role(config.MOD_ROLE)
    async def archivar_categoria(self, ctx, *, category: discord.CategoryChannel):

        channels = category.channels
        for channel in channels:
            if isinstance(channel, discord.channel.TextChannel):
                await self.archivar(ctx, channel=channel)

    def archivar_canal(self, filename: str, messages: List[discord.Message]):
        try:
            with open(filename, "w") as f:
                f.write(
                    "id;content;channel_id;channel_name;channel_category;author_id;"
                    "author_username;author_is_bot\n"
                )

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
                    f.write(
                        f"{m_id};{m_content};{m_channel_id};{m_channel_name};{m_channel_category};"
                        f"{m_author_id};{m_author_name}#{m_author_discriminator};{m_author_bot}\n"
                    )
            print(f"File written: {filename}")
        except Exception as e:
            print(f"{type(e).__name__}: {e}")
            return False, None

        return True, filename
