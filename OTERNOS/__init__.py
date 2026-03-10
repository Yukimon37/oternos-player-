"""
OTERNOS PLAYER  v1.1
Cybercore Music Player — White Void Edition

Package structure:
  constants.py  — palette, fonts, globals, animation math
  animation.py  — ColorAnim, FadeOverlay
  audio.py      — AudioEngine, EQProcessor
  services.py   — GlobalHotkeys, LastFmScrobbler, DiscordRPC, FolderWatcher
  streaming.py  — SpotifyAuth, SpotifyAPI, SoundCloudAPI, YouTubeAPI
  widgets.py    — all custom tkinter canvas widgets + logos
  player.py     — VoidPlayer main application class
  boot.py       — TronBoot startup sequence
  __main__.py   — entry point  (python -m oternos)
"""

__version__ = "1.1"
__author__  = "OTERNOS"
