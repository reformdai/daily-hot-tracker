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

# Jina Reader（可选）：正文补抓失败时用浏览器渲染兜底。无 key 也可用但限流更严。
JINA_API_KEY = os.getenv("JINA_API_KEY", "")
JINA_READER_FALLBACK = os.getenv("JINA_READER_FALLBACK", "false").lower() == "true"

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
    "chatbot", "agent", "agentic", "RAG", "embedding", "fine-tuning", "prompt",
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

    # 补充：常见缩写与厂商
    "GenAI", "AGI", "multimodal", "Grok", "xAI", "Kimi", "Hugging Face", "NVIDIA",
    "MCP", "vibe coding", "Codex", "open-weight", "open-source model",

    # 中文
    "人工智能", "大模型", "智能体", "生成式", "机器学习", "深度学习", "多模态",
    "具身智能", "机器人", "开源模型", "推理模型", "算力", "芯片", "融资",
]

# 关键词匹配规则：英文/数字关键词按词边界匹配（允许复数），避免 "AI" 命中 "said"、"paid"；
# 中文关键词按子串匹配。以下来源本身就是 AI 垂直源，跳过关键词预筛选。
KEYWORD_EXEMPT_SOURCES = [
    "AIHOT",
    "ArXiv",
    "Hugging Face Papers",
    "Hugging Face Trending",
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

# 个别来源的条目上限（RSS 源多，按源轮询，20 条只够每个源 1 条）
SOURCE_ITEM_LIMITS = {
    "rss_feeds": 60,
    "hn_search": 30,
}

# 并发抓取的来源数量
FETCH_WORKERS = int(os.getenv("FETCH_WORKERS", "6"))

# AI 筛选后保留的条目数
TOP_N_ITEMS = 10

# AI 评分阈值 (1-10)
MIN_SCORE_THRESHOLD = 6

# ==================== 去重与排序增强 ====================
# 标题相似度去重阈值（0-1）
TITLE_DEDUP_SIMILARITY = float(os.getenv("TITLE_DEDUP_SIMILARITY", "0.84"))

# 时效窗口：发布时间（多源合并时取最新一次出现）超过该小时数的条目丢弃；无时间的条目保留
MAX_ITEM_AGE_HOURS = float(os.getenv("MAX_ITEM_AGE_HOURS", "72"))
# 个别来源族的时效窗口：ArXiv/HF 论文的时间是投稿时间，周末投稿到周一才公布，放宽到 5 天
MAX_ITEM_AGE_HOURS_BY_SOURCE = {
    "ArXiv": 120,
    "Hugging Face Papers": 120,
}

# 送入 AI 评分的候选条数，以及单一来源族（如 Reddit、ArXiv）最多占用的名额
AI_CANDIDATE_LIMIT = int(os.getenv("AI_CANDIDATE_LIMIT", "40"))
MAX_CANDIDATES_PER_FAMILY = int(os.getenv("MAX_CANDIDATES_PER_FAMILY", "10"))

# ==================== 信源分级 ====================
# 参考 AIHOT：T1 官方一手（实验室/公司官方博客）、T2 媒体与精选聚合、T3 社区与榜单。
# RSS/网页/JSON 源在各自配置里写 "tier"；内置抓取器按来源名在这里查，未列出的默认 T3。
SOURCE_TIERS = {
    "AIHOT": "T2",
    "ArXiv": "T2",
    "Hugging Face Papers": "T2",
    "Hugging Face Trending": "T3",
    "Hacker News": "T3",
    "GitHub Trending": "T3",
    "Product Hunt": "T3",
    "Reddit": "T3",
}

# ==================== 正文补抓 ====================
# 对送入 AI 的候选，描述不足该长度时抓取原文页面补充正文摘录（GitHub/HF 读 README）
ENRICH_MIN_DESCRIPTION = int(os.getenv("ENRICH_MIN_DESCRIPTION", "280"))
ENRICH_MAX_CHARS = int(os.getenv("ENRICH_MAX_CHARS", "1500"))
ENRICH_WORKERS = int(os.getenv("ENRICH_WORKERS", "8"))

# 轻量防霸榜配置（不依赖持久化）
MAX_GITHUB_ITEMS_PER_DAY = int(os.getenv("MAX_GITHUB_ITEMS_PER_DAY", "2"))
MIN_AI_SCORE_FOR_GITHUB = float(os.getenv("MIN_AI_SCORE_FOR_GITHUB", "8.0"))

# ==================== 数据源配置 ====================
# 启用的数据源
ENABLED_SOURCES = [
    "hackernews",
    "hn_search",
    "huggingface",
    "producthunt",
    "github_trending",
    "reddit",
    "rss_feeds",
    "web_list",
    "json_list",
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
# 2026-09-29：404 源保留配置但停用；Anthropic 改用下方 WEB_SOURCES。
# 单源按最新排序后轮询取样；Y Combinator、VentureBeat 更新较慢，会打印 stale 警告。
# 2026-10-02：参考 AIHOT industry/sources.json 补充 T1 官方博客与 T2 媒体/个人博客；
# 新增源未在本仓库环境实测，首次运行请看抓取日志，失效的改为 "enabled": False。
# category 会参与关键词预筛选：写 "AI" 的源全部条目都会通过；综合性博客写别的分类，让关键词把关。
RSS_FEEDS: List[Dict] = [
    # T1 官方一手
    {"name": "OpenAI Blog", "url": "https://openai.com/news/rss.xml", "category": "AI", "tier": "T1"},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml", "category": "AI", "tier": "T1"},
    {"name": "Google Research", "url": "https://research.google/blog/rss/", "category": "AI", "tier": "T1"},
    {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml", "category": "AI", "tier": "T1"},
    {"name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/feed/", "category": "Research", "tier": "T1"},
    {"name": "NVIDIA Blog", "url": "https://blogs.nvidia.com/feed/", "category": "Tech", "tier": "T1"},
    {"name": "AWS Machine Learning", "url": "https://aws.amazon.com/blogs/machine-learning/feed/", "category": "AI", "tier": "T1"},
    {"name": "GitHub Blog AI", "url": "https://github.blog/ai-and-ml/feed/", "category": "AI", "tier": "T1"},
    {"name": "Mistral AI", "url": "https://mistral.ai/rss.xml", "category": "AI", "tier": "T1"},
    {"name": "Berkeley AI Research", "url": "https://bair.berkeley.edu/blog/feed.xml", "category": "AI", "tier": "T1"},
    # T2 媒体与个人
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "category": "AI", "tier": "T2"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "category": "AI", "tier": "T2"},
    {"name": "Ars Technica AI", "url": "https://arstechnica.com/ai/feed/", "category": "AI", "tier": "T2"},
    {"name": "MIT Tech Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "category": "AI", "tier": "T2"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "category": "AI", "tier": "T2"},
    {"name": "The Decoder", "url": "https://the-decoder.com/feed/", "category": "AI", "tier": "T2"},
    {"name": "Simon Willison", "url": "https://simonwillison.net/atom/everything/", "category": "AI", "tier": "T2"},
    {"name": "Import AI", "url": "https://importai.substack.com/feed", "category": "AI", "tier": "T2"},
    {"name": "Latent Space", "url": "https://www.latent.space/feed", "category": "AI", "tier": "T2"},
    {"name": "Y Combinator", "url": "https://www.ycombinator.com/blog/rss/", "category": "Startup", "tier": "T2"},
    {"name": "a16z", "url": "https://a16z.com/feed/", "category": "VC", "enabled": False},
    {"name": "First Round Review", "url": "https://review.firstround.com/feed.xml", "category": "Startup", "enabled": False},
]

# 无官方 RSS 的站点：选择器来自公开页面，页面改版时需重新试抓。
WEB_SOURCES: List[Dict] = [
    {
        "name": "Anthropic", "url": "https://www.anthropic.com/news", "category": "AI", "tier": "T1",
        "item_selector": 'a[href^="/news/"]:has(time)',
        "title_selector": 'span[class*="__title"]',
        "date_selector": "time",
        "allow_url_prefixes": ["https://www.anthropic.com/news/"],
    },
]

# 公开 JSON GET 接口，按 docs/data-sources.md 配置字段路径后启用。
# 默认不添加软件 release 流，避免改变日报主题。
JSON_SOURCES: List[Dict] = []

# Hacker News 搜索（Algolia 公开 API）：按关键词找最近 24 小时内的高分 AI 讨论，
# 补足 topstories 只看全站前几十条、AI 内容占比低的问题。
HN_SEARCH_QUERIES = ["AI", "LLM", "GPT", "OpenAI", "Anthropic", "Claude", "Gemini", "DeepSeek", "agent", "model"]
HN_SEARCH_MIN_POINTS = int(os.getenv("HN_SEARCH_MIN_POINTS", "30"))
HN_SEARCH_HOURS = 24

# Hugging Face：每日论文（社区投票 + 摘要）与趋势模型
HF_DAILY_PAPERS = True
HF_TRENDING_MODELS = True
HF_MODEL_MAX_AGE_DAYS = 14  # 只收最近两周创建的趋势模型，避免常青模型霸榜

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

# 运行日志（信源健康报告、候选清单），GitHub Actions 会上传该目录
LOG_DIR = os.getenv("LOG_DIR", "logs")
