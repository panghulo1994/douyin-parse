import unittest

from douyin_parse.transcribe import available_backends, pick_backend


class PickBackendTest(unittest.TestCase):
    def test_explicit_choice_wins(self):
        self.assertEqual(pick_backend("whisper"), "whisper")
        self.assertEqual(pick_backend("faster-whisper"), "faster-whisper")

    def test_auto_returns_installed_backend(self):
        self.assertIn(pick_backend("auto"), ("", "faster-whisper", "whisper"))

    def test_available_backends_is_list(self):
        backends = available_backends()
        self.assertIsInstance(backends, list)
        for item in backends:
            self.assertIn(item, ("faster-whisper", "whisper"))


if __name__ == "__main__":
    unittest.main()
