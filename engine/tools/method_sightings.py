#!/usr/bin/env python3
"""
method_sightings.py — which employers post method-building roles, and the skill track's org rotation.

A method-building seat rarely says so in its title (it hides under "Scientist" or
"Bioinformatician"; the build is in the responsibilities), so searching job boards *for* it
yields little. What does predict the next one is the employer: an org that has posted a
build-tools-for-scientists role before is likely to again, and it is a far better cold-outreach
target than one judged from its "about us" page. This tool keeps that record.

A SIGHTING is any posting whose role text shows a build seat, whatever happened to it — collected,
skipped on level or geography, already expired. The skipped ones carry most of the signal: they
say the org hires method people even when this particular ad was not attainable.

Who writes sightings:
  * the skill-track collector, for every row the method lane flagged and it then read
    (engine/skills/search-positions-skill.md §Method lane) — collected or not;
  * /inbox, for every position it scores at method_fit >= 75 (engine/skills/inbox-eval.md).
Collectors still write nothing but staging files and this log; the org profiles are changed only
by --apply, so there is one writer of the derived fields.

    python engine/tools/method_sightings.py                       # per-org summary of the log
    python engine/tools/method_sightings.py add --org genmab --title "Scientist, Computational Biology" \\
        --url https://... --signal "you will build the analysis platform used by our scientists" \\
        --outcome skipped-level --source skill
    python engine/tools/method_sightings.py --apply               # write the counts onto org profiles
    python engine/tools/method_sightings.py --rotation 20         # the skill track's org sweep order

The log is user/workspace/logs/method_sightings.tsv, one row per posting (deduplicated on URL).
--apply writes two DERIVED fields onto the matching company / group profile, like org_floor.py's
floor fields: `method_roles_seen: N` (distinct postings) and `last_method_role: YYYY-MM-DD`. Never
edit them by hand — edit the log and re-apply.
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path


from paths import REPO, WORKSPACE as ROOT  # noqa: E402 — records are relative to user/workspace/

try:
    from dedup_check import same_employer, ALIASES
except Exception:                                    # keep working regardless
    same_employer = lambda a, b: "same" if a == b else "no"
    ALIASES = {}

LOG = ROOT / "logs" / "method_sightings.tsv"
HEADER = ["date", "org", "title", "url", "signal", "outcome", "source"]
# seen = noted on a careers page while profiling the org (/search-companies, /search-groups), not
# screened as a position; scored = logged by /inbox at method_fit >= 75.
OUTCOMES = {"collected", "skipped-level", "skipped-geo", "skipped-gate", "expired", "duplicate",
            "scored", "seen"}
SOURCES = {"skill", "career", "inbox", "manual"}
ORG_DIRS = ("organizations/companies", "organizations/research_groups")
# The skill track's org-sweep threshold (search-positions-common.md §How and Where to Search).
SWEEP_MIN = 60
DERIVED = ("method_roles_seen", "last_method_role")

FM_END = re.compile(r"^---\s*$", re.M)


def read_log():
    if not LOG.exists():
        return []
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines()[1:]:
        p = line.split("\t")
        if len(p) >= len(HEADER):
            rows.append(dict(zip(HEADER, p)))
    return rows


def clean(s):
    """One TSV cell: no tabs, no newlines."""
    return re.sub(r"\s+", " ", s or "").strip()


def frontmatter(text):
    if not text.startswith("---"):
        return "", 0
    m = FM_END.search(text, 3)
    return (text[3:m.start()], m.start()) if m else ("", 0)


def field(fm, key):
    m = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.M)
    if not m:
        return None
    v = m.group(1).strip().strip("\"'")
    return None if v.lower() in ("", "null", "~") else v


def num(fm, key):
    v = field(fm, key)
    return int(v) if v and v.isdigit() else None


def profiles():
    """{slug: path} for every company and research-group profile."""
    out = {}
    for d in ORG_DIRS:
        for p in sorted((ROOT / d).glob("*.md")):
            out[p.stem] = p
    return out


def resolve(org, profs):
    """The profile slug a logged org belongs to, or None. Aliases first, then dedup_check's rule."""
    org = ALIASES.get(org, org)
    if org in profs:
        return org
    hits = [s for s in profs if same_employer(org, s) == "same"]
    return hits[0] if len(hits) == 1 else None


def cmd_add(a):
    if a.outcome not in OUTCOMES:
        sys.exit(f"--outcome must be one of {sorted(OUTCOMES)}")
    if a.source not in SOURCES:
        sys.exit(f"--source must be one of {sorted(SOURCES)}")
    rows = read_log()
    key = a.url.strip() or f"{a.org}|{a.title}".lower()
    for r in rows:
        if (r["url"] or f"{r['org']}|{r['title']}".lower()) == key:
            print(f"already logged {r['date']}: {r['org']} — {r['title']} ({r['outcome']})")
            return 0
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", encoding="utf-8", newline="\n") as f:
        if new:
            f.write("\t".join(HEADER) + "\n")
        f.write("\t".join(clean(x) for x in (a.date, a.org, a.title, a.url, a.signal, a.outcome,
                                               a.source)) + "\n")
    print(f"logged: {a.org} — {a.title} ({a.outcome}, {a.source})")
    return 0


def tally(rows, profs):
    """slug -> (count, last date); plus the orgs that match no profile."""
    by, orphans = {}, {}
    for r in rows:
        slug = resolve(r["org"], profs)
        if slug is None:
            orphans.setdefault(r["org"], []).append(r)
            continue
        n, last = by.get(slug, (0, ""))
        by[slug] = (n + 1, max(last, r["date"]))
    return by, orphans


def set_fields(text, values):
    """Write `values` into the frontmatter: replace in place, else insert after method_fit
    (or skill_match, or before schema_version)."""
    fm, end = frontmatter(text)
    if not end:
        return text
    lines = fm.strip("\n").split("\n")
    for k, v in values.items():
        idx = next((i for i, l in enumerate(lines) if l.startswith(f"{k}:")), None)
        if idx is not None:
            lines[idx] = f"{k}: {v}"
            continue
        after = next((i for i, l in enumerate(lines) if l.startswith(f"{DERIVED[0]}:")), None)
        if after is None:
            after = next((i for key in ("method_fit", "skill_match")
                          for i, l in enumerate(lines) if l.startswith(f"{key}:")), None)
        if after is None:
            after = next((i - 1 for i, l in enumerate(lines) if l.startswith("schema_version:")),
                         len(lines) - 1)
        lines.insert(after + 1, f"{k}: {v}")
    return "---\n" + "\n".join(lines) + "\n" + text[end:]


def cmd_apply(rows, profs):
    by, orphans = tally(rows, profs)
    changed = 0
    for slug, (n, last) in sorted(by.items()):
        p = profs[slug]
        text = p.read_text(encoding="utf-8")
        new = set_fields(text, {"method_roles_seen": n, "last_method_role": last})
        if new != text:
            p.write_text(new, encoding="utf-8", newline="\n")
            changed += 1
            print(f"  SET  {p.relative_to(REPO).as_posix()}: method_roles_seen {n} · last {last}")
    print(f"\n{changed} profile(s) updated, {len(by) - changed} already current.")
    if orphans:
        print(f"{len(orphans)} logged org(s) match no profile — /inbox creates one when a role is "
              f"collected; otherwise consider a company or group profile:")
        for org, rs in sorted(orphans.items()):
            print(f"  {org}: {len(rs)} sighting(s), latest {max(r['date'] for r in rs)}")
    return 0


def tracked_slugs():
    """Org slugs (alias-normalised) with any position file in the vault."""
    out = set()
    for sub in ("open", "applied", "closed"):
        for p in (ROOT / "positions" / sub).glob("*.md"):
            s = p.stem.split("_", 1)[0]
            out.add(ALIASES.get(s, s))
    return out


def cmd_rotation(n, profs):
    """The skill track's org-sweep order: proven method hirers first, then untouched orgs, then
    the oldest check. Eligible = skill_match or method_fit at the sweep threshold, or any sighting."""
    tracked = tracked_slugs()
    rows = []
    for slug, p in profs.items():
        fm, _ = frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        if (field(fm, "type") or "") == "person_bio":
            continue
        sm, mf = num(fm, "skill_match") or 0, num(fm, "method_fit")
        seen = num(fm, "method_roles_seen") or 0
        if max(sm, mf or 0) < SWEEP_MIN and not seen:
            continue
        has_lead = any(t == slug or same_employer(t, slug) == "same" for t in tracked)
        rows.append((seen == 0, has_lead, field(fm, "last_evaluated") or "0000-00-00",
                     slug, sm, mf, seen, p))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    print("seen\tmethod\tskill\tlead\tlast_eval\torg\tprofile")
    for _, has_lead, last, slug, sm, mf, seen, p in rows[:n]:
        print(f"{seen}\t{'-' if mf is None else mf}\t{sm}\t{'yes' if has_lead else 'no'}\t{last}"
              f"\t{slug}\t{p.relative_to(REPO).as_posix()}")
    unscored = sum(1 for r in rows if r[5] is None)
    print(f"\n# {len(rows)} eligible org(s) (skill_match or method_fit >= {SWEEP_MIN}, or a "
          f"sighting); showing {min(n, len(rows))}.", file=sys.stderr)
    if unscored:
        print(f"# {unscored} of them carry no method_fit yet — /inbox scores it.",
              file=sys.stderr)
    return 0


def cmd_status(rows, profs):
    if not rows:
        print(f"No sightings logged yet ({LOG.relative_to(REPO).as_posix()} does not exist).")
        return 0
    by, orphans = tally(rows, profs)
    print(f"{len(rows)} sighting(s) across {len(by) + len(orphans)} org(s)\n")
    for slug, (n, last) in sorted(by.items(), key=lambda kv: (-kv[1][0], kv[0])):
        print(f"  {n:>3}  {last}  {slug}")
    for org, rs in sorted(orphans.items()):
        print(f"  {len(rs):>3}  {max(r['date'] for r in rs)}  {org}  (no profile)")
    pending = sum(1 for slug, (n, _) in by.items()
                  if num(frontmatter(profs[slug].read_text(encoding="utf-8"))[0],
                         "method_roles_seen") != n)
    if pending:
        print(f"\n{pending} profile(s) out of date — run with --apply.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write method_roles_seen / last_method_role onto the org profiles")
    ap.add_argument("--rotation", type=int, metavar="N",
                    help="print the skill track's org-sweep order, first N")
    sub = ap.add_subparsers(dest="cmd")
    add = sub.add_parser("add", help="log one sighting")
    add.add_argument("--org", required=True, help="org slug, as in the position filename")
    add.add_argument("--title", required=True)
    add.add_argument("--url", default="")
    add.add_argument("--signal", required=True,
                     help="the role-text sentence that shows the build seat, verbatim")
    add.add_argument("--outcome", required=True, help=" | ".join(sorted(OUTCOMES)))
    add.add_argument("--source", required=True, help=" | ".join(sorted(SOURCES)))
    add.add_argument("--date", default=dt.date.today().isoformat())
    a = ap.parse_args()

    if a.cmd == "add":
        return cmd_add(a)
    profs = profiles()
    if a.apply:
        return cmd_apply(read_log(), profs)
    if a.rotation:
        return cmd_rotation(a.rotation, profs)
    return cmd_status(read_log(), profs)


if __name__ == "__main__":
    sys.exit(main())
