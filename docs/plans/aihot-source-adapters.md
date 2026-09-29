# AIHOT 数据源接入改进

## 目标与边界

2026-09-29：参考 KKKKhazix/AIHOT 的协议适配和配置分离，改善当前 Python 日报的直接信源覆盖。Codex 为本次唯一写入者；开始时工作区干净。既有 data-source-repair 计划已完成，其 Claude 写入约定只针对旧任务。

不改认证、CI、生产、数据库或评分模型，不调用 AI/飞书，不提交推送，不新增依赖。

## 实施

- [x] 增加配置驱动的公开 HTML 列表和 GET JSON 列表适配器，复用有限重试，统一 ContentItem；检查必填字段和不支持的配置。
- [x] Anthropic 改为官网新闻列表；新增 DeepMind/Google Research RSS；停用仍 404 的 a16z/First Round RSS。
- [x] RSS 支持 enabled、有效条目校验、按源轮询取样，避免高频 feed 占满总额度。
- [x] 主流程接入；提供不加载 dotenv、不调用 AI/推送的单源试抓入口。
- [x] 补回归测试、接入说明和研究结论；离线全套测试、公开端点验证、diff 检查。

## 验收

网页相对链接、日期、重复/坏条目处理正确；JSON 路径失配有诊断；禁用源无请求；某源失败不阻断其他源；现有测试通过。新增实际源可抓到有效标题和原文 URL，日期缺失不伪造为当前时间。

## 研究依据

AIHOT commit 589f79eff09470b31ba8a7f1d9eb62d36ff2be6c，重点 docs/sources.md、industry/sources.json、packages/backend/src/sources/{rss,web-list,json-list,collect}.ts。

实测 2026-09-29：Anthropic /news 返回 200，新闻链接含 time 和标题 span；DeepMind 与 Google Research RSS 均 200、100 条；a16z /feed/ 与 First Round /feed.xml 均 404。

## 验证结果

- 62 项离线测试通过，包括源异常隔离与主流程接入；没有真实 AI/飞书调用。
- 新适配器实测 Anthropic 10 条；DeepMind / Google Research 各 100 条；公开 GitHub LangGraph Releases JSON 示例 5 条，标题/URL/UTC 日期有效。
- `git diff --check` 通过；文档见 `docs/data-sources.md`。
- 没有提交、推送、部署或修改认证/CI。外部页面变动、旧内容时效和下游排序偏差仍需后续独立处理。
