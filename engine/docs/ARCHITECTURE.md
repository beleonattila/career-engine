# Architecture

*Written in the 2026-09-30 restructure (engine/ + user/ split).*

```
career-engine/
├── CLAUDE.md                   ← session instructions; @imports the profile snapshot + memory index
├── .claude/commands/           ← one file per slash command, each points at its skill
├── .claude/settings.local.json ← local permissions (not versioned)
├── .agents/  skills-lock.json  ← agent-browser skill (fallback browser for /linkedin)
├── engine/
│   ├── skills/                 ← cv-generate · inbox-eval · dashboard · track ·
│   │                             linkedin-profile-edit · rescore (temporary)
│   │   └── search: 3 orchestrators (search-positions|companies|groups) each fanning out
│   │     to 2 sub-agents — *-career.md and *-skill.md — over shared search-common.md
│   │     (geography/staging/TRACK) and search-positions-common.md (gates, sources)
│   ├── docs/                   ← ARCHITECTURE (this file) · PIPELINE · CHEATSHEET ·
│   │                             TELEMETRY · LINK_HEALTH · LOG_SCHEMA · decisions (the cases
│   │                             behind the rules, no personal content) · RECORD_SCHEMA
│   ├── packs/life_science/     ← domain pack, picked by `search.pack` in user/settings.toml:
│   │                             boards.md (position boards, company and group discovery) ·
│   │                             synonyms.md · prestige.md · ats_seeds.toml
│   ├── hooks/                  ← pre-commit (doctor.py --share); install once per clone with
│   │                             `git config core.hooksPath engine/hooks`
│   ├── templates/user/         ← starter user/ (placeholder profile, example settings, LaTeX
│   │                             templates, empty workspace); copied by init_user.py
│   └── tools/                  ← stdlib-only Python, run from the repo root (index below)
│       └── web/                ← plan.js · plan.css (Timeline + To-do) and stats.js · stats.css
│                                 (Statistics tab), inlined into dashboard.html by dashboard.py
└── user/                       ← gitignored by the engine; its own local git repo
    ├── personal_data/          ← raw uploads, read-only, not versioned
    │   ├── old_cvs/ · old_cover_letters/ · formal_education/{bsc,msc}/ · publications/
    │   ├── projects/ · references/ · other/
    │   └── _ignore/            ← never a source for claims (compliance output)
    ├── profile/
    │   ├── snapshot.md         ← loaded every session via CLAUDE.md
    │   ├── background.md       ← identity, education, research experience, level, handling notes
    │   ├── preferences.md      ← direction, target roles, job-ad keywords, scoring content,
    │   │                         logistics & salary reference
    │   ├── competencies.md     ← technical competencies (evidence-backed)
    │   ├── soft_skills.md      ← soft skills; prerequisite for /inbox and /cv
    │   ├── search_terms.md     ← what the search gates look for: career tiers + output table,
    │   │                         competency tables, level gate, query groups (read by /search-*)
    │   ├── search_terms.toml   ← the same, for the tools: ats_sweep regexes, log_run query pool
    │   ├── writing/            ← writing_style.md (voice rules) · cover_letter_style_A.md (voice
    │   │                         directives + Style A spec) · cover_letter_style_B.md ·
    │   │                         cover_letter_style.md (pattern library)
    │   ├── cv_template/        ← master_cv.tex (xelatex, Calibri) · master_cv_phd.tex ·
    │   │                         cover_letter.tex · publications.md · references.md ·
    │   │                         NOTES.md (this CV's variants, optional entries, removable lines)
    │   └── linkedin/           ← LINKEDIN.md (TODOs, consumed by /linkedin) + strategy docs
    ├── memory/                 ← session-level notes (how to work, live projects); MEMORY.md is
    │                             the index, loaded every session. Durable facts live elsewhere
    ├── settings.toml           ← thresholds, geography allowlist, career_fit check units; tools
    │                             read it via paths.setting(), skills read the file itself
    ├── secrets/                ← not versioned
    └── workspace/              ← every record path inside the data is relative to this folder
        ├── inbox/              ← drop .txt job ads here for /inbox
        │   ├── _staging/{career,skill}/ ← the two search tracks write here first
        │   └── processed/      ← evaluated by /inbox (last ~2 weeks)
        │       └── archive/    ← processed .txt >2 weeks old. Archiving is folder hygiene ONLY —
        │                         archive/ is still live dedup surface and must be searched
        ├── positions/open/ · applied/ · closed/
        ├── organizations/companies/ · research_groups/ · aliases.toml (renames/acquisitions)
        ├── contacts/           ← one file per person: what was sent and said, when, what next —
        │                         read before writing to them, add a dated line after
        ├── applications/       ← /cv output, one folder per application
        ├── trash/              ← created on demand by /track remove|delete; never scanned
        ├── linkedin/           ← engagement log, stats, connection targets
        ├── notes/              ← plans, briefs, pending_tasks.md
        ├── plan/               ← plan.json: the dashboard's Timeline + To-do items (plan.py)
        ├── logs/               ← search telemetry (search_runs.jsonl, analysis/), link-check
        │                         and ATS-sweep reports
        ├── cache/              ← ats_slugs.tsv
        ├── archive/            ← one-off scrapes and scripts
        └── artifacts/          ← dashboard.html (regenerated, not versioned) and other outputs
```

## Tools (`engine/tools/`)

All stdlib-only Python. Run from the repo root: `python engine/tools/<tool>.py`.

| Tool | What it does |
|---|---|
| `paths.py` | The one place that knows where `user/` and its folders are (override: `CAREER_USER_DIR`) |
| `init_user.py` | New clone: creates `user/` from `engine/templates/user/`, git-inits it and installs the pre-commit guard. Never overwrites; `--add-missing` fills gaps in an existing `user/`, `--dry-run` previews |
| `doctor.py` | Read-only health check: layout, settings.toml keys, stale or dangling paths, tools, git safety (incl. the pre-commit guard), records and their `schema_version`, and personal terms in any file the engine tracks or has staged (`--share` makes that last one fail; the pre-commit hook runs it). Terms come from `user/profile/private_terms.txt` |
| `schema.py` | The record format version: `SCHEMA_VERSION`, a report of records per version, and `--apply` to migrate them (`engine/docs/RECORD_SCHEMA.md`) |
| `dashboard.py` | → `user/workspace/artifacts/dashboard.html` |
| `serve.py` | Serves the dashboard on 127.0.0.1 (regenerated per load) so the Timeline and To-do tabs can save; the only writer of `plan/plan.json` from the browser |
| `plan.py` | The Timeline / To-do store `plan/plan.json`: validation, atomic save with a `rev` check; CLI lists items, `add` appends one |
| `expire_sweep.py` | Retires past-deadline and stale leads `open/` → `closed/` (step 1 of /dashboard). **Applies by default**; `--dry-run` to preview |
| `ats_discover.py` | → `cache/ats_slugs.tsv` (one-off/occasional ATS slug discovery; no `--help`, it runs) |
| `ats_sweep.py` | → `logs/ats_sweep_latest.tsv` (bulk employer-board sweep, ~0 tokens; no `--help`, it runs). `--uncovered` lists band-A employers with no board |
| `dedup_check.py` | Duplicate guard, mandatory before writing to the inbox |
| `link_check.py` | Verifies open leads still point at a live posting; report-only by default, `--apply` stamps `url_status` and retires dead leads; `--browser dead|live` records a verdict seen in the browser pane (see LINK_HEALTH.md §Browser pass) |
| `log_run.py` | Validate + append a run record to `logs/search_runs.jsonl`; archives that run's sweep TSV to `logs/ats_sweep/` |
| `analyze_misses.py` | Attribute recall failures from the telemetry (always writes a JSON to `logs/analysis/`); joins each lead to its record's `career_fit`, prints a strong-lead histogram, `--min-fit N`, `--since` (misses by runs after a fix) |
| `reconcile_staging.py` | Merge the two search tracks' staging folders into `inbox/`; career wins a collision, stamps `TRACK:`, `--apply` to write |
| `org_match.py` | Which company/group profile a position belongs to (shared by `dashboard.py` and `org_floor.py`) |
| `org_floor.py` | An org never scores below its best linked position; report-only by default, `--apply` writes the floor (run by /inbox) |
| `career_fit.py` | Scoring v3 lookup: band + checks → `career_fit` |
| `method_sightings.py` | Log of employers seen posting method-building seats (`logs/method_sightings.tsv`): `add` logs one, `--apply` writes `method_roles_seen` / `last_method_role` onto org profiles (run by /inbox), `--rotation N` prints the skill track's org-sweep order |
| `level_sweep.py` | One-off (2026-08-17) level gate sweep; `--dry-run` to preview |
