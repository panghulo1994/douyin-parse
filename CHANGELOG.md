# Changelog

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
