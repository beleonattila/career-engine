---
name: search-groups
cssclasses: [skill]
recommended_model: Sonnet (low–medium) — the orchestrator is cheap; the sub-agents do the work
description: >
  Build the research-group database on BOTH tracks at once. Fans out to two sub-agents in
  parallel — search-groups-career (does this lab do the science I want?) and search-groups-skill
  (could I be useful in that lab?) — then reconciles their staging folders into the inbox.
  Trigger on /search-groups. Does NOT score; /inbox does that.
---

# search-groups

**Orchestrator.** Spawns and reconciles; does not search.

```
/search-groups ─┬─► search-groups-career.md ──► user/workspace/inbox/_staging/career/ ─┐
                └─► search-groups-skill.md  ──► user/workspace/inbox/_staging/skill/  ─┤
                                                                        ▼
                                                  reconcile_staging.py --apply
                                                                        ▼
                                                              user/workspace/inbox/
```

A group profile is a PI to email, not a job to apply for — and a cold email has to answer "could
I be useful here" as much as "is this the science I want". That is why groups carry both scores
and get both searches, the same as companies.

**Optional argument:** `/search-groups skill` or `/search-groups career` runs one track only.
Bare `/search-groups` runs both.

---

## Workflow

### Step 1 — Confirm staging is clean

```bash
python engine/tools/reconcile_staging.py
```

Reconcile any leftovers (`--apply`) before spawning.

### Step 2 — Spawn both sub-agents, in parallel

**Both Agent calls in a single message.**

> **career agent** — "Read `engine/skills/search-groups-career.md` and follow it exactly.
> You are the CAREER track. Write collections only to `user/workspace/inbox/_staging/career/`.
> Report in the format the skill specifies."

> **skill agent** — "Read `engine/skills/search-groups-skill.md` and follow it exactly.
> You are the SKILL (employability) track. Write collections only to
> `user/workspace/inbox/_staging/skill/`. Report in the format the skill specifies."

Wait for both before Step 3.

### Step 3 — Reconcile

```bash
python engine/tools/reconcile_staging.py            # inspect
python engine/tools/reconcile_staging.py --apply    # stamp TRACK:, move into user/workspace/inbox/, empty staging
```

Career wins every collision.

### Step 4 — Report

```
── Search: research groups ──────────────────────────────────────
career   collected N · screened N · skipped N (geo X · terms X · dedup X)
skill    collected N · screened N · skipped N (…)   competency spread: C1 x · C2 x · …

reconciled: N kept · N dropped (career won)
─────────────────────────────────────────────────────────────────
Run /inbox on Opus to score everything collected.
```

Tell the user to run `/inbox`; do not run it yourself.

---

## Notes

- **The two tracks search differently, not just with different keywords.** The career track
  queries papers by *topic* and filters by journal tier. The skill track queries by *method* and
  deliberately does **not** filter by impact — a pipeline group publishing in *Bioinformatics* or
  *GigaScience* is exactly the kind of employer it exists to find, and an impact filter would
  remove precisely those labs.
- **Faculty calls still route here, from both position tracks.** A professorship or a postdoc ad
  is saved as a `_group-profile_` file rather than a position, because both require a completed
  PhD. That is a funded lab hiring in a relevant area — a cold-outreach lead, not a job lead.
- **Group slugs collide easily** — a lab arrives under its PI, its lab name, or its parent
  institution (`nnf-cpd-ku` ≡ `ku-cpd` ≡ `university-of-copenhagen-cpd`). Both sub-agents must do
  the name-list check as well as the dedup guard, which does not index
  `user/workspace/organizations/research_groups/`.
- **If one sub-agent fails**, reconcile the other's folder anyway and say which track did not
  complete.

---

## Related

[[search-common]] · [[search-groups-career]] · [[search-groups-skill]] ·
[[inbox-eval]] (scores both axes) · [[search-positions]] · [[search-companies]] (sibling
orchestrators) · [[cv-generate]] (writes the cold-outreach letters these profiles feed)
