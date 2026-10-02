"""
Fetchers 模块
"""
from .base import BaseFetcher, ContentItem
from .hackernews import HackerNewsFetcher
from .producthunt import ProductHuntFetcher
from .github_trending import GitHubTrendingFetcher
from .reddit import RedditFetcher
from .rss_feeds import RSSFetcher
from .list_sources import WebListFetcher, JsonListFetcher
from .aihot import AIHotFetcher
from .arxiv import ArxivFetcher
from .hn_search import HNSearchFetcher
from .huggingface import HuggingFaceFetcher

__all__ = [
    "BaseFetcher",
    "ContentItem",
    "HackerNewsFetcher",
    "ProductHuntFetcher",
    "GitHubTrendingFetcher",
    "RedditFetcher",
    "RSSFetcher",
    "WebListFetcher",
    "JsonListFetcher",
    "AIHotFetcher",
    "ArxivFetcher",
    "HNSearchFetcher",
    "HuggingFaceFetcher",
]
