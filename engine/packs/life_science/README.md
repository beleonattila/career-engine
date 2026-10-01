# Domain pack — life science

A domain pack holds what the search engine needs to know about **one field** and nothing about
any one person: where that field's jobs are posted, which employer boards need hand-found ATS
details, which aggregators serve dead postings, and which term variants mean the same thing.
The user picks a pack with `search.pack` in `user/settings.toml`; everything personal (direction,
geography, thresholds) stays in `user/`.

| File | Read by | Holds |
|---|---|---|
| `boards.md` | `engine/skills/search-positions-common.md` Step 2 | science/academic boards, regional national sources, ATS notes, PhD portals, stale-prone sources |
| `synonyms.md` | the keyword pass and Gate 1 of every search track | term variants normalised before matching |
| `ats_seeds.toml` | `engine/tools/ats_discover.py` | Workday / Oracle / Workable boards found by hand, confirmed and known-wrong slugs, the domain check for short-slug hits |

This pack covers computational and structural biology, protein science, pharma and biotech, with
regional sources for Denmark and the Nordics plus the main Swiss, German, Dutch and Belgian
university portals. A pack for another field copies this folder's shape and replaces the content.
