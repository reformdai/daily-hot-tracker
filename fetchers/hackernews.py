"""
Hacker News 数据抓取
"""
import requests
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from .base import BaseFetcher, ContentItem


class HackerNewsFetcher(BaseFetcher):
    """Hacker News 热榜抓取"""
    
    name = "Hacker News"
    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    
    def fetch(self, limit: int = 20) -> List[ContentItem]:
        """获取 HN 热榜"""
        items = []
        
        try:
            # 获取热榜 ID 列表
            resp = requests.get(f"{self.BASE_URL}/topstories.json", timeout=10)
            resp.raise_for_status()
            story_ids = resp.json()[:limit * 2]  # 多取一些，后面过滤
            
            # 并发获取详情
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {
                    executor.submit(self._fetch_item, sid): sid 
                    for sid in story_ids
                }
                
                for future in as_completed(futures):
                    try:
                        item = future.result()
                        if item and item.url:  # 只要有链接的
                            items.append(item)
                    except Exception:
                        pass
                        
            # 按分数排序
            items.sort(key=lambda x: x.score, reverse=True)
            return items[:limit]
            
        except Exception as e:
            print(f"[HackerNews] Error fetching: {e}")
            return []
    
    def _fetch_item(self, item_id: int) -> Optional[ContentItem]:
        """获取单个 story 详情"""
        resp = requests.get(f"{self.BASE_URL}/item/{item_id}.json", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if not data or data.get("type") != "story":
            return None
            
        return ContentItem(
            id=f"hn_{item_id}",
            title=data.get("title", ""),
            url=data.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
            source="Hacker News",
            category="Tech",
            description="",  # HN 没有摘要
            author=data.get("by", ""),
            score=data.get("score", 0),
            comments=data.get("descendants", 0),
            extra={
                "hn_url": f"https://news.ycombinator.com/item?id={item_id}",
            }
        )
