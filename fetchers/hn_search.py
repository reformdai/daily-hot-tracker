"""
Hacker News 搜索（Algolia 公开 API，无需 key）
topstories 只看全站前几十条，AI 内容常被挤出；这里按关键词搜最近 N 小时内的高分 story。
"""
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlencode

from .base import BaseFetcher, ContentItem, get_with_retry
from .list_sources import clean_text


class HNSearchFetcher(BaseFetcher):

    name = "Hacker News"
    BASE_URL = "https://hn.algolia.com/api/v1/search"

    def __init__(self, queries: List[str] = None, min_points: int = 30, hours: int = 24):
        self.queries = queries or ["AI", "LLM"]
        self.min_points = min_points
        self.hours = hours

    def fetch(self, limit: int = 20) -> List[ContentItem]:
        if limit <= 0:
            return []
        since = int(time.time()) - self.hours * 3600
        found: Dict[str, ContentItem] = {}
        failed = 0
        for query in self.queries:
            params = {
                "query": query,
                "tags": "story",
                "numericFilters": f"created_at_i>{since},points>={self.min_points}",
                "hitsPerPage": 30,
            }
            resp = get_with_retry(f"{self.BASE_URL}?{urlencode(params)}", f"HN search '{query}'")
            if resp is None:
                failed += 1
                continue
            try:
                hits = resp.json().get("hits", [])
            except ValueError:
                print(f"[HN search '{query}'] response is not JSON")
                failed += 1
                continue
            for hit in hits:
                item = self._to_item(hit)
                if item and item.id not in found:
                    found[item.id] = item

        items = sorted(found.values(), key=lambda x: x.score, reverse=True)
        print(f"[HN search] {len(items)} stories from {len(self.queries) - failed}/{len(self.queries)} queries")
        return items[:limit]

    @staticmethod
    def _to_item(hit: dict) -> Optional[ContentItem]:
        story_id = hit.get("objectID")
        title = clean_text(hit.get("title") or "")
        if not story_id or not title:
            return None
        hn_url = f"https://news.ycombinator.com/item?id={story_id}"
        created = hit.get("created_at_i")
        return ContentItem(
            # 与 topstories 抓取器同一 ID 规则，两边抓到同一帖时可直接合并
            id=f"hn_{story_id}",
            title=title,
            url=hit.get("url") or hn_url,
            source="Hacker News",
            category="Tech",
            # Ask/Show HN 的正文在 story_text；普通外链没有描述，靠正文补抓
            description=clean_text(hit.get("story_text") or "")[:500],
            author=hit.get("author") or "",
            score=int(hit.get("points") or 0),
            comments=int(hit.get("num_comments") or 0),
            published_at=(
                datetime.fromtimestamp(created, timezone.utc).replace(tzinfo=None)
                if isinstance(created, int) else None
            ),
            extra={"hn_url": hn_url},
        )
