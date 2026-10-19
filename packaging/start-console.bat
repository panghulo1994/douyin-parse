@echo off
REM Douyin parser - console launcher (pure ASCII on purpose)
chcp 65001 >nul
cd /d "%~dp0"
set "PATH=%~dp0runtime;%~dp0python;%~dp0python\Scripts;%PATH%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "USERPROFILE=%~dp0userdata"
set "LOCALAPPDATA=%~dp0userdata"
set "APPDATA=%~dp0userdata"
if not exist "%~dp0userdata" mkdir "%~dp0userdata"
if not exist "%~dp0python\python.exe" goto :nopython
"%~dp0python\python.exe" -u -m douyin_parse interactive
goto :end
:nopython
echo [ERROR] python runtime not found in "%~dp0python"
echo Please re-extract the whole package.
pause
:end
