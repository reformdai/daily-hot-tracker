"""
聚合管道增强：去重合并、信源分级、热度/时效评分、候选多样性、跨天去重（防重复推送）
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

from fetchers.base import ContentItem


@lru_cache(maxsize=4096)
def normalize_title(title: str) -> str:
    t = (title or "").lower().strip()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


# ==================== URL 归一 ====================

TRACKING_PARAMS = {"ref", "ref_src", "source", "fbclid", "gclid", "mc_cid", "mc_eid", "spm", "from", "share"}
ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?")


def canonical_url(url: str) -> str:
    """把同一篇内容的不同链接写法归一：去 www/m 前缀、追踪参数、锚点和尾部斜杠；
    arxiv abs/pdf/各版本以及 HF Papers 页面统一为 arxiv:<id>，使论文跨源合并。"""
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url
    host = (parts.hostname or "").lower()
    for prefix in ("www.", "m.", "mobile."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    path = parts.path or "/"

    if host in ("arxiv.org", "export.arxiv.org", "huggingface.co", "alphaxiv.org"):
        if host != "huggingface.co" or path.startswith("/papers/"):
            match = ARXIV_ID.search(path)
            if match:
                return f"arxiv:{match.group(1)}"

    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    path = re.sub(r"/+$", "", path) or "/"
    if host == "github.com":
        # 仓库主页大小写不敏感，只保留 owner/repo
        segs = [s for s in path.split("/") if s]
        if len(segs) >= 2:
            path = "/" + "/".join(segs[:2]).lower()
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


# ==================== 信源分级与来源族 ====================

TIER_WEIGHTS = {"T1": 1.0, "T2": 0.6, "T3": 0.3}


def source_family(source: str) -> str:
    """独立「参与方」：同一平台的多个子源（各 subreddit）算一个，跨源佐证才有意义。"""
    if not source:
        return ""
    if source.startswith("Reddit"):
        return "Reddit"
    return source


def source_tier(item: ContentItem, tiers: Optional[Dict[str, str]] = None) -> str:
    tier = (item.extra or {}).get("tier")
    if tier in TIER_WEIGHTS:
        return tier
    tiers = tiers or {}
    return tiers.get(item.source) or tiers.get(source_family(item.source)) or "T3"


def tier_weight(tier: str) -> float:
    return TIER_WEIGHTS.get(tier, TIER_WEIGHTS["T3"])


# ==================== 互动热度（按来源族归一） ====================

def annotate_engagement(items: List[ContentItem]) -> List[ContentItem]:
    """不同平台的分数量纲不同（HN points、GitHub 今日 star、HF 投票），
    在同一来源族内按分位数归一到 0-1；没有分数的来源记 0，靠分级、时效和佐证排序。"""
    by_family: Dict[str, List[ContentItem]] = {}
    for item in items:
        by_family.setdefault(source_family(item.source), []).append(item)
    for members in by_family.values():
        scored = sorted((m for m in members if (m.score or 0) + (m.comments or 0) > 0),
                        key=lambda m: (m.score or 0) + (m.comments or 0) * 0.5)
        n = len(scored)
        for rank, item in enumerate(scored, 1):
            item.extra = item.extra or {}
            item.extra["engagement"] = round(rank / n, 3)
        for item in members:
            item.extra = item.extra or {}
            item.extra.setdefault("engagement", 0.0)
    return items


# ==================== 去重合并 ====================

def _lead_key(item: ContentItem, tiers: Optional[Dict[str, str]]):
    # 代表条目：官方一手优先，其次描述更完整，再次热度更高
    return (tier_weight(source_tier(item, tiers)), min(len(item.description or ""), 300), item.score)


def deduplicate_items(
    items: List[ContentItem],
    threshold: float = 0.84,
    tiers: Optional[Dict[str, str]] = None,
) -> List[ContentItem]:
    """先按归一 URL 合并，再按标题相似度合并；合并后记录全部来源与独立参与方。"""
    if not items:
        return []

    ordered = sorted(items, key=lambda x: x.score, reverse=True)
    groups: List[List[ContentItem]] = []
    by_url: Dict[str, int] = {}
    leads: List[ContentItem] = []

    for item in ordered:
        key = canonical_url(item.url)
        idx = by_url.get(key) if key else None
        if idx is None:
            for i, lead in enumerate(leads):
                if title_similarity(item.title, lead.title) >= threshold:
                    idx = i
                    break
        if idx is None:
            groups.append([item])
            leads.append(item)
            idx = len(groups) - 1
        else:
            groups[idx].append(item)
        if key:
            by_url.setdefault(key, idx)

    deduped: List[ContentItem] = []
    for members in groups:
        lead = max(members, key=lambda m: _lead_key(m, tiers))
        lead.extra = lead.extra or {}
        families = sorted({source_family(m.source) for m in members if m.source})
        times = [m.published_at for m in members if m.published_at]

        if len(members) > 1:
            # 合并信号：热度取最大，描述取最完整，时间记录首次与最近一次出现
            lead.score = max(m.score for m in members)
            lead.comments = max(m.comments for m in members)
            richest = max(members, key=lambda m: len(m.description or ""))
            if len(richest.description or "") > len(lead.description or ""):
                lead.extra["source_description"] = lead.description
                lead.description = richest.description
            lead.extra["engagement"] = max((m.extra or {}).get("engagement", 0.0) for m in members)
            best_tier = max((source_tier(m, tiers) for m in members), key=tier_weight)
            lead.extra["tier"] = best_tier
            for m in members:
                if m is not lead and (m.extra or {}).get("hn_url"):
                    lead.extra.setdefault("hn_url", m.extra["hn_url"])

        lead.extra["merged_sources"] = sorted({m.source for m in members if m.source})
        lead.extra["merged_urls"] = sorted({m.url for m in members if m.url})
        lead.extra["families"] = families
        lead.extra["source_count"] = len(families)
        if times:
            lead.extra["first_seen_at"] = min(times).isoformat()
            lead.extra["latest_at"] = max(times).isoformat()
        deduped.append(lead)

    return deduped


# ==================== 时效 ====================

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def latest_time(item: ContentItem) -> Optional[datetime]:
    value = (item.extra or {}).get("latest_at")
    if value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return item.published_at


def filter_fresh(
    items: List[ContentItem],
    max_age_hours: float,
    now: Optional[datetime] = None,
    overrides: Optional[Dict[str, float]] = None,
) -> Tuple[List[ContentItem], List[ContentItem]]:
    """按最近一次出现时间过滤旧内容；没有时间的条目（榜单类）保留。
    overrides 按来源族覆盖窗口（如 ArXiv 时间是投稿时间，周末积压后公布会晚 3 天以上）。
    返回 (保留, 丢弃)。"""
    now = now or _utcnow()
    overrides = overrides or {}
    kept, dropped = [], []
    for item in items:
        families = (item.extra or {}).get("families") or [source_family(item.source)]
        hours = max([overrides.get(f, max_age_hours) for f in families])
        t = latest_time(item)
        (dropped if hours > 0 and t and t < now - timedelta(hours=hours) else kept).append(item)
    return kept, dropped


# ==================== 综合排序分 ====================

RANK_WEIGHTS = {"engagement": 0.35, "tier": 0.25, "recency": 0.20, "corroboration": 0.20}
RECENCY_HALF_LIFE_HOURS = 24


def apply_quality_score(
    items: List[ContentItem],
    tiers: Optional[Dict[str, str]] = None,
    now: Optional[datetime] = None,
) -> List[ContentItem]:
    """
    参考 AIHOT 的热度思路，综合四个 0-1 信号，得到 0-100 的 final_rank_score：
    - engagement：来源族内互动分位数（不同平台分数不可直接比较）
    - tier：T1 官方一手 1.0 / T2 媒体 0.6 / T3 社区 0.3
    - recency：按最近一次出现时间做 24 小时半衰；无时间记 0.5
    - corroboration：独立来源族数量，2 个 0.5，3 个及以上 1.0
    """
    now = now or _utcnow()
    if any("engagement" not in (item.extra or {}) for item in items):
        annotate_engagement([i for i in items if "engagement" not in (i.extra or {})])

    for item in items:
        item.extra = item.extra or {}
        tier = item.extra.get("tier") if item.extra.get("tier") in TIER_WEIGHTS else source_tier(item, tiers)
        t = latest_time(item)
        if t:
            age_hours = max(0.0, (now - t).total_seconds() / 3600)
            recency = 0.5 ** (age_hours / RECENCY_HALF_LIFE_HOURS)
        else:
            recency = 0.5
        participants = int(item.extra.get("source_count", 1) or 1)
        corroboration = min(1.0, (participants - 1) / 2)
        signals = {
            "engagement": float(item.extra.get("engagement", 0.0)),
            "tier": tier_weight(tier),
            "recency": round(recency, 3),
            "corroboration": corroboration,
        }
        final = 100 * sum(RANK_WEIGHTS[k] * v for k, v in signals.items())
        item.extra["tier"] = tier
        item.extra["rank_signals"] = signals
        item.extra["quality_score"] = round(final, 2)
        item.extra["final_rank_score"] = round(final, 2)

    return items


def sort_by_final_score(items: List[ContentItem]) -> List[ContentItem]:
    return sorted(items, key=lambda x: (x.extra or {}).get("final_rank_score", x.score), reverse=True)


def select_diverse_candidates(
    items: Iterable[ContentItem],
    limit: int,
    per_family_cap: int,
) -> List[ContentItem]:
    """按综合分取前 limit 条，但单一来源族最多 per_family_cap 条；名额用不完再按分数补齐。"""
    ranked = sort_by_final_score(list(items))
    if per_family_cap <= 0:
        return ranked[:limit]
    selected, overflow, counts = [], [], {}
    for item in ranked:
        family = source_family(item.source)
        if counts.get(family, 0) < per_family_cap:
            counts[family] = counts.get(family, 0) + 1
            selected.append(item)
        else:
            overflow.append(item)
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        selected.extend(overflow[: limit - len(selected)])
    return sort_by_final_score(selected)


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
