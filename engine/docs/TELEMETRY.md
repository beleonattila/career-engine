# Measuring the Search (telemetry)

*Moved from `engine/docs/TELEMETRY.md` on migration; wording unchanged.*

We cannot know how many matching posts exist online, so recall cannot be measured directly — and
it does not need to be. **When a run finds a post that was already live during an earlier run,
that earlier run missed it**, and the telemetry says why. Late discoveries are the ground truth.

- Every `/search-positions` run appends a record to `user/workspace/logs/search_runs.jsonl` (schema and
  miss-cause taxonomy in `engine/docs/LOG_SCHEMA.md`). Logging is mandatory, including for runs that find
  nothing — a zero-find run records which sources were covered and came up empty.
- **Rejections are logged, not just collections.** Without the `screened` array, "never reached
  that channel" and "saw it and the gate rejected it" are indistinguishable, and they have
  opposite fixes.
- `POSTED:` in each collected `.txt` is load-bearing: `FOUND − POSTED` is the lag, and lag is how
  a miss is detected at all.
- `python engine/tools/analyze_misses.py` does the deterministic attribution; feed `--json` to Opus for the
  reasoning pass and skill recommendations. The **cause histogram** is the deliverable —
  "62% GEO_GAP" is an instruction, "we missed 8 things" is not.
- **Act on the strong-lead histogram, not the headline one.** Since 2026-10-01 the script joins each
  lead to its record's `career_fit` and prints a second histogram over leads at 75+ (`--min-fit N`
  restricts the whole report). The two disagree: the headline is dominated by low-value roles
  (`engine/docs/decisions.md` §Recall on strong leads).
- **Judge a fix on the runs after it, not on the cumulative log.** `--since <date or timestamp>`
  counts only the misses made by runs started then or later; the cumulative histogram stays
  dominated by runs that predate every fix. A run cannot show a miss until a later run finds
  something, so the newest runs are reported as *not yet testable*.

**Current attribution — 48 runs, 573 miss-events, measured 2026-10-01.** Median lag **13 days**,
max 215 (n=66). `SOURCE_INCOMPLETE` 29.3% · `AGE_EXCLUDED` 21.6% · `QUERY_GAP` 21.6% ·
`CHANNEL_SKIPPED` 12.9% · `CHANNEL_NOT_RUN` 5.6% · `GATED_OUT` 4.5% · `GEO_GAP` 4.4%.
6 redundant collections excluded (a lead re-collected under a different slug is a dedup failure,
not a miss; they are reported separately).

Against 2026-08-09 (16 runs, 94 miss-events: `SOURCE_INCOMPLETE` 35.1% · `CHANNEL_SKIPPED` 23.4% ·
`QUERY_GAP` 13.8% · `AGE_EXCLUDED` 12.8% · `GEO_GAP` 12.8% · `GATED_OUT` 2.1%), and the reconstructed
2026-07-29/30 baseline before it (`CHANNEL_SKIPPED` 46% · `AGE_EXCLUDED` 29% · `SOURCE_INCOMPLETE` 11%):
- **Coverage is fixed.** `CHANNEL_SKIPPED` has roughly halved again and `GEO_GAP` fell to a third.
- **`AGE_EXCLUDED` rose, and it is by design, not a filter creeping back.** Every miss since
  August carries the detail *"22–58d old vs 21d window"*: the fast pass's LinkedIn search uses
  `f_TPR=r1814400` (21 days, `search-positions-common.md`), and the deep pass drops it to sweep up
  exactly these. A miss detail citing any *other* window would be a regression.
- **`QUERY_GAP` rose, but on low-value roles.** All 124 events are LinkedIn, *"no logged query
  matched the role wording"*, and 21 of the 23 leads behind them are skill-track data-engineering
  and bioinformatics titles (EMBL-EBI, SandboxAQ, ZS, Our Future Health) that the skill track only
  began finding in September. The on-direction ones (TU Eindhoven de novo PhD, Cranfield enzyme,
  DTU enzyme PhD) are 2–4 events each. More design queries would not move this much.
- **`SOURCE_INCOMPLETE` is the remaining lever.** Detail *"was reached and covered, yet did not
  return it"*: `ats_sweep` 66 and `linkedin` 48 of the post-August events. Neither listing is an
  exhaustive enumeration.

Standing state as of 2026-10-01 (`python engine/tools/log_run.py --stats`):
- **Deep passes are running** — 10 of 48, the last 7 days ago (was 0 of 16).
- **Starved channels** (not reached in the last 3 runs): `nordic_boards` only (was `euraxess`,
  `nordic_boards`, `phd_portals`). But `phd_portals` is still skipped or failed in 22 of 48 runs
  while it yields the best strong-lead rate of any channel (3 strong of 6 new).
- **Yield by config** (new / strong / screened per run): `sonnet/medium/fast` 22 runs
  2.0 / 0.4 / 16.8 · `sonnet/medium/deep` 9 runs 3.4 / 1.2 / 37.1 · `opus/high/fast` 1 run
  3.0 / 1.0 / 30.0. **A deep pass finds ~3× the strong leads of a fast one**; Opus still has too
  few runs to judge model choice (see *Model and effort* in `engine/skills/search-positions-common.md`,
  the data: `engine/docs/decisions.md`).
- **Channels → outcomes** (net-new / strong): `linkedin` 62 / 19 · `ats_sweep` 21 / 5 (the only
  channel with a sent application) · `research_groups` 8 / 2 · `phd_portals` 6 / 3 ·
  `danish_boards` 4 / 2 · `company_rotation` 3 / 2 · `nordic_boards` 1 / 0. LinkedIn funnel:
  12,783 hits → 358 shortlisted (2.8%) over 32 runs.
- **Screening rejections** (981): `dedup` 29.6% · `expired` 14.5% · `unverifiable` 11.3% ·
  `gate1` 10.1% · `geo` 5.7% — dedup doing its job is the single largest filter.
