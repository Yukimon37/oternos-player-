@echo off
setlocal

echo [OTERNOS] Pulling latest from GitHub...
git pull

echo [OTERNOS] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo [OTERNOS] Cleaning PyInstaller temp extractions...
for /d %%i in ("%LOCALAPPDATA%\Temp\_MEI*") do rmdir /s /q "%%i" 2>nul

echo [OTERNOS] Building exe (output: warnings and errors only)...
py -3.12 -m PyInstaller ^
    --log-level WARN ^
    void_player.spec

if errorlevel 1 (
    echo [OTERNOS] BUILD FAILED — check output above.
    pause
    exit /b 1
)

echo [OTERNOS] Cleaning build folder...
if exist build rmdir /s /q build

echo.
echo [OTERNOS] Done^^! Launch: dist\void_player\void_player.exe
pause
