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
        发送每日精选简报 (Newsletter 风格)
        """
        if not items:
            return False
            
        elements = []
        
        # 顶部日期
        today = datetime.now().strftime("%Y-%m-%d")
        elements.append({
            "tag": "markdown",
            "content": f"📅 **{today}** | 精选 {len(items)} 条高价值内容"
        })
        
        elements.append({"tag": "hr"})
        
        # 逐条展示
        for item in items:
            # 优先使用 AI 生成的中文标题
            title_text = item.ai_title if item.ai_title else item.title
            
            # 正文内容
            summary_text = item.ai_summary if item.ai_summary else item.description[:100]
            
            # 构建 Markdown 内容
            # 格式:
            # **标题**
            # 正文内容... [来源](url)
            
            content_md = f"**{title_text}**\n\n{summary_text} [来源]({item.url})"
            
            elements.append({
                "tag": "markdown",
                "content": content_md
            })
            
            # 增加一点间距，使用透明图片或空行 (飞书 markdown 支持有限，用 hr 做分割比较稳)
            elements.append({"tag": "hr"})
            
        # 移除最后一个分割线（美观）
        if elements and elements[-1]["tag"] == "hr":
            elements.pop()
            
        # 底部说明
        elements.append({
            "tag": "note",
            "elements": [{
                "tag": "plain_text",
                "content": "🤖 内容由 AI 自动生成，仅供参考"
            }]
        })
        
        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📰 每日 AI & 跨境简报"
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
