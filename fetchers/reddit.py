"""
Reddit 数据抓取
"""
import requests
from datetime import datetime
from typing import List
from .base import BaseFetcher, ContentItem


class RedditFetcher(BaseFetcher):
    """Reddit 热帖抓取"""
    
    name = "Reddit"
    
    def __init__(self, subreddits: List[str] = None):
        self.subreddits = subreddits or [
            "artificial",
            "MachineLearning", 
            "LocalLLaMA",
            "startups",
        ]
    
    def fetch(self, limit: int = 20) -> List[ContentItem]:
        """获取多个 subreddit 的热帖"""
        all_items = []
        per_sub_limit = max(5, limit // len(self.subreddits))
        
        for subreddit in self.subreddits:
            items = self._fetch_subreddit(subreddit, per_sub_limit)
            all_items.extend(items)
        
        # 按分数排序，取 top
        all_items.sort(key=lambda x: x.score, reverse=True)
        return all_items[:limit]
    
    def _fetch_subreddit(self, subreddit: str, limit: int) -> List[ContentItem]:
        """获取单个 subreddit 的热帖"""
        items = []
        
        try:
            resp = requests.get(
                f"https://www.reddit.com/r/{subreddit}/hot.json",
                params={"limit": limit},
                headers={
                    "User-Agent": "DailyHotTracker/1.0 (by /u/daily_bot)"
                },
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            
            for post in data.get("data", {}).get("children", []):
                post_data = post.get("data", {})
                
                # 跳过置顶帖和广告
                if post_data.get("stickied") or post_data.get("is_ad"):
                    continue
                
                # 获取实际链接 (如果是外链则用外链，否则用 reddit 链接)
                url = post_data.get("url", "")
                if url.startswith("/r/") or "reddit.com" in url:
                    url = f"https://www.reddit.com{post_data.get('permalink', '')}"
                
                created_utc = post_data.get("created_utc", 0)
                published_at = datetime.fromtimestamp(created_utc) if created_utc else None
                
                items.append(ContentItem(
                    id=f"reddit_{post_data.get('id', '')}",
                    title=post_data.get("title", ""),
                    url=url,
                    source=f"Reddit r/{subreddit}",
                    category=subreddit,
                    description=post_data.get("selftext", "")[:500],  # 限制长度
                    author=post_data.get("author", ""),
                    score=post_data.get("score", 0),
                    comments=post_data.get("num_comments", 0),
                    published_at=published_at,
                    extra={
                        "subreddit": subreddit,
                        "reddit_url": f"https://www.reddit.com{post_data.get('permalink', '')}",
                        "upvote_ratio": post_data.get("upvote_ratio", 0),
                    }
                ))
            
            return items
            
        except Exception as e:
            print(f"[Reddit] Error fetching r/{subreddit}: {e}")
            return []
