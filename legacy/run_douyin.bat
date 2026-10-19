@echo off
REM ==================================================================
REM  Douyin video parser - run_douyin.bat
REM
REM  IMPORTANT: this file must stay pure ASCII.
REM  cmd.exe reads .bat files with the OEM codepage (cp936 here), so any
REM  non-ASCII byte sequence - including Chinese folder names - corrupts
REM  line breaks and variables at parse time. Folder paths with Chinese
REM  characters are therefore resolved at runtime via %~dp0, never typed
REM  literally in this file.
REM
REM  Usage:
REM    run_douyin.bat "douyin_link"            parse one item
REM    run_douyin.bat "douyin_link" -v         force video mode
REM    run_douyin.bat --batch "links.txt"      batch mode
REM
REM  Optional env vars (set BEFORE running):
REM    DOUYIN_WHISPER_MODEL  small / medium / large-v3   (default large-v3)
REM    DOUYIN_AI_PROVIDER    mimo / deepseek
REM    DISABLE_VIDEO_OCR     1 = skip OCR
REM    DOUYIN_OUTPUT_BASE    output root folder (default: this folder)
REM ==================================================================
setlocal

set "SCRIPT_DIR=D:\ccgui"
set "PYFILE=%SCRIPT_DIR%\douyin_transcribe.py"
set "UV=C:\Users\Lenovo\.local\bin\uv.exe"

if not exist "%UV%" set "UV=uv"
if not defined DOUYIN_OUTPUT_BASE set "DOUYIN_OUTPUT_BASE=%~dp0"
if not defined DOUYIN_WHISPER_MODEL set "DOUYIN_WHISPER_MODEL=large-v3"

REM force UTF-8 for the redirected python log
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if not exist "%PYFILE%" goto :noscript

set "DEPS=--with playwright --with openai-whisper --with numpy --with scipy --with soundfile --with requests --with rapidocr-onnxruntime --with psutil --with sounddevice --with imageio_ffmpeg"

cd /d "%SCRIPT_DIR%"
if errorlevel 1 goto :noscript

if "%~1"=="" goto :usage

REM log folder name temp_logs matches the temp_* exclude pattern inside
REM auto_number_folders(), so it never gets a number prefix
set "LOG_DIR=%DOUYIN_OUTPUT_BASE%\temp_logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" 2>nul
set "TS=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TS=%TS: =0%"
set "LOG=%LOG_DIR%\run_%TS%.txt"

if /i "%~1"=="--batch" goto :batch
if /i "%~1"=="-b" goto :batch

set "EXTRA="
if /i "%~2"=="-v" set "EXTRA=--force-video"
if /i "%~2"=="--force-video" set "EXTRA=--force-video"

echo [parse] %~1
echo [whisper] %DOUYIN_WHISPER_MODEL%
echo [output] %DOUYIN_OUTPUT_BASE%
"%UV%" run %DEPS% python -u "%PYFILE%" "%~1" %EXTRA% > "%LOG%" 2>&1
goto :done

:batch
echo [batch] %~2
"%UV%" run %DEPS% python -u "%PYFILE%" --batch "%~2" > "%LOG%" 2>&1
goto :done

:noscript
echo [ERROR] main script not found: %PYFILE%
exit /b 1

:usage
chcp 65001 > nul
if exist "%~dp0run_douyin_help.txt" (
  type "%~dp0run_douyin_help.txt"
) else (
  echo Usage:
  echo   run_douyin.bat "douyin_link"
  echo   run_douyin.bat "douyin_link" -v
  echo   run_douyin.bat --batch "links.txt"
)
exit /b 1

:done
set "EXITCODE=%ERRORLEVEL%"
echo.
echo ===EXITCODE=%EXITCODE%===
echo [log] %LOG%
exit /b %EXITCODE%
