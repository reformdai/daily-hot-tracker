# Daily Hot Tracker

每日热榜聚合器 - 自动抓取多平台热门内容，AI 智能筛选，推送到飞书。

## 功能特性

- **多平台数据源**
  - Hacker News - 技术社区热榜
  - Product Hunt - 每日新产品
  - GitHub Trending - 开源项目趋势
  - Reddit - 多个 subreddit 热帖
  - RSS 订阅 - TechCrunch、a16z、YC 等

- **AI 智能筛选**
  - 支持 DeepSeek / OpenAI / Anthropic
  - 基于相关性、创新性、实用价值评分
  - 自动过滤低质量内容

- **飞书推送**
  - 精美卡片消息
  - 每日定时推送

## 快速开始

### 1. 安装依赖

```bash
cd daily-hot-tracker
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的配置：

```bash
cp .env.example .env
```

必填项：
- `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY` - AI 评分用
- `FEISHU_WEBHOOK_URL` - 飞书推送用

### 3. 运行

```bash
# 完整运行
python main.py

# 跳过 AI 评分（仅按热度排序）
python main.py --no-ai

# 仅测试，不推送
python main.py --dry-run

# 指定保留条数
python main.py --limit 15
```

## 配置飞书机器人

1. 打开飞书，进入目标群聊
2. 点击右上角 `...` → `群设置` → `群机器人` → `添加机器人`
3. 选择 `自定义机器人`
4. 复制 Webhook 地址，填入 `.env` 文件

## GitHub Actions 自动运行

1. Fork 本仓库
2. 在仓库 Settings → Secrets and variables → Actions 中添加：
   - `DEEPSEEK_API_KEY` (或其他 AI 提供商的 key)
   - `FEISHU_WEBHOOK_URL`
3. 工作流会在每天北京时间 8:00 自动运行

手动触发：Actions → Daily Hot Tracker → Run workflow

## 自定义配置

编辑 `config.py` 可以自定义：

- `KEYWORDS` - 关注的关键词
- `TOP_N_ITEMS` - 每日推送条数
- `RSS_FEEDS` - RSS 订阅源列表
- `REDDIT_SUBREDDITS` - Reddit 关注的板块
- `ENABLED_SOURCES` - 启用的数据源

## 项目结构

```
daily-hot-tracker/
├── fetchers/              # 数据抓取模块
│   ├── base.py           # 基类和数据模型
│   ├── hackernews.py     # Hacker News
│   ├── producthunt.py    # Product Hunt
│   ├── github_trending.py # GitHub Trending
│   ├── reddit.py         # Reddit
│   └── rss_feeds.py      # RSS 订阅
├── .github/workflows/    # GitHub Actions
├── main.py               # 主程序入口
├── ai_filter.py          # AI 筛选评分
├── feishu.py             # 飞书推送
├── config.py             # 配置文件
├── requirements.txt      # 依赖
└── .env.example          # 环境变量示例
```

## Token 消耗估算

使用 DeepSeek V3：约 ¥2-3/月
使用 GPT-4o-mini：约 ¥3-5/月

## License

MIT
