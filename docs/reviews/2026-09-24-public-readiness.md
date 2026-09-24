# Public readiness review

Date: 2026-09-24
Scope: local repository review, onboarding, English support, pipeline correctness.
Reviewer: Codex. Any subsequent implementation code is to be written by Claude Code and reviewed by Codex, per user request.

## Findings

1. **High: delivery failure is reported as success.** `main.py:209` ignores the boolean from `push_to_feishu` and returns zero at line 214. An offline mocked run with valid selected content and failed delivery returned zero. Distinguish intentionally skipped delivery from failure of a configured destination.
2. **High: digest claims exceed source evidence.** README promises deep reading, but batch scoring receives only the first 200 characters of the description (`ai_filter.py:180`); Hacker News descriptions are empty. Prompts request detailed summaries with technical facts. No article-body retrieval exists. Describe the actual capability and require summaries to stay within supplied facts; do not force detail when evidence is missing.
3. **Medium: model output is insufficiently validated.** `ai_filter.py:197-198` accepts negative indexes; index -1 was reproduced assigning a title and score to the last item. An empty JSON array silently leaves all items at zero. Validate response shape, integer indexes, bounds, uniqueness, coverage, finite scores within range, string fields, and categories. Retry only invalid or missing entries with a bounded fallback.
4. **Medium: candidate selection biases sources before AI sees them.** Raw platform scores are combined with small quality bonuses, then truncated to 25 (`main.py:83`). A fixture with 20 GitHub items, 5 HN items and 1 ArXiv item excluded the paper. Later GitHub caps cannot recover it. Consider per-source candidate allocation and apply caps before final top-N selection so eligible runners-up can fill vacancies.
5. **Medium: unstable RSS identifiers.** RSS and ArXiv fetchers use process-randomized Python `hash()` (`fetchers/rss_feeds.py:79`, `fetchers/arxiv.py:99`), which flows into RSS GUIDs. Two independent processes produced different identifiers for the same URL. Product Hunt page fallback also uses list position as its ID. Use source-native IDs or deterministic URL-derived identifiers and verify across processes.
6. **Medium: onboarding diverges from implementation.** README says 09:30 Beijing time; checked-in cron corresponds to 06:30. README claims AIHOT needs a key, while its fetcher does not use one. Workflow runs with `--no-rss`, has no Pages deployment, and uploads a `logs/` directory that the application does not create. README clone URL is a placeholder. Alternate provider setup needs provider-specific key names and `AI_PROVIDER`. Clarify that dry-run skips delivery but still calls AI unless combined with `--no-ai`.
7. **English support requires separate decisions.** There is no English README. Runtime prompts, categories, Feishu card labels, and RSS language are Chinese. An English README should explicitly state that current generated summaries are Chinese. Runtime English support should preserve Chinese defaults, use stable internal category identifiers, localize output labels and RSS metadata, and define behavior when AI translation is disabled.
8. **Repository maintenance gaps.** README states MIT, but no tracked LICENSE file exists. The sole test script is a live Reddit connectivity probe executed at import time, rather than deterministic regression tests. Add targeted offline tests for the defects above and a short contribution guide after implementation scope is agreed.

## Suggested order

1. English README plus Chinese corrections and reciprocal links; accurately document current behavior and optional Feishu delivery. Mark example digests as illustrative. Do not modify workflows merely to match existing documentation.
2. Delivery failure propagation, validated AI responses, stable RSS IDs, and regression tests, implemented by Claude Code and independently reviewed.
3. Optional Chinese/English runtime output and source balancing, each with an explicit behavior decision before implementation.
4. Improve operational feedback: source success/empty/failure counts, bounded network waits and retries, and explicit configuration errors before fetching.

## Verification and limits

- Initial tracked working tree was clean; no project-specific AGENTS.md or CLAUDE.md was present in the file inventory.
- Parsed all root and fetcher Python source files with `ast.parse`; passed.
- Reproduced failed-delivery exit status, negative model index, empty model response, unstable URL hash, and source preselection exclusion with offline Python fixtures/mocks.
- One hash verification command initially had a parenthesis typo; corrected and rerun successfully.
- No real LLM calls, messages, deployment, dependency installation, or changes to application code, secrets or CI/CD were made.
- Source endpoints and live model availability were not tested. These findings describe checked-in behavior, not current external service health.
- English documentation versus runtime localization scope was asked asynchronously and remains pending at the time of this record.

## Implementation acceptance criteria

- Both README languages agree with the actual CLI, environment configuration and workflow; local links resolve.
- Configured delivery failure produces a nonzero process exit; intentionally disabled delivery succeeds.
- Invalid model indexes never alter unrelated entries; missing results are explicit and bounded fallback is tested.
- A fixed article retains the same GUID across fresh processes; different articles have different IDs.
- If runtime English is selected: prompts, titles/summaries, card headings, categories and RSS metadata consistently follow the language; default Chinese behavior remains covered.

Workflow changes, publishing, commits and pushes require the user's separate authorization under the supplied project rules.
