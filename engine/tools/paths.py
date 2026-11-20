"""
paths.py — the one place that knows where things live.

Every tool imports its folders from here, so the layout can change in one file. Paths are absolute
(derived from this file's location), so the tools work from any working directory; the convention
in the docs is to run them from the repo root: `python engine/tools/<tool>.py`.

    career-engine/
    ├── engine/tools/   ← TOOLS (this file)
    ├── engine/packs/   ← PACKS — domain data (boards, ATS seeds); user/settings.toml picks one
    └── user/           ← USER — override with the CAREER_USER_DIR environment variable
        ├── profile/
        └── workspace/  ← WORKSPACE — every record path (source_file: inbox/…, cv_dir:
                          applications/…) is relative to this folder
"""
import os
import tomllib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ENGINE = TOOLS.parent
REPO = ENGINE.parent
PACKS = ENGINE / "packs"

USER = Path(os.environ["CAREER_USER_DIR"]).resolve() if os.environ.get("CAREER_USER_DIR") else REPO / "user"
PERSONAL_DATA = USER / "personal_data"
PROFILE = USER / "profile"
WORKSPACE = USER / "workspace"

INBOX = WORKSPACE / "inbox"
POSITIONS = WORKSPACE / "positions"
ORGS = WORKSPACE / "organizations"
APPLICATIONS = WORKSPACE / "applications"
LOGS = WORKSPACE / "logs"
CACHE = WORKSPACE / "cache"
ARTIFACTS = WORKSPACE / "artifacts"
PLAN = WORKSPACE / "plan"            # Timeline + To-do store (plan.py)

SETTINGS = USER / "settings.toml"
_settings = None


def settings():
    """user/settings.toml as a dict, read once. Exits with a clear message if it is missing."""
    global _settings
    if _settings is None:
        if not SETTINGS.exists():
            raise SystemExit(f"missing {SETTINGS} — the tools need your personal settings file (new clone? run: python engine/tools/init_user.py)")
        with open(SETTINGS, "rb") as f:
            _settings = tomllib.load(f)
    return _settings


def setting(key):
    """One value from user/settings.toml by dotted key, e.g. setting("thresholds.stale_days").

    The engine keeps no personal defaults of its own, so a missing key stops the tool with a
    message naming the key, rather than a KeyError deep inside it."""
    node = settings()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise SystemExit(f"{SETTINGS} has no `{key}` — add it (see the comments in the file)")
        node = node[part]
    return node


def pack():
    """The domain pack folder named by `search.pack` in user/settings.toml (engine/packs/<name>)."""
    p = PACKS / setting("search.pack")
    if not p.is_dir():
        raise SystemExit(f"no domain pack at {p} — check `search.pack` in {SETTINGS}")
    return p


def pack_data(name):
    """A TOML data file from the selected domain pack, e.g. pack_data("ats_seeds.toml")."""
    with open(pack() / name, "rb") as f:
        return tomllib.load(f)


_user_toml = {}


def user_toml(rel):
    """A TOML file under user/, read once, e.g. user_toml("profile/search_terms.toml"). Exits with a
    clear message if it is missing — like settings.toml, the engine keeps no copy of its own."""
    if rel not in _user_toml:
        p = USER / rel
        if not p.exists():
            raise SystemExit(f"missing {p} — the tools need it (see engine/docs/ARCHITECTURE.md)")
        with open(p, "rb") as f:
            _user_toml[rel] = tomllib.load(f)
    return _user_toml[rel]


def user_name():
    """The user's name from the **Name:** line of profile/snapshot.md, or "" if it has none."""
    import re
    snap = PROFILE / "snapshot.md"
    if not snap.exists():
        return ""
    m = re.search(r"\*\*Name:\*\*\s*([^·\n]+)", snap.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else ""
