# 贡献指南

先谢谢你想改这个项目。它很小，规则也很少。

## 开发环境

```bash
git clone https://github.com/panghulo1994/douyin-parse.git
cd douyin-parse
pip install -e .
pip install faster-whisper        # 或者 openai-whisper
python -m unittest discover -s tests -v
```

Windows 上如果没装 Chrome，跑一次 `playwright install chromium`。

## 跑一遍真实流程

改完先自检，再拿一条短链接（< 2 分钟）跑通：

```bash
python -m douyin_parse doctor
python -m douyin_parse parse "<链接>" --ai none --model small --out ./output
```

本地文件模式不需要网络，适合快速验证：

```bash
python -m douyin_parse transcribe ./sample.mp4 --ai none --model tiny
```

## 代码约定

- 纯函数优先，能被单测覆盖的逻辑不要写在 `pipeline.run()` 里
- 不要引入新的硬编码路径；配置统一走 `config.py`
- 依赖尽量做成可选：缺依赖时给明确提示并降级，而不是直接崩
- 面向用户的输出保持中文，代码注释用中文或英文都行

## 提交

- 一个 PR 一件事
- 提交信息：`<type>(<scope>): <subject>`，type 用 `feat|fix|docs|refactor|test|chore`
- PR 里附上：改了什么、怎么验证的（命令 + 结果）
- 涉及解析逻辑的改动，请附一条真实链接的验证结果

## 报告问题

用 issue 模板，尽量带上：

1. `python -m douyin_parse doctor` 的输出
2. 完整命令和 `temp_logs/` 里的日志
3. 是「解析失败」还是「解析成功但内容不对」——后者请附产出片段
