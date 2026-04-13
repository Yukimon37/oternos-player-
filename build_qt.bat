@echo off
setlocal

echo [OTERNOS-QT] Building separate Qt shell exe.
echo [OTERNOS-QT] This does not replace dist\void_player\void_player.exe.

echo [OTERNOS-QT] Cleaning Qt shell build artifacts...
if exist build\oternos_qt rmdir /s /q build\oternos_qt
if exist dist\oternos_qt  rmdir /s /q dist\oternos_qt

echo [OTERNOS-QT] Building Qt shell exe (output: warnings and errors only)...
py -3.12 -m PyInstaller ^
    --log-level WARN ^
    oternos_qt.spec

if errorlevel 1 (
    echo [OTERNOS-QT] BUILD FAILED - check output above.
    pause
    exit /b 1
)

echo [OTERNOS-QT] Cleaning Qt shell build folder...
if exist build\oternos_qt rmdir /s /q build\oternos_qt

echo.
echo [OTERNOS-QT] Done! Launch: dist\oternos_qt\oternos_qt.exe
echo [OTERNOS-QT] Keep void_player.exe open for playback control.
pause
