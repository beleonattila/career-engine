---
name: search-positions-career
cssclasses: [skill]
recommended_model: Sonnet medium — provisional, never low (see search-positions-common §Model and effort)
description: >
  CAREER track position collector. Searches for open positions on the user's preferred
  direction (user/profile/preferences.md). Run as a sub-agent by /search-positions,
  in parallel with search-positions-skill. Writes raw .txt to user/workspace/inbox/_staging/career/ only.
  Does NOT score — that is /inbox's job.
---

# search-positions-career

**Track: career.** The question is *is this the work the user wants?* — direction, and nothing
else. Whether the user would get the job is the other track's problem, and `level_fit` records it at
scoring time anyway.

## Read these first, in order

1. **[[search-common]]** — geography allowlist, staging protocol, `TRACK:` stamp. Identical
   for both tracks.
2. **[[search-positions-common]]** — everything else: run modes, dedup, Gates 0/2/4, sources,
   output format, telemetry, model guidance.
3. **This file** — supplies the three **[MODE]** steps that common file leaves open.

Write every collection to **`user/workspace/inbox/_staging/career/`**. Never to `user/workspace/inbox/`.

---

## [MODE] Step 5 — keyword tiers

Normalise variants first (the domain pack's `synonyms.md`), then bucket every term by tier. **The
tiers are the user's:** `user/profile/search_terms.md` §Career track → *Keyword tiers*. Their shape
is fixed: **Tier 1** — strong, any one is a bullseye · **Tier 2** — supporting / adjacent ·
**Tier 3** — generic context, never qualifies a lead on its own.

**Ignore `M` / `Mb` rows in the ATS sweep.** They are the skill track's method lane
([[search-positions-skill]] §Method lane) and carry no direction signal; a method role that is
also on-direction already shows up here as `T1`–`T2?`.

## [MODE] Gate 0 — one extra hard reject

In addition to the shared rejects, the career track applies the user's one direction reject —
`user/profile/search_terms.md` §Career track → *Gate 0 reject*. It is off-direction by definition
(`career_fit` < 30).

The skill track deliberately does *not* carry this reject. A role it catches can be a
genuine skills match, and the employability track has no direction floor — so if such a role is
worth collecting at all, that track will collect it.

## [MODE] Gate 1 — keyword presence

List every Tier-1 and Tier-2 term that literally appears in the ad.
**Pass iff ≥1 Tier-1 OR ≥2 distinct Tier-2.** Tier-3 never qualifies a lead alone.

Record as: `Gate 1 (terms found): T1: {terms or none} | T2: {terms or none}`

## [MODE] Gate 3 — output

*What does the person in this role personally ship?* Choose **exactly one** row of the user's
output table — `user/profile/search_terms.md` §Career track → *Gate 3 output*. The verdict is
fixed by the choice — do not override it.

Record as: `Gate 3 (output): {row} — {one clause naming what the person ships}`

> **Rows that SKIP here may COLLECT in the skill track.** That is not an inconsistency to
> reconcile — it is the entire point of running two searches (`search_terms.md` names the rows
> that flip for this profile). Never soften a SKIP row here to "rescue" a lead; the other agent
> is looking at the same ad with the other question and will collect it if it is worth having.

## [MODE] Which orgs to sweep

Rotate `user/workspace/organizations/companies/` and `user/workspace/organizations/research_groups/` oldest-`last_evaluated`-first,
taking orgs at **`career_fit` 60+**. The skill track sweeps the same folders at `skill_match`
60+; an org clearing both gets swept twice and the parent drops the duplicate.

---

## Report

At the end, report to the orchestrator:

```
track: career
mode:  fast | deep
collected: N   -> user/workspace/inbox/_staging/career/
screened:  N
skipped:   N   (gate0 X · gate1 X · gate2 X · gate3 X · gate4 X · dedup X · geo X)
channels:  {which sources were actually queried}
```

The skip breakdown by gate is what `analyze_misses.py` reads to tell precision from recall, so
give the real counts rather than a total.

---

## Related

[[search-common]] · [[search-positions-common]] · [[search-positions-skill]] (the other track —
same ads, different question) · [[background]] · [[preferences]] · [[inbox-eval]]
