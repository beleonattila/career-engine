#!/usr/bin/env python3
"""plan.py — the store behind the dashboard's Timeline and To-do tabs.

One file, two views: user/workspace/plan/plan.json. The Timeline draws every item, past included;
the To-do matrix shows the open ones that are still ahead. Ticking an item done, or flagging it
important/urgent, therefore changes both at once.

    {"version": 1, "rev": 7,
     "items":     [{"id", "title", "start", "end", "color", "important", "urgent", "done",
                    "notes", "created"}],
     "overrides": {"sent:positions/applied/x.md": {"color", "important", "urgent", "done",
                                                   "notes", "hidden"}}}

`items` are what the user added. An item with no `end` is a moment (an application sent), not a
span. `overrides` restyle the items dashboard.py derives from records (applications sent,
interviews, live deadlines): their dates belong to the record's frontmatter and are changed with /track, so an
override can recolour, flag, tick or hide one but never move it. `rev` rises on every save; a
save quoting a stale rev is refused, so a page left open cannot overwrite an edit made since.

Run:  python engine/tools/plan.py                       # list items
      python engine/tools/plan.py add "Title" --start 2026-10-05 [--end …] [--color #4f8cff]
                                      [--important] [--urgent] [--done] [--notes "…"]
Edited in the browser through serve.py.
"""
import argparse, datetime, json, os, re, secrets, tempfile

from paths import PLAN

PLAN_FILE = PLAN / "plan.json"
VERSION = 1
DEFAULT_COLOR = "#4f8cff"
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID = re.compile(r"^[\w:./@-]{1,300}$")
MAX_ITEMS = 2000


class PlanError(ValueError):
    """The document is malformed; the message says which field."""


class Conflict(Exception):
    """A save quoted a rev older than the file's. Carries the current document."""
    def __init__(self, current):
        super().__init__("plan.json changed since it was read")
        self.current = current


def empty():
    return {"version": VERSION, "rev": 0, "items": [], "overrides": {}}


def _date(v, field, optional=False):
    if v in (None, "") and optional:
        return None
    try:
        return datetime.date.fromisoformat(str(v)).isoformat()
    except ValueError:
        raise PlanError(f"{field}: {v!r} is not a YYYY-MM-DD date")


def _text(v, field, limit, required=False):
    s = str(v or "").strip()
    if required and not s:
        raise PlanError(f"{field} is empty")
    if len(s) > limit:
        raise PlanError(f"{field} is longer than {limit} characters")
    return s


def _color(v, field):
    if v in (None, ""):
        return DEFAULT_COLOR
    if not _COLOR.match(str(v)):
        raise PlanError(f"{field}: {v!r} is not a #rrggbb colour")
    return str(v).lower()


def clean_item(it, n):
    f = f"items[{n}]"
    if not isinstance(it, dict):
        raise PlanError(f"{f} is not an object")
    iid = str(it.get("id") or "")
    if not _ID.match(iid):
        raise PlanError(f"{f}.id {iid!r} is missing or malformed")
    start = _date(it.get("start"), f + ".start")
    end = _date(it.get("end"), f + ".end", optional=True)
    if end and end < start:
        raise PlanError(f"{f}: end {end} is before start {start}")
    return {"id": iid, "title": _text(it.get("title"), f + ".title", 200, required=True),
            "start": start, "end": end, "color": _color(it.get("color"), f + ".color"),
            "important": bool(it.get("important")), "urgent": bool(it.get("urgent")),
            "done": bool(it.get("done")), "notes": _text(it.get("notes"), f + ".notes", 4000),
            "created": _date(it.get("created") or datetime.date.today().isoformat(), f + ".created")}


def clean_override(key, o):
    f = f"overrides[{key!r}]"
    if not _ID.match(str(key)) or not isinstance(o, dict):
        raise PlanError(f"{f} is malformed")
    out = {k: bool(o[k]) for k in ("important", "urgent", "done", "hidden") if k in o}
    if "color" in o:
        out["color"] = _color(o["color"], f + ".color")
    if "notes" in o:
        out["notes"] = _text(o["notes"], f + ".notes", 4000)
    return out


def validate(doc):
    """A normalised copy of `doc`, or PlanError. Unknown fields are dropped, not kept."""
    if not isinstance(doc, dict):
        raise PlanError("the plan is not an object")
    items = doc.get("items") or []
    overrides = doc.get("overrides") or {}
    if not isinstance(items, list) or not isinstance(overrides, dict):
        raise PlanError("items must be a list and overrides an object")
    if len(items) > MAX_ITEMS:
        raise PlanError(f"more than {MAX_ITEMS} items")
    clean = [clean_item(it, n) for n, it in enumerate(items)]
    ids = [it["id"] for it in clean]
    if len(ids) != len(set(ids)):
        raise PlanError("two items share an id")
    return {"version": VERSION, "rev": int(doc.get("rev") or 0), "items": clean,
            "overrides": {str(k): clean_override(k, v) for k, v in overrides.items()}}


def load():
    if not PLAN_FILE.exists():
        return empty()
    with open(PLAN_FILE, encoding="utf-8") as f:
        return validate(json.load(f))


def save(doc, expected_rev=None):
    """Validate and write atomically; returns the saved document with its new rev.

    `expected_rev` is the rev the caller last read. If the file has moved on since, nothing is
    written and Conflict carries the current document instead."""
    current = load()
    if expected_rev is not None and int(expected_rev) != current["rev"]:
        raise Conflict(current)
    doc = validate(doc)
    doc["rev"] = current["rev"] + 1
    PLAN.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=PLAN, prefix=".plan-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, PLAN_FILE)
    return doc


def new_id():
    return "u-" + datetime.datetime.now().strftime("%y%m%d%H%M%S") + secrets.token_hex(2)


def main():
    ap =argparse.ArgumentParser(description="The Timeline / To-do store (user/workspace/plan/plan.json)")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("add", help="add one item")
    a.add_argument("title")
    a.add_argument("--start", required=True)
    a.add_argument("--end")
    a.add_argument("--color", default=DEFAULT_COLOR)
    a.add_argument("--notes", default="")
    for flag in ("important", "urgent", "done"):
        a.add_argument("--" + flag, action="store_true")
    args = ap.parse_args()

    doc = load()
    if args.cmd == "add":
        doc["items"].append({"id": new_id(), "title": args.title, "start": args.start,
                             "end": args.end, "color": args.color, "important": args.important,
                             "urgent": args.urgent, "done": args.done, "notes": args.notes})
        try:
            doc = save(doc, doc["rev"])
        except PlanError as e:
            raise SystemExit(f"not added: {e}")
        print(f"added → {PLAN_FILE} (rev {doc['rev']})")
        return
    today = datetime.date.today().isoformat()
    for it in sorted(doc["items"], key=lambda i: i["start"]):
        when = it["start"] + (f" → {it['end']}" if it["end"] else "")
        flags = ("I" if it["important"] else "·") + ("U" if it["urgent"] else "·")
        state = "done" if it["done"] else ("open" if (it["end"] or it["start"]) >= today else "past, open")
        print(f"  {when:<25} {flags} {state:<11} {it['title']}")
    print(f"{len(doc['items'])} item(s), {len(doc['overrides'])} override(s) · rev {doc['rev']} · {PLAN_FILE}")


if __name__ == "__main__":
    main()
