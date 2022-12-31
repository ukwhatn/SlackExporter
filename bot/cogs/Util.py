import math
import re

import discord
from discord.commands import slash_command
from discord.ext import commands


class Util(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @slash_command(name="sort", description="カテゴリ内のチャンネルを名前順にソートします")
    @commands.is_owner()
    async def sort_channels(self, ctx: discord.commands.context.ApplicationContext):
        await ctx.respond("開始します", ephemeral=True)

        chs_in_category = ctx.channel.category.channels
        chs_in_category.sort(key=lambda ch: ch.name)

        for i, ch in enumerate(chs_in_category):
            await ch.edit(position=i)

        await ctx.respond("完了しました", ephemeral=True)

    @slash_command(name="sort_multi_categories", description="複数カテゴリ内のChを名前順にソートします")
    @commands.is_owner()
    async def sort_multi_categories(
            self, ctx: discord.commands.context.ApplicationContext,
            name_contains: str
    ):
        await ctx.respond("開始します", ephemeral=True)

        categories = [category for category in ctx.guild.categories if name_contains.lower() in category.name.lower()]
        categories.sort(key=lambda category: category.name)

        channels = [channel for category in categories for channel in category.channels]
        channels.sort(key=lambda channel: channel.name)

        sort_result = [[] for _ in range(len(categories))]
        for i, channel in enumerate(channels, 1):
            sort_result[math.floor(i / 50)].append(channel)

        for i, category in enumerate(categories):
            # 同一パラメータでカテゴリを作成
            new_category = await ctx.guild.create_category(
                name=category.name,
                overwrites=category.overwrites,
                position=category.position,
            )

            for j, channel in enumerate(sort_result[i]):
                await channel.edit(category=new_category, position=j)

            if len(category.channels) == 0:
                await category.delete()

        await ctx.respond("完了しました", ephemeral=True)

    @slash_command(name="purge_channels", description="カテゴリ内のチャンネルを全て削除します")
    @commands.is_owner()
    async def purge_channels(self, ctx: discord.commands.context.ApplicationContext):
        await ctx.respond("開始します", ephemeral=True)

        for ch in ctx.channel.category.channels:
            if ch.id == ctx.channel.id:
                continue
            await ch.delete()


def setup(bot):
    return bot.add_cog(Util(bot))
