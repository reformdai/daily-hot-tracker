# 数据源接入与 AIHOT 借鉴

## 结论

当前项目是每天执行一次的 Python 日报，保留 `BaseFetcher → ContentItem → 去重/关键词/AI评分` 就能接入新信源。采用 AIHOT 的「协议适配器 + 来源配置」思路，无需引入它的数据库、队列、后台或 TypeScript 服务。

研究基于 [AIHOT](https://github.com/KKKKhazix/AIHOT/tree/589f79eff09470b31ba8a7f1d9eb62d36ff2be6c) 的公开源码。其完整运营信源名单没有开源，`industry/sources.json` 仅有 18 个 RSS 示例。

| AIHOT 的做法 | 本项目应用 |
| --- | --- |
| `rss`、`web_list`、`json_list` 各自映射为 Candidate | 保留 RSS；新增网页 CSS 选择器和 JSON 点分路径适配器，输出 ContentItem |
| 配置键校验，抓取前试抓 | 新列表适配器拒绝未知键/缺失必填字段；`probe_sources.py` 独立试抓 |
| 单源启停、失败隔离 | RSS/网页/JSON 配置支持 `enabled: False`；主流程异常不阻断其他来源 |
| URL 判重、标题/链接必填 | 新适配器源内 URL 去重、HTTP(S) 校验、URL 稳定 ID；RSS 跳过坏条目和重复链接 |
| 失败/空结果有诊断 | 复用现有超时和有限重试；字段失配、非 JSON、空列表输出不同日志 |
| RSS ETag/Last-Modified、持久化游标、首次导入归档 | 暂未移植：本项目没有持久化采集库，直接套用 304 会丢掉当日候选内容 |
| 来源分级、全文补抓 | 2026-10-02 已移植，见下文「获取能力增强」 |
| 自适应频率 | 不适用：本项目每天只跑一次 |
| X、公众号、外部推送 | 暂未接入：分别涉及第三方付费凭据或新服务端入口 |

参考实现：[信源说明](https://github.com/KKKKhazix/AIHOT/blob/589f79eff09470b31ba8a7f1d9eb62d36ff2be6c/docs/sources.md)、[网页适配器](https://github.com/KKKKhazix/AIHOT/blob/589f79eff09470b31ba8a7f1d9eb62d36ff2be6c/packages/backend/src/sources/web-list.ts)、[JSON 适配器](https://github.com/KKKKhazix/AIHOT/blob/589f79eff09470b31ba8a7f1d9eb62d36ff2be6c/packages/backend/src/sources/json-list.ts)、[采集管道](https://github.com/KKKKhazix/AIHOT/blob/589f79eff09470b31ba8a7f1d9eb62d36ff2be6c/packages/backend/src/sources/collect.ts)。本次按现有 Python 架构实现，没有直接复制 TypeScript 代码。

## 已应用的源调整

2026-09-29 在当前主机公开端点试抓：

| 来源 | 调整与结果 |
| --- | --- |
| Anthropic | 失效 RSS 改为 `https://www.anthropic.com/news`；新适配器解析 10 条，提取标题、原文地址和日期 |
| Google DeepMind | 新增官方 RSS `https://deepmind.google/blog/rss.xml`；200，100 条 |
| Google Research | 新增官方 RSS `https://research.google/blog/rss/`；200，100 条 |
| a16z、First Round Review | 原订阅地址仍 404，保留配置并设置 `enabled: False` |

这些结果只证明本机本次可访问，不代表 GitHub Actions 或未来页面改版后仍然有效。Anthropic 页面只有日期，按 UTC 零点存储，不能据此推断精确发布时间。

## 获取能力增强（2026-10-02）

参考 AIHOT 最新代码（commit 3343fe2）的 `industry/sources.json`、`events/hot.ts`、`content/extract.ts`、`prompts/prefilter.md`、`selection.ts`，按日报场景做了取舍：

| 环节 | 改动 | 对应 AIHOT 做法 |
| --- | --- | --- |
| 新信源 | `hn_search`：HN Algolia 搜索 24 小时内 ≥30 分的 AI 讨论；`huggingface`：每日论文（投票+摘要）与 14 天内创建的趋势模型；RSS 从 11 个扩到 20 个启用源 | 示范信源 18 个 RSS |
| 信源分级 | T1 官方一手 / T2 媒体与精选 / T3 社区与榜单；RSS/网页/JSON 配置写 `"tier"`，内置抓取器查 `SOURCE_TIERS` | `tier` + 分级入选门槛 |
| 跨源合并 | 归一化 URL（去 utm/ref、www、锚点；arxiv 各版本与 HF Papers 统一为 `arxiv:<id>`；GitHub 仓库子页面归到仓库）后合并，再按标题相似度合并；代表条目优先 T1；子 subreddit 算同一参与方 | URL 判重、participant_key |
| 热度 | 来源族内互动分位数，避免 GitHub 今日 star 与 HN points 直接相加 | 独立参与方计数 |
| 时效 | 按最近一次出现时间 24 小时半衰；超过 `MAX_ITEM_AGE_HOURS`（默认 72，ArXiv/HF 论文 120）丢弃 | 48 小时窗口、24 小时半衰 |
| 候选多样性 | 送 AI 40 条，单一来源族 ≤10 条 | — |
| 正文补抓 | 描述不足 280 字的候选抓正文：GitHub/HF 读 README，其他读 `<article>/<main>` 段落与 meta 描述；`JINA_READER_FALLBACK=true` 时 Jina 兜底；X/Reddit 等跳过 | Readability + Jina 兜底 |
| 评分输入 | 提示词附带「信号」（分级、独立来源数、热度）和原文摘录，批量评分描述从 200 字增至 600 字 | 精选评分看全文与信源 |
| 关键词 | 英文按词边界匹配，修复 "AI" 命中 "said"/"paid" 使预筛形同虚设；补中文关键词；AI 垂直源免筛 | LLM 宽召回预筛（未移植） |
| 可观测性 | 并发抓取、日志按来源分组；`logs/run-*.json` 记录各源状态/耗时与全部候选的排序信号、补抓方式、AI 分 | 后台信源健康页 |

综合排序分（0-100）= 100 ×（0.35 互动分位 + 0.25 分级权重 + 0.20 时效 + 0.20 佐证）。分级权重 T1 1.0 / T2 0.6 / T3 0.3；时效无时间记 0.5；佐证按独立来源族数，2 个 0.5，3 个及以上 1.0。`--no-ai` 时 AI 分 = 综合分 / 10。

开发环境网络受限，新增 RSS、HN 搜索和 Hugging Face 接口只做了离线解析测试；Anthropic 与 Microsoft Research 实测可抓，正文补抓在这两个站点各读到 5000+ 字。首次在 Actions 运行后请看 `logs/` 产物。

## 推送记忆（2026-10-02）

此前同一热点会连续几天被推送：程序每次运行都没有记忆，热点未散去时会被再次抓到、再次入选。2026-02 曾加过本地文件形式的已推送历史，但 GitHub Actions 每次运行都是新机器，文件无法保留，随后被移除。

现在 `memory.py` 维护 `state/push_history.json`（最近 7 天，每条记录日期、原标题、中文标题、分类和全部归一 URL），workflow 用 `actions/cache`（每次运行一个新 key，按前缀恢复最近一份）在运行之间保存：

1. 去重合并与时效过滤之后、关键词预筛之前，URL 交集或原标题相似度 ≥ 0.8 的条目直接剔除，避免占用候选名额。
2. AI 评分提示词附上最近 60 条已推送中文标题，模型为每条返回 `novelty`：`new` / `followup`（实质新进展，保留并在卡片标「🔄 后续」）/ `repeat`（剔除）。字段缺失或不合法时按 `new` 处理。
3. 只在飞书推送成功后写入；记忆文件损坏或缓存丢失时按无记忆运行。

### 后续可考虑（未实现）

- **LLM 宽召回预筛**：AIHOT 用 PASS/BLOCK/UNKNOWN 三分类代替关键词，召回更全，但每天多一次模型调用。
- **事件归组**：用 embedding 把同一事件的不同报道（标题差异大、URL 不同）聚成一组，佐证信号会更准。
- **X / 公众号**：AIHOT 分别用 SocialData、极致了的付费接口；也可自建 RSSHub / WeWe RSS 后作为普通 RSS 接入。
- **中文信源**：机器之心、量子位等可通过 RSSHub 或网页列表接入，需要先实测页面结构。

## 如何新增来源

优先选官方 RSS/Atom；无 feed 再选公开 JSON GET 接口；两者都没有再选静态 HTML 列表。每个配置中的 `name` 就是下游看到的来源名，`category` 参与现有关键词预筛选。

### RSS

在 `config.py` 的 `RSS_FEEDS` 增加：

```python
{"name": "Example Blog", "url": "https://example.com/feed.xml", "category": "AI", "tier": "T1"}
```

`tier` 可选（默认 T3），网页/JSON 源同样支持。`category` 写 `"AI"` 时该源所有条目都会通过关键词预筛选；综合性博客请写其他分类。

`enabled` 默认为 True，False 时不请求。各 feed 内按日期从新到旧排序，然后轮询取样，整体最多 `MAX_ITEMS_PER_SOURCE` 条。当限额小于启用的源数量时，仍只覆盖前面的源；旧文章依然有资格入选，stale 目前只是警告。

### 网页列表

在 `WEB_SOURCES` 增加配置：

```python
{
    "name": "Example News", "url": "https://example.com/news", "category": "AI",
    "item_selector": "article",
    "link_selector": "a", "title_selector": "h2",
    "summary_selector": "p", "date_selector": "time",
    "allow_url_prefixes": ["https://example.com/news/"],
}
```

必填 `name`、`url`、`item_selector`。选择器相对于每个条目；如果条目本身是 `<a>`，省略 `link_selector`，标题也可省略选择器使用条目文本。日期优先读取 `datetime` 属性，否则读取文字。支持 ISO 8601、`Sep 23, 2026` / `September 23, 2026`、`2026/09/23`；无法解析则保留 None，不假装刚发布。相对链接依据 HTTP 重定向后的最终地址解析。只抓静态 HTML，不执行 JavaScript，不自动绕过验证页。

### JSON 列表

在 `JSON_SOURCES` 添加公开接口，例如（默认列表为空，是否订阅自行决定）：

```python
{
    "name": "LangGraph Releases",
    "url": "https://api.github.com/repos/langchain-ai/langgraph/releases?per_page=5",
    "category": "AI",
    "items_path": "",
    "title_path": "name", "url_path": "html_url",
    "date_path": "published_at", "summary_path": "body", "author_path": "author.login",
}
```

上述 GitHub 示例已于 2026-09-29 试抓，解析 5 条有效 release；默认未启用。

必填 `name`、`url`、`title_path`、`url_path`。`items_path` 为空表示根数组；嵌套列表可填 `data.items`，数组索引如 `links.0.href`。字段值须为字符串，日期规则同网页源。返回非 JSON、列表路径不是数组、非空列表完全无法映射都会报错；合法空数组报告 0 条。仅支持单页公开 GET，不支持 POST、认证、脚本内嵌 JSON、分页或 Unix 时间戳；这些需求应在有具体信源时补充。

新列表适配器只接受上述字段和 `enabled`、`tier`，拼错配置会报告失败。每个适配器分别受 `MAX_ITEMS_PER_SOURCE` 限额约束，多源时按源轮询。

## 单源试抓

```bash
venv/bin/python probe_sources.py web_list --name Anthropic --limit 3
venv/bin/python probe_sources.py rss --name 'Google DeepMind' --limit 3
venv/bin/python probe_sources.py json_list --name 'LangGraph Releases' --limit 3
venv/bin/python probe_sources.py hn_search --limit 5
venv/bin/python probe_sources.py huggingface --limit 5 --body
venv/bin/python -m unittest discover -s tests -t .
```

试抓入口不加载 `.env`，不调用 AI、不推送、不写 RSS。无有效条目返回退出码 1（合法空 feed 也如此），有条目返回 0。省略 `--name` 会试抓该类型全部启用源；不要把原有 `--dry-run` 当成该入口，它仍会调用 AI。

`--body` 会对每条结果试读原文摘录，显示补抓方式（readme/html/meta/jina）与字数。
