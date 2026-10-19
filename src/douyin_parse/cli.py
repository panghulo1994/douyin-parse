"""命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, ai, pipeline
from .batch import run_batch
from .config import build

ENV_TEMPLATE = """# douyin-parse 配置（不填也能跑，AI 相关全部可选）
# AI：任意 OpenAI 兼容接口
AI_API_URL=https://api.deepseek.com/v1/chat/completions
AI_API_KEY=
AI_MODEL=deepseek-chat
# 供应商快捷选择：deepseek / mimo
DOUYIN_AI_PROVIDER=

# 运行参数
# tiny / base / small / medium / large-v3（默认 small）
DOUYIN_WHISPER_MODEL=small
# 转录后端：auto / faster-whisper / whisper
DOUYIN_TRANSCRIBE_BACKEND=auto
# 输出根目录，默认 ./output
DOUYIN_OUTPUT_BASE=
# 1 = 跳过画面文字提取
DISABLE_VIDEO_OCR=
# 1 = 给输出目录统一编号
DOUYIN_AUTO_NUMBER=
"""


def _force_utf8_output() -> None:
    """Windows 上把输出重定向到文件/管道时，默认编码可能是 cp936/cp1252。"""
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", "") or "").lower()
        if encoding in ("utf-8", "utf8"):
            continue
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dyparse",
        description="抖音文案解析：链接 → 文案 + 画面文字 + 可靠性分析；也支持本地文件",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--out", metavar="DIR", help="输出根目录（默认 ./output）")
        sp.add_argument("--model", metavar="NAME", help="whisper 模型：tiny/base/small/medium/large-v3（默认 small）")
        sp.add_argument(
            "--backend",
            default="auto",
            choices=("auto", "faster-whisper", "whisper"),
            help="转录后端（默认 auto：装了 faster-whisper 就优先用它）",
        )
        sp.add_argument("--no-ocr", action="store_true", help="跳过画面文字提取")
        sp.add_argument("--ai", default="auto", choices=("auto", "none", "deepseek", "mimo"), help="AI 供应商（默认 auto）")
        sp.add_argument("--auto-number", action="store_true", help="按修改时间给输出目录统一编号")
        sp.add_argument("--profile", metavar="DIR", help="浏览器 profile 目录")
        sp.add_argument("--proxy", metavar="URL", help="代理，如 http://127.0.0.1:7890")
        sp.add_argument("--user-agent", metavar="UA", help="自定义 User-Agent")

    p_parse = sub.add_parser("parse", help="解析一条抖音链接")
    p_parse.add_argument("url", help="抖音分享链接")
    p_parse.add_argument("-v", "--force-video", action="store_true", help="强制按视频解析")
    p_parse.add_argument("--headless", action="store_true", help="无头浏览器（服务器上用）")
    add_common(p_parse)

    p_batch = sub.add_parser("batch", help="批量解析链接文件")
    p_batch.add_argument("file", help="一行一个链接，空行和 # 开头跳过")
    p_batch.add_argument("--headless", action="store_true", help="无头浏览器（服务器上用）")
    add_common(p_batch)

    p_local = sub.add_parser("transcribe", help="转录本地音视频文件（不联网、不开浏览器）")
    p_local.add_argument("file", help="本地视频或音频文件")
    add_common(p_local)

    p_web = sub.add_parser("web", help="本地网页界面（粘贴链接、点按钮）")
    p_web.add_argument("--port", type=int, default=8765, help="端口（默认 8765）")
    p_web.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    add_common(p_web)

    sub.add_parser("interactive", help="控制台交互模式（按提示粘贴链接）")

    sub.add_parser("doctor", help="检查运行环境")

    p_config = sub.add_parser("config", help="配置")
    p_config.add_argument("--init", action="store_true", help="在当前目录生成 .env 模板")
    return parser


def _handle_config(args: argparse.Namespace) -> int:
    target = Path.cwd() / ".env"
    if not args.init:
        print("用法: dyparse config --init   # 生成 .env 模板")
        return 2
    if target.exists():
        print(f"已存在，未覆盖: {target}")
        return 1
    target.write_text(ENV_TEMPLATE, encoding="utf-8")
    print(f"已生成: {target}")
    print("按需填写 AI_API_KEY 等字段；不填也能用 --ai none 跑全本地流程。")
    return 0


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    args = build_parser().parse_args(argv)

    if args.command == "doctor":
        from .doctor import main as doctor_main

        return doctor_main()
    if args.command == "config":
        return _handle_config(args)
    if args.command == "interactive":
        from .interactive import run_interactive

        return run_interactive(build())

    cfg = build(
        url=getattr(args, "url", ""),
        input_file=getattr(args, "file", "") if args.command == "transcribe" else "",
        out=args.out,
        model=args.model,
        backend=args.backend,
        no_ocr=args.no_ocr,
        force_video=getattr(args, "force_video", False),
        ai=args.ai,
        auto_number=args.auto_number,
        profile_dir=args.profile,
        batch_file=getattr(args, "file", "") if args.command == "batch" else "",
        headless=getattr(args, "headless", False),
        proxy=args.proxy,
        user_agent=args.user_agent,
    )
    ai.configure(cfg.ai_provider, cfg.ai_api_url, cfg.ai_api_key, cfg.ai_model, cfg.ai_api_format)

    if args.command == "web":
        from .webui import run_web

        return run_web(cfg, port=args.port, open_browser=not args.no_browser)
    if args.command == "transcribe":
        from .local import run_local

        return run_local(cfg)
    if args.command == "batch":
        return run_batch(cfg)
    return pipeline.run(cfg)
