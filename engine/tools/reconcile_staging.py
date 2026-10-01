#!/usr/bin/env python3
"""
reconcile_staging.py — merge the two search tracks' staging folders into the inbox.

Since 2026-08-17 each /search-* command runs two sub-agents in parallel: a `career` track
(is this the work the user wants?) and a `skill` track (could they get and do it?). They write to
separate staging folders because neither can reliably see the other's writes mid-run:

    inbox/_staging/career/   <- career sub-agent
    inbox/_staging/skill/    <- skill sub-agent
              |
              +--> this script --> inbox/

Overlap between the tracks is the COMMON CASE, not an edge case: a protein-design role that
also names Snakemake and HPC passes the career output gate and the skill competency gate, so
both agents collect it. On a collision **career wins** -- a lead clearing the career gate is one
the user wants regardless of how well their skills fit it, and that is the more useful provenance.

Each surviving file gets a `TRACK: career|skill` header line, which /inbox reads and writes to
the profile frontmatter as `track: career|employability`.

    python engine/tools/reconcile_staging.py             # report only
    python engine/tools/reconcile_staging.py --apply     # stamp, move, empty the staging folders
"""
import argparse
import re
import sys
from pathlib import Path

from paths import REPO, WORKSPACE as ROOT  # noqa: E402 — records are relative to user/workspace/
STAGING = ROOT / "inbox" / "_staging"
CAREER, SKILL = STAGING / "career", STAGING / "skill"
INBOX = ROOT / "inbox"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dedup_check import canon_url as _dedup_canon_url  # noqa: E402

SOURCE_RE = re.compile(r"^SOURCE:\s*(\S+)", re.M)
FOUND_RE = re.compile(r"^FOUND:\s*(\S+)", re.M)
TRACK_RE = re.compile(r"^TRACK:\s*\S+\s*$", re.M)


def canon_url(u):
    """Normalise a job-ad URL enough to compare two collections of the same posting.

    Delegates to dedup_check.canon_url so the two scripts share one notion of "the same
    posting" instead of drifting apart. That version requires the path itself to look
    posting-specific (an id-like digit run, a UUID, or a long slug) before treating a URL as
    an identity -- important for portals like employment.ku.dk, where every posting shares
    the path `/all-vacancies/` and the identity lives entirely in a `?show=<id>` query
    parameter. This script used to strip query strings unconditionally, which collapsed
    every KU posting onto one identity and produced false "within-track duplicate" warnings
    (caught 2026-08-26: three genuinely distinct KU Globe Institute / PLEN postings, four
    different `?show=` ids, all flagged as duplicates of each other).

    LinkedIn is the one case with its own rule: the same req appears as /jobs/view/<id>,
    with a ?trk= suffix, and via the ad-library path, so it is reduced to host + the numeric
    id before falling through to the generic check.
    """
    if not u:
        return ""
    low = u.strip().lower()
    m = re.search(r"linkedin\.com/.*?(\d{8,})", low)
    if m:
        return "linkedin:" + m.group(1)
    return _dedup_canon_url(u)


def identity(p):
    """(org_slug, role_slug) from the filename: org_role_found-DATE.txt -> (org, role)."""
    stem = p.stem
    stem = re.sub(r"_found-\d{4}-\d{2}-\d{2}$", "", stem)
    parts = stem.split("_")
    org = parts[0] if parts else stem
    role = parts[1] if len(parts) > 1 else ""
    return org.lower(), role.lower()


def read(p):
    return p.read_text(encoding="utf-8", errors="replace")


def collect(d, track):
    out = []
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.txt")):
        text = read(p)
        m = SOURCE_RE.search(text)
        out.append({
            "path": p, "track": track, "text": text,
            "url": canon_url(m.group(1) if m else ""),
            "ident": identity(p),
        })
    return out


def stamp_track(text, track):
    """Insert `TRACK: <track>` after the FOUND: line, or at the top if there is none."""
    if TRACK_RE.search(text):
        return TRACK_RE.sub(f"TRACK: {track}", text, count=1)
    m = FOUND_RE.search(text)
    if m:
        end = text.index("\n", m.start()) + 1 if "\n" in text[m.start():] else len(text)
        return text[:end] + f"TRACK: {track}\n" + text[end:]
    return f"TRACK: {track}\n" + text


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="stamp TRACK:, move into inbox/, empty the staging folders. "
                         "Default is report-only.")
    args = ap.parse_args()

    for d in (CAREER, SKILL):
        d.mkdir(parents=True, exist_ok=True)

    career = collect(CAREER, "career")
    skill = collect(SKILL, "skill")
    if not career and not skill:
        print("Both staging folders are empty — nothing to reconcile.")
        return 0

    # Career wins a collision. Match on canonical URL first (strongest), then on the
    # (org, role) pair from the filename for the case where two agents wrote different
    # URLs for the same posting -- a board mirror versus the employer ATS, say.
    career_urls = {c["url"] for c in career if c["url"]}
    career_idents = {c["ident"] for c in career}

    keep, dropped = list(career), []
    for s in skill:
        if s["url"] and s["url"] in career_urls:
            dropped.append((s, "same url as a career collection"))
        elif s["ident"] in career_idents:
            dropped.append((s, "same org+role as a career collection"))
        else:
            keep.append(s)

    # A track colliding with itself means the sub-agent's own dedup failed -- worth saying
    # out loud rather than silently merging, because it points at a bug in that skill.
    seen, self_dupes = {}, []
    for r in keep:
        k = r["url"] or r["ident"]
        if k in seen:
            self_dupes.append((r, seen[k]))
        else:
            seen[k] = r

    print(f"staging: {len(career)} career · {len(skill)} skill")
    print(f"  keep    {len(keep)}")
    print(f"  dropped {len(dropped)} (career wins)")
    for s, why in dropped:
        print(f"    - {s['path'].name}  [{why}]")
    if self_dupes:
        print(f"  [!] {len(self_dupes)} within-track duplicate(s) — a collector's own dedup "
              f"missed these:")
        for a, b in self_dupes:
            print(f"    - {a['path'].name}  ==  {b['path'].name}")

    if not args.apply:
        print("\nreport only — re-run with --apply to stamp TRACK: and move into inbox/")
        return 0

    moved, clashes = 0, []
    for r in keep:
        dest = INBOX / r["path"].name
        if dest.exists():
            # Never overwrite something already waiting in the inbox: that file has not been
            # processed yet and losing it would lose a whole collection silently.
            clashes.append(r["path"].name)
            continue
        dest.write_text(stamp_track(r["text"], r["track"]), encoding="utf-8")
        r["path"].unlink()
        moved += 1

    for s, _ in dropped:
        s["path"].unlink()

    leftover = [p for d in (CAREER, SKILL) for p in d.glob("*.txt")]
    print(f"\nmoved {moved} file(s) into inbox/")
    if clashes:
        print(f"  [!] {len(clashes)} left in staging — a file of that name is already in "
              f"inbox/ and was NOT overwritten:")
        for n in clashes:
            print(f"    - {n}")
    if leftover and not clashes:
        print(f"  [!] {len(leftover)} unexpected file(s) still in staging")
    elif not leftover:
        print("  staging folders empty")
    print("\nNext: /inbox  (scores everything, on Opus)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
