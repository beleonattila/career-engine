---
name: inbox-eval
cssclasses: [skill]
recommended_model: Opus (high effort; budget: Sonnet high)
description: >
  Process every file in the career inbox. This is the single "thinking" stage of the
  pipeline: it reads the raw .txt files dropped by the search collectors
  (search-positions, search-companies, search-groups), routes each by its filename pattern
  (company-profile / group-profile / else a position), scores it, extracts CV-targeting keywords, and writes or updates the matching
  profile in the vault. Trigger on /inbox, "check inbox", "process inbox", "evaluate
  job ads", "build profiles from inbox", or whenever the user says they dropped files
  in the inbox. All scoring and database-building lives here — /search only collects.
---

# inbox

The **only** evaluation stage in the career pipeline. `/search` and the LinkedIn
collectors dump raw `.txt` into `user/workspace/inbox/`; this skill does all the thinking:
scores each item, extracts keywords for CV targeting, and builds the four databases.

```
COLLECT (Sonnet)         THINK — this skill (Opus)        PRODUCE (Sonnet)
/search-* ─► inbox ──┬─► user/workspace/organizations/companies/        ─┐
   raw .txt  (branch  │   user/workspace/organizations/research_groups/   ├─► /cv
  by filename)        │   user/workspace/positions/open/  (leads)    ─┘
                                └─► user/workspace/inbox/processed/
```

---

## Prerequisites

Verify before processing. Stop and tell the user if any is missing.

- `user/profile/background.md` + `user/profile/preferences.md` — master profile (identity, education, targets)
- `user/profile/competencies.md` — ranked, evidence-backed **technical** competencies
- `user/profile/soft_skills.md` — evidence-backed **soft** skills

The last two are the ground truth for what the user has. All scoring and every "matched strength"
must trace to them — the same evidence base `/cv` writes from.

---

## Input format

Every file written by a collector starts with a small header, then the body:

```
SOURCE: [url]
POSTED: [YYYY-MM-DD or unknown]     # positions only
FOUND:  [YYYY-MM-DD]
TRACK:  [career | skill]

[body — raw descriptive text (companies/groups) or full ad text (positions)]
```

**`TRACK:` says which search found it**, stamped by `reconcile_staging.py` when the two parallel
collectors are merged. Copy it into the profile's frontmatter, translating the name:

| Header | Frontmatter | Meaning |
|---|---|---|
| `TRACK: career` | `track: career` | Found by the direction search — on the preferred direction |
| `TRACK: skill` | `track: employability` | Found by the competency search — direction irrelevant, skills fit |

A file with **no** `TRACK:` header is a legacy collection or a manual drop: write
`track: career` (`engine/docs/decisions.md` §Two tracks).

**`track` is provenance, not a verdict.** It must never influence any score. A skill-track record
can still score high on direction: the searches overlap, and career wins collisions.

**Routing is driven by the filename.** If a filename matches no pattern and the file is not
obviously a job ad, move it to `user/workspace/inbox/processed/misc/` and flag it. Never guess from junk.

| Filename contains | Kind | Output |
|---|---|---|
| `_company-profile_` | companies | `user/workspace/organizations/companies/[slug].md` — durable company entry |
| `_group-profile_` | groups | `user/workspace/organizations/research_groups/[slug].md` — durable group entry |
| neither (a position file) | positions | `user/workspace/positions/open/[slug].md` — persistent lead (status + deadline) |
| neither, role title is PhD / doctoral / fellowship | phd | `user/workspace/positions/open/[slug].md` with `type: phd` |

---

## Workflow

### Step 0 — Archive stale processed files (run first, every time)

**Before anything else**, move every `.txt` in `user/workspace/inbox/processed/` whose collection date is
**older than 2 weeks** (14 days before today) into `user/workspace/inbox/processed/archive/`.
The subfolders `archive/` and `misc/` are never touched by this step.

> ⚠️ **Archiving is folder hygiene only — it does NOT retire a file from dedup.** `archive/` is live
> dedup surface: `/search-positions` globs it alongside `processed/`, `user/workspace/inbox/` and
> `user/workspace/positions/{open,applied,closed}/`. Never restore "no need to check archive", and
> never re-add an age filter to make it true (`engine/docs/decisions.md` §Archiving is not retirement).

The collection date is the **`FOUND:` header inside each file** (a copy or edit resets the
modified-time). Fall back to last-modified time only for a legacy file with no `FOUND:` header.
Command (PowerShell, from the repo root):

```powershell
$cutoff = (Get-Date).AddDays(-14)
Get-ChildItem "user/workspace/inbox/processed" -File -Filter *.txt | ForEach-Object {
  $m = Select-String -Path $_.FullName -Pattern '^FOUND:\s*(\d{4}-\d{2}-\d{2})' -List
  $found = if ($m) { [datetime]::ParseExact($m.Matches[0].Groups[1].Value,'yyyy-MM-dd',$null) }
           else    { $_.LastWriteTime }   # fallback: legacy file with no FOUND: header
  if ($found -lt $cutoff) { Move-Item $_.FullName -Destination "user/workspace/inbox/processed/archive/" }
}
```

Report how many files were archived (e.g. "Archived 12 processed file(s) older than 2 weeks."),
then continue. If none qualify, say so briefly and continue.

### Step 1 — Scan inbox

List every `.txt` in `user/workspace/inbox/` that is not already under `user/workspace/inbox/processed/`.
If none (after Step 0): report "Inbox is empty." and stop.

### Step 2 — Load profile once

Read the four prerequisite files once and hold them for the whole run.

### Step 3 — Process files one at a time

**Process each file independently: read it, evaluate it, write/update its profile,
archive it, then move to the next.** Never load all inbox files into context at once.

For each file:

1. Read the file; infer its type from the filename (see *Input format*).
2. **Dedup / merge check** (see *Dedup, merge & freshness* below): does a profile for
   this org/role already exist? If yes, you will update it, not duplicate it.
3. Route to the matching handler (companies / groups / positions / phd).
	3.5 If it is a company or a research group then search the web and gather information for profiling.
4. Score `career_fit`, `method_fit` **and** `skill_match` for every kind; add `level_fit` and `bench_load` (reported, never scored) for positions/phd.
5. Extract keywords (see *Keyword extraction*).
6. Write the new profile, or merge into the existing one.
   **A position or PhD scored `method_fit` ≥ 75 is a method sighting** — log it, whatever its
   other scores (why: [[search-positions-skill]] §Method lane):
   ```bash
   python engine/tools/method_sightings.py add --org <orgslug> --title "<title>" --url <url> \
       --signal "<the role-text sentence that shows the build seat, verbatim>" --outcome scored --source inbox
   ```
   It deduplicates on URL, so a role the skill track already logged is not counted twice.
7. Move the source `.txt` to `user/workspace/inbox/processed/` (or `processed/misc/` if junk).

### Step 4 — Ranked summary

After all files, print one summary grouped by kind, **sorted by `career_fit` descending**
(format at the end of this file) — "what is most worth wanting", with `method_fit`, `skill_match`
and `level_fit` shown alongside.

### Step 5 — Apply the org floor, then refresh the dashboard (always, every run)

**First run `python engine/tools/org_floor.py --apply`** from the repo root. It lifts any company or
group scoring below its best linked position (*Step 4 — the org floor* under Scoring) and must run
before the dashboard reads the scores. Report its LIFTED / RELEASED lines, if any. A new position
can lift an org this run never touched — that is intended.

**Then `python engine/tools/method_sightings.py --apply`**, which writes `method_roles_seen` /
`last_method_role` onto the org profiles from the sightings log (derived fields — never edit them by
hand). Run it after this batch's org profiles exist. Report any org it lists as having no profile.

**Then always run `/dashboard`** (`engine/skills/dashboard.md`), on every `/inbox` run, even when
the inbox was empty or nothing changed. The only exception: if `/inbox` aborted before writing
anything (e.g. a missing prerequisite), skip the refresh and say why.

---

## Scoring — the one place it lives

Scoring for **all** kinds happens here and nowhere else (`/search` does not score).
**Three independent numbers, never blended.** A record high on one and low on another is
information, not a contradiction.

| Field | Question | Applies to |
|---|---|---|
| `career_fit` (0–100) | **Is this the science I want?** How close is the work to the user's direction (`user/profile/preferences.md` §Scoring)? | positions · phd · companies · groups |
| `method_fit` (0–100) | **Is this the work I want?** Does the seat *build* methods, tools and systems — or only operate them? | positions · phd · companies · groups |
| `skill_match` (0–100) | **Can I do this?** How much of the work can be evidenced from user/profile/competencies.md? | positions · phd · companies · groups |
| `level_fit` (badge) | Is the seniority attainable today? | positions · phd only |

`skill_match` and `method_fit` are **holistic judgements against their anchor bands** — not
weighted sums of sub-criteria. `career_fit` is **one judgement (the band) plus the user's yes/no checks
read off a lookup table** — still direction only, and bounded inside its band so the checks can never
outvote the method. Write each number, then one sentence of justification naming the band
(and, for `career_fit`, the checks).

`fit_score` and `verdict` were deleted; never reintroduce a blended score (why:
`engine/docs/decisions.md` §Why two scores).

### `career_fit` — direction: a band, then three checks (0–100)

Rubric: **scoring v3** — a band, the user's checks, and the org floor (`engine/docs/decisions.md`
§Scoring v3). The number is built in four steps. Only step 1 is a judgement; steps 2–3 are yes/no checks and a
table lookup; step 4 is a script.

#### Step 1 — the band (the one judgement)

**What the bands mean is the user's.** Read `user/profile/preferences.md` §Scoring → *Bands*: the
direction question, its two pillars (the **method** and the **deliverable**), the A–E anchors, and
which variations score alike within a band. The scale is fixed for every user:

| Band | Range | Shape — the anchors in preferences.md decide |
|---|---|---|
| **A** | 90–100 | Dead centre: both pillars — the method **and** the deliverable. |
| **B** | 75–89 | Core, one pillar partial. |
| **C** | 50–74 | Adjacent: no deliverable. |
| **D** | 30–49 | Weak: the domain is present, neither pillar is. |
| **E** | 0–29 | Off-direction. Judged holistically inside 0–29; the checks do not apply. |

**Orgs are banded by their most on-direction line, not their average.** A company or group takes
the band of its most on-direction **stated, active** line of work — a named team, platform,
programme, publication stream or posting. Breadth never lowers it (examples in `user/profile/preferences.md` §Scoring). A *token*
mention (one sentence on a careers page, no team, no output) is not a line.

> ⚠️ **Score the role, not the employer** (`engine/docs/decisions.md` §Score the role). The
> employer's direction is already carried by its own profile; scoring it again double-counts it.
>
> So: **a support, infrastructure, deployment, platform, advisory or customer-facing seat scores
> what the seat ships**, wherever it sits. Ships integrations, pipelines or tooling → **30–49**.
> Ships advice about other people's work in the direction, or analysis with no deliverable →
> **50–74**. It reaches 75+ only when the person named in the ad personally ships the band-A
> deliverable (`user/profile/preferences.md` §Scoring names it). The phrase "but this seat…" in a
> justification is a reliable sign the number above it is too high.

#### Step 2 — the checks (yes / no)

The user's checks — `user/profile/preferences.md` §Scoring → *Checks* — place a record inside its
band. That section says what each check means, what it is worth and where it is read; the names
and units the tools accept are in `user/settings.toml` `[career_fit.checks]`. A check is ✓ only on a
stated fact.

**Where checks are read**, in general: for an org, on the line that set its band; for a position, a
project-level check on the project and a team-level check on the seat's own team — a support,
infrastructure, platform or customer-facing seat inherits no team-level check (score the role, not
the employer).

#### Step 3 — the lookup

The checks place the record **inside** its band and can never lift it out: an adjacent lab with
every check still sits below a plain dead-centre role. Score = band floor + round(units ÷ maximum
units × band width), where the maximum is the sum of the full checks in `user/settings.toml`.

**Do the lookup with the script, never by hand:** `python engine/tools/career_fit.py A "<checks>"`
prints the number; `python engine/tools/career_fit.py` prints the whole table for your checks.

Ties are expected and accepted — `skill_match` sits beside every row.

Record both inputs in frontmatter, so any score can be re-derived by script:

    career_fit: 97
    career_band: A
    career_checks: <check names from user/settings.toml, comma-separated>   # or: none

Justification format (a worked example is in preferences.md §Scoring):
**Career fit:** N/100 — band X (what sets it); <check> ✓/✗ (the stated fact) · … → U units.

#### Step 4 — the org floor (mechanical)

**An organisation never scores below its best linked position** — open, applied *or closed* (an
expired posting still proves the org does the work). Nobody judges this:
`python engine/tools/org_floor.py --apply` enforces it in Step 5. Positions are linked to profiles by
`org_match.py` (the dashboard's matcher); a position's `org_profile:` overrides it.

When the floor binds, the script sets `career_fit` to the position's score and keeps the org's own
judgement beside it (`career_fit_own`, `career_fit_floor`, `career_fit_floor_from`) plus a History
line; `career_band` / `career_checks` remain the org's own. **When you re-judge an org, write your
number to `career_fit` and delete the three floor fields** — the script restores the floor. Never
hand-edit a floor value. `python engine/tools/org_floor.py --candidates` also lists well-scored positions whose
employer has no profile yet.

The floor only runs upward: a position is never lifted toward its employer — that is the *score
the role* rule above.

**Nothing else enters this number.** Not location, salary, prestige, seniority, company size or
funding. `prestige_tier` carries standing as its own field — do not double-count it. No check is a
back door for prestige: checks read the work, never the employer's standing.

### `skill_match` — evidenced overlap only (0–100)

The one question: **of the tools, methods and skills this ad names, how many can be
evidenced from `user/profile/competencies.md` or `user/profile/soft_skills.md`?**

| Band | Anchor |
|---|---|
| **90–100** | Nearly every named tool and method is evidenced. Little or nothing to learn on arrival. |
| **75–89** | Every core requirement covered; one or two secondary or peripheral tools unfamiliar. |
| **50–74** | Majority covered, but a **named, significant** requirement is absent — e.g. the ad asks for RFdiffusion *and* PyRosetta and only one is evidenced. |
| **30–49** | Minority covered. The role's **central** method is one the user has not used. |
| **<30** | Little real overlap; the ad's stack is essentially foreign. |

**Scope discipline.** `skill_match` scores the *skills*, full stop. A PhD requirement, a
"5+ years" line, the city, the salary and the employer's reputation are **not** skills and
must not move this number — seniority is carried by `level_fit`, geography and pay are
reported unscored under *Logistics & Salary*, standing is `prestige_tier`.

**Grounding is mandatory.** Every point of `skill_match` must trace to a specific entry in
`user/profile/competencies.md` (technical) or `user/profile/soft_skills.md` (soft) — name the competency or
the evidence, do not invent. A requirement counts against the score only if it is genuinely
absent from both files.

#### `skill_match` for companies and research groups

An org advertises no requirements, so the question becomes: **how much of what this organisation
actually works on could the user do today?** Score the org's *stated technical work* — the methods,
tools and outputs named on its science / research / platform / publications pages — against
`user/profile/competencies.md`. Same 0–100 bands. This is the cold-outreach question ("could I be
useful here"); worked examples: `user/profile/preferences.md` §Scoring → *Worked examples: org scores*.

**Score only what the source states.** If the pages describe the science but never the stack,
score what the science *necessarily* implies (a structure-prediction group uses structure-prediction
tools) and no further. Never infer a stack from the sector or a big name.

### `method_fit` — does the seat build methods? (0–100)

Makes methods-building roles outside the direction visible **without touching `career_fit`**
(why: `engine/docs/decisions.md` §method_fit; `user/workspace/notes/rebrand_plan.md` §SPEC C).

The one question: **is the deliverable a method, tool, pipeline, platform or benchmark that other
people then use — or is the deliverable results produced by running something that already exists?**

| Band | Anchor |
|---|---|
| **90–100** | Building *is* the job. The seat ships methods, tools, pipelines, platforms, frameworks or benchmarks for others to use. Method development named in the ad; research engineer / scientific software / platform / tooling / infrastructure-for-science roles; a tool with no current owner. |
| **75–89** | Substantial building alongside application. New methods are expected and the person is trusted to invent them, but the headline deliverable is results or a paper. Most methods-flavoured research roles and PhDs land here. |
| **50–74** | Mixed. Applies existing methods, with real customisation, scripting or integration expected — but nothing is shipped for others. |
| **30–49** | Mostly operating. Runs established pipelines to produce results; building is incidental and unnamed. |
| **<30** | No building. Service analysis, ticket-driven support, routine reporting, pure wet lab, pure management. |

**Signals that raise it:** "develop methods/tools", "build a pipeline/platform/framework",
benchmark or evaluation work, heterogeneous unharmonised data from different sources, **domain
scientists as the end users** (the user would build it *and* teach them), frontier or unowned
tooling, first/only technical hire.
**Signals that lower it:** "run the standard pipeline", "respond to requests from scientists",
"deliver reports/dashboards", fixed SOPs, a large team where the method is already owned by someone
else.

**Score the seat, not the employer** — as for `career_fit`. A methods-heavy company whose seat runs
its existing product scores low; a small group where nobody owns the tooling scores high even if it
publishes no software. *"But the company builds tools"* in a justification means the number is too high.

**Independence.** `method_fit` is the **nature of the work**, never the domain (that is
`career_fit`) and never a familiar stack (that is `skill_match`). A genomics pipeline-engineering
role can be `career_fit` 35 · `method_fit` 92; a dead-centre design seat that only runs campaigns
can be `career_fit` 97 · `method_fit` 45. **Both are worth seeing; neither is a contradiction.**

**Nothing else enters this number.** Not location, salary, prestige, seniority or company size.
Record salary under *Logistics & Salary*, never in a score.

#### `method_fit` for companies and research groups

An org advertises no seat, so the question becomes: **would the user be the methods person here?** Score
the org's stated technical work — does it build its own methods and tools, and is there room for
someone to own them? An org that visibly needs technical ownership (a tool whose developer left, a
group whose science outgrew its tooling) scores **high**; an org whose methods are mature, owned and
staffed scores lower even when the science is excellent.

### `level_fit` — a badge, not a score

`level_fit: realistic | reach | below`. Non-numeric; contributes **nothing** to any score.

| Value | When |
|---|---|
| `realistic` | The ad asks for what the user holds today — degree, years of experience, seniority. `user/profile/background.md` §Level says what that is and what it means in practice. |
| `reach` | The ad requires something not held today: a degree the user lacks (a PhD, while they have none — this includes every postdoc call), more years of experience than they have, or a title above their level. |
| `below` | Beneath the qualification — internships, student assistantships, technician roles. |

**While the user holds no PhD, postdocs are `reach`, without exception** — the badge reports
today, not after a future doctorate. `reach` is not a rejection (`career_fit 95 · level_fit reach`
is a good record to see). Never soften the badge to make a lead look better.

Produce for every item: **`career_fit`**, **`method_fit`** and **`skill_match`**, plus **`level_fit`** for
positions/phd; **matched** (2–3 bullets), **gaps** (1–2 bullets, no softening), **angle**
(one sentence — the single strongest framing for an application).

### Logistics reference — reported, never scored

> ⚠️ **Logistics scores nothing.** Report location and pay plainly under **Logistics & Salary**
> and let the user weigh them. Never let either move any score
> (`engine/docs/decisions.md` §Logistics and prestige).

Work-arrangement preference, how to describe each situation, and the country salary ranges for
the user's level: `user/profile/preferences.md` §Logistics & salary. For the prose only.

**Salary** (positions/phd): if stated, compare to that table and flag below/at/above market; if
not stated, give the country-typical range as context.

**Bench load** (positions/phd only) — `bench_load:` how much **wet-lab work the seat itself**
requires, read off the ad's duties and requirements. **Reported, never scored** (moves no score).
How the user feels about bench work lives in `user/profile/preferences.md`.

| Value | When |
|---|---|
| `none` | A computational seat. Working *with* an experimental team, or the org testing its designs, does not count: that is the `validation` check, not the seat's bench work. |
| `light` | Bench work is occasional, optional, or a minority of the role: "support experimental colleagues", "some lab work", "hands-on lab experience is a plus". |
| `substantial` | Bench work is a core duty or a hard requirement: running assays, cloning and expression, cell culture, a 50/50 or wet-lab-first role, "hands-on lab experience required". |
| `unknown` | The ad does not say enough to tell. Never guess `none` from silence. |

Report it under **Logistics & Salary** as `**Wet lab in the seat:** [value] — [the ad's own words]`,
quoting the phrase that decided it.

### Prestige reference

Tiers: `elite` (1) · `strong` (2) · `established` (3) · `early_stage` (4). What each means in the
user's field is the domain pack's `prestige.md` (`engine/packs/<pack>/`, `<pack>` = `search.pack`
in `user/settings.toml`).

> ⚠️ **Prestige scores nothing.** `prestige_tier` is its own field and dashboard column; never let
> it move `career_fit` (`engine/docs/decisions.md` §Logistics and prestige).

Record the tier, 2–3 concrete signals (funding, revenue, h-index, journal tier, grants),
and a one-line rationale. Look up signals with WebSearch/WebFetch when the raw text is thin.

### Slugs

- `OrgSlug` — org name, lowercase, hyphens (`novo-nordisk`)
- `RoleSlug` — role in 2–3 words (`structural-bioinformatician`)
- `GroupSlug` — `[institution-abbrev]-[pi-surname]` or lab-name (`opig-deane-oxford`)
- `DateSlug` — `YYYY-MM` from today

---

## Keyword extraction (all kinds)

Every profile carries a **Language Patterns** block — the fuel `/cv` uses for targeting.

- **Identity & culture** — value/mission/relational words revealing personality
  ("connecting", "precision", "impact", "native", "designed").
- **Technical keywords** — domain and tool terms ("structural", "pipeline",
  "antibody", "RFdiffusion", "GPCR").

**Frequency counts:** include `×N` **only** when the source is real ad or posting text where terms
genuinely repeat (positions/phd, dense careers copy). For narrative snapshots (most company/group
text), never fabricate counts — list the term with a short context phrase instead.

Minimum 4 entries per list where the source supports it.

---

## Dedup, merge & freshness

`/search` dedups by **identity, not age** — there is no staleness skip (`engine/docs/decisions.md`
§No staleness skip). A file arriving here is new, a new role at a known org, or a deliberate
refresh. Inbox is the **authority** on merging.

1. Check `user/workspace/organizations/companies/`, `user/workspace/organizations/research_groups/`, `user/workspace/positions/open/`,
   `user/workspace/positions/applied/`, and `user/workspace/inbox/processed/` for an existing entry.
2. **If none:** create the profile.
3. **If one exists:** **merge, do not overwrite.**
   - Update factual frontmatter (location, funding, prestige, `career_fit`, `method_fit`,
     `skill_match`, and for positions/phd `level_fit` and `bench_load`) and refresh `last_evaluated` to today.
   - If the file has no `method_fit`, score and add it (whatever its `scoring:` stamp).
   - Leave `method_roles_seen` / `last_method_role` alone on an org: `method_sightings.py --apply`
     owns them (Step 5).
   - If the existing file carries anything but `scoring: v3`, re-judge `career_fit` under the v3
     rubric (band + checks, writing `career_band` / `career_checks`) and stamp `scoring: v3`. A
     `scoring: v1` or unstamped file: also rescore `skill_match` and delete its `fit_score` and
     `verdict`. Never carry an older number forward as a v3 one. On an org, delete any
     `career_fit_own` / `career_fit_floor` / `career_fit_floor_from` before writing — Step 5's
     `org_floor.py` restores the floor.
   - Append newly found roles to `open_positions`; never drop existing ones.
   - `schema_version` is the record *format* (`engine/tools/schema.py` `SCHEMA_VERSION`; the
     templates below write the current one), separate from `scoring:`. If an existing file's stamp
     is missing or older, run `python engine/tools/schema.py --apply` before merging — never edit
     the stamp by hand.
   - **Preserve the `## Notes` / manual sections verbatim** — only auto-generated
     sections may be rewritten.
   - Add a one-line entry to `## History` describing what changed.
4. **Positions:** if the same org+role already exists, update its `status`/`deadline`
   rather than creating a duplicate. Different role at the same org = new file.

**Org-name aliases (normalise before the dedup check).** The same employer can arrive under
different slugs (an acquisition, a group vs its parent). Resolve the org to a canonical slug with
`user/workspace/organizations/aliases.toml` — the table `dedup_check.py`, `org_match.py` and the
dashboard read — and add any new rename or acquisition there. When the canonical org + role matches
an existing profile/position, **merge or skip** — never create a second file under the alias.

---

## Handlers

### companies → `user/workspace/organizations/companies/[OrgSlug].md`

```markdown
---
name: "[organization]"
type: [pharma_company | biotech | tech | other]
cssclasses: [company]
location: "[city, country]"
country: [ISO]
remote_policy: [on_site | hybrid | remote_eu | remote_worldwide | unknown]
prestige_tier: [elite | strong | established | early_stage]
career_fit: [0–100]           # band + checks (lookup table), then org_floor.py — is this the science I want?
career_band: [A | B | C | D | E]
career_checks: [none | check names from user/settings.toml, comma-separated]
method_fit: [0–100]           # would I be the methods person here? (builds tools vs operates them)
skill_match: [0–100]          # can I do what they actually work on? (org stack vs user/profile/competencies.md)
track: [career | employability]   # provenance: which search found it. Never a verdict
scoring: v3
last_evaluated: [YYYY-MM-DD]
contact_status: not_contacted
open_positions: []
salary_range: [stated or null]
url: "[careers or homepage url]"
schema_version: 2
---

## Summary
[2–3 sentences: what they do and why relevant to the profile]

## Prestige
**Tier:** [tier]
- [signal] · [signal] · [signal]

## Why Relevant
- [concrete overlap] ...

## Key People
<!-- add manually / via /search -->

## Open Roles Noted ([date])
- [role + location, if any were in the source — else omit this section]

## Language Patterns
**Identity & culture** — mirror in cover-letter tone:
1. ...
**Technical keywords** — use in CV and cover-letter body:
1. ...

## Gaps
- [missing skills / logistics, direct]

## History
- [YYYY-MM-DD]: Profile created from /inbox (companies) · [source note]

## Related
[[slug]] (why) · [[slug]] (why)

## Notes
<!-- manual; preserved across merges -->
```

### groups → `user/workspace/organizations/research_groups/[GroupSlug].md`

Score `career_fit`, `method_fit` **and** `skill_match`, as for a company.
**Faculty filter:** if the source is an Assistant Professor / Professor / Group-Leader
*recruitment call* (a faculty opening, not a PhD/postdoc), do not create a group profile — flag and
skip; that is years away.

```markdown
---
name: [Full lab or centre name]
type: research_group
cssclasses: [research-group]
location: [City, Country (Institution)]
country: [ISO]
remote_policy: [on_site | hybrid | remote_eu | unknown]
prestige_tier: [elite | strong | established | early_stage]
career_fit: [0–100]           # band + checks (lookup table), then org_floor.py — is this the science I want?
career_band: [A | B | C | D | E]
career_checks: [none | check names from user/settings.toml, comma-separated]
method_fit: [0–100]           # would I be the methods person here? (builds tools vs operates them)
skill_match: [0–100]          # can I do what they actually work on? (org stack vs user/profile/competencies.md)
track: [career | employability]   # provenance: which search found it. Never a verdict
scoring: v3
last_evaluated: [YYYY-MM-DD]
contact_status: not_contacted
open_positions: []
salary_range: null
schema_version: 2
---

## Summary
[2–3 sentences: what the group does, key tools/outputs, current direction, notable grants/papers]

## Why Relevant
- [name the exact thesis method or skill that maps]

## Key People
- **[PI name]** ([role]) — [email if known] · [lab website]

## Language Patterns
**Identity & culture** — mirror in cold-outreach tone:
1. ...
**Technical keywords** — use in CV and cover-letter body:
1. ...

## Gaps
- [what's missing vs this group's needs, or logistics]

## Tension
[optional — one paragraph if methodology overlaps but domain diverges]

## History
- [YYYY-MM-DD]: Profile created from /inbox (groups) · [source note]
- [next action: email X, monitor Y]

## Related
[[slug]] (why) · [[slug]] (why)

## Notes
<!-- manual; preserved across merges -->
```

### positions → `user/workspace/positions/open/[OrgSlug]_[RoleSlug]_[DateSlug].md`

Persistent lead. Carries `status` (lifecycle: `evaluating → open → applied →
closed/expired`) and `deadline`. Never deleted — when applied, status becomes `applied`
(and `/cv` or the user moves the file to `user/workspace/positions/applied/`); when the deadline passes,
status becomes `expired` but the record stays for history.

```markdown
---
role_title: [role_title]
organization: [organization]
org_profile:                 # optional — slug of the owning user/workspace/organizations/ entry, or `none`.
                             # Only set it when the automatic match is wrong (see below).
org_type: [type]
location: [city, country]
country: [ISO]
remote_policy: [policy]
bench_load: [none | light | substantial | unknown]   # wet-lab work in the seat; reported, never scored
salary: [as stated or null]
salary_context: [at_market | above_market | below_market | not_stated]
prestige_tier: [tier]
deadline: [YYYY-MM-DD or null]
career_fit: [0–100]          # is this the science I want — band + checks, read off the lookup table
career_band: [A | B | C | D | E]
career_checks: [none | check names from user/settings.toml, comma-separated]
method_fit: [0–100]          # is this the work I want — does the seat build methods or operate them?
skill_match: [0–100]         # can I do it — evidenced tools/methods only
level_fit: [realistic | reach | below]   # badge; scores nothing. Postdoc ⇒ always reach
track: [career | employability]          # provenance: which search found it. Never a verdict
scoring: v3
url: [url]                   # LinkedIn ⇒ store the canonical https://www.linkedin.com/jobs/view/<id>
url_status: unchecked        # working | unverified | unresolved | dead | unchecked
url_checked: null            # YYYY-MM-DD
source_file: user/workspace/inbox/processed/[filename]
created: [YYYY-MM-DD]
last_evaluated: [YYYY-MM-DD]
status: evaluating           # expired ONLY if deadline strictly before today, or posting confirmed removed
schema_version: 2
---

## Role
[2–3 sentences]

## Fit Assessment
**Career fit:** [N]/100 — band [A–E] ([why]); [check] ✓/✗ ([the stated fact]) · … → [units] units
**Skill match:** [N]/100 — [one sentence naming the band and the decisive requirement]
**Level:** [realistic | reach | below] — [what the ad asks for vs the user's level, `user/profile/background.md` §Level]
**Matched strengths:** [bullets — each traceable to user/profile/competencies.md / user/profile/soft_skills.md]
**Gaps:** [bullets]
**Recommended angle:** [one sentence]

## Logistics & Salary
**Work arrangement:** [...] · [city, country]
**Geographic fit:** [...]
**Salary stated:** [...] · **Market range ([country]):** [...] · **Assessment:** [...]
**Wet lab in the seat:** [none | light | substantial | unknown] — [the ad's own words]

## Prestige
**Tier:** [tier]
**Key signals:** [bullets]

## Key Requirements
- [bullets]

## Language Patterns
**Identity & culture:** 1. word ×N — "phrase"
**Technical keywords:** 1. word ×N — "phrase"

## Notes
<!-- manual -->
```

**`org_profile:` — leave it blank almost always.** The position→profile link is automatic
(`dedup_check.py`'s alias table and org-token rules). `/dashboard` uses it to date the last CV sent
to each employer, and `org_floor.py` uses it to floor each org's `career_fit`, so a wrong match
inflates a score as well as mis-dating a CV. Set this field only to correct a wrong match:

- **A sibling group in the same department.** A posting naming its lab but not its PI is
  indistinguishable from its neighbours. Point it at the right group: `org_profile: <group-slug>`.
- **A funder or parent whose name is in the employer's name.** `org_profile: none` suppresses the
  match entirely.
- **An incubator or host that is not the employer.** Also `org_profile: none` — otherwise the host
  is floored to its tenant's score.
- **A group whose name shares no token with its posting.** Point it at the group's slug.

The cases from this vault that produced these four: `engine/docs/decisions.md` §org_profile.

**`url:` — normalise LinkedIn to the canonical form before writing it.** A collector's `SOURCE:`
for LinkedIn is often `linkedin.com/ad-library/job/detail/<id>`. **Rewrite it to
`https://www.linkedin.com/jobs/view/<id>`**, keeping the numeric id. The ad-library surface
**returns HTTP 200 for expired postings**, and `url:` is the link a human clicks and `/cv`
pre-flights (`engine/docs/decisions.md` §LinkedIn URLs).

`url_status` values: `unchecked` (never verified) · `working` (verified live — **never valid for a
LinkedIn lead**) · `unverified` (a page was served but liveness cannot be established; the normal
LinkedIn outcome) · `unresolved` (the stored URL is a search page or board root and can never
confirm anything) · `dead` (confirmed removed).

> ⚠️ **Never write `url_status: working` for a LinkedIn URL.** LinkedIn renders its expiry banner
> client-side, so an unauthenticated fetch cannot tell dead from live. `link_check.py` returns only
> `DEAD` or `UNVERIFIED` for LinkedIn; `expire_sweep.py` reports any `working` stamp under `⚠ unproven`.

Write the `org_profile:` slug bare (`some-group-slug`), with no inline `#` comment — the
frontmatter parser takes everything after the colon as the value.

### phd → `user/workspace/positions/open/[OrgSlug]_[RoleSlug]_[DateSlug].md` with `type: phd`

Same template and lifecycle as positions, with these differences:
- Add `type: phd` to the frontmatter.
- Score all three fields as for positions (PhD stipends use the stipend column of the salary
  table in `user/profile/preferences.md`). For a user without a PhD, a PhD call is
  `level_fit: realistic` — it is the qualification an MSc is *for* — and a **postdoc** is
  `level_fit: reach`, always.
- Academic framing: under **Logistics & Salary**, report the stipend and the supervising
  PI/group; cross-link the matching `user/workspace/organizations/research_groups/` entry under **Related**
  if one exists.

---

## Edge cases

| Situation | Action |
|---|---|
| Filename matches no pattern and not obviously a job ad | Move to `user/workspace/inbox/processed/misc/`; flag in summary |
| Recognised file but body empty/garbled | Skip; move to `processed/misc/`; flag |
| Company snapshot lists no open roles | Normal — the profile is the deliverable; omit "Open Roles Noted" |
| Profile already exists (<3mo, manual drop) | Merge anyway; preserve Notes; refresh `last_evaluated` |
| Same org+role position already exists | Update status/deadline; do not duplicate |
| Faculty (professor/group-leader) recruitment call | Do not profile; flag and skip |
| Deadline already passed | Create/keep record, set `status: expired`, flag in summary |
| Non-English ad | Process normally; add `language: [lang]` to frontmatter |
| Position `SOURCE` is a portal/search page (not a single posting), or the text is "reconstructed"/"inferred" | Do **not** trust it: set `url_status: unresolved`, keep requirements out of the scored "matched/gaps", and flag in the summary that the ad needs re-verification. `/search` should not produce these — flag it. |
| Salary ambiguous (equity/bonus) | Record as-is; note components; do not collapse to one number |

---

## Output Format

```
── Inbox Evaluation ─────────────────────────────────────────────
                    career · skill · level
COMPANIES                                   (no level — no advertised role)
  [NN] · [NN] ·  —   [Org] — [tier] · [city, country]
    ✓ [matched]   △ [gap]   ↳ [angle]
    → user/workspace/organizations/companies/[slug].md  [created | updated]

GROUPS                                      (no level — no advertised role)
  [NN] · [NN] ·  —   [Lab] — [PI] · [institution]
    → user/workspace/organizations/research_groups/[slug].md  [created | updated]

POSITIONS / PHD
  [NN] · [NN] · [level]   [Org] — [Role]  (deadline [date], status [x])
    → user/workspace/positions/open/[slug].md  [created | updated]
─────────────────────────────────────────────────────────────────
Processed [N] file(s): [c] companies · [g] groups · [p] positions · [phd] phd · [m] misc.
Run /cv [profile path] to generate targeted application materials.
```

---

## Related

[[background]] · [[preferences]] · [[competencies]] · [[search-positions]] · [[search-companies]] · [[search-groups]] (collect the .txt this skill processes) · [[cv-generate]] (consumes the profiles this skill builds)
