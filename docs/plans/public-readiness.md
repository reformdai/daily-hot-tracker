# Public readiness first batch

## Scope and ownership

User authorized implementation on 2026-09-24. Claude Code is the sole implementation writer; Codex reviews and verifies after Claude finishes. No parallel writes.

## Tasks

- [x] Add English README (README.en.md), retain Chinese README with reciprocal links. Correct schedule to checked-in cron, clarify optional Feishu and provider-specific keys/provider selection, local RSS versus workflow --no-rss, dry-run AI costs, actual description-based summaries, real clone URL, illustrative examples. Do not promise free LLM usage or automatic Pages deployment.
- [x] Constrain summary prompts to supplied evidence, no invented facts when input is sparse.
- [x] Propagate configured Feishu delivery failure as nonzero exit while intentional no-push/dry-run and absent optional webhook remain nonfatal.
- [x] Validate batch and single AI output: JSON shape, unique integer (not boolean) in-range indexes, complete coverage or bounded per-item retry for missing/invalid items, finite 1–10 score, string fields, allowed categories. Preserve valid batch results. Keep existing Chinese API field compatibility. Correct category example.
- [x] Replace unstable hash/position IDs in RSS, ArXiv, Product Hunt page fallback and AIHOT fallback with stable source ID or deterministic URL-derived ID.
- [x] Add offline unittest regression tests for failure/skip behavior, malformed AI output, bounded fallback and stable IDs across processes; no new dependencies, real LLM calls, messages or network in tests.
- [x] Codex independent diff review, run tests, verify bilingual documentation links and clean diff formatting.

## Excluded this batch

Runtime English localization, source ranking changes, workflows/CI, .env or example env modifications, global config, dependency installs, deletion, commits/push/deployment. Do not add a license or assign a copyright holder without an explicit scope decision. No live main.py run (loads real .env). Tests must mock dotenv loading before importing main or otherwise isolate it.

## Acceptance

Docs reflect actual behavior. Failed configured delivery is visible via exit status; deliberate skips succeed. Invalid model data cannot corrupt unrelated items; fallback is bounded. Same article keeps the same identifier across fresh processes, distinct articles do not share positional IDs. Existing Chinese output is preserved. All targeted offline tests pass.

## Progress

Initial sandboxed Claude invocation could not access the existing login. Retried successfully in the host command line at the user’s request; no new login was needed. Claude implemented the code; Codex reviewed it.

2026-09-24 · Claude Code (run from local CLI after login): implemented tasks 1–6; awaiting Codex review (task 7). Nothing committed.

- Docs: README.md corrected (06:30 Beijing cron, optional Feishu, provider keys + `AI_PROVIDER`, local RSS vs workflow `--no-rss`, dry-run still calls AI, description-based summaries, real clone URL, illustrative preview, exit codes, known limitations, test command). README.en.md added with reciprocal links; states generated output is Chinese. Both READMEs keep the original "MIT License" statement and note that no standalone LICENSE file is included yet. Summary wording says prompts restrict the model to source info and output still needs verification (no absolute guarantee). `TOP_N_ITEMS` docs note it is always overridden by CLI `--limit` (default 10) and recommend `--limit`. Language note: AI-generated digest is Chinese; original source titles/text may stay in original language (`--no-ai` / fallback).
- `ai_filter.py`: both prompts forbid facts not in supplied title/source/description and allow short summaries when input is sparse; batch example category fixed to `产品发布`. New `_parse_json` / `_validate_result`: object shape, finite non-bool numeric score in 1–10, string `title_cn`/`summary`, category in `config.AI_CATEGORIES`. Batch: must be a JSON array; indexes must be non-bool ints in range; duplicated indexes are voided; valid entries are kept; each missing/invalid item is retried once via `score_single` (at most one extra call per item); failed retries score 0 and are filtered out.
- `main.py`: missing webhook returns success (skip); configured delivery failure returns exit 1; `--dry-run`/`--no-push` unchanged.
- IDs: `fetchers/base.stable_id` (sha256 prefix). RSS uses entry id or link; ArXiv uses atom id; Product Hunt page fallback uses URL; AIHOT keeps native id, else URL/title digest.
- Tests: `tests/` (20 unittest cases) with `requests` network guard, `dotenv.load_dotenv` patched before importing `main`, mocked LLM/Feishu/feedparser, cross-process ID check with PYTHONHASHSEED 1 vs 2. Run: `venv/bin/python -m unittest discover -s tests -t .` → OK.
- Not addressed (out of batch scope): source-balanced candidate selection (review finding 4), workflow `logs/` upload mismatch, license decision, runtime English output.

2026-09-24 · Codex final review: independently ran all 20 offline unittest cases successfully; reviewed application and test diffs; git diff --check and README relative-link validation passed. Requested and verified documentation corrections preserving the original MIT declaration, avoiding guaranteed factuality claims and explaining CLI limit precedence. No CI/env/auth changes, dependency installation, real LLM calls, delivery, commits or deployment. Runtime English and ranking changes remain outside this batch. Existing RSS subscribers may see older items once more when migrating from the old identifiers to stable IDs.

## Follow-up: English as default README

2026-09-24 · User requested the English README be shown by default (docs only). Claude Code:

- [x] Chinese content preserved verbatim as `README.zh-CN.md`; English content moved to `README.md`. Only the language-switch line changed in each.
- [x] Language links: `README.md` ↔ `README.zh-CN.md`.
- [x] `README.en.md` kept (deletion requires user confirmation) as a short English compatibility page linking to `README.md` and `README.zh-CN.md`; it no longer holds a second copy of the English body.
- No other in-repo README links needed updating; historical references in `WORKLOG.md` and `docs/reviews/` left as records. No code, CI, env, auth or global config changes; nothing committed.
