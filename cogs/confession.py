import discord
from discord.ext import commands
import json
import os
from datetime import datetime

CONFESSION_CHANNEL_ID = 1461951872364449984
LOG_CHANNEL_ID = 1461951962965868680

COUNT_FILE = "confession_count.json"


def get_confession_number():
    if not os.path.exists(COUNT_FILE):
        with open(COUNT_FILE, "w") as f:
            json.dump({"count": 0}, f)

    with open(COUNT_FILE, "r") as f:
        data = json.load(f)

    data["count"] += 1

    with open(COUNT_FILE, "w") as f:
        json.dump(data, f)

    return data["count"]


async def send_confession_box(channel):
    embed = discord.Embed(
        title="📮 Confession Box",
        description=(
            "Share your thoughts freely.\n\n"
            "• Your identity is hidden\n"
            "• Staff can see logs for safety\n"
            "• Be respectful"
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Click the button below to submit")

    await channel.send(embed=embed, view=ConfessionBoxView())


# ───────────────────── MODALS ─────────────────────

class ConfessionModal(discord.ui.Modal, title="Submit a Confession"):
    confession = discord.ui.TextInput(
        label="Your confession",
        style=discord.TextStyle.paragraph,
        placeholder="Type what you want to say...",
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        confession_channel = interaction.guild.get_channel(CONFESSION_CHANNEL_ID)
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)

        if not confession_channel or not log_channel:
            await interaction.response.send_message(
                "❌ Confession system is not configured.",
                ephemeral=True
            )
            return

        number = get_confession_number()

        # Public confession
        confession_embed = discord.Embed(
            title=f"📢 Confession #{number}",
            description=self.confession.value,
            color=discord.Color.purple(),
            timestamp=datetime.utcnow()
        )
        confession_embed.set_footer(text="Use the reply button to respond")

        msg = await confession_channel.send(
            embed=confession_embed,
            view=ConfessionReplyView()
        )

        # Log with full profile
        log_embed = discord.Embed(
            title=f"🔒 Confession #{number} — Log",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        log_embed.set_thumbnail(url=interaction.user.display_avatar.url)
        log_embed.add_field(
            name="User",
            value=f"{interaction.user} (`{interaction.user.id}`)",
            inline=False
        )
        log_embed.add_field(
            name="Account Created",
            value=interaction.user.created_at.strftime("%Y-%m-%d"),
            inline=True
        )
        log_embed.add_field(
            name="Confession",
            value=self.confession.value,
            inline=False
        )
        log_embed.add_field(
            name="Message Link",
            value=f"[Jump to confession]({msg.jump_url})",
            inline=False
        )

        await log_channel.send(embed=log_embed)

        # Spawn next confession box
        await send_confession_box(confession_channel)

        await interaction.response.send_message(
            f"✅ Confession #{number} submitted successfully.",
            ephemeral=True
        )


class ReplyModal(discord.ui.Modal, title="Reply to Confession"):
    reply = discord.ui.TextInput(
        label="Your reply",
        style=discord.TextStyle.paragraph,
        placeholder="Type your reply...",
        max_length=800
    )

    def __init__(self, confession_message):
        super().__init__()
        self.confession_message = confession_message

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💬 Reply",
            description=self.reply.value,
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Reply sent")

        await self.confession_message.reply(embed=embed)
        await interaction.response.send_message("✅ Reply posted.", ephemeral=True)


# ───────────────────── VIEWS ─────────────────────

class ConfessionBoxView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💌 Confess", style=discord.ButtonStyle.primary)
    async def confess(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfessionModal())


class ConfessionReplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💬 Reply", style=discord.ButtonStyle.secondary)
    async def reply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ReplyModal(interaction.message)
        )


# ───────────────────── COG ─────────────────────

class Confession(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(CONFESSION_CHANNEL_ID)
        if channel:
            await send_confession_box(channel)


async def setup(bot):
    await bot.add_cog(Confession(bot))