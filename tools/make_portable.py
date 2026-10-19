"""打 Windows 便携版：内置 Python + 依赖 + ffmpeg + whisper 模型 + 启动器。

用法：
    python tools/make_portable.py                 # 默认输出 dist/抖音文案工具/
    python tools/make_portable.py --no-zip        # 只生成目录，不打 zip
    python tools/make_portable.py --model small   # 指定模型
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
APP_NAME = "抖音文案工具"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(cmd: list[str], **kw) -> None:
    log("$ " + " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def build_wheel() -> Path:
    tmp = DIST / "_wheel"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    run([sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp)], cwd=str(ROOT))
    wheels = list(tmp.glob("*.whl"))
    if not wheels:
        raise SystemExit("构建 wheel 失败")
    return wheels[0]


def copy_python(base: Path, dst: Path) -> None:
    def ignore(dirname: str, names: list[str]) -> set[str]:
        skipped = {"__pycache__", "test", "tests", "idlelib", "tkinter", "turtledemo"}
        return {n for n in names if n in skipped or n.endswith(".pyc")}

    log(f"复制 Python: {base} -> {dst}")
    shutil.copytree(base, dst, ignore=ignore, symlinks=False)


def install_package(python: Path, wheel: Path) -> None:
    run([str(python), "-m", "pip", "install", "--no-index", "--no-deps",
         "--force-reinstall", "--no-warn-script-location", str(wheel)])


def copy_ffmpeg(base_python: Path, dst: Path) -> None:
    try:
        out = subprocess.check_output(
            [str(base_python), "-c",
             "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
            text=True,
        ).strip()
    except Exception as exc:
        log(f"找不到 imageio-ffmpeg 的 ffmpeg：{exc}")
        return
    src = Path(out)
    if src.is_file():
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst / "ffmpeg.exe")
        log(f"ffmpeg -> {dst / 'ffmpeg.exe'}")


def copy_model(model: str, dst: Path) -> None:
    cache = Path(os.environ.get("USERPROFILE", Path.home())) / ".cache" / "whisper" / f"{model}.pt"
    if not cache.is_file():
        log(f"⚠ 模型不存在：{cache}（跳过，买家首次运行会自行下载）")
        return
    target = dst / "userdata" / ".cache" / "whisper"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cache, target / f"{model}.pt")
    log(f"模型 -> {target / (model + '.pt')}")


def copy_extras(dst: Path) -> None:
    (dst / "docs").mkdir(parents=True, exist_ok=True)
    for name in ("使用说明.pdf", "使用说明.html"):
        src = ROOT / "docs" / name
        if src.is_file():
            shutil.copy2(src, dst / name)
    for name in ("LICENSE", "README.md"):
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, dst / name)

    pack = ROOT / "packaging"
    shutil.copy2(pack / "start.bat", dst / "start.bat")
    shutil.copy2(pack / "start.bat", dst / "启动.bat")
    shutil.copy2(pack / "start-console.bat", dst / "start-console.bat")
    shutil.copy2(pack / "start-console.bat", dst / "启动-控制台.bat")
    log("启动器 + 说明文档已复制")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DIST))
    ap.add_argument("--python-dir", default=sys.base_prefix)
    ap.add_argument("--model", default="small")
    ap.add_argument("--no-zip", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    target = out / APP_NAME
    base = Path(args.python_dir)

    if not (base / "python.exe").is_file():
        raise SystemExit(f"不是有效的 Windows Python 目录：{base}")

    if target.exists():
        log(f"清理旧的 {target}")
        shutil.rmtree(target)
    target.mkdir(parents=True)

    wheel = build_wheel()
    copy_python(base, target / "python")
    install_package(target / "python" / "python.exe", wheel)
    copy_ffmpeg(base / "python.exe", target / "runtime")
    copy_model(args.model, target)
    copy_extras(target)

    size_gb = sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) / 1024 ** 3
    log(f"目录完成：{target}（{size_gb:.2f} GB）")

    if not args.no_zip:
        log("打包 zip（可能要几分钟）…")
        zip_base = out / f"{APP_NAME}-便携版"
        shutil.make_archive(str(zip_base), "zip", root_dir=str(out), base_dir=APP_NAME)
        log(f"zip: {zip_base}.zip （{(zip_base.with_suffix('.zip')).stat().st_size / 1024 ** 3:.2f} GB）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
