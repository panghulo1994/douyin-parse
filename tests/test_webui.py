import unittest

from douyin_parse.webui import extract_output_dir, pick_port, progress_of


class ProgressTest(unittest.TestCase):
    def test_idle(self):
        self.assertEqual(progress_of([]), 0)

    def test_steps_advance(self):
        lines = ["步骤1: 打开页面", "步骤2: 下载", "步骤3: 提取音频"]
        self.assertGreater(progress_of(lines), 0)
        self.assertLess(progress_of(lines), 60)

    def test_done_is_hundred(self):
        self.assertEqual(progress_of(["步骤1", "=== 完成 (12.3秒) ==="]), 100)

    def test_never_exceeds_95_before_done(self):
        lines = ["步骤1", "步骤2", "步骤3", "步骤4", "步骤5.5", "步骤6"]
        self.assertLessEqual(progress_of(lines), 95)


class OutputDirTest(unittest.TestCase):
    def test_extracts_folder(self):
        lines = ["输出: D:/out/标题_20261019/文案.txt", "输出: D:/out/标题_20261019/文案_分析版.md"]
        self.assertEqual(extract_output_dir(lines), "D:/out/标题_20261019")

    def test_missing(self):
        self.assertEqual(extract_output_dir(["没有输出行"]), "")


class PortTest(unittest.TestCase):
    def test_returns_int(self):
        self.assertIsInstance(pick_port(8900, 3), int)


if __name__ == "__main__":
    unittest.main()
