#!/usr/bin/env python3
"""
expire_sweep.py — retire past-deadline leads out of the active working set.

Sets `status: expired`, stamps `expired_on`, and moves the file from positions/open/ to
positions/closed/. The record is NEVER deleted:

  * the position template states leads are never deleted -- the record stays for history;
  * dedup_check.py globs positions/{open,applied,closed}, so an erased lead would simply be
    re-collected on the next search;
  * the miss-attribution telemetry needs the history to attribute recall failures.

"Removed" therefore means removed from rotation and from the dashboard's active tabs, not
removed from disk.

Guards:
  * strictly-before-today only -- a lead is NOT expired on its deadline day (CLAUDE.md rule)
  * `deadline: null` never expires; absence of a deadline is not evidence of one having passed
  * anything applied/sent/interviewing is left where it is -- you applied before the deadline
    and the application is still live
  * positions/applied/ is never touched at all

AGE RETIREMENT -- STALE_DAYS (set 2026-08-29 on the user's explicit instruction)
-----------------------------------------------------------------------------
A lead with `deadline: null` and more than STALE_DAYS days since `created` is retired
to positions/closed/ **on age alone**, stamped `expired_reason: stale_no_deadline`. STALE_DAYS is
`thresholds.stale_days` in user/settings.toml (45 when the rule was introduced).

>>> THIS DELIBERATELY OVERRIDES THE STANDING RULE. <<<
CLAUDE.md says a position is expired ONLY on a deadline strictly before today or a posting
confirmed removed, because neither a 200 nor a 404 proves anything (engine/docs/LINK_HEALTH.md:
20 of 50 "healthy" leads were dead behind HTTP 200s; a live board also renders empty to a
bot). Age is likewise not evidence a posting closed -- some of these will still be open.
The user chose this trade on 2026-08-29 after `biohub_computational-biologist-cellxstate_2026-06`
was found in open/ at 83 days: a smaller, colder active set is preferred over an accurate but
unmanageable one. Do not silently revert it; it is a decision, not a bug.

Why this stayed safe:
  * nothing is deleted -- records move open/ -> closed/, exactly as a deadline expiry does;
  * `expired_reason: stale_no_deadline` marks every age-retirement, so the whole set can be
    listed and reversed with one grep. A deadline expiry has no such field;
  * a dated Notes line on each record says it was retired on age and NOT confirmed dead;
  * `dedup_check.py` globs positions/{open,applied,closed}, so a retired lead is not
    re-collected as if it were new;
  * `--keep-stale` disables age retirement entirely for one run.

To undo: `grep -l "expired_reason: stale_no_deadline" positions/closed/*.md`, then move back
and reset `status:`/`expired_on:`/`expired_reason:`.

VERIFIED-RECENTLY EXEMPTION -- VERIFIED_DAYS (added 2026-11-18)
---------------------------------------------------------------
A deadline-less lead confirmed live within VERIFIED_DAYS days is KEPT, and reported under
"kept -- verified live recently" instead of being retired on age.

Why this is a refinement and not a reversal of the 2026-08-29 decision: age retirement fires
because a deadline-less lead carries no evidence either way, and age is the only handle there
is. A positive liveness verdict IS that evidence. When it exists and is fresh, the premise the
rule rests on does not hold, so the rule has nothing to say. The trade the user chose -- a
smaller, colder active set over an accurate but unmanageable one -- is untouched for every lead
nobody has checked, which is nearly all of them.

The case that produced it: `latent-labs_member-of-technical-staff_2026-10` (domain_fit 98,
method_fit 95) was retired at 46 days, then found fully live the same day -- the ad rendered
with an Apply button and was still listed on the employer's board. Reviving it put it straight
back over the threshold, so the next sweep would have retired it again, with no way to record
that it had been checked.

Three guards keep this narrow, so link_check.py cannot quietly exempt the vault:
  * only `url_status: working` counts. unverified / unresolved / unchecked / dead do not;
  * a LinkedIn `working` NEVER counts -- stale_verdict() rejects it, because link_check.py has
    been unable to produce that verdict for LinkedIn since 2026-08-16;
  * VERIFIED_DAYS is deliberately much shorter than STALE_DAYS (14 vs 45 at introduction), so
    the check has to be recent and deliberate. A lead verified once at collection still ages
    out on schedule.

`--verified-days -1` turns the exemption off for one run, restoring pre-2026-11-18 behaviour.

Also reported (never retired): leads carrying `url_status: working` on a linkedin.com URL --
a verdict link_check.py has been unable to produce since 2026-08-16, so any survivor predates
that fix and means nothing.

Usage:
    python engine/tools/expire_sweep.py --dry-run          # show what would move, change nothing
    python engine/tools/expire_sweep.py                    # apply
    python engine/tools/expire_sweep.py --stale-days 90    # widen/narrow the age threshold for one run
    python engine/tools/expire_sweep.py --keep-stale       # deadline expiry only; report age, retire none
    python engine/tools/expire_sweep.py --verified-days 7  # narrow the verified-recently exemption
    python engine/tools/expire_sweep.py --verified-days -1 # disable the exemption for one run
"""

import datetime as dt
import re
import shutil
import sys
from pathlib import Path

from paths import REPO, WORKSPACE as ROOT, setting  # noqa: E402 — records are relative to user/workspace/
OPEN, CLOSED = ROOT / "positions" / "open", ROOT / "positions" / "closed"
TODAY = dt.date.today()


# A lead in any of these states is an active application, not a stale lead.
PROTECTED = {"applied", "sent", "interviewing", "offer"}

# Days since `created` after which a deadline-less lead is RETIRED on age alone.
# Set to 45 and made a retirement trigger on 2026-08-29 at the user's explicit instruction --
# see the AGE RETIREMENT note in the module docstring for what this overrides and how to undo it.
# The number is personal, so it lives in user/settings.toml; dashboard.py reads the same key.
STALE_DAYS = setting("thresholds.stale_days")

# Days within which a POSITIVE liveness check exempts a deadline-less lead from age retirement.
# Deliberately far shorter than STALE_DAYS: the exemption is for a deliberate, recent check, not
# for the routine stamp link_check.py leaves on every lead it sweeps. See the VERIFIED-RECENTLY
# note in the module docstring for why this refines the age rule rather than reverting it.
VERIFIED_DAYS = setting("thresholds.verified_days")


def field(text, name):
    m = re.search(rf"^{name}:\s*(.*)$", text, re.M)
    return (m.group(1).strip().strip('"\'') if m else "")


def parse_deadline(v):
    if v in ("", "null", "~", "None", "unknown"):
        return None
    try:
        return dt.date.fromisoformat(v[:10])
    except ValueError:
        return None


# `created` uses the same encoding as `deadline`, so the same parser answers "how old is this
# lead?" as well as "has its deadline passed?".
parse_date = parse_deadline


def age_days(text):
    """Days since `created`; None when the field is missing or unparseable."""
    c = parse_date(field(text, "created"))
    return (TODAY - c).days if c else None


def stale_verdict(text):
    """
    True when this lead carries a url_status the current link_check.py cannot emit.

    link_check.py has not returned ALIVE for a LinkedIn URL since 2026-08-16: LinkedIn renders
    its expiry banner client-side, so an unauthenticated fetch of a dead posting is byte-for-byte
    indistinguishable from a live one. Any `url_status: working` on a linkedin.com lead was
    therefore written by the superseded version of the tool and proves nothing.
    """
    return ("linkedin.com" in field(text, "url").lower()
            and field(text, "url_status").lower() == "working")


def verified_live(text, window):
    """
    Days since this lead was confirmed live, when that was recent enough to exempt it from
    age retirement. None when there is no such evidence.

    Age retirement fires because a deadline-less lead carries no evidence either way. A
    positive liveness verdict is that evidence, so while it is fresh, age says nothing new.
    The guards are in the module docstring: `working` only, never a LinkedIn `working`, and a
    short window. A negative `window` disables the exemption entirely.
    """
    if window < 0:
        return None
    if field(text, "url_status").lower() != "working" or stale_verdict(text):
        return None
    checked = parse_date(field(text, "url_checked"))
    if checked is None:
        return None
    days = (TODAY - checked).days
    return days if 0 <= days <= window else None


AGE_NOTE = (
    "- {date}: retired open/ -> closed/ by expire_sweep.py on **age alone** — {age} days since\n"
    "  `created`, with no deadline to expire against (threshold {thr}d, set 2026-08-29).\n"
    "  ⚠️ **This posting was NOT confirmed removed.** It may still be live. Age is not evidence a\n"
    "  posting closed; this is a deliberate trade for a smaller active set, not a verification.\n"
    "  To revive: move back to positions/open/, set `status: evaluating`, clear `expired_on` and\n"
    "  `expired_reason`, then verify the link.\n"
)


def retire(p, text, dest_dir, reason, note, dry):
    """Move a lead open/ -> closed/, stamping status, date and why. Shared by both triggers.

    `reason` lands in `expired_reason` so an age retirement is always distinguishable from a
    deadline expiry -- that field is the handle for reversing the whole set.
    """
    dest = dest_dir / p.name
    if dest.exists():
        return f"{p.name}: already present in closed/, left in open/"

    new = text
    if re.search(r"^status:.*$", new, re.M):
        new = re.sub(r"^status:.*$", "status: expired", new, count=1, flags=re.M)
    else:
        new = re.sub(r"^---\s*$", "---\nstatus: expired", new, count=1, flags=re.M)
    if not re.search(r"^expired_on:", new, re.M):
        new = re.sub(r"^status: expired$",
                     f"status: expired\nexpired_on: {TODAY.isoformat()}",
                     new, count=1, flags=re.M)
    if reason and not re.search(r"^expired_reason:", new, re.M):
        new = re.sub(r"^expired_on: .*$",
                     lambda m: m.group(0) + f"\nexpired_reason: {reason}",
                     new, count=1, flags=re.M)
    if note:
        if re.search(r"^## Notes\s*$", new, re.M):
            new = re.sub(r"^## Notes\s*$", "## Notes\n" + note, new, count=1, flags=re.M)
        else:
            new = new.rstrip() + "\n\n## Notes\n" + note

    if not dry:
        p.write_text(new, encoding="utf-8")
        shutil.move(str(p), str(dest))
    return None


def main():
    # This sweep moves records by default, so an unknown flag (a typo, --help) must stop it.
    args = sys.argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        return
    valued = ("--stale-days", "--verified-days")
    unknown = [a for i, a in enumerate(args)
               if a not in ("--dry-run", "--keep-stale") + valued
               and not (i and args[i - 1] in valued)]
    if unknown:
        sys.exit(f"unknown option {unknown[0]!r}; nothing changed. Options: --dry-run, "
                 "--keep-stale, --stale-days N, --verified-days N (see --help)")
    dry = "--dry-run" in sys.argv
    keep_stale = "--keep-stale" in sys.argv
    stale_days = STALE_DAYS
    if "--stale-days" in sys.argv:
        try:
            stale_days = int(sys.argv[sys.argv.index("--stale-days") + 1])
        except (IndexError, ValueError):
            sys.exit("--stale-days needs an integer, e.g. --stale-days 90")
    verified_days = VERIFIED_DAYS
    if "--verified-days" in sys.argv:
        try:
            verified_days = int(sys.argv[sys.argv.index("--verified-days") + 1])
        except (IndexError, ValueError):
            sys.exit("--verified-days needs an integer, e.g. --verified-days 7 (-1 disables)")
    if not OPEN.is_dir():
        sys.exit(f"missing {OPEN}")
    CLOSED.mkdir(parents=True, exist_ok=True)

    moved, protected, kept_today, bad = [], [], [], []
    stale, unproven, aged, verified = [], [], [], []

    for p in sorted(OPEN.glob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        dl = parse_deadline(field(text, "deadline"))
        status = field(text, "status").lower()
        app = field(text, "app_status").lower()
        active = status in PROTECTED or app in PROTECTED

        # A verdict the current link_check.py cannot produce, on a lead of any age. Reported
        # separately because it is a data-integrity problem, not an ageing problem.
        if stale_verdict(text) and not active:
            unproven.append((p.name, field(text, "url_checked") or "never"))

        if dl is None:
            # No deadline: the deadline test can never fire, so age is the only handle there is.
            # Retiring on it overrides the CLAUDE.md rule by explicit instruction -- see the
            # AGE RETIREMENT note at the top of this file.
            age = age_days(text)
            if age is None or age <= stale_days or active:
                continue
            # Confirmed live recently: the evidence age stands in for actually exists, so the
            # age rule has nothing to say about this lead. Reported, never silent.
            seen = verified_live(text, verified_days)
            if seen is not None:
                verified.append((p.name, age, seen, field(text, "domain_fit"),
                                 field(text, "skill_match")))
                continue
            row = (p.name, age, field(text, "domain_fit"),
                   field(text, "skill_match"), field(text, "url_status") or "unchecked")
            if keep_stale:
                stale.append(row)          # --keep-stale: report, do not move
                continue
            err = retire(p, text, CLOSED, "stale_no_deadline",
                         AGE_NOTE.format(date=TODAY.isoformat(), age=age, thr=stale_days), dry)
            if err:
                bad.append(err)
            else:
                aged.append(row)
            continue
        if active:
            if dl < TODAY:
                protected.append((p.name, dl, status or app))
            continue
        if dl == TODAY:
            kept_today.append((p.name, dl))       # deadline day is still live
            continue
        if dl > TODAY:
            continue

        err = retire(p, text, CLOSED, "deadline_passed", "", dry)
        if err:
            bad.append(err)
        else:
            moved.append((p.name, dl, (TODAY - dl).days))

    tag = "[dry-run] would retire" if dry else "retired"
    if moved:
        print(f"{tag} {len(moved)} past-deadline lead(s) -> positions/closed/")
        for name, dl, days in sorted(moved, key=lambda x: x[1]):
            print(f"    {dl}  ({days:>3}d ago)  {name}")
    else:
        print(f"{tag} 0 leads — nothing past its deadline in positions/open/")

    if kept_today:
        print(f"\nkept ({len(kept_today)}) — deadline is TODAY, still live:")
        for name, dl in kept_today:
            print(f"    {dl}  {name}")
    if protected:
        print(f"\nkept ({len(protected)}) — past deadline but an active application:")
        for name, dl, st in protected:
            print(f"    {dl}  status={st:<12} {name}")

    # ---- reported, never retired -------------------------------------------------
    if unproven:
        print(f"\n⚠ unproven ({len(unproven)}) — `url_status: working` on a LinkedIn URL, a verdict")
        print("  link_check.py has not been able to produce since 2026-08-16. Not evidence of life.")
        for name, checked in sorted(unproven):
            print(f"    checked={checked:<12} {name}")

    if aged:
        verb = "[dry-run] would retire" if dry else "retired"
        print(f"\n{verb} {len(aged)} lead(s) ON AGE ALONE — no deadline, over {stale_days} days old:")
        print("  ⚠ none of these was confirmed removed; some are probably still live.")
        print("  stamped `expired_reason: stale_no_deadline` — that field reverses the whole set.")
        for name, age, cf, sm, us in sorted(aged, key=lambda x: -x[1]):
            print(f"    {age:>4}d  cf={cf:>3} sm={sm:>3}  url={us:<10} {name}")

    if verified:
        print(f"\nkept ({len(verified)}) — over {stale_days} days old, but confirmed live "
              f"within {verified_days} days:")
        for name, age, seen, cf, sm in sorted(verified, key=lambda x: -x[1]):
            print(f"    {age:>4}d old  checked {seen}d ago  cf={cf:>3} sm={sm:>3}  {name}")
        print("  → age retirement stands in for missing evidence; these have it. "
              "`--verified-days -1` retires them anyway.")

    if stale:
        print(f"\n⚠ stale ({len(stale)}) — no deadline, older than {stale_days} days. "
              f"NOT retired (--keep-stale):")
        for name, age, cf, sm, us in sorted(stale, key=lambda x: -x[1]):
            print(f"    {age:>4}d  cf={cf:>3} sm={sm:>3}  url={us:<10} {name}")
        print("  → verify with: python engine/tools/link_check.py --apply   (or a browser, then /track)")

    if bad:
        print("\nwarnings:")
        for b in bad:
            print(f"    {b}")

    print(f"\nopen/ now: {len(list(OPEN.glob('*.md')))} | closed/: {len(list(CLOSED.glob('*.md')))}")


if __name__ == "__main__":
    main()
