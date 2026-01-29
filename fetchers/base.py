"""
Fetcher 基类和数据模型
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class ContentItem:
    """统一的内容数据模型"""
    id: str                          # 唯一标识
    title: str                       # 标题
    url: str                         # 链接
    source: str                      # 来源平台
    category: str = ""               # 分类
    description: str = ""            # 描述/摘要
    author: str = ""                 # 作者
    score: int = 0                   # 原平台热度分数
    comments: int = 0                # 评论数
    published_at: Optional[datetime] = None  # 发布时间
    extra: dict = field(default_factory=dict)  # 额外信息
    
    # AI 评分结果 (后续填充)
    ai_score: float = 0.0            # AI 综合评分
    ai_title: str = ""               # AI 生成的中文标题
    ai_summary: str = ""             # AI 生成的深度简讯 (120-140字)
    ai_category: str = ""            # AI 分类
    ai_reason: str = ""              # (已弃用) 评分理由
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "score": self.score,
            "comments": self.comments,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "ai_score": self.ai_score,
            "ai_title": self.ai_title,
            "ai_summary": self.ai_summary,
        }
    
    def __str__(self) -> str:
        return f"[{self.source}] {self.title} (score: {self.score})"


class BaseFetcher(ABC):
    """数据抓取器基类"""
    
    name: str = "base"
    
    @abstractmethod
    def fetch(self, limit: int = 20) -> List[ContentItem]:
        """
        获取内容列表
        
        Args:
            limit: 最大获取数量
            
        Returns:
            ContentItem 列表
        """
        pass
    
    def filter_by_keywords(self, items: List[ContentItem], keywords: List[str]) -> List[ContentItem]:
        """
        根据关键词过滤
        
        Args:
            items: 内容列表
            keywords: 关键词列表
            
        Returns:
            过滤后的列表
        """
        if not keywords:
            return items
            
        filtered = []
        keywords_lower = [k.lower() for k in keywords]
        
        for item in items:
            text = f"{item.title} {item.description}".lower()
            if any(kw in text for kw in keywords_lower):
                filtered.append(item)
                
        return filtered
