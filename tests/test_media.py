import unittest
from unittest import mock

from douyin_parse import media


class DownloadRetryTest(unittest.TestCase):
    """下载失败重试：瞬时网络错误要重试，HTTP 状态码错误不重试。"""

    def test_success_returns_size(self):
        with mock.patch.object(media, "_download_once", return_value=(True, "", 2048)):
            ok, err, size = media.download_to_file("u", "out.bin", {}, min_bytes=1, retries=2)
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertEqual(size, 2048)

    def test_transient_error_is_retried(self):
        calls = []

        def fake(url, output_path, headers, min_bytes, timeout):
            calls.append(1)
            if len(calls) < 3:
                return False, "SSLError(EOF)", 0
            return True, "", 4096

        with mock.patch.object(media, "_download_once", side_effect=fake):
            with mock.patch.object(media.time, "sleep"), mock.patch("builtins.print"):
                ok, err, size = media.download_to_file("u", "out.bin", {}, retries=2)
        self.assertTrue(ok)
        self.assertEqual(size, 4096)
        self.assertEqual(len(calls), 3, "瞬时错误应重试到成功")

    def test_http_error_is_not_retried(self):
        calls = []

        def fake(url, output_path, headers, min_bytes, timeout):
            calls.append(1)
            return False, "HTTP 403", 0

        with mock.patch.object(media, "_download_once", side_effect=fake):
            with mock.patch.object(media.time, "sleep"), mock.patch("builtins.print"):
                ok, err, size = media.download_to_file("u", "out.bin", {}, retries=2)
        self.assertFalse(ok)
        self.assertEqual(err, "HTTP 403")
        self.assertEqual(len(calls), 1, "HTTP 状态码错误重试也不会变，不应重试")

    def test_gives_up_after_retries(self):
        with mock.patch.object(media, "_download_once", return_value=(False, "连接重置", 0)) as m:
            with mock.patch.object(media.time, "sleep"), mock.patch("builtins.print"):
                ok, err, size = media.download_to_file("u", "out.bin", {}, retries=2)
        self.assertFalse(ok)
        self.assertEqual(err, "连接重置")
        self.assertEqual(m.call_count, 3, "重试次数 = retries + 1 次首试")


class RecordDeviceTest(unittest.TestCase):
    def test_prefers_default_input(self):
        fake_sd = mock.Mock()
        fake_sd.default.device = [3, 0]
        self.assertEqual(media.choose_record_device(fake_sd), 3)

    def test_falls_back_to_first_input_device(self):
        fake_sd = mock.Mock()
        fake_sd.default.device = [-1, 0]
        fake_sd.query_devices.return_value = [
            {"name": "out", "max_input_channels": 0},
            {"name": "mic", "max_input_channels": 2},
        ]
        self.assertEqual(media.choose_record_device(fake_sd), 1)

    def test_returns_none_without_input_device(self):
        fake_sd = mock.Mock()
        fake_sd.default.device = [-1, 0]
        fake_sd.query_devices.return_value = [{"name": "out", "max_input_channels": 0}]
        self.assertIsNone(media.choose_record_device(fake_sd))


if __name__ == "__main__":
    unittest.main()
