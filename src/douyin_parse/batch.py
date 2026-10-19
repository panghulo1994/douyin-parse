"""批量模式：逐条子进程解析，单条失败不影响整批。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime

from .config import Config


def read_batch_links(batch_file: str):
    """读取批量链接文件：一行一个，空行和 # 注释跳过。"""
    path = os.path.abspath(batch_file)
    if not os.path.exists(path):
        raise FileNotFoundError(f"批量链接文件不存在: {path}")

    links = []
    with open(path, "r", encoding="utf-8-sig") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            links.append({"line": line_no, "url": line})
    return path, links


def extract_output_dirs(stdout: str) -> list[str]:
    """从单条解析输出里提取「输出: ...」目录。"""
    dirs: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("输出: "):
            output_path = line.replace("输出: ", "", 1).strip()
            output_dir = os.path.dirname(output_path)
            if output_dir and output_dir not in dirs:
                dirs.append(output_dir)
    return dirs


def write_batch_summary(summary_path: str, batch_file: str, results: list[dict]) -> None:
    ok_count = sum(1 for item in results if item["status"] == "success")
    fail_count = len(results) - ok_count

    md_lines = [
        "# 批量解析汇总",
        "",
        f"- 链接文件：{batch_file}",
        f"- 总数：{len(results)}",
        f"- 成功：{ok_count}",
        f"- 失败：{fail_count}",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| 序号 | 行号 | 状态 | 链接 | 输出目录/错误 |",
        "|---:|---:|---|---|---|",
    ]
    for index, item in enumerate(results, start=1):
        detail = "<br>".join(item.get("output_dirs") or []) if item["status"] == "success" else item.get("error", "")
        detail = detail.replace("|", "\\|")
        md_lines.append(f"| {index} | {item['line']} | {item['status']} | {item['url']} | {detail} |")

    with open(summary_path + ".json", "w", encoding="utf-8") as handle:
        json.dump(
            {
                "batch_file": batch_file,
                "total": len(results),
                "success": ok_count,
                "failed": fail_count,
                "results": results,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
    with open(summary_path + ".md", "w", encoding="utf-8") as handle:
        handle.write("\n".join(md_lines))


def _child_args(cfg: Config, url: str) -> list[str]:
    args = [sys.executable, "-m", "douyin_parse", "parse", url, "--out", cfg.output_base, "--model", cfg.whisper_model]
    args += ["--ai", cfg.ai_provider or "auto"]
    if cfg.disable_ocr:
        args.append("--no-ocr")
    if cfg.auto_number:
        args.append("--auto-number")
    if cfg.profile_dir:
        args += ["--profile", cfg.profile_dir]
    return args


def run_batch(cfg: Config) -> int:
    os.makedirs(cfg.output_base, exist_ok=True)
    batch_file, links = read_batch_links(cfg.batch_file)
    if not links:
        print(f"错误: 批量文件没有可处理链接 - {batch_file}")
        return 1

    print("=== 抖音批量文案提取 ===")
    print(f"链接文件: {batch_file}")
    print(f"任务数: {len(links)}")

    results = []
    for index, item in enumerate(links, start=1):
        url = item["url"]
        print(f"\n[{index}/{len(links)}] 开始处理: {url}")
        started = time.time()
        proc = subprocess.Popen(
            _child_args(cfg, url),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output_lines = []
        for line in proc.stdout:
            print("  " + line.rstrip())
            output_lines.append(line)
        proc.wait()

        stdout = "".join(output_lines)
        status = "success" if proc.returncode == 0 else "failed"
        error = ""
        if status == "failed":
            tail = [line.strip() for line in stdout.splitlines() if line.strip()]
            error = tail[-1] if tail else "未知错误"
        results.append(
            {
                "line": item["line"],
                "url": url,
                "status": status,
                "returncode": proc.returncode,
                "seconds": round(time.time() - started, 1),
                "output_dirs": extract_output_dirs(stdout),
                "error": error,
            }
        )
        if status == "success":
            print(f"  完成，用时 {results[-1]['seconds']} 秒")
        else:
            print(f"  失败，用时 {results[-1]['seconds']} 秒: {error}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_base = os.path.join(cfg.output_base, f"batch_summary_{stamp}")
    write_batch_summary(summary_base, batch_file, results)

    ok_count = sum(1 for item in results if item["status"] == "success")
    print("\n=== 批量完成 ===")
    print(f"成功: {ok_count}/{len(results)}")
    print(f"汇总: {summary_base}.md")
    return 0 if ok_count == len(results) else 1
