---
name: search-positions-skill
cssclasses: [skill]
recommended_model: Sonnet medium — provisional, never low (see search-positions-common §Model and effort)
description: >
  SKILL (employability) track position collector. Searches for open positions the user could
  realistically get and do, judged purely on evidenced competencies — direction is irrelevant
  here. Run as a sub-agent by /search-positions, in parallel with search-positions-career.
  Writes raw .txt to user/workspace/inbox/_staging/skill/ only. Does NOT score — that is /inbox's job.
---

# search-positions-skill

**Track: skill (employability).** The question is *could the user realistically get this job and
do it?* — evidenced competence, and nothing else. Whether the work is on-direction is the other
track's problem, and `career_fit` records it at scoring time anyway.

> **This track will surface roles built on the user's strongest competencies, whatever their
> field. That is correct.** Those need not be the stated direction — `user/profile/search_terms.md`
> §Skill track says what that means for this profile. A search that maximises skill match can
> point away from the direction; that is the honest shape of the profile, and seeing it is the
> reason this track exists. **Never add a direction filter here.** `/inbox` scores `career_fit` on
> everything, so how off-direction a lead is stays visible without being suppressed at collection time.

## Read these first, in order

1. **[[search-common]]** — geography allowlist, staging protocol, `TRACK:` stamp. Identical
   for both tracks.
2. **[[search-positions-common]]** — everything else: run modes, dedup, Gates 0/2/4, sources,
   output format, telemetry, model guidance.
3. **This file** — supplies the three **[MODE]** steps that common file leaves open.

Write every collection to **`user/workspace/inbox/_staging/skill/`**. Never to `user/workspace/inbox/`.

---

## [MODE] Step 5 — keyword pass

There are no direction tiers here. Normalise variants (the domain pack's `synonyms.md`), then simply
note every term matching the competency triggers in the user's table (Gate 3 below).
a cheap pre-filter; Gate 3 is the real test, and they read the same vocabulary.

Skip an ad at this step only when **nothing at all** in the competency table appears anywhere
in it. Anything else goes through to the gates.

## [MODE] Gate 0 — no extra reject

Use the shared rejects only (dead deadline · removed posting · portal page · outside the
geography allowlist).

**Do not apply the career track's direction reject here.** The career track rejects such work as
off-direction; this track has no direction floor, and a role that reject catches can be a
real skills match. If it clears Gate 3 on competencies, collect it.

## [MODE] Gate 1 — competency presence

List every competency-trigger term that literally appears in the ad, grouped by competency.
**Pass iff any term from the table appears in the role text at all.** Gate 3 does the counting;
Gate 1 only weeds out ads with no overlap whatsoever.

Record as: `Gate 1 (terms found): {C1: terms | C2: terms | ...}` or `none`

## [MODE] Gate 3 — competency count

*Does this role need what the user can prove they have?* Mechanical: for each competency in the
user's table — `user/profile/search_terms.md` §Skill track → *Competency table — positions* — mark
**PRESENT** iff the **role text** (responsibilities, requirements, "you will…") names at least
one trigger term or an unambiguous synonym. Gate 2 has already discarded company boilerplate, so
only role text counts.

> ### A competency counts only when it is CENTRAL
>
> **Added 2026-08-18, after the first two-track run.** The gate previously passed on a
> competency being *named anywhere* in the role text. That is far looser than `skill_match`
> and it showed: Latent Labs' Forward Deployed AI Engineer passed on `{C1: "data pipelines",
> C4: "API, CI/CD pipelines"}` and then scored **35**. Three of six collections scored ≤35.
>
> A competency is **PRESENT** only if it describes **what the person does**, not what the
> employer would like them to have heard of. Concretely:
>
> | Counts | Does not count |
> |---|---|
> | Named in the primary responsibilities — "you will build/own/maintain X" | Buried in a requirements laundry list of a dozen technologies |
> | The role is organised around it (a section, a repeated theme) | Mentioned once in passing |
> | Named in the job title | Under "nice to have", "a plus", "what sets you apart" |
> | The daily work is unimaginable without it | Listed as an acceptable degree field |
>
> When a term appears only in a "bonus" or "differentiator" section, **record it and move on** —
> note it in the Gate 3 line as `(noted, not counted)` so the decision stays auditable, but do
> not let it reach the threshold. Naming a competency is not the same as the role being about it.

**COLLECT iff ≥2 distinct counting competencies are PRESENT** — the table marks the Tier-3 rows,
which are recorded but never count. One competency alone is not enough — nearly every
computational biology ad names Python or Linux, and a single generic overlap says nothing about
employability. A Tier-3 row never counts, for the same reason Tier 3 never qualifies a lead in the
career track.

Record as: `Gate 3 (competencies): {C1, C6, C7} — 3 present`

> **This is the mirror of the career track's output test, and the rows that flip are the point**
> (`search_terms.md` §Skill track names them for this profile). Two searches exist so that
> neither question has to be compromised to accommodate the other.

## [MODE] Which orgs to sweep

Rotate `user/workspace/organizations/companies/` and `user/workspace/organizations/research_groups/` oldest-`last_evaluated`-first,
taking orgs at **`skill_match` 60+** — the employers whose actual stack overlaps the
competencies, whatever they work on. The career track sweeps the same folders at `career_fit`
60+; an org clearing both gets swept twice and the parent drops the duplicate.

---

## What this track does NOT change

Everything below stays exactly as the career track runs it — do not re-derive or relax any of it:

- **Gate 2 (placement)** — a company that mentions Snakemake in its "about us" while advertising
  a finance role still fails. Terms must be in the role text.
- **Gate 4 (level)** — the same seniority rules, with the user's thresholds (`search_terms.md`
  §Level gate). Being well-qualified on competencies does not make an over-level role attainable,
  and `level_fit` will say `reach` regardless.
- **Calls for the qualification the user is working towards → PASS** (for this profile: PhD
  calls). Collected by this track too: such a call matching the existing stack is a real lead,
  and it is also how a developing competency gets closed.
- **Roles requiring a qualification the user lacks, and faculty calls → group profile**, not a
  position (for this profile: postdocs, which need a completed PhD no matter how well the
  competencies line up).

---

## Report

At the end, report to the orchestrator:

```
track: skill
mode:  fast | deep
collected: N   -> user/workspace/inbox/_staging/skill/
screened:  N
skipped:   N   (gate0 X · gate1 X · gate2 X · gate3 X · gate4 X · dedup X · geo X)
competency spread: {how many collections hit each counting competency}
channels:  {which sources were actually queried}
```

The competency spread is worth reporting because it says which of the user's skills the market is
actually asking for — information the career track structurally cannot produce.

---

## Related

[[search-common]] · [[search-positions-common]] · [[search-positions-career]] (the other track —
same ads, different question) · [[competencies]] (the evidence base this gate reads) ·
[[background]] · [[preferences]] · [[inbox-eval]]
