# AGENTS.md — 给 AI 编码助手的项目记忆

> 面向所有会读仓库根目录 `AGENTS.md` 的工具：Codex、Claude Code、Cursor、Copilot、DSH 等。
> 人看的说明在 [README.md](README.md)，贡献流程在 [CONTRIBUTING.md](CONTRIBUTING.md)。
>
> **本文件是项目知识的唯一来源**（架构 / 命令 / 约定 / 坑）。本机路径、密钥位置、个人工作流不要写进来。
> Claude Code 通过 [CLAUDE.md](CLAUDE.md) 导入本文件；Copilot 读 [.github/copilot-instructions.md](.github/copilot-instructions.md)（只是索引，不重复维护）。

## 这是什么

把抖音分享链接转成可读文案的命令行工具：抓流 → FFmpeg 转 16k 单声道 → Whisper 转录 → 本地字典纠错 → RapidOCR 识屏 →（可选）AI 加标点与可靠性分析。

输出是「一条内容一个文件夹」：`文案.txt` / `文案_分析版.md` / `画面文字.md` / `修订报告.md` / `info.json` / `audio.wav`。

## 架构地图

| 文件 | 职责 | 什么时候改它 |
| --- | --- | --- |
| `src/douyin_parse/cli.py` | argparse：parse / batch / transcribe / doctor / config | 加子命令或参数 |
| `config.py` | 配置优先级（CLI > env > .env > 默认）、ffmpeg 定位、AI 供应商解析 | 加配置项 |
| `pipeline.py` | 主流程编排：页面 → 抓流 → 下载 → 转码 → 转录 → 修订 → OCR → 分析 → 落盘 | 改流程顺序或落盘内容 |
| `extract.py` | 图文/视频判定、标题、作者、标签 | 抖音页面结构变了 |
| `browser.py` | 把抢焦点的窗口最小化（非 Windows 自动跳过） | 浏览器体验问题 |
| `media.py` | 媒体下载、录音降级设备选择 | 下载/降级逻辑 |
| `transcribe.py` | 转录双后端（faster-whisper 优先，回落 openai-whisper） | 换模型或加后端 |
| `ocr.py` | 截帧 + RapidOCR + 结果解析/去重 | 画面文字相关 |
| `ai.py` | 标点恢复 + 可靠性分析（任意 OpenAI 兼容接口） | 改 prompt 或供应商 |
| `render.py` | 输出 Markdown 版式 | 改产出格式 |
| `correct.py` | 2098 条 ASR 字典修订（`corrections.json`） | 加纠错词条 |
| `naming.py` | 文件名清洗、时长格式化、目录编号 | 命名/编号规则 |
| `batch.py` | 批量模式（子进程逐条跑） | 批量行为 |
| `local.py` | 本地文件模式（不开浏览器） | 本地转录 |
| `webui.py` | 本地网页界面（标准库 http.server，子进程跑解析、轮询进度） | 改买家交互 |
| `interactive.py` | 控制台交互模式（菜单 + 粘贴链接） | 改控制台流程 |
| `doctor.py` | 环境自检 | 加检查项 |

顶层还有两个非包目录：`packaging/`（便携版启动器模板）、`tools/make_portable.py`（打 Windows 便携版）。

## 常用命令

```bash
pip install -e ".[all]"                     # 开发安装
python -m unittest discover -s tests -v      # 单测
python -m douyin_parse doctor                # 环境自检
python -m douyin_parse parse "<链接>" --ai none --model small
python -m douyin_parse transcribe ./a.mp4 --ai none --model tiny
python -m douyin_parse web --no-browser      # 网页界面（开发时手动开）
python -m douyin_parse interactive           # 控制台交互
python tools/make_portable.py --no-zip       # 打便携版（不压 zip 快一点）
```

测试不需要网络、不需要浏览器、不需要 ffmpeg：**不要让单测触发真实抓取**。

## 硬性约定

1. **纯函数优先**：能被单测覆盖的逻辑（命名、渲染、字典、配置解析、OCR 结果过滤）不要写进 `pipeline.run()`。
2. **不新增硬编码路径**：一切路径走 `config.py`，输出默认 `./output`，profile 默认系统缓存目录。
3. **依赖可选**：缺 playwright / whisper / rapidocr / sounddevice 时降级并给明确提示，不要 import 时直接崩。
4. **面向用户的输出用中文**，日志前缀保持现有风格（`步骤1:`、`[OCR]`）。
5. **不提交**：`output/`、`*.wav`、`*.mp4`、`cookies/`、`.env`、任何 API key。
6. 提交信息格式：`<type>(<scope>): <subject>`，type 用 `feat|fix|docs|refactor|test|chore`。

## 发布

- 版本号在 `pyproject.toml`，同时改 `src/douyin_parse/__init__.py` 的 `__version__` 和 `CHANGELOG.md`
- 推 `v*` 标签自动触发 `.github/workflows/publish.yml`（OIDC 可信发布，无需 token）
- **不要**同时再发 GitHub Release，会重复发布并在第二次失败
- 详见 [docs/发布.md](docs/发布.md)

## 已知坑（都是踩过的）

- **rapidocr 的置信度是字符串**：`conf` 可能是 `'0.79'`，直接和 `0.5` 比较会抛 `TypeError`，被裸 `except` 吞掉后表现为「OCR 恒为 0 段」。过滤逻辑统一走 `ocr.pick_texts()`。
- **页面上的 duration 不可信**：可能是预加载片段，落盘前以音频实际长度为准。
- **Windows 编码**：PowerShell 的 `*>` 重定向会写成 UTF-16；CLI 在非 TTY 时会把输出强制成 UTF-8，否则 `--help` 在 Windows CI 上会 `UnicodeEncodeError`。
- **playwright 启动**：Windows 先找系统 Chrome，没有就用 Edge（`config.detect_browser_channel()`），其他平台用自带 chromium；服务器环境加 `--headless`。
- **AI 探测不要起子进程**：Windows 上 `powershell` 冷启动可达 50 秒，早期用它读环境变量导致探测必然超时。现在写的是 `os.environ` + `winreg` 直读。
- **纠错必须是单趟替换**：`correct.py` 用一条正则（同一起点取最长匹配）+ 窗口守卫，保证规则之间互相看不见。**不要改回"按长度逐条 `str.replace`"**——那样后一条规则会吃到前一条的产物，历史上造成 57 条词条互相打架：`SOTA` 注解被追加两次、`FDE` 被补成 `FDEE`、`开源项目` 被改成 `开开源项目`。
- **词条不要写成全局单字/常用词映射**：`假→甲`、`现成→县城`、`缺乏→确权` 这类会把正常文本改错。上下文专用的修正要写成带上下文的短语。

## 改完先自检

```bash
python -m unittest discover -s tests        # 必须全绿
python -m douyin_parse doctor                # 环境是否就绪
python -m douyin_parse parse "<短链接>" --ai none --model small   # 端到端
```

端到端改动请附：命令、耗时、产出目录里前几行内容（不要贴 cookie/key）。
