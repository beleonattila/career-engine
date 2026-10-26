---
name: track
cssclasses: [skill]
recommended_model: Haiku (low effort; Sonnet for plain-language targets)
description: >
  Update the application status of a position, company, or research group, then refresh
  the dashboard. Trigger on /track, "mark as sent", "I applied to", "I sent my CV to",
  "got feedback from", "rejected by", "got an offer from", "interview with", or any
  update about where an application stands. Also handles "remove"/"delete this lead",
  "this link is dead", "this looks hallucinated" — which quarantine the profile and its
  source files to user/workspace/trash/ rather than editing status. Edits the application-tracking
  frontmatter in the matching profile (single source of truth) and regenerates user/workspace/artifacts/dashboard.html.
---

# track

Records where an application stands by updating the lifecycle frontmatter on the relevant
profile/position, then regenerating the dashboard. Frontmatter is the single source of
truth; this skill is the safe way to edit it.

**Recommended model:** Haiku, low effort (mechanical frontmatter edits + file moves).
Use Sonnet only when the target is given in plain language and needs fuzzy matching.

---

## Syntax

```
/track <target> <event> [value] [date]
```

- `<target>` — a slug, org name, or role keyword. Resolve it against `name` /
  `organization` / filename across `user/workspace/positions/{open,applied,closed}` and
  `user/workspace/organizations/{companies,research_groups}`. If 0 matches: tell the user. If >1: list the
  matches and ask which.
- Plain-language equivalents are fine ("I sent my CV to Skape Bio today" → target
  `skape-bio`, event `sent`, date today).

## Events → frontmatter changes

| Event | Sets | Notes |
|---|---|---|
| `contact` [date] | `last_contact: <date>` | records a contact event (email, meeting, intro) without changing `app_status`; the dashboard shows it as "last contact" in the Status column for companies/research groups |
| `cv` [date] | `app_status: cv_generated`, `cv_date: <date>` | CV produced (usually set by `/cv`) |
| `sent` [date] | `app_status: sent`, `sent_date: <date>` | application submitted |
| `interviewing` [date] | `app_status: interviewing` | add a `feedback` line with the date |
| `feedback "<note>"` [date] | append `"<date>: <note>"` to the `feedback:` list | does not change status |
| `closed <outcome>` | `app_status: closed`, `app_outcome: <offer\|rejected\|ghosted\|withdrawn>` | |
| `next "<text>"` | `next_action: <text>` | a reminder / follow-up |
| `remove` / `delete` ["<reason>"] | **no frontmatter edit** — moves the profile **and** its source inbox file(s) to `user/workspace/trash/` and logs the removal | for a dead link or a suspected hallucination; see *Removing a lead* below |

Default `[date]` to today (currentDate) when omitted. Never overwrite existing dates
silently — if a date field already holds a value and a new one is given, update it and
note the change.

## Rules

1. **Edit frontmatter only; preserve the body.** Add the field if missing, update if
   present. Keep keys grouped with the other lifecycle fields.
2. **One `cv_dir`, earlier folders in `cv_dir_prior`.** When a record's application moves to a
   new folder (an outreach letter first, a formal programme application later), point `cv_dir`
   at the new folder and append the old value to the `cv_dir_prior:` list — never drop it. The
   dashboard's integrity check counts both, so a superseded folder is not reported as untracked.
   One application folder may be named by several records (an application naming two labs).
3. **Positions move folders with their lifecycle** (the dashboard reads all three, so this
   is for tidiness):
   - `sent` → also set lead `status: applied` and move the file to `user/workspace/positions/applied/`.
   - `closed` → set lead `status: closed`, move the file to `user/workspace/positions/closed/`.
   - Companies/groups never move — only their frontmatter changes.
4. **Outcomes:** `offer`, `rejected`, `ghosted`, `withdrawn`. Anything else → ask.
5. **Confirm in one line** what changed (target, old → new status, dates).
6. **Regenerate the dashboard** at the end:
   ```bash
   python engine/tools/dashboard.py
   ```
   Report the refreshed key stats.

## Removing a lead (`remove` / `delete`)

Use when a lead is a **dead link** or a **suspected hallucination** (a posting/org that an
automated fetch can't confirm and may never have existed). Instead of editing status, this
**quarantines** the lead so it leaves the dashboard but is preserved for later analysis —
after 20–30 such files the user will ask to study them to find what causes the hallucinations.
The raw source `.txt` is the key artifact, so it must be moved too, not just the profile.

**Never permanently delete — only move to `user/workspace/trash/`.** Files there are recoverable
and `user/workspace/trash/` is not scanned by the dashboard, so removed leads vanish from all counts/tabs.

Procedure:

1. **Resolve `<target>`** to its profile exactly as for any other event (0 matches → tell the
   user; >1 → list and ask which). The profile may live in `user/workspace/positions/{open,applied,closed}`
   or `user/workspace/organizations/{companies,research_groups}`.
2. **Create `user/workspace/trash/`** if it does not exist.
3. **Track down the source file(s)** that produced this profile:
   - If the profile frontmatter has a `source_file:` field (positions usually do), that path
     is authoritative — include it.
   - Always *also* glob `user/workspace/inbox/` **and** `user/workspace/inbox/processed/` for any `.txt` whose name starts
     with the org/role slug (companies/groups have no `source_file`, and a merged profile may
     have several refresh files). Collect every match.
4. **Move everything to `user/workspace/trash/`** — the profile `.md` plus all source `.txt` found — keeping
   their original basenames. If two files would collide, prefix the later one with its origin
   folder (e.g. `processed__name.txt`).
5. **Append one entry to `user/workspace/trash/_trash_log.md`** (create it with a header if missing) recording
   what was removed and why, so the batch can be analysed later:
   ```
   - <YYYY-MM-DD> · <target> · <reason: dead_link | hallucination | duplicate | other>
     · profile: <original path>
     · sources: <original path(s), or "none found">
   ```
   If no source `.txt` was found, still trash the profile and log `sources: none found` —
   that absence is itself a signal worth analysing.
6. **Do not** apply the position folder-move rules (step 3 of Rules) — removal supersedes them.
7. **Confirm in one line** what was trashed (profile + N source files), then **regenerate the
   dashboard** so the lead drops off.

Default `<reason>` to `dead_link` when omitted; if the user's wording implies a fabricated
posting ("this looks made up", "can't find this anywhere"), use `hallucination`.

## Examples

- `/track skape-bio cv` → app_status cv_generated, cv_date today; refresh.
- `/track symphogen sent 2026-06-10` → status applied + app_status sent + sent_date; move to applied/; refresh.
- `/track symphogen feedback "phone screen booked for 2026-06-20"` → append feedback line.
- `/track symphogen interviewing` → app_status interviewing.
- `/track westberg closed rejected` → app_status closed, outcome rejected, move to closed/.
- `/track skape-bio next "follow up if no reply by 2026-06-25"` → next_action set.
- `/track ghost-bio remove "404, link dead"` → move ghost-bio profile + its source .txt to `user/workspace/trash/`, log it (reason dead_link), refresh.
- `/track aganitha delete "can't find this posting anywhere — looks hallucinated"` → trash profile + sources, log reason hallucination, refresh.

## Edge cases

| Situation | Action |
|---|---|
| Target matches nothing | Report; suggest `/search`+`/inbox` to create the profile first |
| Target matches several | List candidates with paths; ask which |
| `sent` on an item with no `cv_date` | Set both `sent` and a `cv_date` (ask if unknown); flag that no CV folder is linked |
| Outcome word not recognised | Ask for one of offer/rejected/ghosted/withdrawn |
| `remove`/`delete` and no source `.txt` found | Trash the profile anyway; log `sources: none found` (the absence is itself a hallucination signal) |
| `remove`/`delete` on an already-applied/closed item | Allowed, but warn the user it has application history before trashing; proceed only on confirmation |
| User later asks to *analyse* trashed files | Read `user/workspace/trash/_trash_log.md` + the quarantined `.txt`/`.md` in `user/workspace/trash/`; look for common patterns (fabricated URLs, identical boilerplate, missing source files, recurring orgs) that correlate with hallucinated leads |

## Related

[[dashboard]] (regenerated after every update) · [[cv-generate]] (sets `cv_generated`) · [[PIPELINE]]
