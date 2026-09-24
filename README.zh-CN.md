# 🤖 AI Daily Hot Tracker (每日热点追踪器)

简体中文 | [English](README.md)

一个 AI 领域每日精选生成器。它从 Hacker News、GitHub Trending、Reddit、Product Hunt、ArXiv、AIHOT 和科技博客 RSS 抓取 AI 相关热门内容，调用 DeepSeek / OpenAI / Anthropic 大模型进行评分、分类、翻译标题并撰写中文简讯，生成**中文精选简报**，可选推送到飞书群，本地运行时还可输出 RSS Feed。

> **特点**：GitHub Actions 定时运行，无需自建服务器；提示词要求模型仅依据各平台提供的标题和描述撰写摘要，但生成结果仍可能出错，使用前请对照原文核对。AI 生成的标题、简讯和版块名为中文；原始来源的标题和文本可能保留原语言（尤其在 `--no-ai` 或 AI 调用失败回退时）。LLM API 调用按所选提供商计费。

---

## ✨ 核心功能

- **🔥 多源热点聚合（7 大数据源）**
  - **Hacker News**: 科技圈最硬核的讨论（该来源没有描述，只有标题）
  - **GitHub Trending**: 今日增长最快的开源项目
  - **Product Hunt**: 每日最佳新产品（有 Token 时走官方 API；否则只抓取公开首页的「今日」榜单区域）
  - **Reddit**: 热门社区讨论 (r/LocalLLaMA, r/MachineLearning 等)
  - **ArXiv**: AI/ML 领域最新论文 (cs.AI, cs.CL, cs.LG, cs.CV)
  - **AIHOT**: AIHOT 平台精选热点（公开 API，无需 Key）
  - **Tech Blog**: OpenAI, Anthropic, Hugging Face, a16z, TechCrunch 等 RSS 订阅

- **🧠 AI 智能处理**
  - **关键词预筛选**: 按关键词过滤后，取综合热度前 25 条交给 AI
  - **智能评分**: 1-10 分，保留 6 分以上的 Top 10（GitHub Trending 每天最多 2 条且需 8 分以上）
  - **中文简讯**: 根据来源提供的标题和描述（批量评分时取描述前 200 字）撰写不超过 140 字的中文简讯。**不会抓取原文全文**；描述很少时（如 Hacker News）简讯也会相应简短
  - **5 大版块分类**: 🧠 模型发布 / 🚀 产品发布 / 📊 行业动态 / 📝 论文研究 / 💡 技巧与观点
  - **结果校验**: 模型返回的评分、编号、分类和字段类型会被校验，缺失或不合法的条目单独重试一次，仍失败则丢弃

- **📱 输出**
  - **飞书卡片消息（可选）**: 按版块分组展示。未配置 Webhook 时跳过推送；已配置但推送失败时进程以非零状态退出
  - **RSS Feed**: 本地运行默认生成 `output/feed.xml`。仓库自带的 workflow 使用 `--no-rss`，也不会部署 GitHub Pages，如需对外订阅请自行托管
  - 仓库自带的 workflow 每天 **UTC 22:30（北京时间 06:30）** 定时运行

## 📸 推送效果预览

以下为**示意**，仅展示卡片结构，内容并非真实输出：

> 📅 **2026-01-01** | 精选 10 条高价值内容
> -----------------------------------
> **🧠 模型发布**
>
> **1. [示例模型发布开源权重](https://example.com)**
> 一两句基于来源标题和描述的中文简讯……
> 🔗 来源: Hacker News | 查看原文
>
> -----------------------------------
> **🚀 产品发布**
> ...

---

## 🚀 快速开始

### 方式一：使用 GitHub Actions

无需服务器，Fork 本项目即可运行。

1. **Fork 本仓库** 到你的 GitHub 账号。
2. **配置 Secrets**:
   进入 `Settings` -> `Secrets and variables` -> `Actions`，添加 Repository secrets:
   - 与所选提供商对应的 API Key（三选一）：`DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
   - `FEISHU_WEBHOOK_URL`:（可选）飞书机器人 Webhook 地址；不配置则只跑流程不推送
   - `PRODUCTHUNT_TOKEN`:（可选）Product Hunt Developer Token
3. **选择 AI 提供商**（可选）:
   默认使用 `deepseek`。如需切换，在同一页面的 `Variables` 标签页添加 Repository variable `AI_PROVIDER`，值为 `openai` 或 `anthropic`，并确保配置了对应的 Key。
4. **启用 Workflow**:
   进入 `Actions` 页面，点击 `I understand my workflows, go ahead and enable them`。
5. **手动触发测试**:
   在 `Actions` -> `Daily Hot Tracker` -> `Run workflow` 手动运行一次。
6. **定时运行**:
   默认每天 **北京时间 06:30**（cron `30 22 * * *`，UTC）运行。如需其他时间，请修改 `.github/workflows/daily.yml` 中的 cron。

### 方式二：本地运行

1. **克隆项目**
   ```bash
   git clone https://github.com/reformdai/daily-hot-tracker.git
   cd daily-hot-tracker
   ```

2. **安装依赖**（Python 3.11+）
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   复制 `.env.example` 为 `.env`，填入所选提供商的 Key，并用 `AI_PROVIDER` 指定提供商（`deepseek` / `openai` / `anthropic`，默认 `deepseek`）。`FEISHU_WEBHOOK_URL` 和 `PRODUCTHUNT_TOKEN` 均为可选。
   ```bash
   cp .env.example .env
   vim .env
   ```

4. **运行**
   ```bash
   python main.py

   # 常用选项
   python main.py --limit 5            # 最终保留 5 条（默认 10）
   python main.py --no-ai              # 不调用 AI，按热度排序（无中文简讯）
   python main.py --dry-run            # 不推送飞书，但仍会抓取、调用 AI 并生成 RSS
   python main.py --no-push            # 同上，跳过飞书推送
   python main.py --no-rss             # 不生成 RSS
   python main.py --dry-run --no-ai    # 完全不产生 AI 调用费用的试运行
   ```

   注意：`--dry-run` 只跳过推送，**仍会调用 LLM 并产生费用**；配合 `--no-ai` 才不会调用。

### 退出码

| 情况 | 退出码 |
|------|--------|
| 正常完成，或未配置 Webhook / 使用 `--dry-run`、`--no-push` 主动跳过推送 | 0 |
| 已配置 Webhook 但推送失败 | 1 |
| 未抓取到内容、无符合条件的内容或运行异常 | 1 |

---

## ⚙️ 配置说明

环境变量（`.env` 或 GitHub Secrets / Variables）：

| 变量 | 说明 |
|------|------|
| `AI_PROVIDER` | `deepseek`（默认）/ `openai` / `anthropic` |
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | 与 `AI_PROVIDER` 对应的 Key，只需配置一个 |
| `FEISHU_WEBHOOK_URL` | 可选，飞书机器人 Webhook |
| `PRODUCTHUNT_TOKEN` | 可选，Product Hunt API Token |
| `RSS_OUTPUT_DIR` | 可选，RSS 输出目录，默认 `output` |

`config.py` 中可调整：

- `AI_MODELS`: 各提供商使用的模型和接口地址
- `KEYWORDS`: 预筛选关键词（默认包含 AI、LLM、agent、RAG 等）
- `ENABLED_SOURCES` / `RSS_FEEDS` / `REDDIT_SUBREDDITS` / `ARXIV_CATEGORIES`: 数据源
- `TOP_N_ITEMS`: 每天保留条数的配置默认值（10）。注意：命令行 `--limit` 默认值也是 10，且运行时总会覆盖该配置，因此只修改 `TOP_N_ITEMS` 不会生效；请使用 `python main.py --limit N` 调整条数（GitHub Actions 中需在 workflow 的运行命令里加上该参数）
- `MIN_SCORE_THRESHOLD`: AI 评分阈值（默认 6）

## 🩺 数据源诊断

RSS 和 Reddit 请求使用显式超时（连接 5 秒、读取 20 秒）。HTTP 429/500/502/503/504 和网络错误最多重试 2 次，遵循 `Retry-After`，每个 URL 的等待总预算为 10 秒；403/404 等其他状态不重试。每个 feed 输出一行日志，例如：

```text
[RSS OpenAI Blog] 1229 entries, latest 2026-09-23 17:00 UTC
[RSS Y Combinator] 15 entries, latest 2026-06-16 16:00 UTC (stale: no update in 7+ days)
[RSS a16z] HTTP 404, not retrying; check https://a16z.com/feed/
[Reddit r/SaaS] HTTP 429, retry wait 60s exceeds 10s budget, skipping
[RSS Example] invalid feed (text/html): not an RSS/Atom document
[RSS Example] valid feed with 0 entries
```

Product Hunt 会输出 API 的 HTTP 状态码和 GraphQL 错误信息（服务端若回显已配置的 Token，会替换为 `***`），并区分页面兜底是遇到机器人验证还是页面结构变化。AIHOT 会列出回退到「行业动态」的未知分类名。

## ⚠️ 已知限制

- AI 生成的标题、简讯，以及版块名、飞书卡片和 RSS 的固定文案均为中文，暂不支持其他输出语言；原始来源标题和文本可能保留原语言（尤其在 `--no-ai` 或 AI 失败回退时）。
- 各数据源的页面结构或接口变化可能导致某个来源暂时抓不到内容；控制台日志会说明原因（见上节）。
- 截至 2026-09-24，已配置的 a16z、First Round Review、Anthropic 订阅地址返回 404，尚未找到等价的官方 feed。它们仍保持启用，每次运行输出 `HTTP 404, not retrying`。Y Combinator、VentureBeat 更新较慢，可能输出 stale 警告。
- Product Hunt：有 Token 时优先使用官方 API，但本次未使用真实 Token 验证该路径。公开页面兜底依赖当前首页结构，可能被机器人验证拦截，且拿不到发布时间。API 查询按票数排序、未加日期过滤，是否返回当日新品尚未验证。
- Reddit RSS 经常被限流（HTTP 429）。`Retry-After` 过长时直接跳过而不等待，因此单次运行可能缺少部分社区。
- 各来源的时间戳尚未统一时区（有的是 UTC，有的是本地时间），也没有硬性的时效截止：旧条目仍可能入选，只会在日志中标记。
- 本机网络下的抓取结果不代表 GitHub Actions 运行环境同样可用。
- workflow 中的 `Upload logs` 步骤上传 `logs/` 目录，但程序目前不会生成该目录，该步骤可能提示未找到文件。

## 🧪 测试

离线回归测试不访问网络、不读取 `.env`、不调用 LLM：

```bash
venv/bin/python -m unittest discover -s tests -t .
```

根目录的 `test_reddit.py` 是需要联网的手动连通性脚本，不属于上述测试。

## 🛠️ 技术栈

- **Python 3.11+**
- **LLM API**: DeepSeek / OpenAI / Anthropic
- **Feedparser**: RSS 解析
- **GitHub Actions**: 定时任务调度

## 📝 License

MIT License

注：仓库目前尚未包含独立的 LICENSE 文件。
