"""
推送记忆：记住最近几天推过什么，避免同一个热点每天重复推送。

两层判重：
1. 规则层（AI 评分前）：归一 URL 相同或原标题高度相似的条目直接剔除，候选名额留给新内容。
2. 语义层（AI 评分时）：把近几天已推送的中文标题交给模型，判断每条是新事件、
   已推事件的实质后续进展（保留并标注「后续」），还是同一事件的重复报道（剔除）。

GitHub Actions 每次运行都是全新机器，历史文件靠 workflow 里的 actions/cache 在运行之间保存。
缓存丢失时只是退化为无记忆，不影响推送。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fetchers.base import ContentItem
from pipeline import canonical_url, title_similarity

VERSION = 1


def _item_urls(item: ContentItem) -> List[str]:
    urls = [item.url, *((item.extra or {}).get("merged_urls") or [])]
    hn_url = (item.extra or {}).get("hn_url")
    if hn_url:
        urls.append(hn_url)
    return sorted({canonical_url(u) for u in urls if u})


class PushHistory:
    """最近 ttl_days 天已推送条目的轻量记录（JSON 文件）"""

    def __init__(self, path: str, ttl_days: int = 7, today: Optional[datetime] = None):
        self.path = Path(path)
        self.ttl_days = ttl_days
        self.today = (today or datetime.now()).date()
        self.entries: List[Dict] = []
        self.load_error = ""

    def load(self) -> "PushHistory":
        if not self.path.exists():
            return self
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            entries = data.get("entries", []) if isinstance(data, dict) else []
        except (OSError, ValueError) as exc:
            self.load_error = type(exc).__name__
            return self
        cutoff = self.today - timedelta(days=self.ttl_days)
        for entry in entries:
            try:
                day = datetime.fromisoformat(entry["date"]).date()
            except (KeyError, TypeError, ValueError):
                continue
            if day > cutoff:
                self.entries.append(entry)
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": VERSION, "entries": self.entries}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def record(self, items: List[ContentItem]) -> None:
        date = self.today.isoformat()
        for item in items:
            self.entries.append({
                "date": date,
                "title": item.title,
                "ai_title": item.ai_title or item.title,
                "category": item.ai_category,
                "urls": _item_urls(item),
                "followup": bool((item.extra or {}).get("followup")),
            })

    def match(self, item: ContentItem, threshold: float = 0.8) -> Optional[Dict]:
        """规则层判重：URL 相同，或原标题高度相似"""
        urls = set(_item_urls(item))
        for entry in self.entries:
            if urls & set(entry.get("urls") or []):
                return entry
        for entry in self.entries:
            if title_similarity(item.title, entry.get("title", "")) >= threshold:
                return entry
        return None

    def split_seen(self, items: List[ContentItem], threshold: float = 0.8) -> Tuple[List[ContentItem], List[ContentItem]]:
        fresh, seen = [], []
        for item in items:
            entry = self.match(item, threshold)
            if entry:
                item.extra = item.extra or {}
                item.extra["seen_on"] = entry.get("date")
                seen.append(item)
            else:
                fresh.append(item)
        return fresh, seen

    def headlines(self, limit: int = 60) -> List[str]:
        """给模型看的近期已推送标题，新的在前"""
        rows = sorted(self.entries, key=lambda e: e.get("date", ""), reverse=True)[:limit]
        return [f"{e['date'][5:]} {e.get('ai_title') or e.get('title', '')}" for e in rows]
