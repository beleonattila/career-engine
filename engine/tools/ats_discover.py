#!/usr/bin/env python3
"""
ats_discover.py — one-time (re-runnable) ATS slug discovery for the company database.

Probes the public job-board endpoints of every company in organizations/companies/ and caches
which ATS + slug actually resolves. Writes user/workspace/cache/ats_slugs.tsv, which ats_sweep.py
then reads on every /search-positions run.

Standard library only. Safe to re-run: existing confirmed rows are kept unless --refresh.

Usage:
    python engine/tools/ats_discover.py              # probe only companies not already in the cache
    python engine/tools/ats_discover.py --refresh    # re-probe everything
    python engine/tools/ats_discover.py --only novo-nordisk,genmab
    python engine/tools/ats_discover.py --orc efzu.fa.em2.oraclecloud.com   # resolve an Oracle ORC host
"""

import concurrent.futures as cf
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from paths import REPO, WORKSPACE as ROOT, pack_data  # noqa: E402 — records are relative to user/workspace/
COMPANIES = ROOT / "organizations" / "companies"
CACHE = ROOT / "cache" / "ats_slugs.tsv"

UA = "Mozilla/5.0 (compatible; career-vault-ats-discovery/1.0)"
TIMEOUT = 8

# The boards that cannot be found by guessing are domain data, not code: they live in the domain
# pack that user/settings.toml selects (`search.pack`), in engine/packs/<pack>/ats_seeds.toml.
# Each table there says how its rows were verified. Add a board there, never here.
_SEEDS = pack_data("ats_seeds.toml")
WORKDAY_KNOWN = {k: (v["tenant"], v["site"], v["wd"]) for k, v in _SEEDS["workday"].items()}
WORKABLE_KNOWN = dict(_SEEDS["workable"])
ORACLE_KNOWN = {k: (v["host"], v["site"]) for k, v in _SEEDS["oracle"].items()}
CONFIRMED_BY_HAND = {k: (v["ats"], v["slug"]) for k, v in _SEEDS["confirmed_by_hand"].items()}
KNOWN_WRONG = {k: set(v) for k, v in _SEEDS["known_wrong"].items()}

# ATS probe definitions: (name, url_template, json_path_to_jobs)
PROBES = [
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{s}/jobs", "jobs"),
    ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{s}", "jobs"),
    ("lever", "https://api.lever.co/v0/postings/{s}?mode=json", None),
    ("smartrecruiters", "https://api.smartrecruiters.com/v1/companies/{s}/postings", "content"),
    ("recruitee", "https://{s}.recruitee.com/api/offers/", "offers"),
    ("workable", "https://apply.workable.com/api/v1/widget/accounts/{s}?details=true", "jobs"),
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# A bare first token ("novo", "eli", "nabla") collides with unrelated companies, so any hit
# from that variant must additionally look like an employer in the pack's domain. The terms are
# the pack's `board_check` (see ats_seeds.toml for why the guard exists).
LIFESCI = re.compile(_SEEDS["board_check"]["terms"], re.I)


def slug_variants(vault_slug):
    """Candidate ATS slugs, most likely first. Third element is collision-prone -> needs proof."""
    trusted = []
    for s in (vault_slug.replace("-", ""), vault_slug):   # generatebiomedicines, generate-biomedicines
        if s and s not in trusted and len(s) > 2:
            trusted.append(s)
    risky = vault_slug.split("-")[0]                      # "novo" -- only with a content check
    risky = [risky] if (risky not in trusted and len(risky) > 3) else []
    return [(s, False) for s in trusted] + [(s, True) for s in risky]


def looks_like_lifesci(jobs):
    """True if any posting on the board reads like a life-science employer."""
    for j in jobs[:40]:
        if not isinstance(j, dict):
            continue
        blob = " ".join(str(j.get(k, "")) for k in
                        ("title", "department", "team", "categories", "name", "jobFamily"))
        if LIFESCI.search(blob):
            return True
    return False


def probe_orc(host):
    """Resolve an Oracle Recruiting Cloud host -> (siteNumber, n_jobs), or None.

    ORC publishes its own site list at `recruitingCESites`, so only the host has to be found by
    hand; the site number (needed for public job links) is read off the tenant. A tenant usually
    carries several sites, most of them inactive -- pick the active one.
    """
    try:
        sites = fetch(f"https://{host}/hcmRestApi/resources/latest/recruitingCESites"
                      "?onlyData=true&limit=50").get("items", [])
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            json.JSONDecodeError, ConnectionError, OSError):
        return None
    cands = [s.get("SiteNumber") for s in sites if s.get("StatusCode") == "ORA_ACTIVE"]
    cands += [s.get("SiteNumber") for s in sites if s.get("StatusCode") != "ORA_ACTIVE"]
    for site in [c for c in cands if c]:
        finder = f"findReqs;siteNumber={site},limit=200,sortBy=POSTING_DATES_DESC"
        url = (f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
               "?onlyData=true&expand=requisitionList&finder="
               + urllib.parse.quote(finder, safe=""))
        try:
            items = fetch(url).get("items", [])
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError, ConnectionError, OSError):
            continue
        reqs = items[0].get("requisitionList", []) if items else []
        if reqs:
            return (site, len(reqs))
    return None


def probe_company(vault_slug):
    """Return (vault_slug, ats, ats_slug, n_jobs) for the first endpoint that resolves."""
    if vault_slug in CONFIRMED_BY_HAND:
        ats, aslug = CONFIRMED_BY_HAND[vault_slug]
        return (vault_slug, ats, aslug, -1, "ok")
    if vault_slug in ORACLE_KNOWN:
        host, site = ORACLE_KNOWN[vault_slug]
        return (vault_slug, "oracle_orc", f"{host}/{site}", -1, "ok")
    if vault_slug in WORKDAY_KNOWN:
        tenant, site, wd = WORKDAY_KNOWN[vault_slug]
        return (vault_slug, "workday", f"{tenant}/{site}/{wd}", -1, "ok")
    if vault_slug in WORKABLE_KNOWN:
        return (vault_slug, "workable", WORKABLE_KNOWN[vault_slug], -1, "ok")

    banned = KNOWN_WRONG.get(vault_slug, set())
    for cand, needs_proof in slug_variants(vault_slug):
        if cand in banned:
            continue
        for ats, tmpl, key in PROBES:
            try:
                data = fetch(tmpl.format(s=cand))
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                    json.JSONDecodeError, ConnectionError, OSError):
                continue
            jobs = data if key is None else (data.get(key) if isinstance(data, dict) else None)
            if not (isinstance(jobs, list) and len(jobs) > 0):
                continue
            if needs_proof and not looks_like_lifesci(jobs):
                # Real board, but the slug is collision-prone and the content does not prove
                # it is the right employer. Park it for a one-time human/LLM confirmation
                # rather than silently accepting (wrong data) or silently dropping (lost cover).
                return (vault_slug, ats, cand, len(jobs), "review")
            return (vault_slug, ats, cand, len(jobs), "ok")
    return (vault_slug, "", "", 0, "")


def orc_report(hosts):
    """Check candidate Oracle Recruiting Cloud hosts and print rows for the pack's [oracle] table.

    ORC hosts cannot be guessed, so this takes them as input: find an employer's careers page
    once (`*.fa.*.oraclecloud.com`, or the host a vanity careers domain redirects to) and hand
    it here. Everything after that -- site number, live requisition count -- is automatic.
    """
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for host, res in zip(hosts, ex.map(probe_orc, [h.strip() for h in hosts])):
            host = host.strip()
            if not res:
                print(f"  {host:<40} -> no ORC requisitions (wrong host, or board is empty)")
                continue
            site, n = res
            print(f"  {host:<40} -> {site} ({n} live roles)")
            print(f'      add to [oracle] in ats_seeds.toml:  <vault-slug> = {{ host = "{host}", site = "{site}" }}')


def load_cache():
    rows = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines()[1:]:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 5:
                rows[p[0]] = p
    return rows


def main():
    argv = sys.argv[1:]
    refresh = "--refresh" in argv
    skip_empty = "--skip-empty" in argv
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))

    all_slugs = sorted(p.stem for p in COMPANIES.glob("*.md"))
    # Always load the existing cache. --refresh means "re-probe", NOT "discard": starting from an
    # empty dict here combined with --only rewrote the TSV with just the requested rows and
    # silently dropped every other company (caught 2026-07-30).
    cache = load_cache()

    if "--orc" in argv:
        orc_report(argv[argv.index("--orc") + 1].split(","))
        return

    # Hand-found ORC boards are seeded straight into the cache: they are not necessarily
    # companies. DTU is a university with no organizations/companies/ file, so probe_company() is
    # never called for it, but the sweep still needs the row.
    seeded = []
    for vs, (host, site) in ORACLE_KNOWN.items():
        row = [vs, "oracle_orc", f"{host}/{site}", "-1", "ok"]
        if cache.get(vs) != row:
            cache[vs] = row
            seeded.append(vs)
    if seeded:
        print(f"Seeded {len(seeded)} Oracle ORC board(s): {', '.join(sorted(seeded))}")

    def needs_probe(s):
        if only is not None and s not in only:
            return False
        if refresh or s not in cache:
            return True
        # An empty row means "found nothing LAST time", which is often just a transient network
        # failure -- dyno-therapeutics was lost exactly this way. Retry empties by default.
        return cache[s][1] == "" and not skip_empty

    todo = [s for s in all_slugs if needs_probe(s)]
    if not todo and not seeded:
        print(f"Nothing to probe. Cache has {len(cache)} of {len(all_slugs)} companies.")
        return

    if todo:
        print(f"Probing {len(todo)} companies across {len(PROBES)} ATS x up to 3 slug "
              "variants...")
    found = 0
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for i, res in enumerate(ex.map(probe_company, todo), 1):
            vs, ats, aslug, n, status = res
            cache[vs] = [vs, ats, aslug, str(n), status]
            if ats:
                found += 1
                flag = "  <-- NEEDS REVIEW" if status == "review" else ""
                print(f"  [{i:>3}/{len(todo)}] {vs:<28} -> {ats}:{aslug} "
                      f"({n if n >= 0 else '?'} roles){flag}")
            elif i % 15 == 0:
                print(f"  [{i:>3}/{len(todo)}] ...")

    lines = ["vault_slug\tats\tats_slug\tn_jobs_at_discovery\tstatus"]
    for k in sorted(cache):
        lines.append("\t".join(cache[k]))
    CACHE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok = sum(1 for v in cache.values() if v[4] == "ok")
    review = sum(1 for v in cache.values() if v[4] == "review")
    print(f"\nWrote {CACHE.name}: {ok}/{len(cache)} confirmed endpoints "
          f"({found} resolved this run), {review} awaiting review.")
    if review:
        print("  Rows marked 'review' use a collision-prone short slug and are EXCLUDED from the")
        print("  sweep. Eyeball the board; if correct, add it to [confirmed_by_hand] in the pack's ats_seeds.toml and re-run.")
    print("Companies with no endpoint are not covered by ats_sweep.py and still need a "
          "manual/WebSearch check. Empty rows are retried automatically on the next run.")


if __name__ == "__main__":
    main()
