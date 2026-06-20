#!/usr/bin/env python3
"""
每日热榜聚合器 - 主程序入口
"""
import argparse
import sys
from typing import List
from dotenv import load_dotenv

# 加载环境变量 (必须在导入 config 之前)
load_dotenv()

import config
from fetchers import (
    ContentItem,
    HackerNewsFetcher,
    ProductHuntFetcher,
    GitHubTrendingFetcher,
    RedditFetcher,
    RSSFetcher,
    AIHotFetcher,
    ArxivFetcher,
)
from ai_filter import AIFilter
from feishu import FeishuBot
from pipeline import (
    deduplicate_items,
    apply_quality_score,
    sort_by_final_score,
    apply_light_source_caps,
)
from rss_output import generate_rss_feed


def fetch_all_sources() -> List[ContentItem]:
    """从所有数据源获取内容"""
    all_items = []

    sources = [
        ("hackernews", "Hacker News", lambda: HackerNewsFetcher().fetch(limit=config.MAX_ITEMS_PER_SOURCE)),
        ("producthunt", "Product Hunt", lambda: ProductHuntFetcher(token=config.PRODUCTHUNT_TOKEN).fetch(limit=config.MAX_ITEMS_PER_SOURCE)),
        ("github_trending", "GitHub Trending", lambda: GitHubTrendingFetcher().fetch(limit=config.MAX_ITEMS_PER_SOURCE)),
        ("reddit", "Reddit", lambda: RedditFetcher(subreddits=config.REDDIT_SUBREDDITS).fetch(limit=config.MAX_ITEMS_PER_SOURCE)),
        ("rss_feeds", "RSS 订阅", lambda: RSSFetcher(feeds=config.RSS_FEEDS).fetch(limit=config.MAX_ITEMS_PER_SOURCE)),
        ("aihot", "AIHOT 精选", lambda: AIHotFetcher().fetch(limit=config.MAX_ITEMS_PER_SOURCE)),
        ("arxiv", "ArXiv 论文", lambda: ArxivFetcher(categories=config.ARXIV_CATEGORIES).fetch(limit=config.MAX_ITEMS_PER_SOURCE)),
    ]

    enabled = [s for s in sources if s[0] in config.ENABLED_SOURCES]
    total = len(enabled)

    print("=" * 50)
    print("📡 开始获取各平台数据...")
    print("=" * 50)

    for idx, (key, name, fetch_fn) in enumerate(enabled, 1):
        print(f"\n[{idx}/{total}] 获取 {name}...")
        items = fetch_fn()
        print(f"      获取到 {len(items)} 条")
        all_items.extend(items)

    print(f"\n📊 总共获取 {len(all_items)} 条内容")
    return all_items


def prefilter_by_keywords(items: List[ContentItem]) -> List[ContentItem]:
    """根据关键词预筛选（用增强后的 final_rank_score 排序）"""
    print("\n🔍 关键词预筛选...")

    keywords_lower = [k.lower() for k in config.KEYWORDS]
    filtered = []

    for item in items:
        text = f"{item.title} {item.description} {item.category}".lower()
        if any(kw in text for kw in keywords_lower):
            filtered.append(item)

    print(f"   筛选后剩余 {len(filtered)} 条 (原 {len(items)} 条)")

    filtered = sort_by_final_score(filtered)
    if len(filtered) > 25:
        print("   按综合热度取前 25 条给 AI 评分")
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
    parser.add_argument("--no-rss", action="store_true", help="跳过 RSS Feed 生成")
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
        
        # 2. 去重 + 质量评分增强（参考 multi-source digest 逻辑）
        deduped_items = deduplicate_items(all_items, threshold=config.TITLE_DEDUP_SIMILARITY)
        print(f"\n🧹 去重后剩余 {len(deduped_items)} 条 (原 {len(all_items)} 条)")

        enhanced_items = apply_quality_score(deduped_items, priority_sources=config.PRIORITY_SOURCES)

        # 3. 关键词预筛选
        filtered_items = prefilter_by_keywords(enhanced_items)

        if not filtered_items:
            print("❌ 关键词筛选后无内容")
            # 如果筛选后为空，使用增强排序回退
            filtered_items = sort_by_final_score(enhanced_items)[:50]
        
        # 4. AI 评分
        if args.no_ai:
            print("\n⏭️  跳过 AI 评分")
            top_items = sort_by_final_score(filtered_items)[:config.TOP_N_ITEMS]
            for item in top_items:
                item.ai_score = min(10, ((item.extra or {}).get("final_rank_score", item.score)) / 20)
                item.ai_reason = "综合热度排序"
        else:
            top_items = ai_score_and_rank(filtered_items)
        
        if not top_items:
            print("❌ 无符合条件的内容")
            return 1

        # 5. 轻量防霸榜（不依赖历史存储）
        top_items = apply_light_source_caps(
            top_items,
            max_github_items=config.MAX_GITHUB_ITEMS_PER_DAY,
            min_ai_score_for_github=config.MIN_AI_SCORE_FOR_GITHUB,
        )
        if not top_items:
            print("❌ 轻量限流后无可推送内容")
            return 1

        # 6. 打印结果
        print_results(top_items)

        # 7. 生成 RSS Feed
        if args.no_rss:
            print("\n⏭️  跳过 RSS Feed 生成")
        else:
            rss_path = generate_rss_feed(top_items, output_dir=config.RSS_OUTPUT_DIR)
            if rss_path:
                print(f"\n📡 RSS Feed 已生成: {rss_path}")

        # 8. 推送到飞书
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
