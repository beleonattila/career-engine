#!/usr/bin/env python3
"""
level_sweep.py — retire leads that fail Gate 4 (level) out of the active working set.

Gate 4 rejects roles above the user's level — the title words in
user/profile/search_terms.toml [level] (via ats_sweep.over_level()). It was added on
2026-08-09 on this evidence:

  * 57 senior/principal leads had been collected and NOT ONE was ever applied to;
  * all 8 real applications went to 6 PhD calls and 2 unmarked IC roles;
  * backtested over the whole vault the gate drops 61 of 175 leads and loses 0 of 8 applications.

A high score does not contradict that — and since 2026-08-17 the scoring system says so itself.
The old blended `fit_score` gave "Senior / Lead Scientist — Computational Protein Design" an 83
while it was never a realistic application; the record now reads `career_fit 92 · skill_match 55
· level_fit reach`, which is the same fact stated honestly instead of averaged away.

`career_fit` measures desirability and nothing else, so an on-direction senior role SHOULD score
high there — that is not an argument against this sweep. `level_fit` is the field that speaks to
attainability, and this script and that badge are two implementations of the same judgement.
Never gate this sweep on `career_fit`.

Gate 4 applies to new collections; this script applies it once to the backlog. Same guards and
conventions as expire_sweep.py:

  * the record is NEVER deleted — dedup_check.py globs positions/{open,applied,closed}, so an
    erased lead would simply be re-collected on the next search, and the miss telemetry needs
    the history;
  * anything applied/sent/interviewing/offer is left exactly where it is;
  * positions/applied/ is never touched at all;
  * PhD and doctoral calls are exempt — in a PhD advert a "Senior Researcher" line names the
    supervisor, not the vacancy, and Nordic/German academic titles do this constantly.

The gate's boundary is a judgement that can move -- `senior` was inside it for a few hours on
2026-08-09 and then taken back out -- so every closure records `prior_status:` and `--undo`
re-tests the closed set against the *current* gate and restores whatever now passes.

Usage:
    python engine/tools/level_sweep.py --dry-run     # show what would move, change nothing
    python engine/tools/level_sweep.py               # apply
    python engine/tools/level_sweep.py --undo        # restore leads that no longer fail the gate
    python engine/tools/level_sweep.py --undo --dry-run
"""

import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ats_sweep import over_level          # one definition of "over-level", shared with the sweep

from paths import REPO, WORKSPACE as ROOT  # noqa: E402 — records are relative to user/workspace/
OPEN, CLOSED = ROOT / "positions" / "open", ROOT / "positions" / "closed"
TODAY = dt.date.today()


# A lead in any of these states is an active application, not a stale lead.
PROTECTED = {"applied", "sent", "interviewing", "offer", "cv_generated"}


def field(text, name):
    m = re.search(rf"^{name}:\s*(.*)$", text, re.M)
    return (m.group(1).strip().strip('"\'') if m else "")


def head_status(name):
    """`status:` for this file at the last commit, if git still has it. Best-effort only."""
    for d in ("open", "applied", "closed"):
        r = subprocess.run(["git", "show", f"HEAD:./positions/{d}/{name}"],
                           capture_output=True, text=True, cwd=str(ROOT))
        if r.returncode == 0:
            m = re.search(r"^status:\s*(\S+)", r.stdout, re.M)
            return m.group(1) if m else None
    return None


def undo(dry):
    """Restore gate4-closed leads that the CURRENT gate would let through.

    Re-tests rather than blindly reversing, so narrowing the gate restores exactly the leads the
    narrowing was about and leaves the rest closed.
    """
    restored, guessed = [], []
    for p in sorted(CLOSED.glob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        if field(text, "closed_reason") != "gate4_level":
            continue
        title = field(text, "role_title")
        if over_level(title):
            continue                       # still fails the gate — leave it closed

        prior = field(text, "prior_status")
        if not prior:
            prior = head_status(p.name)
            if prior:
                guessed.append((p.name, f"git HEAD: {prior}"))
            else:
                prior = "evaluating"
                guessed.append((p.name, "defaulted to 'evaluating' — not in git HEAD"))

        dest = OPEN / p.name
        if dest.exists():
            print(f"    SKIP {p.name}: already present in open/")
            continue

        new = re.sub(r"^status:.*$", f"status: {prior}", text, count=1, flags=re.M)
        for f in ("prior_status", "closed_reason", "closed_on"):
            new = re.sub(rf"^{f}:.*\n", "", new, count=1, flags=re.M)
        if not dry:
            p.write_text(new, encoding="utf-8")
            shutil.move(str(p), str(dest))
        restored.append((p.name, title, prior))

    tag = "[dry-run] would restore" if dry else "restored"
    print(f"{tag} {len(restored)} lead(s) -> positions/open/ "
          f"(they no longer fail Gate 4)")
    for name, title, prior in sorted(restored, key=lambda x: x[1].lower()):
        print(f"    [{prior}] {title[:58]}")
    if guessed:
        print(f"\n{len(guessed)} had no prior_status recorded, so it was recovered:")
        for name, how in guessed:
            print(f"    {how:<44} {name}")
    still = sum(1 for p in CLOSED.glob("*.md")
                if field(p.read_text(encoding="utf-8", errors="replace"),
                         "closed_reason") == "gate4_level")
    if dry:
        still -= len(restored)             # they have not moved yet, so do not count them twice
    print(f"\n{still} lead(s) {'would remain' if dry else 'remain'} closed as gate4_level.")
    if dry:
        print("(dry run — nothing was written or moved)")


def main():
    dry = "--dry-run" in sys.argv
    if not OPEN.is_dir():
        sys.exit(f"missing {OPEN}")
    CLOSED.mkdir(parents=True, exist_ok=True)
    if "--undo" in sys.argv:
        undo(dry)
        return

    moved, protected, bad, untitled = [], [], [], []

    for p in sorted(OPEN.glob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        title = field(text, "role_title")
        if not title:
            untitled.append(p.name)       # cannot judge a level without a title — leave it
            continue
        if not over_level(title):
            continue

        status, app = field(text, "status").lower(), field(text, "app_status").lower()
        if status in PROTECTED or app in PROTECTED:
            protected.append((p.name, title, status or app))
            continue

        dest = CLOSED / p.name
        if dest.exists():
            bad.append(f"{p.name}: already present in closed/, left in open/")
            continue

        # `prior_status` is what makes --undo exact rather than a guess.
        stamp = (f"status: closed\nprior_status: {status or 'evaluating'}\n"
                 f"closed_reason: gate4_level\nclosed_on: {TODAY.isoformat()}")
        new = text
        if re.search(r"^status:.*$", new, re.M):
            new = re.sub(r"^status:.*$", "status: closed", new, count=1, flags=re.M)
        else:
            new = re.sub(r"^---\s*$", "---\nstatus: closed", new, count=1, flags=re.M)
        if not re.search(r"^closed_reason:", new, re.M):
            new = re.sub(r"^status: closed$", stamp, new, count=1, flags=re.M)

        if not dry:
            p.write_text(new, encoding="utf-8")
            shutil.move(str(p), str(dest))
        moved.append((p.name, title))

    tag = "[dry-run] would retire" if dry else "retired"
    if moved:
        print(f"{tag} {len(moved)} over-level lead(s) -> positions/closed/ "
              f"(status: closed, closed_reason: gate4_level)")
        for name, title in sorted(moved, key=lambda x: x[1].lower()):
            print(f"    {title[:62]:<63} {name}")
    else:
        print(f"{tag} 0 leads — nothing in positions/open/ fails Gate 4")

    if protected:
        print(f"\nkept ({len(protected)}) — over-level but an active application, never touched:")
        for name, title, st in protected:
            print(f"    [{st}] {title[:56]}")
    if untitled:
        print(f"\nkept ({len(untitled)}) — no role_title, level not judgeable:")
        for name in untitled:
            print(f"    {name}")
    if bad:
        print(f"\n{len(bad)} problem(s):")
        for b in bad:
            print(f"    {b}")
    if dry:
        print("\n(dry run — nothing was written or moved)")


if __name__ == "__main__":
    main()
