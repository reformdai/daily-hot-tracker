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

# AIHOT 是公开 API，无需配置 API key

# ==================== AI 模型配置 ====================
# 可选: deepseek, openai, anthropic
AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")

AI_MODELS = {
    "deepseek": {
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
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
    # AI/LLM 模型
    "AI", "LLM", "GPT", "Claude", "Gemini", "OpenAI", "Anthropic", "DeepSeek",
    "machine learning", "deep learning", "neural network", "transformer",
    "Llama", "Mistral", "Qwen", "MoE", "RLHF", "reasoning",

    # AI 应用与工具
    "chatbot", "agent", "RAG", "embedding", "fine-tuning", "prompt",
    "Stable Diffusion", "Midjourney", "DALL-E", "Sora", "generative",
    "Cursor", "Copilot", "coding assistant", "AI editor",

    # AI 基础设施
    "GPU", "CUDA", "inference", "training", "VRAM", "quantization",
    "GGUF", "ONNX", "TensorRT", "MLOps", "vector database",

    # 创业/产品
    "startup", "founder", "YC", "funding", "Series A", "seed round",
    "SaaS", "B2B", "indie", "maker", "launch", "Product Hunt",

    # 论文/研究
    "arxiv", "paper", "benchmark", "SOTA", "attention", "diffusion",
]

# AI 内容分类体系（5 大版块）
AI_CATEGORIES = [
    "模型发布",
    "产品发布",
    "行业动态",
    "论文研究",
    "技巧与观点",
]

# 每个来源获取的最大条目数
MAX_ITEMS_PER_SOURCE = 20

# AI 筛选后保留的条目数
TOP_N_ITEMS = 10

# AI 评分阈值 (1-10)
MIN_SCORE_THRESHOLD = 6

# ==================== 去重与排序增强 ====================
# 标题相似度去重阈值（0-1）
TITLE_DEDUP_SIMILARITY = float(os.getenv("TITLE_DEDUP_SIMILARITY", "0.84"))

# 优先来源（会用于质量分加权）
PRIORITY_SOURCES = [
    "AIHOT",
    "Hacker News",
    "GitHub Trending",
    "Product Hunt",
    "ArXiv",
    "TechCrunch AI",
    "OpenAI Blog",
    "Anthropic",
]

# 轻量防霸榜配置（不依赖持久化）
MAX_GITHUB_ITEMS_PER_DAY = int(os.getenv("MAX_GITHUB_ITEMS_PER_DAY", "2"))
MIN_AI_SCORE_FOR_GITHUB = float(os.getenv("MIN_AI_SCORE_FOR_GITHUB", "8.0"))

# ==================== 数据源配置 ====================
# 启用的数据源
ENABLED_SOURCES = [
    "hackernews",
    "producthunt",
    "github_trending",
    "reddit",
    "rss_feeds",
    "aihot",
    "arxiv",
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

# ArXiv 关注的分类
ARXIV_CATEGORIES = [
    "cs.AI",   # Artificial Intelligence
    "cs.CL",   # Computation and Language (NLP)
    "cs.LG",   # Machine Learning
    "cs.CV",   # Computer Vision
]

# ==================== 推送配置 ====================
# 推送时间 (用于 GitHub Actions cron)
PUSH_HOUR_UTC = 0  # UTC 0点 = 北京时间 8点

# RSS 输出路径
RSS_OUTPUT_DIR = os.getenv("RSS_OUTPUT_DIR", "output")
