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


class SinglePassTest(unittest.TestCase):
    """规则之间不能互相污染：每个位置只匹配一次、替换一次。"""

    def test_already_correct_form_not_extended(self):
        # FD->FDE 不能把已经正确的 FDE 再补一个 E
        for text in ("FDE", "FDEE"):
            out = correct_transcript(text)["corrected"]
            self.assertNotIn("FDEEE", out, out)
            self.assertIn("FDE", out)

    def test_annotation_not_appended_twice(self):
        for text in ("SOTA", "SOTA（State-of-the-Art）"):
            out = correct_transcript(text)["corrected"]
            self.assertEqual(out.count("State-of-the-Art"), 1, out)

    def test_book_title_not_wrapped_twice(self):
        out = correct_transcript("《女儿红》")["corrected"]
        self.assertEqual(out, "《女儿红》")

    def test_correct_word_not_prefixed(self):
        # 源项目->开源项目 不能把已经正确的「开源项目」改成「开开源项目」
        out = correct_transcript("这个开源项目")["corrected"]
        self.assertEqual(out, "这个开源项目")

    def test_reversed_rules_removed(self):
        # 这两条方向写反（同期短语规则都指向相反方向），必须不再生效
        self.assertNotIn("县城", correct_transcript("现成的程序")["corrected"])
        self.assertNotIn("通义千问", correct_transcript("几千万家企业")["corrected"])

    def test_idempotent(self):
        text = "它在KTAP上刚拿到三万多颗星，叫Deep Tutor，SOTA很强，FDE很重要，开源项目很多。"
        once = correct_transcript(text)["corrected"]
        twice = correct_transcript(once)["corrected"]
        self.assertEqual(once, twice)


class NewlyAddedCorrectionsTest(unittest.TestCase):
    """2026-10-20 从「第275集 AI教育」那期补的误听。"""

    def test_github_misheard_as_ktap(self):
        self.assertIn("GitHub", correct_transcript("它在KTAP上拿到三万多颗星")["corrected"])

    def test_tool_name_variants(self):
        for text in ("叫Deep Tutor", "构建这个领域的Deep Shooter"):
            self.assertIn("DeepTutor", correct_transcript(text)["corrected"])

    def test_feed_and_idiom(self):
        self.assertIn("投喂给", correct_transcript("资料投位给他")["corrected"])
        self.assertIn("起承转合", correct_transcript("需要启程转合")["corrected"])


if __name__ == "__main__":
    unittest.main()
