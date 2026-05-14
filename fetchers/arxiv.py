"""
ArXiv 论文抓取
获取 AI/ML 领域最新论文，补充「论文研究」版块。
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List
from .base import BaseFetcher, ContentItem


class ArxivFetcher(BaseFetcher):

    name = "ArXiv"

    BASE_URL = "http://export.arxiv.org/api/query"

    DEFAULT_CATEGORIES = [
        "cs.AI",
        "cs.CL",
        "cs.LG",
        "cs.CV",
    ]

    def __init__(self, categories: List[str] = None):
        self.categories = categories or self.DEFAULT_CATEGORIES

    def fetch(self, limit: int = 20) -> List[ContentItem]:
        cat_query = " OR ".join(f"cat:{c}" for c in self.categories)
        url = (
            f"{self.BASE_URL}?search_query={cat_query}"
            f"&start=0&max_results={limit}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )

        import time
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=60)
                if resp.status_code == 429:
                    wait = 3 * (attempt + 1)
                    print(f"[ArXiv] 限流，等待 {wait}s 后重试...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return self._parse_response(resp.text, limit)
            except requests.exceptions.HTTPError:
                if attempt < 2:
                    continue
                print(f"[ArXiv] 获取失败: HTTP {resp.status_code}")
                return []
            except Exception as e:
                print(f"[ArXiv] 获取失败: {e}")
                return []
        return []

    def _parse_response(self, xml_text: str, limit: int) -> List[ContentItem]:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_text)
        items = []

        for entry in root.findall("atom:entry", ns)[:limit]:
            title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
            summary = (entry.findtext("atom:summary", "", ns) or "").strip().replace("\n", " ")

            link = ""
            for link_el in entry.findall("atom:link", ns):
                if link_el.get("type") == "text/html" or link_el.get("rel") == "alternate":
                    link = link_el.get("href", "")
                    break
            if not link:
                link = entry.findtext("atom:id", "", ns)

            published_at = None
            pub_str = entry.findtext("atom:published", "", ns)
            if pub_str:
                try:
                    dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    published_at = dt.replace(tzinfo=None)
                except Exception:
                    pass

            authors = []
            for author_el in entry.findall("atom:author", ns):
                name = author_el.findtext("atom:name", "", ns)
                if name:
                    authors.append(name)
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += f" 等 {len(authors)} 人"

            categories = []
            for cat_el in entry.findall("atom:category", ns):
                term = cat_el.get("term", "")
                if term:
                    categories.append(term)

            items.append(ContentItem(
                id=f"arxiv_{hash(link)}",
                title=title,
                url=link,
                source="ArXiv",
                category="论文研究",
                description=summary[:500],
                author=author_str,
                published_at=published_at,
                extra={"arxiv_categories": categories},
            ))

        return items
