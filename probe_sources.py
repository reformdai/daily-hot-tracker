#!/usr/bin/env python3
"""只试抓配置中的 RSS/网页/JSON 源，不加载 dotenv，不调用 AI 或推送。"""
import argparse

import config
from fetchers import RSSFetcher, WebListFetcher, JsonListFetcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["rss", "web_list", "json_list"])
    parser.add_argument("--name", help="精确匹配配置中的源名称")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")
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
    items = fetcher(sources).fetch(args.limit)
    for item in items:
        print(f"[{item.source}] {item.published_at or 'unknown date'} | {item.title}\n  {item.url}")
    return 0 if items else 1


if __name__ == "__main__":
    raise SystemExit(main())
