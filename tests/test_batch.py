import unittest

from douyin_parse.batch import _child_args
from douyin_parse.config import build


class ChildArgsTest(unittest.TestCase):
    def test_ai_none_is_propagated(self):
        """--ai none 必须传给子进程，否则每一条都会重新去探测 key。"""
        args = _child_args(build("u", ai="none"), "https://v.douyin.com/x/")
        self.assertEqual(args[args.index("--ai") + 1], "none")

    def test_headless_proxy_and_ua(self):
        cfg = build("u", headless=True, proxy="http://127.0.0.1:7890", user_agent="UA")
        args = _child_args(cfg, "u")
        self.assertIn("--headless", args)
        self.assertEqual(args[args.index("--proxy") + 1], "http://127.0.0.1:7890")
        self.assertEqual(args[args.index("--user-agent") + 1], "UA")

    def test_no_ocr_flag(self):
        args = _child_args(build("u", no_ocr=True), "u")
        self.assertIn("--no-ocr", args)


if __name__ == "__main__":
    unittest.main()
