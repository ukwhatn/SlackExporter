import io
import json
import os
from datetime import datetime
from pprint import pprint

import discord
import httpx
from discord import Option
from discord.commands import slash_command
from discord.ext import commands


class SlackAttachments:
    def __init__(
            self,
            name: str,
            url: str
    ):
        self.name = name
        self.url = url


class SlackMessage:
    def __init__(
            self,
            message_ts: str,
            thread_ts: str,
            user_name: str,
            user_real_name: str,
            user_profile_image: str,
            text: str,
            attachments: list[SlackAttachments]
    ):
        self.message_ts = message_ts
        self.thread_ts = thread_ts
        self.user_name = user_name
        self.user_real_name = user_real_name
        self.user_profile_image = user_profile_image
        self.text = text
        self.attachments = attachments


class SlackExporter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.messages = self.get_all_messages()

    @staticmethod
    def get_all_messages() -> dict[str, list[SlackMessage]]:
        res = {}

        # get users
        users = {}

        with open(f"/opt/target_files/users.json") as f:
            users_data = json.load(f)

        for user in users_data:
            users[user["id"]] = user

        # get channels
        dirs = os.listdir("/opt/target_files")
        dirs = [f for f in dirs if os.path.isdir(os.path.join("/opt/target_files", f))]

        # get messages per channels
        for dirname in dirs:
            _data = []
            jsons = os.listdir(f"/opt/target_files/{dirname}")
            for json_path in jsons:
                with open(f"/opt/target_files/{dirname}/{json_path}") as f:
                    d = json.load(f)
                for _d in d:
                    try:
                        if "subtype" in _d or "user" not in _d:
                            continue

                        attachments = []
                        if "files" in _d:
                            for file in _d["files"]:
                                if file["mode"] in ("tombstone", "hidden_by_limit"):
                                    continue

                                if "url_private_download" not in file:
                                    continue

                                attachments.append(SlackAttachments(
                                    name=file["name"],
                                    url=file["url_private_download"]
                                ))

                        user_name = user_real_name = user_profile_image = None
                        if _d["user"] in users:
                            user_name = users[_d["user"]]["profile"]["display_name_normalized"]
                            user_real_name = users[_d["user"]]["profile"]["real_name_normalized"]
                            user_profile_image = users[_d["user"]]["profile"]["image_72"]

                        elif _d["user"] == "USLACKBOT":
                            user_name = "Slackbot"
                            user_real_name = "Slackbot"
                            user_profile_image = "https://a.slack-edge.com/80588/marketing/img/meta/slack_hash_128.png"

                        else:
                            user_name = _d["user_profile"]["display_name"]
                            user_real_name = _d["user_profile"]["real_name"]
                            user_profile_image = _d["user_profile"]["image_72"]

                        _data.append(SlackMessage(
                            message_ts=_d["ts"],
                            thread_ts=_d["thread_ts"] if "thread_ts" in _d else None,
                            user_name=user_name,
                            user_real_name=user_real_name,
                            user_profile_image=user_profile_image,
                            text=_d["text"],
                            attachments=attachments
                        ))
                    except Exception:
                        pprint(_d)
                        raise

            res[dirname] = _data
        return res

    async def autocomplete_channel_names(self, ctx: discord.commands.context.ApplicationContext):
        return [value for value in self.messages.keys() if value.startswith(ctx.value)]

    @slash_command(name="execute", description="移行を開始します")
    @commands.is_owner()
    async def execute(self, ctx,
                      channel_name: Option(str, 'provide channel name', autocomplete=autocomplete_channel_names)):
        await ctx.respond("開始します", ephemeral=True)

        await ctx.send("\n".join([
            "===================",
            "ここからSlackのログ",
            "==================="
        ]))

        ts_msg_dict = {}

        messages = self.messages[channel_name]
        for message in messages:

            embed = discord.Embed(
                title=message.user_real_name,
                description=message.text,
                timestamp=datetime.fromtimestamp(float(message.message_ts), tz=datetime.now().astimezone().tzinfo),
                color=discord.Color.blue()
            )
            embed.set_author(name=message.user_name, icon_url=message.user_profile_image)

            attachments = []
            for attachment in message.attachments:
                file = io.BytesIO(httpx.get(attachment.url).read())
                attachments.append(discord.File(file, filename=attachment.name))

            reply_to: discord.Message | None = None
            if message.message_ts != message.thread_ts and message.thread_ts in ts_msg_dict:
                reply_to = ts_msg_dict[message.thread_ts]

            if reply_to is None:
                msg = await ctx.send(embed=embed)
            else:
                msg = await reply_to.reply(embed=embed)

            if len(attachments) > 0:
                await ctx.send(files=attachments)

            ts_msg_dict[message.message_ts] = msg

        await ctx.send("\n".join([
            "===================",
            "ここまでSlackのログ",
            "==================="
        ]))

    @slash_command(name="purge", description="全メッセージを削除します")
    @commands.is_owner()
    async def purge(self, ctx: discord.commands.context.ApplicationContext):
        await ctx.respond("開始します", ephemeral=True)
        await ctx.channel.purge(limit=None)
        await ctx.respond("完了しました", ephemeral=True)


def setup(bot):
    return bot.add_cog(SlackExporter(bot))
