# Career Pipeline

The shared blueprint for how the skills, databases, and folders connect.
Three stages: **collect → think → produce.**

```
COLLECT (Sonnet)              THINK (Opus)                      PRODUCE (Sonnet)
─────────────────             ───────────────────────────      ────────────────────
/search-positions ┐              (search-positions covers industry + academic + PhD)
/search-companies │  raw .txt   ┌─► user/workspace/organizations/companies/      ─┐
/search-groups    ├───────────► │   user/workspace/organizations/research_groups/ │
                  │ (route by   │   user/workspace/positions/open/  (leads)  ├──► /cv ──► user/workspace/applications/
                  ┘  filename)  │   user/workspace/inbox/processed/          │    (solicited OR
                     inbox ────►└───────────────────────────  ┘     unsolicited)
        ▲                              /inbox
        │
        └── user/workspace/organizations/companies/ + user/workspace/organizations/research_groups/ feed back as
            search targets for /search-positions
```

## Stage contracts

| Stage | Skill(s) | Model | Does | Does NOT |
|---|---|---|---|---|
| **Collect** | `search-positions`, `search-companies`, `search-groups` | Sonnet* | Each fans out to **two parallel sub-agents** — a `career` track (direction) and a `skill` track (evidenced competencies) — writing to `user/workspace/inbox/_staging/{career,skill}/`; the orchestrator then runs `reconcile_staging.py --apply` (career wins a collision, stamps `TRACK:`) and merges into `user/workspace/inbox/` | Score, rank, write profiles, judge fit |
| **Think** | `inbox-eval` (`/inbox`) | Opus | Route by filename; score; extract keywords; build/merge every profile; manage position lifecycle | Search the web, write CVs |
| **Produce** | `cv-generate` (`/cv`) | Sonnet | Targeted CV + cover letter from a profile; apply writing rules + LaTeX | Score or search |

\* **Collect's model is provisional, not measured.** `log_run.py --stats` groups yield by
`model/effort/mode` and as of 2026-08-09 (16 runs) it cannot settle the question — per-run
collections range `0–8` *within* `sonnet/?` alone, so no cell is distinguishable at n=1–3.
What is separable: screening volume tracks **channel breadth** (8.3/run at ≤2 channels vs 30.2 at
5–6) while collections stay flat at ~2.0/run at every breadth. See *Model and effort* in
`engine/skills/search-positions-common.md` (the data: `engine/docs/decisions.md`).

**Scoring lives in exactly one place: `/inbox`.** Collectors never score; `/cv` consumes
scores but doesn't compute them. (`org_floor.py` adjusts org scores mechanically, but judges
nothing.)

**Three scores, never blended.** `domain_fit` (is this the science I want — direction only),
**`method_fit`** (is this the work I want — does the seat build methods or only operate them;
added 2026-09-29 for the rebrand) and `skill_match` (can I do it) all sit on every kind of record.
For a position `skill_match` reads the ad's requirements; for a company or group it reads the org's
stated stack, because the org databases are what unsolicited applications are sent from — and
`method_fit` asks "would I be the methods person here?". Only the `level_fit` badge is position/PhD-
specific — an org advertises no seniority. The retired `fit_score` averaged desirability against
winnability and hid exactly the tension worth seeing. Rubric: `engine/skills/inbox-eval.md` §Scoring.

## The routing contract

Every collected `.txt` begins with:

```
SOURCE: [url]
POSTED: [YYYY-MM-DD or `unknown`]   ← the posting's OWN publish date
FOUND:  [YYYY-MM-DD]

[raw body]
```

`POSTED:` is load-bearing, not decorative: `FOUND − POSTED` is the lag, and lag is the only way a
missed post is ever detected (see *Measuring recall* below). Position files additionally carry the
`Gate 1/2/3` audit block from `search-positions` step 7.

`/inbox` routes by **filename** — each search skill produces a distinct pattern:

| Filename contains | Kind | Body content | Output |
|---|---|---|---|
| `_company-profile_` | companies | About / Mission / Research / Projects / team / careers URL | `user/workspace/organizations/companies/[slug].md` |
| `_group-profile_` | groups | lab "about", projects, PI/people, recent papers, funding | `user/workspace/organizations/research_groups/[slug].md` |
| neither (position file) | positions | full ad text verbatim | `user/workspace/positions/open/[slug].md` (status + deadline) |
| neither, role = PhD | phd | full ad text verbatim | `user/workspace/positions/open/[slug].md` with `type: phd` |

## Databases

| Database | Built by | Nature | Used by |
|---|---|---|---|
| `user/workspace/organizations/companies/` | /inbox | durable; ~150–200 target | /search (targets), /cv (unsolicited) |
| `user/workspace/organizations/research_groups/` | /inbox | durable; 100+ target | /search (targets), /cv (unsolicited) |
| `user/workspace/positions/open/` | /inbox | **persistent leads**, status lifecycle | /cv (solicited) |

**Position lifecycle:** `evaluating → open → applied → closed/expired`. Leads are **never
deleted** — applied roles move to `user/workspace/positions/applied/` (status `applied`); past-deadline roles are
retired by `expire_sweep.py` (step 1 of `/dashboard`, every run): `status: expired`, `expired_on`
stamped, file moved `user/workspace/positions/open/ → user/workspace/positions/closed/`. Retired means out of rotation, not off
disk — `dedup_check.py` reads all three folders, so a deleted lead would simply be re-collected.

## Dedup & merge rule

**Dedup is by identity, never by age.** There is no freshness skip and no age filter: a lead is
stale only when its deadline has passed or the posting is confirmed removed.

- Before collecting, `dedup_check.py` compares a candidate against `user/workspace/inbox/`,
  `user/workspace/inbox/processed/`, `user/workspace/inbox/processed/archive/` **and** `user/workspace/positions/{open,applied,closed}/`.
  All six locations count; archiving is folder hygiene and does not retire a file from dedup.
- A **new role at a known org is always collected** (new file). Only the same org *and* role is a
  duplicate.
- `/inbox` **merges** a re-collected file into the existing profile: refresh facts +
  `last_evaluated`, append new roles, **preserve the manual `## Notes` section**, add a
  `## History` line.
- Rotation across the company/group databases is **oldest-`last_evaluated`-first, and orgs with
  no tracked lead before orgs that already have one** — not a fixed staleness cutoff.

## Measuring recall

Every `/search-positions` run appends a record to `user/workspace/logs/search_runs.jsonl` via `log_run.py`
(mandatory, including zero-find runs; rejections logged as well as collections).
`analyze_misses.py` then attributes each late discovery to the rule that caused the miss.
Full rationale in `engine/docs/LOG_SCHEMA.md` and `engine/docs/TELEMETRY.md`.

## Typical cadence

1. **Weekly (Sonnet):** `/search-positions` (industry + academic + PhD) — check profiled orgs'
   careers pages + run job-board queries. Optionally a `companies`/`groups` batch to keep
   the databases growing.
2. **After collecting (Opus):** `/model opus`, then `/inbox` to score everything and build
   profiles.
3. **On demand (Sonnet):** `/model sonnet`, then `/cv [profile]` for any role or org worth
   applying to.

## Related

[[background]] · [[preferences]] · [[competencies]] · [[search-positions]] · [[search-companies]] · [[search-groups]] · [[inbox-eval]] · [[cv-generate]]
