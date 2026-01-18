import discord
from discord.ext import commands
import random
import json
import os
from cogs.economy import add_coins, get_balance

# Helper function to format cooldown
def format_cooldown(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h {m}m {s}s"

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["cf", "gamble"])
    @commands.cooldown(1, 10, commands.BucketType.user)  # example 10s cooldown
    async def coinflip(self, ctx, choice: str, bet: int):
        user = ctx.author
        choice = choice.lower()
        if choice not in ["heads","tails"]:
            return await ctx.send("❌ Choose heads or tails")
        if bet <=0 or get_balance(user.id)<bet:
            return await ctx.send("❌ Invalid bet or insufficient coins")

        result = random.choice(["heads","tails"])
        if choice==result:
            add_coins(user.id, bet)
            await ctx.send(f"🪙 Coin landed {result}! You won 💰{bet}!")
        else:
            add_coins(user.id, -bet)
            await ctx.send(f"🪙 Coin landed {result}! You lost 💰{bet}!")

    @coinflip.error
    async def coinflip_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Cooldown: {format_cooldown(error.retry_after)}")

    @commands.command(aliases=["bfight","bf"])
    @commands.cooldown(1,300,commands.BucketType.user)
    async def betfight(self, ctx, opponent: discord.Member, amount: int):
        challenger = ctx.author
        if opponent==challenger or amount<=0:
            return await ctx.send("❌ Invalid fight")
        if get_balance(challenger.id)<amount or get_balance(opponent.id)<amount:
            return await ctx.send("❌ Not enough coins")

        await ctx.send(f"{opponent.mention}, {challenger.display_name} challenges you! Type yes to accept 30s")
        def check(m): return m.author==opponent and m.content.lower()=="yes" and m.channel==ctx.channel
        try: await self.bot.wait_for("message", check=check, timeout=30)
        except: return await ctx.send("⌛ Time's up! Fight canceled")

        winner = random.choice([challenger, opponent])
        loser = opponent if winner==challenger else challenger
        add_coins(winner.id, amount)
        add_coins(loser.id, -amount)
        await ctx.send(f"🏆 {winner.display_name} won 💰{amount} from {loser.display_name}")

    @betfight.error
    async def betfight_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Cooldown: {format_cooldown(error.retry_after)}")

    @commands.command(aliases=["lb","top"])
    async def leaderboard(self, ctx):
        if not os.path.exists("currency.json"):
            return await ctx.send("No coins yet")
        with open("currency.json","r") as f:
            currency = json.load(f)
        top = sorted(currency.items(), key=lambda x:x[1], reverse=True)[:10]
        embed=discord.Embed(title="🏆 Top 10 Richest Users", color=discord.Color.gold())
        for i,(uid,balance) in enumerate(top,1):
            try: user = await self.bot.fetch_user(int(uid))
            except: user=None
            embed.add_field(name=f"#{i} {user.display_name if user else 'Unknown'}", value=f"💰 {balance}", inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Games(bot))
