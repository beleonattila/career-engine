---
name: cv-generate
cssclasses: [skill]
recommended_model: Sonnet (medium; high for the cover letter)
description: >
  Generate a targeted CV and cover letter for a specific job position OR for an
  unsolicited application to a company or research group. Trigger immediately on /cv,
  "make CV", "write cover letter", "apply to [org/role]", "generate application for",
  or when the user points to a position, company, or research-group profile file.
  Reads the profile from the vault, modifies the master LaTeX CV, writes a cover letter,
  compiles both to PDF, and saves to the applications folder.
---

# cv-generate

The **produce** stage. Generates a targeted CV and cover letter from a vault profile,
applies language-pattern mirroring, modifies the master CV LaTeX, writes a matching
cover letter, and compiles both to PDF.

**Recommended model:** Sonnet, medium effort — high for the cover letter (it's the real
writing). The profile (built by `/inbox`) supplies the keywords, angle, and fit; this
skill applies the writing rules and the LaTeX template. Not a Haiku task.

## Input modes

`/cv` accepts two profile shapes. Detect which from the `type`/frontmatter of the file
passed in.

| Input | Source | Application kind |
|---|---|---|
| **Position profile** (`user/workspace/positions/open/*.md`, has `role_title` + `skill_match` + Key Requirements) | solicited | apply to a specific advertised role |
| **Company / group profile** (`user/workspace/organizations/companies/*.md` or `user/workspace/organizations/research_groups/*.md`, no `role_title`) | **unsolicited** | speculative application / cold outreach to an org or lab |

The workflow below is written for the position (solicited) path. The
**Unsolicited path** section near the end says what changes when the input is a
company or research-group profile.

---

## Prerequisites

Verify these exist. Stop and report if any are missing.

- `user/profile/background.md` + `user/profile/preferences.md` — master profile
- `user/profile/competencies.md` — ranked, evidence-backed competency profile; source of all skill claims
- `user/profile/soft_skills.md` — soft skills library with role-type selection notes
- `user/profile/cv_template/publications.md` — verified publication list with per-context selection guide
- `user/profile/cv_template/master_cv.tex` — visual and structural LaTeX template (preamble, commands, layout)
- `user/profile/writing/cover_letter_style_B.md` — spec for the experimental Style B letter (Step 4b)
- `user/profile/writing/cover_letter_style_A.md` — spec and voice directives for the Style A letter (Step 4)
- `user/profile/writing/writing_style.md` — the user's writing rules (Writing Style Guide)
- `user/profile/cv_template/NOTES.md` — this CV's variants, optional entries and removable lines (Step 2)
- `user/profile/cv_template/cover_letter.tex` — cover-letter LaTeX template with the sender header
- Position profile `.md` — passed as argument, e.g. `user/workspace/positions/open/[OrgSlug]_[RoleSlug]_[DateSlug].md`

---

## Workflow

### Step 0 — Pre-flight: verify the application link is live

Before doing any work, confirm the posting is still applyable — this is the cheapest place
to catch a dead link (far better than after the CV is made, on deadline day).

1. Check the profile's `url`. Verify it opens and shows the posting:
   - **Workday host** (`*.myworkdayjobs.com`): query the ATS JSON
     (`POST /wday/cxs/{tenant}/{site}/jobs` with the role title as `searchText`) — if the
     req isn't returned, it's been removed.
   - Otherwise: open it in a **real browser** (agent-browser headless). An automated-fetch
     refusal (404/ECONNREFUSED) is *unverified, not dead* — don't trust WebFetch alone.
2. Outcomes:
   - **Live** → set `url_status: working`, `url_checked: today`, proceed.
   - **Moved** (found at a new URL) → update `url`, proceed.
   - **Confirmed removed** → **stop. Do not generate.** Tell the user the posting is gone,
     set `url_status: dead`; apply the status-discipline rule (expired only if deadline is
     strictly past or posting removed) and close it. Saves a wasted CV.
3. Skip Step 0 only for the **unsolicited** path (company/group profile — no single posting).

### Step 1 — Parse the position profile

Read the target `.md` file. Extract:

- YAML frontmatter: `role_title`, `organization`, `org_type`, `location`, `career_fit`,
  `skill_match`, `level_fit`, `deadline`, `salary`
- **Fit Assessment** section: matched strengths, gaps, recommended angle

> **`skill_match` is the number that shapes the letter; `career_fit` is not.** `career_fit`
> says how much the user wants the work — useful for deciding *whether* to apply, irrelevant to
> *how* to write. `skill_match` and the gaps behind it tell you how much framing the letter
> has to do. A low `skill_match` means lead harder on the transferable evidence and the
> matched strengths; it never means inventing coverage (see *Factual grounding*, CLAUDE.md).
- **Key Requirements** section: full list
- **Language Patterns** section: both lists (identity & culture, technical keywords)
- **Notes** section: any manual additions

Also load:
- `user/profile/background.md` — personal facts, education details
- `user/profile/competencies.md` — verify every skill claim against tier levels and key
  tools before writing any competency bullet; this is the authoritative source
- `user/profile/soft_skills.md` — select 3–5 bullets for the CV using the
  **Usage notes** at the bottom of that file. Role-type mapping:
  - Industry / pharma / biotech → leadership, parallel delivery, cross-functional
  - Academic / PhD → self-direction, adaptability, communication, resilience
  - NGS / bioinformatics → parallel workload + technical decision-making
  - Protein / structural → self-direction + adaptability
  Hold selected bullets in context for Step 2h.
- `user/profile/cv_template/publications.md` — use the **Selection Guide** table to decide which
  publications to include for this target type.
  Copy author strings and DOIs exactly from this file. Never invent or paraphrase citations.
- If it is a position then read the source text file for the verbatim text of the job ad. (look for the "source_file" section in the .md file of the position)

---

### Step 2 — Plan the CV modifications

Decide the following before touching any file. State the plan in a brief summary
printed to the user before generating (e.g. "Subtitle: X · Profile: new · Competencies:
structural first · Experience variant: general · [optional entry]: included").

#### 2a — Subtitle
Write a new subtitle matching the role title and domain. Format:
`[Role Title] | [Domain 1] \& [Domain 2]`
Mirror the exact terminology from the job ad where possible.

#### 2b — Profile paragraph
Always write a **new** paragraph. Do not reuse existing variants verbatim.
Apply writing rules (see **Writing Style Guide** below).
Length: 4–6 sentences. Targets: weave in 1–2 identity/culture words naturally,
mirror 2–3 technical keywords from the position's language patterns.

#### 2c — Competencies section
Rules:
- Reorder `\cvskill` blocks so the most relevant group comes first
- Rename category labels to mirror job ad terminology if closer
- Within each block, move the most relevant items to the top
- Remove items clearly irrelevant to this role (NOTES.md names examples for this CV)
- **Never add items that are not already in the master CV** — only reorder, rename, trim

Which `\cvskill` block leads for which role type: the relevance guide in
`user/profile/cv_template/NOTES.md` §Competency blocks.

#### 2d — CV-specific entries and variants
`user/profile/cv_template/NOTES.md` §Rules lists what this CV varies per target: experience-bullet
variants, optional entries (included for some target types, omitted for others) and entries left
out by default. Decide each one by the target type as NOTES.md says, and name each decision in the
Step 2 summary and the Step 6 report.

#### 2g — Section ordering
- Industry / pharma / biotech: Experience → Education (current order)
- Academic / PhD: Education → Experience (swap the two `\section` blocks)

#### 2i — Page target
Target length: **exactly 2 pages, both pages filling to roughly ~85–90%** (no page ending
with a large gap above the footer).

- After planning content, mentally estimate page fill. If the draft would be **under 2 pages**,
  add content in the priority order in `user/profile/cv_template/NOTES.md` §Filling a short page
  until it reaches 2 pages.
- If the draft would be **over 2 pages**, trim in reverse priority order.
- If 3 pages feels genuinely justified (very strong publication record, extensive
  experience, academic CV with full course list), **ask the user for permission before
  generating** — do not produce a 3-page CV without explicit approval.

**Filling without padding — content is king, spacing is the dial.** When the genuine content
lands at ~1.5–1.8 pages (common for an early-career CV), the failure mode is compressing
everything to the top of each page and leaving a big bottom gap (especially on page 1). Fix it
in this order:
1. **Add genuine, traceable content first** (the priority list in NOTES.md) — never invent.
2. **Then use generous, even spacing** so the real content breathes out to fill both pages.
   Spacing is a legitimate dial: raise inter-section (`\titlespacing`), inter-entry
   (`\vspace`), inter-block (`\cvskill` trailing gap), and list `itemsep` rather than leaving
   whitespace pooled at one page bottom. Note which elements live on which page — e.g. all
   `\cvskill` competency blocks usually sit together, so their spacing tunes that page
   specifically without disturbing the other.
3. **Order sections so the page break falls inside flowable content.** A breakable list
   (Publications `enumerate`, or a run of `\cvskill` blocks) straddles a page boundary cleanly;
   two atomic blocks butted against the boundary leave a gap. For academic/PhD CVs, placing
   **Publications right after Experience** both foregrounds the papers and gives the
   page-1→page-2 break a breakable section to flow through.

**Verify actual fill after compiling — don't trust the estimate.** Page count from the
compile log (`[1][2]`) only tells you it's 2 pages, not whether they're well-filled. Confirm
by rendering the pages and checking where content ends, e.g.:
```bash
pdftoppm -png -r 90 CV_[Name]_[OrgSlug].pdf _pg   # then view _pg-1.png / _pg-2.png
```
If a page's content ends well short (more than ~15% empty above the footer) while the CV is
under two pages, it is over-compressed: apply the spacing/reorder steps above and recompile.
Iterate until both pages read as deliberately filled. (`pdftoppm`/`pdfinfo` are from poppler;
if unavailable, open the PDF to eyeball it.)

#### 2h — Soft skills / research approach block
Using bullets selected in Step 1 from `user/profile/soft_skills.md`:
- Always include a **Collaboration & delivery** `\cvskill` block drawn from the
  Cross-functional collaboration and Communication sections of the library
- For academic / PhD roles: also add a **Research approach** `\cvskill` block drawn
  from Self-direction, Adaptability, and Technical decision-making sections
- For industry roles: draw from Project leadership and Parallel workload sections
  instead; label the block **Leadership & delivery**
- Write bullets subjectless and concise — trim library bullets to fit one line where
  possible without losing the evidential detail
- Never use bullets marked `*(Interview context: ...)*` — those are for interview prep only

#### 2j — Removable lines
Some lines are optional by design: `user/profile/cv_template/NOTES.md` marks them and says when to
keep or drop each (for example a language still being learned, decided by the employer's country).

Rules:
- Never drop such a line to make room on the page. Length is handled in Step 2i; this is a
  *signalling* decision only. If the CV is over-long, trim elsewhere.
- Dropping one line makes the CV shorter — re-check page fill (Step 2i) after deciding.
- State the decision and the reason in the Step 6 report so it is reviewable.

---

### Step 3 — Generate the targeted CV `.tex`

Read `user/profile/cv_template/master_cv.tex`. This is a visual and structural template —
use its preamble, commands, spacing, and layout verbatim. Content (competencies,
profile, publications) is filled from the source `.md` files, not copied from the template.

Apply the modifications planned in Step 2 by editing the LaTeX source directly.

**Section orphan rule:** Prevent a `\section{}` header from stranding alone at the bottom
of a page (header on one page, its content on the next) by preceding each section after
the first (Profile) with a `\needspace` guard. **Size the guard to the section's first
atomic unit — do not use a flat 5cm on everything.** A flat `\needspace{5cm}` on every
section backfires whenever the CV is under two pages: it bumps whole sections to the next
page and leaves large mid-document gaps (a header that "needs 5cm" but only has 3cm jumps,
stranding the space above it). Use:

- **Sections whose first entry is a multi-line block** (an Experience job, an Education
  entry): `\needspace{2.5cm}`–`3cm` — enough to keep the header with the start of the first
  entry.
- **Short final sections** (Languages: header + a few one-line items): size to the
  section's own height (`~2cm`) so the whole section stays together without reserving space
  it doesn't need. A 5cm guard here is the classic cause of a near-empty final page.
- **Competency lists built from atomic `\cvskill` minipages**: a smaller guard (`~2cm`)
  lets the section start wherever there's room and its blocks flow across the page break,
  filling the page — each `\cvskill` block is internally unbreakable and breaks only
  *between* blocks, so flow is clean.

Never let a guard be large enough to force a whole section onto a fresh page while half a
page sits empty above it. The goal is orphan prevention, not fixed gaps.

Output path: `user/workspace/applications/[OrgSlug]_[YYYY-MM]/CV_[Name]_[OrgSlug].tex`

> **Filename convention (all generated artefacts).** Every file a recruiter or PI ever sees
> must carry **both the candidate name and the organisation**, because it lands in someone
> else's inbox next to fifty other attachments called `CV.pdf`:
>
> - `CV_[Name]_[OrgSlug].tex` / `.pdf`
> - `CoverLetter_[Name]_[OrgSlug].tex` / `.pdf` / `.txt`
> - `Email_[Name]_[OrgSlug].txt`
>
> `[Name]` is the user's full name from the **Name:** line of `user/profile/snapshot.md`, spaces as
> underscores (e.g. `Jane_Doe`).
>
> `[OrgSlug]` is the same slug used for the folder. Keep it readable in a filename: prefer
> `DoeLab-ETH` over `doe-lab-eth---laboratory-of-protein-and-cell-engineering`. Never
> emit a bare `CV_[OrgSlug].pdf`.

Preservation rules — these lines must never be changed:
- All `\usepackage`, `\definecolor`, `\setmainfont`, layout, and spacing commands
- Name header line
- All `\fancyfoot` lines (contact info)
- Publication entries: reproduce exactly (author strings, DOIs, wording) whichever papers
  the user/profile/cv_template/publications.md Selection Guide includes for this target; never
  invent, paraphrase, reorder, or add a citation
- Languages section — **one exception:** a line `user/profile/cv_template/NOTES.md` marks as
  removable may be dropped per Step 2j. No language is ever added or upgraded.
- All dates, institution names, thesis titles

---

### Step 4 — Generate the cover letter (Style A)

> **Two letters are generated on every run.** Style A is specified in
> `user/profile/writing/cover_letter_style_A.md`; Style B in `user/profile/writing/cover_letter_style_B.md`,
> generated in **Step 4b**. Both are produced, compiled, and reported so the user can compare them
> on real targets. Neither is the default yet; the trial ends when the user decides. Do not skip one,
> and do not merge them into a single hybrid letter — the whole point is that they differ.
>
> **The voice directives in `cover_letter_style_A.md` govern both styles.** So does the Writing Style
> Guide. Only structure and emphasis differ.

Write a new cover letter as a LaTeX file. Use the **Cover Letter Template** below.
Apply writing rules (see **Writing Style Guide**).

**Read `user/profile/writing/cover_letter_style_A.md` and follow it.** It holds the user's voice
directives (authoritative: they override any conflicting rule in this skill), the paragraph
structure, and the phrase banks for the opening. Do not improvise a structure from memory.

Output paths: `user/workspace/applications/[OrgSlug]_[YYYY-MM]/CoverLetter_[Name]_[OrgSlug]_A.tex`
**and** `user/workspace/applications/[OrgSlug]_[YYYY-MM]/CoverLetter_[Name]_[OrgSlug]_A.txt`
(mandatory plain-text companion — see HARD RULE #2 in the Writing Style Guide; each paragraph
one unbroken line, LaTeX stripped, for pasting into web application forms).

> **`_A` / `_B` are working suffixes for the comparison trial only.** Once the user picks the
> letter to send, rename that one to the clean `CoverLetter_[Name]_[OrgSlug].tex/.pdf/.txt`
> and delete or archive the other. **Never send a file with `_A` or `_B` in the name** — it tells
> the reader the letter was one of two drafts. The filename convention in Step 3 still governs
> everything that leaves the folder.


---

### Step 4b — Generate the cover letter (Style B)

Read `user/profile/writing/cover_letter_style_B.md` and follow it. It is the authoritative spec
for this letter; do not improvise a structure from the Style A rules above.

Style B is the forward-facing, organisation-centred variant: the CV is the history, so the
letter is the plan. Its paragraphs are defined in the file.

Constraints that carry over unchanged from Step 4:
- **All the voice directives in `cover_letter_style_A.md`**, in full (the logic checks included).
- The **Writing Style Guide**, including one paragraph = one unbroken source line and the
  mandatory `.txt` companion.
- **Factual grounding.** B's forward tense ("I can", "I would") makes unevidenced claims
  easier to write. Every capability claim still needs backing in `user/profile/competencies.md`,
  `user/profile/cv_template/publications.md`, `user/profile/soft_skills.md`, or `user/profile/background.md`.
- One page maximum. Five paragraphs is more structure, not more words.

Use the same **Cover Letter LaTeX Template** below. If B3 uses labelled bullets, add
`\usepackage{enumitem}` and the compact `itemize` block given at the end of the Style B file.

Output paths:
`user/workspace/applications/[OrgSlug]_[YYYY-MM]/CoverLetter_[Name]_[OrgSlug]_B.tex`
**and** `..._B.txt` (same plain-text companion rule as Style A).

**Same target, same facts, different letter.** Both styles draw on the same position profile,
the same matched strengths, and the same evidence. B is not a second attempt at A and must not
reuse A's sentences: if a paragraph could be dropped into either letter unchanged, it is not
doing Style B's job.

---

### Step 4c — Generate the covering email (always, never optional)

Most applications go out as an **email with PDFs attached**, so the email body is a real
deliverable, not an afterthought. Generate it on every run, solicited or unsolicited.

Output: `user/workspace/applications/[OrgSlug]_[YYYY-MM]/Email_[Name]_[OrgSlug].txt`

**The email is a wrapper, not a second cover letter.** The cover letter is attached as a PDF
and says the full thing. If the email repeats its arguments, the reader reads the same case
twice and the attachment becomes redundant. Compress, do not restate.

**One email only, not one per style.** The email is a wrapper and is largely style-neutral, so
doubling it would only add noise to the comparison. Write it from whichever letter's strongest
beat compresses best, and say in the Step 6 report which one it was drawn from. Re-check it
against the chosen letter before sending.

**Hard constraints**
- **120–150 words in the body**, greeting and sign-off excluded. If it is longer, cut.
- **Three short paragraphs maximum.** One idea per paragraph.
- Plain text only. **Each paragraph is one unbroken line**, paragraphs separated by a blank
  line (same rule as the `.txt` letter, and for the same reason).
- **All of the user's cover-letter voice directives apply in full**
  (`user/profile/writing/cover_letter_style_A.md` §Voice directives).

**Structure**

```
To:      [Full name]  <[email address, or "[EMAIL NOT FOUND — do not guess]"]>
         [Organisation, department / team]
         [Street, postcode city, country]
Subject: [concrete — role or programme + name. Never "Application" or "CV attached"]

Dear [Prof. Surname / Hiring Team],

[P1 — one sentence: what this is, and what is attached.]

[P2 — two or three sentences: the single strongest reason the user fits. Take the one best beat
from cover-letter P2 and compress it. Name the tools. Do not attempt the full case.]

[P3 — one sentence: the concrete next step. Availability for a conversation, plus anything
the target explicitly asked for (referee contacts, portal reference number, start date).]

Best regards,
[the user's full name]
[the user's phone]
[the user's email]
```

The sign-off's name, phone and email are exactly those in the sender header of
`user/profile/cv_template/cover_letter.tex`.

**Addressee.** Use the named PI or contact from the profile's **Key People** / **Notes** where
one exists (research groups almost always have one). Fall back to `Dear Hiring Team,` only when
the profile names nobody. Never `To Whom It May Concern`.

**Recipient block (`To:`) is mandatory.** The file must carry who it goes to and where, so the
email can be addressed without reopening the profile. Rules:
- **Never invent an email address.** Guessing a corporate pattern (`first.last@org.com`) can
  send a real application to the wrong person or nowhere. If the vault does not record one,
  write `[EMAIL NOT FOUND — do not guess]` and add a short note at the end of the file naming
  the fallback channel (LinkedIn message, public contact form, a general recruitment address).
- **Verify the postal address before writing it**, the same standard as a job-ad `url`. It is a
  factual claim in a document that leaves the building. Confirm it, or write only the city.
- **Confirm the named contact still works there** when the profile's contact line is more than
  a few weeks old; a cold application to someone who has left is a wasted send.
- Any bracketed placeholder or trailing note is scaffolding: say plainly in the Step 6 report
  that it must be deleted before sending.

**Subject line.** It is the only part guaranteed to be read. Name the specific role or
programme and include the user's name, e.g.
`PhD application, computational track (EDBB November intake) — [Full name]`.
Do not use a bare `Application` or `CV and cover letter`.

**Attachment line.** State plainly what is attached, in P1, using the real filenames so the
reader can match them: "I have attached my CV and cover letter."

---

### Step 5 — Compile

```bash
cd "user/workspace/applications/[OrgSlug]_[YYYY-MM]"
latexmk -xelatex -interaction=nonstopmode CV_[Name]_[OrgSlug].tex
latexmk -xelatex -interaction=nonstopmode CoverLetter_[Name]_[OrgSlug]_A.tex
latexmk -xelatex -interaction=nonstopmode CoverLetter_[Name]_[OrgSlug]_B.tex
```

Three PDFs, not two, for as long as the style trial runs. If either letter fails to compile,
fix it — do not report a run as complete with only one letter.

> **latexmk caches aggressively.** After editing a `.tex` to fix page fill, an identical output
> byte count across two runs means it did not actually rebuild. Force it with `latexmk -C`
> before recompiling, otherwise you will iterate on layout changes that never took effect.

Verify page count in compilation output (e.g. `[1][2]` = 2 pages). If the CV compiled
to 1 page, return to Step 2i and add content before proceeding.

Use `latexmk` — it handles multi-pass compilation automatically, which is required
for page-number references (`\pageref{LastPage}`) to resolve correctly. Running
xelatex only once produces `??` in the page footer.

If latexmk is not available, fall back to running xelatex **twice** per file:
```bash
xelatex -interaction=nonstopmode CV_[Name]_[OrgSlug].tex
xelatex -interaction=nonstopmode CV_[Name]_[OrgSlug].tex
```

If xelatex is not found: report the error and tell the user the `.tex` files are
ready to compile locally. The `.tex` files are the deliverable.

If Calibri font is not found: substitute `Open Sans` or `TeX Gyre Heros` in the
`\setmainfont` line and recompile.

Clean up auxiliary files after successful compilation:
```bash
latexmk -c
```

---

### Step 5b — Stamp the application lifecycle

After a successful compile, write the tracking fields onto the **source profile**
(the position/company/group `.md` passed in) so the dashboard reflects it:

```yaml
app_status: cv_generated        # only if currently not_started/absent — never downgrade
cv_dir: user/workspace/applications/[OrgSlug]_[YYYY-MM]/
cv_date: [today]
```

Do not overwrite a more advanced status (if `app_status` is already `sent`/`interviewing`/
`closed`, leave it and just refresh `cv_dir`/`cv_date`). Then regenerate the dashboard
(`python engine/tools/dashboard.py`) so the new CV appears. Status beyond
`cv_generated` (sent, feedback, outcome) is set later via `/track`.

### Step 6 — Report output

Print a summary:

```
── CV Generated ─────────────────────────────────────────────
Role:     [role_title]
Org:      [organization]
Scores:   career [career_fit]/100 · skill [skill_match]/100 · level [level_fit]

Modifications:
  Subtitle   → [new subtitle]
  Profile    → new paragraph (structural/pharma focus)
  Skills     → [first block] first · [items trimmed or reordered]
  Experience → [variant used] · [optional entries included/omitted]
  Order      → [industry/academic]
  Removable  → [line] [kept/dropped] ([one-line reason])

Output:
  CV          → user/workspace/applications/[OrgSlug]_[YYYY-MM]/CV_[Name]_[OrgSlug].pdf
  Letter A    → user/workspace/applications/[OrgSlug]_[YYYY-MM]/CoverLetter_[Name]_[OrgSlug]_A.pdf (+ .txt)
                current style · fit and trajectory
  Letter B    → user/workspace/applications/[OrgSlug]_[YYYY-MM]/CoverLetter_[Name]_[OrgSlug]_B.pdf (+ .txt)
                experimental style · forward-facing, organisation-centred
  Email body  → user/workspace/applications/[OrgSlug]_[YYYY-MM]/Email_[Name]_[OrgSlug].txt
                drawn from Letter [A/B] · attach CV + chosen letter · to [name or "Hiring Team"]
─────────────────────────────────────────────────────────────
Style trial: two letters generated. Pick one, rename it to the clean
CoverLetter_[Name]_[OrgSlug].* before sending, and tell me what worked
and what did not so the styles can be tuned.

Review before sending. Run /cv [path] again with feedback to revise.
```

**Style-trial line.** After the block, add one short line naming the sharpest difference
between the two letters on *this* target (e.g. "B leads on the screening-pipeline
contribution; A leads on the thesis toolchain"). It gives the user something concrete to react
to instead of reading both cold.

**Send-ready summary.** After the block, state in one line how the application is sent: which
address it goes to, which files attach, and anything the target asked for that is not in the
folder (referee contacts, a portal submission that must follow the email).

---

## Writing Style Guide

Apply these rules to every piece of text generated — profile paragraph, cover letter,
any modified bullet points.

### Rules

**HARD RULE — one paragraph = one line in the source, AND always emit a plain-text cover letter.**
Two separate things, both required:

1. **Source formatting.** Every generated paragraph of prose must be a **single unbroken line**
   in the `.tex` source: the **CV Profile paragraph**, every **cover-letter body paragraph**, and
   any other flowing prose. Do **not** hard-wrap a paragraph across multiple source lines.
   Separate paragraphs with a single blank line only. This applies even though the master CV
   template ships its Profile paragraph hard-wrapped — flatten it to one line when you generate.
   (Line breaks *inside* bracketed LaTeX structures — bullet `\item`s, `\cvskill` blocks,
   addresses — are fine; this rule is about flowing prose paragraphs only.)

2. **Plain-text companion (this is what actually fixes copy-paste).** Source formatting alone
   does **not** make text copy cleanly out of the *compiled PDF*: LaTeX reflows each paragraph
   into several visual lines, and PDF viewers copy a newline at every visual line break, so a
   PDF copy always comes out fragmented regardless of source. Therefore, whenever a cover letter
   is generated, also write its `.txt` next to the `.tex` (`..._A.txt` and `..._B.txt` while the
   style trial runs) — the
   full letter as plain text with **each paragraph on one unbroken line**, paragraphs separated
   by a blank line (strip all LaTeX: `\&`→`&`, drop `\textit{}`/`\textbf{}`/`\href{}` wrappers,
   no `---`). This `.txt` is what the user pastes into web application forms that want the letter
   inline; the PDF is for attaching. Do not skip it.

3. **Covering email.** Separately from the `.txt` letter, every run also produces
   `Email_[Name]_[OrgSlug].txt` (Step 4c) — the short body for the email that carries the
   PDFs. The `.txt` letter and the email are **not** the same artefact and must not have the
   same content: the letter is the full case, the email is a 120–150 word wrapper.

**The voice and tone rules are the user's: `user/profile/writing/writing_style.md`.** CV and
cover-letter registers, banned punctuation and phrasing, the upsell mandate and its hard limit,
tone. Read it before writing and apply it to every piece of generated text.

**Language pattern integration**
- Identity/culture words: weave 1–2 into profile paragraph + cover letter P1 or P4.
  Must feel earned — the word has to fit the actual sentence naturally.
- Technical keywords: use in competencies labels, bullet points, and cover letter P2.
  Mirror the ad's exact phrasing where it's technically accurate.


---

## Cover Letter LaTeX Template

Use `user/profile/cv_template/cover_letter.tex` verbatim: it carries the sender header (name, city,
email, phone), the fonts and the colours. Copy it into the application folder, fill in the
bracketed fields, and write the body paragraphs to the letter's style file.

---

## Unsolicited path (company / research-group profile)

When the input is a `user/workspace/organizations/companies/*.md` or `user/workspace/organizations/research_groups/*.md` file,
there is no advertised role — it is a speculative application or cold outreach. Build it
from what the profile *does* contain. Everything else (writing rules, LaTeX template,
compile, report) is unchanged.

**Step 1 — parse differently.** There is no `role_title`, `level_fit`, `deadline`, or
**Key Requirements** — but an org profile *does* carry both scores. `skill_match` here means
"how much of what this org works on could the user do", scored from its stated stack rather than
from requirements, so it sizes the letter's framing exactly as it does for a position.
Instead extract:
- frontmatter: `name`, `type`, `location`, `prestige_tier`, `career_fit`, `skill_match`, `url`
- **Summary** and **Why Relevant** — these define the angle
- **Language Patterns** — same role as before (identity words + technical keywords)
- **Key People** — use the PI / named contact as the cover-letter addressee
- treat the org's stated direction (Summary + technical keywords) as the *implicit*
  requirements to mirror

**Step 2 — planning differences.**
- **Subtitle:** there is no ad title to mirror, so use the user's own target framing for
  this org — pull from `user/profile/preferences.md` target roles and the profile's technical keywords
  (same format as Step 2a: `[Target role] | [Domain 1] \& [Domain 2]`).
- **Angle:** derive it from the single strongest item in **Why Relevant** (the tool /
  domain / methodology overlap the profile names). That overlap is the spine of P2.
- **Section ordering & optional entries:**
  - `type: research_group` (or university) → **academic ordering** (Education → Experience);
    optional entries as `user/profile/cv_template/NOTES.md` says for academic targets.
  - `type` company (`pharma_company` / `biotech` / `tech`) → **industry ordering**
    (Experience → Education); optional entries as NOTES.md says for industry targets.
- **Competencies:** order the `\cvskill` blocks to lead with the org's technical focus as
  shown in its **Language Patterns → technical keywords**.

**Step 4 — cover-letter differences.** It is an open/speculative letter, so:
- **P1:** run the same four-move opening (`cover_letter_style_A.md` §Structure), with two substitutions: move 1 draws the
  mission from the profile's **Summary**, and move 2 names the lab's **research direction or
  a concrete programme** instead of an advertised project. Signal that it is speculative:
  "I am reaching out because..." rather than "I am applying for [role]".
- **P2:** same technical-match technique, anchored on the **Why Relevant** overlap.
- Name a **concrete team / project / programme** from the profile where the fit lands,
  and (if no posting) say you'd welcome hearing about openings that match.
- **Research groups:** address the PI by name (from Key People); keep it short and
  conversational, like a cold email in letter form; for a PhD-oriented lab, frame around
  research-fellow / PhD fit and propose a short conversation.

Output paths and compile steps are identical (`user/workspace/applications/[OrgSlug]_[YYYY-MM]/`).
In the Step 6 report, label it `Unsolicited` and name the source profile. Print both scores
in the Scores line; only `level —` is blank, since an org profile advertises no seniority.

---

## Edge Cases

| Situation | Action |
|---|---|
| `skill_match` < 50 (position) | Generate, but warn: "⚠ Skill match [N]/100 — the gaps are real; review the letter's claims before sending". Never close the gap with language the evidence base can't support. |
| `career_fit` < 50 (position) | Generate, but warn: "⚠ Career fit [N]/100 — off-direction. Worth asking whether this is one to send at all." |
| `level_fit: reach` (position) | Generate, but note it: "⚠ Level: reach — the ad asks for [PhD / N years / seniority]". Not a blocker; a strong `career_fit` reach is a legitimate application. |
| Unsolicited input with low `career_fit` (<50) | Generate but warn: "⚠ Low company/group career fit — review before sending" |
| Unsolicited input with low `skill_match` (<50) | Generate but warn: "⚠ Skill match [N]/100 — this org's stack is largely outside the evidence base; lead on what genuinely overlaps" |
| No profile exists yet | Tell user to run `/search` then `/inbox` first, or provide a path to an existing profile |
| Deadline has passed (position) | Flag in report: "⚠ Deadline was [date]" — generate anyway |
| Input is a company/group profile | Use the **Unsolicited path** section above |
| `type: research_group` or university | Academic section ordering; optional entries as NOTES.md says for academic targets |
| User provides free-text feedback after reviewing | Re-read the `.tex` files, apply the specific changes requested, recompile |
| **User rejects the opening paragraph** | Do **not** reword the same idea. Offer **five alternatives on five distinct spines** (different reasons for writing, not different phrasings of one reason), let the user pick, then rebuild the paragraph around that choice. A reworded near-duplicate wastes a round (`engine/docs/decisions.md` §Rejected openings). |
| **A rejected sentence appears elsewhere in the pair** | Fix every instance, not the one the user quoted. (`engine/docs/decisions.md` §Rejected openings.) |

---

## Related

[[background]] · [[preferences]] · [[competencies]] · [[soft_skills]] · [[inbox-eval]] (produces the position profiles this skill consumes) · [[writing_style]] · [[cover_letter_style_A]] · [[NOTES]] (the CV's own rules)
