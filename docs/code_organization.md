# OTERNOS Code Organization Map

This is the working map for keeping the app from turning into one giant file again.

## Current Boundaries

- `oternos/ui_qt/` owns the Qt desktop shell and visual UI.
- `oternos/core/` owns UI-independent state, queues, library data, runtime snapshots, and bridge commands.
- `oternos/discord_bot.py` owns Discord commands, voice playback, queue control, and message/embed behavior.
- `oternos/discord_config.py` owns Discord startup settings, token lookup, cloud mode, and local single-instance locking.
- `oternos/discord_embeds.py` owns Discord embed formatting, command help UI, and help dropdown views.
- `oternos/discord_bridge.py` owns communication from Discord to the desktop runtime bridge.
- `oternos/soundcloud_client.py` owns lightweight SoundCloud lookup code that can run without importing desktop UI modules.
- `oternos/streaming.py` still owns the larger app-side streaming clients and Spotify/SoundCloud/YouTube service code.

## Refactor Rule

When a file grows because of a new feature, split by responsibility instead of by vibes:

- startup/config goes into a config module
- API clients go into service/client modules
- pure data and persistence go into `core`
- UI rendering stays in `ui_qt`
- Discord-only behavior stays in Discord modules
- shared behavior must not import Qt, Tkinter, or Discord unless that module is specifically for that integration

## Next Good Splits

- Move Discord source resolving and FFmpeg voice input helpers out of `discord_bot.py`.
- Move Discord conversion button flows out of `discord_bot.py`.
- Split `ui_qt/shell.py` into page modules once a page is stable enough to move without breaking navigation.
- Keep Spotify playlist import logic out of visual pages so it can be tested without opening the app.
