"""
配置文件
"""
import os
from typing import List, Dict

# ==================== API Keys ====================
# 从环境变量读取，也可以在 .env 文件中配置

# AI API 配置 (选择一个即可)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# 飞书 Webhook
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")

# Product Hunt API (可选，无 token 也能用公开数据)
PRODUCTHUNT_TOKEN = os.getenv("PRODUCTHUNT_TOKEN", "")

# ==================== AI 模型配置 ====================
# 可选: deepseek, openai, anthropic
AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")

AI_MODELS = {
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
    },
    "anthropic": {
        "model": "claude-3-haiku-20240307",
        "base_url": "https://api.anthropic.com",
    },
}

# ==================== 筛选配置 ====================
# 关注的关键词 (用于预筛选)
KEYWORDS = [
    # AI/LLM 相关
    "AI", "LLM", "GPT", "Claude", "Gemini", "OpenAI", "Anthropic", "DeepSeek",
    "machine learning", "deep learning", "neural network", "transformer",
    "chatbot", "agent", "RAG", "embedding", "fine-tuning", "prompt",
    "Stable Diffusion", "Midjourney", "DALL-E", "Sora", "generative",
    
    # 跨境/出海相关
    "跨境", "出海", "cross-border", "e-commerce", "Shopify", "Amazon",
    "TikTok Shop", "dropshipping", "DTC", "独立站",
    
    # 创业/产品
    "startup", "founder", "YC", "funding", "Series A", "seed round",
    "SaaS", "B2B", "indie", "maker", "launch", "Product Hunt",
]

# 每个来源获取的最大条目数
MAX_ITEMS_PER_SOURCE = 20

# AI 筛选后保留的条目数
TOP_N_ITEMS = 10

# AI 评分阈值 (1-10)
MIN_SCORE_THRESHOLD = 6

# ==================== 数据源配置 ====================
# 启用的数据源
ENABLED_SOURCES = [
    "hackernews",
    "producthunt", 
    "github_trending",
    "techcrunch",
    "reddit",
    "rss_feeds",
]

# Reddit 关注的 subreddit
REDDIT_SUBREDDITS = [
    "artificial",
    "MachineLearning",
    "LocalLLaMA",
    "startups",
    "SaaS",
    "Entrepreneur",
]

# RSS 订阅源
RSS_FEEDS: List[Dict] = [
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "category": "AI"},
    {"name": "a16z", "url": "https://a16z.com/feed/", "category": "VC"},
    {"name": "Y Combinator", "url": "https://www.ycombinator.com/blog/rss/", "category": "Startup"},
    {"name": "First Round Review", "url": "https://review.firstround.com/feed.xml", "category": "Startup"},
    {"name": "OpenAI Blog", "url": "https://openai.com/blog/rss/", "category": "AI"},
    {"name": "Anthropic", "url": "https://www.anthropic.com/feed.xml", "category": "AI"},
    {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml", "category": "AI"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "category": "AI"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "category": "AI"},
    {"name": "MIT Tech Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "category": "AI"},
]

# ==================== 推送配置 ====================
# 推送时间 (用于 GitHub Actions cron)
PUSH_HOUR_UTC = 0  # UTC 0点 = 北京时间 8点
