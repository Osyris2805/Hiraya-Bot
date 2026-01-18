import discord
from discord.ext import commands
import os
import asyncio

intents = discord.Intents.default()
intents.message_content = True

def get_prefix(bot, message):
    prefixes = ["!", "+"]
    return commands.when_mentioned_or(*prefixes)(bot, message)

class HirayaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, intents=intents)

    async def setup_hook(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded cog: {filename}")

bot = HirayaBot()

@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")

TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN not found")

async def main():
    async with bot:
        await bot.start(TOKEN)

asyncio.run(main())
