# OTERNOS Discord Bot Hosting

This is the always-on path for HOOD BOT. The desktop app can still run locally, but the Discord bot no longer has to live in a command prompt on your PC.

## What Changed

- `python -m oternos --discord-bot --cloud` starts the bot in cloud mode.
- Cloud mode reads `HIN_TECH_DISCORD_BOT_TOKEN` from environment variables only.
- Cloud mode skips the local single-instance socket lock.
- The bot uses a lightweight SoundCloud client so the hosted process does not import the desktop UI stack.
- The Docker image installs FFmpeg so Discord voice playback can work.

## Required Secret

Set this in the host provider, never in chat and never in git:

```text
HIN_TECH_DISCORD_BOT_TOKEN=your_reset_bot_token_here
```

Optional:

```text
HIN_TECH_DISCORD_PREFIX=!
HIN_TECH_DISCORD_CLOUD=1
HIN_TECH_DISCORD_DISABLE_LOCAL_LOCK=1
```

## Railway Deploy

1. Push this repo to GitHub.
2. Create a new Railway project from the GitHub repo.
3. Railway should detect `railway.json` and use `Dockerfile.discord`.
4. Add `HIN_TECH_DISCORD_BOT_TOKEN` in Railway variables.
5. Deploy.
6. In Discord, test `!commands`, `!join`, and `!play <soundcloud search>`.

## Fly.io Deploy

Fly can use the same Dockerfile:

```powershell
fly launch --dockerfile Dockerfile.discord --name oternos-hood-bot
fly secrets set HIN_TECH_DISCORD_BOT_TOKEN="your_reset_bot_token_here"
fly deploy
```

## Local Cloud-Mode Test

This runs the same entrypoint the host will run:

```powershell
$env:HIN_TECH_DISCORD_BOT_TOKEN="your_reset_bot_token_here"
py -3.12 -m oternos --discord-bot --cloud
```

## Important Limits

- The hosted bot cannot directly read local files from your PC.
- Local Qt "cast this exact file" still needs the desktop bridge or a future pairing/upload flow.
- Discord `!play <link or search>` is the correct cloud-friendly route.
- Keep your token private. If it is pasted anywhere public or into chat, reset it in the Discord Developer Portal.
