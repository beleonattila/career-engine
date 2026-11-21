#!/usr/bin/env python3
"""
link_check.py — verify that position leads still point at a live posting.

Stdlib only. Run from the repo root.

    python engine/tools/link_check.py                     # report only, nothing is written
    python engine/tools/link_check.py --apply             # stamp url_status/url_checked, archive dead leads
    python engine/tools/link_check.py --min-fit 0         # check every lead, not just the dashboard-visible ones
    python engine/tools/link_check.py --only cradle       # check leads whose filename contains "cradle"

    # record what the built-in browser pane showed for ONE lead (no fetch; writes at once)
    python engine/tools/link_check.py --browser dead --only <file-stem> --why "LinkedIn: No longer accepting applications"
    python engine/tools/link_check.py --browser live --only <file-stem> --why "Apply button shown"

WHY THIS EXISTS
---------------
A naive "does the URL return 200?" check is actively misleading on the two surfaces
that dominate this vault:

  * **LinkedIn `ad-library/job/detail/<id>` returns HTTP 200 for dead postings.**
    Measured 2026-08-16: of 24 LinkedIn leads that all returned 200, **16 were dead**.
    This tool always re-checks LinkedIn leads against the canonical
    `linkedin.com/jobs/view/<id>` page, which catches the *redirect* form of expiry
    (`trk=expired_jd_redirect`). That is how those 16 were found.

    ⚠️ **But the canonical page does NOT reliably tell the truth to a bot, and this
    tool therefore never reports a LinkedIn lead as ALIVE.** Re-measured 2026-08-16
    against a Genmab posting a human had just seen marked "No longer accepting
    applications": the fetched page was 233KB of full job description with NO expiry
    text, no redirect, no `validThrough`, no job-state field, and was byte-for-byte
    indistinguishable in kind from three other LinkedIn leads. LinkedIn gates the
    expiry banner behind authentication: a real but logged-out browser was tested too
    and showed neither an expiry marker nor an apply affordance on live and dead
    postings alike. An earlier version called that ALIVE and stamped
    `url_status: working` on a dead lead the same day.

    Consequence: LinkedIn leads resolve to DEAD (explicit signal) or UNVERIFIED
    (everything else). UNVERIFIED here means "open it in a logged-in browser" — the
    desktop app's built-in browser pane, signed in to LinkedIn (engine/docs/LINK_HEALTH.md
    §Browser pass) — not "probably fine". Record what it showed with --browser.

  * **A 404 is not proof.** CLAUDE.md's link-hygiene rule: a link an automated fetch
    refuses is *unverified, not dead*. So a bare 404 is reported as DEAD_UNCONFIRMED
    and is **never auto-archived**; it is listed for you to confirm in a real browser,
    then record with --browser dead (one lead) or --trust-404 (all of them).
    Only unambiguous evidence (HTTP 410 Gone, an explicit "no longer available"
    message, or LinkedIn's expiry redirect) counts as DEAD.

VERDICTS
--------
  ALIVE             posting fetched and looks live
  DEAD              unambiguous: 410 Gone, explicit gone-message, or LinkedIn expiry
                    -> --apply archives these
  DEAD_UNCONFIRMED  404 only. Confirm in a browser, then record with --browser dead,
                    or re-run with --trust-404
  UNVERIFIED        403 / 429 / timeout / JS-rendered shell / ANY LinkedIn lead without an
                    explicit dead signal — no conclusion possible, needs a real browser
  UNRESOLVED        the stored url is a search page or job board root, not a posting,
                    so liveness cannot be established from it at all
  NO_URL            no url in frontmatter

WHAT --apply WRITES
-------------------
  ALIVE       -> url_status: working    · url_checked: today
  UNRESOLVED  -> url_status: unresolved · url_checked: today
  DEAD        -> url_status: dead · status: expired · expired_on: today
                 + a dated line under ## Notes recording how it was verified,
                 then moved positions/open/ -> positions/closed/

--browser dead|live writes the same fields for the single lead --only names, with
"browser pane: <--why>" as the Notes reason. It needs --only matching exactly one lead
in open/ or applied/, and ignores --min-fit: a verdict seen in a browser stands
whatever the lead scores.

Leads that are applied/sent/interviewing/offer are never touched, and nothing is
ever deleted — an archived lead stays on disk for dedup_check.py and the
miss-attribution telemetry, exactly as expire_sweep.py leaves it.
"""

import argparse
import csv
import datetime as dt
import gzip
import re
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from paths import REPO, WORKSPACE as ROOT, setting  # noqa: E402 — records are relative to user/workspace/
from frontmatter import fm_fields  # noqa: E402
OPEN, APPLIED, CLOSED = (ROOT / "positions" / "open",
                         ROOT / "positions" / "applied",
                         ROOT / "positions" / "closed")
LOGS = ROOT / "logs"
TODAY = dt.date.today().isoformat()


# An active application is not a stale lead — same guard as expire_sweep.py
PROTECTED = {"applied", "sent", "interviewing", "offer"}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9,da;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# Specific on purpose. Bare "expired" or "not found" false-positive on page furniture
# (cookie banners, "your session has expired", nav links), which would archive live leads.
GONE_MARKERS = [
    # "no longer accept" covers accepts/accepting/accepted. NOTE: the literal "no longer
    # accepting" was ALREADY here and was never the cause of the missed Genmab lead — that
    # text simply never reaches an unauthenticated fetch (see check_linkedin). This broader
    # form is cheap insurance for other boards, not a bug fix.
    # Do NOT shorten to bare "no longer": Bayer's careers copy contains "hunger for none is
    # no longer a dream", which would archive a live lead.
    "no longer available", "no longer accept", "no longer active",
    "no longer being accepted", "no longer open", "no longer exists",
    "this job is closed", "job is no longer", "position has been filled",
    "position is filled", "position is no longer", "role is no longer",
    "vacancy is closed", "vacancy has closed", "vacancy has expired",
    "closed for applications", "applications are closed",
    "application deadline has passed", "this posting has expired",
    "job posting has expired", "advert has expired", "job has expired",
    "opportunity has expired", "job not found", "this job posting is no longer",
    "sorry, this job", "recruitment for this position has closed",
    "stillingen er udløbet", "ansøgningsfristen er udløbet",  # da
]
LIVE_HINTS = [
    "apply now", "apply for this", "submit your application", "application deadline",
    "job description", "responsibilities", "qualifications", "what you will do",
    "søg stillingen", "ansøgningsfrist", "easy apply", "apply on company website",
    "seniority level", "employment type", "job function",
]
# stored url points at a board/search surface rather than one posting
BOARD_PATTERNS = [
    r"/search-jobs/?$", r"/search/?$", r"/careers/?$", r"/jobs/?$",
    r"/vacancies/?$", r"/all-vacancies/?$", r"/open-positions/?$", r"/recruitment/?$",
    r"/career/?$", r"/joinus/?$", r"/positions/?$",
]
# ...unless the query string carries the posting's own id. Greenhouse-on-own-domain
# (`/open-positions?gh_jid=…`) and KU (`/all-vacancies/?show=…`) both look like board
# roots by path alone but address exactly one posting.
JOB_ID_PARAMS = re.compile(
    r"(?:^|[?&])(gh_jid|jobid|job_id|jid|reqid|req_id|requisition|show|vacancyid|"
    r"vacancy_id|positionid|id|jobno|job)=([A-Za-z0-9_\-]{3,})", re.I)


# ------------------------------------------------------------------ frontmatter
def set_field(text, name, value):
    if re.search(rf"^{name}:.*$", text, re.M):
        return re.sub(rf"^{name}:.*$", f"{name}: {value}", text, count=1, flags=re.M)
    return re.sub(r"^---\s*$", f"---\n{name}: {value}", text, count=1, flags=re.M)


def as_int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ fetching
def fetch(url, timeout=25):
    """-> (code|None, final_url, body). code None means a transport-level failure."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            raw = r.read(400_000)
            if r.headers.get("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            return r.getcode(), r.geturl(), raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read(200_000).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, url, body
    except Exception as e:
        return None, url, f"__ERR__{type(e).__name__}: {str(e)[:120]}"


def gone_marker(body):
    low = body.lower()
    return next((g for g in GONE_MARKERS if g in low), "")


def looks_live(body):
    low = body.lower()
    return any(h in low for h in LIVE_HINTS)


def linkedin_job_id(url):
    if "linkedin.com" not in url:
        return None
    m = re.search(r"/(?:job/detail|jobs/view)/(?:[a-z0-9\-]*?-)?(\d{6,})", url)
    return m.group(1) if m else None


def is_board_url(url):
    """True when the url addresses a board/search surface rather than one posting."""
    parts = url.split("?", 1)
    query = parts[1] if len(parts) > 1 else ""
    if JOB_ID_PARAMS.search(query):
        return False          # the query pins one posting — not a board
    path = re.sub(r"^https?://[^/]+", "", parts[0])
    return any(re.search(p, path) for p in BOARD_PATTERNS)


# ------------------------------------------------------------------ classify
def check_generic(lead):
    url = lead["url"]
    if not url.startswith(("http://", "https://")):
        return dict(lead, verdict="NO_URL", code="", why="no url in frontmatter", final="")
    if is_board_url(url):
        return dict(lead, verdict="UNRESOLVED", code="", final=url,
                    why="url is a board/search root, not a single posting")

    code, final, body = fetch(url)

    if code is None:
        return dict(lead, verdict="UNVERIFIED", code="", final=final,
                    why=body.replace("__ERR__", ""))
    if code == 410:
        return dict(lead, verdict="DEAD", code=code, final=final,
                    why="HTTP 410 Gone" + (f" + '{gone_marker(body)}'" if gone_marker(body) else ""))
    if code == 404:
        return dict(lead, verdict="DEAD_UNCONFIRMED", code=code, final=final,
                    why="HTTP 404 — confirm in a real browser before archiving")
    if code in (401, 403, 429, 999):
        return dict(lead, verdict="UNVERIFIED", code=code, final=final,
                    why="blocked/rate-limited — needs a real browser")
    if code >= 500:
        return dict(lead, verdict="UNVERIFIED", code=code, final=final, why="server error")

    mark = gone_marker(body)
    if mark:
        return dict(lead, verdict="DEAD", code=code, final=final, why=f"page says '{mark}'")
    if "expired_jd_redirect" in final:
        return dict(lead, verdict="DEAD", code=code, final=final, why="expired_jd_redirect")
    if is_board_url(final) and final.rstrip("/") != url.rstrip("/"):
        return dict(lead, verdict="DEAD", code=code, final=final,
                    why="redirected from the posting to a generic board page")
    if len(body) < 1500:
        return dict(lead, verdict="UNVERIFIED", code=code, final=final,
                    why=f"thin body ({len(body)}b) — JS-rendered, needs a browser")
    return dict(lead, verdict="ALIVE", code=code, final=final,
                why="" if looks_live(body) else "200 but no apply/description cue — spot-check")


def check_linkedin(lead, delay):
    """Re-check via the canonical job view. ad-library 200s are meaningless."""
    jid = linkedin_job_id(lead["url"])
    canonical = f"https://www.linkedin.com/jobs/view/{jid}/"
    code, final, body = fetch(canonical, timeout=30)
    time.sleep(delay)
    if code is None or code in (429, 999):
        return dict(lead, verdict="UNVERIFIED", code=code or "", final=canonical,
                    why="LinkedIn rate-limited — re-run later or check in a browser")
    if "expired_jd_redirect" in final:
        return dict(lead, verdict="DEAD", code=code, final=final, why="LinkedIn expired_jd_redirect")
    mark = gone_marker(body)
    if mark:
        return dict(lead, verdict="DEAD", code=code, final=canonical, why=f"LinkedIn: '{mark}'")
    if code in (404, 410):
        return dict(lead, verdict="DEAD", code=code, final=canonical, why=f"LinkedIn HTTP {code}")
    # NEVER return ALIVE from an unauthenticated LinkedIn fetch. Measured 2026-08-16 against a
    # posting the user had just seen marked "No longer accepting applications" in a browser: the
    # served HTML was 233KB, contained the full job description, "Seniority level", "Employment
    # type" and "Job function", carried NO expiry text of any kind, and did not redirect. It was
    # indistinguishable from three other LinkedIn leads. The expiry banner is rendered
    # client-side and never reaches this fetcher, and there is no validThrough or job-state
    # field in the markup to fall back on.
    #
    # So the only LinkedIn signals that mean anything here are the explicit dead ones handled
    # above (expired_jd_redirect, a gone marker on the landing page, 404/410). Absence of those
    # is NOT evidence of life. Saying ALIVE here is what stamped `url_status: working` on a dead
    # Genmab posting on the same day a human saw the expiry banner.
    return dict(lead, verdict="UNVERIFIED", code=code, final=canonical,
                why="LinkedIn served a page but liveness cannot be established without a "
                    "logged-in browser — expiry is client-side rendered")


# ------------------------------------------------------------------ collect
def collect(scope, min_fit, only):
    dirs = [OPEN]
    if scope in ("open+applied", "all"):
        dirs.append(APPLIED)
    if scope == "all":
        dirs.append(CLOSED)

    leads, skipped_low, skipped_dead = [], 0, 0
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            if only and only.lower() not in p.name.lower():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            fm = fm_fields(text)
            # Three scores since 2026-09-29 (method_fit joined domain_fit and skill_match),
            # checked with OR: a lead is worth re-validating if it is EITHER something the user
            # wants (domain_fit), OR the kind of work they want (method_fit), OR something they
            # could clearly do (skill_match). Requiring all would quietly stop link-checking
            # exactly the stretch roles the split exists to keep visible. `fit` below is the
            # higher of the two, used only for the report's sort order — never written back.
            domain = as_int(fm.get("domain_fit"))
            skill = as_int(fm.get("skill_match"))
            method = as_int(fm.get("method_fit"))
            fit = max(domain, skill, method)
            status = (fm.get("status") or "").lower()
            if fit < min_fit:
                skipped_low += 1
                continue
            if status in ("expired", "closed") and scope != "all":
                skipped_dead += 1
                continue
            leads.append({
                "path": p, "file": p.name, "fit": fit,
                "org": fm.get("organization") or "",
                "url": fm.get("url") or "",
                "status": status,
                "app_status": (fm.get("app_status") or "").lower(),
                "old_url_status": fm.get("url_status") or "unchecked",
            })
    return leads, skipped_low, skipped_dead


# ------------------------------------------------------------------ apply
def apply_results(results, trust_404):
    archived, stamped, blocked = [], [], []
    CLOSED.mkdir(parents=True, exist_ok=True)

    for r in results:
        p = r["path"]
        if not p.exists():
            continue
        verdict = r["verdict"]
        if trust_404 and verdict == "DEAD_UNCONFIRMED":
            verdict = "DEAD"
        text = p.read_text(encoding="utf-8", errors="replace")

        if verdict == "DEAD":
            if r["status"] in PROTECTED or r["app_status"] in PROTECTED:
                blocked.append((r["file"], r["status"] or r["app_status"]))
                continue
            text = set_field(text, "status", "expired")
            if not re.search(r"^expired_on:", text, re.M):
                text = re.sub(r"^status: expired$", f"status: expired\nexpired_on: {TODAY}",
                              text, count=1, flags=re.M)
            text = set_field(text, "url_status", "dead")
            text = set_field(text, "url_checked", TODAY)
            stamp = (f"⛔ **Link-checked dead {TODAY}** — {r['why']}. Retired to positions/closed/; "
                     f"record kept on disk for dedup and miss-attribution history.")
            text = (text.replace("## Notes", f"## Notes\n\n{stamp}", 1)
                    if "## Notes" in text else text.rstrip() + f"\n\n## Notes\n\n{stamp}\n")
            p.write_text(text, encoding="utf-8")
            dest = CLOSED / p.name
            if dest.exists():
                blocked.append((r["file"], "already in closed/"))
                continue
            if p.parent == OPEN:
                shutil.move(str(p), str(dest))
            archived.append((r["file"], r["why"]))

        elif verdict in ("ALIVE", "UNRESOLVED"):
            new_status = "working" if verdict == "ALIVE" else "unresolved"
            new = set_field(text, "url_status", new_status)
            new = set_field(new, "url_checked", TODAY)
            if new != text:
                p.write_text(new, encoding="utf-8")
            stamped.append((r["file"], new_status))
        # UNVERIFIED / DEAD_UNCONFIRMED / NO_URL: deliberately left untouched

    return archived, stamped, blocked


# ------------------------------------------------------------------ browser verdict
def record_browser_verdict(verdict, only, why):
    """Write one browser-pane verdict through apply_results, so a lead retired by eye
    gets exactly the fields, Notes line and move that an automatic DEAD gets."""
    if not only:
        sys.exit("--browser needs --only <file-stem> naming exactly one lead")
    if not why.strip():
        sys.exit("--browser needs --why: what the page showed (it goes into the Notes line)")
    leads, _, _ = collect("open+applied", 0, only)
    if len(leads) != 1:
        names = ", ".join(l["file"] for l in leads) or "none"
        sys.exit(f"--only {only!r} matched {len(leads)} lead(s) ({names}); it must match exactly one")
    lead = leads[0]
    result = dict(lead, verdict="DEAD" if verdict == "dead" else "ALIVE", code="browser",
                  final=lead["url"], why=f"browser pane: {why.strip()}")
    archived, stamped, blocked = apply_results([result], trust_404=False)
    if archived:
        print(f"retired  {lead['file']}  ({result['why']})")
    elif stamped:
        print(f"stamped  {lead['file']}  url_status: working, url_checked: {TODAY}")
    else:
        for n, reason in blocked:
            print(f"left in place  {n} — {reason}")


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Verify position-lead links are still live.")
    ap.add_argument("--apply", action="store_true",
                    help="write results back (stamp url_status, archive DEAD leads). "
                         "Default is report-only.")
    shown = setting("thresholds.min_score_shown")
    ap.add_argument("--min-fit", type=int, default=shown,
                    help="only check leads reaching this on ANY of domain_fit, "
                         f"method_fit or skill_match (default {shown}: thresholds.min_score_shown "
                         "in user/settings.toml, the dashboard's visibility bar)")
    ap.add_argument("--scope", choices=["open", "open+applied", "all"], default="open")
    ap.add_argument("--only", default="", help="substring filter on the lead filename")
    ap.add_argument("--no-linkedin", action="store_true",
                    help="skip the LinkedIn canonical re-check (faster, much less accurate)")
    ap.add_argument("--trust-404", action="store_true",
                    help="treat a bare 404 as DEAD. Only pass this after confirming in a browser.")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--linkedin-delay", type=float, default=4.0,
                    help="seconds between LinkedIn requests (they rate-limit hard)")
    ap.add_argument("--report", default=str(LOGS / "link_check_latest.tsv"))
    ap.add_argument("--browser", choices=["dead", "live"],
                    help="record a verdict seen in a logged-in browser for the ONE lead --only "
                         "matches; no fetch, writes immediately (see LINK_HEALTH.md §Browser pass)")
    ap.add_argument("--why", default="",
                    help="with --browser: what the page showed, quoted into the Notes line")
    args = ap.parse_args()

    if args.browser:
        record_browser_verdict(args.browser, args.only, args.why)
        return

    leads, low, dead = collect(args.scope, args.min_fit, args.only)
    if not leads:
        print("no leads to check"); return
    print(f"checking {len(leads)} lead(s)  "
          f"[scope={args.scope} min-fit={args.min_fit}; skipped {low} below fit, {dead} already retired]")

    li = [l for l in leads if linkedin_job_id(l["url"])] if not args.no_linkedin else []
    other = [l for l in leads if l not in li]

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(check_generic, other))

    if li:
        print(f"  re-checking {len(li)} LinkedIn lead(s) against the canonical job view "
              f"(ad-library 200s are meaningless)…")
        for i, lead in enumerate(li, 1):
            r = check_linkedin(lead, args.linkedin_delay)
            print(f"    {i:2d}/{len(li)} {r['verdict']:16s} {r['fit']:>3}  {r['file'][:58]}")
            results.append(r)

    order = {"DEAD": 0, "DEAD_UNCONFIRMED": 1, "UNRESOLVED": 2, "UNVERIFIED": 3,
             "NO_URL": 4, "ALIVE": 5}
    results.sort(key=lambda r: (order.get(r["verdict"], 9), -r["fit"]))

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        # "best_score" = max(domain_fit, method_fit, skill_match) — the number the --min-fit gate
        # uses. It orders the report; it is never written back to a profile.
        w.writerow(["verdict", "code", "best_score", "file", "why", "url", "final"])
        for r in results:
            w.writerow([r["verdict"], r["code"], r["fit"], r["file"], r["why"], r["url"], r["final"]])

    tally = {}
    for r in results:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print("\nresults:")
    for k in sorted(tally, key=lambda k: order.get(k, 9)):
        print(f"  {k:17s} {tally[k]}")
    for k in ("DEAD", "DEAD_UNCONFIRMED", "UNRESOLVED", "UNVERIFIED"):
        rows = [r for r in results if r["verdict"] == k]
        if rows:
            print(f"\n{k}:")
            for r in rows:
                print(f"    {r['fit']:>3}  {r['file'][:60]:60s} {r['why'][:70]}")
    print(f"\nreport: {args.report}")

    if not args.apply:
        n_dead = tally.get("DEAD", 0)
        print(f"\n[report only] nothing written. Re-run with --apply to stamp url_status "
              f"and archive {n_dead} DEAD lead(s).")
        if tally.get("DEAD_UNCONFIRMED"):
            print(f"              {tally['DEAD_UNCONFIRMED']} DEAD_UNCONFIRMED (bare 404) will NOT be "
                  f"archived — confirm in a browser first (CLAUDE.md link hygiene).")
        return

    archived, stamped, blocked = apply_results(results, args.trust_404)
    print(f"\napplied: archived {len(archived)} · stamped {len(stamped)}")
    for n, why in archived:
        print(f"    retired  {n[:60]:60s} {why[:60]}")
    if blocked:
        print("  left in place (active application or name clash):")
        for n, why in blocked:
            print(f"    {n} — {why}")
    print(f"\nopen/: {len(list(OPEN.glob('*.md')))} | closed/: {len(list(CLOSED.glob('*.md')))}")
    print("Re-run `python engine/tools/dashboard.py` to refresh the view.")


if __name__ == "__main__":
    main()
