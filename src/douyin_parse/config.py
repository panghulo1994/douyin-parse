"""配置解析：CLI 参数 > 环境变量 > .env > 内置默认。"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

APP = "douyin-parse"

# 内置供应商：都走 OpenAI 兼容接口
PROVIDERS = {
    "deepseek": {
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "key_env": ("DEEPSEEK_API_KEY",),
    },
    "mimo": {
        "url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        "model": "mimo-v2.6-flash",
        "key_env": ("XIAOMI_MIMO_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
    },
}
AUTO_ORDER = ("mimo", "deepseek")


@dataclass
class Config:
    url: str = ""
    input_file: str = ""
    batch_file: str = ""
    output_base: str = ""
    profile_dir: str = ""
    ffmpeg: str = ""
    whisper_model: str = "small"
    transcribe_backend: str = "auto"
    force_video: bool = False
    disable_ocr: bool = False
    auto_number: bool = False
    browser_channel: str = ""
    headless: bool = False
    proxy: str = ""
    user_agent: str = ""
    ai_choice: str = "auto"
    ai_provider: str = ""
    ai_api_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_api_format: str = "openai"


def config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP


def cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / APP


def load_dotenv() -> None:
    """读 ./.env 与配置目录的 .env；不覆盖已存在的环境变量。"""
    for path in (Path.cwd() / ".env", config_dir() / ".env"):
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _windows_env(name: str) -> str:
    """读 Windows「用户环境变量」——他们的 key 通常只存在这里，不进进程环境。"""
    if os.name != "nt":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value).strip()
    except OSError:
        return ""


def read_setting(name: str) -> str:
    """进程环境变量优先，Windows 上再回落到用户环境变量。"""
    return (os.environ.get(name) or "").strip() or _windows_env(name)


def detect_browser_channel() -> str:
    """挑一个能用的浏览器：Chrome 优先，其次 Edge（Windows 自带），否则用 playwright 自带 chromium。"""
    if os.name != "nt":
        return ""
    candidates = [
        (Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe", "chrome"),
        (Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe", "chrome"),
        (Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe", "chrome"),
        (Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe", "msedge"),
        (Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe", "msedge"),
    ]
    for path, channel in candidates:
        if str(path).strip() and path.is_file():
            return channel
    return ""


def resolve_ffmpeg(explicit: str = "") -> str:
    """显式路径 → DOUYIN_FFMPEG → PATH → imageio-ffmpeg 兜底。"""
    for candidate in (explicit, os.environ.get("DOUYIN_FFMPEG", "")):
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


def resolve_ai(choice: str = "auto") -> dict:
    """解析 AI 配置；返回 provider/url/key/model/format。"""
    empty = {"provider": "", "url": "", "key": "", "model": "", "format": "openai"}
    if choice == "none":
        return empty

    url = read_setting("AI_API_URL")
    key = read_setting("AI_API_KEY")
    model = read_setting("AI_MODEL")
    fmt = read_setting("AI_API_FORMAT") or "openai"

    if key and url:
        return {"provider": "custom", "url": url, "key": key, "model": model or "deepseek-chat", "format": fmt}

    configured = read_setting("DOUYIN_AI_PROVIDER").lower()
    order = (choice,) if choice in PROVIDERS else AUTO_ORDER
    if configured in PROVIDERS and configured not in order:
        order = (configured,) + tuple(name for name in order if name != configured)

    for name in order:
        spec = PROVIDERS[name]
        found = next((v for v in (read_setting(e) for e in spec["key_env"]) if v), "")
        if not found:
            continue
        return {
            "provider": name,
            "url": url or spec["url"],
            "key": found,
            "model": model or spec["model"],
            "format": fmt,
        }
    return empty


def build(
    url: str = "",
    *,
    out: str | None = None,
    model: str | None = None,
    no_ocr: bool = False,
    force_video: bool = False,
    ai: str = "auto",
    auto_number: bool = False,
    profile_dir: str | None = None,
    batch_file: str = "",
    input_file: str = "",
    backend: str = "auto",
    browser_channel: str | None = None,
    headless: bool = False,
    proxy: str | None = None,
    user_agent: str | None = None,
) -> Config:
    load_dotenv()

    output = out or os.environ.get("DOUYIN_OUTPUT_BASE") or str(Path.cwd() / "output")
    profile = profile_dir or os.environ.get("DOUYIN_PROFILE_DIR") or str(cache_dir() / "browser")
    whisper = model or os.environ.get("DOUYIN_WHISPER_MODEL") or "small"
    ocr_off = no_ocr or os.environ.get("DISABLE_VIDEO_OCR") == "1"
    numbered = auto_number or os.environ.get("DOUYIN_AUTO_NUMBER") == "1"
    ai_cfg = resolve_ai(ai)
    backend_name = backend if backend not in (None, "", "auto") else (os.environ.get("DOUYIN_TRANSCRIBE_BACKEND") or "auto")

    channel = browser_channel
    if channel is None:
        channel = os.environ.get("DOUYIN_BROWSER_CHANNEL", "")
        # Windows 优先用系统 Chrome，没有就用 Edge；其他平台用 playwright 自带的 chromium
        if not channel:
            channel = detect_browser_channel()

    return Config(
        url=url,
        input_file=input_file,
        batch_file=batch_file,
        output_base=str(Path(output).expanduser().resolve()),
        profile_dir=str(Path(profile).expanduser()),
        ffmpeg=resolve_ffmpeg(),
        whisper_model=whisper,
        transcribe_backend=backend_name,
        force_video=force_video,
        disable_ocr=ocr_off,
        auto_number=numbered,
        browser_channel=channel,
        headless=headless,
        proxy=proxy if proxy is not None else os.environ.get("DOUYIN_PROXY", ""),
        user_agent=user_agent if user_agent is not None else os.environ.get("DOUYIN_USER_AGENT", ""),
        ai_choice=ai,
        ai_provider=ai_cfg["provider"],
        ai_api_url=ai_cfg["url"],
        ai_api_key=ai_cfg["key"],
        ai_model=ai_cfg["model"],
        ai_api_format=ai_cfg["format"],
    )
