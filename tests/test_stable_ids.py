"""
RSS / ArXiv / Product Hunt 页面 / AIHOT 的 ID 需跨进程稳定
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import feedparser

from fetchers import AIHotFetcher, ArxivFetcher, ProductHuntFetcher, RSSFetcher
from rss_output import generate_rss_feed
from tests import OfflineTestCase

REPO_ROOT = Path(__file__).resolve().parent.parent

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2409.00001v1</id>
    <title>Paper A</title><summary>Abstract A</summary>
    <link href="http://arxiv.org/abs/2409.00001v1" rel="alternate" type="text/html"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2409.00002v1</id>
    <title>Paper B</title><summary>Abstract B</summary>
    <link href="http://arxiv.org/abs/2409.00002v1" rel="alternate" type="text/html"/>
  </entry>
</feed>"""


def _ph_html(slugs):
    posts = "".join(
        f'<div data-test="post-item"><a href="/posts/{s}"><span data-test="post-name">{s}</span></a></div>'
        for s in slugs
    )
    return f"<html><body>{posts}</body></html>"


def _collect_ids(ph_order=("alpha", "beta")):
    """用固定的离线输入跑各 fetcher 的解析逻辑，返回 {source: [ids]}"""
    feed = feedparser.FeedParserDict(
        feed=feedparser.FeedParserDict(title="Feed"),
        entries=[
            feedparser.FeedParserDict(id="tag:example.com,2026:1", link="https://example.com/a", title="A"),
            feedparser.FeedParserDict(link="https://example.com/b", title="B"),
        ],
    )
    with mock.patch("fetchers.rss_feeds.fetch_feed", return_value=feed):
        rss = RSSFetcher(feeds=[{"name": "Feed", "url": "https://example.com/feed"}]).fetch()

    arxiv = ArxivFetcher()._parse_response(ARXIV_XML, 10)

    with mock.patch("fetchers.producthunt.requests.get") as get:
        get.return_value.text = _ph_html(ph_order)
        ph = ProductHuntFetcher()._fetch_from_page(10)

    aihot_fetcher = AIHotFetcher()
    with mock.patch.object(aihot_fetcher.session, "get") as get:
        get.return_value.json.return_value = {"items": [
            {"id": "native-1", "title": "Native", "url": "https://example.com/n"},
            {"title": "No id 1", "url": "https://example.com/x"},
            {"title": "No id 2", "url": "https://example.com/y"},
        ]}
        aihot = aihot_fetcher.fetch()

    return {
        "rss": [i.id for i in rss],
        "arxiv": [i.id for i in arxiv],
        "producthunt": {i.url: i.id for i in ph},
        "aihot": [i.id for i in aihot],
    }


def _collect_ids_in_subprocess(hash_seed):
    env = dict(os.environ, PYTHONHASHSEED=str(hash_seed))
    code = "import json; from tests.test_stable_ids import _collect_ids; print(json.dumps(_collect_ids()))"
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


class StableIdTest(OfflineTestCase):

    def test_ids_are_identical_across_processes(self):
        first = _collect_ids_in_subprocess(1)
        second = _collect_ids_in_subprocess(2)
        self.assertEqual(first, second)

    def test_distinct_articles_get_distinct_ids(self):
        ids = _collect_ids()
        for source in ("rss", "arxiv", "aihot"):
            with self.subTest(source=source):
                self.assertEqual(len(set(ids[source])), len(ids[source]))
        self.assertEqual(len(set(ids["producthunt"].values())), 2)
        self.assertEqual(ids["aihot"][0], "aihot_native-1")

    def test_product_hunt_page_id_does_not_depend_on_position(self):
        forward = _collect_ids(ph_order=("alpha", "beta"))["producthunt"]
        reverse = _collect_ids(ph_order=("beta", "alpha"))["producthunt"]
        self.assertEqual(forward, reverse)

    def test_rss_output_guid_uses_item_id(self):
        items = ArxivFetcher()._parse_response(ARXIV_XML, 10)
        with tempfile.TemporaryDirectory() as tmp:
            path = generate_rss_feed(items, output_dir=tmp)
            guids = [g.text for g in ET.parse(path).getroot().iter("guid")]
        self.assertEqual(guids, [i.id for i in items])


if __name__ == "__main__":
    unittest.main()
