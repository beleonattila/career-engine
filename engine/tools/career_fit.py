#!/usr/bin/env python3
"""
career_fit.py — the scoring v3 lookup: band + checks -> career_fit.

The mechanism is in engine/skills/inbox-eval.md §career_fit (Step 3 — the lookup); what the checks
mean is the user's (user/profile/preferences.md §Scoring), and their names and units come from
user/settings.toml [career_fit.checks]. This is the lookup as code, so /inbox and /rescore do the
arithmetic identically, and rescore_status.py --verify can catch a record whose number does not
follow from its own band and checks.

    python engine/tools/career_fit.py                     # print the whole table for your checks
    python engine/tools/career_fit.py A "<check>, <check>"
    python engine/tools/career_fit.py E none              # band E is judged inside 0-29, no lookup

Score = band floor + round(units / max units * band width), max units = the sum of the full checks.
The checks place a record inside its band and can never lift it out: the method sets the band.
The band scale is fixed for every user; only the checks are personal.
"""
import sys

from paths import settings

BANDS = {"A": (90, 100), "B": (75, 89), "C": (50, 74), "D": (30, 49), "E": (0, 29)}
CHECK_UNITS = {str(k): float(v) for k, v in settings()["career_fit"]["checks"].items()}
# "<name>-half" is the half-met form of <name>; the two exclude each other.
HALVES = {k: k[:-5] for k in CHECK_UNITS if k.endswith("-half") and k[:-5] in CHECK_UNITS}
MAX_UNITS = sum(u for k, u in CHECK_UNITS.items() if k not in HALVES)


def _names():
    full = [k for k in CHECK_UNITS if k not in HALVES]
    return ", ".join(f"{k} | {k}-half" if f"{k}-half" in HALVES else k for k in full)


def parse_checks(value):
    """'a, b-half' -> ['a', 'b-half'], checked against user/settings.toml. Raises ValueError."""
    v = (value or "").strip().strip("[]").strip()
    if v.lower() in ("", "none", "null", "~"):
        return []
    items = [x.strip().strip("\"'") for x in v.split(",") if x.strip()]
    unknown = [x for x in items if x not in CHECK_UNITS]
    if unknown:
        raise ValueError(f"unknown check(s) {', '.join(unknown)} (want none, or any of: {_names()})")
    if len(set(items)) != len(items):
        raise ValueError("a check is listed twice")
    for half, full in HALVES.items():
        if half in items and full in items:
            raise ValueError(f"{full} and {half} are mutually exclusive")
    return items


def units(checks):
    return sum(CHECK_UNITS[c] for c in checks)


def score(band, checks):
    """career_fit for bands A-D. None for band E, which is judged inside 0-29 without checks."""
    b = (band or "").strip().upper()
    if b not in BANDS:
        raise ValueError(f"unknown band {band!r} (want A, B, C, D or E)")
    if b == "E":
        return None
    lo, hi = BANDS[b]
    return lo + round(units(checks) / MAX_UNITS * (hi - lo))


def main(argv):
    if not argv:
        steps = [i / 2 for i in range(int(MAX_UNITS * 2) + 1)]
        print("units   " + "".join(f"{s:>5g}" for s in steps))
        for b, (lo, hi) in BANDS.items():
            if b == "E":
                print(f"E {lo}-{hi}  judged holistically, checks do not apply")
                continue
            row = [lo + round(s / MAX_UNITS * (hi - lo)) for s in steps]
            print(f"{b} {lo}-{hi}" + "".join(f"{n:>5}" for n in row)[len(f'{lo}-{hi}') - 4:])
        return 0
    if len(argv) not in (1, 2):
        print(__doc__)
        return 2
    try:
        checks = parse_checks(argv[1] if len(argv) == 2 else "none")
        n = score(argv[0], checks)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if n is None:
        if checks:
            print("error: band E takes no checks", file=sys.stderr)
            return 2
        print("band E: judge inside 0-29; no lookup")
        return 0
    print(n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
