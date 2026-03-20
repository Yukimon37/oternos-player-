@echo off
echo [OTERNOS] Pulling latest from GitHub...
git pull

echo [OTERNOS] Building exe...
py -3.12 -m PyInstaller ^
    --onefile ^
    --console ^
    --name void_player ^
    --collect-all oternos ^
    --hidden-import pygame ^
    --hidden-import mutagen ^
    --hidden-import mutagen.mp3 ^
    --hidden-import mutagen.id3 ^
    --hidden-import mutagen.flac ^
    --hidden-import mutagen.oggvorbis ^
    --hidden-import mutagen.mp4 ^
    --hidden-import soundfile ^
    --add-data "boot.mp3;." ^
    --add-data "oternos;oternos" ^
    oternos\__main__.py

echo [OTERNOS] Done! Exe is in dist/void_player.exe
pause
