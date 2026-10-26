#!/usr/bin/env python3
"""
schema.py — the record format version: the one place that knows it, and the way records move to it.

Every record (positions, organisation profiles, contacts) carries `schema_version: N` in its
frontmatter. It versions the *file format* — which fields exist, where records live, what paths
inside them are relative to — and is separate from `scoring:`, which versions the *rubric* a score
was judged under. A record older than SCHEMA_VERSION is migrated by this script, never by hand.

    python engine/tools/schema.py            # report: records per schema_version
    python engine/tools/schema.py --apply    # migrate every record to SCHEMA_VERSION

Versions (details: engine/docs/RECORD_SCHEMA.md):
    0  no stamp — any record written before 2026-10-01
    1  the layout after the 2026-09-30 / 10-01 restructure: records under user/workspace/, record
       paths relative to it, career_fit + method_fit + skill_match (+ level_fit on positions),
       career_band / career_checks, track. Going 0 -> 1 only adds the stamp: every record on disk
       at that date already had this layout.

To change the format: write migrate_N_to_N1() below, register it in MIGRATIONS, bump
SCHEMA_VERSION, update the templates in engine/skills/inbox-eval.md §Handlers and the contacts
README, then run --apply.
"""
import argparse
import re
import sys
from collections import Counter

from paths import WORKSPACE

SCHEMA_VERSION = 2

RECORD_DIRS = ("positions/open", "positions/applied", "positions/closed",
               "organizations/companies", "organizations/research_groups", "contacts")
SKIP_FILES = {"README.md"}

FM = re.compile(r"\A---\r?\n(.*?)\r?\n(---[ \t]*)\r?\n", re.S)
VERSION = re.compile(r"^schema_version:\s*(\d+)\s*(?:#.*)?$", re.M)   # a trailing comment is tolerated
VERSION_LINE = re.compile(r"^schema_version:\s*\d+\s*(?:#.*)?$")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def records():
    for d in RECORD_DIRS:
        for p in sorted((WORKSPACE / d).glob("*.md")):
            if p.name not in SKIP_FILES:
                yield p


def version_of(text):
    """The record's schema_version; 0 when unstamped; None when it has no frontmatter at all."""
    m = FM.match(text)
    if not m:
        return None
    v = VERSION.search(m.group(1))
    return int(v.group(1)) if v else 0


def set_version(text, n):
    """Write `schema_version: n` as the last frontmatter line, replacing any existing stamp."""
    m = FM.match(text)
    nl = "\r\n" if "\r\n" in text[:m.end()] else "\n"
    lines = [l for l in m.group(1).replace("\r\n", "\n").split("\n") if not VERSION_LINE.match(l)]
    return "---" + nl + nl.join(lines + [f"schema_version: {n}"]) + nl + m.group(2) + nl + text[m.end():]


def migrate_0_to_1(text):
    """0 -> 1: the format did not change, the stamp is all that is missing."""
    return set_version(text, 1)


BENCH_LOAD = re.compile(r"^bench_load:", re.M)


def migrate_1_to_2(text):
    """1 -> 2: positions gain `bench_load` (how much wet-lab work the seat itself requires; reported,
    never scored). Existing positions get `unknown`, placed after `remote_policy:` when present;
    organisations and contacts only take the new stamp."""
    m = FM.match(text)
    fm = m.group(1)
    if re.search(r"^role_title:", fm, re.M) and not BENCH_LOAD.search(fm):
        nl = "\r\n" if "\r\n" in fm else "\n"
        lines = fm.split(nl)
        at = next((i + 1 for i, l in enumerate(lines) if l.startswith("remote_policy:")), None)
        if at is None:
            at = next((i for i, l in enumerate(lines) if VERSION_LINE.match(l)), len(lines))
        lines.insert(at, "bench_load: unknown")
        text = "---" + nl + nl.join(lines) + nl + m.group(2) + nl + text[m.end():]
    return set_version(text, 2)


MIGRATIONS = {0: migrate_0_to_1, 1: migrate_1_to_2}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help=f"migrate every record to schema_version {SCHEMA_VERSION}")
    a = ap.parse_args()

    counts, unparsed, moved = Counter(), [], 0
    for p in records():
        raw = p.read_bytes().decode("utf-8")
        v = version_of(raw)
        if v is None:
            unparsed.append(p)
            continue
        counts[v] += 1
        if a.apply and v < SCHEMA_VERSION:
            text = raw
            while v < SCHEMA_VERSION:
                if v not in MIGRATIONS:
                    raise SystemExit(f"{p}: no migration from schema_version {v}")
                text = MIGRATIONS[v](text)
                v += 1
            p.write_bytes(text.encode("utf-8"))
            moved += 1

    rel = lambda p: p.relative_to(WORKSPACE).as_posix()
    print(f"schema_version {SCHEMA_VERSION} is current. Records by version:")
    for v in sorted(counts):
        if v == SCHEMA_VERSION:
            tag = "current"
        elif v > SCHEMA_VERSION:
            tag = "NEWER than this engine — update the engine"
        else:
            tag = "unstamped" if v == 0 else "older"
        print(f"  v{v}: {counts[v]:4}  ({tag})")
    for p in unparsed:
        print(f"  no frontmatter: {rel(p)}")
    if a.apply:
        print(f"migrated {moved} record(s) to v{SCHEMA_VERSION}")
    elif sum(n for v, n in counts.items() if v < SCHEMA_VERSION):
        print("run with --apply to migrate them")
    newer = sum(n for v, n in counts.items() if v > SCHEMA_VERSION)
    return 1 if newer or unparsed else 0


if __name__ == "__main__":
    sys.exit(main())
