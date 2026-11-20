#!/usr/bin/env python3
"""
doctor.py — is this repo set up correctly, and is the engine ready to share? Read-only.

    python engine/tools/doctor.py            # all checks; exit 1 on any FAIL
    python engine/tools/doctor.py --share    # also FAIL if engine/ still contains personal terms
    python engine/tools/doctor.py -v         # list every finding, not just the first few

Checks, in order:
  layout     the user/ folders and profile files the skills rely on exist; CLAUDE.md @imports resolve
  settings   user/settings.toml parses and has every key the tools read, in range; each allowlist
             country is one ats_sweep.py can place in a location string
  paths      no stale pre-restructure references (career_vault, CONTEXT.md, profiles/ …) in the
             engine, and every user/… or engine/… path the engine names actually exists
  tools      every script in engine/tools/ compiles and finds its folders through paths.py
  git        user/ is ignored by the engine repo, nothing personal is tracked there, user/'s own
             repo keeps personal_data/ and secrets/ out, and the pre-commit guard is installed
  records    every position and organisation record has parseable frontmatter with its scores and
             every record carries the current schema_version; rescore_status.py --verify is summarised
  share      personal terms (name, email, the words in user/profile/private_terms.txt) in any file
             the engine tracks or has staged, staged copy included — WARN normally, FAIL with
             --share. engine/hooks/pre-commit runs it before every commit.

The personal terms are read from user/, never written here: a list of them inside the engine
would itself be the leak.
"""
import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from paths import ENGINE, PACKS, PROFILE, REPO, SETTINGS, TOOLS, USER, WORKSPACE, user_name

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# What the engine reads, prose-wise: the files an agent follows.
PROSE = [REPO / "CLAUDE.md", REPO / "README.md", *sorted((REPO / ".claude" / "commands").glob("*.md")),
         *sorted((ENGINE / "skills").glob("*.md")), *sorted((ENGINE / "docs").glob("*.*")),
         *sorted(PACKS.rglob("*.md")), *sorted(PACKS.rglob("*.toml"))]

REQUIRED = [
    "profile/snapshot.md", "profile/background.md", "profile/preferences.md",
    "profile/competencies.md", "profile/soft_skills.md", "profile/cv_template/master_cv.tex",
    "profile/cv_template/publications.md", "profile/cv_template/NOTES.md",
    "profile/cv_template/cover_letter.tex", "profile/writing/writing_style.md",
    "profile/writing/cover_letter_style_A.md", "profile/writing/cover_letter_style_B.md",
    "profile/search_terms.md", "profile/search_terms.toml",
    "memory/MEMORY.md", "settings.toml",
    "workspace/inbox/_staging/career", "workspace/inbox/_staging/skill", "workspace/inbox/processed",
    "workspace/positions/open", "workspace/positions/applied", "workspace/positions/closed",
    "workspace/organizations/companies", "workspace/organizations/research_groups",
    "workspace/applications", "workspace/contacts", "workspace/logs",
]

# Pre-restructure names. `profiles/` only as a path start (the dashboard's "profiles" is prose).
STALE = [
    (re.compile(r"career_vault"), "career_vault"),
    (re.compile(r"CONTEXT\.md|\[\[CONTEXT\]\]"), "CONTEXT.md"),
    (re.compile(r"COMPETENCIES\.md|\[\[COMPETENCIES\]\]"), "COMPETENCIES.md"),
    (re.compile(r"soft_skills_library"), "soft_skills_library"),
    (re.compile(r"(?<![\w/.-])profiles/(companies|research_groups)"), "profiles/"),
    (re.compile(r"Projects[\\/]Career[\\/]"), r"C:\Projects\Career"),
]
# A path the engine names. Templated ones ([slug], {a,b}, *.md, <id>, YYYY) are patterns, not files.
PATH_RE = re.compile(r"(?<![\w/.-])((?:user|engine)/[\w./@-]*[\w/])")
TEMPLATED = re.compile(r"[\[\]{}*<>|]|YYYY|\.\.\.")
ON_DEMAND = {"user/workspace/trash", "user/workspace/trash/_trash_log.md",   # created by /track
             "user/workspace/logs/method_sightings.tsv",                     # by method_sightings.py add
             # outputs the tools write on first use, so absent in a new install
             "user/workspace/artifacts/dashboard.html", "user/workspace/plan/plan.json",
             "user/workspace/logs/search_runs.jsonl", "user/workspace/logs/ats_sweep_latest.tsv",
             "user/workspace/logs/link_check_latest.tsv", "user/workspace/cache/ats_slugs.tsv",
             "user/workspace/linkedin/linkedin_stats.csv"}
# The engine cites a few of the owner's own notes as rationale; another install will not have them.
NOTES = "user/workspace/notes/"

results = []  # (status, check, message, details)


def report(status, check, msg, details=()):
    results.append((status, check, msg, list(details)))


def rel(p):
    return p.relative_to(REPO).as_posix()


def read(p):
    return p.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------------------------
def check_layout():
    missing = [r for r in REQUIRED if not (USER / r).exists()]
    if not USER.exists():
        report("FAIL", "layout", f"{USER} does not exist — nothing to run on. Run: python engine/tools/init_user.py")
        return
    report("FAIL" if missing else "PASS", "layout",
           f"{len(REQUIRED) - len(missing)}/{len(REQUIRED)} required user/ paths present",
           [f"missing: user/{m}" for m in missing])
    claude = REPO / "CLAUDE.md"
    imports = re.findall(r"^@(\S+)", read(claude), re.M) if claude.exists() else []
    broken = [i for i in imports if not (REPO / i).exists()]
    report("FAIL" if broken or not claude.exists() else "PASS", "layout",
           f"CLAUDE.md: {len(imports) - len(broken)}/{len(imports)} @imports resolve",
           [f"broken @import: {b}" for b in broken])


# What every domain pack must provide (engine/packs/<pack>/).
PACK_FILES = ("boards.md", "synonyms.md", "prestige.md", "ats_seeds.toml")

# Every key a tool reads from user/settings.toml, with the range that makes sense for it.
THRESHOLDS = {"min_score_shown": (0, 100), "stale_days": (1, 3650), "on_direction": (0, 100),
              "verified_days": (0, 3650)}


def check_settings():
    if not SETTINGS.exists():
        return  # check_layout already reports it missing
    try:
        with open(SETTINGS, "rb") as f:
            s = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        report("FAIL", "settings", f"user/settings.toml does not parse: {e}")
        return
    bad = []
    th = s.get("thresholds", {})
    for key, (lo, hi) in THRESHOLDS.items():
        v = th.get(key)
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            bad.append(f"thresholds.{key} = {v!r} — want an integer {lo}–{hi}")
    checks = s.get("career_fit", {}).get("checks")
    if not checks or not all(isinstance(v, (int, float)) and v > 0 for v in checks.values()):
        bad.append("career_fit.checks — want a table of check name = positive units")
    blocks = s.get("geography", {}).get("block")
    if not blocks:
        bad.append("geography.block — want at least one [[geography.block]] with name and countries")
    for i, b in enumerate(blocks or []):
        if not isinstance(b.get("name"), str) or not b.get("countries") or \
                not all(isinstance(c, str) for c in b["countries"]):
            bad.append(f"geography.block #{i + 1} — want name = \"…\" and countries = [\"…\"]")
    geo = s.get("geography", {})
    loop, req = geo.get("linkedin_loop"), geo.get("linkedin_required")
    if not loop or not all(isinstance(c, str) for c in loop):
        bad.append("geography.linkedin_loop — want a list of LinkedIn location= tokens, in order")
    elif not isinstance(req, int) or isinstance(req, bool) or not 0 <= req <= len(loop):
        bad.append(f"geography.linkedin_required = {req!r} — want an integer 0–{len(loop)}")
    pack = s.get("search", {}).get("pack")
    if not isinstance(pack, str) or not pack:
        bad.append("search.pack — want the name of a folder in engine/packs/")
    elif not (PACKS / pack).is_dir():
        bad.append(f"search.pack = {pack!r} — no such folder engine/packs/{pack}/")
    else:
        missing = [f for f in PACK_FILES if not (PACKS / pack / f).exists()]
        bad += [f"engine/packs/{pack}/{f} is missing — the skills and tools read it" for f in missing]
    report("FAIL" if bad else "PASS", "settings", "user/settings.toml has every key the tools read", bad)
    check_search_terms()

    try:
        from ats_sweep import PLACES
    except Exception as e:  # noqa: BLE001 — a broken sweep is reported, not raised
        report("WARN", "settings", f"could not import ats_sweep.PLACES to check the allowlist: {e}")
        return
    unknown = [f"{c} (block \"{b.get('name')}\")" for b in blocks or [] if not b.get("remote_only")
               for c in b.get("countries", []) if c not in PLACES]
    report("WARN" if unknown else "PASS", "settings",
           f"ats_sweep.py can place {'all' if not unknown else 'not all'} allowlist countries",
           [f"no PLACES entry, so the sweep drops its postings: {u}" for u in unknown])


# What ats_sweep.py, level_sweep.py and log_run.py read from user/profile/search_terms.toml.
SEARCH_PATTERNS = {"sweep": ("tier1", "tier2", "maybe", "computational"),
                   "level": ("overlevel", "phd_call", "optional_level")}
# ats_sweep.py's method lane, [sweep.method] — optional as a section, complete when present.
METHOD_PATTERNS = ("title_strong", "title", "body_build", "body_users")


def check_search_terms():
    p = PROFILE / "search_terms.toml"
    if not p.exists():
        return  # check_layout already reports it missing
    try:
        with open(p, "rb") as f:
            t = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        report("FAIL", "settings", f"user/profile/search_terms.toml does not parse: {e}")
        return
    bad = []
    for section, keys in SEARCH_PATTERNS.items():
        for k in keys:
            v = t.get(section, {}).get(k)
            if not isinstance(v, str) or not v:
                bad.append(f"{section}.{k} — want a regular expression (a TOML literal string)")
                continue
            try:
                re.compile(v, re.I)
            except re.error as e:
                bad.append(f"{section}.{k} does not compile: {e}")
    # [sweep.method] is optional (no section = no M tier), but when present it is read whole.
    method = t.get("sweep", {}).get("method")
    if method is not None:
        for k in METHOD_PATTERNS:
            v = method.get(k) if isinstance(method, dict) else None
            if not isinstance(v, str) or not v:
                bad.append(f"sweep.method.{k} — want a regular expression (a TOML literal string)")
                continue
            try:
                re.compile(v, re.I)
            except re.error as e:
                bad.append(f"sweep.method.{k} does not compile: {e}")
    fit = t.get("sweep", {}).get("t2q_min_employer_fit")
    if not isinstance(fit, int) or isinstance(fit, bool) or not 0 <= fit <= 100:
        bad.append(f"sweep.t2q_min_employer_fit = {fit!r} — want an integer 0–100")
    pool = t.get("linkedin", {}).get("query_pool")
    if not pool or not all(isinstance(q, str) and q for q in pool):
        bad.append("linkedin.query_pool — want a non-empty list of LinkedIn keyword queries")
    report("FAIL" if bad else "PASS", "settings", "user/profile/search_terms.toml has every term the tools read", bad)


def check_paths():
    stale, dangling, notes = [], [], []
    for p in PROSE:
        if not p.exists():
            continue
        for n, line in enumerate(read(p).splitlines(), 1):
            for pat, label in STALE:
                if pat.search(line):
                    stale.append(f"{rel(p)}:{n}  [{label}]  {line.strip()[:110]}")
            for m in PATH_RE.finditer(line):
                path = m.group(1).rstrip("./")
                if TEMPLATED.search(path) or path in ON_DEMAND or \
                        (path.startswith("user/") and not USER.is_dir()):  # layout reports that
                    continue
                if not (REPO / path).exists():
                    (notes if path.startswith(NOTES) else dangling).append(f"{rel(p)}:{n}  {path}")
    report("FAIL" if stale else "PASS", "paths", f"{len(stale)} stale pre-restructure reference(s)", stale)
    report("FAIL" if dangling else "PASS", "paths",
           f"{len(dangling)} path(s) named in the engine that do not exist", sorted(set(dangling)))
    if notes:
        report("WARN", "paths", f"{len(set(notes))} cited personal note(s) not in this user/ (normal in a "
               "new install)", sorted(set(notes)))


def check_tools():
    bad, rooted = [], []
    for p in sorted(TOOLS.glob("*.py")):
        try:
            compile(read(p), str(p), "exec")  # syntax only; writes no .pyc, runs nothing
        except SyntaxError as e:
            bad.append(f"{p.name}:{e.lineno}: {e.msg}")
        if p.name == "paths.py":
            continue
        t = read(p)
        if re.search(r"^ROOT\s*=\s*.*__file__", t, re.M):
            rooted.append(f"{p.name}: ROOT derived from __file__ instead of paths.py")
    n = len(list(TOOLS.glob("*.py")))
    report("FAIL" if bad else "PASS", "tools", f"{n - len(bad)}/{n} tools compile", bad)
    report("FAIL" if rooted else "PASS", "tools", "all tools locate data through paths.py", rooted)


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout.strip()


def check_git():
    code, _ = git(REPO, "rev-parse", "--git-dir")
    if code:
        report("WARN", "git", "the engine folder is not a git repo — skipped")
        return
    code, _ = git(REPO, "check-ignore", "-q", "user/")
    tracked = git(REPO, "ls-files", "user")[1].splitlines()
    issues = ([] if code == 0 else ["user/ is not ignored by the engine .gitignore"]) + \
             [f"tracked in the engine repo: {t}" for t in tracked]
    report("FAIL" if issues else "PASS", "git", "engine repo keeps user/ out", issues)

    if not USER.is_dir():
        return  # check_layout already reports it missing
    code, top = git(USER, "rev-parse", "--show-toplevel")
    if code or Path(top).resolve() != USER.resolve():
        report("WARN", "git", "user/ is not its own git repo — it has no history or undo")
        return
    leaked = [f for f in git(USER, "ls-files")[1].splitlines()
              if f.startswith(("personal_data/", "secrets/"))]
    report("FAIL" if leaked else "PASS", "git", "user/ repo keeps personal_data/ and secrets/ out",
           [f"tracked: {f}" for f in leaked[:50]])
    dirty = git(USER, "status", "--porcelain")[1].splitlines()
    if dirty:
        report("WARN", "git", f"user/ has {len(dirty)} uncommitted change(s)", dirty)

    code, hooks = git(REPO, "config", "--get", "core.hooksPath")
    if hooks.replace("\\", "/").rstrip("/") != "engine/hooks":
        report("WARN", "git", "the pre-commit share guard is not installed",
               ["run: git config core.hooksPath engine/hooks   (it runs doctor.py --share before every commit)"])
    else:
        report("PASS", "git", "pre-commit share guard installed (core.hooksPath = engine/hooks)")


FM = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
SKIP_TYPES = {"person_bio"}


def check_records():
    dirs = [WORKSPACE / d for d in ("positions/open", "positions/applied", "positions/closed",
                                    "organizations/companies", "organizations/research_groups")]
    n, bad = 0, []
    for d in dirs:
        for p in sorted(d.glob("*.md")):
            n += 1
            m = FM.match(read(p))
            if not m:
                bad.append(f"{rel(p)}: no frontmatter block")
                continue
            fm = m.group(1)
            t = re.search(r"^type:\s*(\S+)", fm, re.M)
            if t and t.group(1) in SKIP_TYPES:
                continue
            for field in ("career_fit", "skill_match"):
                if not re.search(rf"^{field}:\s*\d+", fm, re.M):
                    bad.append(f"{rel(p)}: no numeric {field}")
    report("FAIL" if bad else "PASS", "records", f"{n - len(bad)}/{n} records parse with scores", bad)

    import schema
    off = [(p, schema.version_of(read(p))) for p in schema.records()]
    off = [(p, v) for p, v in off if v is not None and v != schema.SCHEMA_VERSION]
    report("WARN" if off else "PASS", "records",
           f"{'all' if not off else len(off)} record(s) {'at' if not off else 'not at'} schema_version {schema.SCHEMA_VERSION}",
           [f"{rel(p)}: v{v} — run: python engine/tools/schema.py --apply" for p, v in off])

    rs = TOOLS / "rescore_status.py"
    if rs.exists():
        r = subprocess.run([sys.executable, str(rs), "--verify"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        m = re.search(r"(\d+) problem\(s\) across (\d+) v3", r.stdout)
        if m:
            report("WARN" if int(m.group(1)) else "PASS", "records",
                   f"rescore_status --verify: {m.group(1)} problem(s) across {m.group(2)} v3 record(s)",
                   [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("[!]")])


def private_terms():
    terms = {w for w in user_name().split() if len(w) > 2}
    code, email = git(USER if USER.is_dir() else REPO, "config", "user.email")
    if not code and email:
        terms.update({email, email.split("@")[0]})
    extra = PROFILE / "private_terms.txt"
    if extra.exists():
        terms.update(l.strip() for l in read(extra).splitlines() if l.strip() and not l.startswith("#"))
    return sorted(terms, key=str.lower)


def engine_texts():
    """(label, text) for everything the engine would share: the files doctor reads anyway, every file
    the engine repo tracks, and the *staged* copy of each tracked file where it differs from the
    working tree — the pre-commit hook has to see what will actually be committed."""
    out, seen = [], set()

    def add(label, data):
        if b"\0" in data[:8000] or (label, data) in seen:      # binary, or already scanned
            return
        seen.add((label, data))
        out.append((label, data.decode("utf-8", errors="replace")))

    paths = set(PROSE + sorted(TOOLS.glob("*.py")) + [REPO / "skills-lock.json"])
    code, ls = git(REPO, "ls-files", "-s", "-z")              # "<mode> <sha> <stage>\t<path>"
    staged = {}
    if not code:
        for entry in filter(None, ls.split("\0")):
            meta, path = entry.split("\t", 1)
            staged[path] = meta.split()[1]
            paths.add(REPO / path)
    for p in sorted(paths):
        if p.is_file():
            add(rel(p), p.read_bytes())
    if staged:
        r = subprocess.run(["git", "cat-file", "--batch"], cwd=str(REPO), capture_output=True,
                           input=("\n".join(staged.values()) + "\n").encode())
        buf, i = r.stdout, 0
        for path in staged:
            nl = buf.index(b"\n", i)
            head = buf[i:nl].split()
            if len(head) < 3 or head[1] == b"missing":
                i = nl + 1
                continue
            size = int(head[2])
            add(path, buf[nl + 1:nl + 1 + size])
            i = nl + 1 + size + 1
    return out


def check_share(strict):
    terms = private_terms()
    if not terms:
        report("WARN", "share", "no personal terms known — add user/profile/private_terms.txt")
        return
    pat = re.compile("|".join(re.escape(t) for t in terms), re.I)
    counts = {}
    for label, text in engine_texts():
        hits = pat.findall(text)
        if hits and len(hits) > len(counts.get(label, [])):
            counts[label] = hits                                # the worse of working tree / staged
    per_file, total = [], 0
    for label, hits in counts.items():
        total += len(hits)
        top = ", ".join(f"{t}×{hits.count(t)}" for t in sorted(set(hits), key=lambda x: -hits.count(x))[:4])
        per_file.append((len(hits), f"{label}: {len(hits)}  ({top})"))
    per_file.sort(key=lambda x: -x[0])
    status = ("FAIL" if strict else "WARN") if total else "PASS"
    report(status, "share", f"{total} personal term(s) in {len(per_file)} engine file(s) "
                            f"— {len(terms)} terms checked", [d for _, d in per_file])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--share", action="store_true", help="FAIL (not WARN) on personal terms in the engine")
    ap.add_argument("-v", "--verbose", action="store_true", help="show every finding")
    a = ap.parse_args()

    check_layout()
    check_settings()
    check_paths()
    check_tools()
    check_git()
    check_records()
    check_share(a.share)

    limit = None if a.verbose else 6
    for status, check, msg, details in results:
        print(f"[{status}] {check:<8} {msg}")
        for d in details[:limit]:
            print(f"         {d}")
        if limit and len(details) > limit:
            print(f"         … {len(details) - limit} more (-v to list all)")
    fails = sum(1 for s, *_ in results if s == "FAIL")
    warns = sum(1 for s, *_ in results if s == "WARN")
    print(f"\n{fails} fail · {warns} warn · {len(results) - fails - warns} pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
