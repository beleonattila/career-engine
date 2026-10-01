# Life-science pack — boards and sources

Read by the position collectors after the engine's own groups (`engine/skills/search-positions-common.md`
Step 2: Group 0 employer ATS sweep, Group 1 general boards and LinkedIn). Work through the sections
below in order. **Regional sections apply only to countries in the user's allowlist**
(`user/settings.toml` `[[geography.block]]`); skip a region the allowlist does not name.

## Science and academic job boards

| Source                 | URL                           | Notes                                          |
| ---------------------- | ----------------------------- | ---------------------------------------------- |
| Nature Careers         | nature.com/naturecareers      | Best for pharma/biotech/academic science       |
| Science Careers (AAAS) | sciencecareers.sciencemag.org | Strong bioinformatics coverage                 |
| EURAXESS               | euraxess.ec.europa.eu         | EU-funded; excellent for postdocs and research |
| ERC funded projects dashboard | [dashboard.tech.ec.europa.eu ↗](https://dashboard.tech.ec.europa.eu/qs_digit_dashboard_mt/public/sense/app/c140622a-87e0-412e-8b29-9b5ddd857e13/sheet/61a0bd1d-cd6d-4ac8-8b55-80d8661e44c0/state/analysis) | Funded PIs = labs actively hiring PhDs — see note below |

**ERC funded projects dashboard** (Horizon Europe / European Research Council). Not a job board —
a Qlik dashboard of *funded grants* (labs with money to hire). Best mined as **research-group /
PhD-contact leads**, not open postings. Workflow: filter by Call Year + Country + Domain (Life
Sciences / Physical sciences), export the "List of funded projects" table to `.xlsx`, keyword-filter
the abstracts to the career track's Tier-1/2 terms (`engine/skills/search-positions-career.md`), and save qualifying rows as `_group-profile_`
`.txt` in the inbox (the funded PI is the lead). Caveat: the filter/selection state does **not**
travel through the shared URL (it opens with "No selections applied"), so the user must apply the
filters and export the table from their own browser session; a fresh fetch gives the full unfiltered
dataset.

---

## Regional sources — Denmark & the Nordics

These had **no coverage at all** before 2026-07-29.
Search in **Danish as well as English** — many DK postings never appear in English or on LinkedIn.

| Source | URL | Notes |
|---|---|---|
| Jobindex | jobindex.dk | Largest DK board. **JS-rendered — `WebFetch` returns chrome only.** Use `WebSearch` with `site:jobindex.dk`, or query the org directly. |
| Jobbank | jobbank.dk | Strong on research/biotech |
| Ofir | ofir.dk | |
| WorkinDenmark | workindenmark.dk | State portal, English, aimed at internationals |
| The Hub | thehub.io/jobs/location/denmark | Nordic startups — where small DK biotechs post |
| Life Science Talent Hub | talent-hub.life-science-talent-solutions.dk | DK life-science specialist; surfaced the Gubra de novo peptide design role |
| Jobbnorge / Finn | jobbnorge.no · finn.no | NO academic + general |
| Arbetsförmedlingen | arbetsformedlingen.se | SE national |

**Danish/Nordic query terms:** `proteindesign` · `proteinteknologi` · `bioinformatiker` ·
`beregningsbiologi` · `forsker` · `videnskabelig medarbejder` · `ph.d.-stipendium` ·
`postdoc protein` · (SE/NO) `proteindesign` · `forskare` · `stipendiat`

Also hit the **university portals directly** — academic posts frequently never reach LinkedIn.
**Skip `efzu.dtu.dk`: DTU is enumerated completely by `ats_sweep.py` (Group 0 in the skill), so re-checking it
by hand is wasted budget.** The rest still need a manual pass:
`employment.ku.dk` · `au.dk/om/stillinger` · SDU · AAU · DTU Biosustain · NNF centres
(CPR, CBMR, BRIGHT) · Chalmers · KTH · Lund · Uppsala · Stockholm · SciLifeLab · Karolinska · NTNU ·
UiO · Aalto. For CH/DE/NL/BE add: ETH · EPFL · UZH · Basel/Biozentrum · MPG · Helmholtz · DKFZ ·
TU Delft · Wageningen · Utrecht · Leiden · `academictransfer.nl` · `jobs.vib.be` · KU Leuven · UGent.

---

## ATS notes — employers this pack's seeds cover

The seeds themselves are in `ats_seeds.toml` next to this file; `ats_discover.py` reads them.

**DTU is now swept on every run** (82 live requisitions on 2026-08-02, authoritative `PostedDate`).
`danish_boards` was logged as skipped in 6 of 6 runs
before 2026-07-29; DTU coverage is now free and complete rather than a budget casualty. Note that
`org` reads as `dtu` for every faculty — the sweep folds sub-org slugs (`dtu-bioengineering`,
`dtu-biosustain-cpe`, …) into that one board for the `tracked` check. DTU roles carry
`fit 0` because there is no company profile; judge them on the title, not the fit column.

Confirmed working slugs: `generatebiomedicines`, `isomorphiclabs`, `xairatherapeutics`,
`valencelabs`, `profluent` (Greenhouse) · `chaidiscovery`, `latentlabs` (Ashby) ·
`gsk`/`GSKCareers`, `amgen`/`Careers` (Workday) ·
`efzu.fa.em2.oraclecloud.com`/`CX_2001` = **DTU** (Oracle ORC).

---

## PhD portals

PhD-specific portals a general job search structurally misses: `findaphd.com` · `PhDPortal.com` ·
`jobrxiv.org` · `academicpositions.com` · `euraxess` MSCA Doctoral Network calls · `scholarshipdb.net`
· EMBL EIPP/EIPOD · ISTA & Vienna BioCenter PhD calls · SNSF · Novo Nordisk / Carlsberg / Lundbeck
Foundation calls. Niche compbio boards worth a periodic look: `careers.iscb.org` · `compbiojobs.com` ·
`eurosciencejobs.com` · `jobs.biospace.com`.

---

## Known stale-prone sources — do not trust a date from these

Verified 2026-07-29. Use only to *discover* a lead, then confirm against the employer's own site
or ATS before collecting.

| Source | Problem |
|---|---|
| builtin.com | Served a Novonesis role **removed in July 2025** as if current |
| rosettacommons.org/jobs | Looks perfect for this field; newest posting was **Oct 2025**. Not worth a regular check. |
| vacancyedu.com | Academic-vacancy scraper. On 2026-08-02 served **three** DTU protein-design postdocs as current — *Generative AI for GPCR minibinders*, *Epistatic-Aware ML for Protein Engineering*, *BRIGHT Enzyme Engineering for Greenhouse Removal* — when DTU's own API confirmed all three were already gone. These are exactly the bullseye titles, which is what makes it dangerous. |
| scholaridea.com | Same three phantom DTU postdocs, same day. Mirrors vacancyedu-class content. |
| Generic `site:linkedin.com/jobs/view` web search | Ranks by authority → surfaces multi-year-old expired postings |
| ziprecruiter / glassdoor / recruit.net aggregations | Re-post without dates; frequently long dead |

> The two academic scrapers above are now cheap to disprove: `python engine/tools/ats_sweep.py` enumerates DTU
> in full every run, so a DTU posting absent from the sweep is **gone**, not merely unlisted.

---

## Company discovery

Read by the company collectors (`engine/skills/search-companies-career.md` and
`search-companies-skill.md`). Work through these systematically, session by session — do not
restart from the top of the list each run.

**Career track** — employers working on the direction:

| Source | URL | What to pull |
|---|---|---|
| YC Biotech Companies | ycombinator.com/companies/industry/biotech | YC-backed startups |
| IntuitionLabs Top Startups | intuitionlabs.ai/articles/top-biotech-startups-2026 | 2026 emerging list |
| BioPharma Guy Denmark | biopharmguy.com/links/country-denmark-all-location.php | Denmark full list |
| BioPharma Guy EU | biopharmguy.com | Filter by country for any in-scope nation |
| LinkedIn company search | linkedin.com/search/results/companies/ | Filter by the career track's direction terms (`user/profile/search_terms.md`) |

**Skill track** — the career track's sources plus the ones where a stack is visible:

| Source | URL | What to pull |
|---|---|---|
| BioPharma Guy Denmark | biopharmguy.com/links/country-denmark-all-location.php | Denmark full list — work it systematically |
| BioPharma Guy EU | biopharmguy.com | Filter by country for any in-scope nation |
| YC Biotech Companies | ycombinator.com/companies/industry/biotech | YC-backed startups |
| LinkedIn company search | linkedin.com/search/results/companies/ | Query by **stack terms** from the user's competency table (`user/profile/search_terms.md`) |
| Employer ATS boards | `ats_sweep.py` output (`user/workspace/logs/ats_sweep_latest.tsv`) | A company whose live ads name the competency triggers evidences the stack directly, at zero LLM cost |
| CRO / sequencing / imaging vendors | — | A category the career track never touches: service companies with large bioinformatics and imaging teams |

---

## Group discovery

Read by the group collectors (`engine/skills/search-groups-career.md` and `search-groups-skill.md`).

**Journals to prioritise** (career track — topic queries, filtered by journal impact):

Prioritise: Nature · Science · Cell · Nature Methods · Nature Struct. Mol. Biol. · Nature Chem.
Bio. · Nature Comm. · PNAS · eLife · PLOS Comp. Bio. · J. Mol. Biol. · Bioinformatics · Protein
Science · Structure · bioRxiv

**Newly formed groups** — grant-award pages and institutional job pages that name newly funded PIs:

- Check new grant award pages: ERC, DFF, NNF, Lundbeck, Villum, DNRF, VR (Sweden).
  - **ERC funded projects dashboard** — [dashboard.tech.ec.europa.eu ↗](https://dashboard.tech.ec.europa.eu/qs_digit_dashboard_mt/public/sense/app/c140622a-87e0-412e-8b29-9b5ddd857e13/sheet/61a0bd1d-cd6d-4ac8-8b55-80d8661e44c0/state/analysis).
    Filter by Call Year + Country + Domain, export the "List of funded projects" table to `.xlsx`,
    keyword-filter the abstracts to the career track's direction terms (`user/profile/search_terms.md`), and save qualifying rows as
    `_group-profile_` `.txt` (the funded PI is the group lead — a newly funded lab hiring PhDs).
    Note: filter state does **not** travel through the shared URL, so export from your own session.
  - **VR (Swedish Research Council) grant-award news** — [vr.se/english/just-now/news ↗](https://www.vr.se/english/just-now/news/news-archive/2025-12-09-13-researchers-in-sweden-to-receive-an-erc-consolidator-grant-2025.html).
    National-funder announcements name newly-funded PIs; mine for labs working on the direction.
- Check DTU/KU/AU/SDU/Lund job pages.

**National infrastructure** (skill track — high pipeline / software / imaging density): DTU
Computerome, ELIXIR nodes, DeiC, SciLifeLab, de.NBI.
