@echo off
setlocal

set "MODE=%~1"
set "BOT_MODE=%~2"
set "NO_PAUSE=%OTERNOS_NO_PAUSE%"
set "PYTHON_EXE=%OTERNOS_PYTHON%"
if "%PYTHON_EXE%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

echo [OTERNOS-QT] Building separate Qt shell exe.
echo [OTERNOS-QT] This does not replace dist\void_player\void_player.exe.
echo.
echo [OTERNOS-QT] Modes:
echo [OTERNOS-QT]   build_qt.bat           = fast incremental rebuild
echo [OTERNOS-QT]   build_qt.bat clean     = full clean rebuild
echo [OTERNOS-QT]   build_qt.bat fast nobot = incremental rebuild without bot restart
echo.

if /I "%MODE%"=="clean" (
    set "OTERNOS_QT_FAST_BUILD=0"
    echo [OTERNOS-QT] Full clean requested. Removing Qt shell artifacts...
    echo [OTERNOS-QT] Closing old Qt shell if it is still running...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process -Name oternos_qt -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>nul
    timeout /t 1 /nobreak >nul
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; foreach ($p in @('build\oternos_qt','dist\oternos_qt')) { if (Test-Path $p) { Remove-Item -LiteralPath $p -Recurse -Force } }"
    if errorlevel 1 (
        echo [OTERNOS-QT] Could not remove old build output. Close Explorer windows inside build\oternos_qt or dist\oternos_qt and retry.
        if not "%NO_PAUSE%"=="1" pause
        exit /b 1
    )
) else (
    set "OTERNOS_QT_FAST_BUILD=1"
    echo [OTERNOS-QT] Fast mode: keeping PyInstaller cache for quicker rebuilds.
    echo [OTERNOS-QT] Fast mode: skipping UPX compression.
    echo [OTERNOS-QT] Use build_qt.bat clean if the exe gets stale or broken.
)

echo [OTERNOS-QT] Closing old Qt shell if it is still running...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process -Name oternos_qt -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>nul
timeout /t 1 /nobreak >nul

echo [OTERNOS-QT] Building Qt shell exe (output: warnings and errors only)...
if not "%PYTHON_EXE%"=="" (
    "%PYTHON_EXE%" -m PyInstaller ^
        --noconfirm ^
        --log-level WARN ^
        oternos_qt.spec
) else (
    py -3.12 -m PyInstaller ^
        --noconfirm ^
        --log-level WARN ^
        oternos_qt.spec
)

if errorlevel 1 (
    echo [OTERNOS-QT] BUILD FAILED - check output above.
    echo [OTERNOS-QT] If this says Access Denied, close oternos_qt.exe and retry.
    echo [OTERNOS-QT] You can also run: taskkill /IM oternos_qt.exe /F
    if not "%NO_PAUSE%"=="1" pause
    exit /b 1
)

if /I "%MODE%"=="clean" (
    echo [OTERNOS-QT] Cleaning Qt shell build folder after full build...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path 'build\oternos_qt') { Remove-Item -LiteralPath 'build\oternos_qt' -Recurse -Force }" >nul 2>nul
)

if /I "%MODE%"=="nobot" set "BOT_MODE=nobot"
if /I "%BOT_MODE%"=="nobot" (
    echo [OTERNOS-QT] Skipping Discord bot companion restart.
) else (
    echo [OTERNOS-QT] Restarting Discord bot companion if configured...
    if exist "%~dp0discord_bot_token.txt" (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'oternos --discord-bot' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul
        if exist "%~dp0start_discord_bot_hidden.vbs" (
            cscript //nologo "%~dp0start_discord_bot_hidden.vbs" >nul 2>nul
            echo [OTERNOS-QT] Discord bot companion restarted hidden.
        ) else (
            echo [OTERNOS-QT] Hidden bot launcher missing; run start_discord_bot.bat manually.
        )
    ) else (
        echo [OTERNOS-QT] Discord token file missing; run start_discord_bot.bat once to set it up.
    )
)

echo.
echo [OTERNOS-QT] Done! Launch: dist\oternos_qt\oternos_qt.exe
echo [OTERNOS-QT] Keep void_player.exe open for playback control.
if not "%NO_PAUSE%"=="1" pause
