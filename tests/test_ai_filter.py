"""
AI 返回结果校验与有界回退
"""
import json
import unittest
from unittest import mock

import config
from ai_filter import AIFilter
from fetchers.base import ContentItem
from tests import OfflineTestCase


def _items(n=3):
    return [
        ContentItem(id=f"t_{i}", title=f"Title {i}", url=f"https://example.com/{i}", source="Test")
        for i in range(n)
    ]


def _result(index, score=8.0, category="产品发布", title="标题", summary="摘要"):
    return {"index": index, "score": score, "category": category, "title_cn": title, "summary": summary}


SINGLE_OK = json.dumps({"score": 7, "category": "行业动态", "title_cn": "单条标题", "summary": "单条摘要"})


class FakeLLM:
    """按提示词类型返回预设响应，并记录调用"""

    def __init__(self, batch_response, single_response=SINGLE_OK):
        self.batch_response = batch_response
        self.single_response = single_response
        self.batch_calls = 0
        self.single_prompts = []

    def __call__(self, prompt):
        if "待评估内容列表" in prompt:
            self.batch_calls += 1
            return self.batch_response
        self.single_prompts.append(prompt)
        return self.single_response


class AIFilterValidationTest(OfflineTestCase):

    def _score(self, llm, items):
        with mock.patch.object(AIFilter, "_call_llm", side_effect=llm), \
                mock.patch("builtins.print"):
            return AIFilter(provider="deepseek").score_batch(items)

    def test_valid_batch_applies_all_results_without_fallback(self):
        items = _items()
        llm = FakeLLM("```json\n" + json.dumps([_result(i, score=6 + i) for i in range(3)]) + "\n```")
        self._score(llm, items)
        self.assertEqual(llm.single_prompts, [])
        self.assertEqual([it.ai_score for it in items], [6.0, 7.0, 8.0])
        self.assertEqual(items[0].ai_category, "产品发布")
        self.assertEqual(items[0].ai_title, "标题")

    def test_negative_index_does_not_touch_last_item(self):
        items = _items()
        llm = FakeLLM(json.dumps([_result(0), _result(1), _result(-1, score=10, title="错位")]))
        self._score(llm, items)
        self.assertEqual(len(llm.single_prompts), 1)
        self.assertIn("Title 2", llm.single_prompts[0])
        self.assertEqual(items[2].ai_title, "单条标题")
        self.assertEqual(items[2].ai_score, 7.0)
        self.assertEqual(items[0].ai_score, 8.0)

    def test_empty_array_retries_each_item_once(self):
        items = _items()
        llm = FakeLLM("[]")
        self._score(llm, items)
        self.assertEqual(llm.batch_calls, 1)
        self.assertEqual(len(llm.single_prompts), 3)
        self.assertTrue(all(it.ai_score == 7.0 for it in items))

    def test_non_array_response_falls_back_per_item(self):
        items = _items(2)
        llm = FakeLLM(json.dumps({"items": [_result(0), _result(1)]}))
        self._score(llm, items)
        self.assertEqual(len(llm.single_prompts), 2)

    def test_invalid_indexes_are_rejected(self):
        for bad_index in (True, "0", 1.0, 3, None):
            with self.subTest(index=bad_index):
                items = _items()
                results = [_result(1), _result(2), _result(0)]
                results[2]["index"] = bad_index
                llm = FakeLLM(json.dumps(results))
                self._score(llm, items)
                self.assertEqual(len(llm.single_prompts), 1)
                self.assertIn("Title 0", llm.single_prompts[0])
                self.assertEqual(items[1].ai_score, 8.0)

    def test_duplicate_index_invalidates_that_item_only(self):
        items = _items()
        llm = FakeLLM(json.dumps([_result(0), _result(0, score=2), _result(1), _result(2)]))
        self._score(llm, items)
        self.assertEqual(len(llm.single_prompts), 1)
        self.assertIn("Title 0", llm.single_prompts[0])
        self.assertEqual(items[0].ai_score, 7.0)
        self.assertEqual(items[1].ai_score, 8.0)

    def test_invalid_fields_retry_only_that_item(self):
        bad_results = {
            "score_too_high": _result(1, score=11),
            "score_too_low": _result(1, score=0.5),
            "score_nan": _result(1, score=float("nan")),
            "score_string": _result(1, score="9"),
            "score_bool": _result(1, score=True),
            "unknown_category": _result(1, category="开源项目"),
            "title_not_string": _result(1, title=["x"]),
            "summary_missing": {k: v for k, v in _result(1).items() if k != "summary"},
            "not_object": "oops",
        }
        for name, bad in bad_results.items():
            with self.subTest(name):
                items = _items()
                llm = FakeLLM(json.dumps([_result(0, score=9), bad, _result(2, score=6)]))
                self._score(llm, items)
                self.assertEqual(len(llm.single_prompts), 1)
                self.assertIn("Title 1", llm.single_prompts[0])
                self.assertEqual(items[0].ai_score, 9.0)
                self.assertEqual(items[2].ai_score, 6.0)
                self.assertEqual(items[1].ai_score, 7.0)

    def test_invalid_single_retry_is_bounded_and_filtered_out(self):
        items = _items()
        bad_single = json.dumps({"score": 42, "category": "行业动态", "title_cn": "x", "summary": "y"})
        llm = FakeLLM("not json", single_response=bad_single)
        with mock.patch.object(AIFilter, "_call_llm", side_effect=llm), \
                mock.patch("builtins.print"):
            top = AIFilter(provider="deepseek").filter_top(items, top_n=10, min_score=6)
        self.assertEqual(llm.batch_calls, 1)
        self.assertEqual(len(llm.single_prompts), 3)
        self.assertEqual(top, [])
        self.assertTrue(all(it.ai_score == 0.0 and it.ai_category == "" for it in items))

    def test_empty_title_falls_back_to_original(self):
        items = _items(1)
        llm = FakeLLM(json.dumps([_result(0, title="  ")]))
        self._score(llm, items)
        self.assertEqual(items[0].ai_title, "Title 0")


class PromptTest(unittest.TestCase):

    def test_prompts_constrain_summary_to_supplied_facts(self):
        for prompt in (AIFilter.SCORE_PROMPT, AIFilter.BATCH_PROMPT):
            self.assertIn("不得编造", prompt)
            self.assertIn("描述为空或信息很少时", prompt)

    def test_prompt_example_category_is_allowed(self):
        self.assertIn('"category": "产品发布"', AIFilter.BATCH_PROMPT)
        self.assertNotIn('"category": "开源项目"', AIFilter.BATCH_PROMPT)
        for category in config.AI_CATEGORIES:
            self.assertIn(category, AIFilter.BATCH_PROMPT)


if __name__ == "__main__":
    unittest.main()
