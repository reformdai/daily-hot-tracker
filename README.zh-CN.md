# 🤖 AI Daily Hot Tracker (每日热点追踪器)

简体中文 | [English](README.md)

一个 AI 领域每日精选生成器。它从 Hacker News、GitHub Trending、Reddit、Product Hunt、ArXiv、AIHOT 和科技博客 RSS 抓取 AI 相关热门内容，调用 DeepSeek / OpenAI / Anthropic 大模型进行评分、分类、翻译标题并撰写中文简讯，生成**中文精选简报**，可选推送到飞书群，本地运行时还可输出 RSS Feed。

> **特点**：GitHub Actions 定时运行，无需自建服务器；提示词要求模型仅依据各平台提供的标题和描述撰写摘要，但生成结果仍可能出错，使用前请对照原文核对。AI 生成的标题、简讯和版块名为中文；原始来源的标题和文本可能保留原语言（尤其在 `--no-ai` 或 AI 调用失败回退时）。LLM API 调用按所选提供商计费。

---

## ✨ 核心功能

- **🔥 多源热点聚合**
  - **Hacker News**: 全站热榜 + Algolia 关键词搜索（最近 24 小时内的高分 AI 讨论，弥补热榜里 AI 内容少的问题）
  - **Hugging Face**: 每日论文（社区投票 + 摘要）与新近创建的趋势模型
  - **GitHub Trending**: 今日增长最快的开源项目
  - **Product Hunt**: 每日最佳新产品（有 Token 时走官方 API；否则只抓取公开首页的「今日」榜单区域）
  - **Reddit**: 热门社区讨论 (r/LocalLLaMA, r/MachineLearning 等)
  - **ArXiv**: AI/ML 领域最新论文 (cs.AI, cs.CL, cs.LG, cs.CV)
  - **AIHOT**: AIHOT 平台精选热点（公开 API，无需 Key）
  - **Tech Blog**: 20 个 RSS 订阅，按信源分级：T1 官方一手（OpenAI、DeepMind、Google Research、Hugging Face、Microsoft Research、NVIDIA、AWS、GitHub、Mistral、BAIR）与 T2 媒体/个人（TechCrunch、The Verge、Ars Technica、MIT TR、The Decoder、Simon Willison、Import AI、Latent Space 等）
  - **网页 / JSON 列表**: Anthropic 官网新闻，以及可配置字段映射的公开 JSON GET 接口

- **🧲 获取与排序（参考 AIHOT）**
  - **并发抓取 + 信源健康报告**: 各来源并发抓取，日志按来源分组；每次运行在 `logs/` 写入各源状态、耗时与全部候选的排序信号
  - **跨源合并**: 先按归一化 URL（去追踪参数、arxiv 各版本与 HF Papers 统一）合并，再按标题相似度合并；代表条目优先官方一手信源，并记录被几个独立来源报道
  - **综合排序分**: 来源内互动分位数（不同平台分数不可直接比）+ 信源分级 + 24 小时半衰的时效 + 多源佐证
  - **时效窗口**: 默认丢弃最近一次出现已超过 72 小时的内容（榜单类无时间的条目保留）
  - **候选多样性**: 送 AI 的 40 条候选中，单一来源族（如 Reddit、ArXiv）最多 10 条
  - **原文补抓**: 对描述不足的候选抓取原文正文（GitHub / HF 模型读 README），可选 Jina Reader 兜底

- **🧠 AI 智能处理**
  - **关键词预筛选**: 英文关键词按词边界匹配（此前 "AI" 会误命中 "said"、"paid"），支持中文关键词；ArXiv、HF、AIHOT 等 AI 垂直源免筛
  - **智能评分**: 1-10 分，保留 6 分以上的 Top 10（GitHub Trending 每天最多 2 条且需 8 分以上）
  - **中文简讯**: 根据标题、来源描述和补抓的原文摘录（批量评分时取前 600 字）撰写不超过 140 字的中文简讯；评分时同时提供信源等级、独立来源数和热度作为重要性参考
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
| `JINA_READER_FALLBACK` / `JINA_API_KEY` | 可选，原文补抓失败时用 Jina Reader 渲染兜底（`true` 开启；Key 可不填但限流更严） |
| `MAX_ITEM_AGE_HOURS` | 可选，时效窗口小时数，默认 72；`0` 关闭 |
| `AI_CANDIDATE_LIMIT` / `MAX_CANDIDATES_PER_FAMILY` | 可选，送 AI 的候选数（默认 40）与单一来源族上限（默认 10） |
| `LOG_DIR` | 可选，运行日志目录，默认 `logs` |

`config.py` 中可调整：

- `AI_MODELS`: 各提供商使用的模型和接口地址
- `KEYWORDS`: 预筛选关键词（默认包含 AI、LLM、agent、RAG 等）
- `ENABLED_SOURCES` / `RSS_FEEDS` / `WEB_SOURCES` / `JSON_SOURCES` / `REDDIT_SUBREDDITS` / `ARXIV_CATEGORIES` / `HN_SEARCH_QUERIES`: 数据源
- `SOURCE_TIERS` 及各源配置里的 `"tier"`: 信源分级（T1 官方一手 / T2 媒体与精选 / T3 社区与榜单）
- `KEYWORD_EXEMPT_SOURCES`: 跳过关键词预筛选的 AI 垂直源
- `SOURCE_ITEM_LIMITS`: 单个来源的条目上限（RSS 默认 60）
- `TOP_N_ITEMS`: 每天保留条数的配置默认值（10）。注意：命令行 `--limit` 默认值也是 10，且运行时总会覆盖该配置，因此只修改 `TOP_N_ITEMS` 不会生效；请使用 `python main.py --limit N` 调整条数（GitHub Actions 中需在 workflow 的运行命令里加上该参数）
- `MIN_SCORE_THRESHOLD`: AI 评分阈值（默认 6）

## 🩺 数据源诊断

RSS、Reddit 和新增网页/JSON 列表请求使用显式超时（连接 5 秒、读取 20 秒）。HTTP 429/500/502/503/504 和网络错误最多重试 2 次，遵循 `Retry-After`，每个 URL 的等待总预算为 10 秒；403/404 等其他状态不重试。每个 feed 输出一行日志，例如：

```text
[RSS OpenAI Blog] 1229 entries, latest 2026-09-23 17:00 UTC
[RSS Y Combinator] 15 entries, latest 2026-06-16 16:00 UTC (stale: no update in 7+ days)
[RSS Example] HTTP 404, not retrying; check https://example.com/feed/
[Reddit r/SaaS] HTTP 429, retry wait 60s exceeds 10s budget, skipping
[RSS Example] invalid feed (text/html): not an RSS/Atom document
[RSS Example] valid feed with 0 entries
```

Product Hunt 会输出 API 的 HTTP 状态码和 GraphQL 错误信息（服务端若回显已配置的 Token，会替换为 `***`），并区分页面兜底是遇到机器人验证还是页面结构变化。AIHOT 会列出回退到「行业动态」的未知分类名。

## ⚠️ 已知限制

- AI 生成的标题、简讯，以及版块名、飞书卡片和 RSS 的固定文案均为中文，暂不支持其他输出语言；原始来源标题和文本可能保留原语言（尤其在 `--no-ai` 或 AI 失败回退时）。
- 各数据源的页面结构或接口变化可能导致某个来源暂时抓不到内容；控制台日志会说明原因（见上节）。
- 截至 2026-09-29，a16z、First Round Review 订阅地址仍返回 404，已保留配置并停用。Anthropic 已改用官网新闻列表；新增并验证 Google DeepMind、Google Research 官方 RSS。Y Combinator、VentureBeat 更新较慢，可能输出 stale 警告。
- Product Hunt：有 Token 时优先使用官方 API，但本次未使用真实 Token 验证该路径。公开页面兜底依赖当前首页结构，可能被机器人验证拦截，且拿不到发布时间。API 查询按票数排序、未加日期过滤，是否返回当日新品尚未验证。
- Reddit RSS 经常被限流（HTTP 429）。`Retry-After` 过长时直接跳过而不等待，因此单次运行可能缺少部分社区。
- 时效窗口依赖各来源提供的时间；Anthropic 等只有日期的页面按 UTC 零点计算，GitHub Trending、HF 趋势模型等榜单没有发布时间，不受时效窗口约束。
- 2026-10-02 新增的 RSS 源、HN 搜索与 Hugging Face 接口在开发环境中网络受限，未能实测，只做了离线解析测试；首次运行请查看日志或 `logs/run-*.json` 里的信源状态，失效的源改为 `enabled: False`。
- 原文补抓只读静态 HTML，不执行 JavaScript；读不到时退回来源描述，不影响流程。补抓会对候选原文站点各发一次请求。
- 本机网络下的抓取结果不代表 GitHub Actions 运行环境同样可用。
- 没有持久化存储，同一条热点可能连续两天入选（时效窗口与半衰排序会降低这种概率）。

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

## 新增与试抓信源

见[数据源接入与 AIHOT 借鉴](docs/data-sources.md)：包含 RSS、网页选择器、JSON 字段映射、接入边界与研究结论。RSS 改为各源最新优先、按源轮询取样，减少高频源占满总额度的情况。

```bash
venv/bin/python probe_sources.py web_list --name Anthropic --limit 3
venv/bin/python probe_sources.py rss --name 'Google DeepMind' --limit 3
venv/bin/python probe_sources.py hn_search --limit 5
venv/bin/python probe_sources.py huggingface --limit 5 --body   # --body 同时试读原文摘录
```

试抓不加载 `.env`、不调用 AI、不推送、不生成 RSS 文件。`JSON_SOURCES` 默认留空。
