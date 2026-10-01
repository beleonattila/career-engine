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
here". A group whose methods match the user's competencies is a real place to send that email
even when the science is nowhere near the direction.

> **This track will surface groups whose methods match the user's competencies, whatever they
> study (`search_terms.md` §Skill track says what that means for this profile). That is correct** — never add a direction filter.
> `/inbox` scores `career_fit` on every group, so how off-direction one is stays visible without
> being suppressed at collection time.

**Read [[search-common]] first** — geography allowlist, staging protocol, `TRACK:` stamp.

Write every collection to **`user/workspace/inbox/_staging/skill/`**. Never to `user/workspace/inbox/`.

---

## Task

1. **Check the current database.** List `user/workspace/organizations/research_groups/` and hold names.
2. **Search for groups not on that list** whose *methods* overlap the user's competency table.
3. **Check geography before fetching anything else** — [[search-common]] §Geography.
4. **Read the lab's research / methods / software / publications pages.** The **software** and
   **resources** pages matter more here than in the career track: a lab that ships a tool has
   evidenced the pipeline and software competencies directly.
5. **Collect iff ≥2 distinct counting competencies are evidenced** in the lab's own description.
5.5 **Log any method-building vacancy you see** on the lab's or institute's jobs page — a seat whose
   own text says it builds tools, pipelines or methods others use ([[search-positions-skill]]
   §Method lane, the build signal) — whether or not the lab is collected:
   `python engine/tools/method_sightings.py add --org <slug> --title "…" --url … --signal "<verbatim>" --outcome seen --source skill`.
   A lab whose tooling has outgrown its people is exactly the cold-outreach target the method
   brand is for.
6. **Run the dedup guard before writing — mandatory (CLAUDE.md).**
7. **Report** collections, competency spread, screened count, channels.

**Stop criteria:** 3 minutes of runtime.

## The collect test — competency count

The table is the user's — `user/profile/search_terms.md` §Skill track → *Competency table —
groups*, calibrated with the position and company versions.

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

**Collect iff ≥2 distinct counting competencies are PRESENT** (Tier-3 rows record only). One alone is not enough — nearly every
computational lab says "machine learning" somewhere.

## Dedup guard — mandatory before any write

```bash
python engine/tools/dedup_check.py
python engine/tools/dedup_check.py --query <groupslug> "group-profile"
```

Same coverage gap and same alias hazards as the career track — `dedup_check.py` does not index
`user/workspace/organizations/research_groups/`, and a lab arrives under its PI, its lab name, or its parent
institution (`nnf-cpd-ku` ≡ `ku-cpd` ≡ `university-of-copenhagen-cpd`). Keep the step 1
name-list check as well, and add to the alias table (`user/workspace/organizations/aliases.toml`) when you meet a new pair.

The guard cannot see the career track's staging folder. An overlap is expected; the parent
resolves it, career winning.

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

`TRACK:` is stamped by the parent during reconciliation — do not write it yourself.

---

## Where to Search

### Step 1 — Query papers by METHOD, not by topic

This is the substantive difference from the career track. Search PubMed (E-utilities API) and
Google Scholar for labs whose *methods sections* match, whatever they are studying:

The queries are the user's: `user/profile/search_terms.md` §Skill track → *Paper queries (groups,
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
