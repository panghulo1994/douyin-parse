# Changelog

## Unreleased

- 新增 `dyparse web`：本地网页界面（粘贴链接、点按钮、看进度、复制正文）
- 新增 `dyparse interactive`：控制台交互模式，双击后按提示粘贴链接
- 新增 `tools/make_portable.py`：一键打 Windows 便携版（内置解释器 / 依赖 / ffmpeg / 模型 / 启动器）
- 浏览器探测：Windows 上 Chrome 缺失时自动回退到 Edge
- 转录后端支持 `DOUYIN_MODEL_DIR`，便携版把模型放包内
- 浏览器启动失败时给出可操作的提示（关掉 Chrome / 删除配置目录）

### 修复

- 纠错改为**单趟替换**（`correct.py`）：每个位置只匹配一次、只替换一次，规则之间不再互相污染。此前 `SOTA → SOTA（State-of-the-Art）` 会被同一条规则再追加一次变成 `SOTA（…）（…）`；`FD → FDE` 会把已经正确的 `FDE` 补成 `FDEE`；`源项目 → 开源项目` 会把正确的「开源项目」改成「开开源项目」。
- 新增"窗口守卫"：命中位置已处在完整目标形态时保持原样（`FDE` / `开源项目` / `《女儿红》` 等不再套娃）。
- 删除方向写反的词条：`现成 → 县城`、`千万 → 通义千问`（同期各有 3 条短语级规则指向相反方向）。
- 删除会污染常用词的词条：`影业 → 乙`、`缺乏 → 确权/缺口`、`Multi-On → MultiOn`。
- 4 条链式词条改为一步到位：`sota`、`MILS`、`MITNMILS`、`这个Mid Journey`。
- 自检：会被二次改坏的修正值由 **57 条降到 1 条**（仅 `龙虾时刻` 在重复跑同一段文本时嵌套）。
- 新增 5 条误听：`KTAP → GitHub`、`Deep Tutor` / `Deep Shooter` → `DeepTutor`、`投位给 → 投喂给`、`启程转合 → 起承转合`。
- 补 12 个单测覆盖上述行为（单趟、幂等、注解不重复、反向规则不生效、新增词条生效）。

## 0.1.1 — 2026-10-19

- 文档：安装说明改为 PyPI 正式可用，补 PyPI 与 Python 徽章
- CI：发布工作流除 Release 外，也支持推送 `v*` 标签时触发

## 0.1.0 — 2026-10-19

首个可用版本，从单文件脚本重构为可安装的包。

### 新增

- `dyparse` 命令行：`parse` / `batch` / `transcribe` / `doctor` / `config`
- 本地文件模式：`dyparse transcribe ./a.mp4`，不联网、不开浏览器
- 转录后端可选：`faster-whisper`（推荐，CPU 快 3–4 倍、不装 torch）或 `openai-whisper`
- `dyparse doctor`：Python / playwright / 浏览器 / ffmpeg / 转录后端 / OCR / AI / 输出目录一次检查
- `--headless`、`--proxy`、`--user-agent`
- PyPI 发布工作流（Trusted Publishing，无需 token）与 [docs/发布.md](docs/发布.md)
- README 运行示例图 `docs/demo.png`
- 跨平台配置目录；Windows 用户级环境变量里的 key 也能读到

### 变更

- 1682 行单文件拆成 `cli / config / pipeline / extract / transcribe / ocr / media / browser / ai / render / correct / naming / batch / local / doctor`
- 2098 条 ASR 字典迁到 `corrections.json`
- 移除 3 处硬编码路径（输出目录、浏览器 profile、ffmpeg）
- 默认转录模型由 `large-v3` 改为 `small`
- 目录自动编号改为可选（`--auto-number`）
- 移除 `legacy/`（旧的 Windows bat 入口，仅本机可用）
- AI 供应商探测改用环境变量 + Windows 注册表直读，不再启 powershell 子进程

### 修复

- `--no-ocr` 之前没有真正生效
- 页面上读到的时长可能是预加载片段，现在以音频实际长度为准
- OCR 跳过时的提示不再误报「未安装依赖」
- **OCR 识别结果恒为 0 段**：rapidocr 某些版本返回的置信度是字符串（`'0.79'`），
  与 `0.5` 比较会抛 `TypeError`，而旧代码用裸 `except` 吞掉异常，导致每一帧都被跳过。
  实测同一视频修复前 0 段、修复后 45 段
