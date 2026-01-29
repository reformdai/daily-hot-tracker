#!/usr/bin/env python3
"""
每日热榜聚合器 - 主程序入口
"""
import argparse
import sys
from typing import List

import config
from fetchers import (
    ContentItem,
    HackerNewsFetcher,
    ProductHuntFetcher,
    GitHubTrendingFetcher,
    RedditFetcher,
    RSSFetcher,
)
from ai_filter import AIFilter
from feishu import FeishuBot


def fetch_all_sources() -> List[ContentItem]:
    """从所有数据源获取内容"""
    all_items = []
    
    print("=" * 50)
    print("📡 开始获取各平台数据...")
    print("=" * 50)
    
    # Hacker News
    if "hackernews" in config.ENABLED_SOURCES:
        print("\n[1/5] 获取 Hacker News...")
        fetcher = HackerNewsFetcher()
        items = fetcher.fetch(limit=config.MAX_ITEMS_PER_SOURCE)
        print(f"      获取到 {len(items)} 条")
        all_items.extend(items)
    
    # Product Hunt
    if "producthunt" in config.ENABLED_SOURCES:
        print("\n[2/5] 获取 Product Hunt...")
        fetcher = ProductHuntFetcher(token=config.PRODUCTHUNT_TOKEN)
        items = fetcher.fetch(limit=config.MAX_ITEMS_PER_SOURCE)
        print(f"      获取到 {len(items)} 条")
        all_items.extend(items)
    
    # GitHub Trending
    if "github_trending" in config.ENABLED_SOURCES:
        print("\n[3/5] 获取 GitHub Trending...")
        fetcher = GitHubTrendingFetcher()
        items = fetcher.fetch(limit=config.MAX_ITEMS_PER_SOURCE)
        print(f"      获取到 {len(items)} 条")
        all_items.extend(items)
    
    # Reddit
    if "reddit" in config.ENABLED_SOURCES:
        print("\n[4/5] 获取 Reddit...")
        fetcher = RedditFetcher(subreddits=config.REDDIT_SUBREDDITS)
        items = fetcher.fetch(limit=config.MAX_ITEMS_PER_SOURCE)
        print(f"      获取到 {len(items)} 条")
        all_items.extend(items)
    
    # RSS Feeds
    if "rss_feeds" in config.ENABLED_SOURCES:
        print("\n[5/5] 获取 RSS 订阅...")
        fetcher = RSSFetcher(feeds=config.RSS_FEEDS)
        items = fetcher.fetch(limit=config.MAX_ITEMS_PER_SOURCE)
        print(f"      获取到 {len(items)} 条")
        all_items.extend(items)
    
    print(f"\n📊 总共获取 {len(all_items)} 条内容")
    return all_items


def prefilter_by_keywords(items: List[ContentItem]) -> List[ContentItem]:
    """根据关键词预筛选"""
    print("\n🔍 关键词预筛选...")
    
    keywords_lower = [k.lower() for k in config.KEYWORDS]
    filtered = []
    
    for item in items:
        text = f"{item.title} {item.description} {item.category}".lower()
        if any(kw in text for kw in keywords_lower):
            filtered.append(item)
    
    print(f"   筛选后剩余 {len(filtered)} 条 (原 {len(items)} 条)")
    
    # 按热度排序，只保留前 25 条给 AI 评分（加速）
    filtered.sort(key=lambda x: x.score, reverse=True)
    if len(filtered) > 25:
        print(f"   按热度取前 25 条给 AI 评分")
        filtered = filtered[:25]
    
    return filtered


def ai_score_and_rank(items: List[ContentItem]) -> List[ContentItem]:
    """AI 评分和排序"""
    print("\n🤖 AI 评分中...")
    print(f"   使用模型: {config.AI_PROVIDER}")
    
    ai_filter = AIFilter(provider=config.AI_PROVIDER)
    top_items = ai_filter.filter_top(
        items, 
        top_n=config.TOP_N_ITEMS,
        min_score=config.MIN_SCORE_THRESHOLD
    )
    
    print(f"   精选 {len(top_items)} 条优质内容")
    return top_items


def push_to_feishu(items: List[ContentItem]) -> bool:
    """推送到飞书"""
    print("\n📤 推送到飞书...")
    
    if not config.FEISHU_WEBHOOK_URL:
        print("   ⚠️  飞书 Webhook 未配置，跳过推送")
        return False
    
    bot = FeishuBot()
    success = bot.send_daily_digest(items)
    
    if success:
        print("   ✅ 推送成功!")
    else:
        print("   ❌ 推送失败")
    
    return success


def print_results(items: List[ContentItem]):
    """打印结果到控制台"""
    print("\n" + "=" * 50)
    print("📋 今日精选内容")
    print("=" * 50)
    
    for idx, item in enumerate(items, 1):
        print(f"\n{idx}. [{item.ai_score:.1f}分] {item.title}")
        print(f"   来源: {item.source}")
        print(f"   链接: {item.url}")
        if item.ai_reason:
            print(f"   理由: {item.ai_reason}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="每日热榜聚合器")
    parser.add_argument("--no-ai", action="store_true", help="跳过 AI 评分")
    parser.add_argument("--no-push", action="store_true", help="跳过飞书推送")
    parser.add_argument("--dry-run", action="store_true", help="仅测试，不推送")
    parser.add_argument("--limit", type=int, default=10, help="最终保留条数")
    args = parser.parse_args()
    
    if args.limit:
        config.TOP_N_ITEMS = args.limit
    
    try:
        # 1. 获取所有数据源
        all_items = fetch_all_sources()
        
        if not all_items:
            print("❌ 未获取到任何内容")
            return 1
        
        # 2. 关键词预筛选
        filtered_items = prefilter_by_keywords(all_items)
        
        if not filtered_items:
            print("❌ 关键词筛选后无内容")
            # 如果筛选后为空，使用原始热度排序
            filtered_items = sorted(all_items, key=lambda x: x.score, reverse=True)[:50]
        
        # 3. AI 评分
        if args.no_ai:
            print("\n⏭️  跳过 AI 评分")
            # 按原始热度排序
            top_items = sorted(filtered_items, key=lambda x: x.score, reverse=True)[:config.TOP_N_ITEMS]
            for item in top_items:
                item.ai_score = item.score / 10  # 简单转换
                item.ai_reason = "热度排序"
        else:
            top_items = ai_score_and_rank(filtered_items)
        
        if not top_items:
            print("❌ 无符合条件的内容")
            return 1
        
        # 4. 打印结果
        print_results(top_items)
        
        # 5. 推送到飞书
        if not args.no_push and not args.dry_run:
            push_to_feishu(top_items)
        else:
            print("\n⏭️  跳过飞书推送")
        
        print("\n✅ 完成!")
        return 0
        
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
