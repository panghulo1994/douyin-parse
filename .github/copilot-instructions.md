# Copilot instructions

本项目的完整约定在仓库根目录 [AGENTS.md](../AGENTS.md)。**这里只做索引，不要重复维护。**

要点：

- Python 3.10+，src 布局，hatchling 打包
- 测试：`python -m unittest discover -s tests`
- 不要提交 `output/`、媒体文件、cookies、任何密钥
- 面向用户的中文输出，日志风格保持 `步骤N:` / `[OCR]`
