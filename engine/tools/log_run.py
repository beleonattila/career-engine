#!/usr/bin/env python3
"""
log_run.py — validate a /search-positions run record and append it to logs/search_runs.jsonl.

Telemetry is only worth keeping if it is well-formed months later, so this validates before
appending rather than trusting hand-written JSON. See logs/SCHEMA.md.

Usage:
    python engine/tools/log_run.py run.json          # validate + append (+ archive that run's sweep TSV)
    python engine/tools/log_run.py run.json --check  # validate only, append nothing
    python engine/tools/log_run.py --stats           # summarise the existing log
    python engine/tools/log_run.py --starved         # channels not reached in the last 3 runs
    python engine/tools/log_run.py --next-queries N  # the N least-used LinkedIn queries + 1 recruiter query
"""

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from paths import REPO, WORKSPACE as ROOT, setting, user_toml  # noqa: E402 — records are relative to user/workspace/
LOG = ROOT / "logs" / "search_runs.jsonl"

# Lead identity is shared with the dedup guard and the miss analyser on purpose. When the three
# disagree, the recall report counts the guard's failures as misses while the yield table counts
# them as finds -- both were true on 2026-08-08, for the same three leads.
try:
    from dedup_check import canon_url, same_employer, role_key, lead_key
    HAVE_IDENTITY = True
except ImportError:                                  # run outside the vault
    HAVE_IDENTITY = False

STRONG_FIT = setting("thresholds.on_direction")     # career_fit counted as a strong lead
POSITION_GLOBS = ["positions/open/*.md", "positions/applied/*.md", "positions/closed/*.md"]
PROFILE_GLOBS = ["organizations/companies/*.md", "organizations/research_groups/*.md"]
FM_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")

STATUSES = {"reached", "partial", "skipped", "failed"}
MODELS = {"haiku", "sonnet", "opus", "fable"}
EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultracode"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})$")

# Closed channel vocabulary. Free-text keys make "which channel got starved" uncomputable --
# a typo silently becomes a ninth channel that has never been reached. Every key below is one
# already in use in the log as of 2026-08-08.
CHANNELS = {"ats_sweep", "linkedin", "danish_boards", "nordic_boards", "euraxess",
            "phd_portals", "company_rotation", "research_groups"}
# Which search track produced this run. Added 2026-08-18, after the first two-track run
# logged ONE blended entry: 8 collected, 27 screened, no way to tell which search did what.
# The skill track's own gate vocabulary (competency counts) never reached the log at all --
# every skip was recorded with career-gate labels (gate3d/f/h), because those were the only
# ones the schema knew. Blending two searches into one row makes the yield telemetry strictly
# worse, and it was already unsettleable at n=1-3 per cell.
#   career / skill  -- a single sub-agent's own run. What every run should be from now on.
#   mixed           -- a blended entry that cannot be attributed. Legacy only; never write it.
TRACKS = {"career", "skill", "mixed"}
STARVED_WINDOW = 3
# Was 30. Measured 2026-10-01: a deep pass yields 1.2 strong leads per run against 0.4 for a fast
# one (sonnet/medium, 9 vs 22 runs), so it is now flagged OVERDUE after a week rather than a month.
DEEP_PASS_MAX_AGE_DAYS = 7

# The LinkedIn keyword rotation is the user's: [linkedin] query_pool in
# user/profile/search_terms.toml. Read here so "which term is overdue" is a lookup rather
# than a judgement (the measurement behind that is in the file).
QUERY_POOL = user_toml("profile/search_terms.toml")["linkedin"]["query_pool"]
# One recruiter query per run, rotated separately so it never crowds the design terms out of
# --next-queries. Optional: a terms file without the key simply prints none.
RECRUITER_POOL = user_toml("profile/search_terms.toml")["linkedin"].get("recruiter_queries", [])

# The LinkedIn countries no run may skip: the first `linkedin_required` of the loop in
# user/settings.toml [geography]. A run that leaves one out is warned at log time and counted in
# --stats, because country gaps were 12% of the misses on strong leads vs 4% overall (2026-10-01).
REQUIRED_GEOS = setting("geography.linkedin_loop")[:setting("geography.linkedin_required")]

# Pages per LinkedIn query x country (guest endpoint, start=0/10/20). Since 2026-10-10 a query
# that reads fewer must say why, per combination, in `short_pages`, with one of these reasons:
#   exhausted     the last page read returned fewer than 10 cards -- there is no next page
#   no_shortlist  the last page read shortlisted nothing -- relevance has run out
#   not_run       the query was not issued in that country at all (never in a required one)
# Measured 2026-10-10: both fast tracks paged short on judgement ("relevance had fallen off"),
# the career track reading 41 of 90 pages, with nothing in the log to show it but a free-text note.
PAGES = 3
SHORT_REASONS = {"exhausted", "no_shortlist", "not_run"}

# Each run's ATS sweep output, kept under its run_id. ats_sweep.py overwrites its TSV every run,
# so without a copy "the sweep never returned it" and "it returned it in tier '-', which is not
# printed" look the same to analyze_misses.py -- and they need opposite fixes. Measured
# 2026-10-10: the six ats_sweep misses since the 10-01 fixes were all three Adaptyv postings
# sitting untiered in every sweep since at least 10-01, logged as SOURCE_INCOMPLETE.
SWEEP_LATEST = ROOT / "logs" / "ats_sweep_latest.tsv"
SWEEP_ARCHIVE = ROOT / "logs" / "ats_sweep"
# The sweep belongs to this run if it was written between a little before `started` (the
# orchestrator may sweep before spawning the tracks) and shortly after `ended`.
SWEEP_BEFORE_H, SWEEP_AFTER_MIN = 3, 30


def parse_stamp(s):
    """Parse an ISO-8601 timestamp, or return None if it is not one."""
    if not isinstance(s, str) or not STAMP.match(s):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def duration_min(rec):
    """Wall-clock minutes between started and ended, or None if either is unusable."""
    a, b = parse_stamp(rec.get("started")), parse_stamp(rec.get("ended"))
    if not a or not b:
        return None
    return round((b - a).total_seconds() / 60)


def problems(rec):
    """Return a list of validation errors; empty means valid."""
    p = []
    for f in ("run_id", "started", "ended", "mode", "model", "effort", "channels", "track"):
        if f not in rec:
            p.append(f"missing required field: {f}")
    if rec.get("mode") not in ("fast", "deep", None):
        p.append(f"mode must be 'fast' or 'deep', got {rec.get('mode')!r}")
    if rec.get("mode") == "fast" and "age_window_days" not in rec:
        p.append("fast runs must record age_window_days (needed to attribute AGE_EXCLUDED)")

    # Model + effort: a run's yield is only comparable against runs of the same capability and
    # care level, so both are required and both use a closed vocabulary.
    if "model" in rec and rec.get("model") not in MODELS:
        p.append(f"model must be one of {sorted(MODELS)}, got {rec.get('model')!r}")
    if "effort" in rec and rec.get("effort") not in EFFORTS:
        p.append(f"effort must be one of {sorted(EFFORTS)}, got {rec.get('effort')!r}")

    # Each sub-agent logs its own run. Two tracks means two entries, never one merged row --
    # otherwise "is the employability search worth its Opus bill" has no evidence behind it.
    if "track" in rec and rec.get("track") not in TRACKS:
        p.append(f"track must be one of {sorted(TRACKS)}, got {rec.get('track')!r}")
    if rec.get("track") == "mixed":
        p.append("track 'mixed' is legacy-only — a two-track run logs one entry per sub-agent")

    # Timestamps: 'ended' is required so runtime is measurable. A run that took 70 minutes and
    # one that took 12 are not the same evidence about a channel coming up empty.
    for f in ("started", "ended"):
        if f in rec and not parse_stamp(rec.get(f)):
            p.append(f"{f} must be ISO-8601 (e.g. 2026-08-07T14:05:00Z), got {rec.get(f)!r}")
    a, b = parse_stamp(rec.get("started")), parse_stamp(rec.get("ended"))
    if a and b and b < a:
        p.append(f"ended ({rec['ended']}) is before started ({rec['started']})")

    chans = rec.get("channels")
    if not isinstance(chans, list) or not chans:
        p.append("channels must be a non-empty list")
        chans = []
    for c in chans:
        if not isinstance(c, dict) or "key" not in c or "status" not in c:
            p.append(f"channel needs key+status: {c!r}")
            continue
        if c["status"] not in STATUSES:
            p.append(f"channel {c['key']}: bad status {c['status']!r} (want {sorted(STATUSES)})")
        if c["key"] not in CHANNELS:
            p.append(f"unknown channel key {c['key']!r} — use one of {sorted(CHANNELS)}, or add "
                     f"it to CHANNELS if it is genuinely a new source")
        if c["key"] == "linkedin" and c["status"] in ("reached", "partial"):
            # Without these a miss cannot be split into GEO_GAP vs QUERY_GAP vs SOURCE_INCOMPLETE.
            if not c.get("geos"):
                p.append("linkedin reached but no geos logged — miss attribution impossible")
            if not c.get("queries"):
                p.append("linkedin reached but no queries logged — miss attribution impossible")
            # The triage step. Measured 2026-08-08: 2169 logged hits became 141 screened-or-
            # collected candidates (6.5%), and how is recorded nowhere. That makes genuine
            # SOURCE_INCOMPLETE (the largest miss bucket, 35%) indistinguishable from "the run
            # skimmed past it" — the exact ambiguity `screened` exists to remove, one level up.
            for f in ("hits", "shortlisted"):
                if not isinstance(c.get(f), int):
                    p.append(f"linkedin reached but '{f}' is not an integer — the hits->"
                             f"shortlisted funnel is what makes SOURCE_INCOMPLETE attributable")
            if isinstance(c.get("hits"), int) and isinstance(c.get("shortlisted"), int) \
                    and c["shortlisted"] > c["hits"]:
                p.append(f"linkedin: shortlisted ({c['shortlisted']}) exceeds hits ({c['hits']})")
            # Paging. Three pages per query x country is the rule since 2026-10-01; without the
            # count, a run that read page 1 everywhere logs the same as one that read all three.
            if not isinstance(c.get("pages"), int):
                p.append("linkedin reached but 'pages' is not an integer — the three-page rule "
                         "cannot be checked without it")
            for s in c.get("short_pages") or []:
                if not isinstance(s, dict) or not s.get("query") or not s.get("geo") \
                        or not isinstance(s.get("pages"), int) or not 0 <= s["pages"] < PAGES:
                    p.append(f"linkedin short_pages entry needs query, geo and pages "
                             f"(0-{PAGES - 1}): {s!r}")
                elif s.get("reason") not in SHORT_REASONS:
                    p.append(f"linkedin short_pages: reason must be one of "
                             f"{sorted(SHORT_REASONS)}, got {s.get('reason')!r}")

    if "screened" not in rec:
        p.append("missing 'screened' — without rejected candidates a GATED_OUT miss is "
                 "indistinguishable from never having seen the post (see logs/SCHEMA.md)")

    for bucket in ("screened", "collected"):
        for item in rec.get(bucket, []):
            if not isinstance(item, dict):
                p.append(f"{bucket}: entries must be objects")
                continue
            if not item.get("org") or not item.get("role"):
                p.append(f"{bucket}: entry needs org+role: {item!r}")
            d = item.get("posted")
            if d is not None and not DATE.match(str(d)):
                p.append(f"{bucket}: {item.get('org')}: posted must be YYYY-MM-DD or null, "
                         f"got {d!r}")
            if bucket == "screened" and not item.get("reason"):
                p.append(f"screened: {item.get('org')}: needs a stable 'reason' code")
    return p


def linkedin_channel(rec):
    return next((c for c in rec.get("channels", []) if c.get("key") == "linkedin"
                 and c.get("status") in ("reached", "partial")), None)


def missing_required_geos(rec):
    li = linkedin_channel(rec)
    return [] if li is None else [g for g in REQUIRED_GEOS if g not in (li.get("geos") or [])]


def paging_shortfall(rec):
    """LinkedIn pages owed under the three-page rule and not accounted for, or None if unknown.

    Owed = queries x geos x PAGES. Each `short_pages` entry excuses the pages it did not read;
    whatever is still missing after that was skipped without a logged reason. Records written
    before 2026-10-10 carry no `pages` and return None rather than counting as a shortfall.
    Also returns the required countries in which a query was logged as `not_run`.
    """
    li = linkedin_channel(rec)
    if li is None or not isinstance(li.get("pages"), int):
        return None
    owed = len(li.get("queries") or []) * len(li.get("geos") or []) * PAGES
    shorts = [s for s in li.get("short_pages") or [] if isinstance(s, dict)
              and isinstance(s.get("pages"), int)]
    excused = sum(PAGES - s["pages"] for s in shorts)
    unexplained = max(0, owed - li["pages"] - excused)
    req_not_run = sorted({s.get("geo") for s in shorts
                          if s.get("reason") == "not_run" and s.get("geo") in REQUIRED_GEOS})
    return {"owed": owed, "read": li["pages"], "unexplained": unexplained,
            "required_not_run": req_not_run}


def sweep_archive_path(run_id):
    return SWEEP_ARCHIVE / (re.sub(r"[^0-9A-Za-z_-]", "", str(run_id)) + ".tsv")


def archive_sweep(rec):
    """Copy ats_sweep_latest.tsv to logs/ats_sweep/<run_id>.tsv if this run produced it.

    Returns a one-line message, or None when the run did not reach the sweep. A stale TSV (one
    written outside the run's window) is not archived: filing another run's sweep under this
    run_id would make analyze_misses.py blame this run's triage for rows it never saw.
    """
    if not any(c.get("key") == "ats_sweep" and c.get("status") in ("reached", "partial")
               for c in rec.get("channels", [])):
        return None
    a, b = parse_stamp(rec.get("started")), parse_stamp(rec.get("ended"))
    if not SWEEP_LATEST.exists() or not a or not b:
        return "warning: ats_sweep reached but no sweep output to archive -- UNTIERED misses " \
               "cannot be attributed for this run"
    written = datetime.fromtimestamp(SWEEP_LATEST.stat().st_mtime, tz=a.tzinfo)
    if not (a - timedelta(hours=SWEEP_BEFORE_H) <= written <= b + timedelta(minutes=SWEEP_AFTER_MIN)):
        return (f"warning: {SWEEP_LATEST.name} was written {written:%Y-%m-%d %H:%M}, outside this "
                f"run -- not archived, so UNTIERED misses cannot be attributed for this run")
    SWEEP_ARCHIVE.mkdir(parents=True, exist_ok=True)
    dest = sweep_archive_path(rec["run_id"])
    dest.write_bytes(SWEEP_LATEST.read_bytes())
    return f"sweep output archived to {dest.relative_to(REPO).as_posix()}"


def phd_reached(rec):
    return any(c.get("key") == "phd_portals" and c.get("status") in ("reached", "partial")
               for c in rec.get("channels", []))


def warnings(rec):
    """Coverage shortfalls that do not invalidate a record but must be seen at log time.

    Not validation errors: a time-boxed run must still be logged honestly, and rejecting it would
    only push the shortfall out of the telemetry. The same two counts appear in --stats.
    """
    w = []
    missing = missing_required_geos(rec)
    if missing:
        w.append(f"linkedin skipped required countries {missing} -- every run covers "
                 f"{REQUIRED_GEOS} (user/settings.toml [geography])")
    pg = paging_shortfall(rec)
    if pg and pg["unexplained"]:
        w.append(f"linkedin paging: {pg['read']} of {pg['owed']} pages read, {pg['unexplained']} "
                 f"short with no short_pages entry -- {PAGES} pages per query x country unless the "
                 f"last one was exhausted or shortlisted nothing (search-positions-common.md "
                 f"§Group 1)")
    if pg and pg["required_not_run"]:
        w.append(f"linkedin: a query was not run in required countries {pg['required_not_run']} "
                 f"-- drop the query everywhere, not a required country for one query")
    if rec.get("mode") == "deep" and not phd_reached(rec):
        w.append("deep pass without phd_portals reached -- PhD portals are mandatory on a deep "
                 "pass (best strong-lead rate of any channel, 3 of 6)")
    return w


def load():
    if not LOG.exists():
        return []
    runs = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    runs.sort(key=lambda r: r.get("started") or r.get("run_id", ""))
    return runs


def starved(runs, window=STARVED_WINDOW):
    """Channels not actually reached in the last `window` runs.

    `skipped` is not `reached`, so a channel that keeps losing the budget shows up here rather
    than looking like a source that had nothing. Measured 2026-08-08 over 16 runs: the skill's
    "rotate which category is sacrificed" never happened -- nordic_boards was absent from 14
    runs and phd_portals from 11, while PhD roles carry the highest median fit in the vault.
    """
    hit = {c["key"] for r in runs[-window:] for c in r.get("channels", [])
           if c.get("status") in ("reached", "partial")}
    return sorted(CHANNELS - hit)


def _toks(s):
    return {t for t in re.split(r"[^a-z0-9]+", str(s).lower()) if t and t != "or"}


def query_usage(runs, pool=None):
    """QUERY_POOL entry -> number of runs whose logged LinkedIn queries covered it.

    A pool entry counts as used by a logged query when the logged query contains all of the
    entry's tokens, so `nanobody OR minibinder OR antibody engineering` credits `nanobody` and
    `minibinder` but not the unrelated `peptide design`.
    """
    pool = QUERY_POOL if pool is None else pool
    used = {q: 0 for q in pool}
    for r in runs:
        issued = [_toks(q) for c in r.get("channels", []) if c.get("key") == "linkedin"
                  for q in (c.get("queries") or [])]
        for q in pool:
            qt = _toks(q)
            if qt and any(qt <= i for i in issued):
                used[q] += 1
    return used


def deep_pass_age(runs):
    """(n_deep, days_since_last_deep). days is None when no deep pass was ever logged."""
    deep = [r for r in runs if r.get("mode") == "deep"]
    if not deep:
        return 0, None
    last = parse_stamp(deep[-1].get("started"))
    if not last:
        return len(deep), None
    return len(deep), (datetime.now(last.tzinfo) - last).days


def frontmatter(path):
    """Flat YAML frontmatter of a vault .md as a dict of strings. Stdlib only, so no yaml."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    out = {}
    for line in (text[3:end] if end != -1 else text[3:4000]).splitlines():
        m = FM_LINE.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip().strip("\"'")
    return out


def _record(p, folder, kind):
    fm = frontmatter(p)
    parts = p.stem.split("_")
    # Telemetry tracks `career_fit` — "did this run surface work the user actually wants?".
    # That is the question collection quality is judged on; whether he was qualified for a
    # given lead says nothing about whether the search channel was worth running.
    # Discontinuity to remember when reading old runs: records logged before 2026-08-17
    # carried a blended `fit_score` mixing desirability with skill and level, so pre- and
    # post-rescore numbers are not directly comparable. Records still on v1 read as None.
    try:
        fit = int(float(fm.get("career_fit", "")))
    except (TypeError, ValueError):
        fit = None
    app = (fm.get("app_status") or "").strip().lower()
    return (
        parts[0],
        role_key(parts[1]) if len(parts) > 1 and kind == "position" else "",
        canon_url(fm.get("url", "")),
        {"fit": fit, "folder": folder, "kind": kind, "file": f"{folder}/{p.name}",
         "cv": bool(app) or bool(fm.get("cv_date")) or folder == "applied",
         "sent": app in {"sent", "interviewing", "closed"} or bool(fm.get("sent_date"))},
    )


def vault_outcomes():
    """[(org, role_key, canon_url, info)] over every record a collection could have become.

    `info` carries what became of the lead: its /inbox `career_fit`, and whether a CV was ever
    generated and sent. This is the join that lets collection be judged on quality instead of
    count.

    Profile folders are indexed alongside positions because they are a *designed* destination,
    not a failure: Gate 4 routes postdoc ads and faculty calls to `_group-profile_` files, so a
    collected postdoc that became a research-group entry did exactly what the skill asked. Index
    positions only and every one of those reads as a lost lead.
    """
    idx = [_record(p, Path(g).parent.name, "position")
           for g in POSITION_GLOBS for p in ROOT.glob(g)]
    idx += [_record(p, Path(g).parent.name, Path(g).parent.name.rstrip("s"))
            for g in PROFILE_GLOBS for p in ROOT.glob(g)]
    return idx


def match_outcome(find, idx):
    """The vault record a collected lead became, or None if it never became one.

    Four tiers, weakest last. Unlike `dedup_check.match`, this one accepts role-slug DRIFT and
    bare-employer matches, because the two decisions carry opposite risks: there, a wrong match
    silently drops a real lead at collection time; here, it only mis-attributes a row in a report.

    Drift is matched on TOKEN SUBSET, not substring. Substring was tried first and failed on both
    real cases, because the extra words land mid-slug rather than at the end:
    `postdoc-computational-peptide-design-gpcrs` is not a substring of
    `postdoc-computational-peptide-design-metabolic-gpcrs`, nor
    `research-scientist-ai-enzyme-engineering` of `research-scientist-ai-driven-enzyme-
    engineering-ktp`. As token sets both are clean subsets.
    """
    url = canon_url(find.get("url"))
    if url:
        for _, _, purl, info in idx:
            if purl and purl == url:
                return info
    forg, frk = str(find.get("org") or ""), role_key(find.get("role"))
    ftok = set(frk.split("-")) - {""}
    kin = [(rk, info) for org, rk, _, info in idx
           if same_employer(forg, org) in ("same", "maybe")]
    for rk, info in kin:                                    # exact role
        if rk and rk == frk:
            return info
    for rk, info in kin:                                    # role-slug drift
        rtok = set(rk.split("-")) - {""}
        if rtok and ftok and (rtok <= ftok or ftok <= rtok):
            return info
    for rk, info in kin:                                    # routed to a company/group profile
        if not rk and info["kind"] != "position":
            return info
    return None


def attribute_outcomes(runs, view, idx):
    """[(run_index, find, info|None, credited)] for every net-new collection.

    `credited` is True only the first time a given vault record is reached, so a record two
    separate collections both resolve to -- the NNF CPD centre arrived once as a group profile
    and once as a faculty call under its university name -- is counted once, not twice.
    """
    seen, out = set(), []
    for i, _ in enumerate(runs):
        for find in view[i]["new"]:
            info = match_outcome(find, idx)
            credited = bool(info) and info["file"] not in seen
            if credited:
                seen.add(info["file"])
            out.append((i, find, info, credited))
    return out


def collection_view(runs):
    """Per-run [{'new': [find, ...], 'redundant': n}], using the shared lead identity.

    A lead re-collected under a slug variant is not yield. Counting it as such is what let the
    2026-08-08 run report `coll: 3` when all three were already in the vault and its true
    contribution was zero.
    """
    seen, view = {}, [{"new": [], "redundant": 0} for _ in runs]
    for i, r in enumerate(runs):
        for find in r.get("collected", []):
            key = lead_key(find, seen)
            if key in seen:
                view[i]["redundant"] += 1
                continue
            seen[key] = i
            view[i]["new"].append(find)
    return view


def screen_reasons(runs):
    """Counter of stable `reason` codes over every rejected candidate."""
    return Counter(s.get("reason") or "(unstated)"
                   for r in runs for s in r.get("screened", []))


def stats():
    runs = load()
    if not runs:
        print("no log yet")
        return
    print(f"{len(runs)} run(s) logged")
    n_coll = sum(len(r.get("collected", [])) for r in runs)
    n_scr = sum(len(r.get("screened", [])) for r in runs)
    dated = sum(1 for r in runs for c in r.get("collected", []) if c.get("posted"))
    print(f"  collected: {n_coll} ({dated} with a posting date — only these can measure recall)")
    print(f"  screened/rejected: {n_scr}")
    skipped = {}
    for r in runs:
        for c in r.get("channels", []):
            if c["status"] in ("skipped", "failed"):
                skipped[c["key"]] = skipped.get(c["key"], 0) + 1
    if skipped:
        print("  channels most often skipped/failed:")
        for k, v in sorted(skipped.items(), key=lambda x: -x[1]):
            print(f"    {k:<22} {v}/{len(runs)} runs")

    reasons = screen_reasons(runs)
    if reasons:
        tot = sum(reasons.values())
        print(f"\n  screening rejections by reason ({tot} total) — gate calibration:")
        for code, n in reasons.most_common():
            print(f"    {code:<22} {n:>4}  {100 * n / tot:>5.1f}%")

    if not HAVE_IDENTITY:
        print("\n  (dedup_check.py not importable — net-new and outcome columns unavailable)")
        return

    view = collection_view(runs)
    idx = vault_outcomes()
    attributed = attribute_outcomes(runs, view, idx)

    # Cost/yield per configuration. This is the whole reason model+effort+runtime are logged:
    # "opus/high finds 2x per run but takes 3x as long" is actionable, a raw run count is not.
    #
    # `new/run` counts NET-NEW leads only, and `strong/run` counts those that /inbox went on to
    # score >=75. A config that collects three weak or already-tracked leads must not outrank one
    # that collects a single strong one -- which is exactly what the old raw coll/run did.
    by_cfg = {}
    for i, r in enumerate(runs):
        key = f"{r.get('model', '?')}/{r.get('effort', '?')}/{r.get('mode', '?')}"
        b = by_cfg.setdefault(key, {"runs": 0, "new": 0, "redup": 0, "strong": 0,
                                    "scr": 0, "mins": [], "no_time": 0})
        b["runs"] += 1
        b["new"] += len(view[i]["new"])
        b["redup"] += view[i]["redundant"]
        b["scr"] += len(r.get("screened", []))
        d = r.get("duration_min", duration_min(r))
        if isinstance(d, int):
            b["mins"].append(d)
        else:
            b["no_time"] += 1
    for i, _, info, credited in attributed:
        if credited and info["fit"] is not None and info["fit"] >= STRONG_FIT:
            r = runs[i]
            by_cfg[f"{r.get('model', '?')}/{r.get('effort', '?')}/{r.get('mode', '?')}"]["strong"] += 1
    print("\n  yield by model/effort/mode:")
    print(f"    {'config':<24} {'runs':>4} {'new/run':>8} {'redup':>6} {'strong/run':>11}"
          f" {'scr/run':>8} {'min/run':>8}")
    for k, b in sorted(by_cfg.items(), key=lambda x: -x[1]["runs"]):
        mins = f"{sum(b['mins']) / len(b['mins']):.0f}" if b["mins"] else "-"
        print(f"    {k:<24} {b['runs']:>4} {b['new'] / b['runs']:>8.1f} {b['redup']:>6} "
              f"{b['strong'] / b['runs']:>11.1f} {b['scr'] / b['runs']:>8.1f} {mins:>8}")
    untimed = sum(b["no_time"] for b in by_cfg.values())
    if untimed:
        print(f"    ({untimed} run(s) have no usable start/end pair and are excluded from min/run)")
    redup = sum(b["redup"] for b in by_cfg.values())
    if redup:
        print(f"    redup = leads re-collected under a slug variant: {redup} of "
              f"{redup + sum(b['new'] for b in by_cfg.values())} raw collections were not new")

    # What the leads from each channel actually became. The pipeline's stated bottleneck is
    # conversion, not discovery, and until this table existed nothing recorded which channel
    # feeds the applications that get sent.
    chan = defaultdict(Counter)
    for _, find, info, credited in attributed:
        c = chan[find.get("channel") or "?"]
        c["new"] += 1
        if not info:
            c["unmatched"] += 1
        elif credited:
            c["strong"] += info["fit"] is not None and info["fit"] >= STRONG_FIT
            c["cv"] += bool(info["cv"])
            c["sent"] += bool(info["sent"])
    if chan:
        print("\n  channel -> what its leads became (net-new, each vault record counted once):")
        print(f"    {'channel':<20} {'new':>4} {'strong':>7} {'CV':>4} {'sent':>5} {'unmatched':>10}")
        for k, c in sorted(chan.items(), key=lambda x: -x[1]["new"]):
            print(f"    {k:<20} {c['new']:>4} {c['strong']:>7} {c['cv']:>4} {c['sent']:>5} "
                  f"{c['unmatched']:>10}")
        um = sum(c["unmatched"] for c in chan.values())
        if um:
            print(f"    unmatched = no record in positions/ or organizations/ carries that org+role "
                  f"or url ({um} of {sum(c['new'] for c in chan.values())})")

    n_deep, age = deep_pass_age(runs)
    if n_deep == 0:
        print(f"\n  deep passes: 0 of {len(runs)} runs — never run.  "
              f"** DEEP PASS OVERDUE: make the next run a deep pass **")
    elif age is not None and age > DEEP_PASS_MAX_AGE_DAYS:
        print(f"\n  deep passes: {n_deep} of {len(runs)} runs — last one {age}d ago.  "
              f"** DEEP PASS OVERDUE (>{DEEP_PASS_MAX_AGE_DAYS}d) **")
    else:
        print(f"\n  deep passes: {n_deep} of {len(runs)} runs"
              + (f" — last one {age}d ago" if age is not None else ""))

    recent = runs[-10:]
    geo_short = sum(1 for r in recent if missing_required_geos(r))
    print(f"  required LinkedIn countries {REQUIRED_GEOS}: skipped in {geo_short} of the last "
          f"{len(recent)} runs")
    paged = [(r, paging_shortfall(r)) for r in recent]
    paged = [(r, pg) for r, pg in paged if pg]
    if paged:
        short = sum(1 for _, pg in paged if pg["unexplained"])
        read = sum(pg["read"] for _, pg in paged)
        owed = sum(pg["owed"] for _, pg in paged)
        print(f"  linkedin paging ({PAGES} per query x country): short without a reason in {short} "
              f"of {len(paged)} recent run(s) that log pages — {read} of {owed} pages read")
    else:
        print(f"  linkedin paging ({PAGES} per query x country): no recent run logs 'pages' yet")
    deep = [r for r in runs if r.get("mode") == "deep"]
    if deep:
        print(f"  deep passes without phd_portals reached: "
              f"{sum(1 for r in deep if not phd_reached(r))} of {len(deep)}")

    st = starved(runs)
    print(f"  starved channels (not reached in the last {STARVED_WINDOW} runs): "
          + (", ".join(st) if st else "none — full coverage"))

    # LinkedIn funnel. Only computable on records that carry `shortlisted`; older ones do not.
    hits = short = n = 0
    for r in runs:
        for c in r.get("channels", []):
            if c.get("key") == "linkedin" and isinstance(c.get("shortlisted"), int):
                hits += c.get("hits") or 0
                short += c["shortlisted"]
                n += 1
    if n:
        print(f"  linkedin funnel: {hits} hits -> {short} shortlisted "
              f"({100 * short / hits:.1f}%) over {n} run(s)")
    else:
        print("  linkedin funnel: no run yet logs 'shortlisted' — the hits->candidates step "
              "is still unmeasured")


def main():
    argv = sys.argv[1:]
    if "--stats" in argv:
        stats()
        return
    if "--starved" in argv:
        st = starved(load())
        print("\n".join(st) if st else "none — every channel reached in the last "
              f"{STARVED_WINDOW} runs")
        return
    if "--next-queries" in argv:
        i = argv.index("--next-queries")
        n = int(argv[i + 1]) if len(argv) > i + 1 and argv[i + 1].isdigit() else 4
        used = query_usage(load())
        # Least-used first, ties broken by pool order so the output is stable run to run.
        order = sorted(QUERY_POOL, key=lambda q: (used[q], QUERY_POOL.index(q)))
        for q in order[:n]:
            print(f"{q}\t({used[q]} run(s))")
        if RECRUITER_POOL:
            r_used = query_usage(load(), RECRUITER_POOL)
            q = min(RECRUITER_POOL, key=lambda x: (r_used[x], RECRUITER_POOL.index(x)))
            print(f"{q}\t({r_used[q]} run(s))  <- recruiter query")
        return
    if not argv:
        sys.exit(__doc__)

    path = Path(argv[0])
    if not path.exists():
        sys.exit(f"no such file: {path}")
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"invalid JSON: {e}")

    errs = problems(rec)
    if errs:
        print("INVALID — not appended:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)

    # Derived, so it is stored rather than recomputed by every reader.
    rec["duration_min"] = duration_min(rec)

    n_no_date = sum(1 for c in rec.get("collected", []) if not c.get("posted"))
    print(f"valid: {len(rec.get('collected', []))} collected, "
          f"{len(rec.get('screened', []))} screened/rejected, "
          f"{rec['duration_min']} min on {rec['model']}/{rec['effort']}")
    if n_no_date:
        print(f"  warning: {n_no_date} collected item(s) have no posting date and cannot "
              f"contribute to recall measurement")
    for w in warnings(rec):
        print(f"  warning: {w}")

    if "--check" in argv:
        print("(--check: nothing written)")
        return

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"appended to {LOG.relative_to(REPO).as_posix()}")
    msg = archive_sweep(rec)
    if msg:
        print(("  " if msg.startswith("warning") else "") + msg)


if __name__ == "__main__":
    main()
