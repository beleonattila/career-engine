---
name: search-positions-skill
cssclasses: [skill]
recommended_model: Sonnet medium — provisional, never low (see search-positions-common §Model and effort)
description: >
  SKILL (employability) track position collector. Searches for open positions the user could
  realistically get and do, judged purely on evidenced competencies — direction is irrelevant
  here. Run as a sub-agent by /search-positions, in parallel with search-positions-career.
  Writes raw .txt to user/workspace/inbox/_staging/skill/ only. Does NOT score — that is /inbox's job.
---

# search-positions-skill

**Track: skill (employability).** The question is *could the user realistically get this job and
do it?* — evidenced competence, and nothing else. Whether the work is on-direction is the other
track's problem, and `career_fit` records it at scoring time anyway.

**Never add a direction filter here** ([[search-common]] §The two-track model).

## Read these first, in order

1. **[[search-common]]** — geography allowlist, staging protocol, `TRACK:` stamp, the competency
   gate. Identical for both tracks.
2. **[[search-positions-common]]** — everything else: run modes, dedup, Gates 0/2/4, sources,
   output format, telemetry, model guidance.
3. **This file** — supplies the three **[MODE]** steps that common file leaves open.

Write every collection to **`user/workspace/inbox/_staging/skill/`**. Never to `user/workspace/inbox/`.

---

## [MODE] Step 5 — keyword pass

There are no direction tiers here. Normalise variants (the domain pack's `synonyms.md`), then
note every term matching the competency triggers in the user's table — a cheap pre-filter; Gate 3
is the real test, and they read the same vocabulary.

Skip an ad at this step only when **nothing at all** in the competency table appears anywhere
in it. Anything else goes through to the gates.

## [MODE] Gate 0 — no extra reject

Use the shared rejects only (dead deadline · removed posting · portal page · outside the
geography allowlist).

**Do not apply the career track's direction reject here.** The career track rejects such work as
off-direction; this track has no direction floor, and a role that reject catches can be a
real skills match. If it clears Gate 3 on competencies, collect it.

## [MODE] Gate 1 — competency presence

List every competency-trigger term that literally appears in the ad, grouped by competency.
**Pass iff any term from the table appears in the role text at all.** Gate 3 does the counting;
Gate 1 only weeds out ads with no overlap whatsoever.

Record as: `Gate 1 (terms found): {C1: terms | C2: terms | ...}` or `none`

## [MODE] Gate 3 — competency count

*Does this role need what the user can prove they have?* Mechanical: for each competency in the
user's table — `user/profile/search_terms.md` §Skill track → *Competency table — positions* — mark
**PRESENT** iff the **role text** (responsibilities, requirements, "you will…") names at least
one trigger term or an unambiguous synonym, **and** the competency is central —
[[search-common]] §Skill track: the competency gate. Gate 2 has already discarded company
boilerplate, so only role text counts.

**COLLECT iff ≥2 distinct counting competencies are PRESENT** (Tier-3 rows never count).

Record as: `Gate 3 (competencies): {C1, C6, C7} — 3 present`

**…or through the method lane** (below): **1 counting competency from the user's method
competencies + a BUILD SIGNAL → COLLECT.** Record as
`Gate 3 (method lane): {C4} + "you will develop and maintain the analysis platform our scientists use"`.

## [MODE] Method lane

> `/inbox` scores `method_fit` ([[inbox-eval]] §`method_fit`) and the user wants build seats in
> any domain. They rarely say so in a title, so **never query job boards for method titles**. Find
> them through the ad text of employers already swept, and the employers that have posted such
> seats before (`engine/docs/decisions.md` §Method lane).

**Where the candidates come from.**
- **ATS sweep `M` / `Mb` / `M?` rows** — open every one that is not `tracked`. `M` = the title names
  a method-building seat; `Mb` = the role text says the seat builds tools for scientists; `M?` = a
  software/engineering title at a small employer with a logged method sighting, where neither of the
  others fired. `M?` is the employer route inside the sweep: it says *look*, not *build seat* — the
  BUILD SIGNAL below is still read from the ad.
- **Any ad you read for another reason** that turns out to carry a build signal.
- **The org rotation** (§Which orgs to sweep) — which puts proven method hirers first.

**The BUILD SIGNAL** — a yes/no read, like the career track's output row, not a score. YES iff the
role text says the seat's own deliverable is a method, tool, pipeline, platform, framework or
benchmark **that other people then use**, and it sits where Gate 3's *central* rule says a
competency must sit: the title or the primary responsibilities. Copy the sentence verbatim — it
is the audit trail. NO when the build is a "nice to have", when the users are customers rather
than scientists (corporate IT, product software), or when the deliverable is results from
running something that already exists.

**The method competencies** are the user's: `user/profile/search_terms.md` §Skill track →
*Method lane*. Exactly one of them, PRESENT under the *central* rule, plus the build signal,
collects. Without the build signal the normal ≥2 rule applies unchanged.

**Log every sighting — collected or not.** Every ad you open with a YES build signal goes into
the sightings log, including the ones Gate 4, the geography allowlist or dedup then stops:
```bash
python engine/tools/method_sightings.py add --org <orgslug> --title "<title>" --url <url> \
    --signal "<the build sentence, verbatim>" --outcome <collected|skipped-level|skipped-geo|skipped-gate|expired|duplicate> --source skill
```
A skipped one is not wasted: it says this employer hires method people, which is what ranks it in
the next run's rotation and what makes it a cold-outreach target. This log is the one file
outside your staging folder you write; the org profiles themselves are only changed by
`method_sightings.py --apply`, which `/inbox` runs.

> ⚠️ **The lane does not touch direction.** A method seat in clinical data or a non-bio field is
> collected if it clears the lane, and `/inbox` will score it `career_fit` low and `method_fit`
> high — that pair is the reason the lane exists. Equally, never use the lane to rescue an ad
> that fails Gate 2 or Gate 4.

> **This is the mirror of the career track's output test, and the rows that flip are the point**
> (`search_terms.md` §Skill track names them for this profile). Two searches exist so that
> neither question has to be compromised to accommodate the other.

## [MODE] Which orgs to sweep

```bash
python engine/tools/method_sightings.py --rotation 30
```

It lists `user/workspace/organizations/companies/` and `user/workspace/organizations/research_groups/`
orgs at **`skill_match` or `method_fit` 60+**, plus any org with a logged method sighting —
the employers whose stack overlaps the competencies or that would make the user their methods
person, whatever they work on. Order: **orgs with method sightings first**, then orgs with no
tracked lead, then oldest `last_evaluated`. Work down it for the run's org budget. The career
track sweeps the same folders at `career_fit` 60+; an org clearing both gets swept twice and the
parent drops the duplicate.

---

## What this track does NOT change

Everything below stays exactly as the career track runs it — never re-derive or relax any of it:

- **Gate 2 (placement)** — terms must be in the role text, not the "about us".
- **Gate 4 (level)** — the same seniority rules and thresholds (`search_terms.md` §Level gate).
  Strong competencies do not make an over-level role attainable.
- **Calls for the qualification the user is working towards → PASS** (PhD calls, for this
  profile) — collected by this track too ([[search-common]] §Rules both tracks share).
- **Roles requiring a qualification the user lacks, and faculty calls → group profile**, not a
  position (postdocs, for this profile).

---

## Report

At the end, report to the orchestrator:

```
track: skill
mode:  fast | deep
collected: N   -> user/workspace/inbox/_staging/skill/
screened:  N
skipped:   N   (gate0 X · gate1 X · gate2 X · gate3 X · gate4 X · dedup X · geo X)
competency spread: {how many collections hit each counting competency}
method lane: {M/Mb rows opened} opened · {build signal YES} sightings logged · {collected via the lane} collected
channels:  {which sources were actually queried}
```

Record the lane in the run JSON as `"method_lane": {"opened": N, "sightings": N, "collected": N}`
([[LOG_SCHEMA]]). That is how the lane is judged: collections mostly scoring `method_fit` ≥ 75 at
`/inbox` → it works; mostly below 50 → the build signal is read too loosely.

The competency spread says which of the user's skills the market actually asks for.

---

## Related

[[search-common]] · [[search-positions-common]] · [[search-positions-career]] (the other track —
same ads, different question) · [[competencies]] (the evidence base this gate reads) ·
[[background]] · [[preferences]] · [[inbox-eval]]
