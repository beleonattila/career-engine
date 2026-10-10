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

**Current attribution — 52 runs, 1,058 miss-events, measured 2026-10-10.** Median lag **9 days**,
max 229 (n=137). `SOURCE_INCOMPLETE` 40.8% · `CHANNEL_SKIPPED` 19.8% · `QUERY_GAP` 14.7% ·
`AGE_EXCLUDED` 13.3% · `CHANNEL_NOT_RUN` 4.1% · `GEO_GAP` 3.7% · `GATED_OUT` 2.6% · `UNTIERED` 1.1%.
Two attribution fixes on 2026-10-10 moved these: the ATS sweep is no longer charged with
`AGE_EXCLUDED` (it has no age filter; 104 events moved, mostly to `SOURCE_INCOMPLETE`), and a sweep
miss found in that run's archived sweep output is `UNTIERED` rather than `SOURCE_INCOMPLETE`.
13 redundant collections excluded. 6 are the two tracks of one run each logging the same lead and
2 are one track logging a lead twice (both Oxford, 10-05); `reconcile_staging.py` merges such twins
before the inbox (checked for Bayer on 10-10: one file reached it), so these 8 are a logging
artefact rather than dedup failures. The other 5 are genuine re-collections across runs.

**On strong leads (career_fit ≥ 75: 34 leads, 155 miss-events) — the histogram to act on:**
`SOURCE_INCOMPLETE` 36.1% · `CHANNEL_SKIPPED` 33.5% · `QUERY_GAP` 10.3% · `CHANNEL_NOT_RUN` 7.1% ·
`GEO_GAP` 7.1% · `AGE_EXCLUDED` 4.5% · `GATED_OUT` 1.3%. By channel: `SOURCE_INCOMPLETE` is
`linkedin` 21 · `danish_boards` 15 · `euraxess` 12 · `ats_sweep` 7 (all from runs before the sweep
archive, so unreadable as source gap vs triage); `CHANNEL_SKIPPED` is
`danish_boards` 23 · `euraxess` 19 · `phd_portals` 6 · `ats_sweep` 4 (the last from before the sweep
existed).

**After the 2026-10-01 fixes (`--since 2026-10-02`): 4 runs, 12 miss-events, none on a strong lead.**
Only the 10-05 deep pass (both tracks) is testable; the two 10-10 fast runs are not yet. The 12:
`UNTIERED` 6 (three Adaptyv postings, career_fit 20–30, below), `SOURCE_INCOMPLETE` 2 (`linkedin`),
`QUERY_GAP` 2, `CHANNEL_SKIPPED` 2 (`research_groups`, the run was cut off). One deep pass is too
little to call the fixes working, but nothing in it contradicts them.

**These numbers are not directly comparable with the 2026-10-01 snapshot** (48 runs, 573 events;
strong leads: `SOURCE_INCOMPLETE` 30% · `CHANNEL_SKIPPED` 18% · `QUERY_GAP` 18%). Until 2026-10-10
`analyze_misses.py` charged each track of a two-track run with missing what the other found; removing
that took 72 events out of today's total (1,130 → 1,058). Most of the growth since 10-01 is the 10-05
deep pass: it found long-lived leads, and each counts as a miss against every earlier run.

What the shape says:
- **`CHANNEL_SKIPPED` on strong leads is a pre-fix effect.** Its share rose from 18% to 34%, but
  the four strong leads behind the rise (Groningen ML-guided directed evolution PhD, Priora, Durham
  AI protein design PhD, Black Swans) were all missed by the two 2026-10-01 fast runs, which
  started before the fixes were committed and skipped `euraxess`, `danish_boards` and `phd_portals`
  for budget. The weekly deep pass that the fixes introduced caught all four four days later. Fast
  passes still skip those boards by design (`--starved` forces a channel back after three misses);
  the lever is the deep-pass cadence, not full coverage on every fast pass.
- **`AGE_EXCLUDED` is still by design.** All 92 events since August cite the fast pass's 21-day
  window: `linkedin` 80 (`f_TPR=r1814400`), `euraxess` 7, `phd_portals` 5. The deep pass drops it.
  A miss citing any *other* window would be a regression. On strong leads it is 4.5%.
- **`QUERY_GAP` is still mostly low-value roles.** All 155 events are LinkedIn, *"no logged query
  matched the role wording"*; on strong leads it is 16 events.
- **`SOURCE_INCOMPLETE` is the remaining lever,** led by LinkedIn on strong leads. The 2026-10-01
  three-page rule targets it, but neither 10-10 fast track followed it (the career track read 41 of
  90 pages); since 2026-10-10 runs log `pages` and `short_pages` and `log_run.py` warns on a
  shortfall. Judge the rule with `--since 2026-10-11` once later runs have tested those runs.
- **A sweep miss is a triage miss, not a source gap.** The 10-05 sweep did return the three Adaptyv
  postings the 10-10 run collected, as did every sweep since at least 10-01, with unchanged posting
  dates. They were tier `-`, which goes to the TSV but is not printed, and agents read only what is
  printed: *Software Engineer, Product* names a build seat but no scientist users, so `Mb` did not
  fire, and the display library role matches no career title. The 10-10 skill track reached them
  through Adaptyv's earlier method sightings. Each run's sweep output is now archived
  (`logs/ats_sweep/<run_id>.tsv`), so `analyze_misses.py` can tell `UNTIERED` (returned, not
  printed) and `UNSCREENED` (printed, skimmed past) from a real gap. In all six archived runs every
  sweep miss is `UNTIERED`; the 224 sweep `SOURCE_INCOMPLETE` events before them cannot be re-read.
  Tiering more rows (an `M?` tier for sighted employers) is an open decision
  (`engine/docs/decisions.md` §A sweep miss is a triage miss).

Standing state as of 2026-10-10 (`python engine/tools/log_run.py --stats`):
- **Deep passes:** 12 of 52 runs, the last 4 days ago; 2 of 12 did not reach `phd_portals`.
- **Starved channels** (not reached in the last 3 runs): none. Most often skipped or failed overall:
  `euraxess` 31 · `danish_boards` 27 · `phd_portals` 23 · `nordic_boards` 23 of 52 runs.
- **Required LinkedIn countries** skipped in 6 of the last 10 runs, all of them before the 2026-10-01
  fixes were committed; the four runs since covered all five.
- **Yield by config** (new / strong / screened per run): `sonnet/medium/fast` 24 runs
  2.8 / 0.5 / 19.2 · `sonnet/medium/deep` 9 runs 3.4 / 1.2 / 37.1 · `sonnet/max/deep` 2 runs
  25.0 / 3.5 / 59.0 · `opus/high/fast` 1 run 3.0 / 1.0 / 30.0. **A deep pass at medium finds ~2.4× the
  strong leads of a fast one.** The max-effort deep pass (10-05) is a backlog catch-up, not evidence
  for max effort; Opus still has too few runs to
  judge (*Model and effort* in `engine/skills/search-positions-common.md`).
- **Channels → outcomes** (net-new / strong): `linkedin` 106 / 24 · `ats_sweep` 24 / 5 ·
  `phd_portals` 14 / 4 · `research_groups` 9 / 2 · `euraxess` 9 / 2 · `danish_boards` 8 / 3 ·
  `nordic_boards` 4 / 0 · `company_rotation` 3 / 2. The often-skipped boards have the best strong
  rates per new lead (`danish_boards` 3 of 8, `phd_portals` 4 of 14). LinkedIn funnel: 16,669 hits →
  527 shortlisted (3.2%) over 36 runs.
- **Screening rejections** (1,192): `dedup` 30.3% · `expired` 13.0% · `gate1` 12.9% ·
  `unverifiable` 9.6% · `gate3` 6.5% · `gate3h` 6.0% · `gate4` 5.6% · `geo` 5.2%.
- **ATS sweep boards:** on 2026-10-10, 10x Genomics (Greenhouse → Kula) and Takeda (Workday →
  Radancy) moved platform and were dropped; Ordaos Bio's empty Workable board was verified genuine.
