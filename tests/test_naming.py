import unittest

from douyin_parse.naming import fmt_duration, safe_name


class SafeNameTest(unittest.TestCase):
    def test_replaces_illegal_chars(self):
        self.assertEqual(safe_name('a/b:c*d?e"f<g>h|i'), "a_b_c_d_e_f_g_h_i")

    def test_strips_and_truncates(self):
        self.assertEqual(len(safe_name("x" * 100)), 40)
        self.assertEqual(safe_name("  .abc.  "), "abc")

    def test_empty_becomes_default(self):
        self.assertEqual(safe_name(""), "未命名内容")


class FmtDurationTest(unittest.TestCase):
    def test_seconds_only(self):
        self.assertEqual(fmt_duration(28), "28秒")

    def test_minutes(self):
        self.assertEqual(fmt_duration(752), "12分32秒")

    def test_invalid(self):
        self.assertEqual(fmt_duration(0), "—")
        self.assertEqual(fmt_duration(None), "—")


if __name__ == "__main__":
    unittest.main()
