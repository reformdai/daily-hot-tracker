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

- **🔥 Seven sources**
  - **Hacker News** (title only; no description is available)
  - **GitHub Trending**
  - **Product Hunt** (official API with a token; otherwise only the "Top Products Launching Today" section of the public homepage)
  - **Reddit** (r/LocalLLaMA, r/MachineLearning, etc.)
  - **ArXiv** (cs.AI, cs.CL, cs.LG, cs.CV)
  - **AIHOT** (public API, no key needed)
  - **Tech blogs** via RSS: OpenAI, Anthropic, Hugging Face, a16z, TechCrunch and others

- **🧠 AI processing**
  - **Keyword prefilter**: after keyword filtering, the top 25 items by combined popularity are sent to the model
  - **Scoring**: 1–10; keeps the top 10 items scoring 6 or higher (at most 2 GitHub Trending items per day, each scoring 8 or higher)
  - **Summaries**: up to 140 Chinese characters, written from the source-provided title and description (the first 200 characters of the description in batch scoring). **Full article text is not fetched**; when a source provides little text (e.g. Hacker News), summaries are short
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

In `config.py`:

- `AI_MODELS`: model name and endpoint per provider
- `KEYWORDS`: prefilter keywords (AI, LLM, agent, RAG, etc.)
- `ENABLED_SOURCES` / `RSS_FEEDS` / `REDDIT_SUBREDDITS` / `ARXIV_CATEGORIES`: sources
- `TOP_N_ITEMS`: config default for items kept per day (10). Note: the CLI `--limit` option also defaults to 10 and always overrides this value at runtime, so editing `TOP_N_ITEMS` alone has no effect; use `python main.py --limit N` instead (for GitHub Actions, add it to the run command in the workflow)
- `MIN_SCORE_THRESHOLD`: minimum AI score (default 6)

## 🩺 Source diagnostics

RSS and Reddit requests use explicit timeouts (5 s connect, 20 s read). HTTP 429/500/502/503/504 and network errors are retried at most twice, honoring `Retry-After`, within a 10-second wait budget per URL; other statuses such as 403/404 are not retried. Each feed logs one line, for example:

```text
[RSS OpenAI Blog] 1229 entries, latest 2026-09-23 17:00 UTC
[RSS Y Combinator] 15 entries, latest 2026-06-16 16:00 UTC (stale: no update in 7+ days)
[RSS a16z] HTTP 404, not retrying; check https://a16z.com/feed/
[Reddit r/SaaS] HTTP 429, retry wait 60s exceeds 10s budget, skipping
[RSS Example] invalid feed (text/html): not an RSS/Atom document
[RSS Example] valid feed with 0 entries
```

Product Hunt logs API HTTP status and GraphQL error messages (a configured token echoed by the server is masked as `***`) and says whether the page fallback hit a bot challenge or changed markup. AIHOT logs unknown category names that fall back to 行业动态.

## ⚠️ Known limitations

- AI-generated titles and summaries, plus section names, the Feishu card and RSS metadata, are Chinese only; original source titles and text may stay in their original language (especially with `--no-ai` or AI fallback).
- Source page or API changes may temporarily leave a source empty; the console log states why (see below).
- As of 2026-09-24 the configured a16z, First Round Review and Anthropic feeds return 404 and no equivalent official feed has been verified. They stay enabled and log `HTTP 404, not retrying` each run. Y Combinator and VentureBeat update infrequently and may log a stale warning.
- Product Hunt: prefer the official API when you have a token; the token path was not tested with a real token in this round. The public-page fallback depends on the current homepage markup and can be blocked by bot challenges; it provides no launch time. The API query orders by votes without a date filter, so whether it returns today's launches has not been verified.
- Reddit RSS is often rate limited (HTTP 429). Long `Retry-After` values are skipped rather than waited out, so some communities may be missing from a run.
- Timestamps are not yet normalized across sources (some are UTC, some local time), and there is no hard freshness cutoff: old feed entries stay eligible and are only flagged in the log.
- Results from a local network do not guarantee the same behavior on GitHub Actions runners.
- The workflow's `Upload logs` step uploads a `logs/` directory that the program does not currently create, so the step may report that no files were found.

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
