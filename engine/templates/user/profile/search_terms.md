# Search terms

The search skills (`engine/skills/search-*.md`) hold the gate *mechanics*; this file holds what
they gate *on* for you. Each section names the step that reads it. The tools read the matching
regexes and the LinkedIn query pool from search_terms.toml next to this file: change a term here,
change it there.

---

## Career track — is this the work the user wants?

### Keyword tiers (positions — Step 5 and Gate 1)

- **Tier 1 — strong** (any one is a bullseye): …
- **Tier 2 — supporting / adjacent** (two needed): …
- **Tier 3 — generic/context** (never qualifies a lead on its own): …

### Gate 0 reject (positions)

In addition to the shared rejects: (work that is off-direction by definition → SKIP).

### Gate 3 output (positions)

(What the seat must deliver for the career track to keep it.)

### Direction terms (companies and groups — the collect test)

- **Core:** …
- **Adjacent:** …

### Paper queries (groups, by topic)

```
(one literature query per line, for finding research groups)
```

## Skill track — could the user get and do this?

### What this track surfaces for this profile

(Roles built on your strongest competencies, whatever the field. No direction filter here.)

### Competency table — positions (Gate 1 and Gate 3; the role text)

| Competency (competencies.md) | Terms that show it in an ad |
|---|---|
| … | … |

### Method lane (positions — Gate 3's second route)

Seats that build tools, pipelines or methods others use. Patterns: search_terms.toml [sweep.method].

### Competency table — companies (the collect test; the company's own pages)

| Competency | Terms |
|---|---|

### Competency table — groups (the collect test; the lab's own pages)

| Competency | Terms |
|---|---|

### Paper queries (groups, by method)

```
(one query per line)
```

## Level gate (Gate 4)

- Skip titles above your level (search_terms.toml [level] overlevel), except in PhD calls.
- Skip ads that state more years of experience than you have: (your number) +.

## LinkedIn queries

The query pool is search_terms.toml [linkedin] query_pool; it should span the term groups above.
