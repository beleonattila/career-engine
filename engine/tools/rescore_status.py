#!/usr/bin/env python3
"""
rescore_status.py — progress tracker for the scoring migration (career_fit v3 + method_fit).

On 2026-09-10 `career_fit` was redefined (skills/inbox-eval.md §career_fit): a judged band A-E,
three yes/no checks (application · validation · package) read off a lookup table, orgs banded by
their most on-direction line, and an org floor enforced by org_floor.py. `skill_match` and
`level_fit` did not change. Every record scored before that date carries `scoring: v2` or `v2.1`
and needs its career_fit re-judged by hand (an Opus judgement per file) — this says what is left.

On 2026-09-29 a THIRD score was added, `method_fit` (skills/inbox-eval.md §method_fit): does the
seat build methods, tools and systems, or only operate them? It is independent of career_fit and
is NOT part of the v2 -> v3 redefinition — but it has to be written onto every record, so the two
passes were merged deliberately rather than sweeping 382 files twice. A record counts as done only
when it is v3 AND carries method_fit; the ~22 records migrated before that date are therefore
incomplete again by design, and --next will hand them back.

    python engine/tools/rescore_status.py              # progress by folder
    python engine/tools/rescore_status.py --next 30    # next batch of paths to work, highest value first
    python engine/tools/rescore_status.py --verify     # find malformed / half-migrated v3 records

Earlier migrations this script tracked, both complete: v1 -> v2 (the blended fit_score split into
career_fit + skill_match, 2026-08-17, 364/364) and the v2.1 role-vs-employer re-check
(2026-08-18). The --recheck mode for the latter was removed with v3, which re-judges every
career_fit anyway.

THERE IS NO SEPARATE PROGRESS LEDGER, DELIBERATELY. Progress is derived from the
`scoring: v3` stamp inside each file, so it cannot drift out of sync with reality: a file is
done when it says it is done. A side-car ledger would be a second source of truth, and the
first interrupted run — or one hand-edit — would leave the two disagreeing with no way to
tell which is right. Resumability comes free: re-run this script and keep going.
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

from career_fit import BANDS, parse_checks, score as lookup

from paths import REPO, WORKSPACE as ROOT  # noqa: E402 — records are relative to user/workspace/
TARGET = "v3"

# Worked in this order: the value of a rescored record is how soon it changes a decision.
# Open leads are what /cv is run against tomorrow; closed ones are history — but they still
# feed the org floor, so they are migrated too, last.
SCOPES = [
    ("positions/open",            "position", "open leads — what /cv acts on next"),
    ("positions/applied",         "position", "live applications"),
    ("organizations/companies",   "org",      "employers — drives ats_sweep ranking"),
    ("organizations/research_groups", "org",      "labs — outreach targets"),
    ("positions/closed",          "position", "history — feeds the org floor and telemetry"),
]

FM_END = re.compile(r"^---\s*$", re.M)

# Non-entity documents that live alongside profiles -- a PI biography filed next to the group
# it belongs to, for instance. These are not scoreable records: a person has no scientific
# direction of their own to score and no stack to match, and the group they belong to already
# carries both numbers. Scoring one would invent a figure with nothing behind it and put a
# duplicate of that employer into every later analysis.
#
# KEEP IN SYNC with SKIP_TYPES in dashboard.py and org_floor.py, which skip the same documents
# for the same reason. dashboard.py cannot be imported here -- it generates the HTML as an
# import side effect -- so the literal is duplicated deliberately rather than shared.
SKIP_TYPES = {"person_bio"}

# Written by org_floor.py on an org whose own judgement sits below its best linked position.
FLOOR_KEYS = ("career_fit_own", "career_fit_floor", "career_fit_floor_from")


def frontmatter(text):
    """Return the raw frontmatter block, or '' when the file has none."""
    if not text.startswith("---"):
        return ""
    m = FM_END.search(text, 3)
    return text[3:m.start()] if m else ""


def field(fm, key):
    m = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.M)
    if not m:
        return None
    v = m.group(1).strip().strip("\"'")
    return None if v.lower() in ("", "null", "~") else v


def scan():
    """[(scope, kind, path, fm)] over every record the migration covers."""
    out = []
    for scope, kind, _ in SCOPES:
        d = ROOT / scope
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            fm = frontmatter(p.read_text(encoding="utf-8", errors="replace"))
            if (field(fm, "type") or "").strip().lower() in SKIP_TYPES:
                continue
            out.append((scope, kind, p, fm))
    return out


def is_done(fm):
    """Stamped v3. NOT the same as complete -- see is_complete()."""
    return field(fm, "scoring") == TARGET


def is_complete(scope, kind, p, fm):
    """Stamped v3 AND internally consistent. A stamp alone once reported 100% while 141 records
    were still missing a field (the v1 -> v2 org top-up, 2026-08-17). Count the fields."""
    return is_done(fm) and not problems(scope, kind, p, fm)


def _int(fm, key, bad):
    v = field(fm, key)
    if v is None:
        return None
    try:
        n = int(v)
    except ValueError:
        bad.append(f"{key} is not an integer: {v!r}")
        return None
    if not 0 <= n <= 100:
        bad.append(f"{key} out of range: {n}")
    return n


def problems(scope, kind, p, fm):
    """Everything wrong with one v3 record, as a list of strings. Empty list = clean."""
    bad = []
    if not is_done(fm):
        return bad  # not migrated yet is not a defect, it is just pending

    cf = _int(fm, "career_fit", bad)
    if field(fm, "career_fit") is None:
        bad.append("stamped v3 but has no career_fit")
    if field(fm, "skill_match") is None:
        bad.append("stamped v3 but has no skill_match")
    _int(fm, "skill_match", bad)
    # method_fit (added 2026-09-29) rides along with the v3 pass — see the module docstring.
    if field(fm, "method_fit") is None:
        bad.append("no method_fit (added 2026-09-29; score it — see inbox-eval.md §method_fit)")
    _int(fm, "method_fit", bad)
    for retired in ("fit_score", "verdict"):
        if field(fm, retired) is not None:
            bad.append(f"still carries retired {retired}")

    if kind == "position":
        lvl = field(fm, "level_fit")
        if lvl not in ("realistic", "reach", "below"):
            bad.append(f"level_fit is {lvl!r} (want realistic|reach|below)")
    elif field(fm, "level_fit") is not None:
        # An org advertises no seniority, so there is nothing for level_fit to describe.
        bad.append("org profile must not carry level_fit")

    # --- v3: band + checks
    band = (field(fm, "career_band") or "").upper()
    if band not in BANDS:
        bad.append(f"career_band is {band or None!r} (want A|B|C|D|E)")
    checks = None
    raw = field(fm, "career_checks")
    if raw is None:
        bad.append("no career_checks (write `none` when no check applies)")
    else:
        try:
            checks = parse_checks(raw)
        except ValueError as e:
            bad.append(f"career_checks: {e}")

    # --- org floor: the band and checks describe the org's OWN judgement, not the floored number
    own = cf
    present = [k for k in FLOOR_KEYS if field(fm, k) is not None]
    if present:
        if kind == "position":
            bad.append("a position must not carry org-floor fields (the floor only runs upward)")
        elif len(present) != len(FLOOR_KEYS):
            bad.append(f"partial org floor ({', '.join(present)}) — delete all three and rerun "
                       f"org_floor.py --apply")
        else:
            own = _int(fm, "career_fit_own", bad)
            floor = _int(fm, "career_fit_floor", bad)
            if cf is not None and floor is not None and cf != floor:
                bad.append(f"career_fit {cf} != career_fit_floor {floor} — re-judged without "
                           f"deleting the floor fields? delete them, rerun org_floor.py --apply")
            if own is not None and floor is not None and own >= floor:
                bad.append("career_fit_own is not below the floor — rerun org_floor.py --apply")

    if band in BANDS and checks is not None and own is not None:
        which = "career_fit_own" if present and kind != "position" else "career_fit"
        if band == "E":
            if checks:
                bad.append("band E takes no checks (career_checks: none)")
            if not 0 <= own <= 29:
                bad.append(f"band E must score 0-29, {which} is {own}")
        else:
            want = lookup(band, checks)
            if own != want:
                bad.append(f"{which} {own} does not follow from band {band} + checks — expected "
                           f"{want} (python engine/tools/career_fit.py {band} \"{', '.join(checks) or 'none'}\")")
    return bad


def _needs_method_fit_only(scope, kind, p, fm):
    """True when the record is a clean v3 whose single gap is the method_fit added 2026-09-29."""
    probs = problems(scope, kind, p, fm)
    return len(probs) == 1 and probs[0].startswith("no method_fit")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--next", type=int, metavar="N",
                    help="print the next N file paths to re-judge, highest value first")
    ap.add_argument("--verify", action="store_true",
                    help="check v3 records for malformed or half-applied frontmatter")
    args = ap.parse_args()

    records = scan()
    if not records:
        print("No records found — is user/workspace/ populated?")
        return 1

    if args.next:
        # Incomplete = not yet v3, OR stamped v3 but malformed. Both are work, and /rescore
        # should not have to know which kind it is.
        pending = [pp for sc, k, pp, fm in records if not is_complete(sc, k, pp, fm)]
        for p in pending[:args.next]:
            print(p.relative_to(REPO).as_posix())
        if not pending:
            print("# nothing left — every record is v3 and clean", file=sys.stderr)
        return 0

    if args.verify:
        found = 0
        for scope, kind, p, fm in records:
            for msg in problems(scope, kind, p, fm):
                print(f"  [!] {p.relative_to(REPO).as_posix()}: {msg}")
                found += 1
        print(f"\n{found} problem(s) across {sum(1 for _, _, _, fm in records if is_done(fm))} "
              f"v3 record(s).")
        return 1 if found else 0

    print("scoring migration  (career_fit v2 -> v3 = band + checks; + method_fit; "
          "skill_match untouched)")
    print()
    total_done = total_all = total_bad = total_mf = 0
    for scope, _, note in SCOPES:
        rows = [r for r in records if r[0] == scope]
        if not rows:
            continue
        done = sum(1 for r in rows if is_complete(*r))
        # A v3 record whose only gap is the new method_fit is not malformed, it is pending the
        # 2026-09-29 addition. Counting the two together read as 22 broken files on the day
        # method_fit landed, which is alarming and wrong.
        mf_only = sum(1 for r in rows if is_done(r[3]) and _needs_method_fit_only(*r))
        bad = sum(1 for r in rows
                  if is_done(r[3]) and not is_complete(*r) and not _needs_method_fit_only(*r))
        total_done += done
        total_all += len(rows)
        total_bad += bad
        total_mf += mf_only
        bar_len = 24
        filled = round(bar_len * done / len(rows))
        bar = "#" * filled + "." * (bar_len - filled)
        flag = "".join([f"  [{mf_only} need method_fit]" if mf_only else "",
                        f"  [{bad} malformed]" if bad else ""])
        print(f"  {scope:<28} {bar} {done:>3}/{len(rows):<4} {note}{flag}")

    pct = round(100 * total_done / total_all) if total_all else 0
    print()
    print(f"  {'TOTAL':<28} {'':<24} {total_done:>3}/{total_all:<4} ({pct}%)")
    bands = Counter((field(r[3], "career_band") or "?").upper() for r in records if is_complete(*r))
    if bands:
        print(f"  bands so far: " + " | ".join(f"{b} {bands.get(b, 0)}" for b in BANDS))
    if total_all - total_done:
        print()
        if total_mf:
            print(f"  {total_mf} record(s) are v3 already and only need the new method_fit.")
        if total_bad:
            print(f"  {total_bad} record(s) stamped v3 but malformed -- python engine/tools/rescore_status.py --verify")
        print("  Run /rescore to continue (a fresh session per batch).")
    else:
        print()
        print("  Migration complete. Run `python engine/tools/org_floor.py --apply` and `python engine/tools/dashboard.py`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
