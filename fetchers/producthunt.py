"""
Product Hunt 数据抓取
"""
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from .base import BaseFetcher, ContentItem, stable_id


class ProductHuntFetcher(BaseFetcher):
    """Product Hunt 热门产品抓取"""

    name = "Product Hunt"
    RANKED_NAME = re.compile(r"^(\d+)\.\s*(.+)$")
    # 正常首页也会注入 /cdn-cgi/challenge-platform 脚本，不能作为标记
    CHALLENGE_MARKERS = ("Just a moment...", "cf-chl")

    def __init__(self, token: str = ""):
        self.token = token
    
    def fetch(self, limit: int = 20) -> List[ContentItem]:
        """获取 Product Hunt 今日热门"""
        items = []
        
        # 方法1: 使用 GraphQL API (需要 token)
        if self.token:
            items = self._fetch_with_api(limit)
        
        # 方法2: 爬取公开页面 (无需 token)
        if not items:
            items = self._fetch_from_page(limit)
            
        return items
    
    def _fetch_with_api(self, limit: int) -> List[ContentItem]:
        """使用官方 API 获取"""
        query = """
        query {
            posts(first: %d, order: VOTES) {
                edges {
                    node {
                        id
                        name
                        tagline
                        url
                        votesCount
                        commentsCount
                        website
                        createdAt
                        makers {
                            name
                        }
                        topics {
                            edges {
                                node {
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
        """ % limit
        
        try:
            resp = requests.post(
                "https://api.producthunt.com/v2/api/graphql",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json={"query": query},
                timeout=15
            )
            # 只打印状态码和 GraphQL message，不输出请求头
            if not resp.ok:
                print(f"[ProductHunt] API HTTP {resp.status_code}; check PRODUCTHUNT_TOKEN, falling back to page")
                return []
            data = resp.json()
            if data.get("errors"):
                messages = "; ".join(str(e.get("message", e)) for e in data["errors"])
                print(f"[ProductHunt] API GraphQL errors: {self._redact(messages)}")

            items = []
            for edge in ((data.get("data") or {}).get("posts") or {}).get("edges", []):
                node = edge["node"]
                makers = [m["name"] for m in node.get("makers", [])]
                topics = [t["node"]["name"] for t in node.get("topics", {}).get("edges", [])]
                
                items.append(ContentItem(
                    id=f"ph_{node['id']}",
                    title=node["name"],
                    url=node.get("website") or node["url"],
                    source="Product Hunt",
                    category=", ".join(topics[:3]) if topics else "Product",
                    description=node.get("tagline", ""),
                    author=", ".join(makers) if makers else "",
                    score=node.get("votesCount", 0),
                    comments=node.get("commentsCount", 0),
                    published_at=self._parse_created_at(node.get("createdAt")),
                    extra={
                        "ph_url": node["url"],
                    }
                ))
            return items

        except requests.RequestException as e:
            print(f"[ProductHunt] API network error ({type(e).__name__})")
            return []
        except Exception as e:
            print(f"[ProductHunt] API Error: {type(e).__name__}: {self._redact(str(e))}")
            return []

    def _redact(self, text: str) -> str:
        """服务端可能回显 token：先替换再截断，避免截断留下 token 片段"""
        if self.token:
            text = text.replace(self.token, "***")
        return text[:300]

    @staticmethod
    def _parse_created_at(value: str) -> Optional[datetime]:
        """ISO 8601 → naive UTC"""
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    
    def _fetch_from_page(self, limit: int) -> List[ContentItem]:
        """从公开页面爬取 (备用方案)"""
        try:
            resp = requests.get(
                "https://www.producthunt.com/",
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
                timeout=15
            )
            if resp.status_code in (403, 429, 503) and any(m in resp.text for m in self.CHALLENGE_MARKERS):
                print(f"[ProductHunt] Page blocked by bot challenge (HTTP {resp.status_code})")
                return []
            resp.raise_for_status()
            return self._parse_page(resp.text, limit)

        except requests.HTTPError as e:
            print(f"[ProductHunt] Page HTTP {e.response.status_code if e.response is not None else 'error'}")
            return []
        except requests.RequestException as e:
            print(f"[ProductHunt] Page network error ({type(e).__name__})")
            return []
        except Exception as e:
            print(f"[ProductHunt] Page scrape error: {e}")
            return []

    def _parse_page(self, html: str, limit: int) -> List[ContentItem]:
        soup = BeautifulSoup(html, 'html.parser')

        # 2026-09 首页结构：仅取「今日」区域，排除昨天/上周/上月榜单
        today = soup.select_one('[data-test="homepage-section-today"]')
        if today is not None:
            items = self._parse_today_section(today, limit)
            if not items:
                print("[ProductHunt] Today section found but no ranked /products/ links; markup may have changed")
            return items

        items = self._parse_legacy_posts(soup, limit)
        if not items:
            if any(m in html for m in self.CHALLENGE_MARKERS):
                print("[ProductHunt] Page looks like a bot challenge, no products parsed")
            else:
                print("[ProductHunt] Page structure changed: no homepage-section-today or post-item found")
        return items

    def _parse_today_section(self, today, limit: int) -> List[ContentItem]:
        """卡片结构：section > div > span > a[href^=/products/]「N. 名称」+ 相邻 span 标语。
        只接受带排名前缀的链接，推广位/话题/其他链接不计入。"""
        items = []
        seen = set()
        for link in today.select('a[href^="/products/"]'):
            match = self.RANKED_NAME.match(link.get_text(" ", strip=True))
            if not match:
                continue
            url = "https://www.producthunt.com" + link["href"].split("?")[0]
            if url in seen:
                continue
            seen.add(url)

            card = link.find_parent("section")
            wrapper = link.find_parent("span")
            tagline = wrapper.find_next_sibling("span") if wrapper else None
            topics = [a.get_text(strip=True) for a in card.select('a[href^="/topics/"]')] if card else []
            vote = card.select_one('[data-test="vote-button"]') if card else None
            comment = next(
                (b for b in card.find_all("button", recursive=False) if not b.get("data-test")), None
            ) if card else None

            items.append(ContentItem(
                id=stable_id("ph_page", url),
                title=match.group(2),
                url=url,
                source="Product Hunt",
                category=", ".join(topics[:3]) if topics else "Product",
                description=tagline.get_text(" ", strip=True) if tagline else "",
                score=self._to_int(vote),
                comments=self._to_int(comment),
                extra={"ph_rank": int(match.group(1))},
            ))
            if len(items) >= limit:
                break
        return items

    @staticmethod
    def _to_int(elem) -> int:
        text = elem.get_text(strip=True).replace(",", "") if elem else ""
        return int(text) if text.isdigit() else 0

    def _parse_legacy_posts(self, soup, limit: int) -> List[ContentItem]:
        """旧版首页 post-item 结构，保留兼容"""
        items = []
        for item in soup.select('[data-test="post-item"]')[:limit]:
            title_elem = item.select_one('[data-test="post-name"]')
            tagline_elem = item.select_one('[data-test="post-tagline"]')
            link_elem = item.select_one('a[href*="/posts/"]')

            if title_elem and link_elem:
                href = link_elem.get("href", "")
                url = f"https://www.producthunt.com{href}" if href.startswith("/") else href

                items.append(ContentItem(
                    id=stable_id("ph_page", url),
                    title=title_elem.get_text(strip=True),
                    url=url,
                    source="Product Hunt",
                    category="Product",
                    description=tagline_elem.get_text(strip=True) if tagline_elem else "",
                    score=0,  # 页面爬取难以获取准确票数
                ))
        return items
