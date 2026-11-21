#!/usr/bin/env python3
"""Career dashboard generator.

Scans the vault's profiles + position leads, reads YAML frontmatter, computes
statistics, and emits a single self-contained dashboard.html (tabs + sortable
tables + a Statistics tab of hand-built SVG charts). No external dependencies.

Run:  python engine/tools/dashboard.py
Out:  dashboard.html  (open in any browser)
"""
import os, re, json, glob, datetime
import html
from paths import ARTIFACTS, TOOLS, WORKSPACE, setting, settings, user_name
from frontmatter import fm_parse
import plan as planstore
ROOT = str(WORKSPACE)  # record paths are relative to user/workspace/
TODAY = datetime.date.today()

# Position/PhD leads are kept on disk but hidden from every tab, tile and deadline
# reminder when BOTH scores fall below this. Either number clearing the bar keeps the
# row visible, which is the whole point of the 2026-08-17 split: a domain 88 / skill 40
# stretch and a domain 45 / skill 85 fallback are both worth seeing, and the old blended
# fit_score would have buried the first and flattered the second.
# Companies and groups are never hidden by score at all -- the org databases are browsed
# to pick a cold-outreach target, not worked top-down like a lead list.
# The bar itself is personal: user/settings.toml [thresholds].
MIN_SCORE_SHOWN = setting("thresholds.min_score_shown")
# domain_fit at or above this counts as on-direction (the funnel's second bar). Same file.
ON_DIRECTION = setting("thresholds.on_direction")
# What the page calls domain_fit: the user's own word for their field, e.g. "Protein".
LABEL = str(settings().get("domain_fit", {}).get("label") or "Domain").strip()

# ---------------------------------------------------------------- frontmatter
def parse_frontmatter(path):
    with open(path, encoding="utf-8") as f:
        return fm_parse(f.read())

def as_int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default

def days_until(datestr):
    try:
        d = datetime.date.fromisoformat(str(datestr)[:10])
        return (d - TODAY).days
    except (TypeError, ValueError):
        return None

def days_since(datestr):
    du = days_until(datestr)
    return None if du is None else -du

def interview_lines(v):
    """`interviews:` -> [(date, note)]. One "YYYY-MM-DD: note" line per interview, past or booked
    (written by /track). Lines without a leading date are skipped: they cannot be placed."""
    out = []
    for line in ([v] if isinstance(v, str) else (v or [])):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\s*:?\s*(.*)$", str(line).strip())
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out

# ---------------------------------------------------------------- collectors
# Non-entity docs that may live alongside profiles (e.g. a person bio in
# research_groups/) — never count or list these on the dashboard.
SKIP_TYPES = {"person_bio"}

def load(globpat, kind):
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, globpat))):
        fm = parse_frontmatter(p)
        if not fm:
            continue
        role = fm.get("role_title") or ""
        typ = str(fm.get("type") or fm.get("org_type") or "").lower()
        if typ in SKIP_TYPES:
            continue
        rel = os.path.relpath(p, ROOT).replace("\\", "/")
        is_phd = ("phd" in typ) or ("phd" in role.lower())
        cat = kind
        if kind == "position":
            cat = "phd" if is_phd else "position"
        out.append({
            "category": cat,
            "name": fm.get("name") or fm.get("organization") or os.path.basename(p)[:-3],
            "role": role,
            "org": fm.get("organization") or fm.get("name") or "",
            "type": typ,
            "location": fm.get("location") or "",
            "country": fm.get("country") or "",
            # Three independent scores (two since 2026-08-17, method_fit added
            # 2026-09-29); never blend them. All sit on
            # every kind of record: for a position skill_match reads the ad's requirements,
            # for a company or group it reads the org's stated stack ("could I be useful
            # here"), which is what unsolicited applications are decided on.
            # -1 means the field is absent -- not yet scored. 0 is a real score meaning
            # "no overlap", so the two must stay distinct; the page renders -1 as an em dash.
            # -1 when absent, like method and skill below. It defaulted to 0 until 2026-10-10, which
            # made a real domain_fit 0 (band E, off-direction work) indistinguishable from a missing
            # one, and the unscored count below flagged two fully scored band-E leads.
            "domain": as_int(fm.get("domain_fit"), -1),
            # method_fit (2026-09-29): does the seat BUILD methods or only operate them?
            # Independent of domain_fit by design -- it exists so method roles outside protein
            # design are visible at all.
            "method": as_int(fm.get("method_fit"), -1),
            "skill": as_int(fm.get("skill_match"), -1),
            "level": fm.get("level_fit") or "",
            # bench_load (schema v2, 2026-10-26): wet-lab work in the seat. Reported, never
            # scored -- the page can sort by it or hide `substantial` rows, nothing else reads it.
            # Rank orders the sort: unknown sits between light and substantial, since it may be
            # either; -1 is a record without the field (orgs).
            "bench": fm.get("bench_load") or "",
            "bench_rank": {"none": 0, "light": 1, "unknown": 2, "substantial": 3}.get(fm.get("bench_load") or "", -1),
            # Provenance: which of the two parallel searches found this. Legacy records
            # default to career -- every record predating 2026-08-17 was collected by the
            # direction search, because it was the only one that existed. Provenance never
            # affects a score; it only decides which tab a position appears on.
            "track": (fm.get("track") or "career").lower(),
            "tier": fm.get("prestige_tier") or "",
            "lead_status": fm.get("status") or "",
            "deadline": fm.get("deadline") or "",
            "deadline_in": days_until(fm.get("deadline")),
            "app_status": (fm.get("app_status") or "not_started"),
            "app_outcome": fm.get("app_outcome") or "",
            "cv_date": fm.get("cv_date") or "",
            "cv_dir": fm.get("cv_dir") or "",
            # cv_dir_prior: earlier application folders for the same record, kept when cv_dir
            # moves to a newer one (outreach letter first, formal application later). Only the
            # integrity check reads it, so a superseded folder is not reported as untracked.
            "cv_dir_prior": [fm["cv_dir_prior"]] if isinstance(fm.get("cv_dir_prior"), str) and fm["cv_dir_prior"]
                            else (fm.get("cv_dir_prior") or []),
            "sent_date": fm.get("sent_date") or "",
            # interviews (2026-11-07): each becomes a moment on the Timeline (plan_derived below).
            "interviews": interview_lines(fm.get("interviews")),
            "last_contact": fm.get("last_contact") or "",
            "next_action": fm.get("next_action") or "",
            "contact_status": fm.get("contact_status") or "",
            "org_profile": fm.get("org_profile") or "",
            "url": fm.get("url") or "",
            "url_status": fm.get("url_status") or "unchecked",
            "url_checked": fm.get("url_checked") or "",
            # Age since collection, for the staleness flag below. Distinct from eval_age
            # (which measures re-scoring, not whether the posting still exists).
            "created": fm.get("created") or "",
            "age": days_since(fm.get("created")),
            "last_evaluated": fm.get("last_evaluated") or "",
            "eval_age": days_since(fm.get("last_evaluated")),
            "path": rel,
        })
    return out

records = []
records += load("organizations/companies/*.md", "company")
records += load("organizations/research_groups/*.md", "group")
records += load("positions/open/*.md", "position")
records += load("positions/applied/*.md", "position")
records += load("positions/closed/*.md", "position")

# ------------------------------------------------- applications per organisation
# Company/group rows show when an application was last SENT to that employer, which is
# different information from `last_contact` (an unsolicited approach). Joining the two
# needs employer-identity matching, which lives in org_match.py (built on dedup_check.py's
# alias table and structural org-token rule). It is shared with org_floor.py rather than
# forked, so the dashboard and the domain_fit floor always agree on which positions belong
# to which profile.
from org_match import same_employer, org_tokens, ALIASES, slugify, file_slug, token_df
from org_match import employer_hit as _employer_hit

for prof in records:
    if prof["category"] in ("company", "group"):
        prof["slug"] = os.path.basename(prof["path"])[:-3]

TOKEN_DF = token_df(r for r in records if r["category"] in ("company", "group"))

def employer_hit(profile, pos):
    """True when this position belongs to this company/group — see org_match.employer_hit."""
    return _employer_hit(profile, pos, TOKEN_DF)

def _appdate(r):
    """The date an application actually went out. `sent_date` is the truth; fall back to
    cv_date only when a lead is marked sent/closed but the send date was never stamped."""
    for v in (r["sent_date"], r["cv_date"] if r["app_status"] in ("sent", "interviewing", "closed") else ""):
        if re.match(r"^\d{4}-\d{2}-\d{2}$", str(v or "")):
            return v[:10]
    return ""

def _sent_evidence(r):
    """Positive evidence that an application actually went out. Applies to ANY record.

    `app_status: closed` alone does NOT mean applied — it means the track ended, and several
    leads are closed with `app_outcome: withdrawn` and no cv_date or sent_date, i.e. never
    sent at all. A record counts when it is sent/interviewing, or carries any sent_date (some
    older records say `unknown`), or was closed with an outcome only reachable by applying.

    This was the org-row rule only until 2026-08-18, while the "CVs sent" tile used a looser
    set that treated every `closed` record as sent. The two disagreed on 6 records — all
    closed `withdrawn`, none ever submitted — so the headline funnel number read 28 when the
    truth was 22. One definition now, used by both.
    """
    if r["app_status"] in ("sent", "interviewing"):
        return True
    if str(r["sent_date"] or "").strip():
        return True
    return r["app_status"] == "closed" and r["app_outcome"] in ("rejected", "offer")


def _was_sent(r):
    """Did an application go out for this LEAD specifically?

    Same evidence rule, restricted to positions — the company/group rows are built by joining
    positions to employers, so an org's own unsolicited send is counted on its own row rather
    than through this join.
    """
    return r["category"] in ("position", "phd") and _sent_evidence(r)

# Undated sends are kept — "applied, date not recorded" is the truth for them, and dropping
# them would render as "never applied", which is worse than an imprecise date.
applied_positions = [r for r in records if _was_sent(r)]

for prof in records:
    if prof["category"] not in ("company", "group"):
        continue
    hits = [p for p in applied_positions if employer_hit(prof, p)]
    hits.sort(key=_appdate, reverse=True)
    dates = [d for d in (_appdate(h) for h in hits) if d]
    prof["applied_count"] = len(hits)
    prof["last_applied"] = max(dates) if dates else ""
    prof["applied_roles"] = [{"role": h["role"] or h["name"], "date": _appdate(h) or "date not recorded",
                              "path": h["path"], "outcome": h["app_outcome"]} for h in hits[:6]]

# ---------------------------------------------------------------- statistics
# NB: no loose SENT set any more — "was it sent" is _sent_evidence() and nothing else.
ONGOING = {"sent", "interviewing"}

def is_positive(r):
    """The 'on-direction' tile: how much of the vault is work the user actually wants.

    domain_fit only, deliberately. This counts desirability, not winnability — a record
    here may still be a `reach`, and that is the honest picture. Reading skill_match in
    would recreate the blended fit_score this dashboard stopped using.
    """
    return r["domain"] >= ON_DIRECTION

search_results = len(glob.glob(os.path.join(ROOT, "inbox/processed/**/*.txt"), recursive=True))
cvs_generated_folders = len([d for d in glob.glob(os.path.join(ROOT, "applications/*")) if os.path.isdir(d)])

def _alive(r):
    # "alive" position/phd lead: not expired/closed AND deadline not past
    # (a lead with no deadline is still alive — it hasn't passed anything)
    if r["lead_status"] in ("expired", "closed"):
        return False
    di = r["deadline_in"]
    return di is None or di >= 0

def _best(r):
    """The highest of the three scores. Only ever used for the visibility gate and sorting
    fallback — never displayed, never written to a file. Blending the scores into one
    number for a human to read is the mistake this system was rebuilt to avoid.

    method_fit joined on 2026-09-29 and it had to: the whole point of that score is that a
    methods-building role outside protein design (low domain, moderate skill) is worth seeing.
    Leaving it out of the gate would have hidden exactly the records it was added to surface."""
    return max(r["domain"], r["method"], r["skill"])


# Read from the same settings as expire_sweep.py, so the tripwire and the sweep cannot drift.
STALE_DAYS = setting("thresholds.stale_days")
VERIFIED_DAYS = setting("thresholds.verified_days")
ACTIVE_APP = {"applied", "sent", "interviewing", "offer"}

def _verified_recently(r):
    """True when a fresh liveness verdict exempts this lead from age retirement.

    Mirrors expire_sweep.verified_live() and must stay in step with it: `url_status: working`
    only, never a LinkedIn `working` (link_check.py cannot produce that verdict for LinkedIn
    since 2026-08-16), and checked within VERIFIED_DAYS. See expire_sweep.py's module docstring.
    """
    if r["url_status"].lower() != "working":
        return False
    if "linkedin.com" in r["url"].lower():
        return False
    checked = days_since(r["url_checked"])
    return checked is not None and 0 <= checked <= VERIFIED_DAYS

def _stale(r):
    """TRIPWIRE, not a report: this should normally be zero.

    Since 2026-08-29 `expire_sweep.py` RETIRES deadline-less leads older than STALE_DAYS
    (user/settings.toml) on age alone, and /dashboard runs that sweep as step 1. So a stale lead surviving
    to this page means the sweep has not run -- go and run it. Before that change this flag
    was the only thing surfacing such leads, of which there were 35.

    Since 2026-11-18 a lead confirmed live within VERIFIED_DAYS is exempt from that sweep, so
    flagging it here would be a false alarm: the sweep is deliberately keeping it, and telling
    the user to run the sweep would do nothing. A tripwire that fires on something no action can
    clear stops being a tripwire.
    """
    if r["category"] not in ("position", "phd"):
        return False
    if not _alive(r) or r["deadline"] not in ("", "null", "None", "~"):
        return False
    if r["app_status"] in ACTIVE_APP or r["lead_status"] in ACTIVE_APP:
        return False
    if _verified_recently(r):
        return False
    return r["age"] is not None and r["age"] > STALE_DAYS

def _shown(r):
    """Single source of truth for dashboard visibility.

    Companies and groups always show. A position/PhD lead shows when it is alive (not
    expired/closed, deadline not past) AND at least ONE of its three scores reaches
    MIN_SCORE_SHOWN. The OR is deliberate: hiding a lead needs "I don't want this science",
    "I don't want this kind of work" and "I can't do it" to be true all at once.
    Stamped onto every record below so the statistics, tab counts, tables, home page and
    plan deadlines cannot drift apart — they all read this one flag.
    """
    if r["category"] in ("company", "group"):
        return True
    return _alive(r) and _best(r) >= MIN_SCORE_SHOWN

for r in records:
    r["shown"] = _shown(r)
    r["stale"] = _stale(r)

# every count below is "what is visible on the dashboard", nothing else
by_cat = {c: sum(1 for r in records if r["category"] == c and r["shown"])
          for c in ("company", "group", "position", "phd")}
# kept on disk, hidden from view: still-live leads under the bar on ALL THREE scores
hidden_low = sum(1 for r in records
                 if r["category"] in ("position", "phd") and _alive(r)
                 and _best(r) < MIN_SCORE_SHOWN)
# a record with no domain_fit or skill_match is a hole in the tables (a blank cell is not zero)
unscored = sum(1 for r in records if r["domain"] < 0 or r["skill"] < 0)
# Shown-filtered, like every other tile. It was not, until 2026-08-29: it counted every record
# in the vault including expired and closed leads, so it read 125 while only 79 of those were
# visible anywhere on the page -- 46 were closed/retired positions and PhD leads. Harmless-looking
# until the 45-day age retirement moved 39 leads to closed/ in one run and the tile did not
# budge. `positive_all` keeps the lifetime figure, which is the honest home for that number.
positive = sum(1 for r in records if is_positive(r) and r["shown"])
positive_all = sum(1 for r in records if is_positive(r))
# One definition of "sent", shared with the org-row join above. Orgs are included here
# because an unsolicited application to a company or lab is a real send (7 on record).
cvs_sent = sum(1 for r in records if _sent_evidence(r))
ongoing = sum(1 for r in records if r["app_status"] in ONGOING)
offers = sum(1 for r in records if r["app_outcome"] == "offer")
rejections = sum(1 for r in records if r["app_outcome"] == "rejected")
cv_generated_items = sum(1 for r in records if r["app_status"] != "not_started" or r["cv_date"])
_done_app = {"sent", "interviewing", "closed"}

stats = {
    "search_results": search_results,
    "positive": positive,
    "positive_all": positive_all,
    "companies": by_cat["company"],
    "groups": by_cat["group"],
    "positions": by_cat["position"],
    "phd": by_cat["phd"],
    "hidden_low": hidden_low,
    "unscored": unscored,
    "min_fit_shown": MIN_SCORE_SHOWN,
    # Staleness: shown leads with no deadline that nothing has verified in STALE_DAYS.
    # `stale_positive` is the part that overlaps the On-direction tile, which is why that
    # tile has to be read as an upper bound rather than a count of live opportunities.
    "stale": sum(1 for r in records if r.get("stale") and r["shown"]),
    "stale_positive": sum(1 for r in records if r.get("stale") and r["shown"] and is_positive(r)),
    "stale_days": STALE_DAYS,
    "on_direction": ON_DIRECTION,
    "cvs_generated": max(cvs_generated_folders, cv_generated_items),
    "cvs_sent": cvs_sent,
    "ongoing": ongoing,
    "offers": offers,
    "rejections": rejections,
    "generated_date": TODAY.isoformat(),
}

# ---------------------------------------------------------------- integrity checks
# Surface tracking drift that would otherwise stay silent: generated CVs with no
# stamped source, cv_dir pointers to missing folders, and mis-filed leads.
app_dirs = {os.path.basename(d.rstrip("/\\")) for d in glob.glob(os.path.join(ROOT, "applications", "*")) if os.path.isdir(d)}
referenced = set()
integrity = []
for r in records:
    for field, dirs in (("cv_dir", [r["cv_dir"]]), ("cv_dir_prior", r["cv_dir_prior"])):
        for cd in dirs:
            cd = (cd or "").strip().rstrip("/")
            if not cd:
                continue
            referenced.add(os.path.basename(cd))
            if not os.path.isdir(os.path.join(ROOT, cd)):
                integrity.append({"kind": "missing_cv_dir", "path": r["path"],
                                  "msg": f"{r['path']} points to {field} '{cd}' but that folder is missing"})
for name in sorted(app_dirs - referenced):
    integrity.append({"kind": "untracked_cv", "path": f"applications/{name}/",
                      "msg": f"applications/{name}/ exists but no profile points to it (untracked application)"})
for r in records:
    if r["path"].startswith("positions/open/") and r["lead_status"] in ("expired", "closed"):
        integrity.append({"kind": "stale_in_open", "path": r["path"],
                          "msg": f"{r['path']} is status '{r['lead_status']}' but still filed in positions/open/"})
    if r["category"] in ("position", "phd") and r["app_status"] in ("sent", "interviewing") \
       and (r["path"].startswith("positions/open/") or r["path"].startswith("positions/closed/")):
        integrity.append({"kind": "sent_not_applied", "path": r["path"],
                          "msg": f"{r['path']} is app_status '{r['app_status']}' but not in positions/applied/"})
    if r["app_status"] == "interviewing" and not r["interviews"]:
        integrity.append({"kind": "interview_undated", "path": r["path"],
                          "msg": f"{r['path']} is app_status 'interviewing' but lists no dated "
                                 f"interviews:, so the interview is missing from the Timeline"})

# ---------------------------------------------------------------- plan (Timeline + To-do)
# The two tabs share one store, user/workspace/plan/plan.json (plan.py), which holds what the user
# added. Records contribute two kinds of item of their own, derived fresh on every run so they can
# never drift from the frontmatter: every application SENT (a moment, already done -- history for
# the Timeline), every interview listed under `interviews:` (a moment, done once its day has
# passed), and every live deadline still to act on: shown (so alive and clearing
# MIN_SCORE_SHOWN), not yet applied, any horizon. Their dates are the record's; plan.json may only restyle, flag, tick or hide
# them (`overrides`). Defaults: a deadline or interview is urgent inside 14 days -- the red cut-off
# of the Deadline column; a deadline is important when the lead is on-direction, an interview
# always. Both are a first guess for the matrix, which the user overrides in one click.
def _label(r):
    """Employer · role for a lead, the name for an org. A position's `name` falls back to its
    `organization` (no position record has a `name:`), so comparing the two dropped the employer
    from every lead until 2026-11-07. The employer is cut at " — " (the sub-unit after it is
    noise on a Timeline ribbon) and left out only when the role already names it."""
    if r["category"] in ("position", "phd"):
        role = r["role"] or r["name"]
        org = r["org"].split(" — ")[0].strip()
        return (org + " · " if org and org.lower() not in role.lower() else "") + role
    return r["name"]

plan_derived = []
for r in records:
    if _sent_evidence(r) and _appdate(r):
        plan_derived.append({"id": "sent:" + r["path"], "kind": "sent", "path": r["path"],
                             "title": "Applied · " + _label(r), "start": _appdate(r), "end": None,
                             "color": "#4f8cff", "important": False, "urgent": False, "done": True})
    seen = {}
    for day, note in r["interviews"]:
        # The id is the day, not the list position, so an override survives a line added above it.
        seen[day] = seen.get(day, 0) + 1
        left = days_until(day)
        plan_derived.append({"id": f"interview:{r['path']}:{day}" + ("" if seen[day] == 1 else f"-{seen[day]}"),
                             "kind": "interview", "path": r["path"],
                             "title": "Interview · " + _label(r), "start": day, "end": None,
                             "color": "#f1c40f", "important": True,
                             "urgent": left is not None and 0 <= left <= 14,
                             "done": left is not None and left < 0, "notes": note})
    if (r["category"] in ("position", "phd") and r["shown"] and r["deadline_in"] is not None
            and r["deadline_in"] >= 0 and r["app_status"] not in _done_app):
        plan_derived.append({"id": "deadline:" + r["path"], "kind": "deadline", "path": r["path"],
                             "title": "Deadline · " + _label(r), "start": str(r["deadline"])[:10],
                             "end": None, "color": "#e74c3c", "important": is_positive(r),
                             "urgent": r["deadline_in"] <= 14, "done": False})
try:
    plan_doc = planstore.load()
    plan_error = ""
except (planstore.PlanError, ValueError) as e:  # a hand edit broke it: show the records, say why
    plan_doc, plan_error = planstore.empty(), f"{planstore.PLAN_FILE} is unreadable: {e}"

# ---------------------------------------------------------------- statistics & telemetry tab
# The Statistics tab replaced the stat tiles on 2026-10-10: the same numbers, plus the search
# telemetry, drawn as charts. Telemetry is computed by the telemetry tools' own functions
# (log_run.py) and read from analyze_misses.py's latest cumulative report -- never re-derived
# here, so the tab and `log_run.py --stats` cannot disagree.
def _week(datestr):
    try:
        d = datetime.date.fromisoformat(str(datestr)[:10])
    except (TypeError, ValueError):
        return None
    return (d - datetime.timedelta(days=d.weekday())).isoformat()   # Monday of that week

def vault_stats():
    leads = [r for r in records if r["category"] in ("position", "phd")]
    weeks = {}
    for r in leads:
        w = _week(r["created"])
        if w:
            b = weeks.setdefault(w, {"career": 0, "skill": 0})
            # The skill track's records say `track: employability` (its earlier name) or `skill`.
            b["career" if r["track"] == "career" else "skill"] += 1
    recent = sorted(weeks)[-16:]
    return {
        "funnel": [["Search results", stats["search_results"]],
                   ["On-direction, live (%s fit ≥ %d)" % (LABEL, ON_DIRECTION), stats["positive"]],
                   ["CVs generated", stats["cvs_generated"]], ["CVs sent", stats["cvs_sent"]],
                   ["Ongoing", stats["ongoing"]], ["Offers", stats["offers"]]],
        "outcomes": {"rejections": stats["rejections"], "offers": stats["offers"],
                     "ongoing": stats["ongoing"]},
        "kinds": [["Companies", stats["companies"]], ["Research groups", stats["groups"]],
                  ["Positions", stats["positions"]], ["PhD leads", stats["phd"]]],
        "scatter": [{"domain": r["domain"], "skill": r["skill"], "cat": r["category"],
                     "name": _label(r), "path": r["path"]}
                    for r in leads if r["shown"] and r["domain"] >= 0 and r["skill"] >= 0],
        "weeks": [{"week": w, **weeks[w]} for w in recent],
    }

def telemetry_stats():
    """Search telemetry for the Statistics tab, or {"error": ...} when there is none yet."""
    try:
        import log_run
    except Exception as e:                      # a broken terms file must not break the page
        return {"error": f"log_run.py could not be loaded: {e}"}
    runs = log_run.load()
    if not runs:
        return {"error": "no search runs logged yet (user/workspace/logs/search_runs.jsonl)"}
    view = log_run.collection_view(runs)
    idx = log_run.vault_outcomes()
    strong_by_run, chan = {}, {}
    for i, find, info, credited in log_run.attribute_outcomes(runs, view, idx):
        c = chan.setdefault(find.get("channel") or "?", {"new": 0, "strong": 0})
        c["new"] += 1
        if credited and info["fit"] is not None and info["fit"] >= log_run.STRONG_FIT:
            c["strong"] += 1
            strong_by_run[i] = strong_by_run.get(i, 0) + 1
    run_rows, cover = [], {}
    for i, r in enumerate(runs):
        d = r.get("duration_min", log_run.duration_min(r))
        run_rows.append({"id": r.get("run_id"), "date": str(r.get("started") or "")[:10],
                         "mode": r.get("mode") or "?", "track": r.get("track") or "?",
                         "cfg": f"{r.get('model', '?')}/{r.get('effort', '?')}",
                         "new": len(view[i]["new"]), "strong": strong_by_run.get(i, 0),
                         "screened": len(r.get("screened", [])),
                         "mins": d if isinstance(d, int) else None})
        for c in r.get("channels", []):
            k = cover.setdefault(c["key"], {"reached": 0, "skipped": 0, "failed": 0})
            st = "reached" if c.get("status") in ("reached", "partial") else c.get("status")
            if st in k:
                k[st] += 1
    reasons = log_run.screen_reasons(runs).most_common()
    top = [[k, n] for k, n in reasons[:10]]
    if len(reasons) > 10:
        top.append(["other", sum(n for _, n in reasons[10:])])
    hits = short = 0
    for r in runs:
        for c in r.get("channels", []):
            if c.get("key") == "linkedin" and isinstance(c.get("shortlisted"), int):
                hits += c.get("hits") or 0
                short += c["shortlisted"]
    n_deep, deep_age = log_run.deep_pass_age(runs)
    out = {"runs": run_rows, "channels": chan, "coverage": cover, "reasons": top,
           "n_runs": len(runs), "n_deep": n_deep, "deep_age": deep_age,
           "strong_fit": log_run.STRONG_FIT, "li_hits": hits, "li_short": short, "misses": None}
    # The latest CUMULATIVE attribution report. Windowed ones (--since) carry "since" in the
    # name and answer a different question, so they are skipped.
    reports = [p for p in glob.glob(os.path.join(ROOT, "logs", "analysis", "misses_*.json"))
               if "since" not in os.path.basename(p)]
    if reports:
        latest = max(reports, key=os.path.getmtime)
        try:
            with open(latest, encoding="utf-8") as f:
                m = json.load(f)
            out["misses"] = {
                "file": os.path.relpath(latest, ROOT).replace("\\", "/"),
                "written": datetime.date.fromtimestamp(os.path.getmtime(latest)).isoformat(),
                "runs": m.get("runs_logged"), "total": m.get("total_attributed_misses"),
                "strong_leads": m.get("strong_leads"), "threshold": m.get("strong_threshold"),
                "all": m.get("cause_histogram") or {},
                "strong": m.get("strong_cause_histogram") or {},
                "lags": [x["lag_days"] for x in m.get("leads", []) if isinstance(x.get("lag_days"), int)],
            }
        except (OSError, ValueError, KeyError) as e:
            out["misses_error"] = f"{os.path.basename(latest)} is unreadable: {e}"
    return out

payload = {"records": records, "stats": stats, "integrity": integrity,
           "plan": {"doc": plan_doc, "derived": plan_derived, "error": plan_error},
           "vault": vault_stats(), "telemetry": telemetry_stats(), "label": LABEL}

# ---------------------------------------------------------------- HTML
HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><base href="../">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Career Engine__TITLE_NAME__</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--line:#272c36;--txt:#e6e9ef;--sub:#9aa3b2;--accent:#4f8cff;
--link:#5eead4;--cv:#d8b4fe;
--strong:#2ecc71;--mod:#f1c40f;--weak:#e67e22;--reach:#e74c3c;}
*{box-sizing:border-box}
body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--txt)}
header{padding:18px 24px;border-bottom:1px solid var(--line);display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
header h1{font-size:18px;margin:0}
header .meta{color:var(--sub);font-size:12px}
.wrap{padding:20px 24px;max-width:1400px;margin:0 auto}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:18px 0 10px}
.tab{background:var(--panel);border:1px solid var(--line);color:var(--sub);padding:8px 14px;border-radius:8px;cursor:pointer}
.tab.active{color:var(--txt);border-color:var(--accent);box-shadow:inset 0 -2px 0 var(--accent)}
.controls{margin:8px 0}
.controls input{background:var(--panel);border:1px solid var(--line);color:var(--txt);padding:8px 10px;border-radius:8px;width:280px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--sub);text-transform:uppercase;letter-spacing:.04em;cursor:pointer;user-select:none;position:sticky;top:0;background:#1b1f27}
tr:hover td{background:#1b1f27}
/* Text is never blue: blue and the browser's default link blue are near-invisible on this
   background. --accent stays for borders and fills; text that used it reads --link. */
a,a:visited{color:var(--link);text-decoration:none} a:hover{text-decoration:underline}
.score{font-weight:700;border-radius:6px;padding:2px 8px;display:inline-block;min-width:34px;text-align:center;color:#0b0d10}
.s-strong{background:var(--strong)} .s-mod{background:var(--mod)} .s-weak{background:var(--weak)} .s-reach{background:var(--reach)}
.badge{font-size:11px;padding:2px 8px;border-radius:20px;border:1px solid var(--line);color:var(--sub);white-space:nowrap}
.b-sent{border-color:var(--link);color:var(--link)} .b-interviewing{border-color:var(--mod);color:var(--mod)}
.b-cv{border-color:var(--cv);color:var(--cv)} .b-closed{border-color:var(--sub)} .b-offer{border-color:var(--strong);color:var(--strong)}
.b-rejected{border-color:var(--reach);color:var(--reach)}
.tier{font-size:11px;color:var(--sub)}
.tier.applied{color:var(--link);font-weight:600;cursor:help}
.dl-soon{color:var(--reach);font-weight:700} .dl-ok{color:var(--sub)}
.hidden{display:none}
.note{color:var(--sub);font-size:12px;margin:6px 0 0}
.notice{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;margin-top:12px}
__PLAN_CSS__
__STATS_CSS__
__HOME_CSS__
</style></head><body>
<header>
  <button class="home-btn" onclick="setTab('home')" title="Home (Esc)">⌂ Home</button>
  <h1>Career Engine</h1>
  <span class="meta">__META_NAME__generated __DATE__ · regenerate with <code>/dashboard</code></span>
</header>
<div class="wrap">
  <div class="tabs" id="tabs"></div>
  <div class="controls"><input id="filter" placeholder="filter the current tab…" oninput="render()">
    <label id="benchctl" class="tier" style="margin-left:12px;cursor:pointer"><input type="checkbox" id="hidebench" onchange="setHideBench(this.checked)" style="width:auto;vertical-align:middle"> hide substantial wet lab</label></div>
  <div id="table"></div>
  <p class="note"><b>__DOMAIN_LABEL__</b> = is this the science I want (direction only) · <b>Method</b> = is this the work I want (does the seat build methods or operate them) · <b>Skill</b> = can I do it (evidenced overlap) · <b>Level</b> = attainable today · <b>Wet lab</b> = bench work in the seat (<code>bench_load</code>; reported, never scored). <span class="tier">—</span> = not yet scored. Three independent scores, never blended. Ranked by __DOMAIN_LABEL__ fit; click any column header to sort. Status reflects <code>app_status</code> in each profile's frontmatter — update it with <code>/track</code>.</p>
  <p class="note" id="threshold"></p>
</div>
<script>
const DATA = __PAYLOAD__;
const S = DATA.stats;
function scoreClass(n){return n>=75?'s-strong':n>=50?'s-mod':n>=30?'s-weak':'s-reach';}
// A skill score of -1 means "not applicable" (companies and research groups advertise no
// requirements, so there is nothing to match against). 0 is a real score meaning "no
// overlap" — the two must never render the same way.
function scoreCell(n){return (n==null||n<0)?'<span class="tier">—</span>'
  :'<span class="score '+scoreClass(n)+'">'+n+'</span>';}
function levelCell(r){
  if(!r.level)return '<span class="tier">—</span>';
  const c={realistic:'var(--strong)',reach:'var(--mod)',below:'var(--sub)'}[r.level]||'var(--sub)';
  return '<span class="badge" style="border-color:'+c+';color:'+c+'">'+r.level+'</span>';
}
// Wet lab in the seat (bench_load). A view, never a score: the colours only make the
// substantial rows easy to spot, and the hide toggle only filters the Positions and PhD tabs.
function benchCell(r){
  if(!r.bench)return '<span class="tier">—</span>';
  const c={substantial:'var(--weak)',light:'var(--mod)'}[r.bench]||'var(--sub)';
  return '<span class="badge" style="border-color:'+c+';color:'+c+'">'+r.bench+'</span>';
}
// Remembered per browser; storage can be missing (private window, file:// quirks), so every
// access is guarded and the page works without it.
let hideBench=false;
try{hideBench=localStorage.getItem('hideBench')==='1';}catch(e){}
function setHideBench(v){hideBench=v;try{localStorage.setItem('hideBench',v?'1':'0');}catch(e){}render();tabs();}
function benchOk(r){return !(hideBench&&r.bench==='substantial');}
// Visibility is decided once, in Python (_shown), and stamped on each record as r.shown:
// companies/groups always; position/phd only when alive AND at least one score reaches
// MIN_SCORE_SHOWN. Read the flag here rather than recomputing it, so the two halves cannot
// drift.
function appBadge(r){
  const m={cv_generated:['CV ready','b-cv'],sent:['sent','b-sent'],interviewing:['interviewing','b-interviewing'],closed:['closed','b-closed']};
  let out='';
  if(r.app_status&&r.app_status!=='not_started'&&m[r.app_status]){out='<span class="badge '+m[r.app_status][1]+'">'+m[r.app_status][0]+'</span>';}
  if(r.app_outcome){const o={offer:'b-offer',rejected:'b-rejected'}[r.app_outcome]||'b-closed';out+=' <span class="badge '+o+'">'+r.app_outcome+'</span>';}
  if(r.lead_status==='closed'||r.lead_status==='expired'){out+=' <span class="badge b-closed">role '+r.lead_status+'</span>';}
  return out||'<span class="badge">—</span>';
}
function dl(r){
  if(r.deadline_in===null||r.deadline==='')return '<span class="dl-ok">—</span>';
  const c=r.deadline_in<=14?'dl-soon':'dl-ok';
  return '<span class="'+c+'">'+r.deadline+' ('+r.deadline_in+'d)</span>';
}
function linkCell(r){
  const s=r.url_status||'unchecked';
  const col={working:'var(--strong)',unverified:'var(--mod)',dead:'var(--reach)',
             unresolved:'var(--mod)',unchecked:'var(--sub)'}[s]||'var(--sub)';
  const old=(r.eval_age!=null&&r.eval_age>45);
  const age=(r.eval_age!=null)?(' <span class=\"tier\" style=\"color:'+(old?'var(--mod)':'var(--sub)')+'\">'+r.eval_age+'d</span>'):'';
  // Staleness rides on the link column because it is the same question: does this posting
  // still exist? No deadline means expire_sweep can never retire it, so nothing else asks.
  const st=r.stale
   ? ' <span class="badge" style="border-color:var(--mod);color:var(--mod)" title="No deadline and '
     +r.age+' days old — past the age limit, should already have been retired. Run expire_sweep.py.">'
     +'⚠ overdue '+r.age+'d</span>'
   : '';
  return '<span class=\"badge\" style=\"border-color:'+col+';color:'+col+'\">'+s+'</span>'+age+st;
}
function evalCell(r){
  if(r.eval_age==null)return '<span class=\"tier\">—</span>';
  const stale=r.eval_age>90;
  return '<span class=\"tier\" style=\"color:'+(stale?'var(--mod)':'var(--sub)')+'\">'+(r.last_evaluated||'')+' ('+r.eval_age+'d)</span>';
}
const TABS=[
 {id:'home',label:'Home'},
 {id:'stats',label:'Statistics'},
 {id:'timeline',label:'Timeline'},
 {id:'todo',label:'To-do'},
 {id:'applications',label:'Applications'},
 {id:'company',label:'Companies'},
 {id:'group',label:'Research Groups'},
 {id:'position',label:'Positions'},
 {id:'phd',label:'PhD'},
];
// Which tab a record belongs to. Positions/PhD are the CAREER track; everything the skill
// search found sits in its own tab, so the headline counts keep meaning "on-direction
// pipeline". Companies and groups are never split -- those are browsed to pick a
// cold-outreach target, not worked top-down like a lead list.
function inTab(r,id){
  return r.category===id;
}
const NAME=__NAME_JS__, GEN_DATE='__DATE__';
let active='home', sortKey='domain', sortDir=-1;
function tabs(){
  // Home has its own button in the header; on Home itself the icons are the navigation.
  if(active==='home'){renderHome();return;}
  document.getElementById('tabs').innerHTML=TABS.filter(t=>t.id!=='home').map(t=>
   '<div class="tab'+(t.id===active?' active':'')+'" onclick="setTab(\\''+t.id+'\\')">'+t.label+
   (t.id!=='home'&&t.id!=='stats'?' <span class="tier">'+countFor(t.id)+'</span>':'')+'</div>').join('');
}
function countFor(id){
  if(id==='timeline'||id==='todo')return planCount(id);
  if(id==='applications')return DATA.records.filter(r=>r.app_status&&r.app_status!=='not_started').length;
  return DATA.records.filter(r=>inTab(r,id)&&r.shown&&benchOk(r)).length;
}
function setTab(id){active=id;sortKey=(id==='applications')?'app_status':'domain';sortDir=(id==='applications')?1:-1;render();tabs();}
function rowsFor(){
  // Applications stays a complete history — the score filter deliberately does not apply
  // there, so a role that was actually worked on never vanishes from the record.
  let rows=(active==='applications')
   ? DATA.records.filter(r=>r.app_status&&r.app_status!=='not_started')
   : DATA.records.filter(r=>inTab(r,active)&&r.shown&&benchOk(r));
  const q=document.getElementById('filter').value.toLowerCase();
  if(q)rows=rows.filter(r=>(r.name+' '+r.org+' '+r.role+' '+r.location+' '+r.tier).toLowerCase().includes(q));
  rows.sort((a,b)=>{let x=a[sortKey],y=b[sortKey];
    if(typeof x==='number'||typeof y==='number'){x=+x||0;y=+y||0;return (x-y)*sortDir;}
    return String(x||'').localeCompare(String(y||''))*sortDir;});
  return rows;
}
function th(label,key){return '<th onclick="setSort(\\''+key+'\\')">'+label+(sortKey===key?(sortDir>0?' ▲':' ▼'):'')+'</th>';}
function setSort(k){if(sortKey===k)sortDir*=-1;else{sortKey=k;sortDir=(k==='domain'||k==='skill'||k==='method')?-1:1;}render();}
function render(){
  // Home is the OS-style entry page (home.js); it carries the integrity check in its tray.
  document.body.classList.toggle('at-home',active==='home');
  if(active==='home'){renderHome();return;}
  document.getElementById('filter').parentNode.classList.toggle('hidden',active==='stats');
  document.getElementById('benchctl').classList.toggle('hidden',active!=='position'&&active!=='phd');
  document.getElementById('hidebench').checked=hideBench;
  if(active==='stats'){renderStats();return;}
  if(active==='timeline'){renderTimeline();return;}
  if(active==='todo'){renderTodo();return;}
  const rows=rowsFor();
  const isPos=(active==='position'||active==='phd'||active==='applications');
  // Domain and Method on every row; Skill and Level only where a job description exists to
  // match against. Three columns, never a blend — see the MIN_SCORE_SHOWN note in dashboard.py.
  let head='<tr>'+th(DATA.label,'domain')+th('Method','method')+(isPos?th('Skill','skill')+th('Level','level')+th('Wet lab','bench_rank'):'')+
           th(active==='applications'?'Org / Role':'Name','name');
  if(active==='applications')head+=th('Status','app_status')+th('CV','cv_date')+th('Sent','sent_date')+th('Next action','next_action')+th('Deadline','deadline_in');
  else{head+=th('Location','location')+th('Tier','tier');
    if(isPos)head+=th('Deadline','deadline_in')+th('Lead','lead_status')+th('Link · age','eval_age');
    else head+=th('Evaluated','eval_age');
    head+=th('Status','app_status');}
  head+='</tr>';
  const body=rows.map(r=>{
    const nm='<a href="'+r.path+'">'+(r.name||r.org)+'</a>'+(r.role&&active!=='applications'&&!isPos?'':'')+
             (isPos&&r.org?'<div class="tier">'+r.org+'</div>':'');
    let tr='<tr><td>'+scoreCell(r.domain)+'</td><td>'+scoreCell(r.method)+'</td>'+
           (isPos?'<td>'+scoreCell(r.skill)+'</td><td>'+levelCell(r)+'</td><td>'+benchCell(r)+'</td>':'');
    if(active==='applications'){
      tr+='<td><a href="'+r.path+'">'+(r.org||r.name)+'</a><div class="tier">'+(r.role||r.category)+'</div></td>'+
          '<td>'+appBadge(r)+'</td><td>'+(r.cv_date||'—')+'</td><td>'+(r.sent_date||'—')+'</td>'+
          '<td>'+(r.next_action||'—')+'</td><td>'+dl(r)+'</td>';
    } else {
      tr+='<td>'+nm+'</td><td>'+(r.location||'—')+'</td><td class="tier">'+(r.tier||'—')+'</td>';
      if(isPos)tr+='<td>'+dl(r)+'</td><td class="tier">'+(r.lead_status||'—')+'</td><td>'+linkCell(r)+'</td>';
      else tr+='<td>'+evalCell(r)+'</td>';
      let st=appBadge(r);
      if(active==='company'||active==='group'){
        // Two different facts, deliberately both shown and labelled:
        //   applied      — the last CV actually SENT to a role at this employer
        //   last contact — the last unsolicited approach, from the profile's own frontmatter
        if(r.applied_count){
          const n=r.applied_count>1?' · '+r.applied_count+' roles':'';
          const tip=(r.applied_roles||[]).map(x=>x.date+'  '+x.role+(x.outcome?' ('+x.outcome+')':'')).join('\\n');
          const lbl=r.last_applied?('applied '+r.last_applied+n):('applied · date not recorded'+n);
          st+='<div class="tier applied" title="'+tip.replace(/"/g,'&quot;')+'">'+lbl+'</div>';
        }
        const cd=[r.last_contact,r.sent_date].filter(Boolean).sort().pop();
        if(cd)st+='<div class="tier">last contact '+cd+'</div>';
        // only claim "never applied" when nothing at all is on record — a CV-ready badge
        // with "never applied" underneath reads as a contradiction
        if(!r.applied_count&&!cd&&(!r.app_status||r.app_status==='not_started'))
          st+='<div class="tier" style="opacity:.5">never applied</div>';
      }
      tr+='<td>'+st+'</td>';
    }
    return tr+'</tr>';
  }).join('');
  document.getElementById('table').innerHTML='<table><thead>'+head+'</thead><tbody>'+body+'</tbody></table>'+
    '<p class="note">'+rows.length+' rows</p>';
}
function thresholdNote(){
  const el=document.getElementById('threshold');if(!el)return;
  let t='Position and PhD statistics, tabs and plan deadlines count only <b>live leads '
    +'reaching '+S.min_fit_shown+' on at least one score</b> — a lead is hidden only when it is '
    +'both off-direction <i>and</i> out of reach. '
    +S.hidden_low+' live lead(s) below '+S.min_fit_shown+' on <i>both</i> scores are kept on disk in '
    +'<code>positions/</code> and excluded from view. Companies and groups are never hidden by score; '
    +'the Applications tab shows the full history regardless.';
  if(S.unscored)t+=' <b style="color:var(--mod)">⚠ '+S.unscored+' record(s) are missing a score</b> '
    +'— <code>python engine/tools/doctor.py</code> lists them; score them with <code>/inbox</code>. '
    +'Until then a blank cell does not mean zero.';
  if(S.stale)t+=' <b style="color:var(--mod)">⚠ '+S.stale+' lead(s) are past the '+S.stale_days
    +'-day age limit and should already have been retired</b> — <code>expire_sweep.py</code> retires '
    +'deadline-less leads on age, and /dashboard runs it as step 1, so this normally reads zero. '
    +'Run <code>python engine/tools/expire_sweep.py</code>.';
  if(S.positive_all>S.positive)t+=' <b>On-direction (≥'+S.on_direction+')</b> counts the '+S.positive+' live record(s) '
    +'you can act on; '+(S.positive_all-S.positive)+' more scored ≥'+S.on_direction+' but are expired, closed or '
    +'age-retired ('+S.positive_all+' lifetime).';
  el.innerHTML=t;
}
__PLAN_JS__
__STATS_JS__
__HOME_JS__
tabs();thresholdNote();render();planInit();
</script></body></html>"""

payload_json = json.dumps(payload).replace("</", "<\\/")  # keep inline <script> safe
# The plan tabs' code lives beside this file rather than in the string above: it is long, and in a
# Python string every JS backslash would need doubling.
def _asset(name):
    with open(os.path.join(str(TOOLS), "web", name), encoding="utf-8") as f:
        return f.read().replace("</script", "<\\/script")
_name = html.escape(user_name())  # from user/profile/snapshot.md; the header just omits it if unset
out = (HTML.replace("__PLAN_CSS__", _asset("plan.css")).replace("__PLAN_JS__", _asset("plan.js"))
       .replace("__STATS_CSS__", _asset("stats.css")).replace("__STATS_JS__", _asset("stats.js"))
       .replace("__HOME_CSS__", _asset("home.css")).replace("__HOME_JS__", _asset("home.js"))
       .replace("__NAME_JS__", json.dumps(_name).replace("</", "<\\/"))
       .replace("__PAYLOAD__", payload_json).replace("__DOMAIN_LABEL__", html.escape(LABEL)).replace("__DATE__", TODAY.isoformat())
       .replace("__TITLE_NAME__", f" — {_name}" if _name else "")
       .replace("__META_NAME__", f"{_name} · " if _name else ""))
outpath = os.path.join(str(ARTIFACTS), "dashboard.html")
with open(outpath, "w", encoding="utf-8") as f:
    f.write(out)

print(f"Dashboard written: {outpath}")
print(f"  shown: {sum(1 for r in records if r['shown'])} of {len(records)} records "
      f"(companies {by_cat['company']} · groups {by_cat['group']} · positions {by_cat['position']} · phd {by_cat['phd']})")
print(f"  hidden: {hidden_low} live lead(s) below {MIN_SCORE_SHOWN} on all three scores "
      f"(kept on disk, excluded from every count)")
print(f"  search_results {stats['search_results']} · on-direction {positive} · CVs gen {stats['cvs_generated']} · sent {cvs_sent} · ongoing {ongoing}")
if stats["stale"]:
    print(f"  ⚠ overdue: {stats['stale']} lead(s) past the {stats['stale_days']}-day age limit are still "
          f"in open/ — run: python engine/tools/expire_sweep.py")
if unscored:
    print(f"  [!] {unscored} record(s) missing a score — python engine/tools/doctor.py lists them; "
          f"score them with /inbox")
print(f"  plan: {len(plan_doc['items'])} item(s) of your own + {len(plan_derived)} from records "
      f"(edit them: python engine/tools/serve.py)")
if plan_error:
    print(f"  [!] {plan_error}")
if integrity:
    print(f"  [!] integrity: {len(integrity)} issue(s):")
    for x in integrity:
        print(f"      [{x['kind']}] {x['msg']}")
else:
    print("  [OK] integrity: no tracking inconsistencies")
