"""
Fetchers 模块
"""
from .base import BaseFetcher, ContentItem
from .hackernews import HackerNewsFetcher
from .producthunt import ProductHuntFetcher
from .github_trending import GitHubTrendingFetcher
from .reddit import RedditFetcher
from .rss_feeds import RSSFetcher
from .aihot import AIHotFetcher
from .arxiv import ArxivFetcher

__all__ = [
    "BaseFetcher",
    "ContentItem",
    "HackerNewsFetcher",
    "ProductHuntFetcher",
    "GitHubTrendingFetcher",
    "RedditFetcher",
    "RSSFetcher",
    "AIHotFetcher",
    "ArxivFetcher",
]
