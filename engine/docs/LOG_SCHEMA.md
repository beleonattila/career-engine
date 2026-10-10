# Search telemetry — schema

Purpose: make **recall** measurable without knowing how many matching posts exist on the internet.

The trick: we never need the true total. When a run finds a post that was already live during an
earlier run, that earlier run *missed* it — and the log holds enough context to say **why**. Late
discoveries are the ground truth signal.

```
user/workspace/logs/search_runs.jsonl     append-only, one JSON object per /search-positions run
user/workspace/logs/analysis/             miss-attribution reports written by analyze_misses.py
user/workspace/logs/ats_sweep/<run_id>.tsv  that run's ATS sweep output, archived by log_run.py
```

`log_run.py` copies `ats_sweep_latest.tsv` to `logs/ats_sweep/<run_id>.tsv` when it appends a run that
reached `ats_sweep`, provided the TSV was written within the run (3 h before `started` to 30 min after
`ended`); otherwise it warns and archives nothing. Since 2026-10-10; the 10-01, 10-05 and 10-10 runs
were backfilled from the user repo's history. It is what lets a sweep miss be split into "the board
did not have it" and "the sweep returned it and triage hid it".

---

## Why `screened` is mandatory

Log every candidate that was **looked at and rejected**, not only what was collected.

Without it, these two cases are indistinguishable in the log:

| What happened | Correct fix |
|---|---|
| The run never reached the channel carrying the post | reach that channel |
| The run saw the post and the gate rejected it | recalibrate the gate |

They look identical if only collections are recorded, and they have opposite remedies. A log
without `screened` cannot attribute a miss.

---

## Run record

One object per run, appended to `search_runs.jsonl`:

```json
{
  "run_id": "2026-07-30T1405",
  "started": "2026-07-30T14:05:00Z",
  "ended":   "2026-07-30T14:31:00Z",
  "mode": "fast",
  "age_window_days": 21,
  "model": "sonnet",
  "effort": "medium",
  "duration_min": 26,

  "channels": [
    {"key": "ats_sweep",  "status": "reached", "boards": 36, "postings_seen": 9049},
    {"key": "linkedin",   "status": "reached",
     "geos": ["United Kingdom", "European Union", "Denmark"],
     "queries": ["protein design", "enzyme engineering"],
     "hits": 121, "shortlisted": 14, "pages": 11,
     "short_pages": [{"query": "enzyme engineering", "geo": "Denmark", "pages": 1,
                      "reason": "no_shortlist"}]},
    {"key": "danish_boards",     "status": "skipped", "reason": "budget"},
    {"key": "euraxess",          "status": "skipped", "reason": "budget"},
    {"key": "company_rotation",  "status": "partial", "checked": ["affinityai", "ai-proteins"]},
    {"key": "research_groups",   "status": "partial", "checked": ["fleishman-lab-weizmann"]}
  ],

  "screened": [
    {"org": "ellison-gbi", "role": "bioinformatician", "posted": "2026-07-20",
     "country": "GB", "channel": "linkedin", "verdict": "skip", "reason": "gate3d"}
  ],

  "collected": [
    {"org": "latent-labs", "role": "machine-learning-scientist",
     "url": "https://...", "posted": "2026-06-29", "country": "GB",
     "channel": "ats_sweep", "tier": "T1", "gate3": "b"}
  ],

  "notes": "free text"
}
```

### Field rules

- `started` / `ended` — ISO-8601, both **required**. `ended` is what makes runtime measurable:
  a channel that came up empty after 5 minutes and one that came up empty after 40 are not the
  same evidence. `log_run.py` derives `duration_min` from the pair and stamps it on the record —
  do not write `duration_min` by hand.
- `model` — `haiku` · `sonnet` · `opus` · `fable`, lowercase, **required**.
- `effort` — `low` · `medium` · `high` · `xhigh` · `max` · `ultracode`, **required**, in ascending
  order (`ultracode` is a distinct tier above `max`, not a synonym for it — multi-agent
  orchestration via the Workflow tool, not just a higher single-agent reasoning setting). Model and
  effort are separate axes: capability buys judgment, effort buys care, and a run's yield is only
  comparable against runs made at the same setting. `python engine/tools/log_run.py --stats` reports
  collected/run, screened/run and min/run grouped by `model/effort/mode` — that table is the
  payoff, and it is only readable if the vocabulary above is used exactly.
- `channels[].key` — a **closed vocabulary**: `ats_sweep` · `linkedin` · `danish_boards` ·
  `nordic_boards` · `euraxess` · `phd_portals` · `company_rotation` · `research_groups`.
  Free text made "which channel got starved" uncomputable — a typo silently becomes a ninth
  channel that has never been reached. Add a genuinely new source to `CHANNELS` in `log_run.py`
  rather than inventing a key at write time.
- `channels[].status` — `reached` · `partial` · `skipped` · `failed`. **`skipped` is not `reached`
  with no results.** A channel that was never opened must never be logged as having found nothing.
- `channels[].geos` / `queries` — required for `linkedin`. Without them a miss cannot be separated
  into "wrong country" vs "right country, source didn't return it".
- `channels[].hits` / `shortlisted` — required for `linkedin`, both integers, `shortlisted <= hits`.
  This is the **triage step**, and it was the last unmeasured stage in the funnel. Measured
  2026-08-08: 2169 logged hits became 141 screened-or-collected candidates (6.5%), and how that
  happened was recorded nowhere. Without it, genuine `SOURCE_INCOMPLETE` — the largest miss
  bucket at 35% — is indistinguishable from "the run skimmed past the row", which is the exact
  ambiguity `screened` exists to remove, one level further up.
- `channels[].pages` / `short_pages` — `pages` is **required** for `linkedin` (since 2026-10-10): the
  number of guest-endpoint pages actually fetched. The rule is three pages per query × country
  (`search-positions-common.md` §Group 1), so a run owes `len(queries) × len(geos) × 3`. Every
  query × country that read fewer gets one `short_pages` entry — `query`, `geo`, `pages` read
  (0–2) and a `reason`: `exhausted` (the last page had < 10 cards) · `no_shortlist` (the last page
  shortlisted nothing) · `not_run` (the query was not issued in that country; never in a required
  one). `log_run.py` warns when `pages` plus the excused pages fall short of what is owed. Without
  this, a run that read page 1 everywhere logged the same as one that read all three: on
  2026-10-10 the career track read 41 of 90 pages and only a free-text note said so.
- `posted` — the posting's own publish date, `YYYY-MM-DD`, or `null` if genuinely unknown.
  **This is the load-bearing field.** With no posting date, lag is uncomputable and the record
  contributes nothing to recall measurement.
- `verdict` — `skip` or `collect`; `reason` uses stable codes (`gate0`, `gate2`, `gate3d`,
  `dedup`, `expired`, `geo`, `unverifiable`) so they aggregate.
- `method_lane` — **skill track only, optional** (since 2026-10-01):
  `{"opened": N, "sightings": N, "collected": N}` — `M`/`Mb` rows opened, ads with a YES build
  signal (each also logged in `user/workspace/logs/method_sightings.tsv`), and collections that
  came through the lane rather than the ≥2-competency rule. Not validated yet; it is how the lane
  will be judged (`engine/skills/search-positions-skill.md` §Report).

**Records written before 2026-08-07** predate the `effort` / `ended` requirements: all 13 carry a
`model`, none carry an `effort`, and the first six have no `ended`. They are left as written — the
log is append-only and the effort actually used is not recoverable — so they show up as `?` in the
`--stats` grouping and drop out of the min/run column.

**Records written before 2026-10-10** carry no `pages`; `--stats` leaves them out of the paging line
rather than counting them as short.

**Records written before 2026-08-09** predate `channels[].shortlisted`, so all 16 would fail
validation today. That is expected and harmless: validation runs only on a record being appended,
never on history. The same thing happened when `effort` and `ended` were introduced. The LinkedIn
funnel line in `--stats` is computed only over records that carry the field, so it reports
"still unmeasured" until real runs accumulate rather than averaging over a hole.

---

## Reading the log for the next run's plan

Three queries turn the log from a record into an instruction. Run them **before** allocating a
run's budget, not after:

```bash
python engine/tools/log_run.py --starved            # channels not reached in the last 3 runs
python engine/tools/log_run.py --next-queries 4     # least-used LinkedIn keywords
python engine/tools/log_run.py --stats              # includes the deep-pass overdue flag
```

- **`--starved`** exists because "rotate which category is sacrificed" was advisory and therefore
  never happened. Over 16 runs `nordic_boards` was absent from 14 and `phd_portals` from 11 —
  while PhD roles carry the **highest median fit score in the vault (70 vs 52–63)** and hold 12 of
  its 23 strong leads. The most-starved channel was serving the highest-yielding category.
- **`--next-queries`** ranks `QUERY_POOL` (the user's `query_pool` in `user/profile/search_terms.toml`) by how many runs have covered each term. `protein design`
  ran in 15 of 16 runs; 10 of 27 pool entries have never run at all. `QUERY_GAP` is 13.8% of
  attributed misses and this is the whole fix.
- The **deep-pass flag** fires when no `mode: deep` run is logged, or the last one is over 30 days
  old. As of 2026-08-09 it reads *0 of 16 runs — never run*.

### What `--stats` reports about yield (added 2026-08-09)

Three additions, all computed from data already in the vault — nothing new needs logging.

- **`new/run` replaces `coll/run`.** A lead re-collected under a slug variant is not yield.
  `analyze_misses.py` had excluded these from misses since 2026-08-08 while `--stats` still counted
  them as finds, so the two reports disagreed about the same three leads. Both now use
  `dedup_check.lead_key`, which is where lead identity lives so that the tool that *prevents*
  duplicates, the one that *measures* recall and the one that *reports* yield cannot drift apart.
  The `redup` column shows what was withheld.
- **`strong/run` — collection quality, not count.** Every net-new lead is joined to the record it
  became in `user/workspace/positions/` or `user/workspace/organizations/`, and counted strong when `/inbox` gave it a `career_fit` ≥ `thresholds.on_direction` (`user/settings.toml`). Without
  this a config collecting three weak leads outranks one collecting a single strong one. Each vault
  record is credited **once**, on first collection, so a centre that arrives twice under two names
  is not counted twice.
- **`channel → what its leads became`** — new · strong · CV · sent · unmatched, per channel. This is
  the conversion view: the stated bottleneck is applications, not discovery, and nothing previously
  recorded which channel feeds them. `unmatched` means no record anywhere carries that org+role or
  URL — a genuinely lost collection, and it should stay near zero.

The join is deliberately looser than `dedup_check.match`: it accepts role-slug drift (token-subset,
because the drift lands mid-slug — `...-design-gpcrs` vs `...-design-metabolic-gpcrs`) and bare
employer matches against `user/workspace/organizations/`. The risks are opposite — a wrong match here mis-attributes a
row in a report, whereas there it silently drops a real lead at collection time.

**Also reported: `screening rejections by reason`.** The `reason` codes were logged and read for
`GATED_OUT` attribution but never aggregated, so gate calibration was invisible. First run of it
(243 rejections) shows `dedup` 35.4% · `gate1` 13.6% · `gate3d` 11.9% · `expired` 10.3% —
i.e. **a third of all screening effort is spent recognising leads the vault already has.**

---

## Miss-cause taxonomy

`analyze_misses.py` assigns these mechanically. For a lead posted `P`, found at `F`, via channel
`C`, and any earlier run `R` with `P <= R.started < F`:

| Code | Test | Fix it points at |
|---|---|---|
| `NOT_YET_POSTED` | `P > R.started` | not a miss — excluded |
| `GATED_OUT` | lead appears in `R.screened` | gate calibration — the run *saw* it |
| `CHANNEL_NOT_RUN` | `C` absent from `R.channels` | source coverage |
| `CHANNEL_SKIPPED` | `C` present with status `skipped` | run budget / ordering |
| `CHANNEL_FAILED` | `C` present with status `failed` | robustness, retries |
| `GEO_GAP` | `C` is linkedin and lead's country not in `R.geos` | geography loop |
| `QUERY_GAP` | geo covered, but no logged query matches the lead's terms | keyword rotation |
| `AGE_EXCLUDED` | `R.mode == fast` and `R.started - P > R.age_window_days`; never for `ats_sweep`, which has no age filter | window / deep-pass cadence |
| `UNTIERED` | `C` is `ats_sweep` and the lead is in `R`'s archived sweep output as tier `-` | **triage, not the source** — the sweep returned it and did not print it |
| `UNSCREENED` | `C` is `ats_sweep` and the lead is in `R`'s sweep output with a printed tier, but not in `R.screened` | the run skimmed past a row it was shown |
| `SOURCE_INCOMPLETE` | everything above covered, still missed | **the source is not an enumeration** — don't trust it alone |

`SOURCE_INCOMPLETE` is the residual bucket and the most important one to watch: it is what
LinkedIn's ranked-subset behaviour looks like in aggregate. A rising share there means no amount
of query or geography tuning will help, and the channel needs replacing rather than tuning.

For `ats_sweep` it is the wrong reading whenever that run's sweep output is archived: the sweep
enumerates every board in full, so a lead in its output was *returned*, and the miss is `UNTIERED`
or `UNSCREENED`. Runs before the archive (all of them up to 2026-10-01) still fall to
`SOURCE_INCOMPLETE` for want of evidence. Measured 2026-10-10: in the six archived runs every sweep
miss was `UNTIERED` (three Adaptyv postings untiered in each sweep), and none was a board gap.

---

## Reading the output

The aggregate cause histogram is the deliverable. "62% of misses were `GEO_GAP`" is an
instruction; "we missed 8 things" is not.

Interpretation guide:

- Lots of `CHANNEL_SKIPPED` → the run budget is the bottleneck, not the method.
- Lots of `GATED_OUT` → precision was bought at the cost of recall; re-read the Gate 3 buckets.
- Lots of `SOURCE_INCOMPLETE` → stop tuning that source; add an independent one.
- Lots of `UNTIERED` → the sweep's tier rules hide relevant rows; fix the tiering, not the source.
- `AGE_EXCLUDED` above zero → an age filter has crept back in somewhere.

## Related

`log_run.py` (validate + append) · `analyze_misses.py` (attribution) ·
`engine/skills/search-positions.md` step 9
