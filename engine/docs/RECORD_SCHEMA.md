# Record schema

Every record in `user/workspace/` — positions (`positions/{open,applied,closed}/`), organisation
profiles (`organizations/{companies,research_groups}/`) and contacts (`contacts/`) — is a Markdown
file whose YAML frontmatter ends with `schema_version: N`.

Two fields version a record, and they move independently:

| Field | Versions | Owned by |
|---|---|---|
| `schema_version` | the record **format** — which fields exist, where records live, what paths inside them are relative to | `engine/tools/schema.py` (`SCHEMA_VERSION`) |
| `scoring` | the **rubric** the scores were judged under (`v1`, `v2`, `v2.1`, `v3`) | `engine/skills/inbox-eval.md` §Scoring; `/inbox` re-judges |

A rubric change re-judges scores and bumps `scoring:`. A format change is a mechanical migration
and bumps `schema_version`. Neither is ever edited by hand.

## Versions

| Version | Since | Format |
|---|---|---|
| 0 | — | No stamp: anything written before 2026-10-01. |
| 1 | 2026-10-01 | The layout after the restructure: records under `user/workspace/`, record paths (`source_file:`, `cv_dir:`) relative to it; `career_fit`, `method_fit` and `skill_match` on every record, `level_fit` on positions; `career_band` / `career_checks`; `track`; contacts as records of their own. Going 0 → 1 adds the stamp and nothing else. |
| 2 | 2026-10-26 | Positions (and PhD calls) gain `bench_load: none \| light \| substantial \| unknown`, the wet-lab work the seat itself requires; reported, never scored (`engine/docs/decisions.md` §`bench_load`). Going 1 → 2 adds `bench_load: unknown` to every position, after `remote_policy:`; organisations and contacts only take the new stamp. |
| 3 | 2026-11-21 | `career_fit` is renamed `domain_fit` (`engine/docs/decisions.md` §`domain_fit`), with `career_band` / `career_checks` → `domain_band` / `domain_checks` and the org-floor fields → `domain_fit_own` / `_floor` / `_floor_from`. Every mention in a record's body is renamed too (the `**Domain fit:**` line, History lines). `--apply` also renames `[career_fit.checks]` in `user/settings.toml` to `[domain_fit.checks]` and adds `[domain_fit] label`. |

**Derived fields** are written by a tool from other data and are not part of the format version:
an org may carry them or not, and nothing else writes them. `domain_fit_own` /
`domain_fit_floor` / `domain_fit_floor_from` (`org_floor.py`); `method_roles_seen` /
`last_method_role` (`method_sightings.py --apply`, from `logs/method_sightings.tsv`).

## Where new records come from

The templates in `engine/skills/inbox-eval.md` §Handlers (companies, groups, positions / PhD) and
`user/workspace/contacts/README.md` (contacts). All of them write the current version.

## Changing the format

1. Write `migrate_N_to_N1(text)` in `engine/tools/schema.py` and register it in `MIGRATIONS`.
2. Bump `SCHEMA_VERSION`.
3. Update the templates above and the version table here.
4. Run `python engine/tools/schema.py --apply`, then `python engine/tools/doctor.py`.

`python engine/tools/schema.py` reports how many records sit at each version; `doctor.py` warns
about any record that is unstamped, older, or newer than the engine.
