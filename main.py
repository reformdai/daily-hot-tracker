#!/usr/bin/env python3
"""
每日热榜聚合器 - 主程序入口
"""
import argparse
import io
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple
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
    WebListFetcher,
    JsonListFetcher,
    AIHotFetcher,
    ArxivFetcher,
    HNSearchFetcher,
    HuggingFaceFetcher,
)
from ai_filter import AIFilter
from feishu import FeishuBot
from enrich import enrich_items
from pipeline import (
    annotate_engagement,
    deduplicate_items,
    apply_quality_score,
    filter_fresh,
    select_diverse_candidates,
    sort_by_final_score,
    apply_light_source_caps,
    source_family,
)
from rss_output import generate_rss_feed


class _ThreadOutput(io.TextIOBase):
    """并发抓取时按线程缓存各来源的日志，结束后按配置顺序整段打印，避免日志交错"""

    def __init__(self, fallback):
        self.fallback = fallback
        self.local = threading.local()

    def write(self, text):
        buffer = getattr(self.local, "buffer", None)
        return (buffer or self.fallback).write(text)

    def flush(self):
        self.fallback.flush()


def _source_limit(key: str) -> int:
    return config.SOURCE_ITEM_LIMITS.get(key, config.MAX_ITEMS_PER_SOURCE)


def source_registry() -> List[Tuple[str, str, Callable[[], List[ContentItem]]]]:
    """(配置键, 显示名, 抓取函数)；新增来源在这里登记，并加入 config.ENABLED_SOURCES"""
    return [
        ("hackernews", "Hacker News", lambda: HackerNewsFetcher().fetch(limit=_source_limit("hackernews"))),
        ("hn_search", "Hacker News 搜索", lambda: HNSearchFetcher(
            queries=config.HN_SEARCH_QUERIES, min_points=config.HN_SEARCH_MIN_POINTS,
            hours=config.HN_SEARCH_HOURS).fetch(limit=_source_limit("hn_search"))),
        ("producthunt", "Product Hunt", lambda: ProductHuntFetcher(token=config.PRODUCTHUNT_TOKEN).fetch(limit=_source_limit("producthunt"))),
        ("github_trending", "GitHub Trending", lambda: GitHubTrendingFetcher().fetch(limit=_source_limit("github_trending"))),
        ("huggingface", "Hugging Face", lambda: HuggingFaceFetcher(
            daily_papers=config.HF_DAILY_PAPERS, trending_models=config.HF_TRENDING_MODELS,
            model_max_age_days=config.HF_MODEL_MAX_AGE_DAYS).fetch(limit=_source_limit("huggingface"))),
        ("reddit", "Reddit", lambda: RedditFetcher(subreddits=config.REDDIT_SUBREDDITS).fetch(limit=_source_limit("reddit"))),
        ("rss_feeds", "RSS 订阅", lambda: RSSFetcher(feeds=config.RSS_FEEDS).fetch(limit=_source_limit("rss_feeds"))),
        ("web_list", "网页列表", lambda: WebListFetcher(config.WEB_SOURCES).fetch(limit=_source_limit("web_list"))),
        ("json_list", "JSON 列表", lambda: JsonListFetcher(config.JSON_SOURCES).fetch(limit=_source_limit("json_list"))),
        ("aihot", "AIHOT 精选", lambda: AIHotFetcher().fetch(limit=_source_limit("aihot"))),
        ("arxiv", "ArXiv 论文", lambda: ArxivFetcher(categories=config.ARXIV_CATEGORIES).fetch(limit=_source_limit("arxiv"))),
    ]


def fetch_all_sources(health: List[Dict] = None) -> List[ContentItem]:
    """并发获取所有启用的数据源；单源失败不影响其他来源。health 传入列表时写入各源健康记录"""
    enabled = [s for s in source_registry() if s[0] in config.ENABLED_SOURCES]
    total = len(enabled)

    print("=" * 50)
    print(f"📡 开始获取各平台数据（{total} 个来源，并发 {config.FETCH_WORKERS}）...")
    print("=" * 50)

    output = _ThreadOutput(sys.stdout)

    def run(source):
        key, name, fetch_fn = source
        output.local.buffer = io.StringIO()
        started = time.monotonic()
        record = {"key": key, "name": name, "items": 0, "status": "ok", "error": ""}
        items: List[ContentItem] = []
        try:
            items = fetch_fn() or []
        except Exception as exc:
            record.update(status="error", error=type(exc).__name__)
        record["items"] = len(items)
        if record["status"] == "ok" and not items:
            record["status"] = "empty"
        record["seconds"] = round(time.monotonic() - started, 1)
        log = output.local.buffer.getvalue()
        output.local.buffer = None
        return items, record, log

    real_stdout = sys.stdout
    sys.stdout = output
    try:
        with ThreadPoolExecutor(max_workers=max(1, config.FETCH_WORKERS)) as pool:
            results = list(pool.map(run, enabled))
    finally:
        sys.stdout = real_stdout

    all_items: List[ContentItem] = []
    for idx, (items, record, log) in enumerate(results, 1):
        print(f"\n[{idx}/{total}] {record['name']}（{record['seconds']}s）")
        if log.strip():
            print("      " + log.rstrip().replace("\n", "\n      "))
        if record["status"] == "error":
            print(f"      {record['name']} 获取失败 ({record['error']})，继续其他来源")
        else:
            print(f"      获取到 {record['items']} 条")
        all_items.extend(items)
        if health is not None:
            health.append(record)

    failed = [r["name"] for _, r, _ in results if r["status"] != "ok"]
    print(f"\n📊 总共获取 {len(all_items)} 条内容" + (f"；无数据/失败: {', '.join(failed)}" if failed else ""))
    return all_items


def _keyword_patterns(keywords: List[str]) -> List[re.Pattern]:
    """英文/数字关键词按词边界匹配（允许复数），中文按子串匹配"""
    patterns = []
    for kw in keywords:
        kw = kw.strip().lower()
        if not kw:
            continue
        if re.search(r"[a-z0-9]", kw):
            patterns.append(re.compile(rf"(?<![a-z0-9]){re.escape(kw)}(?:s|es)?(?![a-z0-9])"))
        else:
            patterns.append(re.compile(re.escape(kw)))
    return patterns


def matches_keywords(item: ContentItem, patterns: List[re.Pattern]) -> bool:
    text = f"{item.title} {item.description} {item.category}".lower()
    return any(p.search(text) for p in patterns)


def prefilter_by_keywords(items: List[ContentItem]) -> List[ContentItem]:
    """关键词预筛选，再按综合分选出送 AI 的候选（单一来源族有名额上限）"""
    print("\n🔍 关键词预筛选...")

    patterns = _keyword_patterns(config.KEYWORDS)
    exempt = set(config.KEYWORD_EXEMPT_SOURCES)
    filtered = []

    for item in items:
        sources = set((item.extra or {}).get("merged_sources") or [item.source])
        if sources & exempt or matches_keywords(item, patterns):
            filtered.append(item)

    print(f"   筛选后剩余 {len(filtered)} 条 (原 {len(items)} 条)")

    limit = config.AI_CANDIDATE_LIMIT
    if len(filtered) > limit:
        filtered = select_diverse_candidates(filtered, limit, config.MAX_CANDIDATES_PER_FAMILY)
        print(f"   按综合分取前 {limit} 条给 AI 评分（单一来源族最多 {config.MAX_CANDIDATES_PER_FAMILY} 条）")
    else:
        filtered = sort_by_final_score(filtered)

    return filtered


def enrich_candidates(items: List[ContentItem]) -> None:
    """为候选补抓原文摘录"""
    print("\n📖 补抓原文摘录...")
    started = time.monotonic()
    stats = enrich_items(
        items,
        min_description=config.ENRICH_MIN_DESCRIPTION,
        max_chars=config.ENRICH_MAX_CHARS,
        workers=config.ENRICH_WORKERS,
        jina_fallback=config.JINA_READER_FALLBACK,
        jina_key=config.JINA_API_KEY,
    )
    if not stats:
        print("   描述均已足够，无需补抓")
        return
    summary = ", ".join(f"{k} {v}" for k, v in sorted(stats.items()))
    print(f"   {sum(stats.values())} 条尝试补抓（{summary}），用时 {time.monotonic() - started:.1f}s")


def write_run_log(health: List[Dict], candidates: List[ContentItem], selected: List[ContentItem]) -> None:
    """写信源健康报告与候选清单，便于排查「为什么没抓到/没入选」"""
    try:
        log_dir = Path(config.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        selected_ids = {item.id for item in selected}

        def row(item: ContentItem) -> Dict:
            extra = item.extra or {}
            return {
                "title": item.title, "url": item.url, "source": item.source,
                "family": source_family(item.source), "tier": extra.get("tier"),
                "merged_sources": extra.get("merged_sources"),
                "final_rank_score": extra.get("final_rank_score"),
                "rank_signals": extra.get("rank_signals"),
                "body_via": extra.get("body_via"),
                "ai_score": item.ai_score, "ai_category": item.ai_category,
                "selected": item.id in selected_ids,
            }

        path = log_dir / f"run-{stamp}.json"
        path.write_text(json.dumps({
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "sources": health,
            "candidates": [row(item) for item in candidates],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n🗂️  运行日志已写入: {path}")
    except OSError as exc:
        print(f"\n⚠️  运行日志写入失败: {exc}")


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
    """推送到飞书。仅当已配置的 Webhook 推送失败时返回 False，未配置视为跳过"""
    print("\n📤 推送到飞书...")

    if not config.FEISHU_WEBHOOK_URL:
        print("   ⚠️  飞书 Webhook 未配置，跳过推送")
        return True
    
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
    parser.add_argument("--no-enrich", action="store_true", help="跳过原文补抓")
    parser.add_argument("--no-log", action="store_true", help="不写 logs/ 运行日志")
    args = parser.parse_args()
    
    if args.limit:
        config.TOP_N_ITEMS = args.limit
    
    try:
        # 1. 获取所有数据源
        health: List[Dict] = []
        all_items = fetch_all_sources(health)
        
        if not all_items:
            print("❌ 未获取到任何内容")
            return 1
        
        # 2. 热度归一 → URL/标题去重合并 → 时效过滤 → 综合评分（分级、热度、时效、多源佐证）
        annotate_engagement(all_items)
        deduped_items = deduplicate_items(
            all_items, threshold=config.TITLE_DEDUP_SIMILARITY, tiers=config.SOURCE_TIERS)
        merged = sum(1 for item in deduped_items if (item.extra or {}).get("source_count", 1) > 1)
        print(f"\n🧹 去重后剩余 {len(deduped_items)} 条 (原 {len(all_items)} 条，其中 {merged} 条被多个来源同时报道)")

        fresh_items, stale_items = filter_fresh(
            deduped_items, config.MAX_ITEM_AGE_HOURS, overrides=config.MAX_ITEM_AGE_HOURS_BY_SOURCE)
        if stale_items:
            print(f"   ⏳ 丢弃 {len(stale_items)} 条超过 {config.MAX_ITEM_AGE_HOURS:g} 小时的旧内容")
        if not fresh_items:
            print("   ⚠️  时效过滤后无内容，回退使用全部条目")
            fresh_items = deduped_items

        enhanced_items = apply_quality_score(fresh_items, tiers=config.SOURCE_TIERS)

        # 3. 关键词预筛选
        filtered_items = prefilter_by_keywords(enhanced_items)

        if not filtered_items:
            print("❌ 关键词筛选后无内容")
            # 如果筛选后为空，使用增强排序回退
            filtered_items = select_diverse_candidates(
                enhanced_items, config.AI_CANDIDATE_LIMIT, config.MAX_CANDIDATES_PER_FAMILY)

        # 4. 原文补抓 + AI 评分
        if args.no_ai:
            print("\n⏭️  跳过 AI 评分")
            top_items = sort_by_final_score(filtered_items)[:config.TOP_N_ITEMS]
            for item in top_items:
                item.ai_score = round(min(10, ((item.extra or {}).get("final_rank_score", 0)) / 10), 1)
                item.ai_reason = "综合热度排序"
        else:
            if args.no_enrich:
                print("\n⏭️  跳过原文补抓")
            else:
                enrich_candidates(filtered_items)
            top_items = ai_score_and_rank(filtered_items)

        if not args.no_log:
            write_run_log(health, filtered_items, top_items)
        
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
            if not push_to_feishu(top_items):
                return 1
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
