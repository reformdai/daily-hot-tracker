"""
Reddit 数据抓取 (通过 RSS)
"""
import feedparser
from datetime import datetime
from typing import List
from .base import BaseFetcher, ContentItem


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
        all_items = []
        per_sub_limit = max(5, limit // len(self.subreddits))
        
        for subreddit in self.subreddits:
            items = self._fetch_subreddit_rss(subreddit, per_sub_limit)
            all_items.extend(items)
        
        # 按分数排序 (RSS里没有分数，只能按时间或默认顺序)
        # 通常 RSS 也是按热度排序的 (hot.rss)
        return all_items[:limit]
    
    def _fetch_subreddit_rss(self, subreddit: str, limit: int) -> List[ContentItem]:
        """通过 RSS 获取单个 subreddit 的热帖"""
        items = []
        url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
        
        try:
            # 使用浏览器 UA
            feed = feedparser.parse(
                url,
                agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )
            
            for entry in feed.entries[:limit]:
                # 尝试从 entry 中提取更多信息
                # RSS entry 通常包含: title, link, updated, summary, author
                
                # 处理时间
                published_at = None
                if hasattr(entry, "published_parsed"):
                    try:
                        published_at = datetime(*entry.published_parsed[:6])
                    except:
                        pass
                
                # 尝试从 summary 中提取一些文本作为 description
                # Reddit RSS 的 summary 是 HTML，包含预览图等，直接用可能太乱
                # 简单清洗一下或者截取
                description = entry.summary if hasattr(entry, "summary") else ""
                if "<" in description:
                    # 简单去除 HTML 标签 (或者只取前一部分)
                    # 这里为了简单，暂不引入 BeautifulSoup，直接截取
                    pass 

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
