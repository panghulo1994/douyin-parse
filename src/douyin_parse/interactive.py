"""控制台交互模式：双击启动后按提示粘贴链接，不需要记命令。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import __version__
from .config import Config

BANNER = """
============================================
  抖音文案提取  v{ver}
============================================
  输出目录：{out}
--------------------------------------------
"""


def _child(args: list[str]) -> int:
    """跑子进程并把输出实时打出来。"""
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "douyin_parse", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    last_output = ""
    for line in proc.stdout:
        print(line, end="")
        if line.strip().startswith("输出: "):
            last_output = line.strip()[len("输出: "):].strip()
    proc.wait()
    if last_output:
        folder = os.path.dirname(last_output)
        if folder and Path(folder).exists():
            print("\n结果文件夹：" + folder)
            answer = input("现在打开这个文件夹？[Y/n] ").strip().lower()
            if answer in ("", "y", "yes"):
                _open(folder)
    return proc.returncode


def _open(path: str) -> None:
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as exc:
        print(f"打不开文件夹：{exc}")


def _ask_link() -> str:
    print()
    print("把抖音链接粘进来（手机上：分享 → 复制链接），然后回车：")
    raw = input("> ").strip()
    return raw


def run_interactive(cfg: Config) -> int:
    print(BANNER.format(ver=__version__, out=cfg.output_base))
    Path(cfg.output_base).mkdir(parents=True, exist_ok=True)

    while True:
        print("  1. 解析一条链接")
        print("  2. 批量（一个 txt，一行一个链接）")
        print("  3. 退出")
        choice = input("\n请选择 [1]: ").strip() or "1"

        if choice == "3":
            print("再见。")
            return 0

        if choice == "2":
            print("\n把 links.txt 的完整路径粘进来（一行一个链接），然后回车：")
            batch_file = input("> ").strip().strip('"')
            if not batch_file:
                continue
            code = _child(["batch", batch_file, "--out", cfg.output_base,
                           "--model", cfg.whisper_model, "--ai", cfg.ai_choice or "auto"])
            print(f"\n批量结束（退出码 {code}）")
            continue

        url = _ask_link()
        if not url:
            print("没有输入链接，回到菜单。")
            continue

        print("\n开始解析，过程中会弹出一个浏览器窗口抓视频，不要关它。\n")
        code = _child(["parse", url, "--out", cfg.output_base,
                       "--model", cfg.whisper_model, "--ai", cfg.ai_choice or "auto"])
        if code != 0:
            print(f"\n这条失败了（退出码 {code}）。可以把上面的日志发给卖家。")
        input("\n按回车回到菜单…")
