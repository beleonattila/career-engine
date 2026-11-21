---
name: dashboard
cssclasses: [skill]
recommended_model: Haiku (low effort)
description: >
  Generate / refresh the career dashboard. Trigger on /dashboard, "refresh the
  dashboard", "update the dashboard", "show my stats", "regenerate dashboard". Runs the
  generator that scans the vault's profiles and position leads, computes statistics, and
  writes a self-contained user/workspace/artifacts/dashboard.html with ranked tabs (companies, research groups,
  positions, PhD) and a Statistics tab charting the vault and the search telemetry.
---

# dashboard

Builds `user/workspace/artifacts/dashboard.html` — a single self-contained file (no dependencies,
no server) with a Statistics tab of charts and sortable/filterable tabs ranked
by `domain_fit`.

**Recommended model:** Haiku, low effort (mechanical). The dashboard is a *view*: it
reads, never scores — the real work is in `dashboard.py`.

---

## What it reads

- `user/workspace/organizations/companies/*.md`, `user/workspace/organizations/research_groups/*.md`
- `user/workspace/positions/open/*.md`, `user/workspace/positions/applied/*.md`, `user/workspace/positions/closed/*.md`
- `user/workspace/inbox/processed/*.txt` (for the "search results" count)
- `user/workspace/applications/*/` (for the "CVs generated" count)
- `engine/data/phd_pay_europe.toml` (the **PhD pay map** tab: a Europe heatmap switchable between
  gross pay, net pay, tax, PPP, housing, living cost and money left at month end; estimates —
  correct a row there when a real offer states the figure)

It parses each file's YAML frontmatter — including the application-tracking fields
(`app_status`, `app_outcome`, `cv_date`, `sent_date`, `next_action`) maintained by
`/track`. Frontmatter is the single source of truth; this skill only aggregates it.

`user/workspace/trash/` is **not** scanned — leads quarantined there by `/track remove`/`delete` (dead
links / suspected hallucinations) are absent from every count and tab by construction.

## Workflow

1. **Expire past-deadline leads first — every run, before generating.**
   ```bash
   python engine/tools/expire_sweep.py
   ```
   Retires leads whose `deadline` is **strictly before today** out of the active working set:
   sets `status: expired`, stamps `expired_on`, and moves the file
   `user/workspace/positions/open/` → `user/workspace/positions/closed/`. Report how many were retired.

   Use `--dry-run` first to see the list without changing anything.

   > **"Retired" means out of rotation, not off disk.** The record is never deleted: leads are
   > persistent, `dedup_check.py` globs `user/workspace/positions/{open,applied,closed}` (a deleted
   > lead would be re-collected), and the miss telemetry needs the history.

   What the sweep deliberately leaves alone:
   - `deadline: null` — never expires on the deadline test. No deadline is not evidence that one has passed.
   - **deadline == today** — still live. Never expire on the deadline day itself (CLAUDE.md).
   - Anything `applied` / `sent` / `interviewing` / `offer` — the application is still pending.
     `user/workspace/positions/applied/` is never touched at all.

   **It ALSO retires deadline-less leads on age — older than `thresholds.stale_days`
   (`user/settings.toml`)** — moving them `open/` → `closed/` stamped
   **`expired_reason: stale_no_deadline`**.

   > ⚠️ **This overrides the CLAUDE.md expiry rule knowingly** (the user's decision): none of these
   > postings was confirmed removed and some are still live. It buys a manageable active set at the
   > cost of accuracy. **Do not "fix" it back** (`engine/docs/decisions.md` §Age retirement).
   >
   > Reverse the whole set: `grep -l "expired_reason: stale_no_deadline" user/workspace/positions/closed/*.md`,
   > move back, reset `status:` / `expired_on:` / `expired_reason:`. Skip for one run with
   > `--keep-stale`. Retune for one run with `--stale-days N`, for good in `user/settings.toml`.

   **Exemption: verified recently — `thresholds.verified_days`.** A deadline-less lead **confirmed
   live within that window** is kept and listed under *"kept — verified live recently"*, never
   retired on age — a fresh positive verdict is the evidence age stands in for. Narrow by design:
   `url_status: working` only, **never** a LinkedIn `working`, and a window far shorter than
   `stale_days`, so a lead verified once at collection still ages out. Disable for one run with
   `--verified-days -1`.

   - **`⚠ unproven (N)`** — reported, never retired: leads stamped `url_status: working` on a
     `linkedin.com` URL, a verdict `link_check.py` can no longer produce. Any survivor predates
     that fix and means nothing.

   > **`expire_sweep.py` and `dashboard.py` read the same `thresholds.stale_days` and
   > `thresholds.verified_days`** and apply the same exemption, so they cannot drift apart. The
   > dashboard's overdue count is a **tripwire** that should read **0**, because `/dashboard` runs
   > the sweep as step 1; a lead the sweep deliberately keeps is never counted as overdue. When it
   > is not 0, a warning appears on the Statistics tab (*Records by kind*) and in the page footer:
   > the sweep has not run.

   > **The sweep only catches leads whose *deadline* has passed.** A posting pulled early stays in
   > `open/` looking healthy — that larger leak is `link_check.py`'s job
   > (`engine/docs/decisions.md` §Dashboard). Never run the link check on every dashboard refresh
   > (network-bound; LinkedIn rate-limits), but run it about weekly, or whenever the open-lead count
   > looks healthier than the application pipeline suggests:
   > ```bash
   > python engine/tools/link_check.py            # report only
   > python engine/tools/link_check.py --apply    # stamp url_status, retire the dead
   > ```

2. Run the generator:
   ```bash
   python engine/tools/dashboard.py
   ```
3. It writes `user/workspace/artifacts/dashboard.html` and prints a one-line summary
   (record counts + key stats).
4. Report both numbers to the user — leads retired **and** the dashboard summary — then give the
   path to open: `user/workspace/artifacts/dashboard.html` (double-click, or `start user/workspace/artifacts/dashboard.html` on Windows).
   Opened that way the Timeline and To-do tabs are read-only; to edit them, `python engine/tools/serve.py`.

If `python` is missing, report it and point the user at `dashboard.py` (no other deps
are required — standard library only).

## Timeline and To-do

Two tabs over **one store**, `user/workspace/plan/plan.json` (`plan.py`), so they are always in
sync: ticking, flagging or recolouring an item in either changes it in both.

- **Timeline** — the long plan *and the past*: every item, done or not. A zoomed, draggable
  Gantt view (wheel or drag to move, Ctrl + wheel or the 1M…2Y / All buttons to zoom) above a
  colour-only miniature of the whole plan, whose window drags too. Ribbons are spans; an item
  with **no end date is a moment** (a diamond — an application sent). Click a ribbon for its info
  page: dates, colour, Important / Urgent / Done, notes, and a delete button.
- **To-do** — what to do next: open items whose date (end, or the moment) is **today or later**,
  in an important × urgent matrix (rows urgent / not urgent, columns important / not important).
  A span in progress stays. Drag a card between squares to re-flag it; tick it when done — it
  leaves the matrix and stays on the Timeline. Your own items left open after their date are
  listed under the matrix, so nothing overdue disappears silently.
- **Add** takes a title, start, optional end and a colour (Important / Urgent optional). A new
  item dated entirely in the past is pre-ticked Done: it records what happened.
- **Items from records**, derived by `dashboard.py` on every run so they cannot drift: every
  application **sent** (`_sent_evidence()`, at its send date, already done), every **interview**
  (each dated line of a record's `interviews:` list, yellow, done once its day has passed) and
  every **live deadline** still to act on (shown, not yet applied, any horizon).
  Their dates are the record's — change them with `/track`. The plan may only recolour, flag, tick
  or hide them (`overrides` in `plan.json`; the trash button *hides*, the record is untouched).
  Defaults: urgent within 14 days; a deadline is important when `domain_fit >=
  thresholds.on_direction`, an interview always. A record at `app_status: interviewing` with no
  dated `interviews:` line is an integrity issue (`interview_undated`), so an interview cannot
  silently miss the Timeline.
- **Saving needs `python engine/tools/serve.py`** (127.0.0.1 only; regenerates the dashboard on
  every load but never runs `expire_sweep.py`). A page opened from disk cannot write files, so it
  shows the plan read-only with that command. Each save carries `rev`; a stale one is refused and
  the page reloads the plan, so an edit made elsewhere (by hand, or `plan.py add`) is never lost.

## Statistics tab (kept in sync with the generator)

The **Statistics** tab (`engine/tools/web/stats.js` · `stats.css`, inlined like the plan tabs):
hand-built SVG charts, no library, each with a hover/focus tooltip and a *Show data* table. The
integrity check lives in the Home page's taskbar tray. Two sections:

- **Vault** — the application funnel, records by kind, a domain-fit × skill-match scatter of live
  position and PhD leads, and leads collected per week split by search track (`track: career`
  against everything else, since skill-track records say `employability` or `skill`).
- **Search telemetry** — runs logged, deep passes, the LinkedIn shortlist rate; why leads were
  missed (all vs strong leads); net-new leads per run by mode; what each channel found; channel
  coverage (reached / skipped / failed); rejections by reason; days from posting to discovery.
  Computed by `log_run.py`'s own functions and read from the newest *cumulative*
  `logs/analysis/misses_*.json` (windowed `--since` reports are skipped), so the tab and
  `log_run.py --stats` cannot disagree. Refresh the miss charts with `analyze_misses.py`.

Colours are the reference data-viz palette's dark steps, validated on the panel surface
`#171a21` (three slots, all pairs pass); text never wears a series colour.

The numbers the funnel and *Records by kind* charts show:

| Number | Definition |
|---|---|
| Search results | count of `user/workspace/inbox/processed/*.txt` (cumulative collected leads) |
| On-direction (≥N) | **shown** records only, with `domain_fit ≥ thresholds.on_direction` (`user/settings.toml`; the label shows the number) — the "positive results" metric. Counts desirability only — a record here may still be a `reach`. The lifetime figure, every record in the vault, is `positive_all` in the footer note (`engine/docs/decisions.md` §Dashboard). |
| Companies / Groups / Positions / PhD | profile counts per category (PhD split from positions by `type: phd` or "PhD" in the title) |
| Overdue (unretired) | **Tripwire — should read 0;** shown only as a warning when it does not. Shown position/PhD leads with `deadline: null` past `thresholds.stale_days` that `expire_sweep.py` should already have retired. Non-zero means the sweep has not run. Leads exempt under `thresholds.verified_days` (confirmed live recently) are **not** counted — the sweep keeps them on purpose |
| CVs generated | count of `user/workspace/applications/*/` folders (or items with `cv_date`) |
| CVs sent | items with **positive evidence** of a submission: `app_status` sent/interviewing, any `sent_date`, or closed with outcome rejected/offer. `closed` **alone does not count** — a lead closed `withdrawn` was never submitted. Includes orgs, since an unsolicited application is a real send |
| Ongoing | items with `app_status` sent or interviewing |
| Offers / Rejections | items with `app_outcome` offer / rejected |

## Display rules (kept in sync with the generator)

- **Positions & PhD tabs show only *alive* leads** — **not** `expired`/`closed` **and** `deadline`
  **not passed** (no deadline counts as alive). This applies to both tabs and their counts. The
  filter is computed live from the current date, so a lead drops off the day after its deadline
  even if its `status` still says otherwise.
  - This filter and `expire_sweep.py` (step 1) are **belt and braces, not duplicates**: the filter
    only hides a stale lead; the sweep also takes it out of `user/workspace/positions/open/`, so it
    stops consuming the `/search-positions` rotation budget and inflating the open-lead count.
- **Company / group Status column shows two different facts, both labelled.**
  `applied <date> · N roles` is the last CV actually **sent** to a role at that employer, joined
  from `user/workspace/positions/`; `last contact <date>` is the last unsolicited approach, read from the
  profile's own frontmatter. An employer with no record of either reads `never applied`.
  Hover the applied line for the full list of roles, dates and outcomes.
  - "Sent" needs positive evidence — `app_status: closed` alone does not count, since leads are
    also closed with `app_outcome: withdrawn` having never been sent. A lead counts when it is
    `sent`/`interviewing`, carries any `sent_date`, or was closed `rejected`/`offer`. Sends whose
    date was never stamped show as `applied · date not recorded` rather than vanishing.
  - **This rule is `_sent_evidence()` in `dashboard.py`, and the CVs-sent tile uses the same
    function.** Anything else that needs "was it sent" calls it — never re-derive the rule
    (`engine/docs/decisions.md` §Dashboard).
  - The position→profile join reuses `dedup_check.py`'s `ALIASES` and `same_employer()` instead
    of forking that logic, then falls back to requiring every identity token of the *profile* to
    appear in the position, at least one of them discriminating (in ≤2 profiles). Direction and
    rarity are both load-bearing (`engine/docs/decisions.md` §Dashboard). Override a wrong match
    with `org_profile:` in the position's frontmatter — see *inbox-eval*.

- **There is no Best Match tab** (the user's request; `engine/docs/decisions.md` §Best Match
  removed) — the Skill column header gives that ranking in one click. `track: career |
  employability` stays a **column**, for provenance only — it never affects a score, a tab, or
  visibility.

- **The Applications tab shows everything** — every record with an `app_status` (CV generated,
  sent, interviewing, closed), regardless of deadline or lead status, so it stays a complete
  history. The alive-only filter deliberately does **not** touch this tab.
- Expired/closed/past-deadline positions stay on disk (in `user/workspace/positions/open|closed/`) and
  still surface in the **Applications** tab with a muted `role closed`/`role expired` badge
  if a CV was generated for them.
- **There is no deadline bar** (the user's request). Live deadlines are items in the **To-do**
  matrix and on the **Timeline** instead: shown leads not yet `sent`/`interviewing`, any horizon
  (§Timeline and To-do).
- **Home is an OS-style entry page** (the user's request; `engine/tools/web/home.js` ·
  `home.css`). Wallpaper, faint logo, the name, one app icon per page with its count, and a taskbar
  holding the **integrity check** (tray: ✓ or ⚠ N, click for the list) and a clock. Other pages
  carry a ⌂ Home button; Esc also goes home.
- **Link flag:** the Positions and PhD tabs' *Link · age* column shows each lead's `url_status` —
  yellow `⚠ unchecked` (not yet validated), yellow `⚠ unresolved` (the stored url is a search page
  or board root, so it can never confirm anything), or red `⚠ dead`. Clear `unchecked` with
  `python engine/tools/link_check.py --apply`, which stamps `url_status` / `url_checked` on every
  open lead and retires the dead ones. A plain HTTP 200 is **not** proof a posting is live
  (`engine/docs/LINK_HEALTH.md`).

- **Score columns on every row, every kind.** `domain_fit` (do I want it) and `skill_match` (can
  I do it) side by side; for a company or group, `skill_match` scores its stated stack against
  user/profile/competencies.md (the cold-outreach question). Only `level_fit` is
  position/PhD-specific; orgs show `—` there. Sorting defaults to `domain_fit` descending; either
  score column is clickable. What each number means: *Scoring* in [[inbox-eval]].

- **Wet lab column and toggle.** Positions, PhD and Applications show
  `bench_load` (`none · light · unknown · substantial`) as a *Wet lab* column; sorting it orders
  those four, with `unknown` between `light` and `substantial` because it may be either. On the
  Positions and PhD tabs a **hide substantial wet lab** checkbox drops `substantial` rows and
  their tab counts; the browser remembers it (`localStorage`, guarded). It is a view, never a
  score: it moves no number, and Home, Statistics, the plan tabs and Applications ignore it
  (`engine/docs/decisions.md` §`bench_load`).

- **Score threshold — `thresholds.min_score_shown` in `user/settings.toml`** (read into
  `MIN_SCORE_SHOWN` in `dashboard.py`). A position/PhD lead is hidden only when **all three**
  scores fall below it; any one clearing it keeps the row visible (a `domain_fit 88 ·
  skill_match 40` stretch and a `domain_fit 45 · skill_match 85` fallback are both worth seeing).
  Hidden leads stay on disk. Companies and groups are never hidden by score. The **Applications
  tab is exempt**. Visibility is decided once, by `_shown()` in Python, and stamped on each record
  as `shown`; the page's JavaScript reads that flag, never recomputes it, so tiles and tab counts
  cannot drift apart.

## When to run

- After `/inbox` (new profiles or scores) — `/inbox` runs it automatically
- After `/cv` (a CV was generated)
- After `/track` (status changed) — `/track` already calls this automatically
- Any time the user wants a fresh view

So the deadline sweep in step 1 rides along with the normal pipeline. It is idempotent and catches
an arbitrary backlog, not only yesterday's expiries.

## Related

[[PIPELINE]] · [[track]] (updates the application fields this reads) · [[inbox-eval]] · [[cv-generate]]
