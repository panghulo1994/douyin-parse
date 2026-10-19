import os
import unittest
from unittest import mock

from douyin_parse.config import build, resolve_ai


class ResolveAiTest(unittest.TestCase):
    def test_none_disables(self):
        cfg = resolve_ai("none")
        self.assertEqual(cfg["provider"], "")

    def test_env_pair_wins(self):
        env = {"AI_API_KEY": "k", "AI_API_URL": "https://example.com/v1", "AI_MODEL": "m"}
        with mock.patch.dict(os.environ, env, clear=False):
            cfg = resolve_ai("auto")
        self.assertEqual(cfg["url"], "https://example.com/v1")
        self.assertEqual(cfg["model"], "m")

    def test_deepseek_key_found(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "d"}, clear=False):
            os.environ.pop("AI_API_KEY", None)
            os.environ.pop("AI_API_URL", None)
            os.environ.pop("DOUYIN_AI_PROVIDER", None)
            cfg = resolve_ai("auto")
        self.assertIn(cfg["provider"], ("deepseek", "mimo"))


class BuildTest(unittest.TestCase):
    def test_defaults(self):
        cfg = build("https://v.douyin.com/x/", out="./out")
        self.assertTrue(cfg.output_base.endswith("out"))
        self.assertEqual(cfg.whisper_model, "small")
        self.assertFalse(cfg.disable_ocr)

    def test_no_ocr_flag(self):
        self.assertTrue(build("u", no_ocr=True).disable_ocr)


if __name__ == "__main__":
    unittest.main()
