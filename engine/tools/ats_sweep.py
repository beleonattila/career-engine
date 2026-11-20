#!/usr/bin/env python3
"""
ats_sweep.py — bulk ATS sweep for /search-positions.

Fetches every confirmed employer job board from ats_slugs.tsv in one pass, normalises the
postings, flags relevance + geography (user/settings.toml [geography]), and marks anything whose org already has a tracked lead.
Pure HTTP + string matching: no LLM tokens are spent deciding what to look at.

Deliberately does NOT filter by posting age. Age is a sort key, never a discard rule --
see "Why age is not a filter" in engine/skills/search-positions-common.md. Dedup is by identity, not date.

Output: a compact TSV on stdout (and user/workspace/logs/ats_sweep_latest.tsv), newest first.
The LLM reads that table and makes the actual collect/skip call. Tiers T1..T2? are the career
track's; M / Mb (after them) are the skill track's method lane, assigned only to rows the career
tiers left untiered (search-positions-skill.md §Method lane).

Usage:
    python engine/tools/ats_sweep.py                 # tiered roles in the allowlist countries, newest first
    python engine/tools/ats_sweep.py --show-all      # also print tier '-' rows (the TSV always has them)
    python engine/tools/ats_sweep.py --all-geo       # include roles outside the allowlist
    python engine/tools/ats_sweep.py --all-roles     # skip the relevance prefilter (very noisy)
    python engine/tools/ats_sweep.py --max-age 60    # only roles published within N days (opt-in)
    python engine/tools/ats_sweep.py --no-body       # title-only tiering (skips description fetching)
    python engine/tools/ats_sweep.py --uncovered     # band-A employers with no working board (no sweep)
"""

import concurrent.futures as cf
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


from paths import REPO, WORKSPACE as ROOT, setting, user_toml  # noqa: E402 — records are relative to user/workspace/
CACHE = ROOT / "cache" / "ats_slugs.tsv"
OUT = ROOT / "logs" / "ats_sweep_latest.tsv"
TODAY = dt.date.today()
UA = "Mozilla/5.0 (compatible; career-vault-ats-sweep/1.0)"
TIMEOUT = 15
# Workday caps `limit` at 20 (25 -> HTTP 400), so a full board is paged. Amgen, the largest
# board in the cache, is 1716 requisitions = 86 pages. 200 is a runaway guard, not a budget.
WORKDAY_MAX_PAGES = 200
# "Generic title at a good-fit employer" (tier T2?) only carries information when the employer
# is small enough that its whole board is about one thing. See the T2? block in main().
T2Q_MAX_BOARD = 100
SR_MAX_PAGES = 40                                  # SmartRecruiters, 100/page

# What the sweep looks for is the user's, not the engine's: user/profile/search_terms.toml.
# [sweep] tier1 = a single match qualifies a lead, tier2 = two distinct matches qualify (the
# career track's tiers in search_terms.md, kept in step); maybe = the broad title prefilter;
# computational = a title that says "computational" without the domain, meaningful only
# alongside employer fit. [level] = Gate 4's over-level test (see over_level() below). The file
# carries the reasoning and the measurements behind each entry.
_TERMS = user_toml("profile/search_terms.toml")
TIER1 = re.compile(_TERMS["sweep"]["tier1"], re.I)
TIER2 = re.compile(_TERMS["sweep"]["tier2"], re.I)
MAYBE = re.compile(_TERMS["sweep"]["maybe"], re.I)
COMPUTATIONAL = re.compile(_TERMS["sweep"]["computational"], re.I)
# T2? needs the employer's career_fit at or above this (the user's threshold, in the same file).
T2Q_MIN_FIT = _TERMS["sweep"]["t2q_min_employer_fit"]
# The skill track's method lane ([sweep.method]): M = the title names a method-building seat,
# Mb = the role text says the seat builds tools for scientists. Only ever assigned to a row the
# career tiers left at '-', so T1..T2? counts are untouched. Optional: a terms file without the
# section simply produces no M rows.
_METHOD = _TERMS["sweep"].get("method", {})
M_TITLE_STRONG = re.compile(_METHOD["title_strong"], re.I) if _METHOD else None
M_TITLE = re.compile(_METHOD["title"], re.I) if _METHOD else None
M_BODY_BUILD = re.compile(_METHOD["body_build"], re.I) if _METHOD else None
M_BODY_USERS = re.compile(_METHOD["body_users"], re.I) if _METHOD else None
# The M? tier's title test: the weak method titles as whole words ("Bioengineer / Molecular
# Biologist" is not an engineer seat), minus corporate functions. Measured 2026-10-10: without
# these, a sighted employer's application-support and security engineers came through as M?.
M_TITLE_WORD = re.compile(r"\b(?:%s)" % _METHOD["title"], re.I) if _METHOD else None
M_CORPORATE = re.compile(r"(?i:\b(security|support|help ?desk|service desk|sales|field service"
                         r"|facilities|workplace)\b)|\bIT\b")
# Roles that are never a fit regardless of keyword noise.
EXCLUDE = re.compile(
    r"\b(sales|account executive|marketing|recruit|talent|people ops|hr\b|finance|"
    r"accounting|legal|counsel|procurement|facilities|administrative assistant|"
    r"executive assistant|office manager|customer success|business development)\b", re.I)
# Gate 4 (level): title words above the user's level; phd_call exempts a doctoral advert (there
# the level word names the supervisor); optional_level strips a "(Senior)"-style marker, which is
# an offer rather than a bar.
OVERLEVEL = re.compile(_TERMS["level"]["overlevel"], re.I)
PHD_CALL = re.compile(_TERMS["level"]["phd_call"], re.I)
OPTIONAL_LEVEL = re.compile(_TERMS["level"]["optional_level"], re.I)


def over_level(title):
    """True if the title is above the user's level (search_terms.toml [level]).

    A title offering a non-over-level alternative passes: "(Senior) Scientist" and "Machine
    Learning Scientist / Senior ML Scientist" are both open at the lower level, while
    "Senior / Lead Scientist" is not. Checked against the vault 2026-08-09 -- without this,
    six genuinely attainable two-level postings were being dropped.
    """
    if PHD_CALL.search(title):
        return False                       # in a PhD advert the level word names the supervisor
    t = OPTIONAL_LEVEL.sub(" ", title)
    alts = [x for x in re.split(r"\s*/\s*", t) if x.strip()]
    return all(OVERLEVEL.search(x) for x in alts) if alts else False

# Where a posting may be is the user's choice: the country blocks in user/settings.toml
# [geography]. This is the engine's half -- a gazetteer from each country to the words an ATS
# location string uses for it (the country, its cities, its biotech hubs). A country in scope
# with no entry here cannot be recognised, so its postings would be dropped; doctor.py and the
# sweep's own summary line both name any such country.
PLACES = {
    "Denmark": "denmark|copenhagen|københavn|lyngby|bagsværd|hillerød|hørsholm|måløv|kalundborg|"
               "roskilde|odense|aarhus|århus|aalborg|søborg|ballerup",
    "Sweden": "sweden|stockholm|gothenburg|göteborg|lund|uppsala|malmö|solna",
    "Norway": "norway|oslo|trondheim|bergen",
    "Finland": "finland|helsinki|espoo",
    "Iceland": "iceland|reykjavik",
    "Netherlands": "netherlands|amsterdam|utrecht|delft|leiden|nijmegen|wageningen|maastricht|"
                   "rotterdam|oss\\b",
    "Belgium": "belgium|brussels|leuven|ghent|gent|mechelen|zwijnaarde",
    "Germany": "germany|berlin|munich|münchen|heidelberg|frankfurt|hamburg|cologne|köln|wuppertal|"
               "tübingen|penzberg|darmstadt",
    "Switzerland": "basel|zurich|zürich|geneva|genève|lausanne|switzerland",
    "Austria": "austria|vienna|wien|graz",
    "France": "france|paris|lyon|toulouse|strasbourg",
    "Spain": "spain|madrid|barcelona|valencia",
    "Italy": "italy|milan|rome|siena",
    "Portugal": "portugal|lisbon|porto",
    "Ireland": "ireland|dublin",
    "Poland": "poland|warsaw|krakow",
    "Czechia": "czech|prague",
    "United Kingdom": "united kingdom|\\buk\\b|\\bgb\\b|london|cambridge|oxford|stevenage|slough|"
                      "hertfordshire|manchester|edinburgh|glasgow|scotland|wales|england|britain",
    "Hungary": "hungary|budapest",
    "Greece": "greece|athens",
    "Romania": "romania", "Bulgaria": "bulgaria", "Slovenia": "slovenia", "Slovakia": "slovakia",
    "Croatia": "croatia", "Serbia": "serbia", "Luxembourg": "luxembourg", "Estonia": "estonia",
    "Latvia": "latvia", "Lithuania": "lithuania", "Malta": "malta", "Cyprus": "cyprus",
    "Liechtenstein": "liechtenstein",
}
# 'remote'/'europe'/'emea' are region *hints*, not places: they are what lets a US posting
# ("United States - Remote") slip through the geography filter. Kept as a weaker signal.
HINTS = "europe|emea|remote"
# Explicit non-European anchors. Only consulted when the sole in-scope signal was a hint:
# "Remote; Watertown, Massachusetts" is not a European role; "London; Montréal" is.
NON_EU = re.compile(
    r"\b(united states|usa|u\.s\.a?\.|canada|india|china|japan|singapore|australia|brazil|"
    r"mexico|israel|south africa|korea|taiwan|new zealand|argentina|chile|colombia|"
    r"california|massachusetts|new york|new jersey|texas|washington|maryland|georgia|"
    r"north carolina|south carolina|pennsylvania|illinois|florida|ohio|michigan|"
    r"minnesota|indiana|missouri|connecticut|utah|colorado|arizona|"
    r"hyderabad|bangalore|bengaluru|mumbai|chennai|pune|shanghai|beijing|suzhou|shenzhen|"
    r"tokyo|osaka|seoul|toronto|vancouver|montréal|montreal|quebec|ontario|"
    r"san francisco|south san francisco|boston|cambridge, ma|seattle|san diego|"
    r"emeryville|watertown|thousand oaks|gaithersburg|rahway|tarrytown|lajolla|la jolla)\b",
    re.I)


def geo_scope():
    """(in-scope regex, in-scope-or-hint regex, blocks, unknown countries) from user/settings.toml.

    Only blocks without `remote_only` count: whether an ad accepts remote work is in its text,
    and the sweep reads a location string. Built on demand, not at import, so level_sweep.py can
    import over_level() without caring about geography.
    """
    blocks = [b for b in setting("geography.block") if not b.get("remote_only")]
    countries = [c for b in blocks for c in b["countries"]]
    unknown = [c for c in countries if c not in PLACES]
    words = "|".join(PLACES[c] for c in countries if c in PLACES)
    strict = re.compile(words, re.I) if words else None
    loose = re.compile(words + "|" + HINTS if words else HINTS, re.I)
    return strict, loose, [b["name"] for b in blocks], unknown


def in_scope(loc, strict, loose):
    """True if the posting is plausibly in an in-scope country. Empty location -> keep (unknown).

    Evaluated per location segment, because ATS location strings are frequently multi-site
    ("London; Montréal, Quebec" is a European role; "Remote; Watertown, Massachusetts" is not)
    and because several European city names are also US ones. A non-European anchor inside a
    segment beats a European one in the same segment -- that is what separates "Cambridge, MA"
    from "Cambridge".
    """
    if not loc:
        return True
    segs = [s for s in re.split(r"[;|/]|\s+-\s+", loc) if s.strip()]
    if strict and any(strict.search(s) and not NON_EU.search(s) for s in segs):
        return True
    if any(NON_EU.search(s) for s in segs):
        return False
    return bool(loose.search(loc))          # 'Remote' with nothing else named: keep, unknown


def fetch(url, post=None):
    data = json.dumps(post).encode() if post else None
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    if post:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def iso(v):
    """Normalise assorted ATS date encodings to YYYY-MM-DD."""
    if v in (None, ""):
        return ""
    if isinstance(v, (int, float)):                       # Lever: epoch ms
        try:
            return dt.datetime.fromtimestamp(v / 1000, dt.timezone.utc).date().isoformat()
        except (ValueError, OSError, OverflowError):
            return ""
    s = str(v)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else ""


def orc_list_url(host, site, offset=0, limit=200):
    """The one Oracle Recruiting Cloud GET that enumerates a tenant's live requisitions.

    `siteNumber` does NOT filter the result set (any value returns the whole tenant), but it
    is still needed to build working public job links, so it is carried per employer.
    """
    finder = (f"findReqs;siteNumber={site},limit={limit},offset={offset},"
              "sortBy=POSTING_DATES_DESC")
    return ("https://" + host + "/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
            "?onlyData=true&expand=requisitionList&finder="
            + urllib.parse.quote(finder, safe=""))


def pull(vault_slug, ats, ats_slug, want_body=True):
    """Return normalised [(title, location, date, url, body)] for one employer board.

    `body` is the job description where the board's list endpoint carries it, else "". It is
    never printed -- it exists so tiering can see terms the title hides (measured 2026-08-08:
    tiering read `title + location` only, so a "Research Scientist" whose ad says RFdiffusion
    scored tier '-'). Greenhouse needs ?content=true; Ashby and Lever include it for free.
    SmartRecruiters, Workday and Oracle ORC would need one extra request per posting, which is
    not worth it -- those stay title-only.
    """
    out = []
    try:
        if ats == "greenhouse":
            q = "?content=true" if want_body else ""
            d = fetch(f"https://boards-api.greenhouse.io/v1/boards/{ats_slug}/jobs{q}")
            for j in d.get("jobs", []):
                out.append((j.get("title", ""), (j.get("location") or {}).get("name", ""),
                            iso(j.get("first_published") or j.get("updated_at")),
                            j.get("absolute_url", ""), unhtml(j.get("content"))))
        elif ats == "ashby":
            d = fetch(f"https://api.ashbyhq.com/posting-api/job-board/{ats_slug}")
            for j in d.get("jobs", []):
                out.append((j.get("title", ""), j.get("location", ""),
                            iso(j.get("publishedAt")), j.get("jobUrl", ""),
                            j.get("descriptionPlain") or unhtml(j.get("descriptionHtml"))))
        elif ats == "lever":
            d = fetch(f"https://api.lever.co/v0/postings/{ats_slug}?mode=json")
            for j in d:
                body = " ".join(str(x) for x in (j.get("descriptionPlain"),
                                                 j.get("additionalPlain")) if x)
                out.append((j.get("text", ""), (j.get("categories") or {}).get("location", ""),
                            iso(j.get("createdAt")), j.get("hostedUrl", ""), body))
        elif ats == "smartrecruiters":
            # Was hard-coded to offsets (0, 100), i.e. 200 postings max -- AbbVie hit that ceiling
            # exactly, which is how the truncation was spotted (2026-08-08). Page it out.
            off = 0
            for _ in range(SR_MAX_PAGES):
                d = fetch(f"https://api.smartrecruiters.com/v1/companies/{ats_slug}"
                          f"/postings?limit=100&offset={off}")
                items = d.get("content", [])
                for j in items:
                    loc = j.get("location") or {}
                    out.append((j.get("name", ""),
                                ", ".join(x for x in (loc.get("city"), loc.get("country")) if x),
                                iso(j.get("releasedDate")),
                                f"https://jobs.smartrecruiters.com/{ats_slug}/{j.get('id','')}",
                                ""))
                if len(items) < 100:
                    break
                off += 100
        elif ats == "workable":
            # One GET, whole board, with `published_on` and a full description. Common among
            # European mid-size biotechs that are on none of the US-startup boards.
            d = fetch("https://apply.workable.com/api/v1/widget/accounts/"
                      f"{ats_slug}?details=true")
            for j in d.get("jobs", []):
                loc = ", ".join(x for x in (j.get("city"), j.get("country")) if x)
                out.append((j.get("title", ""), loc, iso(j.get("published_on")),
                            j.get("shortlink") or j.get("url", ""),
                            unhtml(j.get("description"))))
        elif ats == "recruitee":
            d = fetch(f"https://{ats_slug}.recruitee.com/api/offers/")
            for j in d.get("offers", []):
                out.append((j.get("title", ""), j.get("location", ""),
                            iso(j.get("published_at")), j.get("careers_url", ""),
                            unhtml(j.get("description"))))
        elif ats == "workday":
            # "tenant/site/wdN" -- the wd number is part of the host and is not derivable,
            # so it is stored per tenant rather than guessed.
            #
            # ENUMERATE, don't sample. This used to issue three fixed searchText terms
            # ("protein", "computational biology", "machine learning") at limit 20 with no
            # paging -- at most 60 rows per employer. Measured 2026-08-08: Amgen has 1716 live
            # requisitions and the sweep saw <=60 of them; Zealand Pharma (Copenhagen, peptides)
            # returns 0 for "protein" and 10 for "peptide", so the sweep saw 2 of its 11 roles.
            # Workday's searchText is fuzzy relevance ranking, not keyword filtering -- "peptide"
            # at Zealand returns "UX Designer" -- so those 60 rows were close to arbitrary.
            # A blank searchText returns the whole board; limit is hard-capped at 20 by Workday
            # (25 -> HTTP 400) but offset paging works, so page it.
            bits = ats_slug.split("/")
            tenant, site = bits[0], bits[1]
            wd = bits[2] if len(bits) > 2 else "3"
            host = f"https://{tenant}.wd{wd}.myworkdayjobs.com"
            # Page on the board's own `total`, not on "a short page means the end". Workday
            # returns short intermediate pages: two consecutive full sweeps 10 minutes apart
            # gave 9781 and 6779 postings, and the short-page break was why. A silent 30%
            # truncation reads in the report as "the board had nothing new".
            off, total_n, short = 0, None, 0
            for _ in range(WORKDAY_MAX_PAGES):
                d = fetch(f"{host}/wday/cxs/{tenant}/{site}/jobs",
                          post={"searchText": "", "limit": 20, "offset": off})
                if total_n is None:
                    total_n = d.get("total") or 0
                page = d.get("jobPostings") or []
                for j in page:
                    out.append((j.get("title", ""), j.get("locationsText", ""),
                                workday_age(j.get("postedOn", "")),
                                host + f"/en-US/{site}" + j.get("externalPath", ""), ""))
                off += 20                          # advance by the page size, not by what came back
                if not page:
                    short += 1
                    if short >= 3:                 # three empty pages: genuinely past the end
                        break
                else:
                    short = 0
                if total_n and off >= total_n:
                    break
        elif ats == "oracle_orc":
            # Oracle Recruiting Cloud. "host/site" -- e.g.
            # efzu.fa.em2.oraclecloud.com/CX_2001. Neither part is derivable from the employer
            # name (the tenant prefix is an opaque 4-char pod id), so both are stored per
            # employer. One GET returns every live requisition with a real PostedDate.
            host, site = ats_slug.split("/", 1)
            off, total = 0, None
            while (total is None or off < total) and off < 1000:   # page; DTU is 82
                grp = (fetch(orc_list_url(host, site, offset=off)).get("items") or [{}])[0]
                reqs = grp.get("requisitionList") or []
                total = grp.get("TotalJobsCount") or 0
                for j in reqs:
                    out.append((j.get("Title", ""), j.get("PrimaryLocation", ""),
                                iso(j.get("PostedDate")),
                                f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}"
                                f"/job/{j.get('Id', '')}", ""))
                if not reqs:
                    break
                off += len(reqs)
    except Exception as e:                                  # noqa: BLE001 - report, never crash
        return [], f"{vault_slug} ({ats}:{ats_slug}): {type(e).__name__}"
    return out, None


TAG = re.compile(r"<[^>]+>")
ENT = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
       "&rsquo;": "'", "&ldquo;": '"', "&rdquo;": '"', "&mdash;": "-", "&ndash;": "-"}


def unhtml(s):
    """Strip markup out of an ATS description. Only ever used for regex matching."""
    if not s:
        return ""
    s = TAG.sub(" ", str(s))
    for k, v in ENT.items():
        s = s.replace(k, v)
    s = re.sub(r"&#\d+;", " ", s)
    return re.sub(r"\s+", " ", s)


def terms_in(rx, text):
    """Distinct lowercase tier terms the regex finds in `text`."""
    return {m.lower().strip() for m in rx.findall(text or "")} - {""}


def sentences(body):
    """Normalised sentences of an ad body, for cross-posting comparison."""
    out = []
    for s in re.split(r"(?<=[.!?])\s+|\n+", body or ""):
        s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) > 25:                # too short to be a distinctive house phrase
            out.append(s)
    return out


def board_boilerplate(bodies):
    """Sentences an employer repeats across its ads -- the 'about us' blurb, not the role.

    This is Gate 2 of the relevance gate ("does the term appear in the ROLE text or only in
    company boilerplate?") done mechanically, and it must work at SENTENCE granularity rather
    than term granularity. Measured on Adaptyv Bio, 2026-08-08: counting terms failed outright.
    "protein design" occurs in only 9 of 34 ads, so no term-frequency threshold flags it -- yet
    the densest body match on the whole board (6 hits, 2 distinct terms) was a *Scientific
    Account Executive* ad, while the genuine *Intern, Protein Design* had 4 hits of one term.
    Density does not separate signal from noise; the repeated mission blurb does. Strip the
    blurb and what remains is the role's own text.

    Free to compute: the whole board is already in hand.
    """
    n = len(bodies)
    if n < 4:
        return set()          # too few ads to tell a house phrase from a real requirement
    freq = {}
    for b in bodies:
        for s in set(sentences(b)):
            freq[s] = freq.get(s, 0) + 1
    return {s for s, c in freq.items() if c / n >= 0.3}


def derole(body, house):
    """Body with the employer's repeated boilerplate sentences removed."""
    if not body:
        return ""
    return " ".join(s for s in sentences(body) if s not in house)


def workday_age(txt):
    """'Posted 6 Days Ago' / 'Posted Today' -> approximate ISO date."""
    t = str(txt).lower()
    if "today" in t:
        return TODAY.isoformat()
    if "yesterday" in t:
        return (TODAY - dt.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*day", t)
    if m:
        return (TODAY - dt.timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\+?\s*month", t)
    if m:
        return (TODAY - dt.timedelta(days=30 * int(m.group(1)))).isoformat()
    return ""


STOP = {"the", "a", "of", "and", "for", "in", "to", "senior", "lead", "principal", "staff",
        "junior", "associate", "scientist", "engineer", "researcher", "specialist", "i", "ii"}


def role_tokens(text):
    """Significant lowercase tokens of a role name, for org+role dedup."""
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if t and t not in STOP and len(t) > 2}


def tracked_index():
    """org_slug -> list of token-sets for roles already tracked anywhere in the vault.

    Dedup is by identity, never by date -- so this deliberately includes
    inbox/processed/archive/, which the deep pass can otherwise re-collect.
    """
    idx = {}
    globs = ["inbox/*.txt", "inbox/processed/*.txt", "inbox/processed/archive/*.txt",
             "positions/open/*.md", "positions/applied/*.md", "positions/closed/*.md"]
    for g in globs:
        for p in ROOT.glob(g):
            parts = p.stem.split("_")
            org = parts[0].lower()
            role = parts[1] if len(parts) > 1 else ""
            idx.setdefault(org, []).append(role_tokens(role))
    return idx


def sighted_orgs():
    """Org slugs with at least one logged method sighting (`method_roles_seen` >= 1).

    method_sightings.py --apply (run by /inbox) writes the count onto the profile under its vault
    slug, so this needs no alias resolution of its own. Read for the M? tier.
    """
    out = set()
    for folder in ("companies", "research_groups"):
        for p in (ROOT / "organizations" / folder).glob("*.md"):
            m = re.search(r"^method_roles_seen:\s*(\d+)",
                          p.read_text(encoding="utf-8", errors="replace"), re.M)
            if m and int(m.group(1)) > 0:
                out.add(p.stem)
    return out


def org_fit_scores():
    """company slug -> career_fit, so a generic title at an on-direction employer still ranks.

    career_fit is the only score a company profile carries — with no advertised role there are
    no requirements to match against, so there is no skill_match here to consider.
    """
    out = {}
    for p in (ROOT / "organizations" / "companies").glob("*.md"):
        m = re.search(r"^career_fit:\s*(\d+)", p.read_text(encoding="utf-8", errors="replace"),
                      re.M)
        if m:
            out[p.stem] = int(m.group(1))
    return out


def uncovered(boards):
    """Band-A companies the sweep cannot see: no `ok` row in ats_slugs.tsv.

    Every other channel samples; the sweep is the only one that enumerates, so a band-A employer
    without a board is the most expensive blind spot there is. Measured 2026-10-01: after the v3
    rescore 128 records sat in band A, while the sweep covered 36 of 96 boards. Highest
    career_fit first; registering the employer's ATS host (search-positions-common.md, Group 0)
    removes it from this list for good.
    """
    covered = {vs for vs, _, _ in boards}
    rows = []
    for p in (ROOT / "organizations" / "companies").glob("*.md"):
        t = p.read_text(encoding="utf-8", errors="replace")
        band = re.search(r"^career_band:\s*(\S+)", t, re.M)
        if not band or band.group(1) != "A" or p.stem in covered:
            continue
        fit = re.search(r"^career_fit:\s*(\d+)", t, re.M)
        mf = re.search(r"^method_fit:\s*(\d+)", t, re.M)
        url = re.search(r"^url:\s*\"?([^\"\n]*)", t, re.M)
        rows.append((int(fit.group(1)) if fit else 0, int(mf.group(1)) if mf else 0, p.stem,
                     (url.group(1).strip() if url else "") or "-"))
    rows.sort(key=lambda r: (-r[0], -r[1], r[2]))
    print(f"{len(rows)} band-A compan{'y' if len(rows) == 1 else 'ies'} with no working ATS board "
          f"(the sweep enumerates {len(covered)} boards):")
    print("career\tmethod\torg\tcareers url")
    for fit, mf, slug, url in rows:
        print(f"{fit}\t{mf}\t{slug}\t{url}")


def main():
    argv = sys.argv[1:]
    all_geo = "--all-geo" in argv
    all_roles = "--all-roles" in argv
    show_all = "--show-all" in argv
    want_body = "--no-body" not in argv
    max_age = None
    if "--max-age" in argv:
        max_age = int(argv[argv.index("--max-age") + 1])
    geo_strict, geo_loose, geo_blocks, geo_unknown = geo_scope()

    if not CACHE.exists():
        sys.exit(f"No {CACHE.name}. Run:  python engine/tools/ats_discover.py")

    boards = []
    for line in CACHE.read_text(encoding="utf-8").splitlines()[1:]:
        p = line.rstrip("\n").split("\t")
        if len(p) >= 5 and p[1] and p[4] == "ok":
            boards.append((p[0], p[1], p[2]))
    if "--uncovered" in argv:
        uncovered(boards)
        return

    known = tracked_index()
    fits = org_fit_scores()
    sighted = sighted_orgs()
    # One board can front several vault orgs: DTU's single endpoint covers roles filed as
    # dtu-bioengineering, dtu-biosustain-cpe and a PI-named lab slug. Without folding those in, every
    # university role would read as NEW-ORG on every run. Only applies to single-token board
    # slugs -- "novo-nordisk" is never a hyphen component of another slug.
    board_roles = {}
    for vs, _, _ in boards:
        roles = list(known.get(vs, []))
        for org, prev in known.items():
            if org != vs and vs in org.split("-"):
                roles.extend(prev)
        board_roles[vs] = roles
    rows, errors, total = [], [], 0
    seen_urls = set()
    boilerplate = {}
    sizes = {}
    overlevel = 0

    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(pull, *b, want_body): b for b in boards}
        for fut in cf.as_completed(futs):
            vault_slug, ats, _ = futs[fut]
            jobs, err = fut.result()
            if err:
                errors.append(err)
                continue
            # Computed per board, before the per-posting loop: it needs every ad at once.
            sizes[vault_slug] = len(jobs)
            house = board_boilerplate([j[4] for j in jobs if j[4]])
            if house:
                boilerplate[vault_slug] = len(house)
            for title, loc, date, url, body in jobs:
                total += 1
                blob = f"{title} {loc}"
                if EXCLUDE.search(title):
                    continue
                # The title prefilter stays. Checked 2026-08-08: --all-roles yields identical
                # T1/T2/T2? counts, so MAYBE costs no recall -- and dropping it let body text
                # promote "Community Manager" and "Lab Technician" at a protein-design company
                # to T1b. Body tiering upgrades within this set; it does not widen it.
                # A title outside MAYBE may still enter the method check ("Software Engineer",
                # "Platform Developer") -- but only that check: career tiering keeps its own
                # prefilter, measured above, so a method title can never become T1b.
                career_title = all_roles or bool(MAYBE.search(title))
                method_title = bool(M_TITLE and (M_TITLE.search(title)
                                                 or M_TITLE_STRONG.search(title)))
                if not career_title and not method_title:
                    continue
                if not all_geo and not in_scope(loc, geo_strict, geo_loose):
                    continue
                age = ""
                if date:
                    try:
                        age = (TODAY - dt.date.fromisoformat(date)).days
                    except ValueError:
                        age = ""
                if max_age is not None and isinstance(age, int) and age > max_age:
                    continue
                if url in seen_urls:      # Workday is queried with several search terms
                    continue
                seen_urls.add(url)

                tier = "-"
                if career_title:
                    tier = "T1" if TIER1.search(blob) else ("T2" if TIER2.search(blob) else "-")
                fit = fits.get(vault_slug, 0)
                own = derole(body, house) if body else ""
                # Body match, boilerplate removed. 'b' suffix = the term is in the ad text, not
                # the title, so Gate 2 (placement) still has to be answered when the ad is
                # opened -- but the lead is no longer invisible.
                if tier == "-" and own and career_title:
                    if TIER1.search(own):
                        tier = "T1b"
                    elif len(terms_in(TIER2, own)) >= 2:
                        tier = "T2b"
                # A computational title at a protein-design employer is worth a look even when the
                # title alone says nothing: the regex cannot see that "Machine Learning Scientist"
                # is posted by Latent Labs. Employer fit supplies that context. The threshold is the
                # user's (T2Q_MIN_FIT, from search_terms.toml, with the measurement behind it).
                #
                # Only on a SMALL board. That inference is "this company does one thing, so its
                # generic titles probably do it too" -- true of a 15-role startup, false of a
                # 1716-requisition pharma conglomerate where "Data Scientist" means IT. It went
                # unnoticed while Workday was sampled at 60 rows/board; full enumeration took
                # T2? from 19 to 43, of which 38 were AstraZeneca/Sanofi/Amgen/GSK infrastructure
                # roles (measured 2026-08-08).
                if (tier == "-" and career_title and fit >= T2Q_MIN_FIT
                        and len(jobs) <= T2Q_MAX_BOARD and COMPUTATIONAL.search(title)):
                    tier = "T2?"

                # Method lane, for the skill track only (search-positions-skill.md §Method lane).
                # M from the title alone; Mb needs BOTH a build phrase and scientist users in the
                # role text -- the build phrase on its own is every corporate IT ad on a pharma
                # Workday board. Workday/SmartRecruiters/Oracle carry no body, so there only M fires.
                if tier == "-" and M_TITLE:
                    if M_TITLE_STRONG.search(title):
                        tier = "M"
                    elif own and M_BODY_BUILD.search(own) and M_BODY_USERS.search(own):
                        tier = "Mb"

                # M? -- the method lane's employer route, inside the sweep. An employer that has
                # posted a build seat before is likely to again, and the next one need not say
                # so in the words M/Mb test for: Adaptyv's "Software Engineer, Product" builds
                # its lab orchestration platform ("building the orchestration layer"), which the
                # build-phrase pattern does not match, so it sat in tier '-' through every sweep
                # from 10-01 until the 10-10 skill track went looking (decisions.md §A sweep miss
                # is a triage miss). Title only -- a build-phrase requirement would drop exactly
                # that ad -- and small boards only, as for T2?: on a pharma board "engineer" is
                # everything.
                if (tier == "-" and M_TITLE_WORD and vault_slug in sighted
                        and len(jobs) <= T2Q_MAX_BOARD and M_TITLE_WORD.search(title)
                        and not M_CORPORATE.search(title)):
                    tier = "M?"

                # Demote rather than drop: the row stays in the TSV so a wrong suppression is
                # recoverable and countable, it just does not spend context. --show-all prints it.
                if tier != "-" and over_level(title):
                    overlevel += 1
                    tier = "-"

                toks = role_tokens(title)
                tracked = "NEW-ORG"
                prevs = board_roles.get(vault_slug) or []
                if prevs:
                    tracked = "new-role"
                    for prev in prevs:
                        if prev and toks and len(toks & prev) >= 2:
                            tracked = "tracked"
                            break

                rows.append({
                    "tier": tier, "age": age, "date": date or "?", "org": vault_slug,
                    "fit": fit, "title": title.strip(), "loc": (loc or "").strip(),
                    "tracked": tracked, "url": url,
                })

    rank = {"T1": 0, "T1b": 1, "T2": 2, "T2b": 3, "T2?": 4, "M": 5, "Mb": 6, "M?": 7, "-": 8}
    rows.sort(key=lambda r: (rank[r["tier"]], -r["fit"],
                             r["age"] if isinstance(r["age"], int) else 9999))

    # "career" is the employer's career_fit, carried down onto each of its postings so a
    # generic title at an on-direction employer still ranks. It says nothing about whether
    # this particular role suits the user's skills — /inbox decides that per posting.
    hdr = ["tier", "age_d", "published", "org", "career", "status", "title", "location", "url"]

    def line(r):
        return "\t".join([r["tier"], str(r["age"]), r["date"], r["org"], str(r["fit"]),
                          r["tracked"], r["title"], r["loc"], r["url"]])

    # The file keeps everything; stdout does not. Measured 2026-08-08: 74 of 97 printed rows
    # were tier '-' -- roughly three quarters of this channel's token cost, carrying no signal
    # the tier column had not already reported. The prefilter itself was checked and is NOT
    # costing recall (--all-roles yields identical T1/T2/T2? counts), so this only trims output.
    OUT.write_text("\n".join([("\t".join(hdr))] + [line(r) for r in rows]) + "\n",
                   encoding="utf-8")
    shown = rows if show_all else [r for r in rows if r["tier"] != "-"]
    print("\n".join(["\t".join(hdr)] + [line(r) for r in shown]))

    counts = {t: sum(1 for r in rows if r["tier"] == t) for t in rank}
    print(f"\n# {len(boards)} boards swept | {total} postings seen | {len(shown)} printed "
          f"| {counts['T1']} T1, {counts['T1b']} T1b, {counts['T2']} T2, "
          f"{counts['T2b']} T2b, {counts['T2?']} T2?, {counts['M']} M, {counts['Mb']} Mb, "
          f"{counts['M?']} M? (method lane — skill track), {counts['-']} untiered",
          file=sys.stderr)
    if not show_all and counts["-"]:
        print(f"#   {counts['-']} tier '-' row(s) written to {OUT.name} but not printed "
              f"— use --show-all to see them", file=sys.stderr)
    if overlevel:
        print(f"# {overlevel} tiered row(s) demoted by Gate 4 (level: principal/staff/lead/"
              f"director and above; 'senior' is NOT gated, PhD calls exempt) — in {OUT.name}, "
              f"not printed", file=sys.stderr)
    print(f"# geo filter: {'OFF' if all_geo else ' · '.join(geo_blocks)} | "
          f"age filter: {'none' if max_age is None else str(max_age) + 'd'} | "
          f"body tiering: {'on' if want_body else 'OFF'} | "
          f"written to {OUT.name}", file=sys.stderr)
    if geo_unknown and not all_geo:
        print(f"# ⚠ allowlist countries with no PLACES entry, so none of their postings were kept: "
              f"{', '.join(geo_unknown)}", file=sys.stderr)
    if boilerplate:
        # Report it: a sentence suppressed here is text Gate 2 would have discarded anyway, but
        # a wrong suppression is a silent recall loss, so the count must be visible.
        print("# boilerplate sentences stripped before body tiering "
              "(repeated in >=30% of that board's ads):", file=sys.stderr)
        print("#   " + " · ".join(f"{o}:{boilerplate[o]}" for o in sorted(boilerplate)),
              file=sys.stderr)
    # Per-board totals. A board that silently halves between runs is a paging regression, not
    # an employer that stopped hiring, and there is no other way to tell those apart.
    big = sorted(sizes.items(), key=lambda kv: -kv[1])
    print("# postings per board: " + " · ".join(f"{k}:{v}" for k, v in big if v),
          file=sys.stderr)
    empty = [k for k, v in sizes.items() if not v]
    if empty:
        print(f"# {len(empty)} board(s) returned ZERO postings — verify before believing it: "
              + ", ".join(sorted(empty)), file=sys.stderr)
    if errors:
        print(f"# {len(errors)} board(s) failed — NOT the same as having no roles:",
              file=sys.stderr)
        for e in errors:
            print(f"#   {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
