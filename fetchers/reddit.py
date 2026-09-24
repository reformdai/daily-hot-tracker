"""
Reddit 数据抓取 (通过 RSS)
"""
import re
from typing import List

from bs4 import BeautifulSoup

from .base import BaseFetcher, ContentItem, entry_time, fetch_feed


class RedditFetcher(BaseFetcher):
    """Reddit 热帖抓取 (RSS版，更稳定防403)"""
    
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
        per_sub_limit = max(5, limit // len(self.subreddits))
        per_sub = [self._fetch_subreddit_rss(s, per_sub_limit) for s in self.subreddits]

        # 轮询合并各 subreddit（各自保持 hot.rss 原顺序），避免截断总是丢掉靠后的社区
        all_items = []
        for rank in range(per_sub_limit):
            all_items.extend(items[rank] for items in per_sub if rank < len(items))
        return all_items[:limit]

    def _fetch_subreddit_rss(self, subreddit: str, limit: int) -> List[ContentItem]:
        """通过 RSS 获取单个 subreddit 的热帖"""
        items = []
        url = f"https://www.reddit.com/r/{subreddit}/hot.rss"

        try:
            # 使用浏览器 UA
            feed = fetch_feed(url, f"Reddit r/{subreddit}", headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            })
            if feed is None:
                return []

            for entry in feed.entries[:limit]:
                # Atom 条目通常只有 updated，没有 published
                published_at = entry_time(entry)
                description = self._clean_summary(entry.get("summary", ""))

                items.append(ContentItem(
                    id=f"reddit_{entry.id if hasattr(entry, 'id') else entry.link}",
                    title=entry.title,
                    url=entry.link,
                    source=f"Reddit r/{subreddit}",
                    category=subreddit,
                    description=description[:500],
                    author=entry.author if hasattr(entry, "author") else "",
                    score=0, # RSS 不提供实时分数，设为0
                    comments=0, # RSS 不提供评论数
                    published_at=published_at,
                    extra={
                        "subreddit": subreddit,
                    }
                ))
            
            return items
            
        except Exception as e:
            print(f"[Reddit] Error fetching r/{subreddit}: {e}")
            return []

    @staticmethod
    def _clean_summary(html: str) -> str:
        """Reddit summary 是 HTML（预览图、表格、submitted by 链接），只保留正文文本"""
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return re.split(r"\s*submitted by /u/", text)[0].strip()
