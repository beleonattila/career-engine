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
by `career_fit`.

**Recommended model:** Haiku, low effort (mechanical). The dashboard is a *view*: it
reads, never scores — the real work is in `dashboard.py`.

---

## What it reads

- `user/workspace/organizations/companies/*.md`, `user/workspace/organizations/research_groups/*.md`
- `user/workspace/positions/open/*.md`, `user/workspace/positions/applied/*.md`, `user/workspace/positions/closed/*.md`
- `user/workspace/inbox/processed/*.txt` (for the "search results" count)
- `user/workspace/applications/*/` (for the "CVs generated" count)

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

   Use `--dry-run` first if you want to see the list without changing anything.

   > **"Retired" means out of rotation, not off disk.** The record is never deleted. Leads are
   > persistent by design (see the position template), `dedup_check.py` globs
   > `user/workspace/positions/{open,applied,closed}` so a deleted lead would just be re-collected on the next
   > search, and the miss-attribution telemetry needs the history to attribute recall failures.

   What the sweep deliberately leaves alone:
   - `deadline: null` — never expires. No deadline is not evidence that one has passed.
   - **deadline == today** — still live. Never expire on the deadline day itself (CLAUDE.md).
   - Anything `applied` / `sent` / `interviewing` / `offer` — you applied *before* the deadline
     and the application is still pending. `user/workspace/positions/applied/` is never touched at all.

   **It ALSO retires deadline-less leads on age — `thresholds.stale_days` in `user/settings.toml`
   (45 when introduced).**
   *(The user's decision, 2026-08-29, after `biohub_computational-biologist-cellxstate_2026-06` was
   found in `open/` at 83 days.)* A lead with `deadline: null` can never fail the deadline test, and
   78% of open leads had none, so they accumulated forever. Those older than `stale_days` now move
   `open/` → `closed/` stamped **`expired_reason: stale_no_deadline`**.

   > ⚠️ **This overrides the CLAUDE.md expiry rule and does so knowingly.** None of these postings
   > was confirmed removed; some are still live. It buys a manageable active set at the cost of
   > accuracy. **Do not "fix" it back.** First run retired **39** leads (open/ 85 → 46), including
   > `hzdr_postdoc-generative-ai-denovo-protein-design` (career_fit **95**),
   > `latent-labs_computational-protein-designer` (**93**) and three at **90**.
   >
   > Reverse the whole set: `grep -l "expired_reason: stale_no_deadline" user/workspace/positions/closed/*.md`,
   > move back, reset `status:` / `expired_on:` / `expired_reason:`. Skip for one run with
   > `--keep-stale`. Retune for one run with `--stale-days N`, for good in `user/settings.toml`.

   **Exemption: verified recently — `thresholds.verified_days` (14 when introduced, 2026-11-18).**
   A deadline-less lead **confirmed live within that window** is kept and listed under
   *"kept — verified live recently"*, never retired on age. Age retirement stands in for missing
   evidence; a fresh positive verdict *is* that evidence, so the rule has nothing to say.
   Narrow by design: `url_status: working` only, **never** a LinkedIn `working`, and a window far
   shorter than `stale_days`, so a lead verified once at collection still ages out. Disable for one
   run with `--verified-days -1`. The case: `latent-labs_member-of-technical-staff_2026-10`
   (career_fit **98**) was retired at 46 days and found fully live the same day
   (`engine/docs/decisions.md` §Age retirement).

   - **`⚠ unproven (N)`** — reported, never retired: leads stamped `url_status: working` on a
     `linkedin.com` URL, a verdict `link_check.py` has been unable to produce since 2026-08-16.
     Any survivor predates that fix and means nothing. First run: **7**, all corrected to
     `unverified`.

   > **`expire_sweep.py` and `dashboard.py` read the same `thresholds.stale_days` and
   > `thresholds.verified_days`**, and apply the same verified-recently exemption, so they
   > cannot drift apart. A lead the sweep deliberately keeps is not counted as overdue here:
   > a tripwire that fires on something no action can clear stops being a tripwire. The sweep retires; the dashboard's overdue count is a **tripwire** that should
   > read **0**, because `/dashboard` runs the sweep as step 1. When it is not, a warning appears on the
   > Statistics tab (*Records by kind*) and in the page footer: the sweep has not run.

   > **The sweep only catches leads whose *deadline* has passed.** A posting pulled early — or
   > one that never had a deadline — stays in `open/` looking healthy. That is what
   > `link_check.py` is for, and it is the larger leak: on 2026-08-16 the deadline sweep retired
   > 2 leads while the link check retired 20. Do **not** run the link check on every dashboard
   > refresh (it is network-bound and LinkedIn rate-limits), but run it about weekly, or whenever
   > the open-lead count looks healthier than the application pipeline suggests:
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

## Timeline and To-do (added 2026-10-02)

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
  (each dated line of a record's `interviews:` list, yellow, done once its day has passed, added
  2026-11-07) and every **live deadline** still to act on (shown, not yet applied, any horizon).
  Their dates are the record's — change them with `/track`. The plan may only recolour, flag, tick
  or hide them (`overrides` in `plan.json`; the trash button *hides*, the record is untouched).
  Defaults: urgent within 14 days; a deadline is important when `career_fit >=
  thresholds.on_direction`, an interview always. A record at `app_status: interviewing` with no
  dated `interviews:` line is an integrity issue (`interview_undated`), so an interview cannot
  silently miss the Timeline.
- **Saving needs `python engine/tools/serve.py`** (127.0.0.1 only; regenerates the dashboard on
  every load but never runs `expire_sweep.py`). A page opened from disk cannot write files, so it
  shows the plan read-only with that command. Each save carries `rev`; a stale one is refused and
  the page reloads the plan, so an edit made elsewhere (by hand, or `plan.py add`) is never lost.

## Statistics tab (kept in sync with the generator)

The stat tiles that headed the Overview were replaced on 2026-10-10 by a **Statistics** tab
(`engine/tools/web/stats.js` · `stats.css`, inlined like the plan tabs): hand-built SVG charts, no
library, each with a hover/focus tooltip and a *Show data* table. The integrity check lives in the
Home page's taskbar tray. Two sections:

- **Vault** — the application funnel, records by kind, a career-fit × skill-match scatter of live
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

The numbers the tiles carried are defined below; the funnel and *Records by kind* charts show them.

| Number | Definition |
|---|---|
| Search results | count of `user/workspace/inbox/processed/*.txt` (cumulative collected leads) |
| On-direction (≥N) | **shown** records with `career_fit ≥ thresholds.on_direction` (`user/settings.toml`; the label shows the number) — the "positive results" metric. Counts desirability only — a record here may still be a `reach`. **Shown-filtered only since 2026-08-29**: it previously counted every record in the vault including expired and closed leads, reading 125 when just 79 were visible. The lifetime figure survives as `positive_all` and appears in the footer note. |
| Companies / Groups / Positions / PhD | profile counts per category (PhD split from positions by `type: phd` or "PhD" in the title) |
| Overdue (unretired) | **Tripwire — should read 0;** shown only as a warning when it does not. Shown position/PhD leads with `deadline: null` past `thresholds.stale_days` that `expire_sweep.py` should already have retired. Non-zero means the sweep has not run. Leads exempt under `thresholds.verified_days` (confirmed live recently) are **not** counted — the sweep keeps them on purpose |
| CVs generated | count of `user/workspace/applications/*/` folders (or items with `cv_date`) |
| CVs sent | items with **positive evidence** of a submission: `app_status` sent/interviewing, any `sent_date`, or closed with outcome rejected/offer. `closed` **alone does not count** — a lead closed `withdrawn` was never submitted. Includes orgs, since an unsolicited application is a real send |
| Ongoing | items with `app_status` sent or interviewing |
| Offers / Rejections | items with `app_outcome` offer / rejected |

## Display rules (kept in sync with the generator)

- **Positions & PhD tabs show only *alive* leads** — a lead is alive when it is **not**
  `expired`/`closed` **and** its `deadline` has **not passed** (a lead with no deadline
  counts as alive, since it hasn't passed anything). This applies to the Positions tab,
  the PhD tab, and their tab counts. The filter is computed live from
  the current date, so a lead drops off the day after its deadline even if its `status`
  frontmatter hasn't been updated to `expired` yet.
  - This display filter and `expire_sweep.py` (step 1) are **belt and braces, not duplicates**.
    The filter only hides a stale lead from the HTML; the sweep also takes it out of
    `user/workspace/positions/open/`, so it stops consuming the company/group rotation budget in
    `/search-positions` and stops inflating the open-lead count. Before the sweep existed,
    22 of 130 "open" leads were already dead — a 17% overstatement of the active pipeline.
- **Company / group Status column shows two different facts, both labelled.**
  `applied <date> · N roles` is the last CV actually **sent** to a role at that employer, joined
  from `user/workspace/positions/`; `last contact <date>` is the last unsolicited approach, read from the
  profile's own frontmatter. An employer with no record of either reads `never applied`.
  Hover the applied line for the full list of roles, dates and outcomes.
  - "Sent" needs positive evidence — `app_status: closed` alone does not count, since leads are
    also closed with `app_outcome: withdrawn` having never been sent. A lead counts when it is
    `sent`/`interviewing`, carries any `sent_date`, or was closed `rejected`/`offer`. Sends whose
    date was never stamped show as `applied · date not recorded` rather than vanishing.
  - **This rule is `_sent_evidence()` in `dashboard.py` and the CVs-sent tile uses the same
    function.** Until 2026-08-18 the tile had its own looser set treating every `closed` record
    as sent, so it read 28 while the org rows read 22 — the 6-record gap was entirely leads
    closed `withdrawn` and never submitted. If a third place ever needs "was it sent", call that
    function rather than re-deriving the rule; two definitions is how this drifted.
  - The position→profile join reuses `dedup_check.py`'s `ALIASES` and `same_employer()` instead
    of forking that logic, then falls back to requiring every identity token of the *profile* to
    appear in the position, at least one of them discriminating (in ≤2 profiles). Direction and
    rarity are both load-bearing: overlap alone put a Digital Biotechnology Lab role under **Büll
    Lab** on the shared tokens `{dtu, bioengineering}`. Override a wrong match with `org_profile:`
    in the position's frontmatter — see *inbox-eval*.

- **There is no Best Match tab** (removed 2026-10-02 at the user's request). It was Positions + PhD
  filtered to `skill_match >= 65` and sorted by skill, which the Skill column header already does
  in one click; with three scores, a tab ranked by one of them is the kind of view the engine avoids
  (`engine/docs/decisions.md` §Best Match removed). `track: career | employability` stays a
  **column**, for provenance only — it never affects a score, a tab, or visibility.

- **The Applications tab shows everything** — every record that has an `app_status`
  (CV generated, sent, interviewing, closed) appears here regardless of deadline or lead
  status, so it stays a complete history of what was applied to even after a role expires.
  The alive-only deadline filter deliberately does **not** touch this tab.
- Expired/closed/past-deadline positions stay on disk (in `user/workspace/positions/open|closed/`) and
  still surface in the **Applications** tab with a muted `role closed`/`role expired` badge
  if a CV was generated for them (so a dead-but-worked lead is visible, just not active).
- **There is no deadline bar** (removed 2026-10-02 at the user's request). Live deadlines are
  items in the **To-do** matrix and on the **Timeline** instead: shown leads not yet
  `sent`/`interviewing`, any horizon (see §Timeline and To-do).
- **Home is an OS-style entry page** (2026-11-20, replaced the Overview top-5 tables at the user's
  request; `engine/tools/web/home.js` · `home.css`). Wallpaper, faint logo, the name, one app icon
  per page with its count, and a taskbar holding the **integrity check** (tray: ✓ or ⚠ N, click for
  the list) and a clock. Other pages carry a ⌂ Home button; Esc also goes home.
- **Link flag:** the Positions and PhD tabs' *Link · age* column shows each lead's `url_status` — yellow `⚠ unchecked` (not yet
  validated), yellow `⚠ unresolved` (the stored url is a search page or board root, so it
  can never confirm anything), or red `⚠ dead`. Clear `unchecked` by running
  `python engine/tools/link_check.py --apply`, which stamps `url_status` / `url_checked` on every open
  lead and retires the dead ones. See `engine/docs/LINK_HEALTH.md` — a plain HTTP 200 is **not** proof a
  posting is live, and on 2026-08-16 that mistake was hiding 20 dead leads in the open set.

- **Two score columns on every row, every kind.** `career_fit` (do I want it) and
  `skill_match` (can I do it) side by side. For a company or group, `skill_match` scores its
  stated stack against user/profile/competencies.md rather than requirements — the cold-outreach question
  "could I be useful here" — so both numbers are meaningful everywhere. Only `level_fit` is
  position/PhD-specific; orgs show `—` there, since nothing advertises a seniority. Sorting
  defaults to `career_fit` descending; either score column is clickable. See *Scoring* in
  [[inbox-eval]] for what each number means.

- **Wet lab column and toggle (added 2026-10-26).** Positions, PhD and Applications show
  `bench_load` (`none · light · unknown · substantial`) as a *Wet lab* column; sorting it orders
  those four, with `unknown` between `light` and `substantial` because it may be either. On the
  Positions and PhD tabs a **hide substantial wet lab** checkbox drops `substantial` rows and
  their tab counts; the browser remembers it (`localStorage`, guarded). It is a view, never a
  score: it moves no number, and Home, Statistics, the plan tabs and Applications ignore it
  (`engine/docs/decisions.md` §`bench_load`).

- **Score threshold — `thresholds.min_score_shown` in `user/settings.toml`** (read into
  `MIN_SCORE_SHOWN` in `dashboard.py`). A position/PhD lead is hidden only when **all three**
  scores fall below it. Any one clearing it keeps the row visible, which is the point of the split: a `career_fit 88 · skill_match 40` stretch role
  and a `career_fit 45 · skill_match 85` fallback are both worth seeing, and the old blended
  `fit_score` would have buried the first and flattered the second. Hidden leads stay on
  disk. Companies and groups are never hidden by score.
  The **Applications tab is exempt** — it stays a complete history, so a role that was worked
  on never disappears from the record. Visibility is decided once, by `_shown()` in Python,
  and stamped on each record as `shown`; the page's JavaScript reads that flag rather than
  recomputing it, so the tiles and the tab counts cannot drift apart. Change the number in
  one place to change the whole view.

## When to run

- After `/inbox` (new profiles or scores)
- After `/cv` (a CV was generated)
- After `/track` (status changed) — `/track` already calls this automatically
- Any time the user wants a fresh view

Because `/inbox` auto-runs `/dashboard` and `/track` calls it too, the deadline sweep in step 1
rides along with the normal pipeline — deadlines get checked on every dashboard refresh without
anyone having to remember. Days can still pass without a run, so the sweep is written to be
idempotent and to catch an arbitrary backlog rather than only yesterday's expiries.

## Related

[[PIPELINE]] · [[track]] (updates the application fields this reads) · [[inbox-eval]] · [[cv-generate]]
