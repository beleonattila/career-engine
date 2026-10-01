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

**Current attribution — 16 runs, 94 miss-events, measured 2026-08-09.** Median lag **10 days**,
max 113 (n=23). `SOURCE_INCOMPLETE` 35.1% · `CHANNEL_SKIPPED` 23.4% · `QUERY_GAP` 13.8% ·
`AGE_EXCLUDED` 12.8% · `GEO_GAP` 12.8% · `GATED_OUT` 2.1%.

This supersedes the reconstructed 2026-07-29/30 baseline (`CHANNEL_SKIPPED` 46% · `AGE_EXCLUDED`
29% · `SOURCE_INCOMPLETE` 11%). Two things changed materially: `SOURCE_INCOMPLETE` is now the top
cause, and `CHANNEL_SKIPPED` has halved. `SOURCE_INCOMPLETE + QUERY_GAP + GEO_GAP` = **62%** of
misses — all three are fixed by which sources a run opens and which queries it issues, not by
model choice. `AGE_EXCLUDED` at 12.8% is attributable to runs predating the 2026-07-29 filter
removal; **any new one means an age filter has crept back in.**

Standing state as of 2026-08-09 (`python engine/tools/log_run.py --stats`):
- **Deep pass never run** — 0 of 16. The overdue flag is firing; the next run should be `mode: deep`.
- **Starved channels** (not reached in the last 3 runs): `euraxess` · `nordic_boards` ·
  `phd_portals`. The last is the costly one: PhD roles carry the highest median fit in the vault
  (70 vs 52–63) and hold 12 of its 23 strong leads.
- **10 of 27 rotation queries have never run** — `protein optimization`, `ML-guided design MLDE`,
  `biocatalysis engineering`, `protein structure prediction`, `BindCraft`, `ProteinMPNN` among them,
  while `protein design` ran in 15 of 16.
- **Model/effort is unmeasured, and `coll/run` cannot currently settle it.** `sonnet/medium` has 0
  runs and `opus/high` has 1, but the deeper problem is noise: within `sonnet/?` alone the per-run
  collections were `0,0,1,1,1,3,3,3,8`, a spread larger than any gap between configs. What *is*
  separable is that **screening volume tracks channel breadth** (8.3/run at ≤2 channels vs 30.2 at
  5–6) while **collections stay flat at ~2.0/run at every breadth** — 3.6× more looking, no more
  finding. See *Model and effort* in `engine/skills/search-positions-common.md` (the data: `engine/docs/decisions.md`).
- **Redundant collections are excluded from the miss counts** and reported separately —
  a lead re-collected under a different slug is a dedup failure, not a miss. Three were produced in
  one run on 2026-08-08; counting them as late discoveries had inflated the statistics.
