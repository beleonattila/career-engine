---
name: search-groups-skill
cssclasses: [skill]
recommended_model: Sonnet (low–medium) — unmeasured; the yield telemetry covers positions only
description: >
  SKILL (employability) track research-group collector. Builds the group database with labs
  whose methods overlap the user's evidenced competencies — scientific direction is irrelevant
  here. Run as a sub-agent by /search-groups, in parallel with search-groups-career. Writes
  raw .txt to user/workspace/inbox/_staging/skill/ only. Does NOT score — that is /inbox's job.
---

# search-groups-skill

**Track: skill (employability).** Building the group database with labs where the user **could
walk in and be useful**, judged on their methods against `user/profile/competencies.md`. What they study is
the other track's question.

A lab is cold-emailed the same way a company is, and the email has to answer "could I be useful
here". A group whose methods match the user's competencies is a real place to send it, even when
the science is nowhere near the direction.

**Read [[search-common]] first** — geography, staging, `TRACK:`, the competency gate, org dedup.
No direction filter here, ever (§The two-track model).

Write every collection to **`user/workspace/inbox/_staging/skill/`**. Never to `user/workspace/inbox/`.

---

## Task

1. **Check the current database.** List `user/workspace/organizations/research_groups/` and hold names.
2. **Search for groups not on that list** whose *methods* overlap the user's competency table.
3. **Check geography before fetching anything else** — [[search-common]] §Geography.
4. **Read the lab's research / methods / software / publications pages.** The **software** and
   **resources** pages matter more here than in the career track: a lab that ships a tool has
   evidenced the pipeline and software competencies directly.
5. **Collect iff ≥2 distinct counting competencies are evidenced** in the lab's own description —
   [[search-common]] §Skill track: the competency gate (table: `user/profile/search_terms.md`
   §Skill track → *Competency table — groups*).
5.5 **Log any method-building vacancy** on the lab's or institute's jobs page — [[search-common]]
   §Method sightings.
6. **Run the dedup guard before writing — mandatory (CLAUDE.md)** — [[search-common]] §Org
   collectors: dedup (`--query <groupslug> "group-profile"`).
7. **Report** collections, competency spread, screened count, channels.

**Stop criteria:** 3 minutes of runtime.

---

## Output format

**file name:** `[groupslug]_group-profile_found-[YYYY-MM-DD].txt`
→ written to `user/workspace/inbox/_staging/skill/`

**file content:**

```
SOURCE: https://www.example-lab.univ.dk
FOUND: 2026-08-18

Name: Example Computational Microbiology Group
Web: www.example-lab.univ.dk
Location: Copenhagen, Denmark (KU)
PI: {name}
Competencies: C1 (Nextflow, HPC), C4 (maintains two released tools), C6 (metagenomics, AMR) — 3 present
Geography block: {the block's name in user/settings.toml [[geography.block]]}

{descriptive text from the lab's research / methods / software / publications pages}
```

---

## Where to Search

### Step 1 — Query papers by METHOD, not by topic

The substantive difference from the career track. Search PubMed (E-utilities API) and Google
Scholar for labs whose *methods sections* match, whatever they are studying. The queries are the user's: `user/profile/search_terms.md` §Skill track → *Paper queries (groups,
by method)*, grouped by the competency each one targets.

### Step 2 — Filter by lab, not by journal impact

Unlike the career track, **do not filter by journal tier here.** A well-run pipeline group
publishing in *Bioinformatics*, *BMC Bioinformatics* or *GigaScience* is exactly the kind of
employer this track is for, and an impact filter would remove precisely those labs. Prioritise
labs that ship software and maintain it.

### Step 3 — Extract group information

Corresponding/last author, institution, department, country, lab website, and **the tools the
lab has released** (GitHub organisation, Bioconda recipes, a software page).

### Step 4 — Additional surfaces the career track does not use

- **Core facilities and platform units** — imaging cores, sequencing cores, bioinformatics
  service units. High C1/C4/C7 density and they hire continuously; the career track will never
  see them because they have no scientific direction of their own.
- **National infrastructure** — the pack's `boards.md` §Group discovery names it for the allowlist regions.
- **GitHub / Bioconda** — a maintained tool with a lab affiliation in its README is direct
  evidence of software development, and the affiliation names the group.

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

[[search-common]] · [[search-groups-career]] (the other track — same labs, different question) ·
[[competencies]] (the evidence base this gate reads) · [[inbox-eval]] ·
[[search-positions-skill]] · [[search-companies-skill]]
