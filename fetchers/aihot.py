"""
AIHOT (aihot.virxact.com) 数据源
从 AIHOT 平台获取 AI 领域精选热点。
公开 API，无需 API key，匿名免费使用。
"""
import requests
from datetime import datetime
from typing import List
from .base import BaseFetcher, ContentItem


class AIHotFetcher(BaseFetcher):

    name = "AIHOT"
    BASE_URL = "https://aihot.virxact.com/api/public"
    USER_AGENT = "Mozilla/5.0 (compatible; daily-hot-tracker/1.0)"

    CATEGORY_MAP = {
        "model": "模型发布",
        "product": "产品发布",
        "industry": "行业动态",
        "paper": "论文研究",
        "tip": "技巧与观点",
        "insight": "技巧与观点",
    }

    def __init__(self, api_key: str = ""):
        # api_key 参数保留向后兼容，实际不再需要
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def fetch(self, limit: int = 20) -> List[ContentItem]:
        return self._fetch_items(mode="selected", limit=limit)

    def fetch_daily_report(self) -> List[ContentItem]:
        return self._request("/daily", {}, limit=50)

    def fetch_all(self, limit: int = 50) -> List[ContentItem]:
        return self._fetch_items(mode="all", limit=limit)

    def search(self, keyword: str, limit: int = 20) -> List[ContentItem]:
        return self._request("/items", {"q": keyword, "limit": limit}, limit=limit)

    def _fetch_items(self, mode: str, limit: int) -> List[ContentItem]:
        return self._request("/items", {"mode": mode, "limit": limit}, limit=limit)

    def _request(self, endpoint: str, params: dict, limit: int = 20) -> List[ContentItem]:
        try:
            resp = self.session.get(
                f"{self.BASE_URL}{endpoint}",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            raw_items = data.get("items", []) if isinstance(data, dict) else data
            items = []
            for raw in raw_items[:limit]:
                published_at = None
                pub_str = raw.get("publishedAt") or raw.get("published_at")
                if pub_str:
                    try:
                        dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                        # 转为 naive datetime 保持与其他 fetcher 一致
                        published_at = dt.replace(tzinfo=None)
                    except Exception:
                        pass

                cat_key = raw.get("category", "")
                category = self.CATEGORY_MAP.get(cat_key, "行业动态")

                items.append(ContentItem(
                    id=f"aihot_{raw.get('id', hash(raw.get('title', '')))}",
                    title=raw.get("title", ""),
                    url=raw.get("url", ""),
                    source="AIHOT",
                    category=category,
                    description=raw.get("summary", ""),
                    author=raw.get("source", ""),
                    published_at=published_at,
                    extra={
                        "aihot_category": cat_key,
                        "title_en": raw.get("title_en", ""),
                        "original_source": raw.get("source", ""),
                    },
                ))

            return items

        except requests.exceptions.ConnectionError:
            print("[AIHOT] 无法连接到 AIHOT 服务")
            return []
        except Exception as e:
            print(f"[AIHOT] 获取失败: {e}")
            return []
