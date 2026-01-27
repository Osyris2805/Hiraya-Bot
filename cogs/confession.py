import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime, timezone
from typing import Optional

# ====== CONFIG ======
CONFESSION_CHANNEL_ID = 1461951872364449984
LOG_CHANNEL_ID = 1461951962965868680
DB_FILE = "confessions.db"

COOLDOWN_SECONDS = 120
MAX_CONFESSION_LEN = 1000
MAX_REPLY_LEN = 800
# ====================


def utcnow():
    return datetime.now(timezone.utc)


def safe_text(text: str) -> str:
    # block mass pings
    text = text.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")
    return text.strip()


async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS confessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS panel (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL
        )
        """)
        await db.commit()


async def get_text_channel(guild: discord.Guild, channel_id: int) -> Optional[discord.TextChannel]:
    ch = guild.get_channel(channel_id)
    if isinstance(ch, discord.TextChannel):
        return ch
    try:
        fetched = await guild.fetch_channel(channel_id)
        return fetched if isinstance(fetched, discord.TextChannel) else None
    except Exception:
        return None


class ConfessionModal(discord.ui.Modal, title="Submit a confession"):
    confession = discord.ui.TextInput(
        label="Your confession",
        style=discord.TextStyle.paragraph,
        placeholder="Type what you want to say...",
        max_length=MAX_CONFESSION_LEN
    )

    def __init__(self, cog: "ConfessionsCog"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        retry_after = self.cog.cooldown.update_rate_limit(interaction.user.id)
        if retry_after:
            return await interaction.response.send_message(
                f"⏳ Try again in {int(retry_after)}s.",
                ephemeral=True
            )

        conf_ch = await get_text_channel(interaction.guild, CONFESSION_CHANNEL_ID)
        log_ch = await get_text_channel(interaction.guild, LOG_CHANNEL_ID)
        if not conf_ch or not log_ch:
            return await interaction.response.send_message("❌ Channels not configured.", ephemeral=True)

        content = safe_text(self.confession.value)
        if not content:
            return await interaction.response.send_message("❌ Confession cannot be empty.", ephemeral=True)

        # Insert first to get the confession number (id)
        async with aiosqlite.connect(DB_FILE) as db:
            cur = await db.execute(
                "INSERT INTO confessions (guild_id, channel_id, message_id, author_id, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (interaction.guild.id, conf_ch.id, 0, interaction.user.id, content, utcnow().isoformat())
            )
            confession_id = cur.lastrowid
            await db.commit()

        # LOOK like the screenshot
        embed = discord.Embed(
            title=f"Anonymous Confession (#{confession_id})",
            description=f"“{content}”",
            color=discord.Color.blurple(),
            timestamp=utcnow()
        )

        msg = await conf_ch.send(
            embed=embed,
            view=ConfessionPostView(self.cog),
            allowed_mentions=discord.AllowedMentions.none()
        )

        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE confessions SET message_id=? WHERE id=?", (msg.id, confession_id))
            await db.commit()

        # Log with identity
        log = discord.Embed(
            title=f"🔒 Confession #{confession_id} — Log",
            color=discord.Color.red(),
            timestamp=utcnow()
        )
        log.set_thumbnail(url=interaction.user.display_avatar.url)
        log.add_field(name="User", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
        log.add_field(name="Account Created", value=interaction.user.created_at.strftime("%Y-%m-%d"), inline=True)
        log.add_field(name="Confession", value=content[:1024], inline=False)
        log.add_field(name="Message Link", value=f"[Jump]({msg.jump_url})", inline=False)
        await log_ch.send(embed=log, allowed_mentions=discord.AllowedMentions.none())

        await interaction.response.send_message(f"✅ Confession #{confession_id} submitted.", ephemeral=True)


class ReplyModal(discord.ui.Modal, title="Reply to confession"):
    reply = discord.ui.TextInput(
        label="Your reply",
        style=discord.TextStyle.paragraph,
        placeholder="Type your reply...",
        max_length=MAX_REPLY_LEN
    )

    def __init__(self, confession_message: discord.Message):
        super().__init__()
        self.confession_message = confession_message

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

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

        log = discord.Embed(title="🧾 Reply Log", color=discord.Color.orange(), timestamp=utcnow())
        log.add_field(name="Replier", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
        log.add_field(name="Reply", value=text[:1024], inline=False)
        log.add_field(name="Reply Link", value=f"[Jump]({reply_msg.jump_url})", inline=False)
        log.add_field(name="Confession Link", value=f"[Jump]({self.confession_message.jump_url})", inline=False)
        await log_ch.send(embed=log, allowed_mentions=discord.AllowedMentions.none())

        await interaction.response.send_message("✅ Reply posted.", ephemeral=True)


class ConfessionPanelView(discord.ui.View):
    def __init__(self, cog: "ConfessionsCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Submit a confession!", style=discord.ButtonStyle.primary, custom_id="conf:submit")
    async def submit(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(ConfessionModal(self.cog))


class ConfessionPostView(discord.ui.View):
    def __init__(self, cog: "ConfessionsCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Submit a confession!", style=discord.ButtonStyle.primary, custom_id="conf:submit_post")
    async def submit_post(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(ConfessionModal(self.cog))

    @discord.ui.button(label="Reply", style=discord.ButtonStyle.secondary, custom_id="conf:reply")
    async def reply(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(ReplyModal(interaction.message))


class ConfessionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cooldown = commands.CooldownMapping.from_cooldown(1, COOLDOWN_SECONDS, commands.BucketType.user)

        # persistent views (buttons keep working after restart)
        bot.add_view(ConfessionPanelView(self))
        bot.add_view(ConfessionPostView(self))

    @commands.Cog.listener()
    async def on_ready(self):
        if getattr(self.bot, "_conf_db_ready", False) is False:
            await init_db()
            self.bot._conf_db_ready = True

        # Ensure panel exists ONCE (no spam on reconnect)
        for guild in self.bot.guilds:
            conf_ch = await get_text_channel(guild, CONFESSION_CHANNEL_ID)
            if not conf_ch:
                continue

            async with aiosqlite.connect(DB_FILE) as db:
                row = await db.execute_fetchone("SELECT message_id FROM panel WHERE guild_id=?", (guild.id,))

            if row:
                try:
                    await conf_ch.fetch_message(row[0])
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

        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "INSERT OR REPLACE INTO panel (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
                (channel.guild.id, channel.id, msg.id)
            )
            await db.commit()

    @commands.command(name="confessionpanel")
    @commands.has_permissions(administrator=True)
    async def confessionpanel(self, ctx: commands.Context):
        ch = await get_text_channel(ctx.guild, CONFESSION_CHANNEL_ID)
        if not ch:
            return await ctx.reply("❌ Confession channel not found.", mention_author=False)
        await self.post_panel(ch)
        await ctx.reply("✅ Panel posted.", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfessionsCog(bot))
