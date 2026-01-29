"""
Product Hunt 数据抓取
"""
import requests
from datetime import datetime, timedelta
from typing import List
from .base import BaseFetcher, ContentItem


class ProductHuntFetcher(BaseFetcher):
    """Product Hunt 热门产品抓取"""
    
    name = "Product Hunt"
    
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
            resp.raise_for_status()
            data = resp.json()
            
            items = []
            for edge in data.get("data", {}).get("posts", {}).get("edges", []):
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
                    extra={
                        "ph_url": node["url"],
                    }
                ))
            return items
            
        except Exception as e:
            print(f"[ProductHunt] API Error: {e}")
            return []
    
    def _fetch_from_page(self, limit: int) -> List[ContentItem]:
        """从公开页面爬取 (备用方案)"""
        try:
            from bs4 import BeautifulSoup
            
            resp = requests.get(
                "https://www.producthunt.com/",
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
                timeout=15
            )
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = []
            
            # PH 页面结构可能变化，这里是一个基础实现
            # 实际使用时可能需要根据页面调整选择器
            for idx, item in enumerate(soup.select('[data-test="post-item"]')[:limit]):
                title_elem = item.select_one('[data-test="post-name"]')
                tagline_elem = item.select_one('[data-test="post-tagline"]')
                link_elem = item.select_one('a[href*="/posts/"]')
                
                if title_elem and link_elem:
                    href = link_elem.get("href", "")
                    url = f"https://www.producthunt.com{href}" if href.startswith("/") else href
                    
                    items.append(ContentItem(
                        id=f"ph_page_{idx}",
                        title=title_elem.get_text(strip=True),
                        url=url,
                        source="Product Hunt",
                        category="Product",
                        description=tagline_elem.get_text(strip=True) if tagline_elem else "",
                        score=0,  # 页面爬取难以获取准确票数
                    ))
            
            return items
            
        except Exception as e:
            print(f"[ProductHunt] Page scrape error: {e}")
            return []
