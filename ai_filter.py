"""
AI 筛选评分模块
支持 DeepSeek / OpenAI / Anthropic
"""
import json
import requests
from typing import List, Tuple
from fetchers.base import ContentItem
import config


class AIFilter:
    """AI 内容筛选评分"""
    
    SCORE_PROMPT = """你是一位资深的科技媒体主编，正在为专业读者编写一份"AI与跨境电商"的每日简报。
请评估以下内容，打分、分类并撰写深度简讯。

待评估内容：
---
标题: {title}
来源: {source}
描述: {description}
---

任务要求：
1. score (1-10分): 8-10分(必读/重大新闻), 6-7分(值得关注), 1-5分(普通/无关)。
2. category: 选择一个最匹配的分类 [开源项目, 技术解读, 产品发布, 行业动态, 创业出海, 其他]。
3. title_cn: 将标题翻译为信达雅的中文标题。
4. summary: 用中文撰写一段 120-140 字的深度简讯。包含硬核信息。

请回复纯 JSON：
{{"score": 8.5, "category": "技术解读", "title_cn": "中文标题", "summary": "深度简讯内容..."}}
"""

    BATCH_PROMPT = """你是一位资深的科技媒体主编，正在为专业读者编写一份"AI与跨境电商"的每日简报。
请评估以下多条内容，打分、分类并撰写深度简讯。

评分标准 (1-10分)：
- 8-10分：行业重大新闻、颠覆性技术、热门开源项目 (必须入选)
- 6-7分：有价值的技术更新、深度观点、实用工具 (值得关注)
- 1-5分：普通资讯、营销文、无关内容 (不推荐)

任务要求：
1. score: 给出评分。
2. category: 选择一个最匹配的分类 [开源项目, 技术解读, 产品发布, 行业动态, 创业出海, 其他]。
3. title_cn: 将标题翻译为信达雅的中文标题。
4. summary: 用中文撰写一段 120-140 字的深度简讯。
   - 风格：专业、客观、高信息密度。
   - 结构：一句话讲清是什么 -> 核心功能/亮点 -> 行业意义/价值。
   - 语气：不要用"这款工具"、"该项目"开头，直接说主语。用事实说话。
   - 必须包含：核心参数、技术架构、主要功能、融资数据等硬核信息（如果有）。

待评估内容列表：
---
{items_text}
---

请回复纯 JSON 数组：
[
    {{"index": 0, "score": 9.5, "category": "开源项目", "title_cn": "中文标题", "summary": "简讯内容..."}},
    ...
]
"""

    def __init__(self, provider: str = None):
        """
        Args:
            provider: AI 提供商 (deepseek/openai/anthropic)
        """
        self.provider = provider or config.AI_PROVIDER
        self.model_config = config.AI_MODELS.get(self.provider, {})
        
    def _get_api_key(self) -> str:
        """获取对应的 API Key"""
        if self.provider == "deepseek":
            return config.DEEPSEEK_API_KEY
        elif self.provider == "openai":
            return config.OPENAI_API_KEY
        elif self.provider == "anthropic":
            return config.ANTHROPIC_API_KEY
        return ""
    
    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError(f"Missing API key for provider: {self.provider}")
        
        if self.provider == "anthropic":
            return self._call_anthropic(prompt, api_key)
        else:
            return self._call_openai_compatible(prompt, api_key)
    
    def _call_openai_compatible(self, prompt: str, api_key: str) -> str:
        """调用 OpenAI 兼容 API (OpenAI / DeepSeek)"""
        resp = requests.post(
            f"{self.model_config['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    
    def _call_anthropic(self, prompt: str, api_key: str) -> str:
        """调用 Anthropic API"""
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": self.model_config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
            },
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
    
    def score_single(self, item: ContentItem) -> Tuple[float, str, str, str]:
        """
        对单个内容评分
        
        Returns:
            (score, title_cn, summary, category)
        """
        prompt = self.SCORE_PROMPT.format(
            title=item.title,
            source=item.source,
            description=item.description[:500] if item.description else "(无描述)"
        )
        
        try:
            response = self._call_llm(prompt)
            # 解析 JSON
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            result = json.loads(response.strip())
            return (
                float(result.get("score", 0)), 
                result.get("title_cn", item.title),
                result.get("summary", ""),
                result.get("category", "")
            )
        except Exception as e:
            print(f"[AIFilter] Error scoring item: {e}")
            return 0.0, item.title, f"评分失败: {e}", ""
    
    def score_batch(self, items: List[ContentItem], batch_size: int = 5) -> List[ContentItem]:
        """
        批量评分 (更高效)
        """
        scored_items = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            # 构建批量文本
            items_text = ""
            for idx, item in enumerate(batch):
                items_text += f"""
[{idx}] 标题: {item.title}
    来源: {item.source}
    描述: {item.description[:200] if item.description else "(无描述)"}
"""
            
            prompt = self.BATCH_PROMPT.format(items_text=items_text)
            
            try:
                response = self._call_llm(prompt)
                # 清理响应中可能的 markdown 代码块
                response = response.strip()
                if response.startswith("```"):
                    response = response.split("```")[1]
                    if response.startswith("json"):
                        response = response[4:]
                
                results = json.loads(response.strip())
                
                for result in results:
                    idx = result.get("index", 0)
                    if idx < len(batch):
                        batch[idx].ai_score = float(result.get("score", 0))
                        batch[idx].ai_title = result.get("title_cn", batch[idx].title)
                        batch[idx].ai_summary = result.get("summary", "")
                        batch[idx].ai_category = result.get("category", "")
                
            except Exception as e:
                print(f"[AIFilter] Batch scoring error: {e}")
                # 失败时逐个评分
                for item in batch:
                    score, title_cn, summary, category = self.score_single(item)
                    item.ai_score = score
                    item.ai_title = title_cn
                    item.ai_summary = summary
                    item.ai_category = category
            
            scored_items.extend(batch)
        
        return scored_items
    
    def filter_top(self, items: List[ContentItem], top_n: int = 10, min_score: float = 6.0) -> List[ContentItem]:
        """
        评分并筛选 Top N
        """
        # 批量评分
        scored_items = self.score_batch(items)
        
        # 过滤低分
        filtered = [item for item in scored_items if item.ai_score >= min_score]
        
        # 按 AI 分数排序
        filtered.sort(key=lambda x: x.ai_score, reverse=True)
        
        return filtered[:top_n]
