# Preferences

## Direction

(What science or work you want to do, and why. The career_fit score measures distance from this.)

## Motivation

## PhD or industry

## Target Roles

- **Primary:** …
- **Bridge:** …

## Job ad Keywords

(Words that signal a good ad; the search terms in search_terms.md come from here.)

## Geography

(Mirror of the blocks in settings.toml, in words.)

## Scoring

*The content half of the `career_fit` rubric: what the bands and checks mean for you. The
mechanism (band → checks → lookup) is in `engine/skills/inbox-eval.md` §career_fit; read both.
Check names and units are in `settings.toml` [career_fit.checks].*

### Bands

The question: **is this the work I want?**

| Band | Range | Anchor |
|---|---|---|
| **A** | 90–100 | Dead centre: exactly the direction above. |
| **B** | 75–89 | Core, one part partial. |
| **C** | 50–74 | Adjacent: related methods or field, not the core. |
| **D** | 30–49 | Weak: the field is near, the work is not. |
| **E** | 0–29 | Off-direction. Judged holistically; the checks do not apply. |

### Checks

| Check | Units | Read on | Yes when |
|---|---|---|---|
| **Application** | 1 | the project | (what makes the work's purpose one you care about) |
| **Validation** | 1 | the team | (e.g. results are tested / used for real) |
| **Package** | ½ (`package-half`) or 1 (`package`) | the team | (e.g. several parts of your workflow done in house: 2 → ½, 3+ → 1) |

### Worked examples: org scores (inbox-eval)

(Add a few scored examples here once /inbox has run, to keep later scores consistent.)

## Logistics & salary (reported by /inbox, never scored)

- Salary floor, contract type, start date, languages:
