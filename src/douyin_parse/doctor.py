"""环境自检：把「跑不起来」的原因一次说清楚。"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

from .config import cache_dir, resolve_ai, resolve_ffmpeg

OK = "OK  "
BAD = "FAIL"
WARN = "WARN"


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _chrome_path() -> str:
    if os.name == "nt":
        for base in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("LOCALAPPDATA", "")):
            if not base:
                continue
            candidate = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if candidate.is_file():
                return str(candidate)
        return ""
    if sys.platform == "darwin":
        candidate = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        return str(candidate) if candidate.is_file() else ""
    return shutil.which("google-chrome") or shutil.which("chromium") or ""


def _chromium_cache() -> str:
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or Path.home() / ".cache" / "ms-playwright")
    if not root.is_dir():
        return ""
    for child in root.iterdir():
        if child.name.startswith("chromium"):
            return str(child)
    return ""


def main() -> int:
    rows: list[tuple[str, str, str]] = []
    blocking = 0

    version = ".".join(str(part) for part in sys.version_info[:3])
    if sys.version_info >= (3, 10):
        rows.append((OK, "Python", version))
    else:
        rows.append((BAD, "Python", f"{version}（需要 >= 3.10）"))
        blocking += 1

    if _has_module("playwright"):
        rows.append((OK, "playwright", "已安装"))
    else:
        rows.append((BAD, "playwright", "未安装：pip install playwright"))
        blocking += 1

    chrome = _chrome_path()
    chromium = _chromium_cache()
    if chrome:
        rows.append((OK, "浏览器", chrome))
    elif chromium:
        rows.append((OK, "浏览器", f"playwright chromium: {chromium}"))
    else:
        rows.append((WARN, "浏览器", "未找到 Chrome/Chromium，先跑 playwright install chromium"))

    ffmpeg = resolve_ffmpeg()
    if ffmpeg:
        rows.append((OK, "ffmpeg", ffmpeg))
    else:
        rows.append((BAD, "ffmpeg", "未找到，请装 ffmpeg 或 pip install imageio-ffmpeg"))
        blocking += 1

    if _has_module("whisper"):
        model = os.environ.get("DOUYIN_WHISPER_MODEL", "small")
        cache = Path.home() / ".cache" / "whisper" / f"{model}.pt"
        state = "已缓存" if cache.is_file() else "首次运行会下载模型"
        rows.append((OK, "whisper", f"已安装（{model}，{state}）"))
    else:
        rows.append((WARN, "whisper", "未安装：pip install openai-whisper（不装则无法转录）"))

    rows.append((OK if _has_module("rapidocr_onnxruntime") else WARN, "RapidOCR", "已安装" if _has_module("rapidocr_onnxruntime") else "未安装，将跳过画面文字"))

    from .transcribe import available_backends

    backends = available_backends()
    if backends:
        rows.append((OK, "转录后端", " / ".join(backends)))
    else:
        rows.append((WARN, "转录后端", "未安装：pip install faster-whisper（推荐）或 openai-whisper"))

    ai_cfg = resolve_ai("auto")
    if ai_cfg["key"]:
        rows.append((OK, "AI", f"{ai_cfg['provider']} / {ai_cfg['model']}"))
    else:
        rows.append((WARN, "AI", "未配置，标点走正则、跳过可靠性分析（可用 --ai none 显式关闭）"))

    out = Path.cwd() / "output"
    try:
        out.mkdir(parents=True, exist_ok=True)
        probe = out / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        rows.append((OK, "输出目录", str(out)))
    except OSError as exc:
        rows.append((BAD, "输出目录", str(exc)))
        blocking += 1

    rows.append((OK, "缓存目录", str(cache_dir())))

    width = max(len(label) for _, label, _ in rows)
    print("douyin-parse 环境检查")
    print("-" * 70)
    for status, label, detail in rows:
        print(f"[{status}] {label.ljust(width)}  {detail}")
    print("-" * 70)

    if blocking:
        print(f"{blocking} 项阻塞问题需要先解决。")
        return 1
    print("环境就绪。")
    return 0
