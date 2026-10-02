"""
推送记忆：跨天去重、AI 判断重复/后续进展、只在真正推送后记录
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest import mock

from ai_filter import AIFilter
from feishu import FeishuBot
from fetchers.base import ContentItem
from memory import PushHistory
from tests import OfflineTestCase

with mock.patch("dotenv.load_dotenv"):
    import main

DAY1 = datetime(2026, 10, 1, 7, 0)
DAY2 = datetime(2026, 10, 2, 7, 0)


def pushed(i=1, **kw):
    defaults = dict(id=f"p{i}", title="OpenAI releases GPT-6 with 2M context", url="https://openai.com/index/gpt-6/",
                    source="OpenAI Blog", extra={"merged_urls": ["https://news.ycombinator.com/item?id=9"]})
    defaults.update(kw)
    item = ContentItem(**defaults)
    item.ai_title, item.ai_category = "OpenAI 发布 GPT-6", "模型发布"
    return item


class PushHistoryTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "state", "history.json")

    def test_roundtrip_and_ttl(self):
        old = PushHistory(self.path, ttl_days=7, today=datetime(2026, 9, 20))
        old.record([pushed(0, title="Ancient news", url="https://example.com/old")])
        old.save()
        day1 = PushHistory(self.path, ttl_days=7, today=DAY1).load()
        self.assertEqual(day1.entries, [])  # 超过 7 天的记录被清理
        day1.record([pushed()])
        day1.save()

        day2 = PushHistory(self.path, ttl_days=7, today=DAY2).load()
        self.assertEqual(len(day2.entries), 1)
        self.assertEqual(day2.entries[0]["date"], "2026-10-01")
        self.assertIn("https://openai.com/index/gpt-6", day2.entries[0]["urls"])
        self.assertEqual(day2.headlines(), ["10-01 OpenAI 发布 GPT-6"])

    def test_corrupt_file_degrades_to_empty(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{not json")
        history = PushHistory(self.path, today=DAY2).load()
        self.assertEqual((history.entries, history.load_error), ([], "JSONDecodeError"))

    def test_split_seen_by_url_variants_and_title(self):
        history = PushHistory(self.path, today=DAY2)
        history.today = DAY1.date()
        history.record([pushed()])
        same_url = ContentItem(id="a", title="Totally different words", source="Hacker News",
                               url="https://openai.com/index/gpt-6?utm_source=hn")
        via_hn = ContentItem(id="b", title="Discussion", source="Hacker News",
                             url="https://news.ycombinator.com/item?id=9")
        same_title = ContentItem(id="c", title="OpenAI releases GPT-6 with 2M context!", source="The Verge AI",
                                 url="https://theverge.com/gpt6")
        new = ContentItem(id="d", title="Anthropic ships new Claude tools", source="Anthropic",
                          url="https://anthropic.com/news/tools")
        fresh, seen = history.split_seen([same_url, via_hn, same_title, new])
        self.assertEqual([i.id for i in fresh], ["d"])
        self.assertEqual([i.id for i in seen], ["a", "b", "c"])
        self.assertEqual(seen[0].extra["seen_on"], "2026-10-01")


class NoveltyTest(OfflineTestCase):

    def _run(self, response, items):
        with mock.patch.object(AIFilter, "_call_llm", return_value=response) as llm, \
                contextlib.redirect_stdout(io.StringIO()):
            ai = AIFilter(provider="deepseek", history=["10-01 OpenAI 发布 GPT-6"])
            top = ai.filter_top(items, top_n=10, min_score=6)
        return top, llm

    def test_repeat_dropped_followup_marked_missing_defaults_to_new(self):
        items = [ContentItem(id=f"i{i}", title=f"T{i}", url=f"https://e.com/{i}", source="S") for i in range(4)]
        results = [
            {"index": 0, "score": 9, "category": "模型发布", "title_cn": "重复", "summary": "s", "novelty": "repeat"},
            {"index": 1, "score": 8, "category": "模型发布", "title_cn": "后续", "summary": "s", "novelty": "followup"},
            {"index": 2, "score": 7, "category": "行业动态", "title_cn": "新的", "summary": "s"},
            {"index": 3, "score": 7, "category": "行业动态", "title_cn": "乱填", "summary": "s", "novelty": "maybe"},
        ]
        top, llm = self._run(json.dumps(results), items)
        self.assertEqual([i.ai_title for i in top], ["后续", "新的", "乱填"])
        self.assertTrue(top[0].extra["followup"])
        self.assertEqual(top[2].extra["novelty"], "new")
        prompt = llm.call_args[0][0]
        self.assertIn("10-01 OpenAI 发布 GPT-6", prompt)
        self.assertIn('"followup"', prompt)

    def test_empty_history_and_single_prompt_render(self):
        self.assertEqual(AIFilter(provider="deepseek").history_text, "(无)")
        AIFilter.SCORE_PROMPT.format(title="t", source="s", signals="x", description="d", history="(无)")

    def test_followup_label_in_card(self):
        item = pushed()
        item.ai_summary = "新进展"
        item.extra["followup"] = True
        with mock.patch.object(FeishuBot, "_send", return_value=True) as send:
            FeishuBot(webhook_url="https://example.invalid/hook").send_daily_digest([item])
        self.assertIn("🔄 后续 · OpenAI 发布 GPT-6", json.dumps(send.call_args[0][0], ensure_ascii=False))


class MainMemoryTest(OfflineTestCase):

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "history.json")
        for patcher in (
            mock.patch.object(main, "fetch_all_sources", side_effect=lambda *_: [pushed()]),
            mock.patch.object(main, "generate_rss_feed", return_value=""),
            mock.patch.object(main, "write_run_log"),
            mock.patch.object(main.config, "HISTORY_PATH", self.path),
            mock.patch.object(main.config, "FEISHU_WEBHOOK_URL", "https://example.invalid/hook"),
            mock.patch.object(main.config, "TOP_N_ITEMS", main.config.TOP_N_ITEMS),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _run(self, *args):
        with mock.patch("sys.argv", ["main.py", "--no-ai", *args]), \
                mock.patch.object(main.FeishuBot, "send_daily_digest", return_value=True) as send, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = main.main()
        return code, send, out.getvalue()

    def test_second_run_does_not_repush_same_story(self):
        code, send, _ = self._run()
        self.assertEqual(code, 0)
        send.assert_called_once()
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["entries"]), 1)

        code, send, log = self._run()
        self.assertEqual(code, 0)
        send.assert_not_called()
        self.assertIn("今天没有未推送过的新内容", log)

    def test_dry_run_and_no_memory_do_not_record(self):
        self._run("--dry-run")
        self.assertFalse(os.path.exists(self.path))
        self._run("--no-memory")
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()
