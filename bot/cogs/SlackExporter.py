import io
import json
import os
import re
from datetime import datetime
from pprint import pprint

import discord
import httpx
import sentry_sdk
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
        self.users = self.get_users()

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

            res[dirname] = sorted(_data, key=lambda x: float(x.message_ts))
        return res

    @staticmethod
    def get_users():
        with open(f"/opt/target_files/users.json") as f:
            users_data = json.load(f)

        data = {}

        for user in users_data:
            user_id = user["id"]
            user_name = user["profile"]["display_name_normalized"]
            if user_name == "":
                user_name = user["profile"]["real_name_normalized"]
            data.update({user_id: user_name})

        return data

    async def autocomplete_channel_names(self, ctx: discord.commands.context.ApplicationContext):
        return [value for value in self.messages.keys() if value.startswith(ctx.value)]

    async def export_log(self, channel: discord.TextChannel, channel_name: str = None):
        await channel.send("\n".join([
            "===================",
            "????????????Slack?????????",
            "==================="
        ]))

        ts_msg_dict = {}

        messages = self.messages[channel.name if channel_name is None else channel_name]

        for message in messages:

            try:
                content = re.sub(r"<@([A-Z0-9]+)>", lambda m: f"<@{self.users[m.group(1)]}>", message.text)
                embed = discord.Embed(
                    description=content,
                    timestamp=datetime.fromtimestamp(float(message.message_ts), tz=datetime.now().astimezone().tzinfo),
                    color=discord.Color.blue()
                )
                embed.set_author(
                    name=message.user_name if message.user_name != "" else message.user_real_name,
                    icon_url=message.user_profile_image
                )

                attachments = []
                for attachment in message.attachments:
                    file = io.BytesIO(httpx.get(attachment.url).read())
                    attachments.append(discord.File(file, filename=attachment.name))

                reply_to: discord.Message | None = None
                if message.message_ts != message.thread_ts and message.thread_ts in ts_msg_dict:
                    reply_to = ts_msg_dict[message.thread_ts]

                if reply_to is None:
                    msg = await channel.send(embed=embed, files=attachments)
                else:
                    if reply_to.thread is None:
                        await reply_to.create_thread(name="?????????????????????")
                    msg = await reply_to.thread.send(embed=embed, files=attachments)

                ts_msg_dict[message.message_ts] = msg

            except Exception as e:
                sentry_sdk.capture_exception(e)
                continue

        await channel.send("\n".join([
            "===================",
            "????????????Slack?????????",
            "==================="
        ]))

        for thread in channel.threads:
            await thread.archive()

    @slash_command(name="execute", description="????????????????????????")
    @commands.is_owner()
    async def execute(self, ctx,
                      channel_name: Option(str, 'provide channel name', autocomplete=autocomplete_channel_names)):
        await ctx.respond("???????????????", ephemeral=True)
        await self.export_log(ctx.channel, channel_name)

    @slash_command(name="execute_bulk", description="??????????????????????????????????????????")
    @commands.is_owner()
    async def execute_bulk(self, ctx: discord.commands.context.ApplicationContext):
        await ctx.respond("???????????????", ephemeral=True)

        category = ctx.channel.category

        categories = [category]

        for channel_name in self.messages.keys():

            # ??????Ch???????????????
            is_exist = False
            for _c in categories:
                if channel_name in [channel.name for channel in _c.channels]:
                    is_exist = True
                    break

            if is_exist:
                continue

            # ????????????????????????????????????50????????????????????????????????????
            if len(category.channels) >= 50:

                # category?????????
                if f"{categories[0].name}_{len(categories) + 1}" in [category.name for category in
                                                                     ctx.guild.categories]:
                    # ????????????????????????????????????
                    category = [category for category in ctx.guild.categories if
                                category.name == f"{categories[0].name}_{len(categories) + 1}"][0]
                else:
                    # ???????????????????????????
                    category = await ctx.guild.create_category(
                        name=f"{categories[0].name}_{len(categories) + 1}",
                        overwrites=category.overwrites,
                        position=category.position + 1
                    )

                # ???????????????
                categories.append(category)

            channel = await ctx.guild.create_text_channel(
                name=channel_name,
                category=category
            )
            await self.export_log(channel)

    @slash_command(name="purge", description="????????????????????????????????????")
    @commands.is_owner()
    async def purge(self, ctx: discord.commands.context.ApplicationContext):
        await ctx.respond("???????????????", ephemeral=True)
        await ctx.channel.purge(limit=None)
        await ctx.respond("??????????????????", ephemeral=True)


def setup(bot):
    return bot.add_cog(SlackExporter(bot))
