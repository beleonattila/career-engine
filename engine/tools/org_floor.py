#!/usr/bin/env python3
"""
org_floor.py — an organisation never scores below its best position.

Rule (skills/inbox-eval.md §domain_fit, Step 4 — added 2026-09-10 on the user's instruction):
a company or research group's `domain_fit` is at least the highest `domain_fit` of any position
linked to it, open, applied or closed. A lab that posted a 92 role does that work, however much
else it also does. Found when a research group scored 85 while its own PhD call scored
92 ("the group is broader"); a scan the same day found ~15 orgs below their best role, the widest
being Sanofi at 55 against a 95 protein-design role. Closed positions count on purpose: an expired
posting still proves the org does the work, and an org's score must not fall when an ad expires.

Positions are linked to profiles by org_match.py — the same matcher the dashboard uses — with the
`org_profile:` frontmatter field as the manual override (`none` suppresses a match).

When the floor binds, the profile keeps its own judgement visible:
    domain_fit: 92                 <- what every consumer reads (dashboard, ats_sweep, sweeps)
    domain_fit_own: 85             <- the org judged on its own stated work
    domain_fit_floor: 92           <- the floor as last applied
    domain_fit_floor_from: some-org_phd-some-role_2026-07
plus a dated line under ## History. When it stops binding (the position was re-scored down, or the
org's own judgement caught up), the three fields are removed and domain_fit returns to the judgement.

Re-judging an org: write the new number to `domain_fit`, delete the three floor fields, then run
this with --apply. If the fields are left behind, a domain_fit that no longer equals
domain_fit_floor is still recognised as a fresh judgement and wins over the stale _own.

    python engine/tools/org_floor.py                # report only — nothing is written
    python engine/tools/org_floor.py --apply        # write the floors
    python engine/tools/org_floor.py --candidates   # also list on-direction positions with no org profile at all

Stdlib only. Run from the repo root.
"""
import argparse
import datetime
import re
from pathlib import Path

from org_match import employer_hit, file_slug, token_df

from paths import REPO, WORKSPACE as ROOT, setting  # noqa: E402 — records are relative to user/workspace/
TODAY = datetime.date.today().isoformat()

PROFILE_DIRS = ("organizations/companies", "organizations/research_groups")
POSITION_DIRS = ("positions/applied", "positions/open", "positions/closed")
FOLDER_RANK = {"applied": 2, "open": 1, "closed": 0}     # tie-break: prefer a live position

# KEEP IN SYNC with SKIP_TYPES in dashboard.py.
SKIP_TYPES = {"person_bio"}

FLOOR_KEYS = ("domain_fit_own", "domain_fit_floor", "domain_fit_floor_from")
CANDIDATE_MIN = setting("thresholds.on_direction")

FM_RE = re.compile(r"\A---\n(.*?)\n---[ \t]*\n", re.S)


def read(path):
    """(text with \\n line endings, original line ending)."""
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        raw = f.read()
    return raw.replace("\r\n", "\n"), ("\r\n" if "\r\n" in raw else "\n")


def field(fm, key):
    m = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.M)
    if not m:
        return None
    v = m.group(1).strip().strip("\"'")
    return None if v.lower() in ("", "null", "~") else v


def as_int(v):
    m = re.match(r"\s*(\d+)", v or "")
    return int(m.group(1)) if m else None


def load():
    profiles, positions = [], []
    for d in PROFILE_DIRS:
        for p in sorted((ROOT / d).glob("*.md")):
            m = FM_RE.match(read(p)[0])
            if not m or (field(m.group(1), "type") or "").lower() in SKIP_TYPES:
                continue
            fm = m.group(1)
            profiles.append({
                "slug": p.stem, "path": p,
                "name": field(fm, "name") or field(fm, "organization") or p.stem,
                "cf": as_int(field(fm, "domain_fit")),
                "own": as_int(field(fm, "domain_fit_own")),
                "floor": as_int(field(fm, "domain_fit_floor")),
                "from": field(fm, "domain_fit_floor_from"),
            })
    for d in POSITION_DIRS:
        for p in sorted((ROOT / d).glob("*.md")):
            m = FM_RE.match(read(p)[0])
            if not m:
                continue
            fm = m.group(1)
            cf = as_int(field(fm, "domain_fit"))
            if cf is None:
                continue
            positions.append({
                "slug": p.stem, "path": str(p), "folder": d.split("/")[1], "cf": cf,
                "org": field(fm, "organization") or field(fm, "name") or "",
                "org_profile": field(fm, "org_profile") or "",
            })
    return profiles, positions


def own_judgement(prof):
    """The org's score on its own work. `domain_fit_own` is trusted only while domain_fit still
    equals the floor last applied — otherwise domain_fit was re-judged since, and that wins."""
    if prof["own"] is not None and prof["floor"] is not None and prof["cf"] == prof["floor"]:
        return prof["own"]
    return prof["cf"]


def plan(profiles, positions):
    df = token_df(profiles)
    links = {pos["slug"]: [] for pos in positions}
    rows = []
    for prof in profiles:
        linked = [pos for pos in positions if employer_hit(prof, pos, df)]
        for pos in linked:
            links[pos["slug"]].append(prof["slug"])
        if prof["cf"] is None:
            continue
        own = own_judgement(prof)
        best = max(linked, key=lambda x: (x["cf"], FOLDER_RANK[x["folder"]], x["slug"]),
                   default=None)
        if best and best["cf"] > own:
            want = {"domain_fit": best["cf"], "domain_fit_own": own,
                    "domain_fit_floor": best["cf"], "domain_fit_floor_from": best["slug"]}
        else:
            want = {"domain_fit": own}
        have = {"domain_fit": prof["cf"]}
        for key, src in zip(FLOOR_KEYS, ("own", "floor", "from")):
            if prof[src] is not None:
                have[key] = prof[src]
        rows.append({"prof": prof, "own": own, "best": best, "linked": linked,
                     "want": want, "have": have})
    return rows, links


def add_history(body, line):
    m = re.search(r"^## History[ \t]*\n", body, re.M)
    if not m:
        return None
    nxt = re.search(r"^## ", body[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(body)
    section = body[m.end():end].rstrip("\n")
    return (body[:m.end()] + section + ("\n" if section else "") + line + "\n"
            + ("\n" if nxt else "") + body[end:])


def history_line(row):
    old, new, own = row["have"]["domain_fit"], row["want"]["domain_fit"], row["own"]
    if "domain_fit_floor_from" in row["want"]:
        src = row["want"]["domain_fit_floor_from"]
        return (f"- {TODAY}: org_floor.py — domain_fit {old} → {new}, floored by the linked "
                f"position [[{src}]]; the org's own judgement ({own}) is kept as domain_fit_own.")
    return (f"- {TODAY}: org_floor.py — floor released, domain_fit {old} → {new} (own judgement; "
            f"no linked position scores higher).")


def rewrite(row):
    path = row["prof"]["path"]
    text, eol = read(path)
    m = FM_RE.match(text)
    out = []
    for line in m.group(1).split("\n"):
        if any(re.match(rf"^{k}:", line) for k in FLOOR_KEYS):
            continue
        if re.match(r"^domain_fit:", line):
            out.append(f"domain_fit: {row['want']['domain_fit']}")
            out += [f"{k}: {row['want'][k]}" for k in FLOOR_KEYS if k in row["want"]]
            continue
        out.append(line)
    body = text[m.end():]
    note = ""
    if row["want"]["domain_fit"] != row["have"]["domain_fit"]:
        new_body = add_history(body, history_line(row))
        if new_body is None:
            note = " (no ## History section — frontmatter updated, no history line)"
        else:
            body = new_body
    new = "---\n" + "\n".join(out) + "\n---\n" + body
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(new.replace("\n", eol))
    return note


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="write the floors (default: report only)")
    ap.add_argument("--candidates", action="store_true",
                    help=f"list positions at domain_fit >= {CANDIDATE_MIN} linked to no org profile")
    args = ap.parse_args()

    profiles, positions = load()
    rows, links = plan(profiles, positions)
    changed = [r for r in rows if r["want"] != r["have"]]
    verb = "" if args.apply else "would be "

    print("org_floor — an org never scores below its best linked position (open, applied, closed)")
    print(f"{len(rows)} scored org profiles · {len(positions)} scored positions"
          + ("" if args.apply else " · dry run, nothing written (--apply to write)"))

    for title, sel in (
        ("LIFTED", lambda r: r["want"]["domain_fit"] > r["have"]["domain_fit"]),
        ("RELEASED", lambda r: r["want"]["domain_fit"] < r["have"]["domain_fit"]),
        ("FLOOR FIELDS UPDATED (score unchanged)",
         lambda r: r["want"]["domain_fit"] == r["have"]["domain_fit"]),
    ):
        group = sorted((r for r in changed if sel(r)),
                       key=lambda r: r["have"]["domain_fit"] - r["want"]["domain_fit"])
        if not group:
            continue
        print(f"\n{title} — {len(group)} {verb}changed")
        for r in group:
            best = r["best"]
            src = f"  from {best['slug']} ({best['folder']})" if best and best["cf"] > r["own"] else ""
            shared = [s for s in links[best["slug"]] if s != r["prof"]["slug"]] if src else []
            print(f"  {r['prof']['slug']:<42} {r['have']['domain_fit']:>3} -> "
                  f"{r['want']['domain_fit']:<3}{src}")
            if shared:
                print(f"  {'':<42} (that position also links to: {', '.join(shared)})")
            if args.apply:
                note = rewrite(r)
                if note:
                    print(f"  {'':<42} {note.strip()}")

    floored = sum(1 for r in rows if "domain_fit_floor_from" in r["want"])
    no_link = sum(1 for r in rows if not r["linked"])
    print(f"\n{floored} orgs sit on a floor · {len(rows) - floored - no_link} are at or above "
          f"their best position · {no_link} have no linked position")

    slugs = {p["slug"] for p in profiles}
    dangling = [p for p in positions
                if p["org_profile"] and p["org_profile"] != "none" and p["org_profile"] not in slugs]
    if dangling:
        print(f"\n⚠ org_profile names a profile that does not exist — {len(dangling)}")
        for p in dangling:
            print(f"  {p['slug']}  ->  org_profile: {p['org_profile']}")

    if args.candidates:
        orphans = {}
        for p in positions:
            if not links[p["slug"]] and p["cf"] >= CANDIDATE_MIN and p["org_profile"] != "none":
                orphans.setdefault(file_slug(p["path"]), []).append(p)
        print(f"\nPROFILE CANDIDATES — positions >= {CANDIDATE_MIN} whose employer has no profile "
              f"({len(orphans)} employers)")
        for org, ps in sorted(orphans.items(), key=lambda kv: -max(p["cf"] for p in kv[1])):
            live = sum(1 for p in ps if p["folder"] != "closed")
            print(f"  {max(p['cf'] for p in ps):>3}  {org:<40} {len(ps)} position(s), {live} live")


if __name__ == "__main__":
    main()
