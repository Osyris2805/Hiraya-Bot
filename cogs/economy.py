import discord
from discord.ext import commands
import json
import os

if os.path.exists("currency.json"):
    with open("currency.json", "r") as f:
        currency = json.load(f)
else:
    currency = {}

def save_currency():
    with open("currency.json", "w") as f:
        json.dump(currency, f, indent=4)

def add_coins(user_id, amount):
    user_id = str(user_id)
    if user_id not in currency:
        currency[user_id] = 0
    currency[user_id] += amount
    save_currency()

def get_balance(user_id):
    return currency.get(str(user_id), 0)

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["bal","b"])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        bal = get_balance(member.id)
        await ctx.send(f"{member.display_name} has 💰 {bal} Hiraya Coins!")

    @commands.command(aliases=["addc","givecoins"])
    @commands.has_permissions(administrator=True)
    async def addcoins(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send("❌ Amount must be greater than 0")
        add_coins(member.id, amount)
        await ctx.send(f"✅ Added {amount} Hiraya Coins to {member.mention}")

    @commands.command(aliases=["resetc","resetcoins"])
    @commands.has_permissions(administrator=True)
    async def resetcurrency(self, ctx):
        global currency
        currency = {}
        save_currency()
        await ctx.send("✅ All Hiraya Coins reset.")

# ✅ This must be at module level, not inside any class
async def setup(bot):
    await bot.add_cog(Economy(bot))
