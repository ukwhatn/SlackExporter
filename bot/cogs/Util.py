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
