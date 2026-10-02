---
name: dashboard
cssclasses: [skill]
recommended_model: Haiku (low effort)
description: >
  Generate / refresh the career dashboard. Trigger on /dashboard, "refresh the
  dashboard", "update the dashboard", "show my stats", "regenerate dashboard". Runs the
  generator that scans the vault's profiles and position leads, computes statistics, and
  writes a self-contained user/workspace/artifacts/dashboard.html with ranked tabs (companies, research groups,
  positions, PhD), an applications funnel, and stat tiles.
---

# dashboard

Builds `user/workspace/artifacts/dashboard.html` — a single self-contained file (no dependencies,
no server) with stat tiles, an application funnel, and sortable/filterable tabs ranked
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

   - **`⚠ unproven (N)`** — reported, never retired: leads stamped `url_status: working` on a
     `linkedin.com` URL, a verdict `link_check.py` has been unable to produce since 2026-08-16.
     Any survivor predates that fix and means nothing. First run: **7**, all corrected to
     `unverified`.

   > **`expire_sweep.py` and `dashboard.py` read the same `thresholds.stale_days`**, so they
   > cannot drift apart. The sweep retires; the dashboard tile is a **tripwire** that should read **0**, because
   > `/dashboard` runs the sweep as step 1. A non-zero *Overdue (unretired)* tile means the sweep
   > has not run.

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

If `python` is missing, report it and point the user at `dashboard.py` (no other deps
are required — standard library only).

## Stat definitions (kept in sync with the generator)

| Tile | Definition |
|---|---|
| Search results | count of `user/workspace/inbox/processed/*.txt` (cumulative collected leads) |
| On-direction (≥N) | **shown** records with `career_fit ≥ thresholds.on_direction` (`user/settings.toml`; the tile shows the number) — the "positive results" metric. Counts desirability only — a record here may still be a `reach`. **Shown-filtered only since 2026-08-29**: it previously counted every record in the vault including expired and closed leads, reading 125 when just 79 were visible. The lifetime figure survives as `positive_all` and appears in the footer note. |
| Companies / Groups / Positions / PhD | profile counts per category (PhD split from positions by `type: phd` or "PhD" in the title) |
| Overdue (unretired) | **Tripwire — should read 0.** Shown position/PhD leads with `deadline: null` past `thresholds.stale_days` that `expire_sweep.py` should already have retired. Non-zero means the sweep has not run |
| CVs generated | count of `user/workspace/applications/*/` folders (or items with `cv_date`) |
| CVs sent | items with **positive evidence** of a submission: `app_status` sent/interviewing, any `sent_date`, or closed with outcome rejected/offer. `closed` **alone does not count** — a lead closed `withdrawn` was never submitted. Includes orgs, since an unsolicited application is a real send |
| Ongoing | items with `app_status` sent or interviewing |
| Offers / Rejections | items with `app_outcome` offer / rejected |

## Display rules (kept in sync with the generator)

- **Positions & PhD tabs show only *alive* leads** — a lead is alive when it is **not**
  `expired`/`closed` **and** its `deadline` has **not passed** (a lead with no deadline
  counts as alive, since it hasn't passed anything). This applies to the Positions tab,
  the PhD tab, their tab counts, and the Overview top-5. The filter is computed live from
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
- **Deadline bar** shows only *still-actionable* upcoming deadlines (≤30 days): it excludes
  leads that are `expired`/`closed` and those already `sent`/`interviewing` (no reminder is
  needed for a role you've applied to).
- **Link flag:** each deadline shows its `url_status` — yellow `⚠ unchecked` (not yet
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
