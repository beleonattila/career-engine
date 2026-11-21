---
name: search-common
cssclasses: [skill]
description: >
  Shared contract for all six search collectors (positions/companies/groups x career/skill).
  Not invoked directly — every search skill reads this first. Defines the two-track model,
  the geography allowlist, the staging protocol that keeps two parallel sub-agents from
  colliding, the `TRACK:` stamp, the skill track's competency gate, and the org collectors' dedup.
---

# search-common

**Not a command.** Read by all six collectors. If you are reading this without having been
sent here by one of them, you want `/search-positions`, `/search-companies` or `/search-groups`.

---

## The two-track model

Every kind is searched twice, in parallel, by two sub-agents that never see each other's context
(`engine/docs/decisions.md` §Two tracks):

| Track | Asks | Collects |
|---|---|---|
| **career** | Is this the work I want? | The direction in `user/profile/preferences.md` (the gate terms: `user/profile/search_terms.md`) |
| **skill** | Could I actually get and do this? | Anything the evidenced competencies in user/profile/competencies.md cover, direction irrelevant |

**The skill track has no direction floor, and that is deliberate.** The user's Expert-tier
competencies (`user/profile/competencies.md`) need not be their stated direction, so a search that
maximises skill match will surface roles, companies and labs built on those other competencies,
however off-direction — and the user's strongest credentials may sit there too
(`user/profile/search_terms.md` §Skill track says what that means for this profile). That is the
honest shape of the profile, not a malfunction. **Never add a direction filter to the skill
track.** `/inbox` records `domain_fit` on every record, so how off-direction a lead is stays
visible without suppressing it.

**The skill track is also where method roles come from.** `/inbox` records **`method_fit`** —
*does the seat build methods, tools and systems, or only operate them?* (rubric: [[inbox-eval]]
§`method_fit`; rationale: `user/workspace/notes/rebrand_plan.md`). Method roles in other fields
reach the vault only through this track — one more reason it keeps no direction floor. It looks for
them on purpose through the *method lane* ([[search-positions-skill]] §Method lane): the ATS sweep's
`M`/`Mb`/`M?` rows (build wording in the ad text, or a sighted employer — never method titles), a
second Gate 3 route (one method competency + a build signal), a sightings log of employers that post
such seats, and an org rotation that puts those employers first.

> ⚠️ **The career track stays direction-only.** Never collect on the career track because a role
> "builds methods" — that is `method_fit`'s job, not `domain_fit`'s.

Neither track scores. `/inbox` does all scoring, on Opus. A collector decides collect-or-skip
and writes the raw text down. Nothing else.

---

## Geography — one allowlist, both tracks

Enumerate as a country list. **Never** rely on a region token: LinkedIn's `location=European Union`
silently excludes CH, NO and the UK (`engine/docs/decisions.md` §LinkedIn geography tokens). Query
each block separately.

**The allowlist is the user's: read `user/settings.toml` `[[geography.block]]` before searching.**
Each block has a `name`, its `countries`, and a `note` — follow the note (it says, for example,
which block is preferred and what to record about a visa). A block with **`remote_only = true`**
is collected **only** when the ad itself states that remote work from one of the other blocks, or
from anywhere, is acceptable; an on-site role there is out of scope — do not fetch it, do not
write it. Check this **before the fetch**: if the listing page does not say, it does not qualify —
never open the ad to find out. (Leads collected under the older, looser rule stay:
`engine/docs/decisions.md` §Remote-only regions.) `ats_sweep.py` applies the same list to ATS
location strings.

**Everything else is out of scope before a single fetch.** Where a search surface cannot be
filtered by country, filter the result list before fetching any ad body, not after. Geography is a
collection budget, not a score threshold (`engine/docs/decisions.md` §Geography is not a score
threshold).

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
3. Accept that you **cannot** dedup against the other track mid-run. Do not try. Collecting
   something the other track also found is expected — overlap is the common case — and the parent
   resolves it, career winning.
4. **Never write `TRACK:` yourself** — the parent stamps it during reconciliation.
5. Report your collection count and the paths you wrote.

**The parent command then:**

1. Runs `dedup_check.py` across both staging folders together.
2. On a collision, **career wins**: keep the career copy, drop the skill copy. A lead that
   clears the career gate is one the user wants regardless of how well their skills fit it.
3. Stamps `TRACK: career` or `TRACK: skill` into the header of each surviving `.txt`.
4. Moves everything into `user/workspace/inbox/` and leaves both staging folders empty.

`/inbox` reads `TRACK:` from the header and writes it to the profile frontmatter as
`track: career | employability`. The dashboard's Employability tab reads that field.

> **Empty the staging folders even when a run collects nothing.** A leftover `.txt` from an
> interrupted run would be swept into `user/workspace/inbox/` by the *next* run's reconciliation and attributed
> to the wrong run in the telemetry.

---

## Skill track: the competency gate

All three skill-track collectors gate on the user's competency table
(`user/profile/search_terms.md` §Skill track — one table each for positions, companies and groups,
calibrated together). Mark a competency **PRESENT** iff the source evidences it — and only when it
is **central** (`engine/docs/decisions.md` §Skill track: a competency counts only when central).

A competency is **PRESENT** only if it describes **what the person (or the org) does**, not what
the employer would like them to have heard of:

| Counts | Does not count |
|---|---|
| Named in the primary responsibilities — "you will build/own/maintain X" | Buried in a requirements laundry list of a dozen technologies |
| The role is organised around it (a section, a repeated theme) | Mentioned once in passing |
| Named in the job title | Under "nice to have", "a plus", "what sets you apart" |
| The daily work is unimaginable without it | Listed as an acceptable degree field |

When a term appears only in a "bonus" or "differentiator" section, **record it and move on** —
note it in the Gate 3 line as `(noted, not counted)` so the decision stays auditable, but do not let
it reach the threshold.

**Collect iff ≥2 distinct counting competencies are PRESENT.** Tier-3 rows are recorded but never
count. One competency alone is not enough — nearly every computational ad, company or lab names
"machine learning" or Python somewhere, and a single generic overlap says nothing about whether the
user could be useful there. (Positions also have the method-lane route: [[search-positions-skill]].)

### Method sightings (companies and groups, skill track)

**Log any method-building seat you see** on a careers or jobs page — a role whose own text says it
builds tools, pipelines, methods or platforms that scientists use ([[search-positions-skill]]
§Method lane, the build signal) — whether or not the org is collected, and whether or not the user
could apply:

```bash
python engine/tools/method_sightings.py add --org <slug> --title "…" --url … --signal "<verbatim>" --outcome seen --source skill
```

An employer that posts build seats is the method lane's best target, and a lab whose tooling has
outgrown its people is the cold-outreach target the method brand is for.

---

## Org collectors: dedup

The four company and group collectors share one dedup procedure:

1. **Step 1's name list** — list `user/workspace/organizations/companies/` or
   `user/workspace/organizations/research_groups/` and hold the names. This is eyeball dedup, which
   has demonstrably failed (`engine/docs/decisions.md` §Dedup), so it is never the whole test.
2. **The guard, mandatory before any write** (CLAUDE.md):
   ```bash
   python engine/tools/dedup_check.py
   python engine/tools/dedup_check.py --query <slug> "company-profile"   # or "group-profile"
   ```
   Org-type words are stripped structurally, so `cradle` ≡ `cradle-bio`. Check a single candidate
   before fetching its pages.

> ⚠️ **Known coverage gap — keep both checks.** `SEARCH_GLOBS` in `dedup_check.py` indexes
> `user/workspace/inbox/`, `user/workspace/inbox/processed/`, `processed/archive/` and
> `user/workspace/positions/{open,applied,closed}/` — it does **not** index
> `user/workspace/organizations/companies/` or `user/workspace/organizations/research_groups/`.
> Existing profiles are covered only through the processed `.txt` each was built from, so one
> whose source `.txt` has been pruned reads as new. The guard is the backstop; the name list stays.

A group can also arrive under its PI, its lab name, or its parent institution (`nnf-cpd-ku` ≡
`ku-cpd` ≡ `university-of-copenhagen-cpd`). Renames and parent/child pairs are the one thing no
string rule derives — add them to the alias table (`user/workspace/organizations/aliases.toml`)
when you meet a new pair.

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
  answers, same verdict — holistic judgement is not reproducible (`engine/docs/decisions.md` §The
  collect decision).

---

## Related

[[background]] · [[preferences]] · [[competencies]] (the evidence base the skill track gates on) ·
[[search-positions-common]] · [[inbox-eval]] (the THINK stage — scores everything these collect)
