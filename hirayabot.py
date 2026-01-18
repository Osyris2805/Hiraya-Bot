import discord
from discord.ext import commands
import os

TOKEN = "MTQzODM3ODE5ODk3MzgwODY4MA.GXKNl-.9t2xC-lKhQQ1QGtqTcgHH-xIOgfLg3TsurkG08"  

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
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    print(f"✅ Loaded cog: {filename}")
                except Exception as e:
                    print(f"❌ Failed to load {filename}: {e}")

bot = HirayaBot()

@bot.event
async def on_ready():
    print(f"✅ Bot ready as {bot.user}")

@bot.event
async def on_command_error(ctx, error):
    from discord.ext.commands import CommandOnCooldown

    if isinstance(error, CommandOnCooldown):
        seconds = int(error.retry_after)
        await ctx.send(f"⏳ Cooldown active. Try again in {seconds}s")
    else:
        await ctx.send(f"❌ Error: {error}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason)
    await ctx.send(f"✅ **{member}** has been banned.\nReason: {reason}")


@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"✅ **{member}** has been kicked.\nReason: {reason}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def unbanall(ctx):
    count = 0

    async for ban_entry in ctx.guild.bans():
        await ctx.guild.unban(ban_entry.user)
        count += 1

    if count == 0:
        await ctx.send("⚠️ There are no banned users.")
    else:
        await ctx.send(f"✅ Unbanned **{count} users**.")


@bot.command()
@commands.has_permissions(administrator=True)
async def inviteall(ctx):
    invite = await ctx.channel.create_invite(
        max_uses=0,
        max_age=0,
        unique=False
    )
    await ctx.send(
        "⚠️ Discord does not support un-kicking users.\n"
        "Use this invite link so kicked users can rejoin:\n"
        f"{invite}"
    )


bot.run(TOKEN)
