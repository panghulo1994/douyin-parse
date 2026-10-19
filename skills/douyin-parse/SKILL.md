---
name: douyin-parse
description: 解析抖音分享链接，提取完整文案、画面文字与可靠性分析。Use when the user pastes a douyin.com / v.douyin.com link, asks to 提取抖音文案、视频转文字、批量解析抖音链接, or wants a transcript plus fact-check notes from a Douyin video.
license: MIT
---

# 抖音文案解析

调用 `dyparse` 命令行完成解析，不要自己实现抓流或转录。

## 前置检查

```bash
dyparse doctor
```

有 FAIL 项先按提示装依赖；`whisper` 未安装时无法转录。

## 用法

```bash
dyparse parse "<链接>" --out ./output --ai none
```

- 用户只想拿文案：加 `--ai none`，全本地、不花钱。
- 一条消息里有多个链接：写进 `links.txt`，跑 `dyparse batch links.txt`。
- 视频被误判成图文：加 `-v`。
- 长视频（>10 分钟）：加 `--model small`，否则会很慢。

## 向用户汇报

1. 读 `output/{标题}_{日期}/文案_分析版.md`。
2. 贴出**完整正文**，不要只给摘要。
3. 末尾附上「AI 可靠性分析」原文；若显示「AI 分析暂时不可用」，如实说明，不要自己编一份。
4. 不要贴运行日志、OCR 原始列表、修订对照表。
