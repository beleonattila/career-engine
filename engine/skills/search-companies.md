---
name: search-companies
cssclasses: [skill]
recommended_model: Sonnet (low–medium) — the orchestrator is cheap; the sub-agents do the work
description: >
  Build the company database on BOTH tracks at once. Fans out to two sub-agents in parallel —
  search-companies-career (does this employer do the work I want?) and search-companies-skill
  (could I be useful there?) — then reconciles their staging folders into the inbox. Trigger on
  /search-companies. Does NOT score; /inbox does that.
---

# search-companies

**Orchestrator.** Spawns and reconciles; does not search.

```
/search-companies ─┬─► search-companies-career.md ──► user/workspace/inbox/_staging/career/ ─┐
                   └─► search-companies-skill.md  ──► user/workspace/inbox/_staging/skill/  ─┤
                                                                              ▼
                                                        reconcile_staging.py --apply
                                                                              ▼
                                                                    user/workspace/inbox/
```

**Why two tracks matter here specifically.** The company database is what unsolicited
applications are sent from, so each profile has to answer two separate questions, and `/inbox`
now scores both: `career_fit` (is this the work) and `skill_match` (could I be useful there).
The career track finds the first kind, the skill track the second — including employers the
career track structurally cannot see, like a metagenomics-plus-imaging company that is a
perfectly good place to send an application.

**Optional argument:** `/search-companies skill` or `/search-companies career` runs one track
only. Bare `/search-companies` runs both.

---

## Workflow

### Step 1 — Confirm staging is clean

```bash
python engine/tools/reconcile_staging.py
```

Leftovers from an interrupted run must be reconciled (`--apply`) before spawning, not adopted by
this run.

### Step 2 — Spawn both sub-agents, in parallel

**Both Agent calls in a single message.** Do not await one before starting the other.

> **career agent** — "Read `engine/skills/search-companies-career.md` and follow it
> exactly. You are the CAREER track. Write collections only to
> `user/workspace/inbox/_staging/career/`. Report in the format the skill specifies."

> **skill agent** — "Read `engine/skills/search-companies-skill.md` and follow it exactly.
> You are the SKILL (employability) track. Write collections only to
> `user/workspace/inbox/_staging/skill/`. Report in the format the skill specifies."

Wait for both before Step 3.

### Step 3 — Reconcile

```bash
python engine/tools/reconcile_staging.py            # inspect
python engine/tools/reconcile_staging.py --apply    # stamp TRACK:, move into user/workspace/inbox/, empty staging
```

Career wins every collision. A company doing AI protein design *and* running large pipelines
will be found by both — that is expected.

### Step 4 — Report

```
── Search: companies ────────────────────────────────────────────
career   collected N · screened N · skipped N (geo X · terms X · dedup X)
skill    collected N · screened N · skipped N (…)   competency spread: C1 x · C2 x · …

reconciled: N kept · N dropped (career won)
─────────────────────────────────────────────────────────────────
Run /inbox on Opus to score everything collected.
```

Tell the user to run `/inbox`; do not run it yourself.

---

## Notes

- **`ats_sweep.py` is the cheapest surface for the skill track** — job ads state a stack plainly,
  so a company whose live postings name Nextflow and segmentation has evidenced C1 and C7 at zero
  LLM cost. The skill mode file says so; make sure the sub-agent has actually run it.
- **The dedup guard does not index `user/workspace/organizations/companies/`** — coverage of the 95 existing profiles
  is indirect, so both sub-agents must also do the name-list check. This is a known gap, not an
  oversight to fix in passing.
- **If one sub-agent fails**, reconcile the other's folder anyway and say which track did not
  complete.

---

## Related

[[search-common]] · [[search-companies-career]] · [[search-companies-skill]] ·
[[inbox-eval]] (scores both axes) · [[search-positions]] · [[search-groups]] (sibling
orchestrators) · [[cv-generate]] (writes the unsolicited applications these profiles feed)
