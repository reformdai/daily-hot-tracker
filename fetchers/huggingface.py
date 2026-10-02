"""
Hugging Face 公开 API（无需 key）
- 每日论文：社区投票选出的当日论文，自带摘要，补足 ArXiv「最新」不等于「重要」的问题
- 趋势模型：按 trendingScore 排序的新模型，覆盖「模型发布」
"""
from datetime import datetime, timedelta, timezone
from itertools import zip_longest
from typing import List

from .base import BaseFetcher, ContentItem, get_with_retry
from .list_sources import clean_text, parse_date


class HuggingFaceFetcher(BaseFetcher):

    name = "Hugging Face"
    API = "https://huggingface.co/api"

    def __init__(self, daily_papers: bool = True, trending_models: bool = True, model_max_age_days: int = 14):
        self.daily_papers = daily_papers
        self.trending_models = trending_models
        self.model_max_age_days = model_max_age_days

    def fetch(self, limit: int = 20) -> List[ContentItem]:
        if limit <= 0:
            return []
        batches = []
        if self.daily_papers:
            batches.append(self.fetch_daily_papers(limit))
        if self.trending_models:
            batches.append(self.fetch_trending_models(limit))
        # 论文与模型交替取样，避免一方占满额度
        return [item for row in zip_longest(*batches) for item in row if item is not None][:limit]

    def fetch_daily_papers(self, limit: int) -> List[ContentItem]:
        resp = get_with_retry(f"{self.API}/daily_papers?limit=50", "HF daily papers")
        if resp is None:
            return []
        try:
            rows = resp.json()
        except ValueError:
            print("[HF daily papers] response is not JSON")
            return []
        items = []
        for row in rows if isinstance(rows, list) else []:
            paper = row.get("paper") if isinstance(row, dict) else None
            if not isinstance(paper, dict) or not paper.get("id"):
                continue
            title = clean_text(row.get("title") or paper.get("title") or "")
            if not title:
                continue
            paper_id = paper["id"]
            authors = [a.get("name", "") for a in paper.get("authors", []) if isinstance(a, dict)]
            author = ", ".join(a for a in authors[:3] if a) + (f" 等 {len(authors)} 人" if len(authors) > 3 else "")
            items.append(ContentItem(
                id=f"hfpaper_{paper_id}",
                title=title,
                url=f"https://huggingface.co/papers/{paper_id}",
                source="Hugging Face Papers",
                category="论文研究",
                description=clean_text(row.get("summary") or paper.get("summary") or "")[:800],
                author=author,
                score=int(paper.get("upvotes") or 0),
                comments=int(row.get("numComments") or 0),
                published_at=parse_date(row.get("publishedAt") or paper.get("publishedAt")),
                extra={"arxiv_id": paper_id, "ai_keywords": paper.get("ai_keywords") or []},
            ))
        items.sort(key=lambda x: x.score, reverse=True)
        print(f"[HF daily papers] {len(items)} papers")
        return items[:limit]

    def fetch_trending_models(self, limit: int) -> List[ContentItem]:
        url = f"{self.API}/models?sort=trendingScore&direction=-1&limit=50&full=false"
        resp = get_with_retry(url, "HF trending models")
        if resp is None:
            return []
        try:
            rows = resp.json()
        except ValueError:
            print("[HF trending models] response is not JSON")
            return []
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=self.model_max_age_days)
        items, too_old = [], 0
        for row in rows if isinstance(rows, list) else []:
            model_id = (row.get("id") or row.get("modelId")) if isinstance(row, dict) else None
            if not model_id:
                continue
            created = parse_date(row.get("createdAt"))
            if created and created < cutoff:
                too_old += 1
                continue
            tags = [t for t in row.get("tags", []) if isinstance(t, str) and ":" not in t][:6]
            pipeline = row.get("pipeline_tag") or ""
            description = " · ".join(x for x in [pipeline, ", ".join(tags)] if x)
            items.append(ContentItem(
                id=f"hfmodel_{model_id.replace('/', '_')}",
                title=model_id,
                url=f"https://huggingface.co/{model_id}",
                source="Hugging Face Trending",
                category="模型发布",
                description=description,
                author=model_id.split("/")[0] if "/" in model_id else "",
                score=int(row.get("trendingScore") or 0),
                # 榜单是「当前在涨」，创建时间不代表今天的热度，不作为发布时间参与时效过滤
                published_at=None,
                extra={
                    "created_at": created.isoformat() if created else None,
                    "likes": row.get("likes", 0),
                    "downloads": row.get("downloads", 0),
                    "pipeline_tag": pipeline,
                },
            ))
        print(f"[HF trending models] {len(items)} models (skipped {too_old} older than {self.model_max_age_days} days)")
        return items[:limit]
