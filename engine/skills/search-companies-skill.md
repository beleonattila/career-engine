---
name: search-companies-skill
cssclasses: [skill]
recommended_model: Sonnet (low–medium) — unmeasured; the yield telemetry covers positions only
description: >
  SKILL (employability) track company collector. Builds the company database with employers
  whose actual technical stack overlaps the user's evidenced competencies — direction is
  irrelevant here. Run as a sub-agent by /search-companies, in parallel with
  search-companies-career. Writes raw .txt to user/workspace/inbox/_staging/skill/ only. Does NOT score.
---

# search-companies-skill

**Track: skill (employability).** Building the company database with employers where the user
**could walk in and be useful**, judged on their stated technical stack against
`user/profile/competencies.md`. What they work *on* is the other track's question.

This is the track that makes the company database work as a cold-outreach list. An unsolicited
application has to answer "could I be useful here", and that is exactly what `skill_match`
records — see the four-case table in `user/profile/preferences.md` §Scoring → *Worked examples: org
scores*, which is the shape this search is built to populate.

Rows 2 and 4 are what this track exists to find. Row 2 in particular will never be found by the
career track, and it is a perfectly good place to send an application.

> **This track will surface companies whose stack matches the user's competencies, whatever they
> work on (`search_terms.md` §Skill track says what that means for this profile). That is correct**
> — never add a direction filter. `/inbox` scores
> `career_fit` on every company, so how off-direction one is stays visible without suppressing
> it at collection time.

**Read [[search-common]] first** — geography allowlist, staging protocol, `TRACK:` stamp.

Write every collection to **`user/workspace/inbox/_staging/skill/`**. Never to `user/workspace/inbox/`.

---

## Task

1. **Check the current database.** List `user/workspace/organizations/companies/` and hold the names.
2. **Search for companies not on that list** whose stated stack overlaps the user's competency table.
3. **Check geography before fetching anything else** — [[search-common]] §Geography.
4. **Read its science / research / platform / engineering / careers pages** — the careers page
   matters more here than in the career track, because a stack shows up in job ads before it
   shows up in marketing copy.
5. **Collect iff ≥2 distinct counting competencies are evidenced** in the company's own
   description of its work.
6. **Run the dedup guard before writing — mandatory (CLAUDE.md).**
7. **Report** collections, competency spread, screened count, channels.

## The collect test — competency count

Mark a competency **PRESENT** iff the company's own pages evidence it. The table is the user's —
`user/profile/search_terms.md` §Skill track → *Competency table — companies*, calibrated with the
position and group versions.

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

**Collect iff ≥2 distinct counting competencies are PRESENT** (Tier-3 rows record only). One alone is not enough: almost every biotech
says "machine learning" somewhere, and a single generic overlap says nothing about whether
the user could be useful there.

## Dedup guard — mandatory before any write

```bash
python engine/tools/dedup_check.py
python engine/tools/dedup_check.py --query <org> "company-profile"
```

Same coverage gap as the career track: `dedup_check.py` does not index `user/workspace/organizations/companies/`,
so keep the step 1 name-list check as well. And the guard cannot see the career track's staging
folder — an overlap is expected and the parent resolves it, career winning.

---

## Output format

**file name:** `[orgslug]_company-profile_found-[YYYY-MM-DD].txt`
→ written to `user/workspace/inbox/_staging/skill/`

**file content:**

```
SOURCE: https://www.example-bio.com
FOUND: 2026-08-18

Name: Example Bio ApS
Web: www.example-bio.com
Location: Copenhagen, Denmark
Competencies: C1 (Nextflow, HPC), C6 (metagenomics, AMR), C7 (deep learning segmentation) — 3 present
Geography block: {the block's name in user/settings.toml [[geography.block]]}

{descriptive text from the company's about / science / platform / engineering / careers pages}
```

`TRACK:` is stamped by the parent during reconciliation — do not write it yourself.

---

## Where to Search

The career track's sources plus the ones where a stack is visible: the pack's `boards.md`
§Company discovery (skill-track list).

> **`ats_sweep.py` is the cheapest surface for this track specifically.** It sweeps every known
> employer board in one pass, ~30s and zero LLM tokens. Job ads state a stack plainly, so a
> company whose postings name a competency's trigger terms has evidenced it without anyone
> reading a marketing page.

**Stop criteria:** 3 minutes of runtime.

---

## Report

```
track: skill
collected: N   -> user/workspace/inbox/_staging/skill/
screened:  N
skipped:   N   (geo X · competencies X · dedup X)
competency spread: {how many collections hit each counting competency}
channels:  {which sources were queried}
```

---

## Related

[[search-common]] · [[search-companies-career]] (the other track — same employers, different
question) · [[competencies]] (the evidence base this gate reads) · [[inbox-eval]] ·
[[search-positions-skill]] · [[search-groups-skill]]
