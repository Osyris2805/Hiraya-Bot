import discord
from discord.ext import commands
import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional

# ========= CONFIG =========
CONFESSION_CHANNEL_ID = 1461951872364449984
LOG_CHANNEL_ID = 1461951962965868680

STATE_FILE = "confessions_state.json"

MAX_CONFESSION_LEN = 1000
MAX_REPLY_LEN = 800
COOLDOWN_SECONDS = 60
# ==========================


def utcnow():
    return datetime.now(timezone.utc)


def safe_text(text: str) -> str:
    # Prevent mass pings
    return (text or "").replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere").strip()


async def get_text_channel(guild: discord.Guild, channel_id: int) -> Optional[discord.TextChannel]:
    ch = guild.get_channel(channel_id)
    if isinstance(ch, discord.TextChannel):
        return ch
    try:
        fetched = await guild.fetch_channel(channel_id)
        return fetched if isinstance(fetched, discord.TextChannel) else None
    except Exception:
        return None


class ConfessionState:
    """Small JSON state manager (count + panel message id per guild)."""
    def __init__(self, path: str):
        self.path = path
        self.lock = asyncio.Lock()
        self.data = {
            "count": 0,
            "panels": {}  # guild_id(str) -> {"channel_id": int, "message_id": int}
        }

    async def load(self):
        async with self.lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        self.data = json.load(f)
                except Exception:
                    # If file is corrupted, keep defaults
                    self.data = {"count": 0, "panels": {}}
            else:
                await self.save()

    async def save(self):
        async with self.lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)

    async def next_number(self) -> int:
        async with self.lock:
            self.data["count"] = int(self.data.get("count", 0)) + 1
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            return self.data["count"]

    async def set_panel(self, guild_id: int, channel_id: int, message_id: int):
        async with self.lock:
            panels = self.data.setdefault("panels", {})
            panels[str(guild_id)] = {"channel_id": channel_id, "message_id": message_id}
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)

    async def get_panel(self, guild_id: int):
        async with self.lock:
            panels = self.data.get("panels", {})
            return panels.get(str(guild_id))


# ───────────────────── MODALS ─────────────────────

class ConfessionModal(discord.ui.Modal, title="Submit a confession"):
    confession = discord.ui.TextInput(
        label="Your confession",
        style=discord.TextStyle.paragraph,
        placeholder="Type what you want to say...",
        max_length=MAX_CONFESSION_LEN,
        required=True
    )

    def __init__(self, cog: "ConfessionsCog"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        retry = self.cog.cooldown.update_rate_limit(interaction.user.id)
        if retry:
            return await interaction.response.send_message(
                f"⏳ Please wait {int(retry)}s before confessing again.",
                ephemeral=True
            )

        conf_ch = await get_text_channel(interaction.guild, CONFESSION_CHANNEL_ID)
        log_ch = await get_text_channel(interaction.guild, LOG_CHANNEL_ID)

        if not conf_ch or not log_ch:
            return await interaction.response.send_message(
                "❌ Confession/log channels not found or bot lacks access.",
                ephemeral=True
            )

        content = safe_text(self.confession.value)
        if not content:
            return await interaction.response.send_message("❌ Confession cannot be empty.", ephemeral=True)

        number = await self.cog.state.next_number()

        # Looks like the screenshot: Anonymous Confession (#143) + “text”
        embed = discord.Embed(
            title=f"Anonymous Confession (#{number})",
            description=f"“{content}”",
            color=discord.Color.blurple(),
            timestamp=utcnow()
        )

        msg = await conf_ch.send(
            embed=embed,
            view=ConfessionPostView(self.cog),
            allowed_mentions=discord.AllowedMentions.none()
        )

        # Log identity
        log = discord.Embed(
            title=f"🔒 Confession #{number} — Log",
            color=discord.Color.red(),
            timestamp=utcnow()
        )
        log.set_thumbnail(url=interaction.user.display_avatar.url)
        log.add_field(name="User", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
        log.add_field(name="Account Created", value=interaction.user.created_at.strftime("%Y-%m-%d"), inline=True)
        log.add_field(name="Confession", value=content[:1024], inline=False)
        log.add_field(name="Message Link", value=f"[Jump to confession]({msg.jump_url})", inline=False)

        await log_ch.send(embed=log, allowed_mentions=discord.AllowedMentions.none())

        await interaction.response.send_message(f"✅ Confession #{number} submitted.", ephemeral=True)


class ReplyModal(discord.ui.Modal, title="Reply to confession"):
    reply = discord.ui.TextInput(
        label="Your reply",
        style=discord.TextStyle.paragraph,
        placeholder="Type your reply...",
        max_length=MAX_REPLY_LEN,
        required=True
    )

    def __init__(self, confession_message: discord.Message):
        super().__init__()
        self.confession_message = confession_message

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        log_ch = await get_text_channel(interaction.guild, LOG_CHANNEL_ID)
        if not log_ch:
            return await interaction.response.send_message("❌ Log channel missing.", ephemeral=True)

        text = safe_text(self.reply.value)
        if not text:
            return await interaction.response.send_message("❌ Reply cannot be empty.", ephemeral=True)

        embed = discord.Embed(
            title="💬 Reply",
            description=text,
            color=discord.Color.green(),
            timestamp=utcnow()
        )

        reply_msg = await self.confession_message.reply(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none()
        )

        # Log reply identity
        log = discord.Embed(title="🧾 Reply Log", color=discord.Color.orange(), timestamp=utcnow())
        log.add_field(name="Replier", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
        log.add_field(name="Reply", value=text[:1024], inline=False)
        log.add_field(name="Reply Link", value=f"[Jump to reply]({reply_msg.jump_url})", inline=False)
        log.add_field(name="Confession Link", value=f"[Jump to confession]({self.confession_message.jump_url})", inline=False)
        await log_ch.send(embed=log, allowed_mentions=discord.AllowedMentions.none())

        await interaction.response.send_message("✅ Reply posted.", ephemeral=True)


# ───────────────────── VIEWS ─────────────────────

class ConfessionPanelView(discord.ui.View):
    def __init__(self, cog: "ConfessionsCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Submit a confession!",
        style=discord.ButtonStyle.primary,
        custom_id="confessions:panel_submit"
    )
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfessionModal(self.cog))


class ConfessionPostView(discord.ui.View):
    def __init__(self, cog: "ConfessionsCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Submit a confession!",
        style=discord.ButtonStyle.primary,
        custom_id="confessions:post_submit"
    )
    async def submit_from_post(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfessionModal(self.cog))

    @discord.ui.button(
        label="Reply",
        style=discord.ButtonStyle.secondary,
        custom_id="confessions:post_reply"
    )
    async def reply(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.message:
            return await interaction.response.send_message("❌ Missing message context.", ephemeral=True)
        await interaction.response.send_modal(ReplyModal(interaction.message))


# ───────────────────── COG ─────────────────────

class ConfessionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.state = ConfessionState(STATE_FILE)
        self.cooldown = commands.CooldownMapping.from_cooldown(1, COOLDOWN_SECONDS, commands.BucketType.user)

        # Persistent views so buttons work after restart
        self.bot.add_view(ConfessionPanelView(self))
        self.bot.add_view(ConfessionPostView(self))

        self._ready_once = False  # prevents double panel creation on reconnect

    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready_once:
            return
        self._ready_once = True

        await self.state.load()

        # Ensure ONE panel exists per guild
        for guild in self.bot.guilds:
            conf_ch = await get_text_channel(guild, CONFESSION_CHANNEL_ID)
            if not conf_ch:
                continue

            panel_info = await self.state.get_panel(guild.id)
            if panel_info:
                # Verify it still exists
                try:
                    await conf_ch.fetch_message(int(panel_info["message_id"]))
                    continue
                except Exception:
                    pass

            await self.post_panel(conf_ch)

    async def post_panel(self, channel: discord.TextChannel):
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

        msg = await channel.send(embed=embed, view=ConfessionPanelView(self))
        await self.state.set_panel(channel.guild.id, channel.id, msg.id)

    @commands.command(name="confessionpanel")
    @commands.has_permissions(manage_guild=True)
    async def confessionpanel(self, ctx: commands.Context):
        """Manually (re)post the confession panel."""
        if not ctx.guild:
            return
        conf_ch = await get_text_channel(ctx.guild, CONFESSION_CHANNEL_ID)
        if not conf_ch:
            return await ctx.reply("❌ Confession channel not found.", mention_author=False)

        await self.post_panel(conf_ch)
        await ctx.reply("✅ Confession panel posted.", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfessionsCog(bot))
