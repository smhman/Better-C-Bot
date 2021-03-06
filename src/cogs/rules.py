import io
import json
import re
import time

from discord.ext import commands
import discord


class RulesEnforcer(commands.Cog, name="Rules"):
    with open("src/backend/database.json", 'r') as f:
        file = json.load(f)

    def __init__(self, bot):
        self.bot = bot

        # Maps channel : discord.Message
        self._deleted = {}

        self._recent_joins = []

        self.massjoin_detect = True

        self.next_massjoin_notif = time.time()

        with open("src/backend/database.json", 'r') as f: # Seems to be unavoidable
            self.file = json.load(f)
        bot.loop.create_task(self._update_rules())

    @commands.command()
    async def rule(self, ctx, number):
        """Display a rule"""
        if self._rules.get(number) is None:
            return await ctx.send(f"Invalid rule number: `{discord.utils.escape_mentions(number)}`")
        else:
            await ctx.send(f"**Rule {number}**:\n{self._rules[number]}")

    @commands.command()
    async def snipe(self, ctx):
        if ctx.channel not in self._deleted:
            return await ctx.send("No message to snipe.")

        message: discord.Message = self._deleted[ctx.channel]
        user = str(message.author)
        ts = message.created_at.isoformat(" ")
        content = message.content
        return await ctx.send(f"**{discord.utils.escape_markdown(discord.utils.escape_mentions(user))}** said on {ts} UTC:\n{content}")

    async def _notify_staff(self, guild, message):
        role = self.file["staff_role"]
        channel = guild.system_channel
        if channel:
            await channel.send(f"<@&{role}> {message}.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not self.massjoin_detect:
            return

        current_time = time.time()

        self._recent_joins = [
            x for x in self._recent_joins
            if current_time - x["join_time"] <= self.file["massjoin_window"]
        ]

        self._recent_joins.append({"join_time": current_time, "id": member.id})

        join_amount = len(self._recent_joins)

        if join_amount >= self.file["massjoin_amount"] and self.next_massjoin_notif <= current_time:
            first_joined_id = self._recent_joins[0]["id"]
            await self._notify_staff(member.guild, "Mass member join detected. " + f"First join ID: `{first_joined_id}`")
            self.next_massjoin_notif = current_time + self.file["massjoin_notif_timeout"]

    @commands.command()
    @commands.has_role(file["staff_role"])
    async def toggle_massjoin_detection(self, ctx):
        self.massjoin_detect = not self.massjoin_detect
        if self.massjoin_detect:
            await ctx.send("Massjoin detection is now on")
        else:
            await ctx.send("Massjoin detection is now off")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        self._deleted[message.channel] = message

    async def _update_rules(self):
        channel = self.bot.get_channel(self.file["rules_channel"])
        messages = await channel.history(limit=1000000, oldest_first=True).flatten()
        self._rules = {}

        for message in messages:
            content = message.clean_content
            matches = re.finditer(r"(\d+) - (.+?)(?=[\n ]+\d+? - |$)", content, flags=re.DOTALL)

            for rule in matches:
                if rule[0] == "":
                    continue

                number = rule[1]
                text = rule[2]

                if self._rules.get(number) is None:
                    self._rules[number] = text

    @commands.command(hidden=True)
    @commands.has_role(file["staff_role"])
    async def update_rules(self, ctx):
        await self._update_rules()
        await ctx.send("The rules were updated successully")
def setup(bot):
    bot.add_cog(RulesEnforcer(bot))

