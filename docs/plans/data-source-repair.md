# Data source repair

## Goal and ownership

User requested fixes after the external-source audit. Claude Code is the sole code writer, Codex reviews and verifies. Preserve all existing uncommitted work. Use the host CLI, not the sandboxed Claude login.

## Scope

- Switch OpenAI RSS to the verified /news/rss.xml URL. Keep other source selections unchanged; document currently invalid feeds clearly.
- RSS and Reddit: fetch via requests with explicit timeouts, bounded retries for 429/5xx/connection failures; honor reasonable Retry-After, but if it exceeds a short total wait budget skip with a clear warning rather than hammering the service. Do not retry permanent 403/404. Feedparser parses downloaded bytes only. Distinguish HTTP/network failure, invalid feed, and valid empty feed in console diagnostics; report count/latest known timestamp and warn for feeds older than seven days, without filtering them out.
- Reddit: clean HTML with existing BeautifulSoup, read published/updated timestamps, round-robin merge communities so default truncation does not always discard the last communities. Do not introduce a new ranking model.
- AIHOT: add observed ai-models and ai-products category aliases. Preserve raw category. Do not invent pagination parameters or change API semantics.
- Product Hunt: repair HTML fallback against the public HTML captured in /tmp/daily-hot-tracker-producthunt.html if present. Prefer a narrow verified selector, preserve legacy layout compatibility and URL-based IDs, log empty/challenge/changed-page cases explicitly. Report GraphQL errors without leaking secrets. Do not use credentials or query authenticated endpoints during tests. Capture createdAt if safely supported.
- Add targeted offline fixtures/tests for network failures, timeout configuration, bounded retry, feed types/empty feeds, Reddit HTML/update fields/community fairness, AIHOT aliases, current Product Hunt markup and empty fallback. Existing tests must still pass without network or dotenv.
- Update English default README.md and README.zh-CN.md with accurate source limitations and diagnostic behavior.

## Constraints

No .env/auth/global/CI changes, no deletion, no dependency installs, no commit/push/deploy, no subagents, no real AI or delivery. Do not import main.py in live probes. No broad timezone migration or cross-source ranking overhaul in this batch; state remaining gaps. Keep helpers small and used by the affected sources, not a plugin framework. Existing 404 feeds may stay enabled but must emit actionable warnings, not silent empty results.

## Acceptance

Offline suite passes. Selected public endpoint probes demonstrate current Product Hunt parsing (if markup is available), corrected OpenAI RSS and AIHOT categories. HTTP failures are observable and retry counts/waits bounded. Reddit no longer sends HTML-heavy summaries or excludes later communities solely by concatenation order. Documentation links and diff formatting pass. Host network results do not imply GitHub Actions health.

## Progress

Evidence: docs/reviews/2026-09-24-data-sources.md.

2026-09-24 · Claude Code — implementation complete; Codex review and live verification completed below. Uncommitted.

- [x] OpenAI RSS → https://openai.com/news/rss.xml; config comment documents the 404 feeds (a16z, First Round, Anthropic) and slow feeds (YC, VentureBeat), all left enabled.
- [x] fetchers/base.py: `get_with_retry` (timeout (5, 20); 3 attempts for 429/5xx/network errors; Retry-After seconds or HTTP-date; 10 s total wait budget, otherwise skip; 403/404 not retried) and `fetch_feed` (feedparser parses downloaded bytes; logs HTTP/network failure, invalid feed, valid empty feed, count + latest UTC timestamp, stale warning after 7 days without filtering) and `entry_time` (published, else updated).
- [x] RSS and Reddit use `fetch_feed`. Reddit: BeautifulSoup text, drops the "submitted by" footer, uses updated timestamps, round-robin merge by rank before truncation. Reddit IDs unchanged.
- [x] AIHOT: `ai-models` → 模型发布, `ai-products` → 产品发布; raw category stays in `extra["aihot_category"]`; unknown categories logged once per request. API params unchanged.
- [x] Product Hunt page: only `[data-test="homepage-section-today"]`, links `a[href^="/products/"]` whose text has a rank prefix `N. Name` (skips ads/topic links and yesterday/last-week/last-month sections). Tagline = sibling span, topics, votes (`vote-button`), comments (other direct button), `extra["ph_rank"]`, URL-based `stable_id("ph_page", url)` with query stripped. Legacy post-item layout kept. Logs challenge (`Just a moment...`/`cf-chl`; `challenge-platform` is excluded because normal pages inject it), empty today section, and changed page. Parsing /tmp capture offline yields the 16 today items, ranks 1–16.
- [x] Product Hunt API: logs HTTP status and GraphQL error messages only (no token, no headers); `createdAt` → naive UTC `published_at`.
- [x] Tests: tests/test_data_sources.py (25 cases) + synthetic tests/fixtures/producthunt_homepage.html; test_stable_ids RSS mock now patches `fetch_feed`. `venv/bin/python -m unittest discover -s tests -t .` → 45 tests OK. `git diff --check` clean.
- [x] README.md (English) and README.zh-CN.md: new source diagnostics section, source limitations updated. README.en.md unchanged (compatibility entry).
- [x] Codex: independent review and live probes (Product Hunt page, OpenAI RSS, AIHOT); 45 tests passed on Codex's side.

2026-09-24 · Claude Code — review follow-up (two offline-reproduced issues). Uncommitted.

- [x] `fetch_feed` passes `resp.url or url` as content-location so relative feed links resolve against the final URL after HTTP redirects. Regression: real `requests.Response` with `url` = https://new.example/news/feed.xml, requested https://old.example/feed.xml, item link `article` → https://new.example/news/article (old code gave https://old.example/article).
- [x] Product Hunt API: `_redact` replaces a non-empty `self.token` with `***` before truncating to 300 chars; applied to GraphQL error messages and the generic `Exception` branch (exception type kept). Tests use synthetic `fake-token-for-tests` echoed in both branches.
- [x] README.md / README.zh-CN.md: token API described as preferred but not verified with a real token this round; retry wording now matches code (429/500/502/503/504 only; other statuses such as 403/404 not retried); token masking wording updated.
- [x] Offline suite 48 tests OK; `git diff --check` clean.

Remaining gaps (out of scope): timezone normalization across fetchers, freshness cutoff, Product Hunt API query has no date filter (unverified without token), no replacement for 404 feeds, main.py per-source summary unchanged.

2026-09-24 · Codex final verification: independently reran all 48 offline tests successfully after review fixes; reviewed redirect base URL and redact-before-truncate implementation; git diff --check and all README local links passed. Live host probes: Product Hunt returned 5 ranked products with nonempty descriptions and scores, OpenAI parsed 1229 feed entries and selected 3, AIHOT returned 20 items with correct ai-models/ai-products mapping. No actual LLM, Feishu, authenticated Product Hunt call, CI edit, commit or push. The three 404 feeds are diagnosed but not restored; Reddit rate limits remain external.
