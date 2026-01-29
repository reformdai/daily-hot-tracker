"""
GitHub Trending 数据抓取
"""
import requests
from bs4 import BeautifulSoup
from typing import List
from .base import BaseFetcher, ContentItem


class GitHubTrendingFetcher(BaseFetcher):
    """GitHub Trending 抓取"""
    
    name = "GitHub Trending"
    BASE_URL = "https://github.com/trending"
    
    def fetch(self, limit: int = 20) -> List[ContentItem]:
        """获取 GitHub 今日趋势项目"""
        items = []
        
        try:
            resp = requests.get(
                self.BASE_URL,
                params={"since": "daily"},
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
                timeout=15
            )
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            for article in soup.select('article.Box-row')[:limit]:
                # 获取仓库名
                repo_link = article.select_one('h2 a')
                if not repo_link:
                    continue
                    
                repo_path = repo_link.get('href', '').strip('/')
                if not repo_path:
                    continue
                
                # 获取描述
                desc_elem = article.select_one('p')
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                
                # 获取语言
                lang_elem = article.select_one('[itemprop="programmingLanguage"]')
                language = lang_elem.get_text(strip=True) if lang_elem else ""
                
                # 获取今日 stars
                stars_today = 0
                stars_elem = article.select_one('.float-sm-right')
                if stars_elem:
                    stars_text = stars_elem.get_text(strip=True)
                    # 解析 "1,234 stars today" 格式
                    import re
                    match = re.search(r'([\d,]+)', stars_text)
                    if match:
                        stars_today = int(match.group(1).replace(',', ''))
                
                # 获取总 stars
                total_stars = 0
                star_link = article.select_one('a[href*="/stargazers"]')
                if star_link:
                    stars_text = star_link.get_text(strip=True)
                    import re
                    match = re.search(r'([\d,]+)', stars_text)
                    if match:
                        total_stars = int(match.group(1).replace(',', ''))
                
                items.append(ContentItem(
                    id=f"gh_{repo_path.replace('/', '_')}",
                    title=repo_path,
                    url=f"https://github.com/{repo_path}",
                    source="GitHub Trending",
                    category=language or "Code",
                    description=description,
                    author=repo_path.split('/')[0] if '/' in repo_path else "",
                    score=stars_today,
                    extra={
                        "total_stars": total_stars,
                        "language": language,
                        "stars_today": stars_today,
                    }
                ))
            
            return items
            
        except Exception as e:
            print(f"[GitHub Trending] Error: {e}")
            return []
