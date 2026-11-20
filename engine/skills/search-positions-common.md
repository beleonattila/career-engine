---
name: search-positions-common
cssclasses:
  - skill
recommended_model: Sonnet medium — provisional, never low (see "Model and effort" below)
description: >
  Shared machinery for both position collectors (search-positions-career and
  search-positions-skill). Not invoked directly. Owns everything the two tracks do
  identically — run modes, dedup, Gates 0/2/4, sources, output format, telemetry. The two
  mode-specific steps (the keyword pass and Gate 3) are defined by whichever mode file sent
  you here.
---

# search-positions-common

**Not a command.** Read by `search-positions-career.md` and `search-positions-skill.md`,
which the `/search-positions` orchestrator runs as parallel sub-agents.

**Read `search-common.md` first** — geography, the staging protocol, and the `TRACK:` stamp
live there and are identical for both tracks.

> **[MODE] steps are owned by your mode file** (`search-positions-career.md` or
> `search-positions-skill.md`, whichever sent you here). Everything else here is shared and must
> not be forked: a fix to dedup, sources or telemetry lands once, here.

## Task:
1. Search the web using `WebFetch` for open positions matching the user's profile
2. **Run mode — fast pass or deep pass.** Two cadences, because no source enumerates reliably
   (*Why age is not a filter* below).
   - **Fast pass** — the default; run 2–3× / week. Apply each source's own recency filter at
     **~21 days** where one exists. Treat the result as a *sample*, never a complete sweep.
   - **Deep pass** — run **~weekly** (`log_run.py --stats` flags it OVERDUE after 7 days), or
     whenever the user says "deep". **No age filter at all**: collect anything still open. This run
     recovers what the fast passes dropped. **`phd_portals` is mandatory on every deep pass**
     (`engine/docs/decisions.md` §Recall on strong leads).

   State which mode you ran in the closing report.
3. **Never skip on age alone.** A lead is stale only when its **deadline has passed** or the
   posting is confirmed removed. Age is a *sort priority*, never a discard rule.
4. Check geographical relevance and job type (on-site, hybrid, remote), if not relevant then skip
5. **[MODE] Relevance gate — keyword pass.** A coarse, mechanical "is it worth an Opus pass?"
   filter; `/inbox` does the real scoring. **Your mode file defines the term list and the pass
   rule.** Normalise common variants first (shared domain content: the pack's `synonyms.md`,
   `engine/packs/<pack>/`, where `<pack>` is `search.pack` in `user/settings.toml`).
6. **Dedup against already-collected finds — this is the real cost control.** Skipping is decided
   by **identity, not by age**. Before saving, check *all four* for an entry covering the same
   org+role:
   - `user/workspace/inbox/`
   - `user/workspace/inbox/processed/`
   - `user/workspace/inbox/processed/archive/`  ← **must be checked** (skip it and the deep pass
     re-collects everything you have; `engine/docs/decisions.md` §Dedup)
   - `user/workspace/positions/{open,applied,closed}/`

   Never do this by eye or reason about slugs yourself — `dedup_check.py` does it in three layers
   of decreasing confidence (job-ad URL → same employer + identical role slug → token overlap,
   which never blocks). **The URL is the strongest signal**, so pass it whenever you have one:
   ```bash
   python engine/tools/dedup_check.py --query-url "https://jobs.ashbyhq.com/adaptyv/0b758124-…"
   python engine/tools/dedup_check.py --query cradle "Scientist, Large Libraries" "https://…"
   ```
   Org slug variants are handled **structurally** — organisation-type words (`-university`,
   `-bio`, `-institute`, `-labs`, `-pharma`, …) are stripped, so `cradle` ≡ `cradle-bio`. The
   alias table is only for renames and acquisitions (`novozymes` → `novonesis`)
   (`engine/docs/decisions.md` §Dedup: structural slug rules).
7. **Collect decision — a fixed four-gate procedure. Never a holistic judgement.** Answer the
   gates **explicitly and in order**, and record the answers in the saved `.txt`. Same ad → same
   answers → same verdict (`engine/docs/decisions.md` §The collect decision).

   **Gate 0 — hard rejects.** Any one → SKIP immediately (no further gates):
   deadline strictly before today · posting confirmed removed/filled · the ad is a portal/search
   page rather than one posting · the role is outside the geography allowlist in
   `search-common.md` (US/Canada on-site counts as outside).
   **[MODE] Your mode file may add one further hard reject** (career: the user's direction reject,
   `user/profile/search_terms.md` §Career track → *Gate 0 reject*; skill: none — no direction floor).
   *Exception — faculty:* a professor / group-leader / tenure-track call is **not** a position.
   Save it as `[groupslug]_group-profile_found-YYYY-MM-DD.txt` so it routes to the group database,
   never as a position file (`engine/docs/decisions.md` §Faculty calls).

   **[MODE] Gate 1 — keyword presence** (mechanical, zero judgement).
   List every qualifying term that literally appears in the ad, then apply your mode file's
   pass rule. Record the terms found either way.

   **Gate 2 — placement.** Does each matched term appear in the **role** text (responsibilities,
   requirements, "you will…") or only in **company** text ("about us", "our platform", mission
   boilerplate)? If *every* matched term is company-boilerplate only → **SKIP**.

   **[MODE] Gate 3 — the decisive test**, the only gate whose *question* differs:
   - **career** asks *what does the person in this role personally ship?* — a direction test.
   - **skill** asks *does this role need what I can prove I have?* — a competency test.

   Take the full procedure from your mode file: a fixed table, a single forced choice, the chosen
   row recorded in the saved `.txt`.

   **Tiebreak, shared by both:** if two rows seem to fit, pick the one describing the
   **first-listed responsibility**, or failing that the one named in the **job title**. Never
   weigh them holistically.

   **Modifier (records only, never decides):** `in_silico: yes | no | mixed`. Bench work in the
   seat is neutral per `user/profile/preferences.md`, so a bench role is not disqualified. Keep any
   ad line saying the designs are tested in house or by a named collaborator in the saved text:
   `/inbox` scores experimental validation as a `career_fit` check.

   **Gate 4 — level.** Answer *before* writing anything. The user's level and the thresholds that
   follow from it are in `user/profile/search_terms.md` §Level gate. Ask **in this order**:

   1. Is this a call for **the qualification the user is working towards** (for an MSc graduate: a
      **PhD / doctoral / graduate-school** call)? → **PASS**, regardless of any other word in the
      title. Nordic and German academic titles are misleading here; a "Senior Researcher" line in a
      PhD advert is the supervisor, not the vacancy.
   2. Does it **require a qualification the user does not hold** (for a user without a PhD: a
      **postdoc**)? → **not a position.** But a lab hiring for it is a *funded lab hiring in your
      direction*, so do not discard it: save it as `[groupslug]_group-profile_found-YYYY-MM-DD.txt`
      exactly as with the Gate 0 faculty exception, so it routes to the group database as a
      cold-outreach lead.
   3. Does the title offer a **lower level as an alternative**? → **PASS.** `(Senior) Scientist`
      and `Machine Learning Scientist / Senior ML Scientist` are open at the attainable level —
      the parentheses and the slash *are* the offer. `Senior / Lead Scientist` is not, because
      every alternative is over-level.
   4. Does the ad state a **years-of-experience** requirement at or above the user's threshold
      (`search_terms.md` §Level gate)? → SKIP. Stated years beat the title whenever both are
      present — the title is a house convention, the years are the actual bar.
   5. Otherwise, does the **job title** carry any of the user's over-level title words
      (`search_terms.md` §Level gate)? → **SKIP**.

   Record the answer as `Gate 4 (level): pass | skip | group-profile — {reason}`.
   The same test is `over_level()` in `ats_sweep.py` (its terms: `[level]` in
   `user/profile/search_terms.toml`), which demotes over-level rows out of the printed sweep;
   `level_sweep.py` applies it to the backlog.

   > **A hard gate** (measurements: `search_terms.md` §Level gate). **Never use `career_fit` to
   > argue a level-gated role back through it** — `career_fit` measures desirability only;
   > `level_fit` speaks to attainability, and a `reach` is the gate agreeing with itself.

   Faculty calls never reach this gate: the Gate 0 exception made them `_group-profile_` files.

   When the gates say COLLECT, write the ad body to a `.txt` in **your own staging folder** —
   `user/workspace/inbox/_staging/career/` or `user/workspace/inbox/_staging/skill/`. **Never write
   to `user/workspace/inbox/` directly** ([[search-common]] §Staging protocol). Use the `Gate:`
   block in *Output format* below as the audit trail. Do not fit-score here — that is `/inbox`'s job.
7.5 **Before writing anything to the inbox, run the dedup guard:**
   ```bash
   python engine/tools/dedup_check.py
   ```
   It compares every `user/workspace/inbox/*.txt` against the whole vault (including
   `processed/archive/`) and exits non-zero on a duplicate. Not optional — eyeball dedup has
   demonstrably failed (`engine/docs/decisions.md` §Dedup). Use `--query <org> "<role title>"` to
   check a single candidate *before* fetching its full ad text.

   > ⚠️ **`possible-dup` does not block** — slug *containment* cannot tell a seniority variant from
   > a genuine second req, so the guard hands the row to **you**. **Read both files and decide
   > before writing.** A trailing word on the role slug is the signature. Same employer + same
   > job-ad URL, or same employer + a role slug differing only by a descriptive suffix → duplicate,
   > skip; genuinely different seniority or a different req → collect. `--query-url` settles most
   > of these outright (`engine/docs/decisions.md` §Dedup: `possible-dup`).
8. **Stop criteria and budget.** 30 min of runtime, or all relevant sources covered. **Allocate
   the budget up front rather than working top-to-bottom until time runs out** — first-come-first-
   served starves the same sources (`engine/docs/decisions.md` §Budget).

   **Start by asking the log what this run should cover.** These three are not optional:
   ```bash
   python engine/tools/log_run.py --starved && python engine/tools/log_run.py --next-queries 4
   python engine/tools/log_run.py --stats        # read the deep-pass line
   ```
   - `--starved` lists channels **not reached in the last 3 runs**. They get **first claim** on
     the budget, before the usual split — such a channel is *unmeasured*, not low-yield.
   - `--next-queries` gives the least-used LinkedIn keywords. Issue those, plus at most one free
     choice. Never pick terms by feel.
   - If the deep-pass line says **OVERDUE**, this run is a deep pass. Not a judgement call.

   Rough split for what remains:
   - `ats_sweep.py` — ~2 min, near-zero tokens. **Always run it**; it costs almost nothing.
     Then `ats_sweep.py --uncovered` lists the band-A employers the sweep cannot see: check the
     top **5** by hand (careers page, or `WebSearch` if it blocks), and register any ATS host you
     find (Group 0) — a registered board leaves the list for good, so the list rotates by
     shrinking. Log those checks under `company_rotation`.
   - LinkedIn country loop — ~40% of the remaining budget. The `linkedin_required` countries are
     mandatory **on both tracks, every run** — drop query variants before you drop one of them,
     and before you read fewer than three pages of a query (§Group 1); `log_run.py` warns on both.
   - Company / research-group rotation — ~30%, oldest-`last_evaluated` first, no-tracked-lead first.
   - Regional + academic boards (the pack's `boards.md`) — ~30%.

   If a category gets no time at all, name it in the report — it will then appear in `--starved`
   next run.

   > ⚠️ **`phd_portals` is the highest-value starved channel** (`engine/docs/decisions.md` §Budget).
   > When `--starved` names it, it outranks the company rotation; on a deep pass it is never optional.
9. Report progress: "X added this session, # of new entries found", **plus the run mode
   (fast/deep)** and which sources were checked vs. skipped. A source you did not reach is not
   a source that had nothing — say so explicitly.
10. **Log the run — mandatory, every run, including runs that found nothing.**
    Write a JSON record per `engine/docs/LOG_SCHEMA.md`, then:
    ```bash
    python engine/tools/log_run.py run.json
    ```
    It validates and appends to `user/workspace/logs/search_runs.jsonl`; malformed records are rejected.

    **Record the run's configuration and its clock.** `model` (`haiku`/`sonnet`/`opus`/`fable`),
    `effort` (`low`/`medium`/`high`/`xhigh`/`max`), and both `started` and `ended` as ISO-8601 are
    all required; `duration_min` is derived by the script — never write it yourself. Note the
    start time when the run *begins*, not at the end.

    **Log what you REJECTED, not only what you collected.** The `screened` array is required.
    Without it, "never reached the channel" and "saw it and rejected it" look the same, and they
    have opposite fixes. A zero-find run is one of the most informative records.

    Be exact about `channels[].status`: `skipped` ≠ `reached with no results`. `channels[].key`
    is a **closed vocabulary** (`ats_sweep` · `linkedin` · `danish_boards` · `nordic_boards` ·
    `euraxess` · `phd_portals` · `company_rotation` · `research_groups`); validation rejects
    anything else.

    For `linkedin`, log the actual `geos` and `queries` issued **and both `hits` and
    `shortlisted`** — that pair is the triage step, and without it a source miss cannot be told
    from a skimmed row (`engine/docs/decisions.md` §Search telemetry).

---

## Why age is not a filter

No source here sees everything in its window (LinkedIn returns a ranked, unstable sample), so an
age filter turns a missed posting into a **permanent** miss — and saves almost nothing, because the
expensive stages are gated by dedup, not age. **Its savings and its losses are the same set.**

Hence: dedup on identity (step 6), sample cheaply on the fast pass, sweep without an age limit on
the deep pass. Never reinstate the old 14-day hard filter (`engine/docs/decisions.md` §Why age is
not a filter).

---
## Output format

> ⚠️ **`POSTED:` is load-bearing — never leave it out** ([[search-common]] §Rules both tracks
> share). Take it from the authoritative source — `first_published` / `publishedOn` /
> `publishedAt` from an ATS, the portal's own "posted" date, or LinkedIn's "X days ago" converted
> to a date. Write `unknown` only when the source states none; never guess.

**file name:**

`[orgslug]_[roleslug]_found-[YYYY-MM-DD].txt`

**file content:**

SOURCE: {exact URL of the job ad}
POSTED: {YYYY-MM-DD — the posting's OWN publish date, or `unknown`}
FOUND: {YYYY-MM-DD}

Title: {job_title}
Org: {organisation_name}
Location: {city, country}
Keywords: keyword_1, keyword_2, keyword_3

Gate 1 (terms found): {mode-specific — see your mode file for the exact line}
Gate 2 (placement): role | boilerplate-only
Gate 3: {mode-specific — career records the output row; skill records the competencies matched}
Gate 4 (level): pass | skip — {PhD call | years stated | level word found | none}
in_silico: yes | no | mixed

{full verbatim text of the job ad}

---
## Output example

**file name:**

Protein Design and Biophysics Specialist - DTU Bioengineering_found-2026-06-13.txt

**file content:**
```
SOURCE: https://www.linkedin.com/jobs/view/4426747303/
FOUND: 2026-05-29

Title: Protein Design and Biophysics Specialist - DTU Bioengineering
Org: DTU Bioengineering
Location: Lyngby, Denmark
Keywords: RFdiffusion, ProteinMPNN, AlphaFold, protein engineering

[full verbatim text of the job ad]
```

---
## Geography

**Defined once, in [[search-common]] §Geography — read it there**, including the `remote_only`
check before the fetch. On LinkedIn, **never rely on `location=European Union` alone** — it
excludes Switzerland, Norway, Iceland and the UK entirely (the country loop in Group 1 below).

---

## How and Where to Search

**Step 1 — Check the company + research-group databases first.**
Before hitting job boards, sweep `user/workspace/organizations/companies/` **and**
`user/workspace/organizations/research_groups/` for new openings at orgs already in the vault.
Academic PI labs live only in `research_groups/` — skip it and you cannot find their postings.

- **[MODE] Which orgs to sweep.** **Career**: orgs at `career_fit` 60+. **Skill**: orgs at
  `skill_match` **or** `method_fit` 60+, plus any org with a logged method sighting, in the order
  `python engine/tools/method_sightings.py --rotation 30` prints. An org clearing both is swept by
  both; reconciliation drops the duplicate. **Geography is not a score threshold** — the country
  allowlist decides it (`engine/docs/decisions.md` §Geography is not a score threshold).
- **Rotate oldest-checked-first; don't re-hit the same names.** Sort each folder by
  `last_evaluated` ascending and work a capped batch per run (~15–20 companies + ~10 groups), so
  coverage cycles through the whole database. ("Checked >7 days ago" is always true, so it is no filter.)
- **Within that batch, check orgs with NO tracked lead first; only then break ties by
  oldest `last_evaluated`** — an org with a lead has been mined already.
  - **"Has a tracked lead" = a matching file in `user/workspace/positions/{open,applied,closed}/`,
    NOT the profile's `open_positions:` field**, which is often stale or empty. Glob
    `user/workspace/positions/` for the org slug, normalising aliases
    (`user/workspace/organizations/aliases.toml`; a group vs its parent). Cases:
    `engine/docs/decisions.md` §Org rotation.
- Find keywords to target the search at `user/profile/preferences.md` -> Job ad Keywords.
- **Hit the org's ATS endpoint before any job board** (*Group 0* below): one call returns the
  employer's complete open-role list with authoritative publish dates, no age filter needed.
- **If a domain 403s or cert-errors on `WebFetch`, don't retry the same URL.** Pivot to
  `WebSearch` for `"<org name>" careers <role keyword>` — the snippet usually surfaces the posting.

**Step 2 — Job boards.**
Run 5–10 distinct queries across as many sources as needed. Prioritise sources where
results can be filtered to the **past 2 weeks** (14 days) — this is the hard freshness
window; discard anything older. Work through groups in order.

#### Group 0 — Employer ATS endpoints ⭐ **do this first — it is one command**

```bash
python engine/tools/ats_sweep.py
```

`ats_sweep.py` fetches **every** confirmed employer board in one pass (~2 min, pure HTTP, **zero
LLM tokens**) and prints a ranked TSV — newest and most relevant first — to
`user/workspace/logs/ats_sweep_latest.tsv`. Make the collect/skip calls from that table. **Never**
check companies one at a time by hand (`engine/docs/decisions.md` §The ATS sweep enumerates).

Columns: `tier` · `age_d` · `published` · `org` · `fit` · `status` · `title` · `location` · `url`

- **`tier`** — `T1` / `T2` from the relevance gate, matched on the **title**;
  **`T1b` / `T2b`** = the term is in the ad **body**, not the title (Gate 2 still has to be
  answered when you open it); **`T2?`** = a generic title at a small good-fit employer — worth
  opening.
  **`M` / `Mb` / `M?`** are the **skill track's method lane** and only fill a row the tiers above
  left at `-`: `M` = the title names a method-building seat (research software / research
  engineer …); `Mb` = the role text says the seat builds tools, pipelines or methods *for
  scientists*; `M?` = a software/engineering title (whole word, corporate functions excluded) at
  an employer with a logged method sighting, on a board of at most 100 postings. Terms:
  `[sweep.method]` in `user/profile/search_terms.toml`. The career track ignores them; the skill
  track reads them per [[search-positions-skill]] §Method lane.
- **`status`** — `tracked` (org+role already in the vault, skip) · `new-role` (known org, new role —
  collect if it clears the gate) · `NEW-ORG` (no lead anywhere yet — highest value).
- **`age_d`** is information, not a filter. The script applies **no age limit** by design.
- **Only tiered rows are printed**; the untiered remainder still goes to the TSV.
- Flags: `--show-all` (also print tier `-`) · `--all-geo` (include non-European) ·
  `--all-roles` (skip the title prefilter — it costs no recall) · `--no-body`
  (title-only tiering) · `--max-age N` (opt-in only).
- The footer reports **per-board posting counts**, boards returning **zero**, and boards that
  **failed**. A failed or empty board is not a board with no roles — say so in the run report.
  A board that halves between runs is a paging regression, not an employer that stopped hiring.

**The sweep enumerates; it does not sample.** Workday and SmartRecruiters are paged in full
(Workday's `searchText` is fuzzy relevance ranking, not a keyword filter).

Boards without a working endpoint (mostly big pharma and Danish biotech whose tenant+site cannot
be guessed) are *not* covered by the sweep and still need a manual/WebSearch check. To extend
coverage:

```bash
python engine/tools/ats_discover.py            # probe companies not yet cached; retries past failures
python engine/tools/ats_discover.py --refresh  # re-probe everything (~5 min)
```

It writes `user/workspace/cache/ats_slugs.tsv`. Rows marked `review` use a collision-prone short
slug and are excluded from the sweep until confirmed by hand (`ashby:novo` is not Novo Nordisk).
Confirm a board belongs to the right employer before promoting it into `[confirmed_by_hand]` in the
pack's `ats_seeds.toml`.

**Blind slug guessing does not work for these** (`engine/docs/decisions.md` §The ATS sweep
enumerates). What works is reading the ATS host off the employer's own careers page and registering it:

```bash
python - <<'EOF'
import urllib.request, re
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'}
RX = re.compile(r'https?://[A-Za-z0-9._-]*(?:myworkdayjobs\.com|greenhouse\.io|ashbyhq\.com|lever\.co|smartrecruiters\.com|workable\.com|recruitee\.com|teamtailor\.com|hr-on\.com|oraclecloud\.com)[^\s"\'<>)]*', re.I)
h = urllib.request.urlopen(urllib.request.Request('<CAREERS URL>', headers=UA), timeout=25).read().decode('utf-8', 'replace')
print(sorted(set(RX.findall(h)))[:6])
EOF
```

Add a Workday tenant to `[workday]`, an Oracle ORC host to `[oracle]`, or a Workable account to
`[workable]`, in the selected pack's `ats_seeds.toml` (`engine/packs/<pack>/`), whenever you
discover one by hand. `ats_discover.py` seeds them straight into `user/workspace/cache/ats_slugs.tsv`,
so an entry needs **no** `user/workspace/organizations/companies/` file (DTU is a university, not a
company profile). Employer-specific board notes: the pack's `boards.md` §ATS notes.

---

**Reference — the raw endpoint patterns** (for employers not in the cache, or one-off checks).
The **only sources that enumerate completely**, with authoritative publish dates. Prefer them over
every aggregator; apply **no age filter** here.

| ATS | Pattern | Date field |
|---|---|---|
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | `first_published` |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/{slug}` | `publishedAt` |
| Lever | `https://api.lever.co/v0/postings/{slug}?mode=json` | `createdAt` |
| Workday | `POST https://{tenant}.wdN.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` body `{"searchText":"","limit":20,"offset":N}` | `postedOn` |
| SmartRecruiters | `https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset=N` | `releasedDate` |
| Workable | `https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true` | `published_on` |
| Recruitee | `https://{slug}.recruitee.com/api/offers/` | `published_at` |
| Oracle ORC | `https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs%3BsiteNumber%3D{site}%2Climit%3D200%2CsortBy%3DPOSTING_DATES_DESC` | `PostedDate` |

**Oracle Recruiting Cloud (ORC)** — one **GET**, no browser, no body. Response shape:
`items[0].requisitionList[]`, each with `Title` · `PostedDate` (already `YYYY-MM-DD`) ·
`PrimaryLocation` · `Id`. Public job link: `https://{host}/hcmUI/CandidateExperience/en/sites/`
`{site}/job/{Id}`. Common in **European academia and the public sector**.
- `{host}` is `{tenant}.fa.{pod}.oraclecloud.com` — an opaque 4-char tenant id, **not guessable**. Read
  it off the employer's real careers URL (or a vanity domain's redirect target) once; it is permanent.
- `{site}` does **not** filter the result set (any value returns the whole tenant), but it is
  needed for working job links. Given a host, resolve it automatically:
  ```bash
  python engine/tools/ats_discover.py --orc efzu.fa.em2.oraclecloud.com
  ```
  which reads the tenant's own `recruitingCESites` resource, picks the `ORA_ACTIVE` site, and
  prints the line to paste into `[oracle]` in the pack's `ats_seeds.toml`.

- **Workday: leave `searchText` empty and page on `offset`.** `limit` is hard-capped at 20 (25 →
  HTTP 400) and the first page's `total` is the board size — page until `offset >= total`, never
  stop on a short page (Workday returns short intermediate pages). Never filter server-side.
- **Trust `first_published`, never `updated_at`** — a periodic re-sync bumps `updated_at` without
  a new posting, and aggregators surface the wrong one.
- Confirmed working slugs for the pack's employers: the pack's `boards.md` §ATS notes.
- Work through the `user/workspace/organizations/companies/` batch this way each run — it is roughly one call per org.

#### Group 1 — General job boards

| Source        | URL                         | Notes                                   |
| ------------- | --------------------------- | --------------------------------------- |
| LinkedIn Jobs | linkedin.com/jobs           | A **sampler, not an enumeration** — see the block below. Use the direct search URL, not a generic web search. |
| Indeed        | indeed.com                  | Set the date filter to "Last 14 days"   |

**LinkedIn — fetch the dated search URL directly; don't `WebSearch` for
`site:linkedin.com/jobs/view ...`.** A generic web search ranks by relevance/authority,
which mostly surfaces LinkedIn's cached, long-expired postings (multi-year-old "no
longer accepting applications" listings) rather than genuinely fresh ones. Instead,
build the URL with LinkedIn's own recency filter and `WebFetch` it directly:

`https://www.linkedin.com/jobs/search/?keywords=<terms>&location=<COUNTRY>&f_TPR=r1814400`

- `f_TPR=r1814400` = 21 days in seconds (fast pass). Drop `f_TPR` entirely on a deep pass.
- **Read three pages, one country at a time** — "reached but not returned" is the largest LinkedIn
  miss on strong leads (`engine/docs/decisions.md` §Recall on strong leads). The guest endpoint
  pages cleanly, 10 cards per page:
  `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=<terms>&location=<COUNTRY>&f_TPR=r1814400&start=0`
  then `start=10` and `start=20`. **Three pages per query in every country you run, fast or deep.**
  Exactly two reasons to stop early, both facts about the page just read:
  - `exhausted` — the page returned fewer than 10 cards; there is no next page.
  - `no_shortlist` — not one card on the page made the shortlist; that ends the query in that country.

  "Relevance had fallen off" is not a reason unless the page you just read shortlisted nothing. If
  the run is time-boxed, **drop a query, not a page** — a query run to page 1 everywhere looks like
  coverage and is not (`engine/docs/decisions.md` §Judging the 2026-10-01 fixes).
  `sortBy=DD` has **no effect** on this endpoint, so page, don't sort. Log every page fetched in
  `hits`, the page count in `pages`, and every query × country that stopped short in `short_pages`
  (`engine/docs/LOG_SCHEMA.md`); `log_run.py` warns when the pages do not add up.
- **One recruiter query per pass.** `log_run.py --next-queries` prints it last, marked
  `<- recruiter query` (`recruiter_queries` in `user/profile/search_terms.toml`). Agencies post
  strong roles under generic titles. Run it in the required countries like any other query.
- **`location` MUST be looped over countries, in the configured order** (ordered by measured
  yield). **The first `linkedin_required` entries are not optional** — if the run is time-boxed,
  drop keyword variants, not countries. Order and required count are the user's: `linkedin_loop`
  and `linkedin_required` in `user/settings.toml` `[geography]`.
  > ⛔ `location=European Union` does **not** cast the full net: LinkedIn treats country tokens as
  > *disjoint* sets — the EU token returns **zero** CH/NO/UK and under-samples Denmark and Sweden
  > (`engine/docs/decisions.md` §LinkedIn geography tokens).
- **LinkedIn is a sampler, not a source of truth** — its result set is ranked and unstable
  (`engine/docs/decisions.md` §Why age is not a filter). So:
  - Never conclude "nothing new" from a LinkedIn query returning nothing.
  - Never treat a repeat run of the same query as verification — it is a second random sample.
  - Cross-check anything interesting against the employer's ATS endpoint (Group 0).
- **Never choose `keywords` by feel — ask the log.** `python engine/tools/log_run.py --next-queries 4`
  prints the most overdue terms of the rotation pool (`query_pool` in
  `user/profile/search_terms.toml`; `search_terms.md` §LinkedIn queries lists its term groups and
  the PhD queries). Compound queries count: `A OR B OR C` credits all three pool terms.
  One fetch per combination returns a dated list (title, org, location, "X days ago") — filter that
  list against the tiers and dedup directly, rather than searching one posting at a time.

#### Groups 2–3 — the domain pack's boards

Science and academic boards, regional national sources, and the university portals academic
posts use instead of LinkedIn are domain content: read `engine/packs/<pack>/boards.md`, where
`<pack>` is `search.pack` in `user/settings.toml`. It covers the regions of the allowlist only.

---

#### ⛔ Known stale-prone sources — do not trust a date from these

The pack's `boards.md` §Known stale-prone sources lists the aggregators and scrapers that serve
dead postings as current in this field. Use them only to *discover* a lead, then confirm against
the employer's own site or ATS before collecting.

> ⛔ **LinkedIn `ad-library/job/detail/<id>` returns HTTP 200 for dead postings** — the worst
> offender, because it fails silently (`engine/docs/decisions.md` §Link health). Never treat a 200
> from that surface as evidence a posting is live. The canonical `linkedin.com/jobs/view/<id>` page
> is authoritative — it redirects with `trk=expired_jd_redirect` or renders "No longer accepting
> applications". When collecting from LinkedIn, **store the `/jobs/view/<id>` form in `url:`**.

### Link-health pass — run this, don't hand-roll it

```bash
python engine/tools/link_check.py            # report only, writes user/workspace/logs/link_check_latest.tsv
python engine/tools/link_check.py --apply    # stamp url_status/url_checked, retire the dead
```

It checks every open lead reaching `thresholds.min_score_shown` (`user/settings.toml`) on **any** of
`career_fit`, `method_fit` or `skill_match`, re-checks LinkedIn leads against the canonical job
view, and refuses to archive a bare 404 (reported as `DEAD_UNCONFIRMED` — confirm in a browser,
then re-run with `--trust-404`). Rationale: `engine/docs/LINK_HEALTH.md`.

Recruiter-fronted listings (Hays, Barrington James, VRS, SRG) are often real but anonymised and
sometimes speculative — collect only if the actual employer or a concrete role spec can be confirmed.

---

PhD query additions (they double as `keywords=` values for the LinkedIn URL technique above):
`user/profile/search_terms.md` §LinkedIn queries.

PhD-specific portals a general job search structurally misses, and niche boards: the pack's
`boards.md` §PhD portals.

---
## Telemetry — how we find out what the search misses

Recall cannot be measured directly, and need not be: **when a run finds a post that was already
live during an earlier run, that earlier run missed it** — and the telemetry says why.

```bash
python engine/tools/analyze_misses.py        # attribution report
python engine/tools/analyze_misses.py --json                   # feed this to Opus for the reasoning pass
python engine/tools/log_run.py --stats                         # skipped channels + yield by model/effort/mode
```

`analyze_misses.py` does only the deterministic part: for every collected lead it finds the runs
that *should* have caught it (posted before the run, found after) and assigns a cause —
`CHANNEL_SKIPPED` · `CHANNEL_NOT_RUN` · `CHANNEL_FAILED` · `GEO_GAP` · `QUERY_GAP` ·
`AGE_EXCLUDED` · `GATED_OUT` · `UNTIERED` · `UNSCREENED` · `SOURCE_INCOMPLETE`. Full definitions in
`engine/docs/LOG_SCHEMA.md`. The two sweep causes need each run's sweep output, which `log_run.py`
archives when it logs the run.

**The cause histogram is the deliverable.** Read it as: lots of `CHANNEL_SKIPPED` → the run budget
is the bottleneck · lots of `GATED_OUT` → precision was bought with recall, re-read the Gate 3
buckets · lots of `SOURCE_INCOMPLETE` → stop tuning that source, add an independent one · lots of
`UNTIERED` → the sweep returned it and its tier rules hid it, so fix the tiering · any
`AGE_EXCLUDED` → an age filter has crept back in. Re-run `analyze_misses.py` for today's numbers
(the last snapshot: `engine/docs/decisions.md` §Search telemetry).

`analyze_misses.py` also excludes **redundant collections** — a lead re-collected under a different
slug — from the miss counts, and reports them separately. They are dedup failures, not misses.

---

## Model and effort

**The recommended model is not settled — it is not measured yet** (`engine/docs/decisions.md`
§Model and effort). In short: no configuration is distinguishable on `coll/run`; screening volume
tracks channel breadth, not model or effort, while collections stay flat; and **this is not
settleable by A/B testing at this run rate — stop planning to settle it.**

What to do instead:

- **Decide the setting on cost and on qualitative grounds, not on `coll/run`.**
- **Keep logging `model` and `effort` anyway.** It costs nothing, is unrecoverable if skipped, and
  is the only thing that would reveal a large effect.
- **Put measurement effort where the events are** — per-*candidate* facts (the `screened` reason
  histogram, the channel→conversion table), not per-run outcomes.

---

## Related

[[search-common]] (geography · staging · TRACK — read first) ·
[[search-positions-career]] · [[search-positions-skill]] (the two mode files that own the
**[MODE]** steps above) · [[background]] · [[preferences]] · [[competencies]] ·
[[inbox-eval]] (the THINK stage — run /inbox on Opus after every search) ·
[[search-companies-career]] · [[search-companies-skill]] · [[search-groups-career]] ·
[[search-groups-skill]] (sibling collectors → same staging protocol) ·
[[cv-generate]] (consumes the profiles /inbox builds)
