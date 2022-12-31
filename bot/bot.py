import logging

import discord
from discord.ext import commands
import sentry_sdk

from config import bot_config

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s"
)

sentry_sdk.init(
    dsn=bot_config.SENTRY_DSN,
    traces_sample_rate=1.0
)

# bot init
bot = commands.Bot(help_command=None,
                   case_insensitive=True,
                   activity=discord.Game("©Yuki Watanabe"),
                   intents=discord.Intents.all()
                   )

bot.load_extension("cogs.Admin")
bot.load_extension("cogs.CogManager")
bot.load_extension("cogs.SlackExporter")
bot.load_extension("cogs.Util")

bot.run(bot_config.TOKEN)
