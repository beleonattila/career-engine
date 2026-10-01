---
name: search-common
cssclasses: [skill]
description: >
  Shared contract for all six search collectors (positions/companies/groups x career/skill).
  Not invoked directly — every search skill reads this first. Defines the two-track model,
  the geography allowlist, the staging protocol that keeps two parallel sub-agents from
  colliding, and the `TRACK:` stamp.
---

# search-common

**Not a command.** Read by all six collectors. If you are reading this without having been
sent here by one of them, you want `/search-positions`, `/search-companies` or `/search-groups`.

---

## The two-track model

Since 2026-08-17 every kind is searched twice, in parallel, by two sub-agents that never see
each other's context:

| Track | Asks | Collects |
|---|---|---|
| **career** | Is this the work I want? | The direction in `user/profile/preferences.md` (the gate terms: `user/profile/search_terms.md`) |
| **skill** | Could I actually get and do this? | Anything the evidenced competencies in user/profile/competencies.md cover, direction irrelevant |

**The skill track has no direction floor, and that is deliberate.** The user's Expert-tier
competencies (`user/profile/competencies.md`) need not be their stated direction — the
direction may even be the one competency still marked *in active development*. So a search
that maximises skill match will surface roles built on those other competencies, however
off-direction, and the user's strongest credentials may sit there too.

That is not a malfunction to be corrected with a filter. It is the honest shape of the profile,
and the employability track exists precisely to see it. **Never quietly add a direction filter
to the skill track** to make its results look more on-brand. `/inbox` records `career_fit` on
every record, so how off-direction a lead is stays visible without suppressing it.

> 🆕 **The skill track is where method roles come from (2026-09-29).** `/inbox` now also records
> **`method_fit`** — *does the seat build methods, tools and systems, or only operate them?*
> (rubric: [[inbox-eval]] §`method_fit`; rationale: `user/workspace/notes/rebrand_plan.md`). The user has said yes to
> methods-building roles in genomics, pharma/clinical data and non-bio fields, and those reach the
> vault through **this** track: its pipeline-engineering and scientific-software
> competency triggers are exactly what such ads name. This is one more reason the skill track
> must keep its lack of a direction floor — it is now the only route by which a `career_fit` 30 ·
> `method_fit` 90 role gets collected at all.
>
> ⚠️ **The career track is unchanged and stays direction-only.** Never collect on the career track
> because a role "builds methods" — that is `method_fit`'s job, not `career_fit`'s, and the two
> scores exist precisely so neither has to bend. Collectors still score nothing.

Neither track scores. `/inbox` does all scoring, on Opus. A collector decides collect-or-skip
and writes the raw text down. Nothing else.

---

## Geography — one allowlist, both tracks

Enumerate as a country list. **Never** rely on a region token: measured 2026-07-29, LinkedIn's
`location=European Union` returned 47 hits and **zero** from CH, NO or the UK — it silently
excludes them. Query each block separately.

**The allowlist is the user's: read `user/settings.toml` `[[geography.block]]` before searching.**
Each block has a `name`, its `countries`, and a `note` — follow the note (it says, for example,
which block is preferred and what to record about a visa). A block with **`remote_only = true`**
is collected **only** when the ad itself states that remote work from one of the other blocks, or
from anywhere, is acceptable; an on-site role there is out of scope — do not fetch it, do not
write it. `ats_sweep.py` applies the same list to ATS location strings.

**Everything else is out of scope before a single fetch.** Do not spend tokens screening
postings in countries outside the allowlist. Where a search surface cannot be filtered by
country, filter the result list before fetching any ad body, not after.

> **This replaced a score-based proxy on 2026-08-17.** The old rule swept EU orgs at fit 60+ and
> non-EU at 80+, using the blended `fit_score` as a stand-in for "is this worth the relocation".
> With `career_fit` now measuring direction and only direction, that rule would mean demanding
> *more on-direction work from a foreign lab than a Danish one* — not a preference the user holds.
> Geography is a collection budget, so it is spent as one, explicitly.

---

## Staging protocol — how two parallel agents avoid collecting the same ad twice

Both sub-agents run at once and both write `.txt` files. Neither can reliably see what the other
has written mid-run. So they do not share a directory:

```
career sub-agent  ──►  user/workspace/inbox/_staging/career/
skill  sub-agent  ──►  user/workspace/inbox/_staging/skill/
                         └──► parent command reconciles ──► user/workspace/inbox/
```

**As a sub-agent, your contract is:**

1. Write every collected `.txt` to **your own staging folder only**. Never write directly to
   `user/workspace/inbox/`, and never read or write the other track's folder.
2. Run `dedup_check.py` as normal against the persistent vault — `user/workspace/inbox/`,
   `user/workspace/inbox/processed/`, `user/workspace/inbox/processed/archive/` and `user/workspace/positions/{open,applied,closed}/`.
   That still catches everything already known.
3. Accept that you **cannot** dedup against the other track mid-run. Do not try. Collecting
   something the other track also found is expected, and the parent resolves it.
4. Report your collection count and the paths you wrote.

**Overlap is the common case, not an edge case.** A protein-design role that also names
Snakemake and HPC passes the career output gate *and* the skill competency gate, so both agents
collect it. That is correct behaviour — reconciliation exists for it.

**The parent command then:**

1. Runs `dedup_check.py` across both staging folders together.
2. On a collision, **career wins**: keep the career copy, drop the skill copy. A lead that
   clears the career gate is one the user wants regardless of how well their skills fit it, and
   that is the more useful provenance to record.
3. Stamps `TRACK: career` or `TRACK: skill` into the header of each surviving `.txt`.
4. Moves everything into `user/workspace/inbox/` and leaves both staging folders empty.

`/inbox` reads `TRACK:` from the header and writes it to the profile frontmatter as
`track: career | employability`. The dashboard's Employability tab reads that field.

> **Empty the staging folders even when a run collects nothing.** A leftover `.txt` from an
> interrupted run would be swept into `user/workspace/inbox/` by the *next* run's reconciliation and attributed
> to the wrong run in the telemetry.

---

## Rules both tracks share and must never fork

- **Dedup by identity, never by age.** A lead is stale only when its deadline has passed or the
  posting is confirmed removed. Age is a sort priority, never a discard rule.
- **`POSTED:` is load-bearing.** `FOUND − POSTED` is the lag, and lag is the only way a missed
  posting is detected at all. `unknown` is acceptable when the source states no date; a guess is
  worse than `unknown` because it silently corrupts the measurement.
- **Faculty and postdoc calls are not positions**, in either track. Both require a completed PhD,
  so each is saved as `[groupslug]_group-profile_found-YYYY-MM-DD.txt` and routes to the group
  database as a cold-outreach lead. This holds in the skill track too: no amount of skill overlap
  makes a postdoc applyable without the doctorate.
- **PhD and doctoral calls ARE collected by both tracks.** The career track takes them on
  direction; the skill track takes them on competency overlap. A PhD is also how the generative-
  design gap gets closed, so a doctoral call matching the existing stack is a real lead.
- **Answer the gates explicitly and record the answers in the saved `.txt`.** Same ad, same
  answers, same verdict. Holistic judgement is not reproducible: on 2026-07-29 a run skipped all
  four Basecamp Research roles as "ML infra, not protein design"; on 2026-07-30 a run collected
  all four. Same four ads, opposite verdicts, one day apart.

---

## Related

[[background]] · [[preferences]] · [[competencies]] (the evidence base the skill track gates on) ·
[[search-positions-common]] · [[inbox-eval]] (the THINK stage — scores everything these collect)
