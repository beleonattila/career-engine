---
name: search-positions
cssclasses: [skill]
recommended_model: Sonnet medium — the orchestrator is cheap; the sub-agents do the work
description: >
  Collect open positions on BOTH tracks at once. Fans out to two sub-agents in parallel —
  search-positions-career (is this the work I want?) and search-positions-skill (could I get
  and do it?) — then reconciles their staging folders into the inbox. Trigger on
  /search-positions, "find jobs", "search for positions". Does NOT score; /inbox does that.
---

# search-positions

**Orchestrator.** This file spawns and reconciles; it does not search. The collecting is done by
two sub-agents that run **in parallel** and never see each other's context:

```
/search-positions ─┬─► search-positions-career.md ──► user/workspace/inbox/_staging/career/ ─┐
                   └─► search-positions-skill.md  ──► user/workspace/inbox/_staging/skill/  ─┤
                                                                              ▼
                                                        reconcile_staging.py --apply
                                                                              │
                                                                              ▼
                                                                    user/workspace/inbox/
```

Both tracks read [[search-common]] (geography, staging, `TRACK:`) and
[[search-positions-common]] (run modes, dedup, Gates 0/2/4, sources, telemetry). Each mode file
supplies only the steps that genuinely differ — the keyword pass and Gate 3.

**Optional argument:** `/search-positions skill` or `/search-positions career` runs one track
only. Bare `/search-positions` runs both, which is the default and the normal case.

---

## Workflow

### Step 1 — Pre-flight

```bash
python engine/tools/log_run.py --starved && python engine/tools/log_run.py --next-queries 4
```

Decides the run's budget and whether this must be a **deep pass**. State the mode you are
running (fast or deep) before spawning — both sub-agents must run the *same* mode, or the
telemetry cannot compare them.

Then confirm the staging folders are empty:

```bash
python engine/tools/reconcile_staging.py
```

If it reports leftover files from an interrupted run, reconcile them first (`--apply`) rather
than letting the next run adopt them — they would be attributed to the wrong run in the
telemetry.

### Step 2 — Spawn both sub-agents, in parallel

Issue **both Agent calls in a single message** so they run concurrently. Do not await one before
starting the other — serialising them throws away the only reason this is a fan-out.

Give each the same run mode, and tell it which track it is:

> **career agent** — "Read `engine/skills/search-positions-career.md` and follow it
> exactly. You are the CAREER track for this run. Run mode: {fast|deep}. Write collections only
> to `user/workspace/inbox/_staging/career/`. Report in the format the skill specifies."

> **skill agent** — "Read `engine/skills/search-positions-skill.md` and follow it
> exactly. You are the SKILL (employability) track for this run. Run mode: {fast|deep}. Write
> collections only to `user/workspace/inbox/_staging/skill/`. Report in the format the skill
> specifies."

**Wait for both to finish before Step 3.** Reconciling while one is still writing would drop
whatever it had not yet produced.

### Step 3 — Reconcile

```bash
python engine/tools/reconcile_staging.py            # inspect what collided
python engine/tools/reconcile_staging.py --apply    # stamp TRACK:, move into user/workspace/inbox/, empty staging
```

**Career wins every collision.** Overlap is expected and common — a protein-design role that
also names Snakemake passes both gates — so a long "dropped" list is healthy, not a bug.

Watch for the `[!] within-track duplicate` warning: that means one collector's own dedup missed
something, which is a bug in that mode file rather than an ordinary collision. Report it.

### Step 4 — Log the run

**Log one entry per sub-agent — two runs, not one merged row.**

```bash
python engine/tools/log_run.py career_run.json
python engine/tools/log_run.py skill_run.json
```

Each entry carries `track: career | skill` (required since 2026-08-18; `log_run.py` rejects a
record without it, and rejects `mixed` outright).

> ⚠️ **The first two-track run got this wrong and it cost the run's evidence.** It logged a
> single blended entry — 8 collected, 27 screened — with no way to tell which search did what.
> Worse, every skip was recorded with *career* gate labels (`gate3d`, `gate3f`, `gate3h`),
> because those were the only ones the schema knew; the skill track's competency-count
> vocabulary never reached the log at all. The yield telemetry is already unsettleable at
> n=1–3 per cell (see [[search-positions-common]] §Model and effort), and merging two different searches into one row
> makes it strictly worse. Two entries, always.

Record `model` and `effort` **honestly** in both. 13 of the first 16 runs are unlabelled and
answer nothing.

### Step 5 — Report

```
── Search: positions ────────────────────────────────────────────
mode: {fast|deep}   model: {…}   effort: {…}

career   collected N · screened N · skipped N (gate0 X · gate1 X · gate2 X · gate3 X · gate4 X · dedup X · geo X)
skill    collected N · screened N · skipped N (…)         competency spread: C1 x · C2 x · …

reconciled: N kept · N dropped (career won)
─────────────────────────────────────────────────────────────────
Run /inbox on Opus to score everything collected.
```

Then tell the user to run `/inbox`. **Do not run it yourself** — it is an Opus stage and the
model has to be switched deliberately.

---

## Notes

- **Neither track scores.** `domain_fit`, `skill_match` and `level_fit` are all `/inbox`'s job.
  A collector decides collect-or-skip and writes the raw ad text down.
- **Equal cadence.** Both tracks run every time, 2–3×/week fast plus a monthly deep pass. There
  is no volume cap: measured yield is ~2 collections per run, so a cap would almost never bind.
- **If one sub-agent fails**, reconcile the other's folder anyway — a half run is better than a
  lost one — and say clearly in the report which track did not complete.

---

## Related

[[search-common]] · [[search-positions-common]] · [[search-positions-career]] ·
[[search-positions-skill]] · [[inbox-eval]] (the THINK stage) · [[search-companies]] ·
[[search-groups]] (sibling orchestrators) · [[PIPELINE]]
