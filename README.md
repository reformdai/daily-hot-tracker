# 🤖 AI Daily Hot Tracker

English | [简体中文](README.zh-CN.md)

A daily AI news digest generator. It collects AI-related trending items from Hacker News, GitHub Trending, Reddit, Product Hunt, ArXiv, AIHOT and tech blog RSS feeds, then uses a DeepSeek / OpenAI / Anthropic model to score, categorize, translate titles and write short summaries. The result is a **Chinese-language digest** that can optionally be pushed to a Feishu (Lark) group; local runs can also write an RSS feed.

> **Note**: The AI-generated digest (translated titles, summaries) and fixed labels (section names, Feishu card, RSS metadata) are in **Chinese**; other output languages are not supported yet. Original source titles and text may remain in their original language, especially with `--no-ai` or when AI processing falls back.
>
> The prompts instruct the model to rely only on the source-provided title and description, but generated summaries can still be wrong — verify against the original before relying on them.
>
> Runs on a GitHub Actions schedule, so no server is required. Summaries are based only on the title and description each source provides. LLM API usage is billed by your chosen provider.

---

## ✨ Features

- **🔥 Multi-source collection**
  - **Hacker News**: front page plus Algolia keyword search (high-scoring AI stories from the last 24 hours, which the front page often misses)
  - **Hugging Face**: daily papers (community upvotes + abstracts) and recently created trending models
  - **GitHub Trending**
  - **Product Hunt** (official API with a token; otherwise only the "Top Products Launching Today" section of the public homepage)
  - **Reddit** (r/LocalLLaMA, r/MachineLearning, etc.)
  - **ArXiv** (cs.AI, cs.CL, cs.LG, cs.CV)
  - **AIHOT** (public API, no key needed)
  - **Tech blogs** via 20 RSS feeds, tiered as T1 first-party (OpenAI, DeepMind, Google Research, Hugging Face, Microsoft Research, NVIDIA, AWS, GitHub, Mistral, BAIR) and T2 media/individuals (TechCrunch, The Verge, Ars Technica, MIT TR, The Decoder, Simon Willison, Import AI, Latent Space, etc.)
  - **Web / JSON lists**: Anthropic news via configurable HTML selectors; public JSON GET adapters available

- **🧲 Collection and ranking (inspired by AIHOT)**
  - **Concurrent fetching + source health report**: sources are fetched concurrently with logs grouped per source; each run writes source status, timing and every candidate's ranking signals to `logs/`
  - **Cross-source merging**: items merge by canonical URL (tracking params stripped; arXiv versions and HF Papers unified), then by title similarity; the representative item prefers first-party sources and records how many independent sources covered the story
  - **Rank score**: within-source engagement percentile (platform scores are not comparable) + source tier + 24-hour half-life recency + multi-source corroboration
  - **Freshness window**: items whose latest sighting is older than 72 hours are dropped by default (undated chart items are kept)
  - **Candidate diversity**: of the 40 candidates sent to the model, one source family (e.g. Reddit, ArXiv) can take at most 10
  - **Full-text enrichment**: candidates with thin descriptions get an excerpt of the original page (README for GitHub / HF models), with optional Jina Reader fallback

- **🧠 Push memory (cross-day dedup)**
  - Remembers what was pushed in the last 7 days (`state/push_history.json`, kept between GitHub Actions runs with `actions/cache`)
  - Rule layer: items with the same URL (including tracking-param and HN-discussion variants) or a near-identical original title are dropped before AI scoring
  - Semantic layer: the scoring prompt includes recent pushed headlines; the model labels each item as a new event, a **substantive follow-up** to a pushed story (kept and tagged "🔄 后续" on the card), or a **repeat** re-telling (dropped)
  - Recorded only after a successful Feishu push; `--dry-run` / `--no-push` do not record, `--no-memory` ignores memory entirely

- **🧠 AI processing**
  - **Keyword prefilter**: English keywords match on word boundaries (previously "AI" matched "said" and "paid"); Chinese keywords supported; AI-native sources (ArXiv, HF, AIHOT) are exempt
  - **Scoring**: 1–10; keeps the top 10 items scoring 6 or higher (at most 2 GitHub Trending items per day, each scoring 8 or higher)
  - **Summaries**: up to 140 Chinese characters, written from the title, source description and the fetched article excerpt (first 600 characters in batch scoring); scoring also sees the source tier, independent-source count and engagement as importance hints
  - **Five sections**: 🧠 模型发布 (models) / 🚀 产品发布 (products) / 📊 行业动态 (industry) / 📝 论文研究 (papers) / 💡 技巧与观点 (tips & opinions)
  - **Output validation**: scores, indexes, categories and field types returned by the model are validated; missing or invalid items are retried once individually and dropped if they still fail

- **📱 Output**
  - **Feishu card (optional)**: grouped by section. Delivery is skipped when no webhook is configured; if a configured webhook fails, the process exits with a nonzero status
  - **RSS feed**: local runs write `output/feed.xml` by default. The bundled workflow runs with `--no-rss` and does not deploy GitHub Pages; host the feed yourself if you want public subscriptions
  - The bundled workflow runs daily at **22:30 UTC (06:30 Beijing time)**

## 📸 Preview

The following is **illustrative only**; it shows the card layout, not real output:

> 📅 **2026-01-01** | 精选 10 条高价值内容
> -----------------------------------
> **🧠 模型发布**
>
> **1. [示例模型发布开源权重](https://example.com)**
> A one- or two-sentence Chinese summary based on the source title and description…
> 🔗 来源: Hacker News | 查看原文
>
> -----------------------------------
> **🚀 产品发布**
> ...

---

## 🚀 Getting started

### Option 1: GitHub Actions

1. **Fork** this repository.
2. **Add secrets** under `Settings` -> `Secrets and variables` -> `Actions` -> Repository secrets:
   - The API key for your provider (one of): `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
   - `FEISHU_WEBHOOK_URL`: (optional) Feishu bot webhook; without it the pipeline runs but nothing is pushed
   - `PRODUCTHUNT_TOKEN`: (optional) Product Hunt developer token
3. **Choose a provider** (optional): the default is `deepseek`. To switch, add a Repository variable `AI_PROVIDER` on the `Variables` tab with value `openai` or `anthropic`, and make sure the matching key is set.
4. **Enable workflows** on the `Actions` page.
5. **Test manually**: `Actions` -> `Daily Hot Tracker` -> `Run workflow`.
6. **Schedule**: runs daily at 22:30 UTC (cron `30 22 * * *`). Edit the cron in `.github/workflows/daily.yml` to change it.

### Option 2: Run locally

1. **Clone**
   ```bash
   git clone https://github.com/reformdai/daily-hot-tracker.git
   cd daily-hot-tracker
   ```

2. **Install dependencies** (Python 3.11+)
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   Copy `.env.example` to `.env`, fill in the key for your provider and set `AI_PROVIDER` (`deepseek` / `openai` / `anthropic`, default `deepseek`). `FEISHU_WEBHOOK_URL` and `PRODUCTHUNT_TOKEN` are optional.
   ```bash
   cp .env.example .env
   vim .env
   ```

4. **Run**
   ```bash
   python main.py

   # Options
   python main.py --limit 5            # keep 5 items (default 10)
   python main.py --no-ai              # no AI; rank by popularity (no Chinese summaries)
   python main.py --dry-run            # skip Feishu, but still fetch, call the AI and write RSS
   python main.py --no-push            # same as above: skip Feishu delivery
   python main.py --no-rss             # do not write the RSS feed
   python main.py --dry-run --no-ai    # trial run with no LLM cost
   ```

   `--dry-run` only skips delivery; it **still calls the LLM and incurs cost**. Combine it with `--no-ai` to avoid model calls.

### Exit status

| Situation | Exit code |
|-----------|-----------|
| Completed, or delivery skipped (no webhook configured, `--dry-run`, `--no-push`) | 0 |
| Webhook configured but delivery failed | 1 |
| No items fetched, nothing qualified, or an unexpected error | 1 |

---

## ⚙️ Configuration

Environment variables (`.env`, or GitHub Secrets / Variables):

| Variable | Description |
|----------|-------------|
| `AI_PROVIDER` | `deepseek` (default) / `openai` / `anthropic` |
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Key for the selected provider; only one is needed |
| `FEISHU_WEBHOOK_URL` | Optional Feishu bot webhook |
| `PRODUCTHUNT_TOKEN` | Optional Product Hunt API token |
| `RSS_OUTPUT_DIR` | Optional RSS output directory, default `output` |
| `JINA_READER_FALLBACK` / `JINA_API_KEY` | Optional Jina Reader fallback for full-text enrichment (`true` to enable; key optional but stricter rate limits without it) |
| `MAX_ITEM_AGE_HOURS` | Optional freshness window in hours, default 72; `0` disables |
| `AI_CANDIDATE_LIMIT` / `MAX_CANDIDATES_PER_FAMILY` | Optional candidate count sent to the model (default 40) and per-source-family cap (default 10) |
| `LOG_DIR` | Optional run log directory, default `logs` |
| `HISTORY_PATH` / `HISTORY_TTL_DAYS` | Optional push memory file (default `state/push_history.json`) and retention days (default 7) |

In `config.py`:

- `AI_MODELS`: model name and endpoint per provider
- `KEYWORDS`: prefilter keywords (AI, LLM, agent, RAG, etc.)
- `ENABLED_SOURCES` / `RSS_FEEDS` / `WEB_SOURCES` / `JSON_SOURCES` / `REDDIT_SUBREDDITS` / `ARXIV_CATEGORIES` / `HN_SEARCH_QUERIES`: sources
- `SOURCE_TIERS` and per-source `"tier"`: T1 first-party / T2 media and curated / T3 community and charts
- `KEYWORD_EXEMPT_SOURCES`: AI-native sources that skip the keyword prefilter
- `SOURCE_ITEM_LIMITS`: per-source item caps (RSS defaults to 60)
- `TOP_N_ITEMS`: config default for items kept per day (10). Note: the CLI `--limit` option also defaults to 10 and always overrides this value at runtime, so editing `TOP_N_ITEMS` alone has no effect; use `python main.py --limit N` instead (for GitHub Actions, add it to the run command in the workflow)
- `MIN_SCORE_THRESHOLD`: minimum AI score (default 6)

## 🩺 Source diagnostics

RSS, Reddit and the new web/JSON list adapters use explicit timeouts (5 s connect, 20 s read). HTTP 429/500/502/503/504 and network errors are retried at most twice, honoring `Retry-After`, within a 10-second wait budget per URL; other statuses such as 403/404 are not retried. Each feed logs one line, for example:

```text
[RSS OpenAI Blog] 1229 entries, latest 2026-09-23 17:00 UTC
[RSS Y Combinator] 15 entries, latest 2026-06-16 16:00 UTC (stale: no update in 7+ days)
[RSS Example] HTTP 404, not retrying; check https://example.com/feed/
[Reddit r/SaaS] HTTP 429, retry wait 60s exceeds 10s budget, skipping
[RSS Example] invalid feed (text/html): not an RSS/Atom document
[RSS Example] valid feed with 0 entries
```

Product Hunt logs API HTTP status and GraphQL error messages (a configured token echoed by the server is masked as `***`) and says whether the page fallback hit a bot challenge or changed markup. AIHOT logs unknown category names that fall back to 行业动态.

## ⚠️ Known limitations

- AI-generated titles and summaries, plus section names, the Feishu card and RSS metadata, are Chinese only; original source titles and text may stay in their original language (especially with `--no-ai` or AI fallback).
- Source page or API changes may temporarily leave a source empty; the console log states why (see below).
- As of 2026-09-29 a16z and First Round Review feeds still return 404 and are disabled in config. Anthropic now uses its official news HTML list. Google DeepMind and Google Research RSS feeds were verified and added. Y Combinator and VentureBeat update infrequently and may log a stale warning.
- Product Hunt: prefer the official API when you have a token; the token path was not tested with a real token in this round. The public-page fallback depends on the current homepage markup and can be blocked by bot challenges; it provides no launch time. The API query orders by votes without a date filter, so whether it returns today's launches has not been verified.
- Reddit RSS is often rate limited (HTTP 429). Long `Retry-After` values are skipped rather than waited out, so some communities may be missing from a run.
- The freshness window relies on source timestamps; date-only pages such as Anthropic count as UTC midnight, and chart sources without publish times (GitHub Trending, HF trending models) are not subject to it.
- RSS feeds, HN search and Hugging Face endpoints added on 2026-10-02 could not be fetched live from the development sandbox and are covered by offline parsing tests only; check the first run's log or `logs/run-*.json` and set broken feeds to `enabled: False`.
- Full-text enrichment reads static HTML only (no JavaScript); when a page cannot be read the source description is used. It makes one request per candidate to the original site.
- Results from a local network do not guarantee the same behavior on GitHub Actions runners.
- Push memory relies on the GitHub Actions cache: a cache unused for 7 days is evicted, and after eviction or manual deletion one run proceeds without memory. Whether a same-event item is a repeat or a follow-up is a model judgement and can be wrong; each candidate's `novelty` is recorded in `logs/run-*.json`.

## 🧪 Tests

Offline regression tests make no network requests, do not read `.env` and do not call any LLM:

```bash
venv/bin/python -m unittest discover -s tests -t .
```

`test_reddit.py` in the repository root is a manual live connectivity script and is not part of this suite.

## 🛠️ Tech stack

- **Python 3.11+**
- **LLM APIs**: DeepSeek / OpenAI / Anthropic
- **feedparser** for RSS parsing
- **GitHub Actions** for scheduling

## 📝 License

MIT License

Note: the repository does not yet include a standalone LICENSE file.

## Adding and probing sources

See [data source adapters and AIHOT study](docs/data-sources.md) for RSS, HTML selectors, JSON field mapping, limitations and the implementation rationale. RSS feeds now sample each source in turn (newest first within each feed) to prevent one busy feed from filling the shared limit.

```bash
venv/bin/python probe_sources.py web_list --name Anthropic --limit 3
venv/bin/python probe_sources.py rss --name 'Google DeepMind' --limit 3
venv/bin/python probe_sources.py hn_search --limit 5
venv/bin/python probe_sources.py huggingface --limit 5 --body   # --body also tries the article excerpt
```

This probe does not load `.env`, call an AI model, push messages or write output feeds. `JSON_SOURCES` is empty by default.
