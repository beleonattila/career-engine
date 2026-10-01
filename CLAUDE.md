# career-engine

A career management engine. Every Claude Code session in this folder is working on job
applications, CV generation, position research, or career strategy.

The repo has two halves. **`engine/`** (skills, tools, docs) is generic and versioned.
**`user/`** holds everything personal (raw documents, profile, every generated record) and is
gitignored by the engine; it is its own local git repo.

---

## Profile

@user/profile/snapshot.md

**When the snapshot is enough:** quick questions, navigation, checking what's in a folder,
explaining what a skill does.

**When to read the full profile** — `user/profile/background.md` (identity, education, experience),
`user/profile/preferences.md` (direction, target roles, keywords), `user/profile/competencies.md`:
any writing task (CV, cover letter, profile paragraph, outreach email), and any scoring or
matching task where depth matters.

**Updating the profile:** if it changes (new publication, new skill, moved city), update
`user/profile/snapshot.md` and the matching full profile file together.

## Memory

Session-level notes — how to work, and the projects in flight — live in **`user/memory/`**, not in
Claude Code's auto-memory folder, so they stay with the rest of the personal data. The index is
loaded every session:

@user/memory/MEMORY.md

Durable facts go where they belong instead of into memory: people and correspondence →
`user/workspace/contacts/` (one file per person); direction and motivation →
`user/profile/preferences.md`; facts and handling notes → `user/profile/background.md`; voice rules
→ `user/profile/writing/`. Write a memory only for how-to-work feedback or a live project (one fact
per file, same frontmatter format, one line added to `user/memory/MEMORY.md`).

---

## Environment & Paths

**The project root is the folder holding this file.** The engine assumes Windows, with **Windows
PowerShell 5.1** as the default shell (a `Bash` tool is also available for POSIX scripts).

- **In these docs**, paths are relative to the repo root with forward slashes (e.g.
  `user/profile/background.md`). Forward slashes are accepted by the file tools, by most CLIs,
  and by the Bash tool — keep using them.
- **Tools** are stdlib-only Python in `engine/tools/`, run from the repo root:
  `python engine/tools/dashboard.py`. They find `user/` through `engine/tools/paths.py`, so they
  also work from any other directory.
- **Record paths** inside the data (`source_file: inbox/…`, `cv_dir: applications/…`) are relative
  to `user/workspace/`.
- **Records** end their frontmatter with `schema_version` — the record format, separate from
  `scoring:` (the rubric). Migrate with `python engine/tools/schema.py --apply`, never by hand
  (`engine/docs/RECORD_SCHEMA.md`).
- **LaTeX compile** stays `latexmk -xelatex` regardless of shell; run it from inside the
  application folder.

**Layout and tooling:** `engine/docs/ARCHITECTURE.md` has the annotated tree and the tool index.
**Health check:** `python engine/tools/doctor.py` — run it after any change to the skills, tools or layout; it must end with 0 fail.
**Pre-commit guard:** `git config core.hooksPath engine/hooks` once per clone; the hook runs
`doctor.py --share` and refuses a commit that would put personal content into the engine.

---

## Standing Instructions

These apply to every task in this project unless explicitly overridden.

**Factual grounding** — Never invent or embellish. Every claim in a CV or cover
letter must be traceable to `user/profile/background.md`, a source document in
`user/personal_data/`, or something the user has stated in the current session.
`user/personal_data/_ignore/` is never a source.

**Handling notes** — `user/profile/background.md` §Handling notes lists facts that must not
appear in application material, or only in a set form. Read it before any writing task.

**Writing style** — the user's voice rules are `user/profile/writing/writing_style.md` (its short
version heads the file); the file-format rules — one paragraph per source line, the `.txt`
companion, the covering email — are in `engine/skills/cv-generate.md`. Read both before writing.

**LaTeX compilation** — Always use `latexmk -xelatex` for compilation.
Running xelatex once produces `??` in page footers. If latexmk is unavailable,
run xelatex twice on the same file.

**Profile scoring — three independent numbers, never blended.** When evaluating any position
or organisation (full rubric and anchor bands: `engine/skills/inbox-eval.md` §Scoring):
- `career_fit` **0–100 — is this the science I want?** Direction only, **scoring v3**: a **band**
  for how close the work is to the direction, then yes/no **checks** read off a lookup table that
  place the record *inside* its band, never out of it. What the bands and checks mean is personal:
  `user/profile/preferences.md` §Scoring (check names and units: `user/settings.toml`). Orgs are banded by their most on-direction line, and an org **never scores below
  its best linked position** (`python engine/tools/org_floor.py --apply`). Nothing else enters: not location,
  salary, prestige, seniority or company size. Every kind of record carries this.
- `method_fit` **0–100 — is this the work I want?** Does the seat **build** methods, tools,
  pipelines, platforms or benchmarks that others then use, or only **operate** what already exists?
  Judged against anchor bands, no lookup table. **Independent of domain and of ability** — the
  domain belongs to `career_fit`, a familiar stack to `skill_match`, so a low `career_fit` with a
  high `method_fit` (`career_fit` 35 · `method_fit` 92) is a lead worth seeing, not noise. Carried
  by every kind of record; for an org the question is *"would I be the methods person here?"*. Why
  it exists: `engine/docs/decisions.md` §`method_fit`.
- `skill_match` **0–100 — can I do this?** Evidenced overlap with `user/profile/competencies.md` /
  `user/profile/soft_skills.md` and nothing else. On **every** kind of record: for a position it
  reads the ad's requirements; for a company or research group it reads the org's *stated
  technical work* — "could I be useful here", which is the question a cold-outreach target
  has to answer, since the org databases are what unsolicited applications are sent from.
- `level_fit` **badge, scores nothing** — `realistic | reach | below`, against what the user holds
  today (`user/profile/background.md` §Level). **Positions and PhD calls only** — an org profile
  advertises no seniority, so there is nothing for the badge to describe.
- **Never average them or reintroduce a single score.** A high-`career_fit`, low-`skill_match`
  record is a stretch worth seeing, not a contradiction to smooth over; a low-`career_fit`,
  high-`method_fit` one is the right kind of work in the wrong field, which is also worth seeing.
  A blended score hides exactly that (`engine/docs/decisions.md` §Why two scores).

**Before applying to any position** — Check `user/workspace/positions/` to see if
a profile already exists. If it does, update it rather than creating a duplicate. Check
`user/workspace/applications/` for prior output before writing a cover letter.

**Before writing to anyone** — read their file in `user/workspace/contacts/` if one exists, and add
a dated line to it after the exchange.

**Before writing anything to the inbox** — Run `python engine/tools/dedup_check.py`.
This is mandatory, not optional; eyeball dedup has demonstrably failed.

**Link & status hygiene** — A position's `url` must be verified before it's relied on.
`/cv` checks the link before generating; `python engine/tools/link_check.py --apply`
re-validates every open lead reaching `thresholds.min_score_shown` (`user/settings.toml`) on **any** of `career_fit`,
`method_fit` or `skill_match`, and retires the dead ones.
A link an automated fetch refuses (404/ECONNREFUSED) is *unverified, not dead* — confirm with
a real browser. **The converse also holds: HTTP 200 is not proof a posting is live.** LinkedIn's
`ad-library/job/detail/<id>` returns 200 for expired jobs (measured: `engine/docs/LINK_HEALTH.md`).
Check LinkedIn against the canonical
`linkedin.com/jobs/view/<id>` page and store *that* form in `url:`. See `engine/docs/LINK_HEALTH.md`.
For Workday ATSs
(`*.myworkdayjobs.com`, very common), the JSON endpoint
`POST /wday/cxs/{tenant}/{site}/jobs` with `{"searchText":"…","limit":20}` authoritatively
lists live postings without a browser. Mark a position `expired` **only** if its `deadline`
is strictly before today **or** the posting is confirmed removed — never on the deadline
day itself.
**Exception — age retirement.** A lead with `deadline: null` could never be retired by the rule
above, so `expire_sweep.py` retires deadline-less leads **older than `thresholds.stale_days`
(`user/settings.toml`) on age alone**, stamping `expired_reason: stale_no_deadline` plus a dated
Notes line saying the posting was *not* confirmed removed. This knowingly trades accuracy for a
manageable active set: some retired leads are still live. It is a decision, not a bug — do not
revert it (the case: `engine/docs/decisions.md` §Age retirement). Undo the whole set with
`grep -l "expired_reason: stale_no_deadline" user/workspace/positions/closed/*.md`; skip it for one run with
`--keep-stale`. See `engine/docs/LINK_HEALTH.md`.

**Grades** — extract precisely from transcripts; never round or paraphrase.

---

## Commands

> **The pipeline (collect → think → produce).** See `engine/docs/PIPELINE.md` for the
> full diagram and contracts. In short: the three `/search-*` collectors drop raw
> `.txt` into the inbox (the filename encodes the type) → `/inbox` is the single thinking stage that
> scores, extracts keywords, and builds every database → `/cv` produces application
> materials from those profiles. **Models** (switch with `/model` first): mechanical
> (`/dashboard`, `/track`) → **Haiku**; collection/writing (`/search-*`, `/cv`, `/linkedin`)
> → **Sonnet**; the scoring stage (`/inbox`) → **Opus**. Per-command guide (with effort
> levels) in `engine/docs/CHEATSHEET.txt`.
>
> ⚠️ **The model for `/search-*` is provisional.** The yield telemetry cannot settle it yet
> (`engine/skills/search-positions-common.md` §Model and effort; the numbers: `engine/docs/decisions.md`). Whatever
> setting you pick, record `model` and `effort` honestly — an unlabelled run answers nothing.

**The commands:** `/inbox` · `/cv` · `/search-positions` · `/search-companies` ·
`/search-groups` · `/dashboard` · `/track` · `/linkedin`. Each is defined by its skill file in
`engine/skills/` — that file carries the full instructions *and* a `recommended_model:`
line, so read the skill rather than duplicating its contract here.

> 🔀 **The three `/search-*` commands are orchestrators, not collectors.** Each spawns **two
> sub-agents in parallel** — a `career` track (is this the work I want?) and a `skill` track
> (could I get and do it?) — which write to `user/workspace/inbox/_staging/{career,skill}/`. The orchestrator
> then runs `python engine/tools/reconcile_staging.py --apply`: **career wins any collision**, each survivor
> is stamped `TRACK:`, and everything moves to `user/workspace/inbox/`. Shared rules live in
> `engine/skills/search-common.md` (geography, staging, TRACK) and `engine/skills/search-positions-common.md`;
> only the keyword pass and Gate 3 differ per track. **The skill track has no direction floor
> by design** — it will surface roles built on the user's strongest competencies, whatever their
> field. Never add a direction filter to it. Since 2026-10-01 it also runs the **method lane** —
> build seats found through ad text and through employers that have posted them before
> (`method_sightings.py`), never through method-title queries (`engine/docs/decisions.md` §Method lane).
>
> ⚠️ `/linkedin` runs via **agent-browser** (a headed Chrome reusing a logged-in profile; see the skill). If
> agent-browser errors, stop and ask the user to restart it — never retry.
