---
name: rescore
cssclasses: [skill]
recommended_model: Opus (high effort — this is scoring, same tier as /inbox)
description: >
  Migrate vault records to scoring v3: re-judge `career_fit` as a band (A–E) plus the user's checks
  (user/profile/preferences.md §Scoring) read off the lookup table, score the new `method_fit`,
  and stamp `scoring: v3`. `skill_match` and `level_fit` are untouched. Resumable: works a batch, applies the org floor,
  and stops. Run it repeatedly until `python engine/tools/rescore_status.py` reports 100%. Trigger on
  /rescore, "continue the rescore", "migrate the scores", or when the dashboard warns that
  records still carry a v2 career_fit.
---

# rescore

A one-time migration, run many times. On **2026-09-10** `career_fit` was redefined at the user's
instruction — scoring v3, rubric in [[inbox-eval]] §career_fit. Every record scored before that
date (364, stamped `scoring: v2` or `v2.1`) carries a number judged under rules that no longer
exist: *wet lab is neutral*, *the application never moves the number*, *MD without a design
output is only adjacent*, and orgs scored on the average of everything they do. This skill
re-judges them in batches that survive context limits.

**Only `career_fit` is re-judged, and `method_fit` is added.** `skill_match` and `level_fit`
answer questions neither change touched; re-judging them would turn a bounded migration into an
unbounded rescore and silently recalibrate two fields nobody asked to move.

> 🆕 **`method_fit` rides along (added 2026-09-29).** A third score — *does the seat build methods,
> tools and systems, or only operate them?* — was introduced for the rebrand (`user/workspace/notes/rebrand_plan.md`
> §SPEC C). It is **not** part of the v2 → v3 redefinition, but it has to be written onto all 382
> records, and the v3 pass was only 6% done when it landed. Doing both in one sweep saves a second
> full pass. **Score it for every file in the batch, including the ~22 already stamped `v3`** —
> `rescore_status.py` lists those as *need method_fit* and hands them back via `--next`.
> Rubric: [[inbox-eval]] §`method_fit`. It is a holistic judgement against anchor bands, with no
> lookup table and no script.

**Recommended model:** Opus, high effort — the same judgement `/inbox` makes, so the same tier. A
cheaper model here would write numbers that do not mean what `/inbox` writes tomorrow.

> **Earlier runs of this skill, both complete.** v1 → v2 (2026-08-17): the blended `fit_score`
> split into `career_fit` + `skill_match`, 364/364. v2.1 (2026-08-18): positions ≥ 75 re-checked
> under *score the role, not the employer*. Their instructions were removed when v3 replaced them;
> the History lines they left in each record are the record of what they did.

---

## The one thing to get right

**Do not convert the old number. Place the band, answer the checks, look the number up.**

A v2 `career_fit 92` does not mean band A, and a v2 org at 85 does not mean band B — v2 org
numbers averaged the whole portfolio, which v3 forbids. Read what the record says about the work
and answer, as if it had arrived in the inbox today:

1. **Band** — A–E per Step 1 of the rubric, against the anchors in `user/profile/preferences.md`
   §Scoring. **An org takes the band of its most on-direction stated, active line**, never its
   average. This is where most org numbers will move.
2. **Each check** in `user/profile/preferences.md` §Scoring → *Checks* — yes or no, on a stated fact,
   read where that section says (on the project, or on the seat's own team).

Then `python engine/tools/career_fit.py <band> "<checks>"` gives the number. **Never do the arithmetic by
hand** — `--verify` rejects any record whose number does not follow from its own band and checks.

Expect orgs to rise, often sharply (the average is gone and the checks are new), and positions
to move a few points either way.

---

## Prerequisites

Read once at the start of every batch and hold for the whole run:

- `engine/skills/inbox-eval.md` §**Scoring** — the `career_fit` subsection in full (bands,
  checks, lookup, org floor, *score the role, not the employer*) **and the `method_fit` subsection
  in full**. **The rubric lives there, not here.** Never restate it in this file; a second copy
  would drift from the one `/inbox` uses.
- `user/profile/preferences.md` §Direction and §Scoring — the direction statement, and the band
  anchors and checks that are the content half of the rubric.

`user/profile/competencies.md` and `user/profile/soft_skills.md` are **not** needed: they are the evidence base for
`skill_match`, which this migration does not touch. Leaving them out is what lets batches run large.

---

## Workflow

### Step 1 — See what is left

```bash
python engine/tools/rescore_status.py
```

Progress is derived from the `scoring: v3` stamp inside each file — there is no side-car ledger
to fall out of sync. Report the current percentage to the user before starting.

### Step 2 — Claim a batch

```bash
python engine/tools/rescore_status.py --next 30
```

Order is fixed and by value: `user/workspace/positions/open` → `user/workspace/positions/applied` → `user/workspace/organizations/companies` →
`user/workspace/organizations/research_groups` → `user/workspace/positions/closed`. **You never have to name a folder** — `--next`
walks that order itself, and re-offers any v3 record that `--verify` finds malformed.

| Set | mean file | `--next` |
|---|---|---|
| `user/workspace/positions/open` + `applied` | 4.7–7.2 KB | **30** |
| `user/workspace/organizations/companies` | 2.4 KB | **40** |
| `user/workspace/organizations/research_groups` | 4.5 KB | **25** |
| `user/workspace/positions/closed` | 4.0 KB | **40** |

One judgement per file, on a much lighter fixed context than the v1 → v2 run. Org batches are
smaller than their file sizes suggest because an org may need a web lookup (Step 3). If the user
passes a number (`/rescore 15`), that wins.

> **Do not shrink these "to be safe."** The fixed context is paid fresh in every session; halving
> the batch doubles that overhead without halving any risk.

**Run each batch in a fresh session.** A batch appended to a deep conversation hits
auto-compaction partway through, and the rest of the batch is then scored against a paraphrase of
the rubric — the calibration drift this migration exists to remove.

### Step 3 — Re-judge each file, one at a time

**Read the file.** The Role / Key Requirements (positions) or Summary / Why Relevant (orgs) were
written from the source and are normally enough. Do **not** refetch a position's posting — many
are long dead, and link health is `link_check.py`'s job.

**When the record is silent on a check:**
- **Position** — you may read the linked org profile (its `org_profile:`, or the obvious
  `user/workspace/organizations/` match) for the *team-level* checks, but only credit them if the seat sits inside
  that team (*score the role, not the employer*). No web. Still silent → ✗ "(not stated)".
- **Org in band A or B** — **one** web lookup is allowed per org (a WebSearch, or a WebFetch of
  the org's own research / platform / technology page) to settle a team-level check. Put what
  it found in the History line. Nothing found → ✗ "(not stated)".
- **Org in band C, D or E** — no lookup; the checks move it a few points at most. ✗ "(not stated)".

A check is ✓ only on a stated fact — a named lab facility or screening platform, a collaborator
named as testing the designs, an MD or directed-evolution line that appears in the work. Never
infer a wet lab from the sector, the headcount or the prestige.

**Edit the frontmatter:**

```yaml
career_fit: 97                          # python engine/tools/career_fit.py A "application, validation"
career_band: A
career_checks: application, validation  # none, or check names from user/settings.toml
method_fit: 45                          # judged against the anchor bands — no script, no lookup
scoring: v3
```

- Put `career_band` and `career_checks` directly under `career_fit`; overwrite `scoring: v2` /
  `v2.1` with `v3`. Write the slug-style values bare, with no inline `#` comment.
- **Orgs carrying a floor** (`career_fit_own` / `career_fit_floor` / `career_fit_floor_from`):
  write your own judgement to `career_fit` and **delete all three floor fields**. Step 4 restores
  the floor if it still binds. Never edit a floor by hand.
- Put `method_fit` directly under `career_checks`. **Judge it independently** — it asks whether
  the seat *builds* methods, not whether the science is on-direction and not whether the user could
  do it. A record already stamped `v3` needs nothing but this field (and its History line).
- **Do not touch** `skill_match`, `level_fit`, `track`, or any other field.

**Update the body:**

- **Positions / PhD** — replace the `**Career fit:**` line in `## Fit Assessment` with the v3 form:
  `**Career fit:** 97/100 — band A (ML de novo binder design); application ✓ (therapeutic) · validation ✓ (in-house screening) · package ✗ (one part in house) → 2 units`.
  Add a `**Method fit:**` line directly beneath it, one sentence naming the band:
  `**Method fit:** 45/100 — runs existing design campaigns; nothing shipped for others to use`.
  Leave Skill match, Level, Matched strengths, Gaps and Recommended angle as they are.
- **All kinds** — append one line to `## History` (never edit past lines — History is a log):
  `- YYYY-MM-DD: Rescored career_fit v2 → v3 · N → M · band X · application ✓/✗ (…) · validation ✓/✗ (…) · package ✗/½/✓ (…) · added method_fit M2 (…)`
  For a record already stamped `v3`, the line is just:
  `- YYYY-MM-DD: Added method_fit M2 (…)`
  For an org that carried a floor, N is its old `career_fit_own` (its own judgement), not the
  floored number. Recording N is deliberate: it is the only trace of the v2 judgement.

**Retired rules in the prose.** Many auto-written sections say "wet lab is neutral", "the
application does not move the number" or "the method is the identity". In a `**Career fit:**`
line they disappear with the rewrite. Elsewhere (Why Relevant, Gaps, Tension) fix a sentence only
if it presents a retired *scoring* rule as current — a Gap saying a role *requires* bench skills
he lacks is a skills fact and stays. **Never touch `## Notes`**; if a Note states a retired rule,
flag the file in the batch report instead.

### Step 4 — Verify, then apply the floor

```bash
python engine/tools/rescore_status.py --verify
python engine/tools/org_floor.py --apply
```

`--verify` catches half-applied edits on v3 records: a missing or invalid `career_band` /
`career_checks`, a number that does not follow from its own band and checks, band E with checks,
a partial or stale floor, a position carrying floor fields, a missing `skill_match`. **Fix
everything it reports before stopping** — `--next` keeps re-offering a malformed record.

The floor runs after verify on purpose: verify checks each org's own judgement, then the floor
lifts any org below its best linked position. Report its LIFTED / RELEASED lines.

### Step 5 — Report and stop

Print the batch result and the new overall progress, then stop. The user decides whether to
continue; a long unattended run is how a context limit lands mid-file.

> **The first batch sets the calibration for all 364 records**, and nothing re-reads earlier
> batches. So on batch 1 — and again on the **first org batch**, where best-line banding and the
> web lookups first apply — show every record's band and checks with its one-line reason and ask
> the user to sanity-check before continuing. Watch the edges of the application list (industrial
> enzymes, carbon capture and biomanufacturing platforms are ✗) and whether validation was granted
> on a stated fact.

```
── Rescore batch (v3) ───────────────────────────────────────────
  user/workspace/positions/open      30 records re-judged
    92 → 97   A  application, validation          [org] — [role]
    88 → 84   B  application, validation          [org] — [role]
    45 → 36   D  application                      [org] — [role]
  not stated: 4 checks · Notes flagged: 1 file
  verify: clean · org_floor: 0 lifted, 0 released
  progress: 30/364 (8%) — bands so far: A 12 | B 9 | C 6 | D 2 | E 1
─────────────────────────────────────────────────────────────────
Run /rescore again to continue (fresh session).
```

### Step 6 — When it reaches 100%

```bash
python engine/tools/org_floor.py --apply
python engine/tools/dashboard.py
```

The dashboard stops warning about a mixed `career_fit` scale once no record carries `v2`/`v2.1`.
`/rescore` and `rescore_status.py` can then be deleted — **keep** `career_fit.py`, `org_floor.py`
and `org_match.py`, which `/inbox` and the dashboard use permanently. Tell the user; do not delete
unasked.

---

## Edge cases

| Situation | Action |
|---|---|
| Record has no `career_fit` at all | Judge it normally; note `(was unscored)` in History. If `skill_match` or `level_fit` is also missing, flag it — do not score those here |
| Body too thin to place a band | Band from whatever the Role / Summary states and flag the file as thin. Never guess a band to fill the field |
| A closed / expired position | Re-judge it anyway — its score feeds the org floor and the telemetry. No web; keep it quick |
| An org whose only on-direction evidence is one of its positions | Band from the org's own stated work; the floor carries the position |
| Recruiter or confidential-employer ad | Checks from the ad text only; there is no org profile to read |
| `person_bio` or other non-entity doc in `user/workspace/organizations/` | Skip — not a scored record (`SKIP_TYPES`) |
| The fresh read says the record is badly wrong (wrong org, hallucinated role) | Do not fix it here. Stamp it, flag it, and tell the user to run `/track remove` |
| Already `scoring: v3` and `--verify` clean | `--next` never offers it. If passed by hand, leave it alone unless the user asks for a re-judgement |

---

## Related

[[inbox-eval]] (owns the rubric) · [[dashboard]] (warns while the migration is incomplete) ·
[[preferences]] (§Direction) · `career_fit.py` (lookup) · `org_floor.py` (org floor) ·
`rescore_status.py` (progress)
