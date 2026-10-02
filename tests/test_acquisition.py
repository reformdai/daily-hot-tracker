"""
信息获取增强：新信源、URL 归一与跨源合并、分级/时效评分、候选多样性、正文补抓、并发抓取
"""
import contextlib
import io
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from ai_filter import AIFilter
from enrich import enrich_items, extract_body, html_to_text, markdown_to_text
from fetchers.base import ContentItem
from fetchers.hn_search import HNSearchFetcher
from fetchers.huggingface import HuggingFaceFetcher
from fetchers.list_sources import WebListFetcher
from pipeline import (
    annotate_engagement,
    apply_quality_score,
    canonical_url,
    deduplicate_items,
    filter_fresh,
    select_diverse_candidates,
    source_family,
)
from tests import OfflineTestCase

with mock.patch("dotenv.load_dotenv"):
    import main

NOW = datetime(2026, 10, 2, 12, 0)


def item(i, source="Hacker News", url=None, title=None, score=0, hours_ago=None, **extra):
    return ContentItem(
        id=f"t_{source}_{i}", title=title or f"Unique headline number {i} about things",
        url=url or f"https://example.com/{source.replace(' ', '')}/{i}", source=source, score=score,
        published_at=NOW - timedelta(hours=hours_ago) if hours_ago is not None else None,
        extra=dict(extra),
    )


def json_response(data):
    resp = mock.Mock()
    resp.json.return_value = data
    return resp


class KeywordPrefilterTest(unittest.TestCase):

    def setUp(self):
        self.patterns = main._keyword_patterns(["AI", "LLM", "agent", "大模型"])

    def match(self, title):
        return main.matches_keywords(ContentItem(id="x", title=title, url="u", source="s"), self.patterns)

    def test_short_keyword_needs_word_boundary(self):
        self.assertFalse(self.match("He said they paid by email"))
        self.assertTrue(self.match("New AI-powered editor"))
        self.assertTrue(self.match("AI: what changed"))

    def test_plural_and_chinese(self):
        self.assertTrue(self.match("Small LLMs beat big ones"))
        self.assertTrue(self.match("Coding agents in production"))
        self.assertTrue(self.match("国产大模型发布"))
        self.assertFalse(self.match("Agentic workflows"))  # 不做任意后缀匹配

    def test_exempt_sources_skip_keyword_filter(self):
        paper = ContentItem(id="p", title="Sparse convolution for point clouds", url="u", source="ArXiv")
        other = ContentItem(id="o", title="Sparse convolution for point clouds", url="v", source="Hacker News")
        with mock.patch.object(main.config, "KEYWORD_EXEMPT_SOURCES", ["ArXiv"]), \
                contextlib.redirect_stdout(io.StringIO()):
            kept = main.prefilter_by_keywords(apply_quality_score([paper, other], now=NOW))
        self.assertEqual([i.id for i in kept], ["p"])


class CanonicalUrlTest(unittest.TestCase):

    def test_tracking_params_fragments_and_hosts(self):
        self.assertEqual(
            canonical_url("http://www.Example.com/post/?utm_source=x&ref=hn&id=2#comments"),
            "https://example.com/post?id=2",
        )

    def test_arxiv_versions_and_hf_papers_unify(self):
        ids = {
            canonical_url("https://arxiv.org/abs/2409.01234v3"),
            canonical_url("http://export.arxiv.org/pdf/2409.01234"),
            canonical_url("https://huggingface.co/papers/2409.01234"),
        }
        self.assertEqual(ids, {"arxiv:2409.01234"})
        self.assertNotEqual(canonical_url("https://huggingface.co/org/model-2409.01234"), "arxiv:2409.01234")

    def test_github_repo_subpages_collapse(self):
        self.assertEqual(canonical_url("https://github.com/Owner/Repo/tree/main/src"), "https://github.com/owner/repo")


class MergeAndRankTest(unittest.TestCase):

    def test_same_story_across_sources_merges_into_official_lead(self):
        blog = item(1, "OpenAI Blog", url="https://openai.com/index/new-model/", title="Introducing our new model",
                    hours_ago=30, tier="T1")
        blog.description = "Short."
        hn = item(2, "Hacker News", url="https://openai.com/index/new-model?utm_source=hn", title="OpenAI new model",
                  score=800, hours_ago=2, hn_url="https://news.ycombinator.com/item?id=2")
        hn.description = "A much longer description of the release with details."
        reddit_a = item(3, "Reddit r/LocalLLaMA", url="https://openai.com/index/new-model", title="new model thread")
        reddit_b = item(4, "Reddit r/MachineLearning", url="https://openai.com/index/new-model/#x", title="discussion")

        merged = deduplicate_items(annotate_engagement([blog, hn, reddit_a, reddit_b]))

        self.assertEqual(len(merged), 1)
        lead = merged[0]
        self.assertIs(lead, blog)
        self.assertEqual(lead.score, 800)
        self.assertEqual(lead.description, hn.description)
        self.assertEqual(lead.extra["families"], ["Hacker News", "OpenAI Blog", "Reddit"])
        self.assertEqual(lead.extra["source_count"], 3)
        self.assertEqual(lead.extra["hn_url"], "https://news.ycombinator.com/item?id=2")
        self.assertEqual(lead.extra["latest_at"], (NOW - timedelta(hours=2)).isoformat())

    def test_arxiv_and_hf_paper_merge(self):
        arxiv = item(1, "ArXiv", url="http://arxiv.org/abs/2409.01234v1", title="Scaling laws for agents")
        hf = item(2, "Hugging Face Papers", url="https://huggingface.co/papers/2409.01234", title="Scaling Laws for Agents!",
                  score=120)
        merged = deduplicate_items(annotate_engagement([arxiv, hf]), tiers={"ArXiv": "T2", "Hugging Face Papers": "T2"})
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].extra["source_count"], 2)

    def test_engagement_is_normalized_within_family(self):
        items = [item(i, "Hacker News", score=s) for i, s in enumerate([10, 500, 100])]
        items += [item(9, "GitHub Trending", score=3000), item(10, "OpenAI Blog")]
        annotate_engagement(items)
        self.assertEqual([i.extra["engagement"] for i in items[:3]], [round(1 / 3, 3), 1.0, round(2 / 3, 3)])
        self.assertEqual(items[3].extra["engagement"], 1.0)
        self.assertEqual(items[4].extra["engagement"], 0.0)

    def test_fresh_official_corroborated_beats_stale_community(self):
        official = item(1, "OpenAI Blog", hours_ago=3, tier="T1", source_count=2, engagement=0.5)
        stale = item(2, "Reddit r/startups", hours_ago=60, engagement=1.0)
        apply_quality_score([official, stale], now=NOW)
        self.assertGreater(official.extra["final_rank_score"], stale.extra["final_rank_score"])
        self.assertEqual(stale.extra["tier"], "T3")
        self.assertTrue(0 <= stale.extra["final_rank_score"] <= 100)

    def test_freshness_uses_latest_sighting_and_keeps_undated(self):
        old_but_trending = item(1, hours_ago=200, latest_at=(NOW - timedelta(hours=1)).isoformat())
        old = item(2, hours_ago=100)
        undated = item(3)
        kept, dropped = filter_fresh([old_but_trending, old, undated], 72, now=NOW)
        self.assertEqual([i.id for i in kept], [old_but_trending.id, undated.id])
        self.assertEqual(dropped, [old])
        self.assertEqual(filter_fresh([old], 0, now=NOW), ([old], []))

    def test_freshness_override_per_family(self):
        paper = item(1, "ArXiv", hours_ago=100)
        post = item(2, "Hacker News", hours_ago=100)
        kept, dropped = filter_fresh([paper, post], 72, now=NOW, overrides={"ArXiv": 120})
        self.assertEqual((kept, dropped), ([paper], [post]))

    def test_diverse_candidates_cap_family_then_fill(self):
        items = [item(i, "Reddit r/a" if i % 2 else "Reddit r/b") for i in range(6)] + [item(9, "ArXiv")]
        for rank, it in enumerate(items):
            it.extra["final_rank_score"] = 100 - rank if it.source != "ArXiv" else 1
        picked = select_diverse_candidates(items, limit=3, per_family_cap=2)
        self.assertEqual([source_family(i.source) for i in picked], ["Reddit", "Reddit", "ArXiv"])
        filled = select_diverse_candidates(items, limit=5, per_family_cap=2)
        self.assertEqual(len(filled), 5)


class NewSourceTest(OfflineTestCase):

    def test_hn_search_merges_queries_and_isolates_failures(self):
        hit = {"objectID": "42", "title": "Claude &amp; agents", "url": "https://example.com/a", "points": 300,
               "num_comments": 120, "created_at_i": 1790000000, "author": "pg", "story_text": None}
        ask = {"objectID": "43", "title": "Ask HN: LLM evals?", "url": None, "points": 50,
               "story_text": "<p>How do you <b>evaluate</b>?</p>", "created_at_i": 1790000100}
        responses = [json_response({"hits": [hit, ask]}), None, json_response({"hits": [hit]})]
        with mock.patch("fetchers.hn_search.get_with_retry", side_effect=responses), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            items = HNSearchFetcher(queries=["AI", "LLM", "Claude"]).fetch(limit=10)
        self.assertEqual([i.id for i in items], ["hn_42", "hn_43"])
        self.assertEqual(items[0].title, "Claude & agents")
        self.assertEqual(items[0].comments, 120)
        self.assertIsNotNone(items[0].published_at)
        self.assertEqual(items[1].url, "https://news.ycombinator.com/item?id=43")
        self.assertEqual(items[1].description, "How do you evaluate ?")
        self.assertIn("2/3 queries", out.getvalue())

    def test_hf_papers_and_models(self):
        papers = [
            {"title": "Paper A", "summary": "We study agents.", "publishedAt": "2026-10-01T08:00:00.000Z",
             "numComments": 4, "paper": {"id": "2410.00001", "upvotes": 12, "authors": [{"name": "A"}]}},
            {"title": "Paper B", "paper": {"id": "2410.00002", "upvotes": 80, "authors": []}},
            {"paper": {}},
        ]
        recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        models = [
            {"id": "org/new-model", "trendingScore": 90, "createdAt": recent,
             "pipeline_tag": "text-generation", "tags": ["transformers", "license:mit", "moe"]},
            {"id": "org/old-model", "trendingScore": 99, "createdAt": "2024-01-01T00:00:00.000Z"},
        ]
        with mock.patch("fetchers.huggingface.get_with_retry",
                        side_effect=[json_response(papers), json_response(models)]), \
                contextlib.redirect_stdout(io.StringIO()):
            items = HuggingFaceFetcher(model_max_age_days=14).fetch(limit=10)
        self.assertEqual([i.title for i in items], ["Paper B", "org/new-model", "Paper A"])
        self.assertEqual(items[0].url, "https://huggingface.co/papers/2410.00002")
        self.assertEqual(items[1].description, "text-generation · transformers, moe")
        self.assertIsNone(items[1].published_at)
        self.assertEqual(items[2].published_at, datetime(2026, 10, 1, 8, 0))

    def test_list_source_tier_is_passed_through(self):
        html = '<a href="/news/a"><span class="t">AI news</span></a>'
        resp = mock.Mock(content=html.encode(), url="https://example.com/news")
        config = {"name": "Example", "url": "https://example.com/news", "tier": "T1",
                  "item_selector": "a", "title_selector": ".t"}
        with mock.patch("fetchers.list_sources.get_with_retry", return_value=resp), \
                contextlib.redirect_stdout(io.StringIO()):
            items = WebListFetcher([config]).fetch(5)
        self.assertEqual(items[0].extra["tier"], "T1")


class EnrichTest(OfflineTestCase):

    def test_markdown_readme_is_cleaned(self):
        md = ("---\nlicense: mit\n---\n# Title\n[![badge](https://x/b.svg)](https://x)\n"
              "<p align=center><img src=a.png></p>\n```bash\npip install x\n```\n"
              "A fast inference engine for [large models](https://x.dev) on consumer GPUs.\n- short\n")
        self.assertEqual(markdown_to_text(md), "A fast inference engine for large models on consumer GPUs.")

    def test_html_prefers_article_paragraphs(self):
        html = ('<html><head><meta property="og:description" content="Meta  summary"></head><body>'
                '<nav><p>Navigation menu item that is long enough to count</p></nav>'
                '<article><p>The model scores 90 on the benchmark and ships with open weights today.</p>'
                '<p>short</p></article></body></html>')
        meta, body = html_to_text(html)
        self.assertEqual(meta, "Meta summary")
        self.assertEqual(body, "The model scores 90 on the benchmark and ships with open weights today.")

    def test_github_uses_raw_readme_and_skip_hosts(self):
        readme = ("An agent framework for building reliable multi-step workflows with tools, memory "
                  "and evaluation built in, designed for production teams.").encode()
        with mock.patch("enrich._get", return_value=(readme, "text/plain")) as get:
            text, via = extract_body("https://github.com/owner/repo")
        self.assertEqual(via, "readme")
        self.assertIn("agent framework", text)
        self.assertEqual(get.call_args[0][0], "https://raw.githubusercontent.com/owner/repo/HEAD/README.md")
        with mock.patch("enrich._get") as get:
            self.assertEqual(extract_body("https://x.com/someone/status/1"), ("", "skipped-host"))
        get.assert_not_called()

    def test_enrich_only_short_items_and_feeds_prompt(self):
        short = ContentItem(id="a", title="T", url="https://example.com/a", source="Hacker News")
        rich = ContentItem(id="b", title="T", url="https://example.com/b", source="Blog", description="x" * 400)
        paper = ContentItem(id="c", title="T", url="https://arxiv.org/abs/1", source="ArXiv")
        body = "Body text " * 30
        with mock.patch("enrich.extract_body", return_value=(body, "html")) as extract:
            stats = enrich_items([short, rich, paper], min_description=280, max_chars=100)
        extract.assert_called_once()
        self.assertEqual(stats, {"html": 1})
        self.assertEqual(len(short.extra["body"]), 100)
        self.assertIn("【原文摘录】Body text", AIFilter._context(short, 600))
        self.assertEqual(AIFilter._context(paper, 600), "(无描述)")

    def test_signals_line(self):
        it = ContentItem(id="a", title="T", url="u", source="OpenAI Blog", score=300, comments=40,
                         extra={"tier": "T1", "families": ["Hacker News", "OpenAI Blog"]})
        self.assertEqual(AIFilter._signals(it), "信源 官方一手 | 2 个独立来源报道 (Hacker News, OpenAI Blog) | 热度 300 | 评论 40")


class ConcurrentFetchTest(OfflineTestCase):

    def test_logs_grouped_in_config_order_with_health(self):
        def slow():
            print("slow source log")
            return [ContentItem(id="s", title="AI", url="https://e.com/s", source="S")]

        def broken():
            print("about to fail")
            raise RuntimeError("boom")

        registry = [("a", "Slow", slow), ("b", "Broken", broken), ("c", "Empty", lambda: [])]
        health = []
        with mock.patch.object(main, "source_registry", return_value=registry), \
                mock.patch.object(main.config, "ENABLED_SOURCES", ["a", "b", "c"]), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            items = main.fetch_all_sources(health)
        log = out.getvalue()
        self.assertEqual([i.id for i in items], ["s"])
        self.assertLess(log.index("slow source log"), log.index("about to fail"))
        self.assertIn("Broken 获取失败 (RuntimeError)", log)
        self.assertEqual([(h["key"], h["status"], h["items"]) for h in health],
                         [("a", "ok", 1), ("b", "error", 0), ("c", "empty", 0)])


if __name__ == "__main__":
    unittest.main()
