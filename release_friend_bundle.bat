@echo off
setlocal

set "VERSION=%~1"
set "MODE=%~2"
if "%VERSION%"=="" set "VERSION=dev"

set "ROOT=%~dp0"
set "APP_NAME=OTERNOS"
set "DIST_DIR=%ROOT%dist\oternos_qt"
set "RELEASE_ROOT=%ROOT%releases"
set "STAGE_DIR=%RELEASE_ROOT%\%APP_NAME%-win64"
set "ZIP_PATH=%RELEASE_ROOT%\%APP_NAME%-%VERSION%-win64-portable.zip"

echo [OTERNOS-RELEASE] Building friend bundle: %APP_NAME% %VERSION%
echo.

if /I "%MODE%"=="existing" (
    echo [OTERNOS-RELEASE] Existing mode: packaging current dist\oternos_qt without rebuilding.
) else (
    set "OTERNOS_NO_PAUSE=1"
    call "%ROOT%build_qt.bat" clean nobot
    if errorlevel 1 (
        echo [OTERNOS-RELEASE] Build failed. No release zip was created.
        echo [OTERNOS-RELEASE] After a successful manual build, you can run:
        echo [OTERNOS-RELEASE] release_friend_bundle.bat %VERSION% existing
        exit /b 1
    )
)

if not exist "%DIST_DIR%\oternos_qt.exe" (
    echo [OTERNOS-RELEASE] Missing built exe: %DIST_DIR%\oternos_qt.exe
    exit /b 1
)

echo [OTERNOS-RELEASE] Creating clean release folder...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$stage = '%STAGE_DIR%';" ^
  "$zip = '%ZIP_PATH%';" ^
  "if (Test-Path $stage) { Remove-Item -LiteralPath $stage -Recurse -Force };" ^
  "New-Item -ItemType Directory -Path $stage | Out-Null;" ^
  "Copy-Item -Path (Join-Path '%DIST_DIR%' '*') -Destination $stage -Recurse -Force;" ^
  "$logs = Join-Path $stage 'logs'; if (Test-Path $logs) { Remove-Item -LiteralPath $logs -Recurse -Force };" ^
  "$readme = @('OTERNOS - Windows portable build','','How to launch','1. Extract this zip first.','2. Open the OTERNOS-win64 folder.','3. Double-click START_OTERNOS.bat or oternos_qt.exe.','','Notes','- Windows may show a SmartScreen warning because this friend build is not code-signed yet.','- Keep the _internal folder beside oternos_qt.exe. The exe needs it.','- Your music library and settings are saved in your Windows user profile, not inside this folder.','- No Discord token is bundled. Hosted/local Discord setup is optional.');" ^
  "Set-Content -LiteralPath (Join-Path $stage 'README_FIRST.txt') -Value $readme -Encoding ASCII;" ^
  "$launcher = @('@echo off','cd /d ""%~dp0""','start """" ""oternos_qt.exe""');" ^
  "Set-Content -LiteralPath (Join-Path $stage 'START_OTERNOS.bat') -Value $launcher -Encoding ASCII;" ^
  "if (Test-Path $zip) { Remove-Item -LiteralPath $zip -Force };" ^
  "Compress-Archive -LiteralPath $stage -DestinationPath $zip -Force;"

if errorlevel 1 (
    echo [OTERNOS-RELEASE] Packaging failed.
    exit /b 1
)

echo.
echo [OTERNOS-RELEASE] Done.
echo [OTERNOS-RELEASE] Upload this file to GitHub Releases:
echo [OTERNOS-RELEASE] %ZIP_PATH%
echo.
echo [OTERNOS-RELEASE] Do not upload GitHub's automatic Source code zip as the app download.
