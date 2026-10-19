import unittest

from douyin_parse.correct import KEEP_AS_IS, correct_transcript


class CorrectTranscriptTest(unittest.TestCase):
    def test_fixes_known_asr_error(self):
        result = correct_transcript("我用的是cloud")
        self.assertIn("Claude", result["corrected"])
        self.assertEqual(result["stats"]["total_corrections"], 1)

    def test_keeps_whitelisted_words(self):
        for word in KEEP_AS_IS[:5]:
            result = correct_transcript(f"今天聊{word}")
            self.assertIn(word, result["corrected"])

    def test_returns_original_text(self):
        text = "一个字都不用改"
        result = correct_transcript(text)
        self.assertEqual(result["original"], text)

    def test_stats_count_length(self):
        result = correct_transcript("abc")
        self.assertEqual(result["stats"]["original_length"], 3)


if __name__ == "__main__":
    unittest.main()
