---
name: search-groups-career
cssclasses: [skill]
recommended_model: Sonnet (low–medium) — unmeasured; the yield telemetry covers positions only
description: >
  CAREER track research-group collector. Builds the group database with labs working on
  the user's preferred direction (user/profile/preferences.md). Run as a sub-agent by /search-groups, in
  parallel with search-groups-skill. Writes raw .txt to user/workspace/inbox/_staging/career/ only.
  Does NOT score — that is /inbox's job.
---

# search-groups-career

**Track: career.** Building an ever-growing database of research groups **working on the
preferred direction** (`user/profile/preferences.md`).

A group profile is a cold-outreach target: a PI to email, not a job to apply for. `/inbox`
scores it on both axes — `career_fit` (is this the science) and `skill_match` (could the user be
useful in that lab).

**Read [[search-common]] first** — geography allowlist, staging protocol, `TRACK:` stamp.

Write every collection to **`user/workspace/inbox/_staging/career/`**. Never to `user/workspace/inbox/`.

---

## Task

1. **Check the current database.** List `user/workspace/organizations/research_groups/` and hold names.
2. **Search for groups not on that list** working on the direction.
3. **Check geography before fetching anything else** — [[search-common]] §Geography.
4. **Read the lab's research / about / publications pages** and match the user's direction terms
   (`user/profile/search_terms.md` §Career track → *Direction terms*).
5. **Collect iff ≥3 direction terms** appear in the lab's own description of its research.
6. **Run the dedup guard before writing — mandatory (CLAUDE.md).**
7. **Report** collections, screened count, channels.

**Stop criteria:** 3 minutes of runtime.

## Dedup guard — mandatory before any write

```bash
python engine/tools/dedup_check.py
python engine/tools/dedup_check.py --query <groupslug> "group-profile"
```

Step 1's name list is **eyeball dedup, and eyeball dedup has demonstrably failed** — four
org-slug collisions in ten days (2026-07-29 … 08-08). The one that matters most here is
`kuleuven-dewilde` vs `ku-leuven`: split-vs-joined spellings of the same institution, which is a
*group*-collection failure mode specifically. Those are now handled structurally.

> ⚠️ **Known coverage gap.** `SEARCH_GLOBS` in `dedup_check.py` indexes `user/workspace/inbox/`,
> `user/workspace/inbox/processed/`, `processed/archive/` and `user/workspace/positions/{open,applied,closed}/` — it does
> **not** index `user/workspace/organizations/research_groups/` or `user/workspace/organizations/companies/`. Coverage of the 47 existing
> group profiles is indirect, via the processed `.txt` each was built from, and a group whose
> source `.txt` has been pruned will read as new. Keep the step 1 name-list check **as well**.
>
> A group can also arrive under its PI, its lab name, or its parent institution
> (`nnf-cpd-ku` ≡ `ku-cpd` ≡ `university-of-copenhagen-cpd`). Renames and parent/child pairs are
> the one thing no string rule derives — those live in the alias table
> (`user/workspace/organizations/aliases.toml`), so add one when you meet a new pair.
>
> ⚠️ **The guard cannot see the skill track's staging folder.** An overlap is expected and the
> parent resolves it, career winning. Do not try to check the other folder.

---

## Output format

**file name:** `[groupslug]_group-profile_found-[YYYY-MM-DD].txt`
→ written to `user/workspace/inbox/_staging/career/`

**file content:**

```
SOURCE: https://www.digital-biotechnology.com
FOUND: 2026-06-13

Name: Digital Biotechnology Lab
Web: www.digital-biotechnology.com
Location: Lyngby, Denmark (DTU campus)
PI: {name}
Direction terms: binder design, RFdiffusion, de novo design, protein engineering
Geography block: {the block's name in user/settings.toml [[geography.block]]}

{descriptive text from the lab's research / about / publications pages}
```

`TRACK:` is stamped by the parent during reconciliation — do not write it yourself.

---

## Where to Search

### Step 1 — Query recent high-impact papers (2022–present)

PubMed (E-utilities API) and Google Scholar (via the E-utilities endpoint):

The queries are the user's: `user/profile/search_terms.md` §Career track → *Paper queries*
(core first, then application flavours, then adjacent).

### Step 2 — Filter by journal impact

Prioritise the journals listed in the pack's `boards.md` §Group discovery.

### Step 3 — Extract group information

For each qualifying paper: corresponding/last author, institution, department, country, lab
website.

### Step 4 — Visit the lab page

Verify the lab website and save it into the output.

### For newly formed groups

- The pack's `boards.md` §Group discovery lists the grant-award pages (with the ERC funded-projects
  workflow) and institutional job pages that name newly funded PIs.
- Search Google with 5–10 keyword combinations.
- Search LinkedIn for **"new lab recruiting"** plus a direction term, or similar.

---

## Report

```
track: career
collected: N   -> user/workspace/inbox/_staging/career/
screened:  N
skipped:   N   (geo X · terms X · dedup X)
channels:  {which sources were queried}
```

---

## Related

[[search-common]] · [[search-groups-skill]] (the other track — same labs, different question) ·
[[background]] · [[preferences]] · [[inbox-eval]] · [[search-positions-career]] · [[search-companies-career]]
