# -*- coding: utf-8 -*-
import pathlib, time, zipfile

dist = pathlib.Path(r"D:\ccgui项目文件\douyin-parse\dist")
src = dist / "抖音文案工具"
out = dist / "抖音文案工具-便携版.zip"
started = time.time()
n = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
    for p in src.rglob("*"):
        if p.is_file():
            z.write(p, p.relative_to(dist))
            n += 1
print("entries:", n, "GB:", round(out.stat().st_size / 1024 ** 3, 2), "seconds:", round(time.time() - started))
