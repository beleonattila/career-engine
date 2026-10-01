#!/usr/bin/env python3
"""
dedup_check.py — guard against re-collecting a lead the vault already has.

Step 6 of /search-positions is a dedup check done by eye, and it fails: on 2026-07-29 a run
collected `cradle-bio_scientific-advisor-antibodies` while
`positions/open/cradle-bio_scientific-advisor-antibodies_2026-06.md` already existed — an exact
org+role slug match. This makes that check mechanical.

Dedup is by IDENTITY, never by date, so every location is searched including
inbox/processed/archive/ (which the deep pass would otherwise happily re-collect).

Usage:
    python engine/tools/dedup_check.py                      # audit user/workspace/inbox/*.txt, exit 1 if dupes
    python engine/tools/dedup_check.py --query cradle-bio "Scientific Advisor, Antibodies"
    python engine/tools/dedup_check.py --query-url https://job-boards.greenhouse.io/x/jobs/123
    python engine/tools/dedup_check.py --delete             # audit, then remove confirmed duplicates
"""

import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

from paths import REPO, WORKSPACE as ROOT  # noqa: E402 — records are relative to user/workspace/

# Org aliases: only for renames and acquisitions, which no amount of string normalisation can
# derive. Slug *variants* of the same name are handled structurally by same_employer() below.
# The table is vault data, so it lives with the vault: user/workspace/organizations/aliases.toml
# (variant = "canonical"). A vault without the file simply has no aliases yet.
ALIASES_FILE = ROOT / "organizations" / "aliases.toml"


def _load_aliases():
    if not ALIASES_FILE.exists():
        return {}
    with open(ALIASES_FILE, "rb") as f:
        return dict(tomllib.load(f).get("aliases", {}))


ALIASES = _load_aliases()

# Words that describe what KIND of organisation it is, not WHICH one. Stripping them is what
# makes `cradle` == `cradle-bio` and `cranfield` == `cranfield-university` without anyone
# having to notice the collision first and hand-write an alias.
ORG_NOISE = {
    "university", "universitet", "universite", "universiteit", "univ", "college", "school",
    "institute", "institut", "institutet", "inst", "lab", "labs", "laboratory", "laboratories",
    "bio", "biotech", "biotechnology", "bioscience", "biosciences", "biologics", "biology",
    "therapeutics", "therapeutic", "tx", "pharma", "pharmaceutical", "pharmaceuticals",
    "sciences", "science", "technologies", "technology", "tech", "group", "groups",
    "center", "centre", "centro", "research", "medical", "medicine", "health", "healthcare",
    "hospital", "foundation", "academy", "department", "dept", "faculty", "division",
    "ag", "aps", "gmbh", "inc", "ltd", "llc", "plc", "corp", "nv", "bv", "srl", "spa",
    "holdings", "company", "the", "of", "and", "for",
}


def org_tokens(slug):
    """Identity-bearing tokens of an org slug, organisation-type words removed."""
    t = [x for x in re.split(r"[^a-z0-9]+", slug.lower()) if x]
    keep = [x for x in t if x not in ORG_NOISE]
    return set(keep or t)          # never reduce an org to nothing ("bio-tech" stays itself)


def same_employer(a, b):
    """('same'|'maybe'|'no') for two org slugs.

    'same'  — identical identity tokens, or one de-hyphenated form contains the other.
    'maybe' — one token set is a proper subset of the other. Ambiguous on its own:
              `cambridge` is a subset of `astrazeneca-cambridge` but is a different employer,
              while `cbmr` is a subset of `ku-cbmr` and is the same one. Resolved by the role
              slug in match(), never here.

    Written structurally on purpose. The hand-maintained alias table missed four collisions in
    ten days (2026-07-29..08-08): cbmr/ku-cbmr, cradle/cradle-bio, cranfield/cranfield-university
    and kuleuven-dewilde/ku-leuven — three with byte-identical role slugs. Each cost an ad fetch,
    an inbox write and an Opus scoring pass, and each was then logged as a late discovery, which
    corrupted the miss-attribution telemetry on top.
    """
    ca, cb = ALIASES.get(a.lower().strip(), a.lower().strip()), \
        ALIASES.get(b.lower().strip(), b.lower().strip())
    if ca == cb:
        return "same"
    ta, tb = org_tokens(ca), org_tokens(cb)
    if not ta or not tb:
        return "no"
    if ta == tb:
        return "same"
    # Split-vs-joined spelling of the same name: `kuleuven-dewilde` vs `ku-leuven` squash to
    # "kuleuvendewilde" and "kuleuven". Anchored at the START only -- a free substring test
    # makes `cambridge` a match for `astrazeneca-cambridge`, which is a different employer.
    fa, fb = re.sub(r"[^a-z0-9]", "", ca), re.sub(r"[^a-z0-9]", "", cb)
    if len(fa) > 3 and len(fb) > 3 and (fa.startswith(fb) or fb.startswith(fa)):
        return "same"
    if ta < tb or tb < ta:
        return "maybe"
    return "no"


# Landing pages, not postings. A lead whose SOURCE is the employer's careers index shares that
# URL with every other lead from the same employer, so matching on it would merge unrelated
# roles. Real examples in the vault: `generatebiomedicines.com/open-positions` and
# `employment.ku.dk/faculty` each front two different jobs.
INDEX_PATH = {"careers", "career", "jobs", "job", "vacancies", "vacancy", "positions",
              "open-positions", "openings", "faculty", "opportunities", "join-us",
              "work-with-us", "search", "listings", "en", "index"}
UUIDISH = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}|\d{4,}")


def canon_url(u):
    """Comparable form of a job-ad URL, or "" if the URL does not identify one posting.

    Scheme and query are dropped and the host is lowercased. A URL is only usable for dedup if
    it looks posting-specific: at least two path segments, and either an id-like run of digits,
    a UUID fragment, or a long trailing slug.
    """
    if not u:
        return ""
    try:
        s = urlsplit(u.strip())
    except ValueError:
        return ""
    host = (s.netloc or "").lower().removeprefix("www.")
    if not host:
        return ""
    segs = [x for x in (s.path or "").strip("/").split("/") if x]
    if len(segs) < 2 or segs[-1].lower() in INDEX_PATH:
        return ""
    if not (UUIDISH.search("/".join(segs)) or len(segs[-1]) >= 12):
        return ""
    return f"{host}/{'/'.join(segs)}"


SOURCE_RE = re.compile(r"^\s*(?:SOURCE|url)\s*:\s*(\S+)", re.I | re.M)


def file_url(p):
    """The job-ad URL a vault file points at: `SOURCE:` in a .txt, `url:` in .md frontmatter."""
    try:
        head = p.read_text(encoding="utf-8", errors="replace")[:2000]
    except OSError:
        return ""
    m = SOURCE_RE.search(head)
    return canon_url(m.group(1).strip("<>\"'")) if m else ""

def role_key(role):
    """Comparable form of a role title or role slug."""
    return re.sub(r"[^a-z0-9]+", "-", str(role or "").lower()).strip("-")


def lead_key(find, seen):
    """Identity of a collected lead, robust to the org slug being spelled differently.

    `find` is a telemetry `collected`/`screened` entry (org, role, optionally url); `seen` is an
    iterable of previously issued keys, each an (org, role_key, canon_url) triple. Returns the
    existing key when this lead has been seen before, otherwise a fresh one.

    Lives here rather than in a caller so that the thing which PREVENTS duplicates
    (`dedup_check`), the thing which MEASURES recall (`analyze_misses`) and the thing which
    REPORTS yield (`log_run`) all mean the same thing by "the same lead". When they disagree, the
    recall report counts the dedup guard's failures as misses and the yield table counts them as
    finds — which is exactly what happened on 2026-08-08.
    """
    org, rk = str(find.get("org") or ""), role_key(find.get("role"))
    url = canon_url(find.get("url"))
    if url:
        for prev in seen:
            if prev[2] and prev[2] == url:
                return prev
    for prev in seen:
        if prev[1] == rk and same_employer(org, prev[0]) in ("same", "maybe"):
            return prev
    return (org, rk, url)


STOP = {"the", "a", "of", "and", "for", "in", "to", "senior", "lead", "principal", "staff",
        "junior", "associate", "scientist", "engineer", "researcher", "specialist", "i", "ii",
        "found", "phd", "postdoc"}

SEARCH_GLOBS = [
    # The UNPROCESSED inbox counts too. Omitting it was a live bug (caught 2026-07-30): with 12
    # files awaiting /inbox, `--query latent-labs "Machine Learning Scientist"` returned
    # "new-role" while that exact role sat in inbox/ uncollected-but-present. Two runs before an
    # /inbox pass would each collect it. Self-matches are excluded in match().
    "inbox/*.txt",
    "inbox/processed/*.txt",
    "inbox/processed/archive/*.txt",
    "positions/open/*.md",
    "positions/applied/*.md",
    "positions/closed/*.md",
]


def canon(org):
    o = org.lower().strip()
    return ALIASES.get(o, o)


def toks(text):
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if t and t not in STOP and len(t) > 2}


def build_index():
    """[(org_slug, role_tokens, source_path, role_slug, file_name, url)] over the whole vault."""
    idx = []
    for g in SEARCH_GLOBS:
        for p in ROOT.glob(g):
            parts = p.stem.split("_")
            org = canon(parts[0])
            role = parts[1] if len(parts) > 1 else ""
            idx.append((org, toks(role), p.relative_to(REPO).as_posix(), role, p.name,
                        file_url(p)))
    return idx


def match(idx, org, role_text, exclude_name=None, url=None):
    """Return (verdict, evidence). verdict in {tracked, possible, new-role, NEW-ORG}.

    Checked in order of confidence:

    1. URL. Two records pointing at the same job ad are the same lead whatever they are named.
       The skill has called the URL "the strongest match signal" all along; it was simply never
       consulted here.
    2. Same employer (structurally, see same_employer) + identical role slug -> hard duplicate.
    3. Ambiguous employer ('maybe') + identical role slug -> hard duplicate too. A byte-identical
       role slug is not something two different employers produce by accident, and this is the
       case that leaked: `cbmr` vs `ku-cbmr` with the same
       `postdoc-computational-peptide-design-metabolic-gpcrs`.
    4. Anything weaker -> 'possible', which never blocks.

    Two confidence levels, because token overlap alone cannot tell a repeated ROLE from repeated
    ORG BOILERPLATE. Real case, 2026-07-29: `ellison-institute-oxford` had two distinct roles
    ("Bio-ML Scientist" and "Jamali Lab Postdoc") that both carry "generative-biology" in the slug
    -- the name of the institute they sit in, not the job. A flat 2-token rule called that a
    duplicate and would have blocked a genuine new lead.
    """
    cu = canon_url(url)
    if cu:
        for _, _, src, _, name, prev_url in idx:
            if name != exclude_name and prev_url and prev_url == cu:
                return "tracked", f"{src} (same job-ad URL)"

    t = toks(role_text)
    key = re.sub(r"[^a-z0-9]+", "-", role_text.lower()).strip("-")
    rel = [(e, same_employer(org, e[0])) for e in idx]
    kin = [e for e, r in rel if r in ("same", "maybe")]
    if not kin:
        return "NEW-ORG", ""

    best, best_n, contained, weak_org = None, 0, None, None
    for (eorg, prev, src, prev_key, name, _), r in rel:
        if r == "no" or (exclude_name and name == exclude_name):
            continue
        # Hard duplicate requires slug EQUALITY. Containment is only a hint: "bioinformatics-
        # scientist" is contained in "senior-bioinformatics-scientist", and on 2026-07-30 that
        # rule called two separate live Basecamp reqs (distinct URLs, different seniority)
        # duplicates of each other. Seniority words are stopwords, so token-normalising cannot
        # separate them either -- so containment must never block.
        if prev_key and key and prev_key == key:
            note = "" if r == "same" else f" via org variant '{eorg}'"
            return "tracked", f"{src} (exact slug match{note})"
        if prev_key and key and (prev_key in key or key in prev_key):
            contained = contained or src
        n = len(t & prev)
        if n > best_n:
            best, best_n, weak_org = src, n, r

    if contained:
        return "possible", (f"{contained} (one slug contains the other — often a seniority "
                            f"variant, i.e. a genuinely different req)")
    if best_n >= 2:
        extra = " and the org slug is only a partial match" if weak_org == "maybe" else ""
        return "possible", (f"{best} (shares {best_n} token(s){extra} — check it is not just "
                            f"org boilerplate)")
    return "new-role", f"closest: {best}" if best else "new-role"


def main():
    argv = sys.argv[1:]
    idx = build_index()

    if "--query-url" in argv:
        u = argv[argv.index("--query-url") + 1]
        cu = canon_url(u)
        hit = next((src for _, _, src, _, _, pu in idx if pu and pu == cu), None)
        print(f"{'tracked' if hit else 'not-tracked'}\t{u}\t{hit or ''}")
        sys.exit(1 if hit else 0)

    if "--query" in argv:
        i = argv.index("--query")
        org, role = argv[i + 1], argv[i + 2]
        u = argv[i + 3] if len(argv) > i + 3 and argv[i + 3].startswith("http") else None
        verdict, ev = match(idx, org, role, url=u)
        print(f"{verdict}\t{org}\t{role}\t{ev}")
        sys.exit(1 if verdict == "tracked" else 0)

    files = sorted(ROOT.glob("inbox/*.txt"))
    if not files:
        print("inbox is empty — nothing to check.")
        return

    dupes = []
    for p in files:
        parts = p.stem.split("_")
        org = parts[0]
        role = parts[1] if len(parts) > 1 else ""
        verdict, ev = match(idx, org, role, exclude_name=p.name, url=file_url(p))
        mark = {"tracked": "DUPLICATE", "possible": "possible-dup", "new-role": "ok (new role)",
                "NEW-ORG": "ok (new org)"}[verdict]
        print(f"{mark:<14} {p.name}")
        if ev and verdict in ("tracked", "possible"):
            print(f"               -> {ev}")
        if verdict == "tracked":
            dupes.append(p)

    print(f"\n{len(files)} in inbox, {len(dupes)} confirmed duplicate(s). "
          f"'possible-dup' rows need a human/LLM look and do NOT block.")
    if dupes and "--delete" in argv:
        for p in dupes:
            p.unlink()
            print(f"removed {p.name}")
    elif dupes:
        print("Re-run with --delete to remove them, or keep them if /inbox should merge "
              "updated deadline/status into the existing profile.")
    sys.exit(1 if dupes else 0)


if __name__ == "__main__":
    main()
