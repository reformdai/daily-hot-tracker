"""
RSS 订阅源抓取
"""
from datetime import datetime
from itertools import zip_longest
from typing import List, Dict
from .list_sources import clean_text, http_url
from .base import BaseFetcher, ContentItem, entry_time, fetch_feed, stable_id


class RSSFetcher(BaseFetcher):
    """RSS 订阅源抓取"""
    
    name = "RSS Feeds"
    
    def __init__(self, feeds: List[Dict] = None):
        """
        Args:
            feeds: RSS 订阅源列表，格式: [{"name": "xxx", "url": "xxx", "category": "xxx"}, ...]
        """
        self.feeds = feeds or []
    
    def fetch(self, limit: int = 20) -> List[ContentItem]:
        """获取所有 RSS 源的最新内容"""
        if limit <= 0:
            return []
        batches = []
        for feed_config in self.feeds:
            if feed_config.get("enabled", True) is False:
                continue
            items = self._fetch_feed(feed_config)
            items.sort(key=lambda item: item.published_at or datetime.min, reverse=True)
            batches.append(items)
        # 在单源最新优先的基础上轮询取样，避免高频源占满总额度。
        return [item for row in zip_longest(*batches) for item in row if item is not None][:limit]

    def _fetch_feed(self, feed_config: Dict) -> List[ContentItem]:
        """获取单个 RSS 源"""
        items = []

        try:
            feed = fetch_feed(feed_config["url"], f"RSS {feed_config.get('name', feed_config['url'])}")
            if feed is None:
                return []
            feed_name = feed_config.get("name", feed.feed.get("title", "Unknown"))
            category = feed_config.get("category", "News")

            seen = set()
            for entry in feed.entries:
                title = clean_text(entry.get("title", ""))
                url = http_url(entry.get("link", ""), feed_config["url"])
                if not title or not url or url in seen:
                    continue
                seen.add(url)
                published_at = entry_time(entry)

                # 获取摘要
                description = ""
                if hasattr(entry, 'summary'):
                    description = entry.summary
                elif hasattr(entry, 'description'):
                    description = entry.description
                
                # 清理 HTML 标签
                description = self._clean_html(description)[:500]
                
                # 获取作者
                author = ""
                if hasattr(entry, 'author'):
                    author = entry.author
                elif hasattr(entry, 'authors') and entry.authors:
                    author = entry.authors[0].get('name', '')
                
                items.append(ContentItem(
                    id=stable_id("rss", entry.get("id") or entry.get("link", "")),
                    title=title,
                    url=url,
                    source=feed_name,
                    category=category,
                    description=description,
                    author=author,
                    published_at=published_at,
                    extra={
                        "feed_url": feed_config["url"],
                        **({"tier": feed_config["tier"]} if feed_config.get("tier") else {}),
                    }
                ))
            
            return items
            
        except Exception as e:
            print(f"[RSS] Error fetching {feed_config.get('name', feed_config['url'])}: {e}")
            return []
    
    def _clean_html(self, html: str) -> str:
        """解码实体并清理标签、脚本和空白。"""
        return clean_text(html)
