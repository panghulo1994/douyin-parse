# douyin-parse

把抖音分享链接变成可读的文案：`链接 → 文案.txt / 文案_分析版.md`，附带画面文字（OCR）与一段 AI 可靠性分析。

```bash
dyparse parse "https://v.douyin.com/xxxxxx/"
```

- 视频：Playwright 抓流 → FFmpeg 转 16k 单声道 → Whisper 转录 → 本地字典纠错 → RapidOCR 识屏
- 图文：直接读页面文本，不下载、不 OCR
- AI 可选：标点恢复 + 可靠性分析（任意 OpenAI 兼容接口），不配也能跑

## 安装

需要 Python 3.10+ 和 ffmpeg。

```bash
# 推荐：隔离安装（发布到 PyPI 后）
pipx install "douyin-parse[all]"

# 或者用 uv
uv tool install "douyin-parse[all]"

# 开发模式（现在就能用）
git clone <repo> && cd douyin-parse
pip install -e ".[all]"
playwright install chromium   # 非 Windows 或没装 Chrome 时需要
```

> 还没发布到 PyPI：现在请用「开发模式」安装（`git clone` → `pip install -e ".[all]"`）。
> 上面前两种写法是发布后的目标形态。

装完先自检：

```bash
dyparse doctor
```

## 用法

```bash
dyparse parse "https://v.douyin.com/xxxx/"            # 单条
dyparse parse "https://v.douyin.com/xxxx/" -v         # 强制按视频解析
dyparse parse "https://v.douyin.com/xxxx/" --ai none  # 全本地，不调用 AI
dyparse batch links.txt                               # 批量，一行一个链接
dyparse config --init                                 # 生成 .env 模板
```

常用参数：

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `--out DIR` | 输出根目录 | `./output` |
| `--model NAME` | `tiny/base/small/medium/large-v3` | `small` |
| `--no-ocr` | 跳过画面文字提取 | 不跳过 |
| `--ai auto\|none\|deepseek\|mimo` | AI 供应商 | `auto` |
| `--auto-number` | 按修改时间给输出目录统一编号 | 关 |
| `-v, --force-video` | 图文被误判时强制视频流程 | 关 |

也可以用环境变量：`DOUYIN_OUTPUT_BASE` / `DOUYIN_WHISPER_MODEL` / `DISABLE_VIDEO_OCR` / `DOUYIN_AI_PROVIDER` / `AI_API_URL` / `AI_API_KEY` / `AI_MODEL`。

Windows 上密钥只存在「用户环境变量」里也能读到（不需要重启终端）。

## 给 Agent 用（可选）

仓库带一个 skill：`skills/douyin-parse/SKILL.md`。复制到你的技能目录即可：

- Claude Code：`~/.claude/skills/douyin-parse/`
- DSH：`~/.dsh/skills/douyin-parse/`

skill 只约定「什么时候调用、怎么汇报」，解析仍然由 `dyparse` 完成。

## 产出

每条内容一个文件夹（`{标题}_{YYYYMMDD}`）：

| 文件 | 内容 |
| --- | --- |
| `文案.txt` | 修订、加标点后的纯正文 |
| `文案_分析版.md` | 标题 + 元信息表 + 正文 + AI 可靠性分析 |
| `画面文字.md` | 视频画面 OCR 出来的文字（有结果时） |
| `修订报告.md` | ASR 字典修正记录（有修正时） |
| `info.json` | 元数据 + 原始转录 + 分析 + OCR 文本 |
| `audio.wav` | 16kHz 单声道音频 |

## 速度

CPU 上实测（30 分钟视频，i9-14900HX）：

| 模型 | 体积 | 转录耗时 |
| --- | --- | --- |
| `small` | ≈460 MB | 约为音频时长的 0.6 倍 |
| `large-v3` | ≈2.9 GB | 约为音频时长的 1.7 倍（30 分钟视频 ≈ 50 分钟） |

长视频建议 `--model small`；追求准确度再用 `large-v3`。

## 平台

- Windows：默认调用系统 Chrome（`DOUYIN_BROWSER_CHANNEL=chrome`），窗口会自动最小化
- macOS / Linux：需要 `playwright install chromium`，窗口最小化自动跳过
- 无图形界面服务器：暂不支持（浏览器以有头模式运行）

## 现状

v0.1 把原先的单文件脚本拆成了模块（`config / browser / media / ai / render / correct / naming / ocr / pipeline`），
提供 `dyparse` 命令行、跨平台配置目录、`doctor` 自检和单元测试。

尚未完成：

- [ ] `faster-whisper` 后端（安装体积可从 ~2.5 GB 降到 ~300 MB）
- [ ] 本地文件输入（`dyparse transcribe ./a.mp4`）
- [ ] 代理 / 自定义 UA
- [ ] 更多平台适配与失效自动检测

## 许可与免责声明

MIT。仅供个人学习与研究使用。

抓取行为可能违反平台用户协议，且会随平台改版失效；产出的文案、画面文字版权归原作者，
请勿再分发或用于商业用途。
