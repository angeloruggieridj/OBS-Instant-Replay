@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul
title OBS Instant Replay - Installation

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         OBS Instant Replay - Installation Script             ║
echo ║                     v1.0-beta5                               ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Step 1: Check FFmpeg
echo [1/3] Checking FFmpeg installation...
where ffmpeg >nul 2>&1
if %errorLevel% equ 0 (
    echo      [OK] FFmpeg found in PATH
    for /f "tokens=3" %%v in ('ffmpeg -version 2^>^&1 ^| findstr /r "^ffmpeg version"') do (
        echo      Version: %%v
    )
) else (
    echo      [!] FFmpeg not found in PATH
    echo.
    echo      FFmpeg is required for thumbnail generation.
    echo      Download from: https://www.gyan.dev/ffmpeg/builds/
    echo      Or use: winget install FFmpeg
    echo.
    echo      After installation, add to PATH: C:\ffmpeg\bin
    echo.
    set /p OPEN_PAGE="Open download page? (Y/N): "
    if /i "!OPEN_PAGE!"=="Y" (
        start https://www.gyan.dev/ffmpeg/builds/
    )
    echo.
)

:: Step 2: Determine OBS scripts directory
echo [2/3] Locating OBS Studio scripts directory...
set "OBS_SCRIPTS=%APPDATA%\obs-studio\scripts"

if exist "%OBS_SCRIPTS%" (
    echo      [OK] Found: %OBS_SCRIPTS%
) else (
    echo      [!] Directory not found. Creating...
    mkdir "%OBS_SCRIPTS%" 2>nul
    if exist "%OBS_SCRIPTS%" (
        echo      [OK] Created: %OBS_SCRIPTS%
    ) else (
        echo      [ERROR] Could not create scripts directory
        echo      Please create manually: %OBS_SCRIPTS%
        pause
        exit /b 1
    )
)

:: Step 3: Copy files
echo.
echo [3/3] Copying plugin files...
set "SCRIPT_DIR=%~dp0"

set "COPY_SUCCESS=1"

if exist "%SCRIPT_DIR%obs_replay_manager_browser.py" (
    copy /Y "%SCRIPT_DIR%obs_replay_manager_browser.py" "%OBS_SCRIPTS%\" >nul 2>&1
    if !errorLevel! equ 0 (
        echo      [OK] obs_replay_manager_browser.py
    ) else (
        echo      [ERROR] Failed to copy obs_replay_manager_browser.py
        set "COPY_SUCCESS=0"
    )
) else (
    echo      [ERROR] obs_replay_manager_browser.py not found in %SCRIPT_DIR%
    set "COPY_SUCCESS=0"
)

if exist "%SCRIPT_DIR%replay_http_server.py" (
    copy /Y "%SCRIPT_DIR%replay_http_server.py" "%OBS_SCRIPTS%\" >nul 2>&1
    if !errorLevel! equ 0 (
        echo      [OK] replay_http_server.py
    ) else (
        echo      [ERROR] Failed to copy replay_http_server.py
        set "COPY_SUCCESS=0"
    )
) else (
    echo      [ERROR] replay_http_server.py not found in %SCRIPT_DIR%
    set "COPY_SUCCESS=0"
)

:: Copy locales folder
if exist "%SCRIPT_DIR%locales" (
    if not exist "%OBS_SCRIPTS%\locales" mkdir "%OBS_SCRIPTS%\locales" >nul 2>&1
    xcopy /Y /Q "%SCRIPT_DIR%locales\*.json" "%OBS_SCRIPTS%\locales\" >nul 2>&1
    if !errorLevel! equ 0 (
        echo      [OK] locales folder (i18n translations)
    ) else (
        echo      [ERROR] Failed to copy locales folder
        set "COPY_SUCCESS=0"
    )
) else (
    echo      [!] locales folder not found (optional)
)

:: Done
echo.
if "%COPY_SUCCESS%"=="1" (
    echo ╔══════════════════════════════════════════════════════════════╗
    echo ║                   Installation Complete!                     ║
    echo ╚══════════════════════════════════════════════════════════════╝
) else (
    echo ╔══════════════════════════════════════════════════════════════╗
    echo ║             Installation completed with errors               ║
    echo ╚══════════════════════════════════════════════════════════════╝
)
echo.
echo Next steps:
echo   1. Open OBS Studio
echo   2. Go to Tools ^> Scripts
echo   3. Click '+' and select obs_replay_manager_browser.py
echo   4. Configure the replay folder in script settings
echo   5. Go to Docks ^> Custom Browser Docks
echo   6. Add: Name: "Replay Manager", URL: "http://localhost:8765"
echo.
echo Hotkeys can be configured in File ^> Settings ^> Hotkeys
echo Search for "Replay" to find available shortcuts.
echo.
pause
