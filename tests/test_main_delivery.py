"""
main.py 推送结果与退出码
"""
import contextlib
import io
import unittest
from unittest import mock

from tests import OfflineTestCase

# main 在导入时会调用 load_dotenv()，测试中禁止读取真实 .env
with mock.patch("dotenv.load_dotenv"):
    import main

WEBHOOK = "https://example.invalid/feishu-hook"


def _items():
    return [
        main.ContentItem(
            id=f"hn_{i}",
            title=f"New AI agent framework {i}",
            url=f"https://example.com/{i}",
            source="Hacker News",
            score=100 - i,
        )
        for i in range(3)
    ]


class MainDeliveryTest(OfflineTestCase):

    def setUp(self):
        super().setUp()
        for patcher in (
            mock.patch.object(main, "fetch_all_sources", side_effect=_items),
            mock.patch.object(main, "generate_rss_feed", return_value=""),
            mock.patch.object(main.config, "TOP_N_ITEMS", main.config.TOP_N_ITEMS),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _run(self, *args):
        with mock.patch("sys.argv", ["main.py", "--no-ai", *args]), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return main.main()

    def _mock_feishu_response(self, body):
        resp = mock.Mock()
        resp.json.return_value = body
        return mock.patch("feishu.requests.post", return_value=resp)

    def test_configured_delivery_failure_exits_nonzero(self):
        with mock.patch.object(main.config, "FEISHU_WEBHOOK_URL", WEBHOOK), \
                self._mock_feishu_response({"code": 19001, "msg": "invalid"}) as post:
            self.assertEqual(self._run(), 1)
        post.assert_called_once()

    def test_configured_delivery_exception_exits_nonzero(self):
        with mock.patch.object(main.config, "FEISHU_WEBHOOK_URL", WEBHOOK), \
                mock.patch("feishu.requests.post", side_effect=OSError("boom")):
            self.assertEqual(self._run(), 1)

    def test_configured_delivery_success_exits_zero(self):
        with mock.patch.object(main.config, "FEISHU_WEBHOOK_URL", WEBHOOK), \
                self._mock_feishu_response({"code": 0}) as post:
            self.assertEqual(self._run(), 0)
        post.assert_called_once()

    def test_missing_webhook_is_skipped_successfully(self):
        with mock.patch.object(main.config, "FEISHU_WEBHOOK_URL", ""), \
                mock.patch("feishu.requests.post") as post:
            self.assertEqual(self._run(), 0)
        post.assert_not_called()

    def test_dry_run_and_no_push_skip_delivery_successfully(self):
        for flag in ("--dry-run", "--no-push"):
            with self.subTest(flag=flag), \
                    mock.patch.object(main.config, "FEISHU_WEBHOOK_URL", WEBHOOK), \
                    mock.patch("feishu.requests.post") as post:
                self.assertEqual(self._run(flag), 0)
                post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
