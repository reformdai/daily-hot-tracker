"""
聚合管道增强：去重、质量评分、跨天去重（防重复推送）
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from fetchers.base import ContentItem


def normalize_title(title: str) -> str:
    t = (title or "").lower().strip()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def deduplicate_items(items: List[ContentItem], threshold: float = 0.84) -> List[ContentItem]:
    """按标题相似度去重，并合并来源信息。"""
    if not items:
        return []

    # 先按热度排序，尽量保留更“强”的主条目
    ordered = sorted(items, key=lambda x: x.score, reverse=True)
    groups: List[Tuple[ContentItem, List[ContentItem]]] = []

    for item in ordered:
        matched = False
        for i, (lead, members) in enumerate(groups):
            if title_similarity(item.title, lead.title) >= threshold:
                members.append(item)
                # 用更高分条目做 lead
                if item.score > lead.score:
                    groups[i] = (item, members)
                matched = True
                break
        if not matched:
            groups.append((item, [item]))

    deduped: List[ContentItem] = []
    for lead, members in groups:
        sources = sorted({m.source for m in members if m.source})
        urls = sorted({m.url for m in members if m.url})

        lead.extra = lead.extra or {}
        lead.extra["merged_sources"] = sources
        lead.extra["merged_urls"] = urls
        lead.extra["source_count"] = len(sources)
        deduped.append(lead)

    return deduped


def apply_quality_score(
    items: List[ContentItem],
    priority_sources: List[str],
) -> List[ContentItem]:
    """
    参考 awesome-openclaw-usecases 的多源策略：
    - priority source +3
    - multi-source +5
    - recency +2
    - engagement +1
    """
    priority = {s.lower() for s in priority_sources}
    now = datetime.now()

    for item in items:
        quality = 0.0

        # 1) 优先来源
        if item.source and item.source.lower() in priority:
            quality += 3

        # 2) 多源合并
        source_count = int((item.extra or {}).get("source_count", 1))
        if source_count >= 2:
            quality += 5

        # 3) 时效性
        if item.published_at and (now - item.published_at) <= timedelta(days=1):
            quality += 2

        # 4) 互动热度（简单规则）
        if item.comments >= 20 or item.score >= 100:
            quality += 1

        item.extra = item.extra or {}
        item.extra["quality_score"] = round(quality, 2)
        item.extra["final_rank_score"] = round(item.score + quality * 10, 2)

    return items


def sort_by_final_score(items: List[ContentItem]) -> List[ContentItem]:
    return sorted(items, key=lambda x: (x.extra or {}).get("final_rank_score", x.score), reverse=True)


def apply_light_source_caps(
    items: List[ContentItem],
    max_github_items: int = 2,
    min_ai_score_for_github: float = 8.0,
) -> List[ContentItem]:
    """轻量限流：限制 GitHub Trending 条数，并提高其入选门槛。"""
    selected: List[ContentItem] = []
    github_count = 0

    for item in items:
        source_lower = (item.source or "").lower()
        is_github_trending = "github" in source_lower and "trending" in source_lower

        if is_github_trending:
            if item.ai_score < min_ai_score_for_github:
                continue
            if github_count >= max_github_items:
                continue
            github_count += 1

        selected.append(item)

    return selected


def _fingerprint(item: ContentItem) -> str:
    domain = urlparse(item.url).netloc.lower() if item.url else ""
    return f"{normalize_title(item.title)}|{domain}"


def load_sent_history(path: str) -> Dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_sent_history(path: str, data: Dict[str, str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def filter_already_sent(items: List[ContentItem], history_path: str, ttl_days: int = 7) -> List[ContentItem]:
    history = load_sent_history(history_path)
    now = datetime.now()

    # 清理过期记录
    alive: Dict[str, str] = {}
    for fp, dt in history.items():
        try:
            t = datetime.fromisoformat(dt)
            if (now - t).days <= ttl_days:
                alive[fp] = dt
        except Exception:
            continue

    filtered: List[ContentItem] = []
    for item in items:
        fp = _fingerprint(item)
        if fp not in alive:
            filtered.append(item)

    save_sent_history(history_path, alive)
    return filtered


def mark_sent(items: List[ContentItem], history_path: str) -> None:
    history = load_sent_history(history_path)
    now = datetime.now().isoformat()
    for item in items:
        history[_fingerprint(item)] = now
    save_sent_history(history_path, history)
