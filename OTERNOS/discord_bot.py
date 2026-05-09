from __future__ import annotations

import asyncio
import datetime
import json
import mimetypes
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.parse

try:
    import discord
    from discord.ext import commands
except ImportError as exc:
    raise SystemExit(
        "discord.py is not installed. Install it with: pip install discord.py"
    ) from exc

try:
    from .discord_config import (
        COMMAND_PREFIX,
        DISCORD_DISABLE_LOCAL_LOCK_ENV,
        DISCORD_PANEL_STATE_FILE_NAME,
        DISCORD_SHARE_QT_NOW_PLAYING_ENV,
        DISCORD_STATUS_FILE_ENV,
        DISCORD_STATUS_FILE_NAME,
        DISCORD_TOKEN_ENV,
        DISCORD_TOKEN_FILE_NAME,
        cloud_mode,
        env_truthy,
        single_instance_lock,
        token_for_mode,
    )
    from .discord_embeds import (
        HelpCategoryView,
        _commands_embed,
        _hood_embed,
        _interaction_embed,
        _message_reply_commands,
        _reply_embed,
    )
    from .discord_bridge import DiscordRuntimeBridge
    from .core.runtime_commands import load_runtime_command, runtime_command_file_marker
    from .soundcloud_client import SoundCloudAPI
except ImportError:
    from oternos.discord_config import (
        COMMAND_PREFIX,
        DISCORD_DISABLE_LOCAL_LOCK_ENV,
        DISCORD_PANEL_STATE_FILE_NAME,
        DISCORD_SHARE_QT_NOW_PLAYING_ENV,
        DISCORD_STATUS_FILE_ENV,
        DISCORD_STATUS_FILE_NAME,
        DISCORD_TOKEN_ENV,
        DISCORD_TOKEN_FILE_NAME,
        cloud_mode,
        env_truthy,
        single_instance_lock,
        token_for_mode,
    )
    from oternos.discord_embeds import (
        HelpCategoryView,
        _commands_embed,
        _hood_embed,
        _interaction_embed,
        _message_reply_commands,
        _reply_embed,
    )
    from oternos.discord_bridge import DiscordRuntimeBridge
    from oternos.core.runtime_commands import load_runtime_command, runtime_command_file_marker
    from oternos.soundcloud_client import SoundCloudAPI


def _intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    return intents


class HinTechDiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=COMMAND_PREFIX, intents=_intents(), case_insensitive=True, help_command=None)
        runtime_file = os.environ.get("HIN_TECH_RUNTIME_FILE") or None
        command_file = os.environ.get("HIN_TECH_COMMAND_FILE") or None
        self.bridge = DiscordRuntimeBridge(runtime_file=runtime_file, command_file=command_file)
        self.ffmpeg_path = shutil.which("ffmpeg")
        current_command = load_runtime_command(command_file)
        self._command_file = command_file
        self._runtime_command_marker = runtime_command_file_marker(command_file)
        self._last_runtime_command_id = current_command.command_id if current_command else ""
        self._runtime_command_task: asyncio.Task | None = None
        self._discord_status_task: asyncio.Task | None = None
        status_file = os.environ.get(DISCORD_STATUS_FILE_ENV, "").strip()
        self._discord_status_file = Path(status_file).expanduser() if status_file else Path.home() / DISCORD_STATUS_FILE_NAME
        self.last_cast_status = "No cast requests received yet."
        self._voice_source: discord.PCMVolumeTransformer | None = None
        self._voice_volume_override: float | None = None
        self._resolved_link_cache: dict[str, dict] = {}
        self.cast_queue: list[dict] = []
        self.cast_index = -1
        self.current_cast_payload: dict | None = None
        self.current_cast_input = ""
        self.cast_started_at = 0.0
        self.cast_seek_seconds = 0.0
        self.cast_duration_seconds = 0.0
        self.cast_paused = False
        self._voice_generation = 0
        self.cast_text_channel_id: int | None = None
        self.cast_embed_message_id: int | None = None
        self.cast_embed_channel_id: int | None = None
        self._last_cast_embed_signature = ""
        self._last_cast_embed_check_at = 0.0
        self._discord_panel_state_file = Path.home() / DISCORD_PANEL_STATE_FILE_NAME
        self._load_discord_panel_state()

    @property
    def voice_diag(self) -> str:
        return (
            f"py={sys.version.split()[0]} discord={discord.__version__} "
            f"has_nacl={getattr(discord.voice_client, 'has_nacl', False)} "
            f"ffmpeg={'yes' if self.ffmpeg_path else 'no'}"
        )

    async def setup_hook(self) -> None:
        self.add_view(CastControlView(self))
        await self.add_cog(PlayerControls(self))
        self._runtime_command_task = asyncio.create_task(self._watch_runtime_commands())
        self._discord_status_task = asyncio.create_task(self._publish_discord_status_loop())

    async def close(self) -> None:
        for task in (self._runtime_command_task, self._discord_status_task):
            if task is not None:
                task.cancel()
        await super().close()

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        self.cast_text_channel_id = int(message.channel.id)
        self._save_discord_panel_state()
        content = str(message.content or "").strip()
        command_triggers = {
            "@COMMANDS",
            "COMMANDS",
            "!COMMANDS",
            "CMDS",
            "!CMDS",
            "HELP",
            "!HELP",
            "COMMANDLIST",
            "!COMMANDLIST",
            "ALLCOMMANDS",
            "!ALLCOMMANDS",
        }
        if content.upper() in command_triggers:
            cog = self.get_cog("PlayerControls")
            if isinstance(cog, PlayerControls):
                await _message_reply_commands(message)
            return
        await self.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await _reply_embed(ctx, "COMMAND INPUT", f"Missing `{error.param.name}`. Use `{COMMAND_PREFIX}commands` for the command list.", color=0xFFCC66)
            return
        if isinstance(error, commands.BadArgument):
            await _reply_embed(ctx, "COMMAND INPUT", f"That argument did not parse correctly. Use `{COMMAND_PREFIX}commands` for examples.", color=0xFFCC66)
            return
        await _reply_embed(ctx, "COMMAND ERROR", f"{type(error).__name__}: {error}", color=0xFF5555)

    async def _watch_runtime_commands(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(0.08)
            self._sync_voice_volume()
            marker = runtime_command_file_marker(self._command_file)
            if marker == self._runtime_command_marker:
                continue
            self._runtime_command_marker = marker
            command = load_runtime_command(self._command_file)
            if command is None or command.command_id == self._last_runtime_command_id:
                continue
            self._last_runtime_command_id = command.command_id
            cog = self.get_cog("PlayerControls")
            if not isinstance(cog, PlayerControls):
                continue
            if command.action == "set_volume":
                self._set_voice_volume_from_payload(command.payload)
                continue
            if command.action == "discord_connect":
                await cog.connect_default_voice()
            elif command.action == "discord_disconnect":
                await cog.disconnect_voice()
            elif command.action == "discord_volume":
                self._set_voice_volume_from_payload(command.payload)
            elif command.action == "discord_cast_path":
                await cog.cast_payload_to_voice(command.payload, add_to_queue=True)
            elif command.action == "discord_play_pause":
                await cog.toggle_voice_playback()
            elif command.action == "discord_next":
                await cog.play_cast_queue_offset(1)
            elif command.action == "discord_previous":
                await cog.play_cast_queue_offset(-1)
            elif command.action == "discord_seek_percent":
                await cog.seek_current_cast_percent(command.payload)

    async def _publish_discord_status_loop(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            self._write_discord_status()
            await self._refresh_cast_embed_if_changed()
            await asyncio.sleep(0.5)

    async def _refresh_cast_embed_if_changed(self) -> None:
        has_panel = bool(self.cast_embed_message_id and self.cast_embed_channel_id)
        has_home_channel = bool(self.cast_text_channel_id)
        if not has_panel and not has_home_channel:
            return
        now = time.time()
        if now - float(self._last_cast_embed_check_at or 0.0) < 5.0:
            return
        self._last_cast_embed_check_at = now
        cog = self.get_cog("PlayerControls")
        if not isinstance(cog, PlayerControls):
            return
        await cog.post_or_update_cast_embed(only_if_changed=True)

    def _current_voice(self):
        return next((client for client in self.voice_clients if client.is_connected()), None)

    def _share_qt_now_playing(self) -> bool:
        value = os.environ.get(DISCORD_SHARE_QT_NOW_PLAYING_ENV, "").strip().lower()
        return value in {"1", "true", "yes", "on", "public"} or self._current_voice() is not None

    def _load_discord_panel_state(self) -> None:
        try:
            data = json.loads(self._discord_panel_state_file.read_text(encoding="utf-8"))
        except Exception:
            return
        try:
            self.cast_text_channel_id = int(data.get("cast_text_channel_id") or 0) or None
        except Exception:
            self.cast_text_channel_id = None
        try:
            self.cast_embed_channel_id = int(data.get("cast_embed_channel_id") or 0) or None
        except Exception:
            self.cast_embed_channel_id = None
        try:
            self.cast_embed_message_id = int(data.get("cast_embed_message_id") or 0) or None
        except Exception:
            self.cast_embed_message_id = None

    def _save_discord_panel_state(self) -> None:
        try:
            data = {
                "cast_text_channel_id": self.cast_text_channel_id,
                "cast_embed_channel_id": self.cast_embed_channel_id,
                "cast_embed_message_id": self.cast_embed_message_id,
            }
            tmp = self._discord_panel_state_file.with_name(self._discord_panel_state_file.name + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
            tmp.replace(self._discord_panel_state_file)
        except Exception:
            pass

    def _current_cast_position(self) -> float:
        position = max(0.0, float(self.cast_seek_seconds or 0.0))
        voice = self._current_voice()
        if voice is not None and voice.is_playing() and not voice.is_paused() and not self.cast_paused:
            started_at = float(self.cast_started_at or 0.0)
            if started_at > 0:
                position += max(0.0, time.time() - started_at)
        duration = max(0.0, float(self.cast_duration_seconds or 0.0))
        if duration > 0:
            return min(duration, position)
        return position

    def _minimal_cast_payload(self, payload: dict | None) -> dict:
        payload = dict(payload or {})
        return {
            "title": str(payload.get("title") or payload.get("name") or "Unknown"),
            "artist": str(payload.get("artist") or payload.get("channel") or "Unknown"),
            "album": str(payload.get("album") or ""),
            "source": str(payload.get("source") or ""),
            "path": str(payload.get("path") or ""),
            "url": str(payload.get("url") or payload.get("permalink_url") or ""),
            "duration_seconds": float(payload.get("duration_seconds") or payload.get("duration_sec") or 0.0) if str(payload.get("duration_seconds") or payload.get("duration_sec") or "").replace(".", "", 1).isdigit() else 0.0,
        }

    def _write_discord_status(self) -> None:
        try:
            voice = self._current_voice()
            source = self._voice_source
            volume = self._voice_volume_override
            if volume is None and source is not None:
                volume = float(getattr(source, "volume", 1.0) or 1.0)
            if volume is None:
                volume = self._runtime_volume()
            current = self._minimal_cast_payload(self.current_cast_payload)
            duration = max(float(self.cast_duration_seconds or 0.0), float(current.get("duration_seconds") or 0.0))
            current["duration_seconds"] = duration
            status = {
                "updated_at": time.time(),
                "online": True,
                "connected": bool(voice is not None and voice.is_connected()),
                "guild": str(getattr(getattr(voice, "guild", None), "name", "") if voice is not None else ""),
                "channel": str(getattr(getattr(voice, "channel", None), "name", "") if voice is not None else ""),
                "playing": bool(voice is not None and voice.is_playing()),
                "paused": bool((voice is not None and voice.is_paused()) or self.cast_paused),
                "last_cast_status": self.last_cast_status,
                "volume": max(0.0, min(1.0, float(volume or 0.0))),
                "queue_count": len(self.cast_queue),
                "queue_index": int(self.cast_index),
                "position": self._current_cast_position(),
                "duration": duration,
                "current": current,
                "queue": [self._minimal_cast_payload(item) for item in self.cast_queue],
            }
            self._discord_status_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._discord_status_file.with_name(self._discord_status_file.name + ".tmp")
            tmp.write_text(json.dumps(status, ensure_ascii=True), encoding="utf-8")
            tmp.replace(self._discord_status_file)
        except Exception:
            pass

    def _runtime_volume(self) -> float:
        try:
            snap = self.bridge.snapshot()
            if not snap.is_live:
                return 1.0
            return max(0.0, min(1.0, float(snap.volume or 0.0)))
        except Exception:
            return 1.0

    def _sync_voice_volume(self) -> None:
        source = self._voice_source
        if source is None:
            return
        try:
            if self._voice_volume_override is not None:
                source.volume = self._voice_volume_override
                return
            snap = self.bridge.snapshot()
            if snap.is_live:
                source.volume = self._runtime_volume()
        except Exception:
            self._voice_source = None

    def _invalidate_voice_callbacks(self) -> None:
        self._voice_generation += 1

    def _next_voice_generation(self) -> int:
        self._voice_generation += 1
        return self._voice_generation

    def _set_voice_volume_from_payload(self, payload: dict) -> None:
        try:
            fallback = self._voice_volume_override
            if fallback is None:
                fallback = self._runtime_volume()
            volume = max(0.0, min(1.0, float(payload.get("volume", fallback))))
            self._voice_volume_override = volume
            if self._voice_source is not None:
                self._voice_source.volume = volume
            self._write_discord_status()
        except Exception:
            self._voice_source = None


class CastControlView(discord.ui.View):
    def __init__(self, bot: HinTechDiscordBot):
        super().__init__(timeout=None)
        self.bot = bot

    def _controls(self) -> "PlayerControls | None":
        cog = self.bot.get_cog("PlayerControls")
        return cog if isinstance(cog, PlayerControls) else None

    def _cast_active(self) -> bool:
        voice = self.bot._current_voice()
        return bool(
            voice is not None
            and voice.is_connected()
            and (voice.is_playing() or voice.is_paused() or self.bot._voice_source is not None)
            and self.bot.current_cast_payload
        )

    async def _reply(self, interaction: discord.Interaction, message: str) -> None:
        try:
            await _interaction_embed(interaction, "HOOD BOT", message, ephemeral=True)
        except Exception:
            pass

    async def _ack(self, interaction: discord.Interaction) -> None:
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, custom_id="oternos_cast_prev")
    async def prev_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        controls = self._controls()
        if controls is None:
            await self._reply(interaction, "Controls unavailable.")
            return
        if self._cast_active() and self.bot.cast_queue:
            await controls.play_cast_queue_offset(-1)
        else:
            self.bot.last_cast_status = "Discord cast is not active. Use !qtprev for private Qt control."
        await controls.post_or_update_cast_embed(channel=interaction.channel)
        await self._ack(interaction)

    @discord.ui.button(label="Pause/Resume", style=discord.ButtonStyle.primary, custom_id="oternos_cast_toggle")
    async def toggle_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        controls = self._controls()
        if controls is None:
            await self._reply(interaction, "Controls unavailable.")
            return
        if self._cast_active() or self.bot.current_cast_payload:
            await controls.toggle_voice_playback()
        else:
            self.bot.last_cast_status = "Discord cast is not active. Use !qtplaypause for private Qt control."
            self.bot._write_discord_status()
        await controls.post_or_update_cast_embed(channel=interaction.channel)
        await self._ack(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="oternos_cast_next")
    async def next_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        controls = self._controls()
        if controls is None:
            await self._reply(interaction, "Controls unavailable.")
            return
        if self._cast_active() and self.bot.cast_queue:
            await controls.play_cast_queue_offset(1)
        else:
            self.bot.last_cast_status = "Discord cast is not active. Use !qtnext for private Qt control."
        await controls.post_or_update_cast_embed(channel=interaction.channel)
        await self._ack(interaction)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, custom_id="oternos_cast_stop")
    async def stop_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        controls = self._controls()
        if controls is None:
            await self._reply(interaction, "Controls unavailable.")
            return
        if self._cast_active():
            controls.stop_active_cast()
        else:
            self.bot.last_cast_status = "Discord cast is not active."
            self.bot._write_discord_status()
        await controls.post_or_update_cast_embed(channel=interaction.channel)
        await self._ack(interaction)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, custom_id="oternos_cast_queue")
    async def queue_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        controls = self._controls()
        if controls is None:
            await self._reply(interaction, "Controls unavailable.")
            return
        await self._reply(interaction, controls.cast_queue_text())


class ConvertFormatView(discord.ui.View):
    def __init__(self, controls: "PlayerControls", *, source_spec: dict, requester_id: int):
        super().__init__(timeout=180)
        self.controls = controls
        self.source_spec = dict(source_spec)
        self.requester_id = int(requester_id)

    async def _run(self, interaction: discord.Interaction, fmt: str, quality: str, label: str):
        if int(getattr(getattr(interaction, "user", None), "id", 0) or 0) != self.requester_id:
            await _interaction_embed(interaction, "CONVERT", "Only the person who started this conversion can choose the output format.")
            return
        await interaction.response.defer(thinking=True)
        path, detail = await self.controls.convert_source_spec(self.source_spec, fmt=fmt, quality=quality)
        if not path:
            await interaction.followup.send(embed=_hood_embed("CONVERT FAILED", detail or "Conversion failed.", color=0xFF5555), ephemeral=True)
            return
        output_path = Path(path)
        if not output_path.exists() or not output_path.is_file():
            await interaction.followup.send(embed=_hood_embed("CONVERT FAILED", "The output file was not created.", color=0xFF5555), ephemeral=True)
            return
        size_limit = 24 * 1024 * 1024
        if output_path.stat().st_size > size_limit:
            await interaction.followup.send(
                embed=_hood_embed(
                    "CONVERT READY",
                    f"`{output_path.name}` was created, but it is too large to upload to Discord automatically.",
                    color=0xFFCC66,
                ),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=_hood_embed("CONVERT READY", f"Built `{output_path.name}` as {label}."),
            file=discord.File(str(output_path), filename=output_path.name),
            ephemeral=False,
        )
        self.stop()

    @discord.ui.button(label="MP3", style=discord.ButtonStyle.primary)
    async def mp3_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._run(interaction, "mp3", "320", "MP3 320kbps")

    @discord.ui.button(label="M4A", style=discord.ButtonStyle.secondary)
    async def m4a_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._run(interaction, "m4a", "192", "M4A 192kbps")

    @discord.ui.button(label="FLAC", style=discord.ButtonStyle.secondary)
    async def flac_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._run(interaction, "flac", "0", "FLAC")

    @discord.ui.button(label="WAV", style=discord.ButtonStyle.secondary)
    async def wav_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self._run(interaction, "wav", "0", "WAV PCM")


class PlayerControls(commands.Cog):
    def __init__(self, bot: HinTechDiscordBot):
        self.bot = bot
        self._cast_lock = asyncio.Lock()

    async def _send(self, ctx: commands.Context, title: str, message: str, *, color: int = 0xEDEDED) -> None:
        await _reply_embed(ctx, title, message, color=color)

    def command_list_text(self) -> str:
        prefix = COMMAND_PREFIX
        return "\n".join(
            (
                "H-I-N TECH COMMANDS",
                f"{prefix}join - connect the bot to your current voice channel",
                f"{prefix}leave - disconnect the bot from voice",
                f"{prefix}play <SoundCloud search or direct link> - play/add to the Discord cast queue",
                f"{prefix}scsearch <query> - show top SoundCloud matches",
                f"{prefix}vcast - cast the current H-I-N TECH track and silence local playback",
                f"{prefix}vplay - play the current local runtime track in voice",
                f"{prefix}pause / {prefix}toggle - pause/resume Discord voice playback",
                f"{prefix}next / {prefix}prev - move through the Discord cast queue",
                f"{prefix}skip - skip the current Discord voice song",
                f"{prefix}vstop - stop Discord voice playback",
                f"{prefix}removeSong - remove/stop the current Discord voice song",
                f"{prefix}queue - show the Discord cast queue",
                f"{prefix}castqueue - show the Discord cast queue",
                f"{prefix}castnow <number> - play a Discord cast queue position",
                f"{prefix}clearcast - clear the Discord cast queue",
                f"{prefix}purge <count> - delete recent messages in the current channel",
                f"{prefix}kick / {prefix}ban / {prefix}unban - moderation member actions",
                f"{prefix}timeout / {prefix}untimeout - apply or remove a member timeout",
                f"{prefix}8ball / {prefix}coinflip / {prefix}roll / {prefix}choose / {prefix}rate - fun chat commands",
                f"{prefix}ship / {prefix}mood / {prefix}roast / {prefix}compliment - extra fun/community commands",
                f"{prefix}castpanel - post/update the Discord Now Playing panel",
                f"{prefix}songs [page] - show library songs",
                f"{prefix}volume <0-100> - set Discord voice volume",
                f"{prefix}nowplaying - show the Discord cast track",
                f"{prefix}vunmute - resume local Qt playback after casting",
                f"{prefix}qtplaypause / {prefix}qtnext / {prefix}qtprev / {prefix}qtqueue / {prefix}qtnowplaying - owner-side Qt controls",
                f"{prefix}vcdiag / {prefix}rtdiag / {prefix}castdiag - diagnostics",
                f"{prefix}commands, {prefix}help, commands, or @COMMANDS - show this list",
            )
        )

    def _ffmpeg_audio_args(self, fmt: str, quality: str) -> list[str]:
        fmt = str(fmt or "mp3").lower()
        quality = str(quality or "192")
        if fmt == "mp3":
            return ["-codec:a", "libmp3lame", "-b:a", f"{quality}k"]
        if fmt == "m4a":
            return ["-codec:a", "aac", "-b:a", f"{quality}k"]
        if fmt == "flac":
            return ["-codec:a", "flac"]
        if fmt == "wav":
            return ["-codec:a", "pcm_s16le"]
        return ["-codec:a", "libmp3lame", "-b:a", f"{quality}k"]

    async def convert_source_spec(self, source_spec: dict, *, fmt: str, quality: str) -> tuple[str, str]:
        return await asyncio.to_thread(self._convert_source_spec_sync, dict(source_spec), fmt, quality)

    def _convert_source_spec_sync(self, source_spec: dict, fmt: str, quality: str) -> tuple[str, str]:
        ffmpeg = self.bot.ffmpeg_path or shutil.which("ffmpeg") or ""
        if not ffmpeg:
            return "", "FFmpeg is missing on the bot machine."
        temp_root = Path(tempfile.mkdtemp(prefix="oternos_discord_convert_"))
        output_file = temp_root / f"converted.{fmt}"
        source_kind = str(source_spec.get("kind") or "").strip().lower()
        try:
            if source_kind == "attachment":
                input_path = Path(str(source_spec.get("path") or "")).expanduser()
                if not input_path.exists() or not input_path.is_file():
                    return "", "The attached file is no longer available."
                cmd = [ffmpeg, "-y", "-i", str(input_path), "-vn"]
                cmd.extend(self._ffmpeg_audio_args(fmt, quality))
                cmd.append(str(output_file))
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=1800,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
                )
                if result.returncode != 0:
                    detail = (result.stderr or result.stdout or "FFMPEG FAILED").strip().splitlines()
                    return "", detail[-1] if detail else "FFMPEG FAILED"
            elif source_kind == "link":
                try:
                    import yt_dlp
                except Exception:
                    return "", "yt-dlp is missing on the bot machine."
                url = str(source_spec.get("url") or "").strip()
                if not url:
                    return "", "No link was supplied."
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "format": "bestaudio/best",
                    "noplaylist": True,
                    "outtmpl": str(temp_root / "source.%(ext)s"),
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": str(fmt),
                            "preferredquality": str(quality),
                        }
                    ],
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(url, download=True)
                matches = sorted(temp_root.glob(f"source*.{fmt}"))
                if matches:
                    output_file = matches[0]
                else:
                    all_files = [path for path in temp_root.iterdir() if path.is_file() and path.suffix.casefold() == f".{fmt}".casefold()]
                    if not all_files:
                        return "", "No converted output file was created."
                    output_file = all_files[0]
            else:
                return "", "Unsupported conversion source."
            if not output_file.exists() or not output_file.is_file() or output_file.stat().st_size <= 0:
                return "", "Converted output file is missing."
            return str(output_file), "OK"
        except Exception as exc:
            return "", str(exc)

    async def _save_attachment_to_temp(self, attachment: discord.Attachment) -> tuple[str, str]:
        try:
            suffix = Path(str(attachment.filename or "file")).suffix or mimetypes.guess_extension(str(attachment.content_type or "")) or ".bin"
            temp_root = Path(tempfile.mkdtemp(prefix="oternos_discord_attachment_"))
            target = temp_root / f"input{suffix}"
            await attachment.save(target)
            return str(target), "OK"
        except Exception as exc:
            return "", str(exc)

    async def _send_commands_embed(self, ctx: commands.Context):
        await ctx.reply(embed=_commands_embed(COMMAND_PREFIX), view=HelpCategoryView(), mention_author=False)

    async def _require_guild_permissions(self, ctx: commands.Context, **permissions: bool) -> bool:
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            await self._send(ctx, "MODERATION", "These moderation commands only work inside a server.", color=0xFFCC66)
            return False
        perms = getattr(ctx.author.guild_permissions, "__dict__", None)
        missing = [name.replace("_", " ") for name, needed in permissions.items() if needed and not getattr(ctx.author.guild_permissions, name, False)]
        if missing:
            await self._send(ctx, "MODERATION", f"You are missing permission(s): {', '.join(missing)}.", color=0xFF5555)
            return False
        me = ctx.guild.me if hasattr(ctx.guild, "me") else ctx.guild.get_member(self.bot.user.id if self.bot.user else 0)
        if me is None:
            await self._send(ctx, "MODERATION", "Bot member state is unavailable right now.", color=0xFF5555)
            return False
        bot_missing = [name.replace("_", " ") for name, needed in permissions.items() if needed and not getattr(me.guild_permissions, name, False)]
        if bot_missing:
            await self._send(ctx, "MODERATION", f"I am missing permission(s): {', '.join(bot_missing)}.", color=0xFF5555)
            return False
        return True

    def _member_action_reason(self, ctx: commands.Context, action: str, reason: str = "") -> str:
        actor = str(getattr(ctx.author, "display_name", None) or ctx.author)
        base = f"HOOD BOT {action} by {actor}"
        clean_reason = str(reason or "").strip()
        return f"{base} // {clean_reason}" if clean_reason else base

    async def _ensure_actionable_member(self, ctx: commands.Context, member: discord.Member) -> bool:
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            await self._send(ctx, "MODERATION", "This command only works inside a server.", color=0xFFCC66)
            return False
        if member.id == ctx.author.id:
            await self._send(ctx, "MODERATION", "You cannot use this command on yourself.", color=0xFFCC66)
            return False
        if self.bot.user and member.id == self.bot.user.id:
            await self._send(ctx, "MODERATION", "I cannot moderate myself.", color=0xFFCC66)
            return False
        me = ctx.guild.me if hasattr(ctx.guild, "me") else ctx.guild.get_member(self.bot.user.id if self.bot.user else 0)
        if me is not None and member.top_role >= me.top_role:
            await self._send(ctx, "MODERATION", "I cannot act on that member because of role hierarchy.", color=0xFF5555)
            return False
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await self._send(ctx, "MODERATION", "You cannot act on a member with an equal or higher role.", color=0xFF5555)
            return False
        return True

    def _voice_error_text(self, prefix: str, exc: Exception) -> str:
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        return f"{prefix}: {type(exc).__name__}: {exc} [{self.bot.voice_diag}]"

    def cast_queue_text(self) -> str:
        if not self.bot.cast_queue:
            return "Discord cast queue is empty."
        lines = ["DISCORD CAST QUEUE"]
        for index, payload in enumerate(self.bot.cast_queue[:20]):
            marker = ">" if index == self.bot.cast_index else " "
            title = str(payload.get("title") or payload.get("name") or "Unknown")
            artist = str(payload.get("artist") or payload.get("channel") or "Unknown")
            source = str(payload.get("source") or "cast").upper()
            requester = str(payload.get("requester") or "").strip()
            suffix = f" // requested by {requester}" if requester else ""
            lines.append(f"{marker} {index + 1:02d}. {title} - {artist} [{source}]{suffix}")
        if len(self.bot.cast_queue) > 20:
            lines.append(f"...and {len(self.bot.cast_queue) - 20} more")
        return "\n".join(lines)

    def stop_active_cast(self) -> None:
        voice = self.bot._current_voice()
        if voice is not None and voice.is_connected() and (voice.is_playing() or voice.is_paused()):
            self.bot.cast_seek_seconds = self.bot._current_cast_position()
            self.bot.cast_started_at = 0.0
            self.bot.cast_paused = False
            self.bot._invalidate_voice_callbacks()
            voice.stop()
        self.bot._voice_source = None
        self.bot.last_cast_status = "stopped Discord voice"
        self.bot._write_discord_status()

    def cast_embed(self) -> discord.Embed:
        voice = self.bot._current_voice()
        cast_active = bool(
            voice is not None
            and voice.is_connected()
            and (voice.is_playing() or voice.is_paused() or self.bot._voice_source is not None)
            and self.bot.current_cast_payload
        )
        payload = dict(self.bot.current_cast_payload or {})
        position = self.bot._current_cast_position()
        duration = float(self.bot.cast_duration_seconds or 0.0)
        mode = "DISCORD CAST"
        if cast_active:
            title = str(payload.get("title") or payload.get("name") or "No cast track")
            artist = str(payload.get("artist") or payload.get("channel") or "Unknown Artist")
            source = str(payload.get("source") or "cast").upper()
            status = "PLAYING" if voice is not None and voice.is_playing() else ("PAUSED" if voice is not None and voice.is_paused() else "READY")
        elif payload and (self.bot.cast_queue or voice is not None):
            title = str(payload.get("title") or payload.get("name") or "No cast track")
            artist = str(payload.get("artist") or payload.get("channel") or "Unknown Artist")
            source = str(payload.get("source") or "cast").upper()
            status = "READY"
            mode = "DISCORD CAST"
        elif self.bot._share_qt_now_playing():
            snap = self.bot.bridge.snapshot()
            if snap.is_live and snap.track is not None:
                title = snap.track.title
                artist = snap.track.artist
                source = str(snap.track.source or snap.source or "local").upper()
                status = "PAUSED" if snap.is_paused else "PLAYING" if snap.is_playing else "IDLE"
                position = float(snap.position or 0.0)
                duration = float(snap.duration or 0.0)
                mode = "APP NOW PLAYING"
                payload = {
                    "title": title,
                    "artist": artist,
                    "source": source,
                    "art_url": snap.track.art_url,
                    "art_path": snap.track.art_path,
                }
            elif payload:
                title = str(payload.get("title") or payload.get("name") or "No cast track")
                artist = str(payload.get("artist") or payload.get("channel") or "Unknown Artist")
                source = str(payload.get("source") or "cast").upper()
                status = "READY"
            else:
                title = "No track loaded"
                artist = "Start playback in H-I-N TECH"
                source = "OFFLINE"
                status = "READY"
        else:
            title = "Discord Cast Standby"
            artist = "Qt playback is private while the bot is not casting."
            source = "PRIVATE"
            status = "READY"
            mode = "APP PRIVATE MODE"
        embed = discord.Embed(
            title=title,
            description=f"{artist}\n`{mode}` // `{source}` // `{status}`",
            color=0xEDEDED,
        )
        if duration > 0:
            embed.add_field(
                name="Position",
                value=f"{self._format_duration(position)} / {self._format_duration(duration)}",
                inline=True,
            )
        else:
            embed.add_field(name="Position", value="live / unknown", inline=True)
        queue_pos = self.bot.cast_index + 1 if self.bot.cast_index >= 0 else 0
        queue_label = f"{queue_pos}/{len(self.bot.cast_queue)}" if cast_active or self.bot.cast_queue else "private"
        embed.add_field(name="Queue", value=queue_label, inline=True)
        channel = getattr(getattr(voice, "channel", None), "name", "not connected") if voice is not None else "not connected"
        embed.add_field(name="Voice", value=str(channel), inline=True)
        source_url = str(payload.get("url") or payload.get("web_url") or payload.get("permalink_url") or payload.get("path") or "").strip()
        if source_url.lower().startswith(("http://", "https://")):
            embed.add_field(name="Source", value=f"[Open original]({source_url})", inline=False)
        requester = str(payload.get("requester") or "").strip()
        if requester:
            embed.add_field(name="Requested By", value=requester[:256], inline=True)
        art_url = str(payload.get("art_url") or payload.get("artwork_url") or payload.get("thumbnail") or "")
        if art_url.lower().startswith(("http://", "https://")):
            embed.set_thumbnail(url=art_url)
        embed.set_footer(text=f"H-I-N TECH Discord Cast // {self.bot.last_cast_status}")
        return embed

    def cast_embed_signature(self) -> str:
        voice = self.bot._current_voice()
        snap = self.bot.bridge.snapshot()
        track_key = ""
        share_qt = self.bot._share_qt_now_playing()
        voice_connected = bool(voice is not None and voice.is_connected())
        cast_key = self._payload_key(self.bot.current_cast_payload or {})
        if share_qt and snap.track is not None:
            track_key = "|".join((snap.track.title, snap.track.artist, snap.track.source, snap.track.path))
        voice_state = "none"
        if voice_connected:
            voice_state = "playing" if voice.is_playing() else "paused" if voice.is_paused() else "connected"
        pos_source = self.bot._current_cast_position() if voice_state in {"playing", "paused"} else (snap.position if share_qt else 0.0)
        pos_bucket = int(float(pos_source or 0.0) // 10)
        return "|".join(
            (
                voice_state,
                str(self.bot.cast_index),
                str(len(self.bot.cast_queue)),
                cast_key,
                track_key,
                str(snap.is_playing if share_qt else False),
                str(snap.is_paused if share_qt else False),
                str(pos_bucket),
                self.bot.last_cast_status,
            )
        )

    def _format_duration(self, seconds: float) -> str:
        seconds = max(0, int(seconds or 0))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{sec:02d}"
        return f"{minutes}:{sec:02d}"

    async def post_or_update_cast_embed(self, channel: discord.abc.Messageable | None = None, *, only_if_changed: bool = False) -> None:
        target = channel
        if target is None and self.bot.cast_text_channel_id is not None:
            target = self.bot.get_channel(self.bot.cast_text_channel_id)
        signature = self.cast_embed_signature()
        if only_if_changed and signature == self.bot._last_cast_embed_signature:
            return
        embed = self.cast_embed()
        view = CastControlView(self.bot)
        message = None
        if self.bot.cast_embed_message_id and self.bot.cast_embed_channel_id:
            old_channel = self.bot.get_channel(self.bot.cast_embed_channel_id)
            if old_channel is not None and hasattr(old_channel, "fetch_message"):
                try:
                    message = await old_channel.fetch_message(self.bot.cast_embed_message_id)
                except Exception:
                    message = None
        if message is not None:
            try:
                await message.edit(embed=embed, view=view)
                self.bot._last_cast_embed_signature = signature
                self.bot._save_discord_panel_state()
                return
            except Exception:
                pass
        if target is None and self.bot.cast_embed_channel_id is not None:
            target = self.bot.get_channel(self.bot.cast_embed_channel_id)
        if target is None:
            return
        try:
            sent = await target.send(embed=embed, view=view)
        except Exception:
            return
        self.bot.cast_embed_message_id = int(sent.id)
        self.bot.cast_embed_channel_id = int(sent.channel.id)
        self.bot.cast_text_channel_id = int(sent.channel.id)
        self.bot._last_cast_embed_signature = signature
        self.bot._save_discord_panel_state()

    async def _ensure_voice(self, ctx: commands.Context) -> discord.VoiceClient | None:
        if not isinstance(ctx.author, discord.Member) or ctx.author.voice is None or ctx.author.voice.channel is None:
            await _reply_embed(ctx, "VOICE", "Join a voice channel first.", color=0xFFCC66)
            self.bot._write_discord_status()
            return None
        target = ctx.author.voice.channel
        voice = ctx.guild.voice_client if ctx.guild is not None else None
        if voice is not None:
            if voice.channel != target:
                try:
                    await voice.move_to(target)
                except Exception as exc:
                    await _reply_embed(ctx, "VOICE ERROR", self._voice_error_text("Could not move to voice channel", exc), color=0xFF5555)
                    self.bot._write_discord_status()
                    return None
            self.bot.last_cast_status = f"connected: {getattr(voice.channel, 'name', 'voice')}"
            self.bot._write_discord_status()
            return voice
        try:
            voice = await target.connect()
            self.bot.last_cast_status = f"connected: {target.name}"
            self.bot._write_discord_status()
            return voice
        except Exception as exc:
            await _reply_embed(ctx, "VOICE ERROR", self._voice_error_text("Could not join voice channel", exc), color=0xFF5555)
            self.bot._write_discord_status()
            return None

    async def connect_default_voice(self) -> discord.VoiceClient | None:
        voice = self.bot._current_voice()
        if voice is not None:
            self.bot.last_cast_status = f"connected: {getattr(voice.channel, 'name', 'voice')}"
            self.bot._write_discord_status()
            return voice
        channel = self._default_voice_channel()
        if channel is None:
            self.bot.last_cast_status = "connect failed: no voice channel with users found"
            print(f"Discord cast {self.bot.last_cast_status}.")
            self.bot._write_discord_status()
            return None
        try:
            voice = await channel.connect()
            self.bot.last_cast_status = f"connected: {channel.name}"
            print(f"Discord voice connected: {channel.name}")
            self.bot._write_discord_status()
            return voice
        except Exception as exc:
            self.bot.last_cast_status = f"connect failed: {type(exc).__name__}: {exc}"
            traceback.print_exception(type(exc), exc, exc.__traceback__)
            self.bot._write_discord_status()
            return None

    def _default_voice_channel(self):
        for guild in self.bot.guilds:
            channels = list(getattr(guild, "voice_channels", []) or [])
            for channel in channels:
                try:
                    if any(not member.bot for member in channel.members):
                        return channel
                except Exception:
                    continue
            if channels:
                return channels[0]
        return None

    async def disconnect_voice(self) -> None:
        voice = self.bot._current_voice()
        if voice is None:
            self.bot.last_cast_status = "disconnect ignored: not connected"
            self.bot._write_discord_status()
            return
        try:
            if voice.is_playing() or voice.is_paused():
                self.bot._invalidate_voice_callbacks()
                voice.stop()
            self.bot._voice_source = None
            self.bot.cast_paused = False
            self.bot.cast_started_at = 0.0
            self.bot.cast_seek_seconds = 0.0
            await voice.disconnect()
            self.bot.last_cast_status = "disconnected"
        except Exception as exc:
            self.bot.last_cast_status = f"disconnect failed: {type(exc).__name__}: {exc}"
        self.bot._write_discord_status()

    async def toggle_voice_playback(self) -> None:
        async with self._cast_lock:
            voice = self.bot._current_voice()
            if voice is None:
                await self.connect_default_voice()
                return
            if voice.is_paused():
                voice.resume()
                self.bot.cast_started_at = time.time()
                self.bot.cast_paused = False
                self.bot.last_cast_status = "resumed Discord voice"
            elif voice.is_playing():
                self.bot.cast_seek_seconds = self.bot._current_cast_position()
                self.bot.cast_paused = True
                voice.pause()
                self.bot.last_cast_status = "paused Discord voice"
            elif self.bot.current_cast_payload:
                await self._cast_payload_to_voice_locked(dict(self.bot.current_cast_payload), add_to_queue=False)
            else:
                self.bot.last_cast_status = "play ignored: no cast loaded"
            self.bot._write_discord_status()
        await self.post_or_update_cast_embed()

    async def play_cast_queue_offset(self, offset: int) -> None:
        async with self._cast_lock:
            if not self.bot.cast_queue:
                self.bot.last_cast_status = "queue empty"
                return
            target = max(0, min(len(self.bot.cast_queue) - 1, self.bot.cast_index + int(offset)))
            if target == self.bot.cast_index and self.bot.current_cast_payload:
                self.bot.last_cast_status = "queue boundary"
                return
            self.bot.cast_index = target
            await self._cast_payload_to_voice_locked(dict(self.bot.cast_queue[target]), add_to_queue=False)

    async def seek_current_cast_percent(self, payload: dict) -> None:
        async with self._cast_lock:
            current = dict(self.bot.current_cast_payload or {})
            if not current:
                self.bot.last_cast_status = "seek ignored: no cast loaded"
                return
            duration = self._payload_duration_seconds(current)
            if duration <= 0:
                self.bot.last_cast_status = "seek ignored: unknown duration"
                self.bot._write_discord_status()
                return
            try:
                percent = max(0.0, min(100.0, float(payload.get("percent", 0.0) or 0.0)))
            except Exception:
                percent = 0.0
            current["seek_seconds"] = duration * (percent / 100.0)
            self.bot.last_cast_status = f"seeking to {percent:.0f}%"
            await self._cast_payload_to_voice_locked(current, add_to_queue=False)

    async def cast_payload_to_voice(self, payload: dict, *, add_to_queue: bool = False) -> None:
        async with self._cast_lock:
            await self._cast_payload_to_voice_locked(payload, add_to_queue=add_to_queue)

    async def _cast_payload_to_voice_locked(self, payload: dict, *, add_to_queue: bool = False) -> None:
        """Handle a cast request coming from the Qt library card button."""
        if not self.bot.ffmpeg_path:
            self.bot.last_cast_status = "ignored: ffmpeg not found"
            print(f"Discord cast {self.bot.last_cast_status}.")
            self.bot._write_discord_status()
            return
        voice = self.bot._current_voice()
        active = bool(voice is not None and voice.is_connected() and (voice.is_playing() or voice.is_paused()))
        if add_to_queue:
            self._remember_cast_payload(payload)
            if active and self._payload_key(payload) != self._payload_key(self.bot.current_cast_payload or {}):
                title = str(payload.get("title", "") or payload.get("name", "") or "Source Track")
                self.bot.last_cast_status = f"queued: {title}"
                self.bot._write_discord_status()
                return
        if voice is None:
            voice = await self.connect_default_voice()
            if voice is None:
                self.bot._write_discord_status()
                return
        payload_title = str(payload.get("title", "") or payload.get("name", "") or "Source Track")
        self.bot.last_cast_status = f"resolving: {payload_title}"
        self.bot._write_discord_status()
        audio_input = await asyncio.to_thread(self._resolve_cast_input, payload)
        if not audio_input:
            raw_path = str(payload.get("path", "") or "").strip()
            raw_url = str(payload.get("url", "") or "").strip()
            self.bot.last_cast_status = f"ignored: invalid source path={raw_path!r} url={raw_url!r}"
            print(f"Discord cast {self.bot.last_cast_status}.")
            self.bot._write_discord_status()
            return
        if voice.is_playing() or voice.is_paused():
            self.bot._invalidate_voice_callbacks()
            voice.stop()
        try:
            token = self.bot._next_voice_generation()
            payload_volume = self._payload_volume(payload)
            self.bot._voice_volume_override = payload_volume
            audio = self._voice_audio(
                audio_input,
                volume=payload_volume,
                start_seconds=self._duration_seconds(payload.get("seek_seconds")),
            )
            self.bot._voice_source = audio
            self.bot.current_cast_payload = dict(payload)
            self.bot.current_cast_input = str(audio_input)
            self.bot.cast_duration_seconds = self._payload_duration_seconds(payload)
            self.bot.cast_seek_seconds = self._duration_seconds(payload.get("seek_seconds"))
            self.bot.cast_started_at = time.time()
            self.bot.cast_paused = False
            voice.play(audio, after=lambda error, token=token: self._after_voice_playback(error, token))
        except Exception as exc:
            self.bot.last_cast_status = f"failed: {type(exc).__name__}: {exc}"
            traceback.print_exception(type(exc), exc, exc.__traceback__)
            self.bot._write_discord_status()
            return
        if bool(payload.get("pause_qt", True)):
            self.bot.bridge.pause_qt_local_for_cast()
        title = str(payload.get("title", "") or Path(str(audio_input)).stem or "Source Track")
        artist = str(payload.get("artist", "") or "Unknown Artist")
        self.bot.last_cast_status = f"playing: {title} — {artist}"
        print(f"Discord cast started: {title} — {artist}")
        self.bot._write_discord_status()
        await self.post_or_update_cast_embed()

    def _remember_cast_payload(self, payload: dict) -> None:
        key = self._payload_key(payload)
        for index, item in enumerate(self.bot.cast_queue):
            if self._payload_key(item) == key:
                self.bot.cast_index = index
                self.bot._write_discord_status()
                return
        self.bot.cast_queue.append(dict(payload))
        self.bot.cast_index = len(self.bot.cast_queue) - 1
        self.bot._write_discord_status()

    def _payload_key(self, payload: dict) -> str:
        return str(payload.get("path") or payload.get("url") or payload.get("permalink_url") or payload.get("title") or "")

    def _after_voice_playback(self, error: Exception | None = None, token: int | None = None) -> None:
        if token is not None and token != self.bot._voice_generation:
            return
        self.bot._voice_source = None
        if error is None and self.bot.cast_duration_seconds > 0:
            self.bot.cast_seek_seconds = self.bot.cast_duration_seconds
        else:
            self.bot.cast_seek_seconds = self.bot._current_cast_position()
        self.bot.cast_started_at = 0.0
        self.bot.cast_paused = False
        if error is not None:
            print(f"Discord voice playback ended with error: {error}")
            self.bot.last_cast_status = f"ended with error: {error}"
        self.bot._write_discord_status()
        try:
            self.bot.loop.create_task(self._advance_after_voice_playback(token, error))
        except Exception:
            pass

    async def _advance_after_voice_playback(self, token: int | None, error: Exception | None) -> None:
        await self.post_or_update_cast_embed()
        if error is not None:
            return
        if token is not None and token != self.bot._voice_generation:
            return
        async with self._cast_lock:
            if not self.bot.cast_queue:
                return
            next_index = self.bot.cast_index + 1
            if next_index < 0 or next_index >= len(self.bot.cast_queue):
                return
            self.bot.cast_index = next_index
            await self._cast_payload_to_voice_locked(dict(self.bot.cast_queue[next_index]), add_to_queue=False)

    def _voice_audio(self, source: str, *, volume: float | None = None, start_seconds: float = 0.0) -> discord.PCMVolumeTransformer:
        is_url = str(source).lower().startswith(("http://", "https://"))
        before_parts = []
        if start_seconds > 0:
            before_parts.append(f"-ss {start_seconds:.3f}")
        if is_url:
            before_parts.append("-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5")
        kwargs = {"executable": self.bot.ffmpeg_path}
        if before_parts:
            kwargs["before_options"] = " ".join(before_parts)
        ffmpeg = discord.FFmpegPCMAudio(str(source), **kwargs)
        return discord.PCMVolumeTransformer(ffmpeg, volume=self.bot._runtime_volume() if volume is None else volume)

    def _payload_volume(self, payload: dict) -> float:
        try:
            return max(0.0, min(1.0, float(payload.get("volume", self.bot._runtime_volume()))))
        except Exception:
            return self.bot._runtime_volume()

    def _payload_duration_seconds(self, payload: dict) -> float:
        for key in ("duration_seconds", "duration_sec", "length_seconds"):
            seconds = self._duration_seconds(payload.get(key))
            if seconds > 0:
                return seconds
        seconds = self._duration_seconds(payload.get("duration"))
        if seconds > 0:
            source = str(payload.get("source") or "").strip().lower()
            if source == "soundcloud":
                try:
                    raw = float(payload.get("duration") or 0.0)
                except Exception:
                    raw = 0.0
                if raw > 10000:
                    return seconds / 1000.0
            return seconds
        return self._duration_seconds(payload.get("length"))

    def _resolve_cast_input(self, payload: dict) -> str:
        raw_path = str(payload.get("path", "") or "").strip()
        if raw_path:
            source_path = Path(raw_path)
            if source_path.exists() and source_path.is_file():
                return str(source_path)
        raw_url = str(payload.get("url") or payload.get("stream_url") or payload.get("web_url") or payload.get("permalink_url") or "").strip()
        if not raw_url:
            return ""
        if raw_url.lower().startswith(("http://", "https://")):
            direct = self._resolve_with_ytdlp(raw_url)
            return direct or raw_url
        return raw_url

    def _cache_direct_link_result(self, url: str, *, direct_url: str = "", info: dict | None = None):
        key = str(url or "").strip()
        if not key:
            return
        self.bot._resolved_link_cache[key] = {
            "cached_at": time.time(),
            "direct_url": str(direct_url or "").strip(),
            "info": dict(info or {}),
        }

    def _cached_direct_link_result(self, url: str) -> dict | None:
        key = str(url or "").strip()
        if not key:
            return None
        entry = self.bot._resolved_link_cache.get(key)
        if not entry:
            return None
        if (time.time() - float(entry.get("cached_at") or 0.0)) > 900:
            self.bot._resolved_link_cache.pop(key, None)
            return None
        return entry

    def _link_source_label(self, url: str) -> str:
        try:
            host = urllib.parse.urlparse(str(url or "")).netloc.casefold()
        except Exception:
            host = ""
        if host.startswith("www."):
            host = host[4:]
        if "instagram.com" in host:
            return "instagram"
        if "youtube.com" in host or "youtu.be" in host:
            return "youtube"
        if "soundcloud.com" in host:
            return "soundcloud"
        if "tiktok.com" in host:
            return "tiktok"
        if "facebook.com" in host or "fb.watch" in host:
            return "facebook"
        return "discord-link"

    def _direct_link_payload(self, url: str, *, requester: str) -> dict:
        clean_url = str(url or "").strip().strip("<>")
        source = self._link_source_label(clean_url)
        title = Path(clean_url.split("?", 1)[0].rstrip("/")).name or "Queued Link"
        artist = requester
        duration_seconds = 0.0
        art_url = ""
        cached = self._cached_direct_link_result(clean_url)
        if cached:
            info = dict(cached.get("info") or {})
            title = str(info.get("track") or info.get("title") or title or "Queued Link")
            artist = str(info.get("artist") or info.get("uploader") or info.get("channel") or requester)
            duration_seconds = self._duration_seconds(info.get("duration"))
            art_url = str(info.get("thumbnail") or "")
            extractor_key = str(info.get("extractor_key") or info.get("extractor") or "").strip().lower()
            if extractor_key:
                source = extractor_key
        try:
            import yt_dlp

            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "format": "bestaudio/best",
                "noplaylist": True,
                "socket_timeout": 15,
                "retries": 1,
                "extractor_retries": 1,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
            if isinstance(info, dict):
                self._cache_direct_link_result(clean_url, info=info)
                title = str(info.get("track") or info.get("title") or title or "Queued Link")
                artist = str(
                    info.get("artist")
                    or info.get("uploader")
                    or info.get("channel")
                    or requester
                )
                duration_seconds = self._duration_seconds(info.get("duration"))
                art_url = str(info.get("thumbnail") or "")
                extractor_key = str(info.get("extractor_key") or info.get("extractor") or "").strip().lower()
                if extractor_key:
                    source = extractor_key
        except Exception:
            pass
        return {
            "url": clean_url,
            "title": title,
            "artist": artist,
            "source": source,
            "requester": requester,
            "pause_qt": False,
            "duration_seconds": duration_seconds,
            "art_url": art_url,
            "volume": self.bot._voice_volume_override if self.bot._voice_volume_override is not None else self.bot._runtime_volume(),
        }

    def _resolve_with_ytdlp(self, url: str) -> str:
        cached = self._cached_direct_link_result(url)
        if cached:
            direct_url = str(cached.get("direct_url") or "").strip()
            if direct_url:
                return direct_url
        try:
            import yt_dlp
        except Exception:
            return ""
        try:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "format": "bestaudio/best",
                "noplaylist": True,
                "extract_flat": False,
                "socket_timeout": 15,
                "retries": 1,
                "extractor_retries": 1,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not isinstance(info, dict):
                return ""
            if info.get("url"):
                direct_url = str(info["url"])
                self._cache_direct_link_result(url, direct_url=direct_url, info=info)
                return direct_url
            formats = info.get("formats")
            if isinstance(formats, list):
                for fmt in reversed(formats):
                    direct = fmt.get("url") if isinstance(fmt, dict) else ""
                    if direct:
                        direct_url = str(direct)
                        self._cache_direct_link_result(url, direct_url=direct_url, info=info)
                        return direct_url
        except Exception as exc:
            print(f"yt-dlp cast resolve failed: {exc}")
        return ""

    def _duration_seconds(self, value) -> float:
        if isinstance(value, (int, float)):
            return max(0.0, float(value))
        text = str(value or "").strip()
        if ":" in text:
            try:
                parts = [int(part) for part in text.split(":")]
            except Exception:
                return 0.0
            if len(parts) == 2:
                return float(parts[0] * 60 + parts[1])
            if len(parts) == 3:
                return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
        try:
            return max(0.0, float(text or 0.0))
        except Exception:
            return 0.0

    def _soundcloud_track_url(self, track: dict) -> str:
        for key in ("permalink_url", "web_url", "url", "link"):
            value = str(track.get(key) or "").strip()
            if value:
                return value
        user = track.get("user") if isinstance(track.get("user"), dict) else {}
        user_slug = str(user.get("permalink") or user.get("username") or "").strip().strip("/")
        track_slug = str(track.get("permalink") or "").strip().strip("/")
        if user_slug and track_slug:
            return f"https://soundcloud.com/{user_slug}/{track_slug}"
        return ""

    def _soundcloud_payload(self, track: dict, *, requester: str = "") -> dict:
        user = track.get("user") if isinstance(track.get("user"), dict) else {}
        title = str(track.get("title") or track.get("name") or "SoundCloud Track").strip()
        artist = str(track.get("artist") or track.get("channel") or user.get("username") or user.get("name") or requester or "SoundCloud").strip()
        duration = self._duration_seconds(track.get("duration_seconds") or track.get("duration_sec"))
        if duration <= 0:
            raw_duration = self._duration_seconds(track.get("duration"))
            duration = raw_duration / 1000.0 if raw_duration > 10000 else raw_duration
        return {
            "url": self._soundcloud_track_url(track),
            "title": title,
            "artist": artist,
            "source": "soundcloud",
            "requester": requester,
            "duration_seconds": duration,
            "thumbnail": str(track.get("artwork_url") or track.get("thumbnail") or ""),
            "art_url": str(track.get("artwork_url") or track.get("thumbnail") or ""),
            "pause_qt": False,
            "volume": self.bot._voice_volume_override if self.bot._voice_volume_override is not None else self.bot._runtime_volume(),
        }

    def _payload_label(self, payload: dict) -> str:
        title = str(payload.get("title") or payload.get("name") or "Unknown").strip()
        artist = str(payload.get("artist") or payload.get("channel") or "Unknown").strip()
        return f"{title} - {artist}"

    def _cast_ack_text(self, payload: dict) -> str:
        lines = [f"Queued: {self._payload_label(payload)}"]
        source = str(payload.get("source") or "cast").strip().upper()
        if source:
            lines.append(f"Service: {source}")
        requester = str(payload.get("requester") or "").strip()
        if requester:
            lines.append(f"Requested by: {requester}")
        url = str(payload.get("url") or payload.get("web_url") or payload.get("permalink_url") or "").strip()
        if url:
            lines.append(f"Link: {url}")
        return "\n".join(lines)

    def _format_seconds(self, seconds: float) -> str:
        seconds = max(0, int(round(float(seconds or 0.0))))
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    async def _search_soundcloud(self, query: str, *, limit: int = 6) -> list[dict]:
        query = str(query or "").strip()
        if not query:
            return []

        def _run() -> list[dict]:
            api = SoundCloudAPI()
            if not api.ready:
                api.refresh_client_id()
            if not api.ready:
                return []
            return [item for item in (api.search(query, limit=limit) or []) if isinstance(item, dict)]

        return await asyncio.to_thread(_run)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        payload = self.bot.current_cast_payload or {}
        if payload:
            await ctx.reply(embed=self.cast_embed(), view=CastControlView(self.bot), mention_author=False)
            return
        await self._send(ctx, "NOW PLAYING", "Nothing is casting to Discord right now.")

    @commands.command(name="qtnowplaying", aliases=["qtnp"])
    async def qt_nowplaying(self, ctx: commands.Context):
        await self._send(ctx, "QT NOW PLAYING", self.bot.bridge.now_playing_text())

    @commands.command(name="queue")
    async def queue(self, ctx: commands.Context):
        await self._send(ctx, "CAST QUEUE", self.cast_queue_text())

    @commands.command(name="qtqueue")
    async def qt_queue(self, ctx: commands.Context):
        lines = self.bot.bridge.queue_lines()
        await self._send(ctx, "QT QUEUE", "\n".join(lines))

    @commands.command(name="castqueue", aliases=["cq", "voicequeue"])
    async def cast_queue(self, ctx: commands.Context):
        await self._send(ctx, "CAST QUEUE", self.cast_queue_text())

    @commands.command(name="castnow", aliases=["playcast"])
    async def cast_queue_position(self, ctx: commands.Context, position: int):
        if not self.bot.cast_queue:
            await self._send(ctx, "CAST QUEUE", "Discord cast queue is empty.")
            return
        index = max(0, min(len(self.bot.cast_queue) - 1, int(position) - 1))
        self.bot.cast_index = index
        await self.cast_payload_to_voice(dict(self.bot.cast_queue[index]), add_to_queue=False)
        await self.post_or_update_cast_embed(channel=ctx.channel)
        await self._send(ctx, "CAST QUEUE", f"Playing cast queue #{index + 1}.")

    @commands.command(name="clearcast", aliases=["clearcq"])
    async def clear_cast_queue(self, ctx: commands.Context):
        async with self._cast_lock:
            voice = ctx.guild.voice_client if ctx.guild is not None else None
            if voice is not None and voice.is_connected() and (voice.is_playing() or voice.is_paused()):
                self.bot._invalidate_voice_callbacks()
                voice.stop()
            self.bot.cast_queue.clear()
            self.bot.cast_index = -1
            self.bot.current_cast_payload = None
            self.bot.current_cast_input = ""
            self.bot._voice_source = None
            self.bot.cast_started_at = 0.0
            self.bot.cast_seek_seconds = 0.0
            self.bot.cast_duration_seconds = 0.0
            self.bot.cast_paused = False
            self.bot.last_cast_status = "cast queue cleared"
            self.bot._write_discord_status()
        await self.post_or_update_cast_embed(channel=ctx.channel)
        await self._send(ctx, "CAST QUEUE", "Discord cast queue cleared.")

    @commands.command(name="songs", aliases=["allsongs", "librarysongs"])
    async def songs(self, ctx: commands.Context, page: int = 1):
        lines, _page, page_count = self.bot.bridge.library_song_pages(page=page)
        text = "\n".join(lines)
        if len(text) <= 1900:
            await self._send(ctx, "LIBRARY SONGS", text)
            return
        await self._send(ctx, "LIBRARY SONGS", "\n".join(lines[:12]) + f"\nUse !songs 2 through !songs {page_count} for more.")

    @commands.command(name="commands", aliases=["cmds", "commandlist", "allcommands", "menu"])
    async def command_list(self, ctx: commands.Context):
        await self._send_commands_embed(ctx)

    @commands.command(name="vcdiag")
    async def voice_diagnostics(self, ctx: commands.Context):
        await self._send(ctx, "VOICE DIAGNOSTICS", self.bot.voice_diag)

    @commands.command(name="rtdiag")
    async def runtime_diagnostics(self, ctx: commands.Context):
        await self._send(ctx, "RUNTIME DIAGNOSTICS", self.bot.bridge.runtime_diagnostics_text())

    @commands.command(name="castdiag")
    async def cast_diagnostics(self, ctx: commands.Context):
        await self._send(ctx, "CAST DIAGNOSTICS", self.bot.last_cast_status)

    @commands.command(name="castpanel", aliases=["panel", "nowpanel"])
    async def cast_panel(self, ctx: commands.Context):
        self.bot.cast_text_channel_id = int(ctx.channel.id)
        self.bot._save_discord_panel_state()
        await self.post_or_update_cast_embed(channel=ctx.channel)
        await self._send(ctx, "CAST PANEL", "Discord cast panel updated.")

    @commands.command(name="pause", aliases=["toggle", "playpause"])
    async def playpause(self, ctx: commands.Context):
        await self.toggle_voice_playback()
        await self.post_or_update_cast_embed(channel=ctx.channel)
        await self._send(ctx, "CAST CONTROL", "Discord voice play/pause queued.")

    @commands.command(name="qtplaypause", aliases=["qtpause", "qttoggle"])
    async def qt_playpause(self, ctx: commands.Context):
        result = self.bot.bridge.toggle_play()
        await self._send(ctx, "QT CONTROL", result.message)

    @commands.command(name="play")
    async def play_link(self, ctx: commands.Context, *, query: str = ""):
        query = str(query or "").strip().strip("<>")
        if not query:
            await self._send(ctx, "PLAY", "Use `!play <SoundCloud search or direct link>`. Instagram/YouTube/TikTok-style links are best-effort and only work when yt-dlp can extract playable media.")
            return
        requester = str(ctx.author.display_name if hasattr(ctx.author, "display_name") else ctx.author)
        if query.lower().startswith(("http://", "https://")):
            await ctx.typing()
            payload = await asyncio.to_thread(self._direct_link_payload, query, requester=requester)
        else:
            await ctx.typing()
            matches = await self._search_soundcloud(query, limit=5)
            if not matches:
                await self._send(ctx, "SOUNDCLOUD", f"No SoundCloud results found for `{query}`.", color=0xFFCC66)
                return
            payload = self._soundcloud_payload(matches[0], requester=requester)
            if not payload.get("url"):
                await self._send(ctx, "SOUNDCLOUD", f"Found a SoundCloud result for `{query}`, but it had no playable URL.", color=0xFFCC66)
                return
        await self.cast_payload_to_voice(payload, add_to_queue=True)
        await self.post_or_update_cast_embed(channel=ctx.channel)
        await self._send(ctx, "CAST", self._cast_ack_text(payload))

    @commands.command(name="convert")
    async def convert(self, ctx: commands.Context, *, query: str = ""):
        query = str(query or "").strip().strip("<>")
        source_spec: dict | None = None
        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]
            saved_path, detail = await self._save_attachment_to_temp(attachment)
            if not saved_path:
                await self._send(ctx, "CONVERT", f"Could not save the attachment: {detail}", color=0xFF5555)
                return
            source_spec = {
                "kind": "attachment",
                "path": saved_path,
                "label": str(attachment.filename or "uploaded file"),
            }
        elif query:
            source_spec = {
                "kind": "link",
                "url": query,
                "label": query,
            }
        if source_spec is None:
            await self._send(
                ctx,
                "CONVERT",
                "Start with `!convert <link>` or upload a file and run `!convert`, then choose the output format from the buttons.",
                color=0xFFCC66,
            )
            return
        label = str(source_spec.get("label") or "source")
        embed = discord.Embed(
            title="CONVERT // CHOOSE OUTPUT",
            description=f"Input locked: `{label}`\nChoose the output format below.",
            color=0xEDEDED,
        )
        embed.add_field(name="Step 1", value="Provide a direct link or upload a file with `!convert`.", inline=False)
        embed.add_field(name="Step 2", value="Press `MP3`, `M4A`, `FLAC`, or `WAV` to start conversion.", inline=False)
        embed.set_footer(text="H-I-N TECH // HOOD BOT")
        await ctx.reply(embed=embed, view=ConvertFormatView(self, source_spec=source_spec, requester_id=int(ctx.author.id)), mention_author=False)

    @commands.command(name="purge", aliases=["clear", "clean"])
    async def purge_messages(self, ctx: commands.Context, count: int = 0):
        if not await self._require_guild_permissions(ctx, manage_messages=True):
            return
        bounded = max(1, min(100, int(count or 0)))
        if bounded <= 0:
            await self._send(ctx, "MODERATION", "Use `!purge <1-100>` to remove recent messages.", color=0xFFCC66)
            return
        try:
            deleted = await ctx.channel.purge(limit=bounded + 1, reason=self._member_action_reason(ctx, "purge"))
        except Exception as exc:
            await self._send(ctx, "MODERATION", f"Purge failed: {type(exc).__name__}: {exc}", color=0xFF5555)
            return
        await self._send(ctx, "MODERATION", f"Removed {max(0, len(deleted) - 1)} message(s) from this channel.")

    @commands.command(name="kick")
    async def kick_member(self, ctx: commands.Context, member: discord.Member, *, reason: str = ""):
        if not await self._require_guild_permissions(ctx, kick_members=True):
            return
        if not await self._ensure_actionable_member(ctx, member):
            return
        try:
            await member.kick(reason=self._member_action_reason(ctx, "kick", reason))
        except Exception as exc:
            await self._send(ctx, "MODERATION", f"Kick failed: {type(exc).__name__}: {exc}", color=0xFF5555)
            return
        await self._send(ctx, "MODERATION", f"Kicked `{member}`." + (f" Reason: {reason}" if reason else ""))

    @commands.command(name="ban")
    async def ban_member(self, ctx: commands.Context, member: discord.Member, *, reason: str = ""):
        if not await self._require_guild_permissions(ctx, ban_members=True):
            return
        if not await self._ensure_actionable_member(ctx, member):
            return
        try:
            await member.ban(reason=self._member_action_reason(ctx, "ban", reason), delete_message_seconds=0)
        except Exception as exc:
            await self._send(ctx, "MODERATION", f"Ban failed: {type(exc).__name__}: {exc}", color=0xFF5555)
            return
        await self._send(ctx, "MODERATION", f"Banned `{member}`." + (f" Reason: {reason}" if reason else ""))

    @commands.command(name="unban")
    async def unban_member(self, ctx: commands.Context, user_id: str, *, reason: str = ""):
        if not await self._require_guild_permissions(ctx, ban_members=True):
            return
        if ctx.guild is None:
            return
        try:
            banned_user = await self.bot.fetch_user(int(str(user_id).strip()))
        except Exception:
            await self._send(ctx, "MODERATION", "Use `!unban <user_id>` with the banned user's numeric Discord ID.", color=0xFFCC66)
            return
        try:
            await ctx.guild.unban(banned_user, reason=self._member_action_reason(ctx, "unban", reason))
        except Exception as exc:
            await self._send(ctx, "MODERATION", f"Unban failed: {type(exc).__name__}: {exc}", color=0xFF5555)
            return
        await self._send(ctx, "MODERATION", f"Unbanned `{banned_user}`." + (f" Reason: {reason}" if reason else ""))

    @commands.command(name="timeout", aliases=["mute"])
    async def timeout_member(self, ctx: commands.Context, member: discord.Member, minutes: int = 0, *, reason: str = ""):
        if not await self._require_guild_permissions(ctx, moderate_members=True):
            return
        if not await self._ensure_actionable_member(ctx, member):
            return
        bounded = max(1, min(40320, int(minutes or 0)))
        if bounded <= 0:
            await self._send(ctx, "MODERATION", "Use `!timeout @user <minutes> [reason]`.", color=0xFFCC66)
            return
        try:
            until = discord.utils.utcnow() + datetime.timedelta(minutes=bounded)
            await member.edit(timed_out_until=until, reason=self._member_action_reason(ctx, "timeout", reason))
        except Exception as exc:
            await self._send(ctx, "MODERATION", f"Timeout failed: {type(exc).__name__}: {exc}", color=0xFF5555)
            return
        await self._send(ctx, "MODERATION", f"Timed out `{member}` for {bounded} minute(s)." + (f" Reason: {reason}" if reason else ""))

    @commands.command(name="untimeout", aliases=["unmute"])
    async def untimeout_member(self, ctx: commands.Context, member: discord.Member, *, reason: str = ""):
        if not await self._require_guild_permissions(ctx, moderate_members=True):
            return
        if not await self._ensure_actionable_member(ctx, member):
            return
        try:
            await member.edit(timed_out_until=None, reason=self._member_action_reason(ctx, "untimeout", reason))
        except Exception as exc:
            await self._send(ctx, "MODERATION", f"Timeout removal failed: {type(exc).__name__}: {exc}", color=0xFF5555)
            return
        await self._send(ctx, "MODERATION", f"Removed timeout from `{member}`." + (f" Reason: {reason}" if reason else ""))

    @commands.command(name="8ball", aliases=["eightball"])
    async def eight_ball(self, ctx: commands.Context, *, question: str = ""):
        if not str(question or "").strip():
            await self._send(ctx, "8BALL", "Ask a full question, like `!8ball should we run it back?`", color=0xFFCC66)
            return
        answer = random.choice(
            [
                "Yes. Lock it in.",
                "No chance.",
                "Most likely.",
                "Absolutely not.",
                "Reply hazy, run it again.",
                "Signs point to yes.",
                "That sounds dangerous... but maybe.",
                "The vibes are terrible.",
                "Green light.",
                "Save yourself and don't do it.",
            ]
        )
        await self._send(ctx, "8BALL", f"Question: {question}\nAnswer: {answer}")

    @commands.command(name="coinflip", aliases=["flip", "coin"])
    async def coinflip(self, ctx: commands.Context):
        await self._send(ctx, "COINFLIP", f"Result: **{random.choice(['Heads', 'Tails'])}**")

    @commands.command(name="roll", aliases=["dice"])
    async def roll(self, ctx: commands.Context, sides: int = 6):
        bounded = max(2, min(1000, int(sides or 6)))
        value = random.randint(1, bounded)
        await self._send(ctx, "ROLL", f"Rolled a **{value}** on a **d{bounded}**.")

    @commands.command(name="choose")
    async def choose(self, ctx: commands.Context, *, options: str = ""):
        raw = [item.strip() for item in str(options or "").split("|") if item.strip()]
        if len(raw) < 2:
            await self._send(ctx, "CHOOSE", "Use `!choose option one | option two | option three`.", color=0xFFCC66)
            return
        pick = random.choice(raw)
        await self._send(ctx, "CHOOSE", f"I pick: **{pick}**")

    @commands.command(name="rate")
    async def rate(self, ctx: commands.Context, *, thing: str = ""):
        item = str(thing or "").strip()
        if not item:
            await self._send(ctx, "RATE", "Use `!rate <anything>`.", color=0xFFCC66)
            return
        score = random.randint(1, 100)
        tier = "legendary" if score >= 90 else "solid" if score >= 70 else "mid" if score >= 40 else "criminal"
        await self._send(ctx, "RATE", f"`{item}` gets **{score}/100** // {tier}")

    @commands.command(name="ship")
    async def ship(self, ctx: commands.Context, first: str = "", second: str = ""):
        left = str(first or "").strip()
        right = str(second or "").strip()
        if not left or not right:
            await self._send(ctx, "SHIP", "Use `!ship name1 name2`.", color=0xFFCC66)
            return
        score = random.randint(1, 100)
        if score >= 85:
            verdict = "unreal chemistry"
        elif score >= 60:
            verdict = "surprisingly valid"
        elif score >= 35:
            verdict = "chaotic but possible"
        else:
            verdict = "doomed from the start"
        await self._send(ctx, "SHIP", f"**{left} + {right}** = **{score}%** // {verdict}")

    @commands.command(name="mood")
    async def mood(self, ctx: commands.Context):
        await self._send(
            ctx,
            "MOOD",
            random.choice(
                [
                    "Server mood: locked in.",
                    "Server mood: one bug away from chaos.",
                    "Server mood: immaculate vibes.",
                    "Server mood: sleepy but dangerous.",
                    "Server mood: somebody is about to start something.",
                ]
            ),
        )

    @commands.command(name="roast")
    async def roast(self, ctx: commands.Context, target: str = ""):
        name = str(target or getattr(getattr(ctx, 'author', None), 'display_name', None) or "you").strip()
        line = random.choice(
            [
                "built like a bug report with no repro steps",
                "moving like 2% battery and bad Wi-Fi",
                "acting like the patch was tested when it definitely was not",
                "out here buffering in real life",
                "running on vibes and expired drivers",
            ]
        )
        await self._send(ctx, "ROAST", f"{name} is {line}.")

    @commands.command(name="compliment", aliases=["praise"])
    async def compliment(self, ctx: commands.Context, target: str = ""):
        name = str(target or getattr(getattr(ctx, 'author', None), 'display_name', None) or "you").strip()
        line = random.choice(
            [
                "is carrying the timeline right now.",
                "has top-tier taste and elite timing.",
                "is the kind of person you want on the aux and in the group project.",
                "just has main-character confidence.",
                "is suspiciously good at this.",
            ]
        )
        await self._send(ctx, "COMPLIMENT", f"{name} {line}")

    @commands.command(name="scsearch", aliases=["soundcloud", "sc"])
    async def soundcloud_search(self, ctx: commands.Context, *, query: str = ""):
        query = str(query or "").strip()
        if not query:
            await self._send(ctx, "SOUNDCLOUD SEARCH", "Use `!scsearch <search words>`.")
            return
        await ctx.typing()
        matches = await self._search_soundcloud(query, limit=8)
        if not matches:
            await self._send(ctx, "SOUNDCLOUD SEARCH", f"No SoundCloud results found for `{query}`.", color=0xFFCC66)
            return
        lines = [f"SOUNDCLOUD MATCHES // {query}"]
        for index, item in enumerate(matches[:8], start=1):
            payload = self._soundcloud_payload(item)
            duration = self._format_seconds(float(payload.get("duration_seconds") or 0.0)) if payload.get("duration_seconds") else "--:--"
            lines.append(f"{index}. {payload['title']} - {payload['artist']} [{duration}]")
        lines.append("Use `!play <search words>` to play the top match.")
        await self._send(ctx, "SOUNDCLOUD MATCHES", "\n".join(lines))

    @commands.command(name="next")
    async def next_track(self, ctx: commands.Context):
        await self.play_cast_queue_offset(1)
        await self.post_or_update_cast_embed(channel=ctx.channel)
        await self._send(ctx, "CAST NEXT", self.bot.last_cast_status)

    @commands.command(name="qtnext")
    async def qt_next_track(self, ctx: commands.Context):
        result = self.bot.bridge.next_track()
        await self._send(ctx, "QT NEXT", result.message)

    @commands.command(name="skip")
    async def skip_voice_track(self, ctx: commands.Context):
        async with self._cast_lock:
            voice = ctx.guild.voice_client if ctx.guild is not None else None
            if voice is None or not voice.is_connected():
                await self._send(ctx, "VOICE", "I am not connected to voice.", color=0xFFCC66)
                return
            if voice.is_playing() or voice.is_paused():
                self.bot.cast_seek_seconds = self.bot._current_cast_position()
                self.bot.cast_started_at = 0.0
                self.bot.cast_paused = False
                self.bot._invalidate_voice_callbacks()
                voice.stop()
                self.bot._voice_source = None
                if self.bot.cast_queue and self.bot.cast_index + 1 < len(self.bot.cast_queue):
                    self.bot.cast_index += 1
                    await self._cast_payload_to_voice_locked(dict(self.bot.cast_queue[self.bot.cast_index]), add_to_queue=False)
                else:
                    self.bot._write_discord_status()
                await self.post_or_update_cast_embed(channel=ctx.channel)
                await self._send(ctx, "CAST SKIP", self.bot.last_cast_status)
                return
        await self._send(ctx, "CAST SKIP", "Nothing is playing in Discord voice.")

    @commands.command(name="prev", aliases=["previous"])
    async def previous_track(self, ctx: commands.Context):
        await self.play_cast_queue_offset(-1)
        await self.post_or_update_cast_embed(channel=ctx.channel)
        await self._send(ctx, "CAST PREVIOUS", self.bot.last_cast_status)

    @commands.command(name="qtprev", aliases=["qtprevious"])
    async def qt_previous_track(self, ctx: commands.Context):
        result = self.bot.bridge.previous_track()
        await self._send(ctx, "QT PREVIOUS", result.message)

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, percent: int):
        bounded = max(0, min(100, int(percent)))
        self.bot._set_voice_volume_from_payload({"volume": bounded / 100.0})
        await self.post_or_update_cast_embed(channel=ctx.channel)
        await self._send(ctx, "CAST VOLUME", f"Discord voice volume set: {bounded}%")

    @commands.command(name="qtvolume", aliases=["qtvol"])
    async def qt_volume(self, ctx: commands.Context, percent: int):
        result = self.bot.bridge.set_volume_percent(percent)
        self.bot._set_voice_volume_from_payload({"volume": max(0.0, min(1.0, int(percent) / 100.0))})
        await self._send(ctx, "QT VOLUME", result.message)

    @commands.command(name="qtplayq")
    async def play_queue_position(self, ctx: commands.Context, position: int):
        result = self.bot.bridge.play_queue_position(position - 1)
        await self._send(ctx, "QT QUEUE", result.message)

    @commands.command(name="join")
    async def join_voice(self, ctx: commands.Context):
        self.bot.cast_text_channel_id = int(ctx.channel.id)
        self.bot._save_discord_panel_state()
        voice = await self._ensure_voice(ctx)
        if voice is None:
            return
        await self.post_or_update_cast_embed(channel=ctx.channel)
        await self._send(ctx, "VOICE CONNECTED", f"Joined {voice.channel.name}.")

    @commands.command(name="leave")
    async def leave_voice(self, ctx: commands.Context):
        voice = ctx.guild.voice_client if ctx.guild is not None else None
        if voice is None:
            await self._send(ctx, "VOICE", "I am not in a voice channel.", color=0xFFCC66)
            self.bot._write_discord_status()
            return
        try:
            if voice.is_playing() or voice.is_paused():
                voice.stop()
            self.bot._voice_source = None
            self.bot.cast_paused = False
            self.bot.cast_started_at = 0.0
            await voice.disconnect()
        except Exception as exc:
            await self._send(ctx, "VOICE ERROR", self._voice_error_text("Could not disconnect from voice", exc), color=0xFF5555)
            self.bot._write_discord_status()
            return
        self.bot.last_cast_status = "disconnected"
        self.bot._write_discord_status()
        await self._send(ctx, "VOICE DISCONNECTED", "Disconnected from voice.")

    @commands.command(name="vstop")
    async def stop_voice_playback(self, ctx: commands.Context):
        async with self._cast_lock:
            voice = ctx.guild.voice_client if ctx.guild is not None else None
            if voice is None or not voice.is_connected():
                await self._send(ctx, "VOICE", "I am not connected to voice.", color=0xFFCC66)
                return
            if voice.is_playing() or voice.is_paused():
                self.bot.cast_seek_seconds = self.bot._current_cast_position()
                self.bot.cast_started_at = 0.0
                self.bot.cast_paused = False
                self.bot._invalidate_voice_callbacks()
                voice.stop()
                self.bot._voice_source = None
                self.bot._write_discord_status()
                await self.post_or_update_cast_embed(channel=ctx.channel)
                await self._send(ctx, "CAST STOP", "Stopped voice playback.")
                return
        await self._send(ctx, "CAST STOP", "Nothing is playing in voice.")

    @commands.command(name="removeSong", aliases=["remove_song"])
    async def remove_current_voice_song(self, ctx: commands.Context):
        async with self._cast_lock:
            voice = ctx.guild.voice_client if ctx.guild is not None else None
            if voice is None or not voice.is_connected():
                await self._send(ctx, "VOICE", "I am not connected to voice.", color=0xFFCC66)
                return
            if voice.is_playing() or voice.is_paused():
                current_key = self._payload_key(self.bot.current_cast_payload or {})
                if current_key:
                    self.bot.cast_queue = [item for item in self.bot.cast_queue if self._payload_key(item) != current_key]
                    self.bot.cast_index = min(self.bot.cast_index, len(self.bot.cast_queue) - 1)
                self.bot.cast_seek_seconds = self.bot._current_cast_position()
                self.bot.cast_started_at = 0.0
                self.bot.cast_paused = False
                self.bot._invalidate_voice_callbacks()
                voice.stop()
                self.bot._voice_source = None
                self.bot.current_cast_payload = None
                self.bot._write_discord_status()
                await self.post_or_update_cast_embed(channel=ctx.channel)
                await self._send(ctx, "CAST REMOVE", "Removed current Discord voice song.")
                return
        await self._send(ctx, "CAST REMOVE", "No Discord voice song is currently playing.")

    @commands.command(name="vplay")
    async def voice_play_current(self, ctx: commands.Context):
        await self._voice_play_current(ctx, pause_qt_local=False)

    @commands.command(name="vcast", aliases=["cast", "vplayquiet"])
    async def voice_cast_current(self, ctx: commands.Context):
        await self._voice_play_current(ctx, pause_qt_local=True)

    @commands.command(name="vunmute", aliases=["vresume"])
    async def voice_resume_qt_local(self, ctx: commands.Context):
        result = self.bot.bridge.resume_qt_local_after_cast()
        await self._send(ctx, "QT LOCAL AUDIO", result.message)

    async def _voice_play_current(self, ctx: commands.Context, *, pause_qt_local: bool):
        if not self.bot.ffmpeg_path:
            await self._send(ctx, "VOICE ERROR", "FFmpeg is required for voice playback. Install FFmpeg and add it to PATH.", color=0xFF5555)
            return
        voice = await self._ensure_voice(ctx)
        if voice is None:
            return
        source_path = self.bot.bridge.current_track_local_path()
        if source_path is None:
            await self._send(
                ctx,
                "VOICE PLAYBACK",
                "No playable local runtime track found. Start playback in H-I-N TECH with a local file first. "
                f"[{self.bot.bridge.runtime_diagnostics_text()}]",
                color=0xFFCC66,
            )
            return
        if voice.is_playing() or voice.is_paused():
            self.bot._invalidate_voice_callbacks()
            voice.stop()
        try:
            token = self.bot._next_voice_generation()
            audio = self._voice_audio(str(source_path))
            self.bot._voice_source = audio
            self.bot.current_cast_payload = {
                "path": str(source_path),
                "title": self.bot.bridge.current_track_label(),
                "artist": "H-I-N TECH",
                "source": "local",
                "pause_qt": pause_qt_local,
                "volume": self.bot._voice_volume_override if self.bot._voice_volume_override is not None else self.bot._runtime_volume(),
            }
            self.bot.current_cast_input = str(source_path)
            self.bot.cast_duration_seconds = 0.0
            self.bot.cast_seek_seconds = 0.0
            self.bot.cast_started_at = time.time()
            self.bot.cast_paused = False
            voice.play(audio, after=lambda error, token=token: self._after_voice_playback(error, token))
        except Exception as exc:
            await self._send(ctx, "VOICE ERROR", self._voice_error_text("Could not start voice playback", exc), color=0xFF5555)
            self.bot._write_discord_status()
            return
        suffix = ""
        if pause_qt_local:
            pause_result = self.bot.bridge.pause_qt_local_for_cast()
            suffix = f" [{pause_result.message}]"
        self.bot.last_cast_status = f"streaming runtime track: {self.bot.bridge.current_track_label()}"
        self.bot._write_discord_status()
        await self._send(ctx, "VOICE STREAMING", f"Streaming to voice: {self.bot.bridge.current_track_label()}{suffix}")


async def _main_async() -> None:
    is_cloud = cloud_mode()
    token = token_for_mode(is_cloud=is_cloud)
    if not token:
        if is_cloud:
            raise SystemExit(f"Set {DISCORD_TOKEN_ENV} in the hosting provider environment.")
        raise SystemExit(f"Set {DISCORD_TOKEN_ENV}, or create {DISCORD_TOKEN_FILE_NAME} in the OTERNOS folder.")
    lock = None if is_cloud or env_truthy(DISCORD_DISABLE_LOCAL_LOCK_ENV) else single_instance_lock()
    bot = HinTechDiscordBot()
    try:
        async with bot:
            await bot.start(token)
    finally:
        if lock is not None:
            lock.close()


def main() -> int:
    try:
        asyncio.run(_main_async())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
