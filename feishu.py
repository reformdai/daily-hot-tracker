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
    
    SECTION_ICONS = {
        "模型发布": "🧠",
        "产品发布": "🚀",
        "行业动态": "📊",
        "论文研究": "📝",
        "技巧与观点": "💡",
    }

    SECTION_ORDER = ["模型发布", "产品发布", "行业动态", "论文研究", "技巧与观点"]

    def send_daily_digest(self, items: List[ContentItem]) -> bool:
        if not items:
            return False

        elements = []

        today = datetime.now().strftime("%Y-%m-%d")
        elements.append({
            "tag": "markdown",
            "content": f"📅 **{today}** | 精选 {len(items)} 条高价值内容"
        })

        sections: dict = {}
        for item in items:
            cat = item.ai_category or "行业动态"
            sections.setdefault(cat, []).append(item)

        idx = 0
        for cat in self.SECTION_ORDER:
            cat_items = sections.pop(cat, [])
            if not cat_items:
                continue
            icon = self.SECTION_ICONS.get(cat, "📌")

            elements.append({"tag": "hr"})
            elements.append({
                "tag": "markdown",
                "content": f"**{icon} {cat}**"
            })

            for item in cat_items:
                idx += 1
                title_text = item.ai_title if item.ai_title else item.title
                summary_text = item.ai_summary if item.ai_summary else item.description[:100]
                source_text = self._format_source(item)
                content_md = (
                    f"**{idx}. [{title_text}]({item.url})**\n"
                    f"{summary_text}\n"
                    f"🔗 来源: {source_text} | [查看原文]({item.url})"
                )
                elements.append({
                    "tag": "markdown",
                    "content": content_md
                })

        for cat, cat_items in sections.items():
            if not cat_items:
                continue
            icon = self.SECTION_ICONS.get(cat, "📌")

            elements.append({"tag": "hr"})
            elements.append({
                "tag": "markdown",
                "content": f"**{icon} {cat}**"
            })

            for item in cat_items:
                idx += 1
                title_text = item.ai_title if item.ai_title else item.title
                summary_text = item.ai_summary if item.ai_summary else item.description[:100]
                source_text = self._format_source(item)
                content_md = (
                    f"**{idx}. [{title_text}]({item.url})**\n"
                    f"{summary_text}\n"
                    f"🔗 来源: {source_text} | [查看原文]({item.url})"
                )
                elements.append({
                    "tag": "markdown",
                    "content": content_md
                })

        elements.append({"tag": "hr"})
        elements.append({
            "tag": "note",
            "elements": [{
                "tag": "plain_text",
                "content": "🤖 内容由 AI 自动筛选生成，仅供参考"
            }]
        })

        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📰 AI 每日精选"
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
    
    def _format_source(self, item: ContentItem) -> str:
        """格式化来源显示：AIHOT 显示原始信源，其他显示平台名"""
        if item.source == "AIHOT" and item.author:
            # AIHOT 的 author 字段是原始信源（如 "OpenAI：官网动态"、"X：宝玉"）
            return f"AIHOT · {item.author}"
        return item.source or "未知"

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
