"""
离线回归测试。运行：venv/bin/python -m unittest discover -s tests -t .
"""
import unittest
from unittest import mock


class OfflineTestCase(unittest.TestCase):
    """禁止测试期间通过 requests 发起任何真实网络请求"""

    def setUp(self):
        patcher = mock.patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("tests must not access the network"),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
