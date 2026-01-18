import discord
from discord.ext import commands
import json
import os
import asyncio
import random

# Load user jobs
if os.path.exists("jobs.json"):
    with open("jobs.json", "r") as f:
        user_jobs = json.load(f)
else:
    user_jobs = {}

# Define jobs and mini-games
jobs = {
    "chef": {"min": 20, "max": 50, "minigame": "cut"},
    "coder": {"min": 30, "max": 70, "minigame": "debug"},
    "driver": {"min": 15, "max": 40, "minigame": "signal"},
}

def save_jobs():
    with open("jobs.json", "w") as f:
        json.dump(user_jobs, f, indent=4)

# Helper function to format cooldown
def format_cooldown(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h {m}m {s}s"

class Jobs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["job","choosejob"])
    async def hjob(self, ctx, job: str = None):
        """Choose a job or view available jobs"""
        if job is None:
            embed = discord.Embed(title="💼 Available Jobs", color=discord.Color.blurple())
            for name, info in jobs.items():
                emoji = {"chef":"🍴", "coder":"💻", "driver":"🚗"}.get(name, "⚡")
                embed.add_field(
                    name=f"{emoji} {name.capitalize()}",
                    value=f"Salary: {info['min']} - {info['max']} coins\nMini-Game: {info['minigame'].capitalize()}",
                    inline=False
                )
            await ctx.send(embed=embed)
            return

        job = job.lower()
        if job not in jobs:
            return await ctx.send("❌ That job does not exist!")
        user_jobs[str(ctx.author.id)] = job
        save_jobs()
        await ctx.send(f"✅ You are now working as a **{job.capitalize()}**!")

    @commands.command(aliases=["w"])
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def work(self, ctx):
        user_id = str(ctx.author.id)
        if user_id not in user_jobs:
            return await ctx.send("❌ You don't have a job yet! Choose one with `hjob`")

        job = user_jobs[user_id]
        job_info = jobs[job]

        start_embed = discord.Embed(
            title=f"Working as {job.capitalize()}...",
            description="Preparing your task...",
            color=discord.Color.blue()
        )
        await ctx.send(embed=start_embed)
        await asyncio.sleep(1)

        # Determine mini-game
        timeout = 5
        if job_info["minigame"] == "cut":
            instruction = "🔪 **Chef Mini-Game**\nType **slice** within 5 seconds!"
            correct_answer = "slice"
            timeout = 5
        elif job_info["minigame"] == "debug":
            bug = random.randint(1,3)
            instruction = f"💻 **Coder Mini-Game**\nFix **bug #{bug}** by typing `fix{bug}` within 6 seconds!"
            correct_answer = f"fix{bug}"
            timeout = 6
        elif job_info["minigame"] == "signal":
            signal = random.choice(["left","right"])
            instruction = f"🚗 **Driver Mini-Game**\nType **{signal}** within 4 seconds!"
            correct_answer = signal
            timeout = 4

        instruction_embed = discord.Embed(
            title="Mini-Game Instructions",
            description=instruction,
            color=discord.Color.orange()
        )
        instruction_msg = await ctx.send(embed=instruction_embed)
        await asyncio.sleep(2)

        # Countdown
        for i in range(3,0,-1):
            countdown_embed = discord.Embed(
                title="Get Ready!",
                description=f"{i}...",
                color=discord.Color.orange()
            )
            await instruction_msg.edit(embed=countdown_embed)
            await asyncio.sleep(1)

        go_embed = discord.Embed(
            title="GO!",
            description="Type your answer now!",
            color=discord.Color.green()
        )
        await instruction_msg.edit(embed=go_embed)

        # Wait for user input
        try:
            def check(m):
                return m.author == ctx.author and m.content.lower() == correct_answer
            await self.bot.wait_for("message", check=check, timeout=timeout)
        except:
            fail_embed = discord.Embed(
                title="❌ Mini-Game Failed",
                description="You didn't type the correct response in time. No coins earned.",
                color=discord.Color.red()
            )
            return await instruction_msg.edit(embed=fail_embed)

        # Success - award coins
        earned = random.randint(job_info["min"], job_info["max"])
        from cogs.economy import add_coins
        add_coins(ctx.author.id, earned)

        success_embed = discord.Embed(
            title="🎉 Task Complete!",
            description=f"You earned 💰 {earned} Hiraya Coins!",
            color=discord.Color.gold()
        )
        await instruction_msg.edit(embed=success_embed)

    # Local cooldown handler
    @work.error
    async def work_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ You need to wait {format_cooldown(error.retry_after)} before working again!")

async def setup(bot):
    await bot.add_cog(Jobs(bot))
