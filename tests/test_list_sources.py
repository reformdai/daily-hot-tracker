"""配置化信源回归，所有 HTTP 都由固定样本替代。"""
import contextlib
import io
import json
from datetime import datetime
from unittest import mock

import feedparser
import requests

import config
from fetchers import JsonListFetcher, RSSFetcher, WebListFetcher
from fetchers.list_sources import get_path, parse_date
from tests import OfflineTestCase


def response(body, url="https://example.com/news/"):
    result = requests.Response()
    result.status_code = 200
    result.url = url
    result._content = body.encode()
    return result


WEB = {
    "name": "Example", "url": "https://example.com/old/", "item_selector": "article",
    "link_selector": "a", "title_selector": "h2", "date_selector": "time", "summary_selector": "p",
}
JSON = {
    "name": "Example API", "url": "https://example.com/api", "items_path": "data.items",
    "title_path": "headline.text", "url_path": "links.0.href", "date_path": "date",
    "summary_path": "summary",
}


class ListSourcesTest(OfflineTestCase):
    def fetch(self, fetcher, payload):
        output = io.StringIO()
        with mock.patch("fetchers.list_sources.get_with_retry", return_value=payload), contextlib.redirect_stdout(output):
            items = fetcher.fetch()
        return items, output.getvalue()

    def test_web_redirect_relative_links_duplicates_bad_links_and_dates(self):
        html = '''<article><a href="fresh#top"><h2>New &amp; useful</h2></a>
            <p>Hello <b>world</b></p><time datetime="2026-09-29T08:00:00+08:00"></time></article>
            <article><a href="fresh"><h2>Duplicate</h2></a></article>
            <article><a href="javascript:alert(1)"><h2>Unsafe</h2></a></article>
            <article><a href="missing-title"></a></article>
            <article><a href="#top"><h2>Self</h2></a></article>'''
        items, _ = self.fetch(WebListFetcher([WEB]), response(html))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://example.com/news/fresh")
        self.assertEqual(items[0].title, "New & useful")
        self.assertEqual(items[0].description, "Hello world")
        self.assertEqual(items[0].published_at, datetime(2026, 9, 29))

    def test_anthropic_config_parses_observed_markup(self):
        html = '''<a href="/news/new-model"><time>Sep 23, 2026</time>
          <span class="PublicationList-module-scss-module__abc__title body-3">New model</span></a>
          <a href="/news/navigation">News navigation</a>'''
        items, _ = self.fetch(WebListFetcher(config.WEB_SOURCES), response(html, "https://www.anthropic.com/news"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, "Anthropic")
        self.assertEqual(items[0].title, "New model")
        self.assertEqual(items[0].published_at, datetime(2026, 9, 23))

    def test_web_changed_selector_is_visible(self):
        items, output = self.fetch(WebListFetcher([WEB]), response("<h1>Challenge</h1>"))
        self.assertFalse(items)
        self.assertIn("0 valid items", output)

    def test_url_prefix_filter(self):
        source = {**WEB, "allow_url_prefixes": ["https://example.com/news/"]}
        html = '<article><a href="https://other.example/a"><h2>Other</h2></a></article>'
        items, _ = self.fetch(WebListFetcher([source]), response(html))
        self.assertFalse(items)

    def test_json_nested_fields_invalid_rows_duplicates_and_unknown_date(self):
        row = {"headline": {"text": "AI news"}, "links": [{"href": "/story"}], "date": "bad", "summary": "<p>A &amp; B</p>"}
        body = json.dumps({"data": {"items": [None, {}, row, row, {**row, "links": [{"href": "data:text/html,bad"}]}]}})
        items, _ = self.fetch(JsonListFetcher([JSON]), response(body))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://example.com/story")
        self.assertEqual(items[0].description, "A & B")
        self.assertIsNone(items[0].published_at)

    def test_json_invalid_shape_and_field_mapping_have_diagnostics(self):
        for body, reason in [("<html>", "response is not JSON"), ('{"data":{}}', "items_path"),
                             ('{"data":{"items":[{"changed":true}]}}', "no valid items mapped")]:
            with self.subTest(body=body):
                items, output = self.fetch(JsonListFetcher([JSON]), response(body))
                self.assertFalse(items)
                self.assertIn(reason, output)

    def test_empty_json_is_success(self):
        items, output = self.fetch(JsonListFetcher([JSON]), response('{"data":{"items":[]}}'))
        self.assertFalse(items)
        self.assertIn("0 valid items", output)
        self.assertNotIn("failed", output)

    def test_bad_config_and_disabled_source_make_no_request(self):
        for source in [{**WEB, "enabled": False}, {**WEB, "typo": "x"}, {**WEB, "item_selector": ""}]:
            with self.subTest(source=source), mock.patch("fetchers.list_sources.get_with_retry") as get:
                WebListFetcher([source]).fetch()
                get.assert_not_called()

    def test_source_failure_isolated_and_fair_limit(self):
        html = '<article><a href="a"><h2>A</h2></a></article><article><a href="b"><h2>B</h2></a></article>'
        sources = [{**WEB, "name": name} for name in ("Broken", "One", "Two")]
        with mock.patch("fetchers.list_sources.get_with_retry", side_effect=[None, response(html), response(html)]):
            items = WebListFetcher(sources).fetch(limit=2)
        self.assertEqual([i.source for i in items], ["One", "Two"])

    def test_date_and_path_edge_cases(self):
        self.assertEqual(parse_date("2026-09-29T01:00:00+02:00"), datetime(2026, 9, 28, 23))
        self.assertIsNone(parse_date("yesterday"))
        self.assertIsNone(parse_date(123))
        self.assertEqual(get_path({"a": [{"b": "yes"}]}, "a.0.b"), "yes")
        self.assertIsNone(get_path({"a": []}, "a.1"))

    def test_nonpositive_limit_makes_no_request(self):
        with mock.patch("fetchers.list_sources.get_with_retry") as get:
            self.assertEqual(WebListFetcher([WEB]).fetch(0), [])
            get.assert_not_called()

    def test_url_id_is_independent_of_title_and_order(self):
        first, _ = self.fetch(WebListFetcher([WEB]), response('<article><a href="a"><h2>A</h2></a></article>'))
        second, _ = self.fetch(WebListFetcher([WEB]), response('<article><a href="a"><h2>Updated</h2></a></article>'))
        self.assertEqual(first[0].id, second[0].id)


class RSSSamplingTest(OfflineTestCase):
    def test_disabled_invalid_duplicate_rows_and_fair_sampling(self):
        def feed(url, label):
            entries = [feedparser.FeedParserDict(title="Missing link")]
            entries += [feedparser.FeedParserDict(title=f"Title {i}", link=f"{url}/{i}", summary="A &amp; B") for i in range(12)]
            entries += [entries[1]]
            return feedparser.FeedParserDict(feed={}, entries=entries)
        sources = [{"name": "Off", "url": "https://off.example", "enabled": False},
                   {"name": "One", "url": "https://one.example"}, {"name": "Two", "url": "https://two.example"}]
        with mock.patch("fetchers.rss_feeds.fetch_feed", side_effect=feed) as get:
            items = RSSFetcher(sources).fetch(4)
        self.assertEqual(get.call_count, 2)
        self.assertEqual([i.source for i in items], ["One", "Two", "One", "Two"])
        self.assertTrue(all(i.url and i.title and i.description == "A & B" for i in items))
