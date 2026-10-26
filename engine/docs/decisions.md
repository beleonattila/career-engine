# Decisions — the cases behind the rules

Why particular engine rules exist, told through the records and measurements that exposed them. The
skills and CLAUDE.md state each rule and point here; this file keeps the dated story so a skill can stay short.
Nothing here is personal: the user is "the user", and people are left unnamed. Numbers are as
measured on the date given — re-run the tool for today's figures.

---

## Search (`engine/skills/search-positions-common.md`)

### Why age is not a filter (2026-07-29)

*Rule: search-positions-common.md §Why age is not a filter; step 3 (never skip on age)*

*Measured 2026-07-29. This section exists so the old 14-day hard filter does not get reinstated.*

A tight age window is a sound **incremental-sync watermark** — "anything older was already seen in
a previous run, so re-examining it is waste" — and at 2–3 runs/week it gives every posting 4–6 runs
of exposure. It has one precondition: **each run must actually see everything in its window.**

That precondition is false. LinkedIn's unauthenticated search returns a *ranked, unstable subset*,
not an enumeration. Same keywords, same day: `f_TPR=r1209600` (14 d) returned **47** results while
`f_TPR=r2592000` (30 d) returned **10**. A wider window returning fewer results is impossible for a
real filter-and-enumerate — so "not returned" never means "not there".

The two combine badly. An age filter cannot distinguish *known* from *merely unsampled*, so from
day 15 a missed posting is discarded before it is ever considered — the miss becomes **permanent and
unrecoverable**. Worked example: Latent Labs *ML Scientist, London*, published 2026-06-29 and still
live 30 days later, at a company already tracked in the vault. It was missed while fresh (UK, so
excluded by the geography bug), and age then locked it out for good. One rule caused the miss; the
other made it irreversible.

The filter also saves almost nothing where it was applied. On LinkedIn `f_TPR` already filters
server-side, so the rows are fetched either way; on an ATS endpoint the employer's full open-role
list arrives in one call regardless. The expensive stages — per-posting deep fetch and the Opus
scoring in `/inbox` — are gated by **dedup**, not by age. So the only tokens an age filter saves are
those spent on postings aged 15+ days that are *not already in the ledger* — which is exactly the set
of jobs being missed. **Its savings and its losses are the same set.**

Hence: dedup on identity (step 6), sample cheaply on the fast pass, and sweep without an age limit on
the monthly deep pass.

### Dedup: `archive/` is live dedup surface

*Rule: search-positions-common.md step 6*

⚠️ `archive/` was previously excluded, on the reasoning that anything older than 2 weeks was
outside the collection window anyway. That reasoning was circular with the old age filter and
is void now that the deep pass has no age limit. Skip `archive/` and the deep pass will
re-collect and re-score everything you already have.

### Dedup: structural slug rules replaced the alias allowlist (2026-07-29 … 08-08)

*Rule: search-positions-common.md step 6*

⚠️ The old hand-maintained alias allowlist missed **four collisions in ten days**
(2026-07-29 … 08-08): `cbmr`/`ku-cbmr`, `cradle`/`cradle-bio`,
`cranfield`/`cranfield-university`, `kuleuven-dewilde`/`ku-leuven` — three of them with
byte-identical role slugs. Each cost an ad fetch, an inbox write and a full Opus scoring
pass, and each was then counted as a *late discovery*, inflating the miss statistics.
Re-checked over the whole vault, the structural rule catches 12 historical duplicates the
old one let through, with zero false merges.

### Dedup: `possible-dup` is yours to decide (2026-07-30, 2026-08-08)

*Rule: search-positions-common.md step 7.5*

⚠️ **`possible-dup` does not block, and that is where the residual leak is.** The guard
deliberately refuses to block on slug *containment*, because containment cannot tell a
seniority variant from a genuine second req — on 2026-07-30 it called two live Basecamp
postings (distinct URLs, different seniority) duplicates of each other. So a `possible-dup`
row is handed to **you**, not resolved for you.

**Read both files and decide before writing.** Measured 2026-08-08: of four duplicates that
reached `/inbox` in one run, three were caught as hard `tracked` and the fourth —
`kuleuven-dewilde/phd-nanobody-blood-brain-barrier-**delivery**` against the tracked
`.../phd-nanobody-blood-brain-barrier` — returned `possible-dup` and sailed through, costing a
full Opus scoring pass. A trailing word on the role slug is the signature. Same employer +
same job-ad URL, or same employer + a role slug differing only by a descriptive suffix →
treat as a duplicate and skip; genuinely different seniority or a different req → collect.
`--query-url` settles most of these outright, so pass the URL whenever you have one.

### The collect decision is a fixed procedure (2026-07-29 / 07-30)

*Rule: search-positions-common.md step 7*

⚠️ "Does this feel relevant?" is not reproducible. On **2026-07-29** a run skipped all four
Basecamp Research roles as *"ML infra/data curation, not protein design output"*; on
**2026-07-30** a run collected all four. Same four ads, opposite verdicts, one day apart.
Answer the gates below **explicitly and in order**, and record the answers in the saved
`.txt`. Same ad → same answers → same verdict.

### Faculty calls become group profiles (2026-07-30)

*Rule: search-positions-common.md step 7, Gate 0 exception*

Learned 2026-07-30: a KU CPD professorship collected as a position would have been read and
discarded by `/inbox`, losing the cold-outreach signal.

### Budget: `phd_portals` outranks the company rotation (2026-08-09)

*Rule: search-positions-common.md step 8*

⚠️ **`phd_portals` is the highest-value starved channel.** Measured 2026-08-09 across 176
scored profiles: PhD roles have a **median fit of 70** against 52–63 for every other level,
and hold **12 of the vault's 23 strong (≥75) leads**. That channel was reached in 1 of 16
runs and absent from the log entirely in 11. When `--starved` names it, it outranks the
company rotation.

### Geography is not a score threshold (2026-08-17)

*Rule: search-positions-common.md §How and Where to Search, step 1*

**Geography is not a score threshold.** The old rule ("60+ inside EU/EEA+CH, 80+ outside")
used the blended `fit_score` as a proxy for "is this worth the relocation". That proxy was
dropped on 2026-08-17 — the scores now measure direction and competence, neither of which
has anything to say about relocation, and an explicit country allowlist ([[search-common]]
§Geography) does the job the proxy was doing badly.

### Remote-only regions: leads from the older, looser rule stay

*Rule: search-positions-common.md §Geography*

⚠️ **US and Canadian postings need a remote check before the fetch, not after.** The vault
already holds many US leads collected under the older, looser rule (Arc, Altos, Biohub, Broad,
Janelia, Genentech, Generate, Inceptive). Those stay; new ones qualify only when the ad itself
states EU-remote or worldwide-remote. If the listing page does not say, it does not qualify —
opening the ad to find out is the token spend the allowlist exists to prevent.

### LinkedIn geography tokens are disjoint (2026-07-29)

*Rule: search-positions-common.md Group 1, the country loop*

⛔ The old guidance — *"`location=European Union` casts the full geography net in one call"* —
was **measured false on 2026-07-29**. LinkedIn treats these as *disjoint* sets, not nested.
Same keywords, same day: `European Union` → 47 hits with **zero** CH/NO/UK;
`United Kingdom` → 60 hits including several Tier-1 bullseyes; `Switzerland` → 8.
GSK's *Molecular Design Engineer* (Stevenage) was invisible to the EU query and sat at the top
of the UK one. Running `Denmark` and `Sweden` separately is also worth it — the regional token
under-samples them.

### Org rotation: a tracked lead is a file, not `open_positions:`

*Rule: search-positions-common.md §How and Where to Search, step 1*

- **Within that batch, check orgs with NO tracked lead first; only then break ties by
oldest `last_evaluated`.** An org that already has a lead in the vault has, by
definition, been mined — re-checking mostly resurfaces duplicates (exactly what
happened with Sanofi and Roche: real-looking hits, both already archived). One with
nothing tracked yet is structurally more likely to yield a genuinely new find.
- **"Has a tracked lead" = a matching file in `user/workspace/positions/{open,applied,closed}/`,
NOT the company profile's own `open_positions:` field.** That field is frequently
stale/empty even when leads exist — Sanofi and Roche both show `open_positions: []`
despite having live tracked roles (`sanofi_…-gent_2026-06.md`, the `roche-ihb_…`
files). Trusting it would sort exactly the over-mined names to the *front*. Instead
glob `user/workspace/positions/` for the org slug, normalising aliases (`servier-symphogen` ≡
`symphogen`, `roche` ≡ `roche-ihb`, a group vs its parent).

### The ATS sweep enumerates; it does not sample (2026-08-08)

*Rule: search-positions-common.md Group 0*

**The sweep enumerates; it does not sample.** Until 2026-08-08 the Workday puller issued three
fixed search terms at `limit 20` with no paging — at most 60 rows per employer. Amgen has **1716**
live requisitions; Zealand Pharma (Copenhagen, peptides) returns 0 for `protein` and 10 for
`peptide`, so the sweep saw 2 of its 11 roles. Workday's `searchText` is fuzzy relevance ranking,
not keyword filtering — `peptide` at Zealand returns *UX Designer* — so those 60 rows were close
to arbitrary. Workday and SmartRecruiters are now paged in full: **900 → 8300 postings** per run
at the same token cost.

### Method lane: find build seats through employers, not titles (2026-10-01)

*Rule: search-positions-skill.md §Method lane; terms in the user's search_terms.toml `[sweep.method]`.*

Once `method_fit` existed (2026-09-29), the scoring could see method-building seats but the
search could not: the skill track caught one only if it happened to name ≥2 competencies, the
ATS sweep's tiers were all direction terms, and the org rotation keyed on `skill_match`. The first
plan was to query for method titles (research software engineer, methods developer…). Rejected:
a build seat rarely says so in its title — it is posted as *Scientist, Computational Biology* or
*Bioinformatician*, with the build in the responsibilities — and the titles that do say it, searched
across every domain, return mostly HPC support and corporate IT.

What replaced it, all in the skill track:
- **Ad text, not titles.** `ats_sweep.py` tiers `M` (a title naming the seat) and `Mb` (the role
  text says the seat builds tools/pipelines/methods *and* names scientists as the users). Both
  halves are needed for `Mb`; a build phrase alone is every IT ad on a pharma board. First run:
  career tiers byte-identical, 10 method rows; "design methods" and bare "method development"
  were dropped from the pattern after they promoted an SPR/BLI bench role and a display-library
  role — both are bench vocabulary too.
- **Employers as the target list.** An org that has posted a build seat before is the best
  predictor of the next one, and a better cold-outreach target than its "about us" page. Every
  build-seat ad the skill track opens is logged — *including the ones it then skips* on level or
  geography, which carry most of the signal — and `/inbox` logs every position it scores
  `method_fit` ≥ 75. `method_sightings.py --apply` writes `method_roles_seen` onto the org, and the
  skill track's rotation puts those orgs first.
- **Gate 3's second route.** One method competency (C1/C4/C7 for this user) plus a build signal
  collects; otherwise the ≥2 rule stands. Restricted to the method competencies so "we develop new
  assays" cannot carry a bench role through.
- **`/rescore` does orgs first**, because the rotation ranks on `method_fit` and only 3 of 157 orgs
  carried one that day.

The career track is untouched and ignores `M`/`Mb` rows. Judge the lane by its yield: if its
collections mostly score `method_fit` ≥ 75 at `/inbox` it works; mostly below 50 means the build
signal is read too loosely.

### Search telemetry snapshot (2026-08-09)

*Rule: search-positions-common.md §Telemetry*

**Current attribution — 16 runs, 94 miss-events, measured 2026-08-09.** Median lag **10 days**,
max 113, n=23.

| Cause | Share | What it says to do |
|---|---|---|
| `SOURCE_INCOMPLETE` | 35.1% | stop tuning that source — add an independent one |
| `CHANNEL_SKIPPED` | 23.4% | run budget / ordering |
| `QUERY_GAP` | 13.8% | rotate keywords — `--next-queries` |
| `AGE_EXCLUDED` | 12.8% | expected from pre-2026-07-29 runs; **any new one means a filter crept back** |
| `GEO_GAP` | 12.8% | the country loop |
| `GATED_OUT` | 2.1% | gate calibration |

The shape has **changed since the reconstructed 2026-07-29/30 baseline** (which read
`CHANNEL_SKIPPED` 46% · `AGE_EXCLUDED` 29% · `SOURCE_INCOMPLETE` 11% and is now superseded).
`SOURCE_INCOMPLETE` has overtaken `CHANNEL_SKIPPED` as the top cause. Together
`SOURCE_INCOMPLETE + QUERY_GAP + GEO_GAP` are **62%** of misses, and none of the three is fixed by
a bigger model — they are fixed by which sources the run opens and which queries it issues.

`analyze_misses.py` also excludes **redundant collections** — a lead re-collected under a different
slug — from the miss counts, and reports them separately. Three of this vault's were produced in a
single run on 2026-08-08. They are dedup failures, not misses, and counting them as late
discoveries had been inflating the miss statistics.

### Model and effort: what the log could and could not say (2026-08-09)

*Rule: search-positions-common.md §Model and effort*

**Do not treat the recommended model as settled — it is not measured yet.** `log_run.py --stats`
groups yield by `model/effort/mode` precisely so this can be answered from data, and as of
2026-08-09 the table is too sparse to answer it:

```
config                   runs  coll/run  scr/run  min/run
sonnet/low/fast             3       1.0     11.3       22
sonnet/?/fast               9       2.2     10.3       68
sonnet/ultracode/fast       1       1.0     20.0       65
opus/?/fast                 2       2.0     33.0       38
opus/high/fast              1       3.0     30.0       33
```

**No configuration is distinguishable on `coll/run`, and the table above should not be read as a
ranking.** Within `sonnet/?` alone the per-run collections were `0,0,1,1,1,3,3,3,8`. That
within-config spread is larger than every between-config gap in the table, so at n=1–3 per cell
the differences are noise.

> ⚠️ **A "never run at low effort" finding was published here on 2026-08-09 and withdrawn the same
> day.** It rested on `sonnet/low` collecting 1.0/run against 2.2. Three confounds sit on that one
> cell: the low runs were also the **narrowest** (2, 2, 4 channels reached, against 4–6 elsewhere),
> they were the **three most recent** runs and so carried the most dedup drag, and their 3 logged
> collections were the **3 redundant duplicates** of 2026-08-08 — net new leads, zero. Effort was
> the one variable that could not be isolated. Do not reinstate the claim without runs that hold
> channel breadth fixed.

What *is* separable, because the effect is large and consistent:

- **Screening volume tracks channel breadth, not model or effort.** ≤2 channels → 8.3 screened/run ·
  3–4 → 8.4 · 5–6 → **30.2**. Breadth is what determines how much gets looked at.
- **Collections stay flat at ~2.0/run across every breadth band** (2.0 · 2.0 · 1.8). Widening from
  2 channels to 6 multiplied candidates-seen 3.6× and produced **no additional leads**. That is the
  most actionable number in the log and it deserves investigation before any further widening:
  either the extra channels are duplicative, or the gates are rejecting what they surface.

What the data cannot speak to at all:

- **`sonnet/medium` has never been run** — 0 of 16. The frontmatter recommendation is inference.
- `opus/high` is n=1, `opus/?` is n=2, and 13 of 16 runs predate the `effort` field and show as `?`.

**This question is not settleable by A/B testing at this run rate — stop planning to settle it.**
Measured 2026-08-09: net-new collections average **1.75/run with an SD of 2.08** (range 0–8), a
coefficient of variation of 1.19. At 80% power and α=0.05 that needs **~23 runs per arm to detect
even a doubling**, and ~91 per arm for a 50% difference. At 2–3 runs a week that is four months of
A/B to catch a 2× effect and well over a year for anything subtler. `screened/run` is no better
(CV 1.08). An earlier version of this section proposed "two runs, then re-read `--stats`" — those
two runs would have produced numbers that look like an answer and are not one.

---

## Scoring (`engine/skills/inbox-eval.md`)

### Why two scores (2026-08-17)

*Rule: inbox-eval.md §Scoring*

**Why two scores (2026-08-17).** The single `fit_score` mixed "how much I want it" with
"how likely I am to get it", so *Senior / Lead Scientist — Computational Protein Design*
scored **83** and was still never a realistic application (see [[level_sweep]]). That was
never a scoring error: it is a genuinely on-direction role the user is underqualified for.
The two-score model says so out loud — `career_fit 92 · skill_match 55 · level_fit reach`
— instead of averaging the tension away. `fit_score` and `verdict` were deleted in the
same change; never reintroduce a blended score.

### Scoring v3: band + checks, and the org floor (2026-09-10)

*Rule: inbox-eval.md §career_fit*

**Scoring v3 (2026-09-10), on the user's explicit instruction.** Four v2 rules were reversed
together, and every doc stating them was updated in the same change: *wet lab is neutral*,
*the application never moves the number*, *MD without a design output is only adjacent*, and
*an org is scored on the average of everything it does*. What the user values is set out in `user/profile/preferences.md` §Direction;
and an organisation must never
score below its best position. The trigger: a research group scored **85** while its own
PhD call scored **92** because "the group is broader", and a scan that day found ~15 orgs
below their best role, the widest Sanofi at **55** against a **95**. Records stamped `v2`/`v2.1`
still carry the old number until `/rescore` re-judges them.

### Score the role, not the employer (2026-08-18)

*Rule: `engine/skills/inbox-eval.md` §career_fit, Step 1. This rubric caused four misscores*
*before the rule was added.*

The 75–89 band used to end with "…or a protein-design group where *this particular
seat* is the support/infrastructure role". That clause was deleted: it let the **employer's**
direction leak into a **role's** score. A Forward Deployed AI Engineer at Latent Labs scored
**78** on reasoning that said, in as many words, "Latent Labs is dead-centre direction … but
this specific seat is the infrastructure/deployment support role around the design models".
The employer's direction is already carried by its own profile (Latent Labs the company is
`career_fit` 95); scoring it again on the position double-counts it and buries genuinely
on-direction roles beneath support seats at famous companies.

### `method_fit` (2026-09-29)

*Rule: inbox-eval.md §method_fit*

**Added 2026-09-29, on the user's instruction** (rebrand; see `user/workspace/notes/rebrand_plan.md` §SPEC C).
`career_fit` measures one axis only — closeness to the user's direction. The user has
since said yes to method roles in genomics, pharma/clinical data and **non-bio fields**, all of
which score near zero on `career_fit` and were therefore invisible to `/search-*` and the
dashboard. `method_fit` makes them visible **without touching `career_fit`**, which keeps its
exact v3 meaning. The identity behind it: *the user builds the methods a research team runs on* — the
analyst who improves how the team trains, not the specialist competing head-on.

### Logistics and prestige score nothing (2026-08-17)

*Rule: inbox-eval.md §Logistics reference, §Prestige reference*

⚠️ **Logistics scores nothing.** It was a 10–15% weight in the pre-2026-08-17 rubric and was
removed entirely: geography is a decision the user makes when reading the record, not a
number the record should carry. Report location and pay plainly under
**Logistics & Salary** and let the user weigh them. Never let either move `career_fit` or
`skill_match`.

⚠️ **Prestige scores nothing.** It was a 10–15% weight before 2026-08-17 and was removed:
`prestige_tier` is already its own frontmatter field and its own dashboard column, so
folding it into a score double-counted it. Record the tier; do not let it move `career_fit`.

### Archiving is not retirement from dedup (2026-07-29)

*Rule: inbox-eval.md Step 0*

⚠️ **Archiving is folder hygiene only — it does NOT retire a file from dedup.**
The old rationale said `/search-positions` need not check `archive/`, because it only collected
posts ≤2 weeks old so nothing archived could be re-found. That reasoning was circular with the
14-day age filter, which was removed on 2026-07-29 (it made missed postings permanently
unrecoverable — see *Why age is not a filter* in [[search-positions]]). The **deep pass now
collects at any age**, so `archive/` is live dedup surface: `/search-positions` must glob it
alongside `processed/`, `user/workspace/inbox/` and `user/workspace/positions/{open,applied,closed}/`. Never restore the old
"no need to check archive" wording, and never re-add an age filter to make it true again.

### No staleness skip (2026-07-30)

*Rule: inbox-eval.md §Dedup, merge & freshness*

There is no `<3 months` staleness skip any more: that rule was removed on 2026-07-30 along with
the age filter (see *Why age is not a filter* above).

### LinkedIn URLs are stored in canonical form (2026-08-16, 2026-08-29)

*Rule: inbox-eval.md §Handlers → positions, `url:`*

Both CLAUDE.md and `engine/docs/LINK_HEALTH.md` require the canonical form, but the rule lived only
there and not in `/inbox` — which is why **26 of 37 open LinkedIn leads were still stored in
ad-library form on 2026-08-29**. It matters because `ad-library/job/detail/<id>` **returns HTTP
200 for expired postings** — on 2026-08-16 that concealed 16 dead leads out of 24. Seven
surviving pre-fix `working` stamps were corrected on 2026-08-29.

### `org_profile:` — the matches the automatic link gets wrong

*Rule: `engine/skills/inbox-eval.md` §Handlers → positions. Each case below is one the matcher*
*(`org_match.py`) got wrong in this vault; since 2026-09-10 a wrong match also inflates an org's*
*`career_fit` through the org floor.*

- **A sibling group in the same department.** "DTU Bioengineering — Digital Biotechnology Lab"
  shares every institution-level token with another lab in the same department; the posting
  names its lab but not its PI, so it was pointed at the right group's profile by slug.
- **A funder or parent whose name is in the employer's name.** Used for NNF CBMR — a University
  of Copenhagen centre funded by the Novo Nordisk *Foundation*, which is not Novo Nordisk A/S the
  company, though the org string contains it.
- **An incubator or host that is not the employer.** Used for June Bio, a startup housed at
  BioInnovation Institute: the match would have floored BII — an incubator, not an employer —
  from 40 to 90.
- **A group whose name shares no token with its posting.** `dtu-biosustain-cpe` (Computational
  Protein Engineering Group, DTU Biosustain) points at the group's profile, which is filed under
  its PI's name.

---

## CV and letters (`engine/skills/cv-generate.md`)

### Covering email: re-confirm a named contact before addressing them (2026-08-16)

*Rule: `engine/skills/cv-generate.md` Step 4c, recipient block.* When a profile's contact line was
more than a few weeks old, the named contact at the target company was re-verified on 2026-08-16
before the letter was addressed to them. A cold application to someone who has left is a wasted
send, and the check costs one search.

### Rejected openings: five spines, and fix every instance (2026-08-16)

*Rule: cv-generate.md §Edge Cases*

This is how the Novonesis opener was settled on 2026-08-16 and it worked; a reworded near-duplicate wastes a round.
The Novonesis "enzymes rather than chemistry" false opposition also sat in the Style B closing rung and had to be removed there too.

---

## Engine-wide (`CLAUDE.md`)

### Never one score (2026-08-17)

*Rule: CLAUDE.md §Profile scoring.*

- **Never average them or reintroduce a single score.** A high-`career_fit`, low-`skill_match`
record is a stretch worth seeing, not a contradiction to smooth over; a low-`career_fit`,
high-`method_fit` one is the right kind of work in the wrong field, which is also worth seeing.
The old blended `fit_score` and its `verdict` were deleted on 2026-08-17 precisely because they
hid that.

### Why `method_fit` exists, as CLAUDE.md put it (2026-09-29)

*Rule: CLAUDE.md §Profile scoring. The rubric and its own rationale: §`method_fit` above.*

- `method_fit` **0–100 — is this the work I want?** *(added 2026-09-29, rebrand — see
`user/workspace/notes/rebrand_plan.md`.)* Does the seat **build** methods, tools, pipelines, platforms or
benchmarks that others then use, or only **operate** what already exists? Judged against anchor
bands, no lookup table. **Independent of domain and of ability** — protein content belongs to
`career_fit`, a familiar stack to `skill_match`. It exists because `career_fit` measures one axis
only, so methods roles outside protein design (genomics, pharma/clinical data, non-bio) scored
near zero and were invisible to `/search-*` and the dashboard. `career_fit` 35 · `method_fit` 92
is now a lead worth seeing, not noise. Carried by every kind of record; for an org the question is
*"would I be the methods person here?"*.

### `bench_load`: reported, never scored (2026-10-26)

*Rule: `engine/skills/inbox-eval.md` §Logistics reference (Bench load); format: schema v2.*

The user asked to see how much wet-lab work a seat requires, while keeping bench work neutral in
scoring. A score would have had to choose a sign for it, and the preference ("would avoid it, will
do it if the role needs it") is a judgement made when reading the record, the same as geography.
So positions carry `bench_load: none | light | substantial | unknown`, read off the seat's own
duties, with the deciding phrase quoted under Logistics & Salary. It is kept apart from the
`validation` check: an org testing its designs is a plus in `career_fit`, and says nothing about
whether the person in the seat pipettes. Records older than v2 were migrated to `unknown`, never
guessed, because silence in an ad is not evidence of a computational seat.

### Link health: HTTP 200 is not proof a posting is live (2026-08-16)

*Rule: CLAUDE.md §Link & status hygiene. Full measurement: `engine/docs/LINK_HEALTH.md`.*

LinkedIn's `ad-library/job/detail/<id>` returns 200 for expired jobs — on 2026-08-16 that hid 16
dead leads out of 24, and 20 of 50 open leads overall turned out dead.

### Age retirement of deadline-less leads (2026-08-29)

*Rule: CLAUDE.md §Link & status hygiene; implemented by `expire_sweep.py`.*

**Exception, added 2026-08-29 on the user's explicit instruction — age retirement.** A lead with
`deadline: null` could never be retired by the rule above, and 78% of open leads had no deadline, so
they accumulated indefinitely. `expire_sweep.py` now retires deadline-less leads **older than `thresholds.stale_days`
(`user/settings.toml`, 45 when introduced) on age alone**, stamping `expired_reason: stale_no_deadline` plus a dated Notes line saying the
posting was *not* confirmed removed. This knowingly trades accuracy for a manageable active set:
some retired leads are still live. It is a decision, not a bug — do not revert it. First run moved
**39** leads (open/ 85 → 46), including `career_fit` 95 and 93. Undo the whole set with
`grep -l "expired_reason: stale_no_deadline" user/workspace/positions/closed/*.md`; skip it for one run with
`--keep-stale`. See `engine/docs/LINK_HEALTH.md`.

### The model for `/search-*` is provisional (2026-08-09)

*Rule: CLAUDE.md §Commands. The full data: §Model and effort above.*

⚠️ **Sonnet for `/search-*` is provisional.** The yield telemetry (16 runs, 2026-08-09) cannot
settle it, and not only for want of runs: per-run collections vary `0–8` *within a single config*,
so no cell is distinguishable at n=1–3. What *is* separable is that screening volume tracks
**channel breadth** (8.3/run at ≤2 channels vs 30.2 at 5–6) while collections stay flat at
~2.0/run — more looking, no more finding. Whatever setting you pick, record `model` and `effort`
honestly; 13 of 16 runs are unlabelled and answer nothing. See *Model and effort* in
`engine/skills/search-positions-common.md`.

### `/rescore`: the v3 + `method_fit` migration (2026-09-29)

*Rule: CLAUDE.md §Commands (removed 2026-10-01); the skill was `rescore.md` in engine/skills.*

⏳ `/rescore` is **temporary** — it re-judges `career_fit` on the 364 records scored before
**scoring v3** (2026-09-10: band + checks, org floor) **and writes the new `method_fit` on all
382**, a batch per run (Opus, same tier as `/inbox`); `skill_match` and `level_fit` are untouched.
The two passes were merged on 2026-09-29 because v3 was only 6% done when `method_fit` landed, and
sweeping every record twice would have been waste — so the ~22 records already stamped `v3` come
back round once for the new field. Check progress with
the `rescore_status` tool. Once it reports 100%, `/rescore` and
`rescore_status.py` can both be deleted — `career_fit.py`, `org_floor.py` and `org_match.py`
are permanent. Until then the dashboard's career column mixes two scales and warns that it is
doing so. (The same skill earlier ran the v1 → v2 two-score migration, complete 2026-08.)

**Complete 2026-10-01:** 382/382 records on v3 with `method_fit`, `--verify` clean. The rescore skill, the `rescore_status` tool and the `/rescore` command were deleted the same day; the per-record History lines are the record of what each batch decided.

### Recall on strong leads (2026-10-01)

*Rule: search-positions-common.md §Task step 2 (deep pass), step 8 (budget), §Group 1 (LinkedIn);
`linkedin_loop` / `linkedin_required` in user/settings.toml; `recruiter_queries` in
user/profile/search_terms.toml.*

The headline miss histogram (48 runs, 573 miss-events) was dominated by low-value leads: its top
causes, AGE_EXCLUDED and QUERY_GAP, were mostly skill-track data-engineering roles. Joined to the
records' `career_fit` (now built into `analyze_misses.py`), the 24 leads scoring 75+ carry 93
miss-events with a different shape: SOURCE_INCOMPLETE 30% (LinkedIn 17 of them) · CHANNEL_SKIPPED
18% · QUERY_GAP 18% · CHANNEL_NOT_RUN 12% · GEO_GAP 12% (vs 4% overall, 10 of 11 from July runs) ·
AGE_EXCLUDED 8%. PhD portals skipped or never run account for 15 of the 93.

What changed:
- **Deep pass weekly, not monthly**, with `phd_portals` mandatory on it. Deep passes yield 1.2 strong
  leads per run against 0.4 for a fast pass (sonnet/medium, 9 vs 22 runs).
- **Five required LinkedIn countries on both tracks** — UK, Denmark, Germany, Netherlands,
  Switzerland — with Germany and the Netherlands given their own tokens, because the EU token
  under-samples single countries. `log_run.py` warns when a run skips one.
- **Three pages per LinkedIn query** via the guest endpoint (`start=0/10/20`). `sortBy=DD` was tested
  and has no effect there, so the rule is to page, not to sort.
- **One recruiter query per pass**, rotated by `log_run.py --next-queries`: agencies posted two
  strong roles under titles the design queries did not return.
- **`ats_sweep.py --uncovered`** lists band-A employers with no working board (24 of them on the
  day); five are checked by hand each run and any ATS host found is registered. Ordaos Bio's
  Workable board was registered the same day.

The job-board misses that first suggested "sweep band A every run" (Adaptyv, Latent Labs) all
predate the sweep itself; since it exists it has been skipped in 3 of 48 runs. The lever there is
coverage, not frequency.

### Judging the 2026-10-01 fixes: paging and the `--since` window (2026-10-10)

*Rule: search-positions-common.md §Group 1 (LinkedIn paging); `analyze_misses.py --since`;
`log_run.py` `pages` / `short_pages`.*

The first telemetry after the fixes above was read cumulatively (52 runs) and blamed channel
skipping for four strong misses. All of those misses were made by the two 2026-10-01 fast runs,
which started at 13:06, before the fixes were committed that evening, and the deep pass the fixes
introduced caught all four on 10-05. Two changes came out of it:

- **`--since` now windows the missing runs, not the finds.** Before, it filtered leads by the date
  they were found and still charged each one to every earlier run, fixed or not; that filter is now
  `--found-since`. The same pass fixed an attribution bug: the two tracks of one search start in
  the same second, and each was charged with missing what the other found. Counting only runs that
  started strictly earlier removed 72 miss-events (1,130 → 1,058) and both strong-lead misses that
  had seemed to survive the fixes (Priora, J&J). After the fixes: 4 runs, 12 miss-events, none on a
  strong lead, and the two 10-10 runs not yet testable.
- **Three pages became auditable.** The rule allowed stopping "once a page is off-topic", and on
  10-10 both fast tracks used that as a judgement call: the career track read 41 of 90 pages, most
  queries stopping after page 1, and the skill track two of three. That is the fix aimed at
  `SOURCE_INCOMPLETE` on LinkedIn, the top strong-lead cause. Early stops now need one of two facts
  about the page just read (`exhausted`, `no_shortlist`), a time-boxed run drops a query rather
  than a page, and the log carries `pages` plus one `short_pages` entry per short combination so
  `log_run.py` can warn. The paging fix itself can only be judged once runs that follow it have
  been tested by later finds.

### A sweep miss is a triage miss until shown otherwise (2026-10-10)

*Rule: `analyze_misses.py` `UNTIERED` / `UNSCREENED`; `log_run.py` sweep archive.*

The open question from the same day's telemetry (the 10-05 sweep "did not return" three Adaptyv
postings that the 10-10 sweep did) had a plain answer: it had returned them, in every sweep since at
least 10-01, with unchanged posting dates, as tier `-`. Tier `-` rows go to the TSV but are not
printed, and the agents read only what is printed. *Software Engineer, Product* names a build seat
and its users (the lab), but its build sentence ("building the orchestration layer" of LabOS) is not
one the build-phrase pattern matches, so `Mb` did not fire; the display library role matches no
career title. The 10-10 skill track reached them through Adaptyv's earlier
method sightings, a route the interrupted 10-05 run never took.

Two attribution errors had hidden this. `SOURCE_INCOMPLETE` read "the sweep did not return it",
which an enumerating source cannot do for a live posting; and the fast pass's 21-day window was
charged to the sweep, which has no age filter (104 events, including the same three postings in the
10-01 runs). Each run's sweep output is now archived under its run_id, a sweep miss found in it
becomes `UNTIERED` (tier `-`) or `UNSCREENED` (printed, not screened), and `ats_sweep` is exempt
from `AGE_EXCLUDED`. Across the six archived runs every sweep miss is `UNTIERED`; the 224
`SOURCE_INCOMPLETE` sweep events before them cannot be re-read, but the same mechanism is the likely
explanation for many.

**`M?` tier, taken the same day.** An untiered row becomes `M?` when its employer has a logged
method sighting (`method_roles_seen` ≥ 1 on the profile), its board has at most 100 postings, and its
title matches the weak method titles as whole words and names no corporate function (security,
support, sales, IT …). It is the method lane's employer route moved into the sweep, so it no longer
depends on the org rotation that budget-cut runs skip. Title only, deliberately: a build-phrase
requirement was tested and would have dropped the Product ad it exists for. Measured on a live sweep:
10 rows before the whole-word and corporate filters (Adaptyv "Bioengineer / Molecular Biologist",
Isomorphic Labs support and security engineers), 5 after, all Adaptyv, among them all three postings
the 10-05 run missed.

### Best Match removed (2026-10-02)

The dashboard's Best Match tab and tile (live positions and PhDs with `skill_match >= 65`, sorted by
skill) were removed at the user's request. Every row in it was also under Positions or PhD, whose
sortable Skill column gives the same ranking in one click, and since `method_fit` there are three
scores — a tab ranked by one of them leans toward the single-number view this engine avoids.
It was built 2026-08-17 to make strong-candidate leads visible whatever their direction; the
`min_score_shown` rule (a lead stays visible when *any* score clears the bar) now covers that.

### Timeline and To-do: one store, a local server (2026-10-02)

*Rule: `engine/skills/dashboard.md` §Timeline and To-do.*

The user asked for a timeline (long plan and progression, past included) and an important × urgent
to-do matrix (focus, future and open only), editable and **in sync**. Both read one file,
`user/workspace/plan/plan.json`, so sync is structural rather than a copy kept up to date.
Browser `localStorage` was rejected: the items would live in one browser profile, out of reach of
the tools and of Claude, and lost with the site data. The dashboard is a `file://` page, which
cannot write files, so editing goes through `serve.py`, a stdlib server bound to 127.0.0.1; the
plain file stays a read-only view. Record-derived items (applications sent, live deadlines) take
their dates from the frontmatter on every run and can only be restyled or hidden, so the plan can
never contradict a record.
