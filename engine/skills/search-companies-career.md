---
name: search-companies-career
cssclasses: [skill]
recommended_model: Sonnet (low–medium) — unmeasured; the yield telemetry covers positions only
description: >
  CAREER track company collector. Builds the company database with employers working on
  the user's preferred direction (user/profile/preferences.md). Run as a sub-agent by /search-companies,
  in parallel with search-companies-skill. Writes raw .txt to user/workspace/inbox/_staging/career/ only.
  Does NOT score — that is /inbox's job.
---

# search-companies-career

**Track: career.** Building an ever-growing database of companies **working on the preferred
direction** (`user/profile/preferences.md`).

The company database is what unsolicited applications are sent from, so a profile here is a
cold-outreach target, not a job lead. `/inbox` scores it on both axes: `career_fit` (is this
the work) and `skill_match` (could the user be useful there).

**Read [[search-common]] first** — geography allowlist, staging protocol, `TRACK:` stamp.

Write every collection to **`user/workspace/inbox/_staging/career/`**. Never to `user/workspace/inbox/`.

---

## Task

1. **Check the current database.** List `user/workspace/organizations/companies/` and hold the names.
2. **Search for companies not on that list** whose work is on the direction.
3. **Check geography before fetching anything else** — [[search-common]] §Geography. A company
   with no site in an allowlist country is out of scope unless it hires remotely into one.
4. **Read its science / research / platform / pipeline / publications pages** and match against
   the user's direction terms (below).
5. **Collect iff ≥3 direction terms appear** in the company's own description of its work.
6. **Run the dedup guard before writing — mandatory (CLAUDE.md).**
7. **Report** collections, screened count, and channels queried.

## Direction terms (the collect test)

The terms are the user's: `user/profile/search_terms.md` §Career track → *Direction terms* — core
terms (any one is a strong signal), adjacent terms (count, but a company needs more than these
alone) and off-direction terms (never collect on these alone). The skill track will pick an
off-direction company up if its *stack* matches, which is a different question.

## Dedup guard — mandatory before any write

```bash
python engine/tools/dedup_check.py
```

Step 1's name list is **eyeball dedup, and eyeball dedup has demonstrably failed** — four
org-slug collisions in ten days (2026-07-29 … 08-08), each costing a fetch, an inbox write and a
full Opus scoring pass. Org-type words are stripped structurally, so `cradle` ≡ `cradle-bio` and
`cranfield` ≡ `cranfield-university` without anyone having to spot the collision first. Check a
single candidate before fetching its pages:

```bash
python engine/tools/dedup_check.py --query <org> "company-profile"
```

> ⚠️ **Known coverage gap — do not rely on the guard alone here.** `SEARCH_GLOBS` in
> `dedup_check.py` indexes `user/workspace/inbox/`, `user/workspace/inbox/processed/`, `processed/archive/` and
> `user/workspace/positions/{open,applied,closed}/` — it does **not** index `user/workspace/organizations/companies/` or
> `user/workspace/organizations/research_groups/`. Coverage of the 95 existing company profiles is therefore
> indirect, via the processed `.txt` each was built from, and a company whose source `.txt` has
> been pruned will read as new. Keep doing step 1's name-list check **as well**, and treat the
> guard as the backstop rather than the whole test.

> ⚠️ **The guard cannot see the skill track's staging folder.** Both sub-agents run at once. A
> company found by both is expected; the parent reconciles and career wins. Do not try to check
> the other folder.

---

## Output format

**file name:** `[orgslug]_company-profile_found-[YYYY-MM-DD].txt`
→ written to `user/workspace/inbox/_staging/career/`

**file content:**

```
SOURCE: https://www.novonordisk.com
FOUND: 2026-06-13

Name: Novo Nordisk A/S
Web: www.novonordisk.com
Location: Bagsværd, Denmark
Direction terms: de novo design, protein engineering, AlphaFold, peptide design
Geography block: {the block's name in user/settings.toml [[geography.block]]}

{descriptive text from the company's about / science / mission / pipeline pages}
```

`TRACK:` is stamped by the parent during reconciliation — do not write it yourself.

---

## Where to Search

The discovery sources are domain content: the pack's `boards.md` §Company discovery (career-track
list). Work through these systematically, session by session — do not restart from the top of the
list each run.

**Stop criteria:** 3 minutes of runtime.

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

[[search-common]] · [[search-companies-skill]] (the other track — same employers, different
question) · [[background]] · [[preferences]] · [[inbox-eval]] · [[search-positions-career]] · [[search-groups-career]]
