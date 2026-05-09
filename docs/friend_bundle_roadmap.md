# Friend Bundle Roadmap

The goal is a friend-safe OTERNOS build where the desktop app installs cleanly and the Discord bot can run full-time from a host instead of someone's command prompt.

## Point 1 - Hosted Bot Package

Done in this pass:

- `Dockerfile.discord`
- `requirements-discord-bot.txt`
- `railway.json`
- `--cloud` bot startup mode
- token-file exclusion from Docker builds

This lets HOOD BOT run on Railway, Fly.io, or any Docker host.

## Point 2 - Desktop Bundle Hygiene

Next target:

- keep `build_qt.bat fast` as the normal developer rebuild
- keep `build_qt.bat clean` only for stale/broken exe cases
- make sure PyInstaller includes required data files for Spotify/spotDL/ytmusic/pykakasi
- stop the app before replacing `dist\oternos_qt` so Windows does not lock `.pyd` files
- add a single "known good" smoke test before zipping the app

## Point 3 - First-Run Setup

Next target:

- first-run screen for app settings
- Spotify auth status and reconnect button
- Discord bot status with "hosted bot" vs "local bot" explanation
- friendly errors when a service cannot legally stream or download a track
- config files stored per-user instead of inside the app folder

## Point 4 - Friend Release Pack

Next target:

- zipped portable build or installer
- bundled FFmpeg
- bundled app icon/taskbar assets
- no personal token files or `.env` files
- a short `README_FIRST.txt` explaining how friends launch the app and connect services
