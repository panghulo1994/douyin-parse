import unittest

from douyin_parse.ocr import pick_texts


class PickTextsTest(unittest.TestCase):
    def test_string_confidence(self):
        """rapidocr 某些版本返回的是字符串置信度。"""
        result = [[[[0, 0], [1, 1]], "画面文字", "0.79"]]
        self.assertEqual(pick_texts(result), ["画面文字"])

    def test_filters_low_conf_and_short(self):
        result = [
            [[[0, 0]], "有效文字", "0.90"],
            [[[0, 0]], "低置信", "0.20"],
            [[[0, 0]], "短", "0.99"],
        ]
        self.assertEqual(pick_texts(result), ["有效文字"])

    def test_bad_items_are_skipped(self):
        result = [None, [], [[[0, 0]], "缺分数"], [[[0, 0]], "坏分数", "abc"]]
        self.assertEqual(pick_texts(result), [])

    def test_empty(self):
        self.assertEqual(pick_texts(None), [])


if __name__ == "__main__":
    unittest.main()
