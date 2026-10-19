"""本地网页界面：双击启动后，在浏览器里粘贴链接、点按钮、看进度。

只用标准库（http.server + subprocess），不引入 Web 框架。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__, ai
from .config import Config

STATE_LOCK = threading.Lock()
JOB = {
    "state": "idle",        # idle | running | done | failed
    "lines": [],
    "out_dir": "",
    "url": "",
    "started_at": 0.0,
    "returncode": None,
}

STEPS = ("步骤1", "步骤2", "步骤3", "步骤4", "步骤5.5", "步骤6")


def progress_of(lines: list[str]) -> int:
    """从日志行推断进度百分比（0-100）。纯函数，方便单测。"""
    text = "\n".join(lines)
    if "=== 完成" in text:
        return 100
    seen = sum(1 for step in STEPS if step in text)
    return min(95, int(seen / len(STEPS) * 90))


def extract_output_dir(lines: list[str]) -> str:
    """从「输出: xxx/文案.txt」里取出文件夹。"""
    for line in reversed(lines):
        line = line.strip()
        if line.startswith("输出: "):
            path = line[len("输出: "):].strip()
            parent = os.path.dirname(path)
            if parent:
                return parent
    return ""


def _reset(url: str) -> None:
    with STATE_LOCK:
        JOB.update(state="running", lines=[], out_dir="", url=url,
                   started_at=time.time(), returncode=None)


def _append(line: str) -> None:
    with STATE_LOCK:
        JOB["lines"].append(line)
        if len(JOB["lines"]) > 2000:
            del JOB["lines"][:1000]


def _finish(code: int) -> None:
    with STATE_LOCK:
        JOB["returncode"] = code
        JOB["state"] = "done" if code == 0 else "failed"
        JOB["out_dir"] = JOB["out_dir"] or extract_output_dir(JOB["lines"])


def start_job(cfg: Config, url: str) -> bool:
    """起一个子进程跑解析；同一时间只允许一个任务。"""
    with STATE_LOCK:
        if JOB["state"] == "running":
            return False
    _reset(url)

    args = [
        sys.executable, "-u", "-m", "douyin_parse", "parse", url,
        "--out", cfg.output_base,
        "--model", cfg.whisper_model,
        "--ai", cfg.ai_choice or "auto",
        "--no-ocr",
    ]
    if cfg.disable_ocr:
        args.append("--no-ocr")
    if cfg.headless:
        args.append("--headless")

    def worker() -> None:
        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:  # pragma: no cover
            _append(f"启动失败: {exc}")
            _finish(1)
            return
        assert proc.stdout is not None
        for line in proc.stdout:
            _append(line.rstrip())
        proc.wait()
        _finish(proc.returncode)

    threading.Thread(target=worker, daemon=True).start()
    return True


def open_folder(path: str) -> bool:
    if not path or not Path(path).exists():
        return False
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>抖音文案提取</title>
<style>
:root{--fg:#1f2328;--muted:#57606a;--line:#d0d7de;--accent:#0969da;--bg:#fff;--soft:#f6f8fa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;font-size:15px;line-height:1.7}
.wrap{max-width:760px;margin:0 auto;padding:36px 22px 60px}
h1{font-size:24px;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px;margin-bottom:22px}
textarea{width:100%;min-height:72px;padding:12px 14px;border:1px solid var(--line);border-radius:8px;font-size:15px;font-family:inherit;resize:vertical}
textarea:focus{outline:2px solid var(--accent);outline-offset:-1px}
.row{display:flex;gap:10px;align-items:center;margin-top:12px;flex-wrap:wrap}
button{border:0;border-radius:8px;padding:10px 18px;font-size:15px;cursor:pointer;font-family:inherit}
.primary{background:var(--accent);color:#fff}
.primary:disabled{opacity:.5;cursor:not-allowed}
.ghost{background:var(--soft);color:var(--fg);border:1px solid var(--line)}
.bar{height:8px;background:var(--soft);border-radius:999px;overflow:hidden;margin:18px 0 6px;display:none}
.bar>i{display:block;height:100%;width:0;background:var(--accent);transition:width .4s}
.hint{color:var(--muted);font-size:13px}
.log{margin-top:18px;background:#0d1117;color:#c9d1d9;border-radius:8px;padding:14px 16px;font-family:Consolas,monospace;font-size:12.5px;line-height:1.6;max-height:260px;overflow:auto;white-space:pre-wrap;display:none}
.result{margin-top:22px;border:1px solid var(--line);border-radius:8px;padding:16px 18px;display:none}
.result h2{font-size:17px;margin:0 0 10px}
pre{white-space:pre-wrap;word-break:break-word;margin:0;font-family:inherit;font-size:14px;max-height:320px;overflow:auto}
.badge{display:inline-block;font-size:12px;padding:1px 8px;border-radius:999px;background:var(--soft);color:var(--muted);margin-left:8px}
.badge.ok{background:#dafbe1;color:#116329}
.badge.err{background:#ffebe9;color:#a40e26}
footer{margin-top:36px;color:var(--muted);font-size:12px}
</style></head><body><div class="wrap">
<h1>抖音文案提取 <span class="badge" id="state">就绪</span></h1>
<div class="sub">把抖音分享链接粘进来，点「开始解析」。解析时会弹出一个浏览器窗口抓视频，属于正常现象，请不要关它。</div>
<textarea id="url" placeholder="https://v.douyin.com/xxxxxx/&#10;（手机抖音：分享 → 复制链接，整段粘进来也行）"></textarea>
<div class="row">
  <button class="primary" id="go">开始解析</button>
  <button class="ghost" id="open" style="display:none">打开输出文件夹</button>
  <span class="hint" id="hint"></span>
</div>
<div class="bar" id="bar"><i></i></div>
<div class="log" id="log"></div>
<div class="result" id="result">
  <h2>解析完成</h2>
  <pre id="text"></pre>
  <div class="row"><button class="ghost" id="copy">复制正文</button></div>
</div>
<footer>本工具仅用于个人学习与研究，提取内容的版权归原作者所有。</footer>
</div>
<script>
const $ = s => document.querySelector(s);
let timer = null;
function setState(text, cls){ const b = $('#state'); b.textContent = text; b.className = 'badge' + (cls ? ' ' + cls : ''); }
async function poll(){
  const r = await fetch('/api/status');
  const j = await r.json();
  if (j.state === 'running'){ setState('解析中'); $('#bar').style.display='block'; $('#bar>i').style.width = j.progress + '%'; }
  if (j.lines && j.lines.length){ $('#log').style.display='block'; $('#log').textContent = j.lines.slice(-40).join('\n'); $('#log').scrollTop = 1e6; }
  if (j.state === 'done'){
    clearInterval(timer); timer = null;
    setState('完成', 'ok'); $('#bar>i').style.width = '100%';
    $('#go').disabled = false; $('#hint').textContent = '';
    if (j.out_dir){ $('#open').style.display='inline-block'; $('#open').dataset.dir = j.out_dir; }
    const t = await (await fetch('/api/result')).text();
    $('#result').style.display='block'; $('#text').textContent = t;
  } else if (j.state === 'failed'){
    clearInterval(timer); timer = null;
    setState('失败', 'err'); $('#go').disabled = false;
    $('#hint').textContent = '失败了，看下面日志里最后几行，或把日志发给卖家';
  }
}
async function start(){
  const url = $('#url').value.trim();
  if (!url){ $('#hint').textContent = '先把链接粘进来'; return; }
  $('#go').disabled = true; $('#result').style.display='none'; $('#log').textContent='';
  setState('启动中'); $('#hint').textContent = '';
  const r = await fetch('/api/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url})});
  if (!r.ok){ $('#go').disabled = false; setState('失败','err'); $('#hint').textContent = '启动失败：' + (await r.text()); return; }
  if (timer) clearInterval(timer);
  timer = setInterval(poll, 1200); poll();
}
$('#go').onclick = start;
$('#open').onclick = () => fetch('/api/open', {method:'POST'});
$('#copy').onclick = async () => { await navigator.clipboard.writeText($('#text').textContent); $('#copy').textContent='已复制'; setTimeout(()=>$('#copy').textContent='复制正文', 1500); };
$('#url').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) start(); });
</script></body></html>
"""


def make_handler(cfg: Config):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"douyin-parse/{__version__}"

        def log_message(self, *args):  # 静默访问日志
            pass

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, code: int = 200) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/api/status":
                with STATE_LOCK:
                    lines = JOB["lines"][-80:]
                    payload = {
                        "state": JOB["state"],
                        "progress": progress_of(JOB["lines"]),
                        "lines": lines,
                        "out_dir": JOB["out_dir"],
                        "seconds": round(time.time() - JOB["started_at"], 1) if JOB["started_at"] else 0,
                    }
                self._json(payload)
            elif self.path == "/api/result":
                out = JOB["out_dir"]
                text = ""
                if out:
                    for name in ("文案_分析版.md", "文案.txt"):
                        f = Path(out) / name
                        if f.is_file():
                            text = f.read_text(encoding="utf-8")
                            break
                self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain; charset=utf-8")

        def do_POST(self):  # noqa: N802
            if self.path == "/api/start":
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    data = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    self._json({"error": "bad json"}, 400)
                    return
                url = (data.get("url") or "").strip()
                if not url or not url.startswith("http"):
                    self._json({"error": "链接格式不对"}, 400)
                    return
                if not start_job(cfg, url):
                    self._json({"error": "已有任务在跑"}, 409)
                    return
                self._json({"ok": True})
            elif self.path == "/api/open":
                ok = open_folder(JOB["out_dir"])
                self._json({"ok": ok})
            else:
                self._send(404, b"not found", "text/plain; charset=utf-8")

    return Handler


def pick_port(start: int = 8765, tries: int = 10) -> int:
    import socket

    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def run_web(cfg: Config, port: int = 8765, open_browser: bool = True) -> int:
    ai.configure(cfg.ai_provider, cfg.ai_api_url, cfg.ai_api_key, cfg.ai_model, cfg.ai_api_format)
    Path(cfg.output_base).mkdir(parents=True, exist_ok=True)

    chosen = pick_port(port)
    server = ThreadingHTTPServer(("127.0.0.1", chosen), make_handler(cfg))
    url = f"http://127.0.0.1:{chosen}/"

    print("=" * 46)
    print("  抖音文案提取")
    print("=" * 46)
    print(f"  页面地址：{url}")
    print(f"  输出目录：{cfg.output_base}")
    print("  关闭这个窗口 = 退出工具")
    print("=" * 46)

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
