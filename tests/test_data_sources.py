"""
数据源抓取：超时/有限重试、feed 诊断、Reddit 清洗与公平合并、AIHOT 分类、Product Hunt 页面解析
"""
import contextlib
import io
import unittest
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest import mock

import requests

from fetchers import AIHotFetcher, ProductHuntFetcher, RedditFetcher, RSSFetcher
from fetchers import base
from fetchers.base import ContentItem
from tests import OfflineTestCase

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FRESH_DATE = format_datetime(datetime.now(timezone.utc))

RSS_XML = f"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Example</title>
<item><title>Fresh</title><link>https://example.com/fresh</link><pubDate>{FRESH_DATE}</pubDate>
<description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description></item>
</channel></rss>""".encode()

ATOM_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom</title>
<entry><id>tag:example.com,2020:1</id><title>Old post</title>
<link href="https://example.com/old"/><updated>2020-01-02T03:04:05Z</updated></entry>
</feed>"""

EMPTY_RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Quiet</title></channel></rss>"""

HTML_PAGE = b"<!DOCTYPE html><html><head><title>Not found</title></head><body><p>Oops</p></body></html>"

REDDIT_ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>r/test</title>
<entry>
  <author><name>/u/alice</name></author>
  <content type="html">&lt;table&gt;&lt;tr&gt;&lt;td&gt;&lt;a href="https://preview.redd.it/x.png"&gt;&lt;img src="https://preview.redd.it/x.png" /&gt;&lt;/a&gt;&lt;/td&gt;&lt;td&gt;&lt;!-- SC_OFF --&gt;&lt;div class="md"&gt;&lt;p&gt;New   open model beats baseline.&lt;/p&gt;&lt;/div&gt;&lt;!-- SC_ON --&gt; &amp;#32; submitted by &amp;#32; &lt;a href="https://www.reddit.com/user/alice"&gt; /u/alice &lt;/a&gt; &lt;br/&gt; &lt;span&gt;&lt;a href="https://example.com"&gt;[link]&lt;/a&gt;&lt;/span&gt; &amp;#32; &lt;span&gt;&lt;a href="https://www.reddit.com/r/test/comments/1"&gt;[comments]&lt;/a&gt;&lt;/span&gt;&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;</content>
  <id>t3_abc</id>
  <link href="https://www.reddit.com/r/test/comments/abc/post/"/>
  <updated>2026-09-23T10:20:30+00:00</updated>
  <title>Open model release</title>
</entry>
</feed>"""


def _response(status=200, body=b"", headers=None):
    resp = requests.Response()
    resp.status_code = status
    resp._content = body
    resp.headers.update(headers or {})
    return resp


class _PatchedHttp(OfflineTestCase):
    """patch base.requests.get 与 time.sleep，并捕获控制台输出"""

    def setUp(self):
        super().setUp()
        get = mock.patch("fetchers.base.requests.get")
        sleep = mock.patch("fetchers.base.time.sleep")
        self.get = get.start()
        self.sleep = sleep.start()
        self.addCleanup(get.stop)
        self.addCleanup(sleep.stop)

    def run_quietly(self, func, *args, **kwargs):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = func(*args, **kwargs)
        return result, out.getvalue()


class GetWithRetryTest(_PatchedHttp):

    def test_uses_explicit_timeout(self):
        self.get.return_value = _response(200, b"ok")
        resp, _ = self.run_quietly(base.get_with_retry, "https://example.com/f", "T")
        self.assertEqual(resp.content, b"ok")
        self.assertEqual(self.get.call_args.kwargs["timeout"], base.REQUEST_TIMEOUT)

    def test_retries_server_error_then_succeeds(self):
        self.get.side_effect = [_response(503), _response(200, b"ok")]
        resp, out = self.run_quietly(base.get_with_retry, "https://example.com/f", "T")
        self.assertIsNotNone(resp)
        self.assertEqual(self.get.call_count, 2)
        self.assertIn("HTTP 503, retry 1/2", out)

    def test_rate_limit_retries_are_bounded(self):
        self.get.return_value = _response(429)
        resp, out = self.run_quietly(base.get_with_retry, "https://example.com/f", "T")
        self.assertIsNone(resp)
        self.assertEqual(self.get.call_count, base.MAX_ATTEMPTS)
        self.assertLessEqual(sum(c.args[0] for c in self.sleep.call_args_list), base.MAX_RETRY_WAIT)
        self.assertIn(f"HTTP 429 after {base.MAX_ATTEMPTS} attempts", out)

    def test_short_retry_after_is_honored(self):
        self.get.side_effect = [_response(429, headers={"Retry-After": "2"}), _response(200)]
        resp, _ = self.run_quietly(base.get_with_retry, "https://example.com/f", "T")
        self.assertIsNotNone(resp)
        self.sleep.assert_called_once_with(2.0)

    def test_long_retry_after_skips_without_waiting(self):
        self.get.return_value = _response(429, headers={"Retry-After": "3600"})
        resp, out = self.run_quietly(base.get_with_retry, "https://example.com/f", "T")
        self.assertIsNone(resp)
        self.assertEqual(self.get.call_count, 1)
        self.sleep.assert_not_called()
        self.assertIn("exceeds", out)

    def test_permanent_errors_are_not_retried(self):
        for status in (403, 404):
            with self.subTest(status=status):
                self.get.reset_mock()
                self.get.return_value = _response(status)
                resp, out = self.run_quietly(base.get_with_retry, "https://example.com/f", "T")
                self.assertIsNone(resp)
                self.assertEqual(self.get.call_count, 1)
                self.assertIn(f"HTTP {status}, not retrying", out)
        self.sleep.assert_not_called()

    def test_network_errors_are_retried_then_reported(self):
        self.get.side_effect = [requests.ConnectionError("down"), requests.Timeout("slow"), requests.ConnectionError("down")]
        resp, out = self.run_quietly(base.get_with_retry, "https://example.com/f", "T")
        self.assertIsNone(resp)
        self.assertEqual(self.get.call_count, base.MAX_ATTEMPTS)
        self.assertIn("network error (ConnectionError) after 3 attempts", out)


class FetchFeedTest(_PatchedHttp):

    def test_rss_feed_reports_count_and_latest(self):
        self.get.return_value = _response(200, RSS_XML, {"Content-Type": "application/rss+xml"})
        feed, out = self.run_quietly(base.fetch_feed, "https://example.com/rss", "RSS Example")
        self.assertEqual(len(feed.entries), 1)
        self.assertIn("[RSS Example] 1 entries, latest", out)
        self.assertNotIn("stale", out)

    def test_old_atom_feed_warns_but_keeps_entries(self):
        self.get.return_value = _response(200, ATOM_XML, {"Content-Type": "application/atom+xml"})
        feed, out = self.run_quietly(base.fetch_feed, "https://example.com/atom", "Atom")
        self.assertEqual(len(feed.entries), 1)
        self.assertIn("latest 2020-01-02 03:04 UTC (stale", out)

    def test_valid_empty_feed_is_distinguished(self):
        self.get.return_value = _response(200, EMPTY_RSS, {"Content-Type": "application/rss+xml"})
        feed, out = self.run_quietly(base.fetch_feed, "https://example.com/empty", "Quiet")
        self.assertEqual(feed.entries, [])
        self.assertIn("valid feed with 0 entries", out)

    def test_html_page_is_invalid_feed(self):
        self.get.return_value = _response(200, HTML_PAGE, {"Content-Type": "text/html"})
        feed, out = self.run_quietly(base.fetch_feed, "https://example.com/page", "Broken")
        self.assertIsNone(feed)
        self.assertIn("invalid feed (text/html)", out)

    def test_relative_links_resolve_against_redirected_url(self):
        body = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>R</title>
<item><title>A</title><link>article</link></item></channel></rss>"""
        resp = _response(200, body, {"Content-Type": "application/rss+xml"})
        resp.url = "https://new.example/news/feed.xml"
        self.get.return_value = resp
        feed, _ = self.run_quietly(base.fetch_feed, "https://old.example/feed.xml", "Moved")
        self.assertEqual(feed.entries[0].link, "https://new.example/news/article")

    def test_rss_fetcher_isolates_failing_feed(self):
        def fake_get(url, **kwargs):
            return _response(404) if "missing" in url else _response(200, RSS_XML)
        self.get.side_effect = fake_get
        fetcher = RSSFetcher(feeds=[
            {"name": "Gone", "url": "https://example.com/missing.xml"},
            {"name": "Live", "url": "https://example.com/live.xml"},
        ])
        items, out = self.run_quietly(fetcher.fetch)
        self.assertEqual([i.source for i in items], ["Live"])
        self.assertEqual(items[0].description, "Hello world")
        self.assertIn("[RSS Gone] HTTP 404, not retrying", out)


class RedditTest(_PatchedHttp):

    def test_summary_html_is_cleaned_and_updated_time_used(self):
        self.get.return_value = _response(200, REDDIT_ATOM, {"Content-Type": "application/atom+xml"})
        items, _ = self.run_quietly(RedditFetcher(subreddits=["test"]).fetch)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].description, "New open model beats baseline.")
        self.assertEqual(items[0].published_at, datetime(2026, 9, 23, 10, 20, 30))
        self.assertIn("User-Agent", self.get.call_args.kwargs["headers"])

    def test_communities_are_merged_round_robin(self):
        subs = [f"sub{i}" for i in range(6)]

        def fake_fetch(subreddit, limit):
            return [ContentItem(id=f"{subreddit}-{n}", title="t", url="u", source=subreddit) for n in range(limit)]

        fetcher = RedditFetcher(subreddits=subs)
        with mock.patch.object(fetcher, "_fetch_subreddit_rss", side_effect=fake_fetch):
            items = fetcher.fetch(limit=20)
        self.assertEqual(len(items), 20)
        self.assertEqual({i.source for i in items}, set(subs))
        self.assertEqual([i.id for i in items[:7]], [f"sub{i}-0" for i in range(6)] + ["sub0-1"])

    def test_rate_limited_subreddit_does_not_block_others(self):
        def fake_get(url, **kwargs):
            if "/r/busy/" in url:
                return _response(429, headers={"Retry-After": "600"})
            return _response(200, REDDIT_ATOM)
        self.get.side_effect = fake_get
        items, out = self.run_quietly(RedditFetcher(subreddits=["busy", "test"]).fetch)
        self.assertEqual([i.source for i in items], ["Reddit r/test"])
        self.assertIn("[Reddit r/busy] HTTP 429, retry wait 600s exceeds", out)


class AIHotCategoryTest(OfflineTestCase):

    def test_observed_category_aliases(self):
        fetcher = AIHotFetcher()
        with mock.patch.object(fetcher.session, "get") as get:
            get.return_value.json.return_value = {"items": [
                {"id": "1", "title": "M", "url": "https://example.com/1", "category": "ai-models"},
                {"id": "2", "title": "P", "url": "https://example.com/2", "category": "ai-products"},
                {"id": "3", "title": "N", "url": "https://example.com/3", "category": "brand-new"},
            ]}
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                items = fetcher.fetch()
        self.assertEqual([i.category for i in items], ["模型发布", "产品发布", "行业动态"])
        self.assertEqual([i.extra["aihot_category"] for i in items], ["ai-models", "ai-products", "brand-new"])
        self.assertIn("unknown categories mapped to 行业动态: ['brand-new']", out.getvalue())


class ProductHuntPageTest(OfflineTestCase):

    def setUp(self):
        super().setUp()
        self.html = (FIXTURES / "producthunt_homepage.html").read_text(encoding="utf-8")

    def parse(self, html, limit=20):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            items = ProductHuntFetcher()._parse_page(html, limit)
        return items, out.getvalue()

    def test_current_markup_only_today_ranked_products(self):
        items, out = self.parse(self.html)
        self.assertEqual([i.title for i in items], ["Alpha Agent", "Beta Notes", "Gamma CLI"])
        self.assertEqual([i.url for i in items], [
            "https://www.producthunt.com/products/alpha-agent",
            "https://www.producthunt.com/products/beta-notes",
            "https://www.producthunt.com/products/gamma-cli",
        ])
        self.assertEqual([i.score for i in items], [1428, 298, 76])
        self.assertEqual([i.comments for i in items], [43, 5, 0])
        self.assertEqual(items[0].description, "Agents with their own computers")
        self.assertEqual(items[0].category, "Artificial Intelligence, Developer Tools")
        self.assertEqual(items[2].category, "Product")
        self.assertEqual([i.extra["ph_rank"] for i in items], [1, 2, 3])
        self.assertEqual(items[0].id, base.stable_id("ph_page", items[0].url))
        self.assertEqual(out, "")

    def test_limit_is_respected(self):
        items, _ = self.parse(self.html, limit=2)
        self.assertEqual(len(items), 2)

    def test_legacy_post_item_layout_still_parsed(self):
        html = ('<div data-test="post-item"><a href="/posts/old-app">'
                '<span data-test="post-name">Old App</span></a>'
                '<span data-test="post-tagline">Legacy</span></div>')
        items, _ = self.parse(html)
        self.assertEqual([(i.title, i.url) for i in items],
                         [("Old App", "https://www.producthunt.com/posts/old-app")])

    def test_changed_page_is_logged(self):
        items, out = self.parse("<html><body><div>Welcome</div></body></html>")
        self.assertEqual(items, [])
        self.assertIn("Page structure changed", out)

    def test_empty_today_section_is_logged(self):
        items, out = self.parse('<div data-test="homepage-section-today"><h1>Today</h1></div>')
        self.assertEqual(items, [])
        self.assertIn("Today section found but no ranked", out)

    def test_bot_challenge_is_logged(self):
        with mock.patch("fetchers.producthunt.requests.get") as get:
            get.return_value = _response(403, b"<title>Just a moment...</title>")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                items = ProductHuntFetcher()._fetch_from_page(10)
        self.assertEqual(items, [])
        self.assertIn("blocked by bot challenge (HTTP 403)", out.getvalue())


class ProductHuntApiTest(OfflineTestCase):
    TOKEN = "fake-token-for-tests"

    def fetch(self, api_response):
        with mock.patch("fetchers.producthunt.requests.post", return_value=api_response), \
                mock.patch("fetchers.producthunt.requests.get") as get:
            get.return_value = _response(200, (FIXTURES / "producthunt_homepage.html").read_bytes())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                items = ProductHuntFetcher(token=self.TOKEN).fetch(limit=5)
        return items, out.getvalue()

    def test_graphql_errors_are_reported_without_token_and_fall_back(self):
        items, out = self.fetch(_response(200, b'{"errors": [{"message": "Invalid token"}], "data": null}'))
        self.assertIn("API GraphQL errors: Invalid token", out)
        self.assertNotIn(self.TOKEN, out)
        self.assertEqual(items[0].title, "Alpha Agent")

    def test_echoed_token_in_graphql_error_is_redacted(self):
        body = f'{{"errors": [{{"message": "Bad token {self.TOKEN}"}}], "data": null}}'.encode()
        _, out = self.fetch(_response(200, body))
        self.assertIn("API GraphQL errors: Bad token ***", out)
        self.assertNotIn(self.TOKEN, out)

    def test_echoed_token_in_generic_exception_is_redacted(self):
        with mock.patch("fetchers.producthunt.requests.post", side_effect=ValueError(f"echo {self.TOKEN}")):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                items = ProductHuntFetcher(token=self.TOKEN)._fetch_with_api(5)
        self.assertEqual(items, [])
        self.assertIn("API Error: ValueError: echo ***", out.getvalue())
        self.assertNotIn(self.TOKEN, out.getvalue())

    def test_http_error_is_reported_without_token(self):
        items, out = self.fetch(_response(401, b'{"error": "unauthorized"}'))
        self.assertIn("API HTTP 401", out)
        self.assertNotIn(self.TOKEN, out)
        self.assertEqual(len(items), 3)

    def test_created_at_is_captured(self):
        body = (b'{"data": {"posts": {"edges": [{"node": {"id": "42", "name": "Launch", "tagline": "t",'
                b' "url": "https://www.producthunt.com/posts/launch", "votesCount": 10, "commentsCount": 2,'
                b' "createdAt": "2026-09-24T07:01:00Z", "makers": [], "topics": {"edges": []}}}]}}}')
        items, _ = self.fetch(_response(200, body))
        self.assertEqual(items[0].id, "ph_42")
        self.assertEqual(items[0].published_at, datetime(2026, 9, 24, 7, 1))


if __name__ == "__main__":
    unittest.main()
