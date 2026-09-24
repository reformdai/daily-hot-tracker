"""
Fetcher 基类和数据模型
"""
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import List, Optional
from datetime import datetime, timedelta, timezone

import feedparser
import requests

# (连接超时, 读取超时) 秒
REQUEST_TIMEOUT = (5, 20)
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
# 单个 URL 重试等待总预算（秒）；Retry-After 超出预算时直接跳过，不硬扛限流
MAX_RETRY_WAIT = 10
STALE_AFTER = timedelta(days=7)


def stable_id(prefix: str, key: str) -> str:
    """由 URL 等稳定键生成跨进程一致的 ID（内置 hash() 每个进程随机，不可用）"""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _retry_after_seconds(resp) -> Optional[float]:
    value = resp.headers.get("Retry-After")
    if not value:
        return None
    if value.strip().isdigit():
        return float(value)
    try:
        return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


def get_with_retry(url: str, label: str, headers: Optional[dict] = None) -> Optional[requests.Response]:
    """带超时和有限重试的 GET。成功返回 Response，失败打印原因并返回 None。
    429/5xx/网络错误重试；403/404 等永久错误不重试。"""
    waited = 0.0
    reason = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            reason = f"network error ({type(e).__name__})"
            delay = 2 ** (attempt - 1)
        else:
            if resp.ok:
                return resp
            reason = f"HTTP {resp.status_code}"
            if resp.status_code not in RETRY_STATUSES:
                print(f"[{label}] {reason}, not retrying; check {url}")
                return None
            retry_after = _retry_after_seconds(resp)
            delay = retry_after if retry_after is not None else 2 ** (attempt - 1)

        if attempt == MAX_ATTEMPTS:
            break
        if waited + delay > MAX_RETRY_WAIT:
            print(f"[{label}] {reason}, retry wait {delay:.0f}s exceeds {MAX_RETRY_WAIT}s budget, skipping")
            return None
        print(f"[{label}] {reason}, retry {attempt}/{MAX_ATTEMPTS - 1} in {delay:.0f}s")
        time.sleep(delay)
        waited += delay

    print(f"[{label}] {reason} after {MAX_ATTEMPTS} attempts, skipping")
    return None


def entry_time(entry) -> Optional[datetime]:
    """feedparser 条目的发布时间（无则用更新时间），naive UTC"""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6])
    except (TypeError, ValueError):
        return None


def fetch_feed(url: str, label: str, headers: Optional[dict] = None):
    """下载并解析 RSS/Atom。区分 HTTP/网络失败、无效 feed、合法空 feed，
    打印条目数与最新时间，超过 7 天未更新时警告（不过滤）。失败返回 None。"""
    resp = get_with_retry(url, label, headers=headers)
    if resp is None:
        return None

    feed = feedparser.parse(resp.content, response_headers={
        "content-type": resp.headers.get("Content-Type", ""),
        # 重定向后以最终地址解析相对链接
        "content-location": resp.url or url,
    })
    if not feed.entries:
        if feed.bozo or not feed.version:
            error = feed.get("bozo_exception") or "not an RSS/Atom document"
            print(f"[{label}] invalid feed ({resp.headers.get('Content-Type', 'unknown type')}): {error}")
            return None
        print(f"[{label}] valid feed with 0 entries")
        return feed

    times = [t for t in (entry_time(e) for e in feed.entries) if t]
    if not times:
        print(f"[{label}] {len(feed.entries)} entries, no timestamps")
        return feed
    latest = max(times)
    message = f"[{label}] {len(feed.entries)} entries, latest {latest:%Y-%m-%d %H:%M} UTC"
    if datetime.now(timezone.utc).replace(tzinfo=None) - latest > STALE_AFTER:
        message += f" (stale: no update in {STALE_AFTER.days}+ days)"
    print(message)
    return feed


@dataclass
class ContentItem:
    """统一的内容数据模型"""
    id: str                          # 唯一标识
    title: str                       # 标题
    url: str                         # 链接
    source: str                      # 来源平台
    category: str = ""               # 分类
    description: str = ""            # 描述/摘要
    author: str = ""                 # 作者
    score: int = 0                   # 原平台热度分数
    comments: int = 0                # 评论数
    published_at: Optional[datetime] = None  # 发布时间
    extra: dict = field(default_factory=dict)  # 额外信息
    
    # AI 评分结果 (后续填充)
    ai_score: float = 0.0            # AI 综合评分
    ai_title: str = ""               # AI 生成的中文标题
    ai_summary: str = ""             # AI 生成的深度简讯 (120-140字)
    ai_category: str = ""            # AI 分类
    ai_reason: str = ""              # (已弃用) 评分理由
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "score": self.score,
            "comments": self.comments,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "ai_score": self.ai_score,
            "ai_title": self.ai_title,
            "ai_summary": self.ai_summary,
        }
    
    def __str__(self) -> str:
        return f"[{self.source}] {self.title} (score: {self.score})"


class BaseFetcher(ABC):
    """数据抓取器基类"""
    
    name: str = "base"
    
    @abstractmethod
    def fetch(self, limit: int = 20) -> List[ContentItem]:
        """
        获取内容列表
        
        Args:
            limit: 最大获取数量
            
        Returns:
            ContentItem 列表
        """
        pass
    
    def filter_by_keywords(self, items: List[ContentItem], keywords: List[str]) -> List[ContentItem]:
        """
        根据关键词过滤
        
        Args:
            items: 内容列表
            keywords: 关键词列表
            
        Returns:
            过滤后的列表
        """
        if not keywords:
            return items
            
        filtered = []
        keywords_lower = [k.lower() for k in keywords]
        
        for item in items:
            text = f"{item.title} {item.description}".lower()
            if any(kw in text for kw in keywords_lower):
                filtered.append(item)
                
        return filtered
