"""
飞书推送模块
"""
import json
import requests
from datetime import datetime
from typing import List
from fetchers.base import ContentItem
import config


class FeishuBot:
    """飞书机器人推送"""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or config.FEISHU_WEBHOOK_URL
        
    def send_text(self, text: str) -> bool:
        """发送纯文本消息"""
        if not self.webhook_url:
            print("[Feishu] Webhook URL not configured")
            return False
            
        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }
        
        return self._send(payload)
    
    def send_card(self, title: str, items: List[ContentItem]) -> bool:
        """
        发送卡片消息
        
        Args:
            title: 卡片标题
            items: 内容列表
        """
        if not self.webhook_url:
            print("[Feishu] Webhook URL not configured")
            return False
        
        # 构建卡片内容
        elements = []
        
        # 添加标题描述
        today = datetime.now().strftime("%Y-%m-%d")
        elements.append({
            "tag": "markdown",
            "content": f"**{today}** | 共 {len(items)} 条精选内容"
        })
        
        elements.append({"tag": "hr"})
        
        # 添加每条内容
        for idx, item in enumerate(items, 1):
            # 评分显示
            score_emoji = self._get_score_emoji(item.ai_score)
            
            # 内容块
            content = f"**{idx}. [{item.title}]({item.url})**\n"
            content += f"{score_emoji} AI评分: {item.ai_score:.1f}/10 | 来源: {item.source}\n"
            
            if item.ai_reason:
                content += f"💡 {item.ai_reason}\n"
            
            if item.description:
                desc = item.description[:100] + "..." if len(item.description) > 100 else item.description
                content += f"📝 {desc}\n"
            
            elements.append({
                "tag": "markdown",
                "content": content
            })
            
            # 添加分隔线（除了最后一条）
            if idx < len(items):
                elements.append({"tag": "hr"})
        
        # 构建卡片
        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🔥 {title}"
                },
                "template": "blue"
            },
            "elements": elements
        }
        
        payload = {
            "msg_type": "interactive",
            "card": card
        }
        
        return self._send(payload)
    
    def send_daily_digest(self, items: List[ContentItem]) -> bool:
        """
        发送每日精选摘要（按分类展示）
        
        Args:
            items: 筛选后的内容列表
        """
        # 定义分类映射
        category_map = {
            "GitHub": {"emoji": "⚫", "name": "开源项目", "items": []},
            "Hacker": {"emoji": "🟠", "name": "技术讨论", "items": []},
            "Reddit": {"emoji": "🔴", "name": "社区热议", "items": []},
            "Product": {"emoji": "🟣", "name": "新产品", "items": []},
            "TechCrunch": {"emoji": "🟢", "name": "科技新闻", "items": []},
            "Other": {"emoji": "🔵", "name": "其他资讯", "items": []},
        }
        
        # 按来源分类
        for item in items:
            source_lower = item.source.lower()
            categorized = False
            for key in category_map:
                if key.lower() in source_lower:
                    category_map[key]["items"].append(item)
                    categorized = True
                    break
            if not categorized:
                category_map["Other"]["items"].append(item)
        
        # 构建卡片
        elements = []
        
        today = datetime.now().strftime("%Y年%m月%d日")
        elements.append({
            "tag": "markdown",
            "content": f"📅 **{today}** | AI 精选 {len(items)} 条优质内容"
        })
        
        elements.append({"tag": "hr"})
        
        # 按分类展示
        for cat_key, cat_info in category_map.items():
            if not cat_info["items"]:
                continue
                
            # 分类标题
            elements.append({
                "tag": "markdown",
                "content": f"{cat_info['emoji']} **{cat_info['name']}**"
            })
            
            # 该分类下的内容
            for item in cat_info["items"]:
                score_emoji = self._get_score_emoji(item.ai_score)
                
                # 标题（限制长度）
                title_display = item.title[:40] + "..." if len(item.title) > 40 else item.title
                
                # 构建内容：先是标题和评分
                line = f"{score_emoji} **[{title_display}]({item.url})** `{item.ai_score:.1f}分`\n"
                
                # 添加简介（这是什么）
                if item.ai_summary:
                    line += f"   📌 {item.ai_summary}\n"
                
                # 添加亮点（为什么值得关注）
                if item.ai_reason:
                    line += f"   💡 {item.ai_reason}\n"
                
                elements.append({
                    "tag": "markdown",
                    "content": line
                })
            
            elements.append({"tag": "hr"})
        
        # 底部说明
        elements.append({
            "tag": "markdown",
            "content": "💡 *评分基于 AI 自动分析 | 关注领域：AI/LLM、跨境电商*"
        })
        
        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "🌅 每日热榜精选"
                },
                "template": "orange"
            },
            "elements": elements
        }
        
        payload = {
            "msg_type": "interactive",
            "card": card
        }
        
        return self._send(payload)
    
    def _get_score_emoji(self, score: float) -> str:
        """根据分数返回 emoji"""
        if score >= 9:
            return "🔥"
        elif score >= 8:
            return "⭐"
        elif score >= 7:
            return "✨"
        elif score >= 6:
            return "👍"
        else:
            return "📌"
    
    def _get_source_emoji(self, source: str) -> str:
        """根据来源返回 emoji"""
        source_lower = source.lower()
        if "hacker" in source_lower:
            return "🟠"
        elif "product" in source_lower:
            return "🟣"
        elif "github" in source_lower:
            return "⚫"
        elif "reddit" in source_lower:
            return "🔴"
        elif "techcrunch" in source_lower:
            return "🟢"
        else:
            return "🔵"
    
    def _send(self, payload: dict) -> bool:
        """发送请求"""
        try:
            resp = requests.post(
                self.webhook_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            resp.raise_for_status()
            
            result = resp.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                print("[Feishu] Message sent successfully")
                return True
            else:
                print(f"[Feishu] Send failed: {result}")
                return False
                
        except Exception as e:
            print(f"[Feishu] Error sending message: {e}")
            return False
