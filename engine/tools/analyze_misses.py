#!/usr/bin/env python3
"""
analyze_misses.py — attribute recall failures from search telemetry.

The unknown-N problem: we cannot know how many matching posts exist on the internet, so we cannot
compute recall directly. But we do not need to. When run N finds a post that was already live
during run K, run K missed it -- and the log says why. Late discoveries are the ground truth.

This script does the DETERMINISTIC part: join each find against the runs that should have caught
it, and assign a cause code. It deliberately does not editorialise -- feed its output to Opus for
the judgement calls and the skill recommendations.

Usage:
    python engine/tools/analyze_misses.py                 # report to stdout + logs/analysis/
    python engine/tools/analyze_misses.py --since 2026-10-02         # only misses BY runs started then or later
    python engine/tools/analyze_misses.py --found-since 2026-07-01   # only leads FOUND on or after that date
    python engine/tools/analyze_misses.py --json          # machine-readable, for an LLM pass
    python engine/tools/analyze_misses.py --min-fit 75    # only leads that became a record at career_fit >= 75

`--since` is how a fix is judged: it keeps every lead but counts only the misses made by runs that
started at or after the moment (a date, or a date and time — UTC, the zone `started` is logged in).
Added 2026-10-10: the cumulative histogram over 52 runs was still dominated by runs made before the
2026-10-01 fixes, and the two runs blamed for skipping channels had started nine hours before those
fixes were committed. `--found-since` is the older filter (it was `--since` until then): it narrows
the leads, but still charges each one to every earlier run, fixed or not. Runs started after the
newest find cannot have an attributable miss yet — a fix needs later runs before it can be judged.

Every lead is joined to the vault record it became (log_run.match_outcome), so each carries its
career_fit, and the report always prints a second histogram over strong leads alone. Added
2026-10-01: over all leads the top causes were AGE_EXCLUDED and QUERY_GAP; over leads scoring 75+
they were SOURCE_INCOMPLETE and GEO_GAP. Counting a missed data-analyst role the same as a missed
band-A design role had pointed the fixes the wrong way.
"""

import datetime as dt
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from paths import REPO, WORKSPACE as ROOT, setting  # noqa: E402 — records are relative to user/workspace/
STRONG_FIT = setting("thresholds.on_direction")
LOG = ROOT / "logs" / "search_runs.jsonl"

# Shared with the dedup guard on purpose: "the same lead" must mean the same thing to the thing
# that prevents duplicates and to the thing that measures recall, or the second will report the
# first's failures as misses.
try:
    from dedup_check import canon_url, same_employer, role_key, lead_key
except ImportError:                                       # analysed outside the vault
    canon_url = same_employer = None

    def role_key(role):
        return re.sub(r"[^a-z0-9]+", "-", str(role or "").lower()).strip("-")

    def lead_key(find, seen):                             # org+role only, no URL/alias matching
        return (str(find.get("org") or ""), role_key(find.get("role")), "")
OUTDIR = ROOT / "logs" / "analysis"
# Channels with no recency filter on any pass (search-positions-common.md: the ATS endpoints
# "need no age filter at all"), so AGE_EXCLUDED is never attributed to them.
NO_AGE_FILTER = {"ats_sweep"}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# country -> the linkedin `location=` tokens that would surface it. "European Union" does NOT
# include CH/NO/UK/IS (measured 2026-07-29), which is why GEO_GAP is attributable at all.
EU = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT",
      "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}
GEO_TOKEN = {"GB": "United Kingdom", "CH": "Switzerland", "NO": "Norway", "IS": "Iceland",
             "DK": "Denmark", "SE": "Sweden", "DE": "Germany", "NL": "Netherlands",
             "FR": "France", "BE": "Belgium", "AT": "Austria", "ES": "Spain", "IT": "Italy",
             "FI": "Finland", "IE": "Ireland", "PL": "Poland"}


def d(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def moment(s):
    """'YYYY-MM-DD' or an ISO timestamp -> naive UTC datetime (a bare date is its midnight)."""
    s = str(s or "").strip().replace("Z", "")
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if t.tzinfo:
        t = t.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return t


def load():
    if not LOG.exists():
        sys.exit(f"no telemetry yet at {LOG.relative_to(REPO).as_posix()} — run log_run.py first")
    runs = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"skipping malformed log line: {line[:80]}...", file=sys.stderr)
    runs.sort(key=lambda r: r.get("started", ""))
    return runs


def geo_covered(chan, country):
    """Would this run's linkedin geo loop have surfaced a post in `country`?"""
    geos = set(chan.get("geos") or [])
    if not country:
        return True                       # unknowable -> do not blame geography
    if country in EU and "European Union" in geos:
        return True
    tok = GEO_TOKEN.get(country)
    return bool(tok and (tok in geos or country in geos))


def query_covered(chan, role, org):
    """Did any logged query plausibly match this role's wording?"""
    qs = chan.get("queries") or []
    if not qs:
        return False
    words = set(re.split(r"[^a-z0-9]+", f"{role} {org}".lower())) - {""}
    for q in qs:
        qw = set(re.split(r"[^a-z0-9]+", q.lower())) - {""}
        if qw & words:
            return True
    return False


def was_screened(run, org, role):
    for s in run.get("screened", []):
        if s.get("org") == org and s.get("role") == role:
            return s
    return None


_SWEEPS = {}


def sweep_rows(run_id):
    """The archived ATS sweep of one run as (urls -> tier, [(org, title tokens, tier)]), or None.

    Archived by log_run.py since 2026-10-10 (three earlier runs backfilled from the user repo's
    history). A run with no archive falls back to SOURCE_INCOMPLETE, as before.
    """
    if run_id in _SWEEPS:
        return _SWEEPS[run_id]
    try:
        from log_run import sweep_archive_path
        path = sweep_archive_path(run_id)
    except Exception:                                         # analysed outside the vault
        path = None
    rows = None
    if path is not None and path.exists():
        urls, titled = {}, []
        for line in path.read_text(encoding="utf-8").splitlines()[1:]:
            f = line.split("\t")
            if len(f) < 9:
                continue
            tier, org, title, url = f[0], f[3], f[6], f[8].strip()
            if url:
                urls[canon_url(url) if canon_url else url.lower()] = tier
            titled.append((org, set(role_key(title).split("-")) - {""}, tier))
        rows = (urls, titled)
    _SWEEPS[run_id] = rows
    return rows


def sweep_tier(find, run):
    """The tier `run`'s sweep gave this lead, or None if the sweep did not return it (or is
    not archived). Matched on the URL, else on employer plus every title word in the role slug
    (the slug adds a city: `software-engineer-product-london` for "Software Engineer, Product")."""
    rows = sweep_rows(run.get("run_id"))
    if not rows:
        return None
    urls, titled = rows
    u = find.get("url") or ""
    if u:
        hit = urls.get(canon_url(u) if canon_url else u.lower())
        if hit is not None:
            return hit
    role_toks = set(role_key(find.get("role")).split("-")) - {""}
    for org, toks, tier in titled:
        if org == find.get("org") and len(toks) >= 2 and toks <= role_toks:
            return tier
    return None


def attribute(find, run):
    """Why did `run` not collect `find`? Returns (code, detail)."""
    posted, started = d(find.get("posted")), d(run.get("started"))
    if not posted or not started:
        return None
    if posted > started:
        return ("NOT_YET_POSTED", "")

    scr = was_screened(run, find["org"], find["role"])
    if scr:
        return ("GATED_OUT", f"rejected as {scr.get('reason')}")

    ch_key = find.get("channel")
    chan = next((c for c in run.get("channels", []) if c.get("key") == ch_key), None)
    if chan is None:
        return ("CHANNEL_NOT_RUN", f"{ch_key} not attempted")
    if chan.get("status") == "skipped":
        return ("CHANNEL_SKIPPED", f"{ch_key} skipped: {chan.get('reason', 'unstated')}")
    if chan.get("status") == "failed":
        return ("CHANNEL_FAILED", f"{ch_key} failed")

    # The fast pass's window is each source's own recency filter (LinkedIn's f_TPR). The ATS
    # sweep has none -- it enumerates every board, however old the posting -- so a sweep miss is
    # never an age miss. Charging it as one hid 104 sweep events (2026-10-10), among them the
    # three Adaptyv postings that sat untiered in the 10-01 sweeps.
    if run.get("mode") == "fast" and ch_key not in NO_AGE_FILTER:
        w = run.get("age_window_days")
        if isinstance(w, int) and (started - posted).days > w:
            return ("AGE_EXCLUDED", f"{(started - posted).days}d old vs {w}d window")

    if ch_key == "linkedin":
        if not geo_covered(chan, find.get("country")):
            return ("GEO_GAP", f"{find.get('country')} not in {sorted(chan.get('geos') or [])}")
        if not query_covered(chan, find.get("role", ""), find.get("org", "")):
            return ("QUERY_GAP", "no logged query matched the role wording")

    # The sweep enumerates every board in full, so "reached but not returned" is the wrong
    # reading when the row is in that run's output: the source returned it and triage hid it.
    if ch_key == "ats_sweep":
        tier = sweep_tier(find, run)
        if tier == "-":
            return ("UNTIERED", "in the sweep output as tier '-', which is not printed")
        if tier:
            return ("UNSCREENED", f"printed by the sweep as tier {tier}, but neither screened "
                                  f"nor collected")

    return ("SOURCE_INCOMPLETE", f"{ch_key} was reached and covered, yet did not return it")


def fit_index():
    """find -> career_fit of the vault record it became, via log_run's matcher (None if none)."""
    try:
        from log_run import vault_outcomes, match_outcome
    except Exception:                                         # analysed outside the vault
        return lambda find: None
    idx = vault_outcomes()

    def fit(find):
        info = match_outcome(find, idx)
        return info["fit"] if info else None
    return fit


def histogram(leads):
    c = Counter(m["cause"] for x in leads for m in x["misses"])
    return c, sum(c.values())


def main():
    argv = sys.argv[1:]

    def opt(flag, parse):
        if flag not in argv:
            return None
        i = argv.index(flag)
        val = parse(argv[i + 1]) if i + 1 < len(argv) else None
        if val is None:
            sys.exit(f"{flag} needs a date (YYYY-MM-DD) or timestamp (YYYY-MM-DDTHH:MM)")
        return val

    since = opt("--since", moment)                 # misses made by runs started >= this
    found_since = opt("--found-since", d)          # leads found on or after this date
    as_json = "--json" in argv
    min_fit = int(argv[argv.index("--min-fit") + 1]) if "--min-fit" in argv else None
    fit_of = fit_index()

    runs = load()
    causes = Counter()
    per_lead, by_channel = [], defaultdict(Counter)
    # A lead re-collected under a slug variant is not a late discovery -- it is a dedup failure,
    # and counting it as a miss makes the search look worse at exactly the moment it repeated
    # itself. Measured 2026-08-08: cbmr-ku (collected 07-29, re-collected 08-08 as `cbmr`) was
    # reported as a 68-day-lag lead "missed by 13 runs" while sitting in the vault the whole
    # time. Keep only the FIRST collection of each lead; report the rest separately.
    first_seen, redundant = {}, []
    n_first = n_dated = 0

    for i, run in enumerate(runs):
        for find in run.get("collected", []):
            # Identity is registered BEFORE the posting-date check: a first collection with no
            # `posted` still makes a later re-collection redundant, and 6 of 31 logged collects
            # carry no date. Checking dates first would let those slip back in as "misses".
            key = lead_key(find, first_seen)
            if key in first_seen:
                redundant.append((run.get("run_id"), find.get("org"), find.get("role"),
                                  first_seen[key]))
                continue
            first_seen[key] = run.get("run_id")
            n_first += 1
            posted, found = d(find.get("posted")), d(run.get("started"))
            if not posted or not found:
                continue
            n_dated += 1
            fit = fit_of(find)
            if min_fit is not None and (fit is None or fit < min_fit):
                continue
            if found_since and found < found_since:
                continue
            lag = (found - posted).days
            misses = []
            this_start = moment(run.get("started"))
            for prior in runs[:i]:
                p_start = moment(prior.get("started")) or dt.datetime.min
                if since and p_start < since:
                    continue
                # The other track of the same search starts in the same second. It ran beside
                # this one, not before it, so it cannot have missed what this one found.
                if this_start and p_start >= this_start:
                    continue
                res = attribute(find, prior)
                if not res or res[0] == "NOT_YET_POSTED":
                    continue
                misses.append({"run_id": prior.get("run_id"), "mode": prior.get("mode"),
                               "cause": res[0], "detail": res[1]})
                causes[res[0]] += 1
                by_channel[find.get("channel", "?")][res[0]] += 1
            per_lead.append({
                "org": find["org"], "role": find["role"], "posted": str(posted),
                "found": str(found), "lag_days": lag, "channel": find.get("channel"),
                "country": find.get("country"), "career_fit": fit,
                "missed_by_n_runs": len(misses),
                "misses": misses,
            })

    per_lead.sort(key=lambda x: -x["missed_by_n_runs"])
    total = sum(causes.values())
    strong = [x for x in per_lead if x["career_fit"] is not None and x["career_fit"] >= STRONG_FIT]
    s_causes, s_total = histogram(strong)
    in_window = [r for r in runs
                 if not since or (moment(r.get("started")) or dt.datetime.min) >= since]
    report = {"runs_logged": len(runs), "leads_analysed": len(per_lead),
              "total_attributed_misses": total,
              "since": since.isoformat(timespec="minutes") if since else None,
              "runs_in_window": [r.get("run_id") for r in in_window] if since else None,
              "found_since": str(found_since) if found_since else None,
              "min_fit": min_fit,
              "dated_first_collections": [n_dated, n_first],
              "cause_histogram": dict(causes.most_common()),
              "strong_leads": len(strong), "strong_threshold": STRONG_FIT,
              "strong_cause_histogram": dict(s_causes.most_common()),
              "by_channel": {k: dict(v) for k, v in by_channel.items()},
              "redundant_collections": [
                  {"run_id": r, "org": o, "role": ro, "first_collected_in": f}
                  for r, o, ro, f in redundant],
              "leads": per_lead}

    OUTDIR.mkdir(parents=True, exist_ok=True)
    stamp = runs[-1].get("run_id", "latest") if runs else "latest"
    # A windowed report must not overwrite the cumulative one written from the same log.
    if since:
        stamp = f"{stamp}_since{since:%Y%m%dT%H%M}"
    (OUTDIR / f"misses_{re.sub(r'[^0-9A-Za-z-]', '', str(stamp))}.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")

    if as_json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
        return

    print(f"=== miss attribution over {len(runs)} logged run(s)"
          + (f", leads at career_fit >= {min_fit}" if min_fit is not None else "")
          + (f", leads found since {found_since}" if found_since else "") + " ===")
    if since:
        print(f"misses counted only for runs started at or after {since:%Y-%m-%d %H:%M} UTC: "
              f"{len(in_window)} run(s)"
              + (f" ({', '.join(r.get('run_id', '?') for r in in_window)})" if in_window else ""))
        last_find = max((d(r.get("started")) for r in runs if r.get("collected")), default=None)
        if in_window and last_find:
            untested = [r.get("run_id") for r in in_window
                        if (d(r.get("started")) or last_find) >= last_find]
            if untested:
                print(f"  not yet testable (no later run has found anything): {', '.join(untested)}")
    print(f"posting dates: {n_dated} of {n_first} first collections are dated -- "
          f"only those can be measured")
    if redundant:
        print(f"{len(redundant)} redundant collection(s) excluded — a lead already in the vault, "
              f"re-collected under a different slug. These are dedup failures, not misses:")
        for r, o, ro, f in redundant:
            print(f"    {r}  {o}/{ro[:40]}  (first collected in {f})")
        print()
    lags = [x["lag_days"] for x in per_lead]
    if lags:
        lags_s = sorted(lags)
        med = lags_s[len(lags_s) // 2]
        print(f"lag (posted -> found): median {med}d, max {max(lags)}d, n={len(lags)}")
    if not total:
        print("\nNo attributable misses. Either recall is clean over this window, or too few "
              "runs are logged for a post to have been live across two of them.")
    else:
        print(f"\n{total} attributed miss-events (one lead can be missed by several runs):")
        for c, n in causes.most_common():
            print(f"  {c:<20} {n:>4}  {100 * n / total:>5.1f}%")
        if s_total and min_fit is None:
            print(f"\non strong leads only (career_fit >= {STRONG_FIT}: {len(strong)} leads, "
                  f"{s_total} miss-events) -- the histogram to act on:")
            for c, n in s_causes.most_common():
                print(f"  {c:<20} {n:>4}  {100 * n / s_total:>5.1f}%")
        elif min_fit is None:
            print(f"\non strong leads only (career_fit >= {STRONG_FIT}): no miss-events"
                  + (" in this window" if since else ""))
        print("\nworst leads:")
        for x in per_lead[:8]:
            if not x["missed_by_n_runs"]:
                continue
            cs = ", ".join(sorted({m["cause"] for m in x["misses"]}))
            print(f"  {x['lag_days']:>4}d lag | missed by {x['missed_by_n_runs']} run(s) | "
                  f"{x['org']}/{x['role'][:34]} | {cs}")
    print(f"\nwritten to {OUTDIR.relative_to(REPO).as_posix()}/  — feed the JSON to Opus for the why")


if __name__ == "__main__":
    main()
