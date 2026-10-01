#!/usr/bin/env python3
"""
org_match.py — which company / research-group profile a position record belongs to.

Shared by two consumers that must agree on the answer:
  * dashboard.py  — the date a CV was last sent to each employer;
  * org_floor.py  — the career_fit floor (an org never scores below its best position).

Moved out of dashboard.py on 2026-09-10 when org_floor.py became its second user. dashboard.py
cannot be imported (it writes the HTML as an import side effect), and a forked copy would drift:
every guard below exists because a real mismatch was caught.

Employer identity itself belongs to dedup_check.py — its alias table and structural org-token
rule are reused here, never re-implemented.

Record shapes the functions expect:
    profile  {"slug": file stem, "name": frontmatter name}
    position {"path": file path, "org": frontmatter organization, "org_profile": override or ""}
"""
import os
import re

try:
    from dedup_check import same_employer, org_tokens, ALIASES
except Exception:                                    # keep callers working regardless
    same_employer = lambda a, b: "same" if a == b else "no"
    org_tokens = lambda s: {x for x in re.split(r"[^a-z0-9]+", s.lower()) if x}
    ALIASES = {}


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def file_slug(path):
    """OrgSlug prefix of a position filename: `genmab_senior-scientist_2026-07.md` -> `genmab`."""
    return os.path.basename(path).split("_", 1)[0]


def token_df(profiles):
    """How many org profiles each identity token appears in.

    A token carried by many profiles names an *institution* (dtu, ku, embl), not an employer,
    so it cannot on its own justify attributing a position to one group rather than its
    siblings. Measured, not a hand-written stopword list, so it stays correct as the vault grows.
    Pass every company and group profile, scored or not.
    """
    df = {}
    for prof in profiles:
        for t in org_tokens(prof["slug"]) | org_tokens(slugify(prof["name"])):
            df[t] = df.get(t, 0) + 1
    return df


def employer_hit(profile, pos, df):
    """True when this position belongs to this company/group. `df` is token_df() of all profiles.

    Accepts dedup_check's 'same' verdict outright. A 'maybe' (one token set a subset of the
    other) is accepted only when the overlap is >= 2 tokens AND at least one of them is
    discriminating (appears in <= 2 org profiles).

    Both guards are load-bearing, and each caught a real error on 2026-08-16:
      * without the >=2 rule, `cambridge` matches `astrazeneca-cambridge` — a different employer;
      * without the discriminating-token rule, DTU Bioengineering's *Digital Biotechnology Lab*
        role matched **another lab**, a sibling group in the same department, on {dtu, bioengineering}.
    Together they still admit a PI-named slug (`<pi>-dtu` -> `dtu-<pi>-digital-biotech`), where the surname is rare.
    """
    p_slug = profile["slug"]

    # Explicit wins. `org_profile:` in a position's frontmatter names the owning profile
    # slug outright and shuts off all inference — the escape hatch for cases no rule can
    # resolve, e.g. a DTU Bioengineering posting that names its lab but not its PI and so
    # is indistinguishable from a sibling group in the same department.
    if pos["org_profile"]:
        return pos["org_profile"].strip() == p_slug

    p_name = slugify(profile["name"])
    cands = [file_slug(pos["path"]), slugify(pos["org"])]
    for c in filter(None, cands):
        for target in filter(None, (p_slug, p_name)):
            if same_employer(c, target) == "same":
                return True

    # Fallback for a group whose slug and its posting's slug simply differ. Direction
    # matters here: every identity token of the PROFILE must appear in the position, and
    # at least one of them must be discriminating. Overlap alone is not enough — that is
    # what put a Digital Biotechnology Lab role under Büll Lab, since both share
    # {dtu, bioengineering} while `buell` appears nowhere in the position.
    # If the alias table already declares this slug's canonical employer, that ruling wins —
    # the 'same' layer above resolved it. Running the fallback anyway would additionally
    # credit the parent (`servier-symphogen` -> `symphogen` AND `servier`), which double-counts
    # one application across two profiles.
    if any(c in ALIASES for c in cands):
        return False
    pos_tokens = set()
    for c in filter(None, cands):
        pos_tokens |= org_tokens(c)
    prof_tokens = org_tokens(p_slug)
    if prof_tokens and prof_tokens <= pos_tokens \
       and any(df.get(t, 0) <= 2 for t in prof_tokens):
        return True
    return False
