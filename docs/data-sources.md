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
| 自适应频率、来源分级、全文补抓 | 暂未移植：需要调整调度/评分或存储；目前只采集列表摘要 |
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

## 如何新增来源

优先选官方 RSS/Atom；无 feed 再选公开 JSON GET 接口；两者都没有再选静态 HTML 列表。每个配置中的 `name` 就是下游看到的来源名，`category` 参与现有关键词预筛选。

### RSS

在 `config.py` 的 `RSS_FEEDS` 增加：

```python
{"name": "Example Blog", "url": "https://example.com/feed.xml", "category": "AI"}
```

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

新列表适配器只接受上述字段和 `enabled`，拼错配置会报告失败。每个适配器分别受 `MAX_ITEMS_PER_SOURCE` 限额约束，多源时按源轮询。

## 单源试抓

```bash
venv/bin/python probe_sources.py web_list --name Anthropic --limit 3
venv/bin/python probe_sources.py rss --name 'Google DeepMind' --limit 3
venv/bin/python probe_sources.py json_list --name 'LangGraph Releases' --limit 3
venv/bin/python -m unittest discover -s tests -t .
```

试抓入口不加载 `.env`，不调用 AI、不推送、不写 RSS。无有效条目返回退出码 1（合法空 feed 也如此），有条目返回 0。省略 `--name` 会试抓该类型全部启用源；不要把原有 `--dry-run` 当成该入口，它仍会调用 AI。

后续优先级：先补全跨来源 UTC 时间统一与可配置的时效规则，再考虑持久化抓取状态和跨天去重。仅增加信源数量不能保证最终日报多样性，现有热度排序和 AI 前 25 条限制仍然有效。
