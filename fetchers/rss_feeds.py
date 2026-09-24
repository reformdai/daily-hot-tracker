"""
RSS 订阅源抓取
"""
from datetime import datetime
from typing import List, Dict
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
        all_items = []
        
        for feed_config in self.feeds:
            items = self._fetch_feed(feed_config)
            all_items.extend(items)
        
        # 按发布时间排序
        all_items.sort(
            key=lambda x: x.published_at or datetime.min, 
            reverse=True
        )
        
        return all_items[:limit]
    
    def _fetch_feed(self, feed_config: Dict) -> List[ContentItem]:
        """获取单个 RSS 源"""
        items = []

        try:
            feed = fetch_feed(feed_config["url"], f"RSS {feed_config.get('name', feed_config['url'])}")
            if feed is None:
                return []
            feed_name = feed_config.get("name", feed.feed.get("title", "Unknown"))
            category = feed_config.get("category", "News")

            for entry in feed.entries[:10]:  # 每个源最多取 10 条
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
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    source=feed_name,
                    category=category,
                    description=description,
                    author=author,
                    published_at=published_at,
                    extra={
                        "feed_url": feed_config["url"],
                    }
                ))
            
            return items
            
        except Exception as e:
            print(f"[RSS] Error fetching {feed_config.get('name', feed_config['url'])}: {e}")
            return []
    
    def _clean_html(self, html: str) -> str:
        """简单清理 HTML 标签"""
        import re
        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', '', html)
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
