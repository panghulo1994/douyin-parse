import unittest

from douyin_parse.render import build_ocr_md, mdify_analysis


class MdifyAnalysisTest(unittest.TestCase):
    def test_upgrades_emoji_heads(self):
        text = "📊 基本信息\n- 类型：视频\n✅ 内容核查\n- 可信度：中"
        md = mdify_analysis(text)
        self.assertIn("### 📊 基本信息", md)
        self.assertIn("### ✅ 内容核查", md)

    def test_keeps_plain_lines(self):
        self.assertIn("- 类型：视频", mdify_analysis("📊 基本信息\n- 类型：视频"))


class BuildOcrMdTest(unittest.TestCase):
    def test_lists_every_line(self):
        md = build_ocr_md("标题", ["第一行", "第二行"], url="https://example.com")
        self.assertIn("共 2 段", md)
        self.assertIn("1. 第一行", md)
        self.assertIn("2. 第二行", md)
        self.assertIn("https://example.com", md)


if __name__ == "__main__":
    unittest.main()
