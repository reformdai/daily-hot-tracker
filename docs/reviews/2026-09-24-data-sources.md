# External data source audit — 2026-09-24

Scope: anonymous read-only probes from the host network, without loading .env or using tokens. No source implementation changes. A snapshot is not an uptime guarantee; GitHub Actions uses a different network. Reddit probes were concurrent and this may affect rate limiting.

## Live observations

| Source | Observation |
| --- | --- |
| Hacker News | Topstories API 200, 500 IDs |
| GitHub Trending | 200, current selector matches 17 repository rows |
| Product Hunt public fallback | Homepage 200, existing post-item selector matches zero rows; authenticated API not tested |
| AIHOT | 200, populated items and expected fields; requested limit=3 but response contains 50, local slicing still limits results |
| ArXiv | HTTP redirected to HTTPS; both probes 200, three Atom entries |
| TechCrunch | 200, 20 entries; first published September 24 |
| Hugging Face | 200, 867 entries; first published September 23 |
| The Verge | 200, 10 entries; first updated September 23 |
| MIT Tech Review | 200, 10 entries; first published September 23 |
| Y Combinator | 200, 15 entries; first published June 16; freshness needs attention |
| VentureBeat | 200, seven entries; first published August 27; freshness needs attention |
| a16z configured /feed/ | 404; homepage 200 but no RSS discovery link found |
| First Round configured /feed.xml | 404; /rss/ also 404. A glossary RSS link exists but is not an equivalent editorial source |
| Anthropic configured /feed.xml | 404; news page 200 but no RSS discovery link found |
| OpenAI configured /blog/rss/ | 403 on this network |
| OpenAI /news/rss.xml | 200, 1229 entries; first published September 23; verified replacement candidate |
| Reddit | MachineLearning 200/25 entries; five other configured subreddits returned 429. Do not treat temporary rate limiting as permanent removal |

## Confirmed integration issues

- Product Hunt HTML fallback silently yields no data with the current selector. Official API requires a token (https://api.producthunt.com/v2/docs); that authenticated path remains unverified here.
- AIHOT categories observed include ai-models and ai-products, absent from CATEGORY_MAP. They fall back to industry in the fetcher; the later LLM can reclassify, so this does not prove every final digest is miscategorized. API pagination/limit semantics need documentation verification before claiming parameter support.
- RSS and Reddit delegate URL fetching to feedparser without an explicit timeout, status handling or bounded retries. Failed parsing/HTTP errors can look like an empty feed.
- Reddit HTML description cleanup is a no-op; batch LLM input can be mostly markup. Atom updated timestamps are not used. With six subreddits each contributing five entries, slicing the first twenty excludes the last two when all are full.
- Fetchers mix UTC-naive and local-naive timestamps; stripping timezone offsets does not normalize instants. Main pipeline also lacks a hard content-age cutoff, so old items remain eligible.
- Broad exception-to-empty handling obscures distinctions between unavailable sources, changed formats and genuinely empty results.

## Recommended next implementation batch (not executed)

1. Switch OpenAI to the verified current RSS URL; flag/disable invalid feeds explicitly until equivalent official feeds are verified.
2. Add per-source status, item count, latest date, explicit network timeouts and bounded 429/5xx handling.
3. Fix AIHOT category aliases and Reddit HTML/date parsing; cover with captured synthetic fixtures and offline tests.
4. Make Product Hunt token-based operation the dependable documented path; repair HTML fallback only against verified page structure.
5. Decide freshness window and source allocation separately because these affect which stories are selected.

## README follow-up

Claude Code made README.md English, retained Chinese in README.zh-CN.md, and converted README.en.md to a compatibility entry. Codex verified local links and git diff --check. No commit or push.
