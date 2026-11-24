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

This track makes the company database work as a cold-outreach list: an unsolicited application
has to answer "could I be useful here", which is what `skill_match` records. Rows 2 and 4 of the
four-case table in `user/profile/preferences.md` §Scoring → *Worked examples: org scores* are what
this track exists to find; row 2 will never be found by the career track.

**Read [[search-common]] first** — geography, staging, `TRACK:`, the competency gate, org dedup.
No direction filter here, ever (§The two-track model).

Write every collection to **`user/workspace/inbox/_staging/skill/`**. Never to `user/workspace/inbox/`.

---

## Task

1. **Check the current database.** List `user/workspace/organizations/companies/` and hold the names.
2. **Search for companies not on that list** whose stated stack overlaps the user's competency table.
3. **Check geography before fetching anything else** — [[search-common]] §Geography.
4. **Read its science / research / platform / engineering / careers pages** — the careers page
   matters more here than in the career track: a stack shows up in job ads before marketing copy.
5. **Collect iff ≥2 distinct counting competencies are evidenced** in the company's own pages —
   [[search-common]] §Skill track: the competency gate (table: `user/profile/search_terms.md`
   §Skill track → *Competency table — companies*).
5.5 **Log any method-building seat on the careers page** — [[search-common]] §Method sightings.
6. **Run the dedup guard before writing — mandatory (AGENTS.md)** — [[search-common]] §Org
   collectors: dedup (`--query <org> "company-profile"`).
7. **Report** collections, competency spread, screened count, channels.

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

---

## Where to Search

The career track's sources plus the ones where a stack is visible: the pack's `boards.md`
§Company discovery (skill-track list).

> **`ats_sweep.py` is the cheapest surface for this track** — every known employer board in one
> pass, zero LLM tokens. A company whose postings name a competency's trigger terms has evidenced it.

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
