#!/usr/bin/env python3
"""只试抓配置中的信源，不加载 dotenv，不调用 AI 或推送。
--body 额外试读每条的原文摘录，检查正文补抓是否有效。"""
import argparse

import config
from enrich import extract_body
from fetchers import RSSFetcher, WebListFetcher, JsonListFetcher, HNSearchFetcher, HuggingFaceFetcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["rss", "web_list", "json_list", "hn_search", "huggingface"])
    parser.add_argument("--name", help="精确匹配配置中的源名称（rss/web_list/json_list）")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--body", action="store_true", help="同时试读原文摘录")
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")
    if args.kind in ("hn_search", "huggingface"):
        fetcher = HNSearchFetcher(config.HN_SEARCH_QUERIES, config.HN_SEARCH_MIN_POINTS, config.HN_SEARCH_HOURS) \
            if args.kind == "hn_search" else \
            HuggingFaceFetcher(config.HF_DAILY_PAPERS, config.HF_TRENDING_MODELS, config.HF_MODEL_MAX_AGE_DAYS)
        return show(fetcher.fetch(args.limit), args.body)
    fetcher, sources = {
        "rss": (RSSFetcher, config.RSS_FEEDS),
        "web_list": (WebListFetcher, config.WEB_SOURCES),
        "json_list": (JsonListFetcher, config.JSON_SOURCES),
    }[args.kind]
    sources = [source for source in sources if source.get("enabled", True) is not False
               and (not args.name or source["name"] == args.name)]
    if not sources:
        print("没有匹配的启用源；请检查 config.py")
        return 1
    return show(fetcher(sources).fetch(args.limit), args.body)


def show(items, body=False):
    for item in items:
        print(f"[{item.source}] {item.published_at or 'unknown date'} | score {item.score} | {item.title}\n  {item.url}")
        if body:
            text, via = extract_body(item.url, config.JINA_READER_FALLBACK, "")
            print(f"  body ({via}, {len(text)} chars): {text[:200]}")
    return 0 if items else 1


if __name__ == "__main__":
    raise SystemExit(main())
