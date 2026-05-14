# 🤖 AI Daily Hot Tracker (每日热点追踪器)

一个智能化的 AI 领域每日精选生成器。它能自动从 Hacker News、GitHub、Reddit、Product Hunt、ArXiv、AIHOT 等平台抓取 AI 领域的热门内容，利用 DeepSeek/OpenAI 大模型进行深度阅读、评分和分类，最终生成一份高质量的**中文深度简报**推送到飞书群，并输出 RSS Feed 供订阅。

> **特点**：全自动运行、AI 深度摘要、拒绝标题党、免费部署 (GitHub Actions)。

---

## ✨ 核心功能

- **🔥 多源热点聚合（7 大数据源）**
  - **Hacker News**: 科技圈最硬核的讨论
  - **GitHub Trending**: 今日增长最快的开源项目
  - **Product Hunt**: 每日最佳新产品
  - **Reddit**: 热门社区讨论 (r/LocalLLaMA, r/MachineLearning 等)
  - **ArXiv**: AI/ML 领域最新论文 (cs.AI, cs.CL, cs.LG, cs.CV)
  - **AIHOT**: 接入 AIHOT 平台精选热点（配置 API Key 后启用）
  - **Tech Blog**: OpenAI, Anthropic, a16z, TechCrunch 等 RSS 订阅

- **🧠 AI 智能处理**
  - **智能评分**: 过滤掉低价值内容，只保留 Top 10
  - **深度简讯**: AI 变身主编，撰写 120 字中文深度摘要，讲清"是什么"和"为什么重要"
  - **5 大版块分类**: 🧠 模型发布 / 🚀 产品发布 / 📊 行业动态 / 📝 论文研究 / 💡 技巧与观点

- **📱 多渠道输出**
  - **飞书卡片消息**: 按版块分组展示，一目了然
  - **RSS Feed**: 自动生成 feed.xml，可部署到 GitHub Pages 供订阅
  - 每天定时推送 (默认北京时间 09:30)

## 📸 推送效果预览

**(飞书卡片消息)**

> **📅 2026-02-02 | 精选 10 条高价值内容**
> -----------------------------------
> **【开源项目】DeepSeek-V2-Chat 发布**
> 
> DeepSeek 推出的第二代 MoE 架构大模型，参数量 236B，激活参数 21B。相比前代，它在代码生成和数学推理能力上有显著提升，且推理成本降低了 40%。该模型已完全开源，支持 128K 上下文，是目前最强的开源 MoE 模型之一。 [来源]
> 
> -----------------------------------
> **【行业新闻】Sora 正式向公众开放**
> ...

---

## 🚀 快速开始

### 方式一：使用 GitHub Actions (推荐，免费 & 自动)

无需服务器，Fork 本项目即可运行。

1. **Fork 本仓库** 到你的 GitHub 账号。
2. **配置 Secrets**:
   进入 `Settings` -> `Secrets and variables` -> `Actions`，添加以下 Repository secrets:
   - `DEEPSEEK_API_KEY`: 你的 DeepSeek API Key (或 OpenAI/Anthropic Key)
   - `FEISHU_WEBHOOK_URL`: 你的飞书机器人 Webhook 地址
   - `PRODUCTHUNT_TOKEN`: (可选) Product Hunt Developer Token
3. **启用 Workflow**:
   进入 `Actions` 页面，点击 `I understand my workflows, go ahead and enable them`。
4. **手动触发测试**:
   在 `Actions` -> `Daily Hot Tracker` -> `Run workflow` 手动运行一次。
5. **坐等推送**:
   默认每天 **北京时间 09:30** 自动推送。

### 方式二：本地运行

1. **克隆项目**
   ```bash
   git clone https://github.com/your-username/daily-hot-tracker.git
   cd daily-hot-tracker
   ```

2. **安装依赖**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   复制 `.env.example` 为 `.env`，并填入你的 Key：
   ```bash
   cp .env.example .env
   vim .env
   ```

4. **运行**
   ```bash
   python main.py
   
   # 常用选项
   python main.py --limit 5  # 只处理前5条
   python main.py --no-ai    # 不使用AI (仅抓取)
   python main.py --dry-run  # 不推送到飞书
   ```

---

## ⚙️ 配置说明 (`config.py`)

你可以修改 `config.py` 来自定义行为：

- `KEYWORDS`: 设置你关心的关键词 (当前默认: AI, LLM, 跨境, RAG 等)
- `RSS_FEEDS`: 添加你喜欢的博客 RSS 地址
- `AI_PROVIDER`: 切换 AI 模型 (deepseek / openai / anthropic)
- `TOP_N_ITEMS`: 每天推送的条数 (默认 10)

## 🛠️ 技术栈

- **Python 3.11+**
- **LLM API**: DeepSeek / OpenAI / Anthropic
- **Feedparser**: RSS 解析
- **GitHub Actions**: 定时任务调度

## 📝 License

MIT License
