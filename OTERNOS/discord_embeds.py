from __future__ import annotations

import discord
from discord.ext import commands

try:
    from .discord_config import COMMAND_PREFIX
except ImportError:
    from oternos.discord_config import COMMAND_PREFIX


def _hood_embed(title: str, message: str, *, color: int = 0xEDEDED) -> discord.Embed:
    """Format bot text as a compact monochrome embed instead of a raw wall."""
    text = str(message or "").strip() or "No details."
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = str(title or "HOOD BOT").strip()[:256] or "HOOD BOT"
    if len(lines) <= 3 and len(text) <= 900:
        embed = discord.Embed(title=title, description=text, color=color)
        embed.set_footer(text="H-I-N TECH // HOOD BOT")
        return embed

    embed = discord.Embed(title=title, description=lines[0][:4096] if lines else "Response", color=color)
    chunk: list[str] = []
    chunk_len = 0
    field_index = 1
    for line in lines[1:] if lines else []:
        safe = line[:900]
        projected = chunk_len + len(safe) + 1
        if chunk and projected > 900:
            embed.add_field(name=f"DATA BLOCK {field_index:02d}", value="\n".join(chunk)[:1024], inline=False)
            field_index += 1
            chunk = []
            chunk_len = 0
            if field_index > 24:
                break
        chunk.append(safe)
        chunk_len += len(safe) + 1
    if chunk and field_index <= 24:
        embed.add_field(name=f"DATA BLOCK {field_index:02d}", value="\n".join(chunk)[:1024], inline=False)
    if len(lines) > 1 and field_index > 24:
        embed.add_field(name="TRUNCATED", value="Output was too long for one Discord embed.", inline=False)
    embed.set_footer(text="H-I-N TECH // HOOD BOT")
    return embed


def _commands_embed(prefix: str) -> discord.Embed:
    embed = discord.Embed(
        title="H-I-N TECH COMMANDS",
        description=(
            "A cleaner command hub for the Discord companion. "
            "Use the dropdown below to browse commands by category."
        ),
        color=0xEDEDED,
    )
    embed.add_field(
        name="Getting Started",
        value="\n".join(
            (
                f"1. Use `{prefix}join` to connect me to voice.",
                f"2. Use `{prefix}play <query or link>` to start a cast.",
                f"3. Use `{prefix}convert <link>` or upload a file with `{prefix}convert` to convert media.",
            )
        ),
        inline=False,
    )
    embed.add_field(
        name="Main Categories",
        value="\n".join(
            (
                "`Voice Basics` - connect, pause, leave, and adjust volume.",
                "`Play & Search` - play links, search SoundCloud, and inspect what is playing.",
                "`Queue & Cast` - move through cast queue and sync with the app.",
                "`Moderation` - clear messages and manage members with proper permissions.",
                "`Fun` - lightweight community commands, randomizers, and quick games.",
                "`Convert` - turn links or uploaded files into MP3 / M4A / FLAC / WAV.",
                "`Qt / Diagnostics` - app controls and troubleshooting tools.",
            )
        ),
        inline=False,
    )
    embed.add_field(
        name="Quick Examples",
        value="\n".join(
            (
                f"`{prefix}play space song`",
                f"`{prefix}play https://soundcloud.com/...`",
                f"`{prefix}convert https://youtube.com/...`",
                f"`{prefix}convert` + upload a file",
            )
        ),
        inline=False,
    )
    embed.set_footer(text="H-I-N TECH // HOOD BOT // select a category below")
    return embed


def _commands_category_embed(prefix: str, category: str) -> discord.Embed:
    key = str(category or "overview").strip().lower()
    if key == "voice":
        embed = discord.Embed(title="VOICE BASICS", description="Core commands for getting the bot into voice and controlling playback state.", color=0xEDEDED)
        embed.add_field(name="Connect", value=f"`{prefix}join`\nConnect the bot to the voice channel you are currently in.", inline=False)
        embed.add_field(name="Disconnect", value=f"`{prefix}leave`\nDisconnect from voice and stop the active cast.", inline=False)
        embed.add_field(name="Pause / Resume", value=f"`{prefix}pause` or `{prefix}toggle`\nPause the current Discord cast, or resume it if already paused.", inline=False)
        embed.add_field(name="Volume", value=f"`{prefix}volume <0-100>`\nSet the Discord voice output volume for the cast session.", inline=False)
    elif key == "play":
        embed = discord.Embed(title="PLAY & SEARCH", description="Play media from search text or direct links and inspect the active cast.", color=0xEDEDED)
        embed.add_field(name="Play Search Query", value=f"`{prefix}play <query>`\nSearch SoundCloud and queue the top result for playback.", inline=False)
        embed.add_field(name="Play Direct Link", value=f"`{prefix}play <link>`\nBest-effort playback for SoundCloud, YouTube, Instagram, TikTok, and other resolvable links.", inline=False)
        embed.add_field(name="SoundCloud Search", value=f"`{prefix}scsearch <query>`\nPreview SoundCloud matches before deciding what to play.", inline=False)
        embed.add_field(name="Now Playing / Queue", value=f"`{prefix}nowplaying`\n`{prefix}queue` or `{prefix}castqueue`\nSee the active cast track and queue state.", inline=False)
    elif key == "queue":
        embed = discord.Embed(title="QUEUE & CAST CONTROL", description="Commands for moving around the Discord cast queue and syncing with the desktop app.", color=0xEDEDED)
        embed.add_field(name="Queue Navigation", value=f"`{prefix}next` / `{prefix}prev`\nMove forward or backward through the Discord cast queue.", inline=False)
        embed.add_field(name="Jump To Position", value=f"`{prefix}castnow <number>`\nInstantly switch the cast to a specific queue slot.", inline=False)
        embed.add_field(name="Clear Queue", value=f"`{prefix}clearcast`\nRemove all pending Discord cast items and reset cast state.", inline=False)
        embed.add_field(name="App Cast", value=f"`{prefix}vcast`\nCast the currently playing H-I-N TECH app track and pause local Qt playback.\n`{prefix}vplay` plays the current local runtime track in voice.\n`{prefix}vunmute` resumes local playback after casting.", inline=False)
    elif key == "moderation":
        embed = discord.Embed(title="MODERATION", description="Core moderation tools for staff with the right Discord permissions.", color=0xEDEDED)
        embed.add_field(name="Message Cleanup", value=f"`{prefix}purge <count>`\nDelete a batch of recent messages from the current channel.", inline=False)
        embed.add_field(name="Member Actions", value=f"`{prefix}kick @user [reason]`\n`{prefix}ban @user [reason]`\n`{prefix}unban <user_id> [reason]`\nRemove or restore users with audit-log reasons.", inline=False)
        embed.add_field(name="Timeouts", value=f"`{prefix}timeout @user <minutes> [reason]`\n`{prefix}untimeout @user [reason]`\nTemporarily silence a member or clear an active timeout.", inline=False)
        embed.add_field(name="Safety", value="These commands require the matching Discord permissions and respect role hierarchy where Discord enforces it.", inline=False)
    elif key == "fun":
        embed = discord.Embed(title="FUN", description="Lightweight community commands for energy, randomness, and small interactions.", color=0xEDEDED)
        embed.add_field(name="Quick Randomizers", value=f"`{prefix}8ball <question>`\n`{prefix}coinflip`\n`{prefix}roll [sides]`\nFast luck / chance commands for chat.", inline=False)
        embed.add_field(name="Social Commands", value=f"`{prefix}choose <a | b | c>`\n`{prefix}rate <thing>`\n`{prefix}ship <name1> <name2>`\nPick favorites, score something, or make a goofy match percentage.", inline=False)
        embed.add_field(name="Vibe Commands", value=f"`{prefix}mood`\n`{prefix}roast [@user]`\n`{prefix}compliment [@user]`\nShort reaction-style commands for the server.", inline=False)
    elif key == "convert":
        embed = discord.Embed(title="CONVERT", description="Convert supported links or uploaded files into downloadable audio formats.", color=0xEDEDED)
        embed.add_field(name="Convert a Link", value=f"`{prefix}convert <link>`\nStart a conversion from a supported direct link, then choose MP3, M4A, FLAC, or WAV.", inline=False)
        embed.add_field(name="Convert an Uploaded File", value=f"Upload a file, then run `{prefix}convert`\nThe bot will lock onto the attachment and prompt you for an output format.", inline=False)
        embed.add_field(name="How Output Selection Works", value="After the command starts, press one of the format buttons. The bot converts the source and uploads the result when the file size is small enough for Discord.", inline=False)
    elif key == "qt":
        embed = discord.Embed(title="QT / DIAGNOSTICS", description="Private app-side controls and troubleshooting utilities for the desktop player bridge.", color=0xEDEDED)
        embed.add_field(name="Qt Controls", value=f"`{prefix}qtplaypause` / `{prefix}qtnext` / `{prefix}qtprev`\nControl the connected desktop player remotely.", inline=False)
        embed.add_field(name="Qt Queue / Track Info", value=f"`{prefix}qtqueue` / `{prefix}qtnowplaying`\nInspect the live app queue and the current desktop track.", inline=False)
        embed.add_field(name="Diagnostics", value=f"`{prefix}vcdiag` / `{prefix}rtdiag` / `{prefix}castdiag`\nCheck Discord voice state, runtime bridge state, and cast status when something is acting up.", inline=False)
    else:
        embed = _commands_embed(prefix)
    embed.set_footer(text="H-I-N TECH // HOOD BOT")
    return embed


async def _reply_embed(ctx: commands.Context, title: str, message: str, *, color: int = 0xEDEDED) -> None:
    await ctx.reply(embed=_hood_embed(title, message, color=color), mention_author=False)


async def _message_reply_embed(message: discord.Message, title: str, body: str, *, color: int = 0xEDEDED) -> None:
    await message.reply(embed=_hood_embed(title, body, color=color), mention_author=False)


async def _message_reply_commands(message: discord.Message) -> None:
    await message.reply(embed=_commands_embed(COMMAND_PREFIX), view=HelpCategoryView(), mention_author=False)


async def _interaction_embed(interaction: discord.Interaction, title: str, message: str, *, ephemeral: bool = True) -> None:
    embed = _hood_embed(title, message)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)


class HelpCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Overview", value="overview", description="Start here for the main command hub."),
            discord.SelectOption(label="Voice Basics", value="voice", description="Join, leave, pause, and volume controls."),
            discord.SelectOption(label="Play & Search", value="play", description="Play links, search, and now playing."),
            discord.SelectOption(label="Queue & Cast", value="queue", description="Queue navigation and app casting tools."),
            discord.SelectOption(label="Moderation", value="moderation", description="Staff tools for cleanup and member actions."),
            discord.SelectOption(label="Fun", value="fun", description="Community commands, randomizers, and goofy utilities."),
            discord.SelectOption(label="Convert", value="convert", description="Convert links or uploaded files into audio."),
            discord.SelectOption(label="Qt / Diagnostics", value="qt", description="Desktop app controls and troubleshooting."),
        ]
        super().__init__(placeholder="Select a help category", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = str(self.values[0] if self.values else "overview")
        await interaction.response.edit_message(
            embed=_commands_category_embed(COMMAND_PREFIX, category),
            view=HelpCategoryView(selected=category),
        )


class HelpCategoryView(discord.ui.View):
    def __init__(self, *, selected: str = "overview"):
        super().__init__(timeout=300)
        self.add_item(HelpCategorySelect())
